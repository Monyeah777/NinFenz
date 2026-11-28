"""Delivery（WP-23）：把通过校验的产物打成可交付包（manifest/元数据/可选 sidecar）。

纪律（§13A L7：包完整/路径安全/可重复/sidecar 不阻塞）：
- 只有 `run.status=delivered` 且 `output-report.ok` 的产物才允许打包；否则拒收；
- 包结构：`manifest.json`（`nf-delivery/1`：files[path/role/digest/size]、output、assembly/
  validation digest、version；**不带时间戳**，同输入逐字节可复现）+ `artifact.md`；
  可选 `evidence/sidecar.json`（校验报告/装配记录摘要）；
- **路径安全**：manifest 内路径必须相对 POSIX、无 `..`/绝对路径；symlink/穿越负例即红；
- `verify()` 重算逐文件 digest → 篡改可检出；sidecar 缺失**不阻塞**（缺失只是降级）；
- 交付报告 `nf-delivery-report/1` 可复算（committed == 实时重算）。
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

MANIFEST_SCHEMA = "nf-delivery/1"
REPORT_SCHEMA = "nf-delivery-report/1"
MANIFEST = "manifest.json"
ARTIFACT = "artifact.md"
SIDECAR = "evidence/sidecar.json"
GUIDE = "修复指引："
ROLE_VOCAB = ("artifact", "manifest", "sidecar")


class DeliveryError(Exception):
    """交付拒绝（消息含修复指引）。"""

    def __init__(self, message: str, code: str = "DELIVERY-INVALID") -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical(doc: Any) -> bytes:
    return json.dumps(doc, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":")).encode("utf-8")


def _safe_rel(rel: str) -> bool:
    p = Path(str(rel))
    if p.is_absolute():
        return False
    if ".." in p.parts:
        return False
    return str(p.as_posix()) == str(rel).replace("\\", "/")


def slug(slot: str) -> str:
    return str(slot).replace("slot:", "").replace("/", "-").replace(":", "-").strip() or "slot"


def _build_meta(record: Dict[str, Any], report: Dict[str, Any]) -> Dict[str, Any]:
    """交付元信息：output / assembly digest / validation digest / slot。"""
    run_doc = record.get("run") or {}
    modules = (record.get("assembly") or {}).get("modules") or [""]
    slot_id = str(modules[0]) if modules else "slot:unknown"
    return {"output": run_doc.get("output") or {},
            "assembly_digest": _sha(_canonical(record.get("assembly") or {})),
            "validation_digest": _sha(_canonical(report)),
            "slot": slot_id or "slot:unknown"}


def _file_entry(rel: str, text: str, role: str) -> Dict[str, Any]:
    """manifest 文件条目（path/role/digest/size）。"""
    data = text.encode("utf-8")
    return {"path": rel, "role": role, "digest": _sha(data), "size": len(data)}


def _sidecar_doc(run_doc: Dict[str, Any], report: Dict[str, Any]) -> str:
    """可选证据 sidecar 文本（缺失不阻塞交付）。"""
    side = {"schema": "nf-delivery-sidecar/1",
            "note": "可选证据 sidecar；缺失不阻塞交付",
            "validation": report,
            "assembly_run": {"status": run_doc.get("status"),
                             "checks": run_doc.get("checks") or [],
                             "output": run_doc.get("output") or {}}}
    return json.dumps(side, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _dest_rel(slot: str, dest_rel: Optional[str]) -> str:
    """交付包落点（相对路径；缺省按 slot 的 slug）。"""
    return dest_rel or ("results/delivery/" + slug(slot))


def _manifest_doc(record: Dict[str, Any], meta: Dict[str, Any],
                  entries: List[Dict[str, Any]], sidecar: bool) -> Dict[str, Any]:
    """manifest（nf-delivery/1）：不带时间戳，同输入逐字节可复现。"""
    return {"schema": MANIFEST_SCHEMA, "slot": meta["slot"],
            "pipeline": str((record.get("assembly") or {}).get("pipeline") or ""),
            "version": 1, "files": sorted(entries, key=lambda x: x["path"]),
            "output": meta["output"],
            "assembly_digest": meta["assembly_digest"],
            "validation_digest": meta["validation_digest"],
            "sidecar": bool(sidecar),
            "note": "交付包不带时间戳（同输入逐字节可复现）；路径必须相对 POSIX"}


def build(record: Dict[str, Any], out: Dict[str, Any], report: Dict[str, Any],
          dest_rel: Optional[str] = None, sidecar: bool = False) -> Dict[str, Any]:
    """组装交付包 → {manifest, files:{rel:text}, dest_rel}；不落盘（write_pack 才写）。"""
    run_doc = record.get("run") or {}
    if str(run_doc.get("status")) != "delivered":
        raise DeliveryError(
            "未交付的 run 不能打包：status=%s（修复指引：先让装配运行时 delivered）"
            % run_doc.get("status"), code="NOT-DELIVERED")
    if not (report or {}).get("ok"):
        raise DeliveryError(
            "产物校验未过不能打包（修复指引：先修 output-report 红项）",
            code="OUTPUT-NOT-VALIDATED")
    content = str(((out.get("output") or {}).get("content")) or "")
    if not content.strip():
        raise DeliveryError("产物为空不能打包（修复指引：重跑 adapter 产出内容）",
                            code="EMPTY-ARTIFACT")
    meta = _build_meta(record, report)
    files: Dict[str, str] = {ARTIFACT: content}
    entries: List[Dict[str, Any]] = [_file_entry(ARTIFACT, content, "artifact")]
    if sidecar:
        files[SIDECAR] = _sidecar_doc(run_doc, report)
        entries.append(_file_entry(SIDECAR, files[SIDECAR], "sidecar"))
    manifest = _manifest_doc(record, meta, entries, sidecar)
    files[MANIFEST] = json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    meta["dest_rel"] = _dest_rel(meta["slot"], dest_rel)
    return {"manifest": manifest, "files": files, "dest_rel": meta["dest_rel"]}


def write_pack(pack: Dict[str, Any], root: str = ".") -> Path:
    from core import atomic_write
    base = Path(root) / pack["dest_rel"]
    base.mkdir(parents=True, exist_ok=True)
    for rel, text in pack["files"].items():
        if not _safe_rel(rel):
            raise DeliveryError("交付包路径不安全：%s（修复指引：只允许相对 POSIX 路径）" % rel,
                                code="PATH-UNSAFE")
        atomic_write.write_text(base / rel, text)
    return base


def _load_manifest(base: Path) -> Tuple[Optional[Dict[str, Any]], List[str]]:
    """读交付包 manifest → (doc 或 None, issues)。"""
    manifest_path = base / MANIFEST
    if not manifest_path.is_file():
        return None, ["缺 %s（修复指引：交付包必须带 manifest）" % MANIFEST]
    try:
        return json.loads(manifest_path.read_text(encoding="utf-8")), []
    except (OSError, ValueError) as exc:
        return None, ["manifest 不可解析：%s（修复指引：重打包）" % exc]


def _entry_data_issues(data: bytes, entry: Dict[str, Any], rel: str) -> List[str]:
    """单条 manifest 条目的内容面：digest / size / role 词表。"""
    issues: List[str] = []
    if _sha(data) != str(entry.get("digest")):
        issues.append("文件被篡改或 digest 不符：%s" % rel)
    if len(data) != int(entry.get("size") or 0):
        issues.append("文件大小不符：%s" % rel)
    if str(entry.get("role")) not in ROLE_VOCAB:
        issues.append("manifest role 非法：%s" % entry.get("role"))
    return issues


def _entry_issues(base: Path, entry: Dict[str, Any],
                  seen: set) -> Tuple[List[str], str]:
    """单条 manifest 条目 → (issues, artifact 摘要)。"""
    rel = str(entry.get("path") or "")
    if not _safe_rel(rel):
        return ["下载路径不安全：%s（修复指引：相对 POSIX、无 ..）" % rel], ""
    issues: List[str] = []
    if rel in seen:
        issues.append("manifest 路径重复：%s" % rel)
    seen.add(rel)
    path = base / rel
    if not path.is_file():
        return ["包内缺文件：%s" % rel], ""
    if path.is_symlink():
        return ["包内含 symlink：%s（修复指引：交付包不得含符号链接）" % rel], ""
    data = path.read_bytes()
    issues.extend(_entry_data_issues(data, entry, rel))
    return issues, (_sha(data) if str(entry.get("role")) == "artifact" else "")


def _output_digest_issues(manifest: Dict[str, Any], artifact_digest: str) -> List[str]:
    """artifact 摘要必须与 manifest.output.digest 一致。"""
    out = manifest.get("output") or {}
    if artifact_digest and str(out.get("digest")) and artifact_digest != str(out.get("digest")):
        return ["artifact digest 与 manifest.output 不一致（修复指引：重打包）"]
    return []


def _sidecar_issues(base: Path, manifest: Dict[str, Any]) -> Tuple[List[str], bool]:
    """sidecar 声明 ⇄ 在场（双向）→ (issues, 是否声明)。"""
    sidecar_present = bool(manifest.get("sidecar"))
    issues: List[str] = []
    if sidecar_present and not (base / SIDECAR).is_file():
        issues.append("manifest 声明 sidecar 但包内缺失（修复指引：重打包或去掉声明）")
    if not sidecar_present and (base / SIDECAR).is_file():
        issues.append("包内含未声明的 sidecar（修复指引：重打包并声明）")
    return issues, sidecar_present


def verify(pack_dir: str, root: str = ".") -> Tuple[List[str], Dict[str, Any]]:
    """重算校验交付包 → (issues, `nf-delivery-report/1`)。"""
    base = Path(root) / pack_dir
    issues: List[str] = []
    report: Dict[str, Any] = {"schema": REPORT_SCHEMA, "ok": False, "files": 0,
                              "sidecar": False, "issues": [], "metrics": {}}
    manifest, load_issues = _load_manifest(base)
    if manifest is None:
        report["issues"] = load_issues
        return load_issues, report
    issues.extend(load_issues)
    if str(manifest.get("schema")) != MANIFEST_SCHEMA:
        issues.append("manifest schema 必须 %s" % MANIFEST_SCHEMA)
    files = manifest.get("files") or []
    if not files:
        issues.append("manifest.files 为空")
    seen = set()
    artifact_digest = ""
    for entry in files:
        entry_issues, digest = _entry_issues(base, entry, seen)
        issues.extend(entry_issues)
        if digest:
            artifact_digest = digest
    issues.extend(_output_digest_issues(manifest, artifact_digest))
    side_issues, sidecar_present = _sidecar_issues(base, manifest)
    issues.extend(side_issues)
    report["sidecar"] = sidecar_present
    report["files"] = len(files)
    report["metrics"] = {"files": len(files), "bytes": sum(
        int(e.get("size") or 0) for e in files), "sidecar": sidecar_present}
    report["ok"] = not issues
    report["issues"] = issues
    return issues, report


def render_report(report: Dict[str, Any]) -> str:
    return json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def write_report(report: Dict[str, Any], rel: str, root: str = ".") -> Path:
    from core import atomic_write
    path = Path(root) / rel
    atomic_write.write_text(path, render_report(report))
    return path
