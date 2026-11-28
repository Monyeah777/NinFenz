"""关键词/扩展口登记与检查（WP-52，G5）：§17 标签表/索引/中英对照 + §18 OPEN 扩展口。

判据（`nf keywords --check` / verify check57）：
- 标签只能本表定义：文档里用到的 `[TAG]` 必须在册（前缀标签按前缀匹配），否则=孤儿标签红；
- `OPEN-*` 不得静默关闭：`open` 必须有 owner+interface；`closed` 必须有**在场证据**；
- 禁用词（已认证/合规认证/不可抵赖/零缺陷等）出现时必须有 `[HONESTY]` 或否定语境；
- 中英对照覆盖方案要求的最小术语集；登记件自身 schema/词表/owner 完整。
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List

SCHEMA = "nf-keywords/1"
REL = "protocol/keywords.json"
GUIDE = "修复指引："
STATUSES = ("open", "partial", "closed")
TAG_PATTERN = re.compile(r"\[([A-Z][A-Z0-9-]*)\]")


class KeywordsError(Exception):
    """关键词登记/检查错误（消息含修复指引）。"""

    def __init__(self, message: str, code: str = "KEYWORDS-INVALID") -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def load_registry(root: str = ".") -> Dict[str, Any]:
    path = Path(root) / REL
    if not path.is_file():
        raise KeywordsError("缺 %s（修复指引：补关键词登记）" % REL, code="REGISTRY-MISSING")
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise KeywordsError("%s 不可解析：%s（修复指引：修 JSON）" % (REL, exc)) from exc
    if str(doc.get("schema")) != SCHEMA:
        raise KeywordsError("registry schema 必须 %s" % SCHEMA)
    return doc


def _defined_tags(reg: Dict[str, Any]) -> Dict[str, bool]:
    out: Dict[str, bool] = {}
    for tag in reg.get("tags") or []:
        out[str(tag.get("id"))] = bool(tag.get("prefix"))
    return out


def _tag_known(tag: str, defined: Dict[str, bool]) -> bool:
    if tag in defined and not defined[tag]:
        return True
    for base, is_prefix in defined.items():
        if is_prefix and base.endswith("-*") and tag.startswith(base[:-1]):
            return True
    return False


def used_tags(root: str) -> Dict[str, List[str]]:
    reg = load_registry(root)
    out: Dict[str, List[str]] = {}
    for rel in reg.get("scan_docs") or []:
        path = Path(root) / rel
        if not path.is_file():
            continue
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            for match in TAG_PATTERN.finditer(line):
                out.setdefault(match.group(1), []).append("%s:%d" % (rel, lineno))
    return out


def _tag_table_issues(tags: List[Any]) -> List[str]:
    issues: List[str] = []
    ids = [str(t.get("id")) for t in tags]
    if len(ids) != len(set(ids)):
        issues.append("标签 id 重复")
    if len(tags) < 12:
        issues.append("标签表少于 12（§17.2 标签表应齐全）")
    for tag in tags:
        tid = str(tag.get("id"))
        if not str(tag.get("meaning") or "").strip():
            issues.append("%s 缺 meaning" % tid)
        if not str(tag.get("owner") or "").strip():
            issues.append("%s 缺 owner" % tid)
        if str(tag.get("status")) not in ("active", "planned", "retired"):
            issues.append("%s status 非法" % tid)
    return issues


def _orphan_tag_issues(defined: set, used: Dict[str, List[str]]) -> List[str]:
    issues: List[str] = []
    for tag, places in used.items():
        if not _tag_known(tag, defined):
            issues.append("孤儿标签 [%s]（%s）%s" % (tag, places[0],
                                                    "修复指引：在 protocol/keywords.json 登记"))
    return issues


def _index_issues(reg: Dict[str, Any], defined: set) -> List[str]:
    issues: List[str] = []
    index = reg.get("keyword_index") or []
    if not index:
        issues.append("缺 keyword_index")
    for item in index:
        tag = str(item.get("tag"))
        if not _tag_known(tag, defined):
            issues.append("keyword_index 引用未登记标签：%s" % tag)
        if not item.get("keywords"):
            issues.append("%s 缺 keywords" % tag)
        if not str(item.get("owner") or ""):
            issues.append("%s 缺 owner" % tag)
    return issues


def _synonym_issues(reg: Dict[str, Any]) -> List[str]:
    pairs = {(str(s.get("cn")), str(s.get("en"))) for s in (reg.get("synonyms") or [])}
    issues: List[str] = []
    for cn, en in (("生产装配", "assembly"), ("规范", "spec"), ("契约", "contract"),
                   ("治理", "governance"), ("证据", "evidence"), ("信任等级", "trust level"),
                   ("不可抵赖", "non-repudiation")):
        if (cn, en) not in pairs:
            issues.append("中英对照缺：%s/%s" % (cn, en))
    return issues


def _closed_evidence_issues(opening: Dict[str, Any], oid: str, root: str) -> List[str]:
    issues: List[str] = []
    evidence = opening.get("evidence") or []
    if not evidence:
        issues.append("%s 标 closed 但无证据（修复指引：给在场证据或退回 open）" % oid)
    for rel in evidence:
        if not (Path(root) / rel).exists():
            issues.append("%s 证据不在场：%s" % (oid, rel))
    return issues


def _opening_row_issues(opening: Dict[str, Any], root: str) -> List[str]:
    oid = str(opening.get("id"))
    status = str(opening.get("status"))
    issues: List[str] = []
    if not oid.startswith("OPEN-"):
        issues.append("%s 必须以 OPEN- 开头" % oid)
    if status not in STATUSES:
        issues.append("%s status 非法" % oid)
    if not str(opening.get("owner") or ""):
        issues.append("%s 缺 owner（OPEN 不得无名）" % oid)
    if not str(opening.get("interface") or ""):
        issues.append("%s 缺 interface" % oid)
    if status == "closed":
        issues += _closed_evidence_issues(opening, oid, root)
    return issues


def _opening_issues(openings: List[Any], root: str) -> List[str]:
    issues: List[str] = []
    if len(openings) < 12:
        issues.append("扩展口少于 12（§18 表）")
    ids_open = [str(o.get("id")) for o in openings]
    if len(ids_open) != len(set(ids_open)):
        issues.append("扩展口 id 重复")
    for opening in openings:
        issues += _opening_row_issues(opening, root)
    return issues


def _forbidden_line_issues(rel: str, lineno: int, line: str, forbidden: List[Any],
                           negative: List[str], honesty_marker: Any) -> List[str]:
    issues: List[str] = []
    for phrase in forbidden:
        if phrase in line and honesty_marker not in line:
            if not any(word in line for word in negative):
                issues.append("%s:%d 禁用词「%s」缺 [HONESTY]/否定语境"
                              "（修复指引：改写或标注 [HONESTY]）" % (rel, lineno, phrase))
    return issues


def _forbidden_doc_issues(reg: Dict[str, Any], root: str) -> List[str]:
    forbidden = reg.get("forbidden_claims") or []
    negative = [str(w) for w in reg.get("negative_context") or []]
    honesty_marker = reg.get("honesty_marker")
    issues: List[str] = []
    for rel in reg.get("scan_docs") or []:
        path = Path(root) / rel
        if not path.is_file():
            continue
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            issues += _forbidden_line_issues(rel, lineno, line, forbidden, negative, honesty_marker)
    return issues


def check(root: str = ".") -> List[str]:
    issues: List[str] = []
    reg = load_registry(root)
    tags = reg.get("tags") or []
    issues += _tag_table_issues(tags)
    defined = _defined_tags(reg)
    used = used_tags(root)
    issues += _orphan_tag_issues(defined, used)
    issues += _index_issues(reg, defined)
    issues += _synonym_issues(reg)
    openings = reg.get("extension_openings") or []
    issues += _opening_issues(openings, root)
    # 禁用词需 [HONESTY] 或否定语境
    issues += _forbidden_doc_issues(reg, root)
    boundary = " ".join(str(x) for x in reg.get("claims_boundary") or [])
    if "不是认证" not in boundary:
        issues.append("claims_boundary 必须写明不是认证/合规声明")
    return issues


def summary(root: str = ".") -> Dict[str, Any]:
    reg = load_registry(root)
    openings = reg.get("extension_openings") or []
    return {"schema": "nf-keywords-summary/1",
            "tags": len(reg.get("tags") or []),
            "keywords": sum(len(i.get("keywords") or []) for i in reg.get("keyword_index") or []),
            "synonyms": len(reg.get("synonyms") or []),
            "openings": len(openings),
            "openings_by_status": {s: sum(1 for o in openings if str(o.get("status")) == s)
                                   for s in STATUSES},
            "issues": len(check(root))}
