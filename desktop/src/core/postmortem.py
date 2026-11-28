"""复盘门禁（SRE postmortem：无指责 + 根因指向机制 + 行动项可指派可验）。

真源：`protocol/postmortem.json`（声明）+ `postmortems/PO-*.md`（复盘件）。

判据（全部可证，零第三方依赖）：
- 声明：schema；四段；blame_tokens / root_cause_tokens 非空；status 词表；
- 复盘件：frontmatter 必填齐、status 在词表、date 格式、四段齐；
  `trigger` 与 `refs` 必须解析到真实件或 `checkN`；
  **禁指责**：blame_tokens 命中即 FAIL；**根因指向机制**：根因段须含 root_cause_tokens；
  **行动项可指派可验**：每条行动项必须同时含「负责人」与「判据」；
  **未复盘不得关闭**：`status: closed` 必须已被协议回执锚定。
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Tuple

from core import doc_family
from core import json_doc
from core.library import parse_frontmatter

DECL_REL = "protocol/postmortem.json"
RECEIPTS_REL = "protocol/RECEIPTS.json"
GLOB = "postmortems/PO-*.md"
SCHEMA = "nf-postmortem/1"
SECTIONS = ("## 现象", "## 影响", "## 根因", "## 行动项")


#: 列表块解析的**唯一出处**（与 handover 曾逐字重复的两份拷贝，2026-10-01 收口）
from core.md_blocks import bullet_blocks as _bullet_blocks


def decl(root: str = ".") -> Dict[str, Any]:
    return doc_family.load_decl(root, DECL_REL)


def entries(root: str = ".") -> List[Dict[str, Any]]:
    return doc_family.entries(root, GLOB)


def check_doc(root: str, rel: str) -> Tuple[List[str], Dict[str, Any]]:
    """单件机检 → (issues, stats)。"""
    p = Path(root) / rel
    if not p.is_file():
        return ["复盘件不存在：%s" % rel], {}
    d = decl(root)
    fm, body = parse_frontmatter(p.read_text(encoding="utf-8"))
    fm, body = fm or {}, body or ""
    issues = _section_issues(fm, d, body)
    acts = _action_blocks(body)
    issues += _action_issues(acts)
    r = Path(root)
    checks = doc_family.check_numbers(root)
    issues += doc_family.refs_issues(root, fm.get("trigger"), checks, label="引用")
    issues += doc_family.refs_issues(root, fm.get("refs"), checks, label="引用")
    issues += _receipt_issues(rel, r, fm)
    stats = {"actions": len(acts), "sections": sum(1 for s in SECTIONS if s in body)}
    return issues, stats


def _section_issues(fm: Dict[str, Any], d: Dict[str, Any], body: str) -> List[str]:
    """frontmatter 必填 + 正文四段 + 指责词/根因判据。"""
    issues: List[str] = doc_family.frontmatter_issues(
        fm, d, required=("id", "date", "trigger", "status", "refs"),
        vocab_key="status_vocabulary", field="status",
        default_vocab=("open", "closed"))
    issues += ["正文缺段落：%s" % sec for sec in SECTIONS if sec not in body]
    issues += _blame_issues(d, body)
    issue = _root_cause_issue(d, body)
    if issue:
        issues.append(issue)
    return issues


def _blame_issues(d: Dict[str, Any], body: str) -> List[str]:
    """命中指责性归因词（复盘对事不对人）。"""
    return ["命中指责性归因词「%s」——复盘对事不对人" % tok
            for tok in (d.get("blame_tokens") or []) if tok and tok in body]


def _root_cause_issue(d: Dict[str, Any], body: str) -> str:
    """根因段是否指向机制（须出现 roott_cause_tokens 之一）；空串=无问题。"""
    if "## 根因" not in body:
        return ""
    root_sec = body.split("## 根因", 1)[1].split("## 行动项", 1)[0]
    toks = d.get("root_cause_tokens") or []
    if toks and not any(t in root_sec for t in toks):
        return "根因段未指向机制（须出现 %s 之一）" % "/".join(toks[:4])
    return ""


def _action_blocks(body: str) -> List[str]:
    """行动项段落里的 bullet 块（无行动项段=空）。"""
    if "## 行动项" not in body:
        return []
    return _bullet_blocks(body.split("## 行动项", 1)[1])


def _action_issues(acts: List[str]) -> List[str]:
    """行动项非空 + 每项有负责人/判据。"""
    issues: List[str] = []
    if not acts:
        issues.append("行动项为空——没有行动项的复盘不闭环")
    for a in acts:
        if "负责人" not in a:
            issues.append("行动项缺负责人：%s" % a[:40])
        if "判据" not in a:
            issues.append("行动项缺判据：%s" % a[:40])
    return issues


def _receipt_issues(rel: str, r: Path, fm: Dict[str, Any]) -> List[str]:
    """status=closed 必须被协议回执锚定（防事后美化）。"""
    if str(fm.get("status")) == "closed" and (r / RECEIPTS_REL).is_file():
        doc = json_doc.load(r / RECEIPTS_REL, dict, what=RECEIPTS_REL)
        ids = {e.get("id") for e in (doc.get("entries") or [])}
        if rel not in ids:
            return ["status=closed 但未被协议回执锚定（防事后美化；修复指引：nf receipts --wr"
                    "ite）"]
    return []


def scan(root: str = ".") -> Tuple[List[str], List[str], Dict[str, Any]]:
    """声明 + 全部复盘件 → (issues, warns, stats)。"""
    issues: List[str] = []
    warns: List[str] = []
    d = decl(root)
    if not d:
        return ["缺复盘协议声明 %s" % DECL_REL], warns, {}
    issues += _decl_issues(d)
    rows = entries(root)
    acts = 0
    for e in rows:
        i, st = check_doc(root, e["path"])
        issues += ["%s：%s" % (e["fm"].get("id") or e["file"], x) for x in i]
        acts += st.get("actions", 0)
    if not rows:
        warns.append("暂无复盘件（%s）——门禁空转" % GLOB)
    return issues, warns, {"postmortems": len(rows), "actions": acts}


def _decl_issues(d: Dict[str, Any]) -> List[str]:
    """复盘协议声明的口径。"""
    issues: List[str] = []
    if str(d.get("schema") or "") != SCHEMA:
        issues.append("复盘协议 schema 不匹配（期望 %s）" % SCHEMA)
    if tuple(d.get("sections") or ()) != ("现象", "影响", "根因", "行动项"):
        issues.append("sections 必须是四段（现象/影响/根因/行动项）")
    for k in ("blame_tokens", "root_cause_tokens"):
        if not (d.get(k) or []):
            issues.append("%s 不得为空（无指责与根因判据必须成文）" % k)
    return issues
