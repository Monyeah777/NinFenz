"""T6.2 · 真实模型执行记录（M2 证据）校验与落盘（nf-exec-record/1）。

诚实边界（与 `core.domain_maturity` 的 M2 判据同源，本模块不改它，只复用其工具信号表）：
- executor 是脚本/agent/装配器（工具）→ 不算真实模型执行；
- artifact 缺失 / 不在仓内 / sha256 不可复算 / check_rc!=0 → 不算；
- `template: true` 显式标记「未执行」，校验返回 not-executed，**不构成 M2 证据**；
- 真实 M2 需要外部模型 API（本仓不含任何 key；测试不伪造真实记录）。

CLI 入口：`nf domain record [--check FILE] [--write FILE] [--json]`（见 scripts/nf.py）。
"""
from __future__ import annotations

import hashlib
import json as _json
import os
import re
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from core import atomic_write, json_doc, schema_lint

SCHEMA_NAME = "exec_record.schema.json"
SCHEMA_ID = "nf-exec-record/1"
RECORDS_REL = "protocol/exec_records"
TEMPLATE_NAME = "_TEMPLATE.json"
REGISTRY_REL = "desktop/src/core/registry.json"

RUN_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{2,63}$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
DIGEST_RE = re.compile(r"^(?:sha256:)?([0-9a-f]{64})$")
_ABS_PATH_RE = re.compile(r"^(?:[A-Za-z]:[\\/]|\\\\|/)")
_BAD_ARTIFACT = re.compile(r"[*?\[\]（）()<>]")


def _tool_markers() -> Tuple[str, ...]:
    """工具/装配器信号表：单一真相在 `domain_maturity._TOOL_MARKERS`（不改那份，只读复用）。"""
    from core import domain_maturity as dmx
    return tuple(dmx._TOOL_MARKERS)  # noqa: SLF001 —— 同一判据只在 dm 定义一次


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _registry_packages(root: Path) -> List[str]:
    reg = json_doc.load(root / REGISTRY_REL, dict, what=REGISTRY_REL)
    return [str(p.get("id")) for p in reg.get("protocols") or [] if p.get("id")]


def _resolve_artifact(root: Path, rel: Any) -> Tuple[Optional[Path], str]:
    """artifact → (存在的仓内文件, 原因)。只认单个仓内相对路径（可复算/可移植）。"""
    text = str(rel or "").strip()
    if not text:
        return None, "artifact 缺失"
    if _ABS_PATH_RE.match(text) or os.path.isabs(text):
        return None, "artifact 须为仓内相对路径（绝对路径不可复算/不可移植）：%r" % text
    if _BAD_ARTIFACT.search(text):
        return None, "artifact 不是单个文件路径（含通配/说明文字）：%r" % text
    if ".." in Path(text).parts:
        return None, "artifact 不得含 .. 越界段：%r" % text
    root_p = root.resolve()
    cand = (root_p / text).resolve()
    if not (cand == root_p or root_p in cand.parents):
        return None, "artifact 解析后不在仓内：%r" % text
    if not cand.is_file():
        return None, "artifact 不在盘：%r" % text
    return cand, "仓内相对路径"


def _is_template(record: Dict[str, Any], source_path: str = "") -> bool:
    if record.get("template") is True:
        return True
    return os.path.basename(str(source_path or "")) == TEMPLATE_NAME


