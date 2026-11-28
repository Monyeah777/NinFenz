"""内容建模三件门禁：词表登记册 / 规范与说明件之分 / 数据契约登记。

机制借鉴（一句式）：SKOS 的概念方案（概念用标识符 + 标签 + 映射管理）、标准治理里的
normative / informative 二分、ODCS 与 Data Contract Specification 的数据契约要素。

判据（全部可证、零第三方依赖）：
- **词表**：每个 scheme 用 probe 指回真源（`python_attr` / `json_path` / `literal`），
  声明值必须与真源**逐项一致**；id 唯一；status 在册；值不得重复且不得与 aliases 撞车。
- **规范/说明**：两份名单交集为空；规范件必须被回执锚定**或**显式 `covered_by`（checkN 须真实存在）；
  说明件**不得**出现在回执覆盖面内（否则等于把解释当规范）。
- **数据契约**：artifact 必须存在；`quality_rule` 必须解析到**真实**的 `checkN` 或 `assertion:<id>`；
  owner / freshness 非空；status 在册。
"""
from __future__ import annotations

import importlib
import json
import re
import functools
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Tuple

VOCAB_REL = "protocol/vocabularies.json"
NORM_REL = "protocol/normative.json"
DC_REL = "protocol/data_contracts.json"
RECEIPTS_REL = "protocol/RECEIPTS.json"
VOCAB_SCHEMA = "nf-vocabularies/1"
NORM_SCHEMA = "nf-normative/1"
DC_SCHEMA = "nf-data-contracts/1"
_CHECK_RE = re.compile(r"^check(\d+)$")
_SAFE_PROBE_MODULE = re.compile(r"^core(?:\.[A-Za-z_][A-Za-z0-9_]*)+$")
_SAFE_PROBE_ATTR = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")


def _read(root: str, rel: str) -> Dict[str, Any]:
    p = Path(root) / rel
    return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else {}


def _as_values(obj: Any) -> List[str]:
    if isinstance(obj, dict):
        return [str(k) for k in obj]
    if isinstance(obj, (list, tuple)):
        return [str(x) for x in obj]
    return []


@functools.lru_cache(maxsize=64)
def _python_probe_values(module: str, attr: str) -> tuple:
    mod = importlib.import_module(module)
    return tuple(_as_values(getattr(mod, attr)))


def _python_attr_probe(probe: Dict[str, Any]) -> Tuple[List[str], str]:
    """python_attr 探针：模块/属性必须落安全白名单形态，取不到即带说明返回。"""
    module = str(probe.get("module") or "")
    attr = str(probe.get("attr") or "")
    if not _SAFE_PROBE_MODULE.fullmatch(module) or not _SAFE_PROBE_ATTR.fullmatch(attr):
        return [], "python_attr 模块/属性不在安全白名单形态：%s.%s" % (module, attr)
    try:
        return list(_python_probe_values(module, attr)), "python_attr"
    except (ImportError, AttributeError, TypeError) as exc:
        return [], "python_attr 取不到：%s.%s（%s）" % (module, attr, exc)


def _json_path_probe(root: str, probe: Dict[str, Any]) -> Tuple[List[str], str]:
    """json_path 探针：沿点路径取值，断链即带说明返回。"""
    doc: Any = _read(root, str(probe.get("file") or ""))
    for part in str(probe.get("path") or "").split("."):
        if not isinstance(doc, dict) or part not in doc:
            return [], "json_path 断链：%s" % probe.get("path")
        doc = doc[part]
    return _as_values(doc), "json_path"


def _probe(root: str, probe: Dict[str, Any]) -> Tuple[List[str], str]:
    kind = str(probe.get("kind") or "")
    if kind == "literal":
        return [], "literal（以本册为准）"
    if kind == "python_attr":
        return _python_attr_probe(probe)
    if kind == "json_path":
        return _json_path_probe(root, probe)
    return [], "未知 probe.kind：%s" % kind


def _scheme_values_issues(s: Dict[str, Any], sid: str) -> Tuple[List[str], List[str]]:
    """词表值面：至少两个值、不重复、alias 不撞车 → (issues, vals)。"""
    issues: List[str] = []
    vals = [str(v) for v in (s.get("values") or [])]
    if len(vals) < 2:
        issues.append("词表 %s 少于两个值（不成词表）" % sid)
    if len(set(vals)) != len(vals):
        issues.append("词表 %s 值重复" % sid)
    for a in (s.get("aliases") or []):
        if str(a) in vals:
            issues.append("词表 %s 的 alias 与值撞车：%s" % (sid, a))
    return issues, vals


