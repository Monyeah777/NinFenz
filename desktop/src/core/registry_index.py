"""契约注册表内容寻址（CID）索引：协议包的「内容指纹」正式产物。

背景（Wave 8 T8.2）：`protocol/repo_stats.json` 只数个数、`protocol/RECEIPTS.json` 只覆盖
**协议件**（01–07/schema/baseline），社区域包（111 个）此前没有任何可验证的内容标识——
第三方拿一份包无法判断「是不是同一个包」，联邦/分发自述无法防篡改。本模块把每个登记包
变成内容寻址对象：

- **包 manifest**（`nf-pack-manifest/1`）= `{"schema", "files": [[path, sha256], ...]}`；
  `path` 是**包内相对 POSIX 路径**，按码点序排序；`sha256` 是文件**原始字节**摘要
  （不做换行归一、不剥 BOM——「字节即内容」，任何字节改动都换 CID）。
- **CID** = `SHA-256(canonical(manifest))`，canonical = JSON `sort_keys` + 紧凑分隔符 +
  UTF-8（与仓内「规范化摘要口径」一致，见 protocol/CONFORMANCE.md）。
- **index**（`nf-registry-index/1`）= 每包一条 `{id, version, path, files_count, cid, sig, files}`；
  顶层 `root` = `SHA-256(canonical({"schema", "entries": [{id, version, files_count, cid, sig}]}))`，
  条目按 `id` 码点序排序 ⇒ **registry.json 的书写顺序不影响 root**。

`files` 字段是**自包含**的：第三方只拿 index 就能逐文件复核（发现篡改）；`--check` 也据此
给出文件级差异（索引行号 + 包内路径）。`cid` 只由 `files` 派生，因此「带 files 的 index」
与「只带 cid 的 index」在 CID 语义上等价。

**签名边界（如实声明，不假装已签名）**：`sig` 与顶层 `signature.scheme` 当前一律为空串。
本产物只提供**内容寻址 + 篡改检测**，不提供来源认证。后续接法（不在本任务内）：
1) 对 `root` 用现有 `core.attest` 的锚（hmac-sha256 / ssh-sig / sigstore-keyless）签名，
   把锚字段放进 `signature`，`sig` 存该锚文本；验证器缺位时一律 fail-closed；
2) 若要逐条可证明「某包 ∈ 全表」，复用 `core.receipts` 的 RFC 6962 域分隔 Merkle：
   叶 = `SHA-256(0x00 || canonical({"id","cid"}))`，与现有回执同一套折叠规则。
本模块**不自造密码学**、不改任何包目录、不写 protocol/schema。

真源与成员：`community/<id>/protocol.yaml` 为包自身真源；成员投影 = `desktop/src/core/
registry.json` 的 `protocols[]`（check14 已断言双源一致）。本模块只读扫描。
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from typing import Any, Dict, List, Optional, Tuple

from core import atomic_write

SCHEMA = "nf-registry-index/1"
MANIFEST_SCHEMA = "nf-pack-manifest/1"
INDEX_REL = "protocol/registry_index.json"
REGISTRY_REL = "desktop/src/core/registry.json"
COMMUNITY_REL = "community"

#: manifest 覆盖面（相对包目录）：固定两件 + 三个内容目录（递归）。**范围即契约**：
#: 包根其它文件（如 notes.md）不进 manifest，增删它们不改变 CID——避免把工作区杂物算进内容。
MANIFEST_ROOT_FILES = ("protocol.yaml", "README.md")
MANIFEST_DIRS = ("modules", "assets", "pipelines")
_SKIP_DIRS = {"__pycache__", ".git", ".pytest_cache"}

_CID_RE = re.compile(r"^[0-9a-f]{64}$")
_VERSION_RE = re.compile(r'^\s{2}version:\s*"?([^"\s#]+)"?', re.M)


def _canonical(obj: Any) -> bytes:
    """仓内统一规范化摘要口径：sort_keys + 紧凑分隔符 + UTF-8（与 CONFORMANCE 同源）。"""
    return json.dumps(obj, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":")).encode("utf-8")


def _h(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def file_sha256(path: str) -> str:
    sha = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            sha.update(chunk)
    return sha.hexdigest()


def _relposix(path: str, base: str) -> str:
    return os.path.relpath(path, base).replace(os.sep, "/")


def collect_manifest(pack_dir: str) -> List[List[str]]:
    """→ `[[path, sha256], ...]`（按 path 码点序）；只收 manifest 覆盖面内的常规文件。"""
    files: List[List[str]] = []
    for name in MANIFEST_ROOT_FILES:
        p = os.path.join(pack_dir, name)
        if os.path.isfile(p) and not os.path.islink(p):
            files.append([name, file_sha256(p)])
    for sub in MANIFEST_DIRS:
        base = os.path.join(pack_dir, sub)
        if not os.path.isdir(base) or os.path.islink(base):
            continue
        for dp, dn, fn in os.walk(base):
            dn[:] = sorted(d for d in dn if d not in _SKIP_DIRS and not os.path.islink(
                os.path.join(dp, d)))
            for f in fn:
                p = os.path.join(dp, f)
                if os.path.islink(p) or not os.path.isfile(p):
                    continue
                files.append([_relposix(p, pack_dir), file_sha256(p)])
    files.sort(key=lambda x: x[0])
    return files


def manifest_doc(files: List[List[str]]) -> Dict[str, Any]:
    return {"schema": MANIFEST_SCHEMA, "files": files}


def pack_cid(files: List[List[str]]) -> str:
    return _h(_canonical(manifest_doc(files)))


def root_of(entries: List[Dict[str, Any]]) -> str:
    """顶层 root：条目按 id 排序后取 (id, version, files_count, cid, sig) 的 canonical 摘要。"""
    material = [{"id": e["id"], "version": e["version"], "files_count": e["files_count"],
                 "cid": e["cid"], "sig": e.get("sig", "")}
                for e in sorted(entries, key=lambda e: e["id"])]
    return _h(_canonical({"schema": SCHEMA, "entries": material}))


def _read_json(path: str) -> Any:
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:                                        # noqa: BLE001 - 缺件按 issue 报
        return None


def _pack_version(pack_dir: str, fallback: str) -> Tuple[str, Optional[str]]:
    """→ (version, 问题或 None)：以包自身 protocol.yaml 为准，registry 投影仅作回退/对账。"""
    path = os.path.join(pack_dir, "protocol.yaml")
    try:
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
    except OSError as exc:
        return fallback, "读不到 protocol.yaml：%s" % exc
    m = _VERSION_RE.search(text)
    if not m:
        return fallback, "protocol.yaml 缺 package.version（回退 registry 投影 %s）" % fallback
    ver = m.group(1)
    if fallback and ver != fallback:
        return ver, "protocol.yaml version=%s ≠ registry 投影 %s（check14 双源漂移）" % (ver, fallback)
    return ver, None


def compute(root: str = ".") -> Tuple[Dict[str, Any], List[str]]:
    """只读扫描：→ (index doc, issues)。issues 非空时调用方必须 fail（写面不落盘）。"""
    issues: List[str] = []
    reg = _read_json(os.path.join(root, REGISTRY_REL))
    if not isinstance(reg, dict):
        issues.append("读不到 %s（成员投影真源缺失）" % REGISTRY_REL)
        protocols: List[Dict[str, Any]] = []
    else:
        protocols = list(reg.get("protocols") or [])
    if not isinstance(protocols, list):
        issues.append("%s protocols 不是数组" % REGISTRY_REL)
        protocols = []
    registered: Dict[str, str] = {}
    for p in protocols:
        if not isinstance(p, dict) or not p.get("id"):
            issues.append("%s protocols[] 有缺 id 的条目" % REGISTRY_REL)
            continue
        pid = str(p["id"])
        if pid in registered:
            issues.append("%s protocols[] 重复 id：%s" % (REGISTRY_REL, pid))
            continue
        registered[pid] = str(p.get("version") or "")

    comm = os.path.join(root, COMMUNITY_REL)
    on_disk: List[str] = []
    if os.path.isdir(comm):
        on_disk = sorted(d for d in os.listdir(comm)
                         if os.path.isdir(os.path.join(comm, d)) and not d.startswith("."))
    for pid in registered:
        if pid not in on_disk:
            issues.append("登记包在盘上不存在：%s/%s" % (COMMUNITY_REL, pid))
    for pid in on_disk:
        if pid not in registered:
            issues.append("盘上有未登记包目录（%s/%s 未进 registry protocols[]）"
                          % (COMMUNITY_REL, pid))

    entries: List[Dict[str, Any]] = []
    for pid in sorted(registered):
        pack_dir = os.path.join(root, COMMUNITY_REL, pid)
        if not os.path.isdir(pack_dir):
            continue
        version, ver_issue = _pack_version(pack_dir, registered[pid])
        if ver_issue:
            issues.append("%s：%s" % (pid, ver_issue))
        missing = [n for n in MANIFEST_ROOT_FILES if not os.path.isfile(os.path.join(pack_dir, n))]
        if missing:
            issues.append("%s 缺 manifest 必备文件：%s" % (pid, " / ".join(missing)))
        files = collect_manifest(pack_dir)
        entries.append({
            "id": pid,
            "version": version,
            "path": "%s/%s" % (COMMUNITY_REL, pid),
            "files_count": len(files),
            "cid": pack_cid(files),
            "sig": "",
            "files": files,
        })
    doc = {
        "schema": SCHEMA,
        "manifest_schema": MANIFEST_SCHEMA,
        "algorithm": {"cid": "sha256", "canonical": "json-sort-keys+compact+utf-8",
                      "path": "pack-relative posix，按码点序"},
        "source": {"registry": REGISTRY_REL,
                   "packs": "%s/<id>/protocol.yaml" % COMMUNITY_REL,
                   "manifest_root_files": list(MANIFEST_ROOT_FILES),
                   "manifest_dirs": list(MANIFEST_DIRS)},
        "signature": {"scheme": "",
                      "note": "未签名：本产物只做内容寻址与篡改检测；签名接法见 "
                              "desktop/src/core/registry_index.py 模块文档（attest 锚 + receipts 域分隔 Merkle）"},
        "entries": entries,
        "root": root_of(entries),
    }
    return doc, issues


def dump(doc: Dict[str, Any]) -> str:
    return json.dumps(doc, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _line_of(text: str, needle: str) -> int:
    for no, line in enumerate(text.splitlines(), 1):
        if needle in line:
            return no
    return 0


def _diff_entries(recorded: Dict[str, Any], computed: Dict[str, Any],
                  index_text: str) -> List[str]:
    """文件级差异：定位到 index 行号 + 包内路径（索引不存旧内容，故不做内容行 diff）。"""
    out: List[str] = []
    rec = {e["id"]: e for e in recorded.get("entries") or [] if isinstance(e, dict)}
    new = {e["id"]: e for e in computed.get("entries") or []}
    for pid in sorted(set(rec) - set(new)):
        out.append("registry_index.json 记录了已不存在的包：%s（跑 --write 重生成）" % pid)
    for pid in sorted(set(new) - set(rec)):
        out.append("新登记包未进索引：%s（跑 --write 重生成）" % pid)
    for pid in sorted(set(rec) & set(new)):
        a, b = rec[pid], new[pid]
        ln = _line_of(index_text, '"id": %s' % json.dumps(pid, ensure_ascii=False))
        loc = "%s:%d" % (INDEX_REL, ln) if ln else INDEX_REL
        if a.get("version") != b.get("version"):
            out.append("%s 包 %s version 变：%s → %s" % (loc, pid, a.get("version"),
                                                        b.get("version")))
        if a.get("files_count") != b.get("files_count"):
            out.append("%s 包 %s files_count 变：%s → %s" % (loc, pid, a.get("files_count"),
                                                             b.get("files_count")))
        if a.get("cid") == b.get("cid"):
            continue
        out.append("%s 包 %s 的 CID 不一致（记录 %s… → 实测 %s…）"
                   % (loc, pid, str(a.get("cid"))[:12], str(b.get("cid"))[:12]))
        af = {p: s for p, s in (a.get("files") or []) if isinstance(p, str)}
        bf = {p: s for p, s in (b.get("files") or []) if isinstance(p, str)}
        for path in sorted(set(af) - set(bf)):
            out.append("  - 文件不在索引/manifest 内：%s/%s" % (b["path"], path))
        for path in sorted(set(bf) - set(af)):
            out.append("  + 新增文件：%s/%s" % (b["path"], path))
        for path in sorted(set(af) & set(bf)):
            if af[path] != bf[path]:
                out.append("  ~ 内容已变：%s/%s" % (b["path"], path))
    return out


def verify_doc(doc: Dict[str, Any]) -> List[str]:
    """结构自证（不碰盘）：schema / 排序 / cid 形状 / files_count / root / 签名边界。"""
    issues: List[str] = []
    if doc.get("schema") != SCHEMA:
        issues.append("schema 不是 %s：%r" % (SCHEMA, doc.get("schema")))
    if doc.get("manifest_schema") != MANIFEST_SCHEMA:
        issues.append("manifest_schema 不是 %s" % MANIFEST_SCHEMA)
    entries = doc.get("entries")
    if not isinstance(entries, list):
        return issues + ["entries 不是数组"]
    ids = [e.get("id") for e in entries if isinstance(e, dict)]
    if ids != sorted(ids):
        issues.append("entries 未按 id 码点序排序（顺序不稳定 ⇒ root 不可复现）")
    if len(set(ids)) != len(ids):
        issues.append("entries 有重复 id")
    for e in entries:
        if not isinstance(e, dict):
            issues.append("entries[] 有非对象条目")
            continue
        pid = e.get("id")
        cid = e.get("cid")
        if not isinstance(cid, str) or not _CID_RE.match(cid):
            issues.append("包 %s 的 cid 不是 64 位小写 hex" % pid)
        files = e.get("files")
        if not isinstance(files, list):
            issues.append("包 %s 缺 files（自包含 manifest）" % pid)
            continue
        if e.get("files_count") != len(files):
            issues.append("包 %s files_count=%r ≠ files 长度 %d"
                          % (pid, e.get("files_count"), len(files)))
        if pack_cid(files) != cid:
            issues.append("包 %s 的 cid 与自身 files 不匹配（索引被改过）" % pid)
        if e.get("sig"):
            issues.append("包 %s 的 sig 非空但无验证器接入口（fail-closed：本版只做内容寻址）"
                          % pid)
    sig = doc.get("signature") or {}
    if sig.get("scheme"):
        issues.append("signature.scheme 非空但无验证器（fail-closed）")
    if doc.get("root") != root_of(entries):
        issues.append("顶层 root 与 entries 实时重算不一致（index 被改过）")
    return issues


def write(root: str = ".") -> Tuple[List[str], Dict[str, Any]]:
    doc, issues = compute(root)
    if issues:
        return issues, doc
    atomic_write.write_text(os.path.join(root, INDEX_REL), dump(doc))
    return issues, doc


def check(root: str = ".") -> Tuple[List[str], Dict[str, Any]]:
    doc, issues = compute(root)
    if issues:
        return issues, doc
    path = os.path.join(root, INDEX_REL)
    if not os.path.isfile(path):
        return ["缺 %s（跑 `nf registry index --write` 生成）" % INDEX_REL], doc
    try:
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        recorded = json.loads(text)
    except (OSError, ValueError) as exc:
        return ["%s 读不到/不可解析：%s" % (INDEX_REL, exc)], doc
    if not isinstance(recorded, dict):
        return ["%s 顶层不是对象" % INDEX_REL], doc
    issues.extend(verify_doc(recorded))
    if dump(recorded) != dump(doc):
        issues.extend(_diff_entries(recorded, doc, text))
        if not any("CID 不一致" in i or "files_count 变" in i or "version 变" in i
                   or "新登记包" in i or "已不存在" in i for i in issues):
            issues.append("%s 与实时重算不一致（跑 `nf registry index --write` 重生成）"
                          % INDEX_REL)
    return issues, doc


def scan(root: str = ".") -> Tuple[List[str], Dict[str, Any]]:
    """门禁入口（与 repo_stats.scan 同形）：索引 ↔ 实时重算一致。"""
    return check(root)