def _result(status: str, issues: List[str], *, source_path: str = "",
            record: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    record = record if isinstance(record, dict) else {}
    codes = [i.split("：", 1)[0] for i in issues]
    verdict = {"pass": "PASS", "fail": "FAIL", "not-executed": "NOT_EXECUTED"}[status]
    ex = record.get("executor") if isinstance(record.get("executor"), dict) else {}
    art = record.get("artifact") if isinstance(record.get("artifact"), dict) else {}
    return {
        "kind": "domain-record",
        "status": status,
        "verdict": verdict,
        "path": str(source_path or ""),
        "run_id": str(record.get("run_id") or ""),
        "template": _is_template(record, source_path),
        "issues": issues,
        "codes": codes,
        "summary": {
            "package": str(record.get("package") or ""),
            "date": str(record.get("date") or ""),
            "executor": "%s/%s@%s" % (ex.get("provider", ""), ex.get("model", ""),
                                      ex.get("version", "")),
            "artifact": str(art.get("path") or ""),
            "sha256": str(art.get("sha256") or ""),
            "check_rc": record.get("check_rc"),
        },
    }


def _executor_issues(record: Dict[str, Any]) -> List[str]:
    ex = record.get("executor")
    if not isinstance(ex, dict):
        return ["executor_not_model：executor 须为 {model, provider, version} 对象"]
    missing = [k for k in ("model", "provider", "version")
               if not str(ex.get(k) or "").strip()]
    if missing:
        return ["executor_not_model：executor 缺 %s（模型标识/版本不可缺）"
                % "、".join(missing)]
    text = " ".join(str(ex.get(k)) for k in ("model", "provider", "version")).lower()
    hits = [m for m in _tool_markers() if m in text]
    if hits:
        return ["executor_not_model：executor 命中工具/装配器信号 %r"
                "（脚本/agent/装配器不算真实模型执行）" % hits[0]]
    return []


def _date_issues(record: Dict[str, Any]) -> List[str]:
    raw = str(record.get("date") or "").strip()
    if not DATE_RE.match(raw):
        return ["date_invalid：执行日期须 YYYY-MM-DD：%r" % raw]
    try:
        when = date.fromisoformat(raw)
    except ValueError:
        return ["date_invalid：执行日期不是合法日历日：%r" % raw]
    if when > date.today():
        return ["date_invalid：执行日期晚于今天（%s）——未来日期视为伪造面" % raw]
    return []


def _artifact_issues(root: Path, record: Dict[str, Any]) -> List[str]:
    art = record.get("artifact")
    if not isinstance(art, dict):
        return ["artifact_missing：artifact 须为 {path, sha256} 对象"]
    path, why = _resolve_artifact(root, art.get("path"))
    if path is None:
        if "不在盘" in why or "缺失" in why:
            code = "artifact_missing"
        elif "仓内" in why or "越界" in why or "绝对路径" in why:
            code = "artifact_outside_repo"
        else:
            code = "artifact_invalid"
        return ["%s：%s" % (code, why)]
    declared = str(art.get("sha256") or "").strip().lower()
    m = re.fullmatch(r"([0-9a-f]{64})", declared)
    if not m:
        return ["sha256_invalid：artifact.sha256 须为 64 位小写十六进制"]
    actual = _sha256_file(path)
    if actual != m.group(1):
        return ["sha256_mismatch：artifact 实测 sha256=%s… ≠ 记录 %s…（修复指引：重算或换正确 artifact）"
                % (actual[:12], m.group(1)[:12])]
    return []


def validate_record(root: Any = ".", record: Any = None, *,
                    source_path: str = "") -> Dict[str, Any]:
    """校验一条记录 → 结果 dict（status ∈ pass / fail / not-executed）。"""
    root_p = Path(root)
    if not isinstance(record, dict):
        return _result("fail", ["schema_invalid：记录顶层须为 JSON 对象"], source_path=source_path)
    if _is_template(record, source_path):
        return _result("not-executed", [], source_path=source_path, record=record)
    issues: List[str] = []
    schema = schema_lint.load_schema(str(root_p), SCHEMA_NAME)
    if schema is None:
        issues.append("schema_missing：缺 protocol/schema/%s（修复指引：本件随 T6.2 交付）"
                      % SCHEMA_NAME)
    else:
        issues += ["schema_invalid：%s" % v for v in
                   schema_lint.subset_validate(record, schema)]
    if str(record.get("schema") or "") != SCHEMA_ID:
        issues.append("schema_invalid：schema 须为 %r" % SCHEMA_ID)
    run_id = str(record.get("run_id") or "")
    if not RUN_ID_RE.match(run_id):
        issues.append("run_id_invalid：run_id 须匹配 %s：%r" % (RUN_ID_RE.pattern, run_id))
    pkg = str(record.get("package") or "")
    try:
        packages = _registry_packages(root_p)
    except ValueError as exc:
        issues.append("registry_unreadable：%s" % exc)
        packages = []
    if pkg and pkg not in packages:
        issues.append("package_unregistered：package %r 不在 registry.json protocols[] 在册"
                      "（修复指引：先登记域包，再记录真实执行）" % pkg)
    issues += _executor_issues(record)
    issues += _date_issues(record)
    issues += _artifact_issues(root_p, record)
    rc = record.get("check_rc")
    if isinstance(rc, bool) or not isinstance(rc, int) or rc != 0:
        issues.append("check_rc_nonzero：check_rc 须为整数 0（实为 %r）——机检未过不算真实执行" % (rc,))
    digest = str(record.get("contract_digest") or "")
    if not DIGEST_RE.match(digest.strip().lower()):
        issues.append("contract_digest_invalid：contract_digest 须为 sha256（可带 sha256: 前缀）")
    profile = str(record.get("profile") or "").strip()
    if not profile:
        issues.append("profile_missing：profile（质量门口径）不得为空")
    brief = str(record.get("brief") or "").strip()
    if not brief:
        issues.append("brief_missing：brief（本次执行目标）不得为空")
    return _result("fail" if issues else "pass", issues,
                   source_path=source_path, record=record)


def _resolve_input(root: Path, given: str) -> Path:
    p = Path(given)
    if p.is_absolute():
        return p
    cwd_p = Path.cwd() / p
    if cwd_p.is_file():
        return cwd_p
    return root / p


def _portable_path(root: Path, path: Path) -> str:
    """机器面路径可移植：仓内 → 仓库相对 POSIX；仓外 → 只给文件名（不回吐本机绝对路径）。"""
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except (OSError, ValueError):
        return path.name


def check_file(root: Any, path: str) -> Dict[str, Any]:
    """读记录文件并校验（不可读 = fail，带修复指引）。"""
    root_p = Path(root)
    target = _resolve_input(root_p, path)
    try:
        record = json_doc.load(target, dict, what=str(target))
    except ValueError as exc:
        return _result("fail", ["record_unreadable：%s" % exc],
                       source_path=_portable_path(root_p, target))
    return validate_record(root_p, record, source_path=_portable_path(root_p, target))


def scan(root: Any = ".") -> Dict[str, Any]:
    """扫描 protocol/exec_records/*.json → 汇总（模板计 not-executed，不计 PASS/FAIL）。"""
    root_p = Path(root)
    d = root_p / RECORDS_REL
    rows: List[Dict[str, Any]] = []
    if d.is_dir():
        for p in sorted(d.glob("*.json")):
            try:
                rel = p.relative_to(root_p).as_posix()
            except ValueError:                  # root 为 "." 等非包含形态时退回原路径
                rel = str(p)
            rows.append(check_file(root_p, rel))
    counts = {"pass": 0, "fail": 0, "not-executed": 0}
    for r in rows:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    return {"kind": "domain-record-scan", "dir": RECORDS_REL, "records": rows,
            "count": len(rows), **counts}


def write_record(root: Any, path: str) -> Dict[str, Any]:
    """校验通过后落盘 `protocol/exec_records/<run_id>.json`（原子写；同内容幂等）。"""
    root_p = Path(root)
    res = check_file(root_p, path)
    if res["status"] != "pass":
        res["written"] = False
        return res
    run_id = res["run_id"]
    target = root_p / RECORDS_REL / ("%s.json" % run_id)
    source = _resolve_input(root_p, path)
    try:
        payload = json_doc.load(source, dict, what=str(source))
    except ValueError as exc:                      # 理论不可达（check_file 已读过）
        res["status"] = "fail"
        res["issues"].append("record_unreadable：%s" % exc)
        res["written"] = False
        return res
    text = _json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if target.is_file():
        if target.read_text(encoding="utf-8") == text:
            res.update({"written": True, "target": target.relative_to(root_p).as_posix(),
                        "idempotent": True})
            return res
        res["status"] = "fail"
        res["issues"].append("record_exists：目标 %s 已存在且内容不同（执行记录不可静默覆盖；"
                             "修复指引：换 run_id 或先人工核对旧记录）"
                             % target.relative_to(root_p).as_posix())
        res["written"] = False
        return res
    target.parent.mkdir(parents=True, exist_ok=True)
    atomic_write.write_text(str(target), text)
    res.update({"written": True, "target": target.relative_to(root_p).as_posix(),
                "idempotent": False})
    return res


def run(root: Any = ".", check: Optional[str] = None, write: Optional[str] = None,
        as_json: bool = False) -> int:
    """CLI 内核：--check / --write / 无参扫描。返回退出码（pass/未执行 = 0，fail = 1）。"""
    if check:
        res = check_file(root, check)
        return _emit(res, as_json)
    if write:
        res = write_record(root, write)
        return _emit(res, as_json)
    res = scan(root)
    if as_json:
        print(_json.dumps(res, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print("== nf domain record（扫描 %s）==" % RECORDS_REL)
        for r in res["records"]:
            mark = {"pass": "PASS", "fail": "FAIL", "not-executed": "未执行"}[r["status"]]
            print("  [%s] %s%s" % (mark, r.get("run_id") or r.get("path"),
                                   "" if r["status"] != "fail" else "（%d issue）"
                                   % len(r["issues"])))
        print("  —— %d 条：PASS %d · FAIL %d · 未执行 %d"
              % (res["count"], res["pass"], res["fail"], res["not-executed"]))
    return 1 if res.get("fail") else 0


def _emit(res: Dict[str, Any], as_json: bool) -> int:
    if as_json:
        print(_json.dumps(res, ensure_ascii=False, indent=2, sort_keys=True))
    elif res["status"] == "not-executed":
        print("== nf domain record ==")
        print("  状态：未执行（模板/示例，不构成 M2 证据）")
        print("  真实 M2 需要外部模型 API key + 一次真实运行；复制模板填真实值后去掉 template 字段再校验。")
    elif res["status"] == "pass":
        s = res["summary"]
        print("== nf domain record %s ==" % ("--write" if res.get("written") else "--check"))
        print("  状态：PASS（真实模型执行记录，artifact sha256 可复算 · check_rc=0）")
        print("  run_id：%s｜package：%s｜date：%s" % (res["run_id"], s["package"], s["date"]))
        print("  executor：%s" % s["executor"])
        print("  artifact：%s｜check_rc=%s" % (s["artifact"], s["check_rc"]))
        if res.get("written"):
            print("  ✓ 已落盘：%s%s" % (res.get("target"), "（同内容幂等）"
                                       if res.get("idempotent") else ""))
    else:
        print("== nf domain record ==", end="\n")
        print("  状态：FAIL（%d 项）" % len(res["issues"]))
        for issue in res["issues"]:
            print("  [FAIL] %s" % issue)
    return 0 if res["status"] in ("pass", "not-executed") else 1