def _scheme_probe_issues(root: str, s: Dict[str, Any], sid: str, kinds: tuple,
                         vals: List[str]) -> List[str]:
    """词表探针面：kind 在册、真源可取、与册逐项一致。"""
    issues: List[str] = []
    probe = s.get("probe") if isinstance(s.get("probe"), dict) else {}
    if str(probe.get("kind")) not in kinds:
        issues.append("词表 %s 的 probe.kind 不在册：%s" % (sid, probe.get("kind")))
        return issues
    try:
        live, note = _probe(root, probe)
    except (ImportError, AttributeError, TypeError) as exc:
        live, note = [], "探针异常：%s" % exc
    if str(probe.get("kind")) == "literal":
        return issues
    if not live:
        issues.append("词表 %s 的真源取不到（%s）" % (sid, note))
        return issues
    if sorted(live) != sorted(vals):
        issues.append("词表 %s 与真源漂移：册=%s 真源=%s"
                      % (sid, "/".join(sorted(vals)), "/".join(sorted(live))))
    return issues


def _scheme_issues(root: str, s: Dict[str, Any], statuses: tuple, kinds: tuple,
                   seen: set) -> List[str]:
    """单 scheme：id 唯一 / status 在册 / 值面 / 探针面。"""
    issues: List[str] = []
    sid = str(s.get("id") or "")
    if sid in seen:
        issues.append("词表 id 重复：%s" % sid)
    seen.add(sid)
    if str(s.get("status")) not in statuses:
        issues.append("词表 %s status 越词表：%s" % (sid, s.get("status")))
    value_issues, vals = _scheme_values_issues(s, sid)
    issues.extend(value_issues)
    issues.extend(_scheme_probe_issues(root, s, sid, kinds, vals))
    return issues


def _literal_count(schemes) -> int:
    """probe.kind == literal 的 scheme 数（stats 用）。"""
    return sum(1 for s in (schemes or [])
               if str((s.get("probe") or {}).get("kind")) == "literal")


def verify_vocabularies(root: str = ".") -> Tuple[List[str], List[str], Dict[str, Any]]:
    issues: List[str] = []
    warns: List[str] = []
    doc = _read(root, VOCAB_REL)
    if not doc:
        return ["缺词表登记册 %s" % VOCAB_REL], warns, {}
    if str(doc.get("schema") or "") != VOCAB_SCHEMA:
        issues.append("词表登记册 schema 不匹配（期望 %s）" % VOCAB_SCHEMA)
    statuses = tuple(doc.get("status_vocabulary") or ())
    if sorted(statuses) != ["active", "deprecated"]:
        issues.append("status 词表与判据不一致（期望 active/deprecated）")
    kinds = tuple(doc.get("probe_kinds") or ())
    seen = set()
    for s in doc.get("schemes") or []:
        issues.extend(_scheme_issues(root, s, statuses, kinds, seen))
    stats = {"schemes": len(seen),
             "literal": _literal_count(doc.get("schemes"))}
    return issues, warns, stats


def _receipt_ids(root: str) -> set:
    doc = _read(root, RECEIPTS_REL)
    return {str(e.get("id")) for e in (doc.get("entries") or [])}


def _check_ids(root: str) -> set:
    """verify.sh 里已定义的 checkN 编号集合。"""
    r = Path(root)
    verify_sh = (r / "verify.sh").read_text(encoding="utf-8") if (r / "verify.sh").is_file() else ""
    return set(re.findall(r"^check(\d+)\(\)\{", verify_sh, re.M))


def _covered_issues(rel: str, covered: List[str], checks: set) -> List[str]:
    """covered_by 里的 checkN 必须真实存在。"""
    issues: List[str] = []
    for c in covered:
        m = _CHECK_RE.match(c)
        if m and m.group(1) not in checks:
            issues.append("规范件 %s 的 covered_by 指向不存在的 check：%s" % (rel, c))
    return issues


def _norm_entry_issues(r: Path, entry: Dict[str, Any], checks: set,
                       receipts: set) -> Tuple[List[str], str]:
    """单条规范件：path 在场 + 回执锚定或 covered_by 可核 → (issues, rel)。"""
    issues: List[str] = []
    rel = str(entry.get("path") or "")
    if not rel:
        return ["规范件条目缺 path"], rel
    if not (r / rel).is_file():
        return ["规范件不存在：%s" % rel], rel
    if rel in receipts:
        return issues, rel
    covered = [str(c) for c in (entry.get("covered_by") or [])]
    if not covered:
        return ["规范件既未被回执锚定也无 covered_by：%s"
                "（修复指引：跑 nf receipts --write，或显式声明 covered_by）" % rel], rel
    issues.extend(_covered_issues(rel, covered, checks))
    return issues, rel


def _normative_entries_issues(r: Path, items, checks: set,
                              receipts: set) -> Tuple[List[str], List[str]]:
    """规范件名单逐条 → (issues, norm_paths)。"""
    issues: List[str] = []
    norm_paths = []
    for item in items:
        entry = item if isinstance(item, dict) else {"path": str(item)}
        entry_issues, rel = _norm_entry_issues(r, entry, checks, receipts)
        issues.extend(entry_issues)
        norm_paths.append(rel)
    return issues, norm_paths


def _informative_hits(root: str, globs: List[str]) -> Tuple[List[str], set]:
    """说明件 glob → (warns, 命中相对路径集合)。"""
    warns: List[str] = []
    r = Path(root)
    info_hits: set = set()
    for g in globs:
        pat = g + "/*" if g.endswith("/**") else g
        hits = [p for p in r.glob(pat) if p.is_file()] if any(
            ch in pat for ch in "*?[") else ([r / pat] if (r / pat).is_file() else [])
        if not hits:
            warns.append("说明件名单的条目无匹配（可能写错）：%s" % g)
        for p in hits:
            info_hits.add(p.relative_to(r).as_posix())
    return warns, info_hits


def _tracked_filter(root: str, info_hits: set) -> set:
    """说明件计数只认 git tracked 面（git 不可用则保持原样）。"""
    tracked = _tracked(root)
    if tracked is not None:
        return {rel for rel in info_hits if rel in tracked}
    return info_hits


def _informative_coverage_issues(norm_paths: List[str], info_hits: set,
                                 receipts: set) -> List[str]:
    """说明件不得被回执锚定；同一件不得既列规范又列说明。"""
    issues: List[str] = []
    for rel in sorted(info_hits):
        if rel in receipts:
            issues.append("说明件被回执锚定（等于把解释当规范）：%s" % rel)
    for rel in sorted(set(norm_paths) & info_hits):
        issues.append("同一件既列规范又列说明：%s" % rel)
    return issues


def verify_normative(root: str = ".") -> Tuple[List[str], List[str], Dict[str, Any]]:
    issues: List[str] = []
    warns: List[str] = []
    doc = _read(root, NORM_REL)
    if not doc:
        return ["缺规范/说明件名单 %s" % NORM_REL], warns, {}
    if str(doc.get("schema") or "") != NORM_SCHEMA:
        issues.append("规范件名单 schema 不匹配（期望 %s）" % NORM_SCHEMA)
    r = Path(root)
    checks = _check_ids(root)
    receipts = _receipt_ids(root)
    entry_issues, norm_paths = _normative_entries_issues(
        r, doc.get("normative") or [], checks, receipts)
    issues.extend(entry_issues)
    info_globs = [str(g) for g in (doc.get("informative") or [])]
    warns, info_hits = _informative_hits(root, info_globs)
    info_hits = _tracked_filter(root, info_hits)
    issues.extend(_informative_coverage_issues(norm_paths, info_hits, receipts))
    stats = {"normative": len(norm_paths), "informative_files": len(info_hits),
             "receipts": len(receipts)}
    return issues, warns, stats


def _assertion_ids(root: str) -> set:
    """assertions.json 里登记的断言 id 集合。"""
    return {str(a.get("id")) for a in
            (_read(root, "protocol/assertions.json").get("assertions") or [])}


def _contract_artifact_issues(r: Path, c: Dict[str, Any], cid: str,
                              statuses: tuple) -> List[str]:
    """契约面：artifact 在场 + status 在册 + owner/freshness 非空。"""
    issues: List[str] = []
    art = str(c.get("artifact") or "")
    if not art or not (r / art).is_file():
        issues.append("契约 %s 的 artifact 不存在：%s" % (cid, art or "(缺)"))
    if str(c.get("status")) not in statuses:
        issues.append("契约 %s status 越词表：%s" % (cid, c.get("status")))
    if not str(c.get("owner") or "").strip():
        issues.append("契约 %s 缺 owner（无人认领的契约不许登记）" % cid)
    if not str(c.get("freshness") or "").strip():
        issues.append("契约 %s 缺 freshness（重建动作必须写明）" % cid)
    return issues


def _contract_rule_issues(c: Dict[str, Any], cid: str, checks: set,
                          assertion_ids: set) -> List[str]:
    """quality_rule 必须解析到真实 checkN 或 assertion:<id>。"""
    issues: List[str] = []
    rule = str(c.get("quality_rule") or "")
    if rule.startswith("check"):
        if rule[5:] not in checks:
            issues.append("契约 %s 的 quality_rule 指向不存在的 check：%s" % (cid, rule))
    elif rule.startswith("assertion:"):
        if rule.split(":", 1)[1] not in assertion_ids:
            issues.append("契约 %s 的 quality_rule 指向不存在的断言：%s" % (cid, rule))
    else:
        issues.append("契约 %s 的 quality_rule 无法解析（须 checkN 或 assertion:<id>）：%s"
                      % (cid, rule or "(缺)"))
    return issues


def _contract_issues(r: Path, c: Dict[str, Any], checks: set, assertion_ids: set,
                     seen: set, statuses: tuple) -> List[str]:
    """单条数据契约：id 唯一 + artifact 面 + quality_rule 面。"""
    issues: List[str] = []
    cid = str(c.get("id") or "")
    if cid in seen:
        issues.append("契约 id 重复：%s" % cid)
    seen.add(cid)
    issues.extend(_contract_artifact_issues(r, c, cid, statuses))
    issues.extend(_contract_rule_issues(c, cid, checks, assertion_ids))
    return issues


def verify_contracts(root: str = ".") -> Tuple[List[str], List[str], Dict[str, Any]]:
    issues: List[str] = []
    warns: List[str] = []
    doc = _read(root, DC_REL)
    if not doc:
        return ["缺数据契约登记 %s" % DC_REL], warns, {}
    if str(doc.get("schema") or "") != DC_SCHEMA:
        issues.append("数据契约登记 schema 不匹配（期望 %s）" % DC_SCHEMA)
    statuses = tuple(doc.get("status_vocabulary") or ())
    prefixes = tuple(doc.get("rule_prefixes") or ())
    if prefixes != ("check", "assertion:"):
        issues.append("rule_prefixes 与判据不一致（期望 check / assertion:）")
    r = Path(root)
    checks = _check_ids(root)
    assertion_ids = _assertion_ids(root)
    seen = set()
    for c in doc.get("contracts") or []:
        issues.extend(_contract_issues(r, c, checks, assertion_ids, seen, statuses))
    stats = {"contracts": len(seen), "checks_seen": len(checks),
             "assertions_seen": len(assertion_ids)}
    return issues, warns, stats


def scan(root: str = ".") -> Tuple[List[str], List[str], Dict[str, Any]]:
    """三件聚合 → (issues, warns, stats)。"""
    issues: List[str] = []
    warns: List[str] = []
    stats: Dict[str, Any] = {}
    for name, fn in (("vocabularies", verify_vocabularies),
                     ("normative", verify_normative),
                     ("data_contracts", verify_contracts)):
        i, w, s = fn(root)
        issues += i
        warns += w
        stats[name] = s
    return issues, warns, stats


def _tracked(root: str) -> set | None:
    """git 追踪面（可复现口径）：说明件计数只认 tracked 文件。

    动机（2026-11-15 实测）：informative globs 覆盖 results/** 等路径，本地未跟踪件
    （如 results/trust/rekor-public-key.pem，被 .gitignore 吸收）会让 conformance root
    依赖本机状态——同一 commit 在干净 clone 上算出不同的 root（BASELINE-F-001）。
    说明件是仓库内容，不应由本机未跟踪文件改变计数；git 不可用时返回 None（保持旧行为）。
    """
    try:
        out = subprocess.run(["git", "-C", str(root), "ls-files", "-z"],
                             capture_output=True, text=True, timeout=60)
    except Exception:
        return None  # best-effort 显式忽略（不可读/不可用属预期，由上层门禁另行报出）
    if out.returncode != 0:
        return None
    return {p for p in out.stdout.split("\0") if p}
