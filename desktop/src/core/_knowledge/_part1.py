"""core.knowledge 私有实现分片 1/2（对外只经 core.knowledge 门面导入）：DECL_REL、LOG_REL 等"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

from core import json_doc

DECL_REL = "protocol/knowledge_sources.json"


LOG_REL = "protocol/transform_log.json"


USAGE_REL = "protocol/knowledge_usage.json"


SCHEMA = "nf-knowledge-sources/1"


LOG_SCHEMA = "nf-transform-log/1"


USAGE_SCHEMA = "nf-knowledge-usage/1"


AUTHORITIES = ("contract", "reference")


KINDS = ("local-compiled", "external-retrieval")


VISIBILITIES = ("public", "internal", "restricted")


TIERS = ("machine-checkable", "reproducible", "externally-attestable")


TRIGGERS = ("reuse-frequency", "author-mark", "machine-check-pass")


FRESH_CONTRACT = ("stale_after",)


FRESH_REFERENCE = ("ttl", "no-cache")


REQUIRED_SRC = ("id", "authority", "kind", "locator", "requires_source_label",
                "visibility", "freshness")


REQUIRED_ENTRY = ("from", "to", "digest", "reviewed_by", "reviewed_at", "evidence")


_MODULE_ID = re.compile(r"^\s*id:\s*(M\d+|事件:M\d+|通用:M\d+)\s*$", re.M)


_DATED = re.compile(r"^\d{4}-\d{2}-\d{2}$")


#: 可见性秩：clearance 达到源的秩即可见（public ⊆ internal ⊆ restricted）
VISIBILITY_RANK = {"public": 0, "internal": 1, "restricted": 2}


def _read_json(path: Path) -> Dict[str, Any]:
    return json_doc.load(path, dict, what=path.name) if path.is_file() else {}


def load_decl(root: str = ".") -> Dict[str, Any]:
    return _read_json(Path(root) / DECL_REL)


def load_log(root: str = ".") -> Dict[str, Any]:
    return _read_json(Path(root) / LOG_REL)


def load_usage(root: str = ".") -> Dict[str, Any]:
    return _read_json(Path(root) / USAGE_REL)


def sha256_file(path: str) -> str:
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def _module_ids(root: str = ".") -> set:
    r = Path(root)
    out = set()
    for pat in ("04_模块库/*/*.md", "community/*/modules/*.md"):
        for p in sorted(r.glob(pat)):
            for m in _MODULE_ID.finditer(p.read_text(encoding="utf-8")):
                out.add(m.group(1))
    return out


def sources(root: str = ".") -> List[Dict[str, Any]]:
    return list(load_decl(root).get("sources") or [])


def reference_ids(root: str = ".") -> set:
    return {str(s.get("id")) for s in sources(root) if s.get("authority") == "reference"}


def visible_ids(root: str = ".", clearance: str = "restricted") -> set:
    """逐源可见性裁剪：clearance 达到源的可见性秩即可见（public ⊆ internal ⊆ restricted）。

    认知边界协同的**执行面**：消费方（含叙事域的 M23 裁剪）按 clearance 取源，
    越权源不进入查询顺序。
    """
    cap = VISIBILITY_RANK.get(str(clearance))
    if cap is None:
        return set()
    out = set()
    for s in sources(root):
        rank = VISIBILITY_RANK.get(str(s.get("visibility")), 99)
        if rank <= cap:
            out.add(str(s.get("id")))
    return out


def resolve_order(root: str = ".", clearance: str = "") -> List[Dict[str, str]]:
    """按声明的 query_order 解析查询顺序（先合同级，再参考级）。

    `clearance` 非空时先过逐源可见性裁剪（越权源不出现）。
    """
    decl = load_decl(root)
    by_id = {str(s.get("id")): s for s in sources(root)}
    allowed = visible_ids(root, clearance) if clearance else None
    out = []
    for sid in decl.get("query_order") or []:
        s = by_id.get(str(sid))
        if s is None:
            continue
        if allowed is not None and str(sid) not in allowed:
            continue
        out.append({"id": str(sid), "authority": str(s.get("authority")),
                    "kind": str(s.get("kind")), "locator": str(s.get("locator")),
                    "requires_source_label": str(bool(s.get("requires_source_label"))).lower(),
                    "visibility": str(s.get("visibility"))})
    return out


def _auth(rows: List[Dict[str, Any]], sid: str) -> str:
    for s in rows:
        if str(s.get("id")) == sid:
            return str(s.get("authority"))
    return ""


def scan(root: str = ".") -> Tuple[List[str], List[str], Dict[str, Any]]:
    """声明机检 → (issues, warns, stats)。"""
    issues: List[str] = []
    warns: List[str] = []
    decl = load_decl(root)
    if not decl:
        return ["缺知识源声明 %s（修复指引：见 docs/knowledge.md）" % DECL_REL], warns, {}
    if str(decl.get("schema") or "") != SCHEMA:
        issues.append("知识源声明 schema 不匹配（期望 %s）" % SCHEMA)
    for key, vocab in (("authority_vocabulary", AUTHORITIES),
                       ("kind_vocabulary", KINDS), ("visibility_vocabulary", VISIBILITIES)):
        if tuple(decl.get(key) or ()) != vocab:
            issues.append("%s 词表与判据不一致（期望 %s）" % (key, "/".join(vocab)))
    rows = sources(root)
    if not rows:
        issues.append("未声明任何知识源（%s.sources 为空）" % DECL_REL)
    seen: Dict[str, int] = {}
    for s in rows:
        sid = str(s.get("id") or "")
        for k in REQUIRED_SRC:
            if k not in s:
                issues.append("源 %s 缺必填字段：%s" % (sid or "(无名)", k))
        if sid in seen:
            issues.append("源 id 重复：%s" % sid)
        seen[sid] = seen.get(sid, 0) + 1
        auth, kind = str(s.get("authority")), str(s.get("kind"))
        if auth not in AUTHORITIES:
            issues.append("源 %s authority 越词表：%s" % (sid, auth))
        if kind not in KINDS:
            issues.append("源 %s kind 越词表：%s" % (sid, kind))
        vis = str(s.get("visibility"))
        if vis not in VISIBILITIES:
            issues.append("源 %s visibility 越词表：%s" % (sid, vis))
        loc = str(s.get("locator") or "")
        if loc and not (Path(root) / loc).exists():
            issues.append("源 %s 的 locator 不存在：%s（防纸面源）" % (sid, loc))
        fresh_raw = s.get("freshness")
        fresh: Dict[str, Any] = fresh_raw if isinstance(fresh_raw, dict) else {}
        pol = str(fresh.get("policy") or "")
        labelled = bool(s.get("requires_source_label"))
        if auth == "reference":
            if kind != "external-retrieval":
                issues.append("源 %s 为 reference 级但 kind 非 external-retrieval" % sid)
            if not labelled:
                issues.append("源 %s 为 reference 级但未要求标注来源"
                              "（外部数据不得写死；修复指引：requires_source_label: true）" % sid)
            if pol not in FRESH_REFERENCE:
                issues.append("源 %s 为 reference 级但时效策略非法：%s（需 %s）"
                              % (sid, pol or "(缺)", " / ".join(FRESH_REFERENCE)))
            elif pol == "ttl" and not (isinstance(fresh.get("ttl_days"), int)
                                       and fresh["ttl_days"] > 0):
                issues.append("源 %s 声明 ttl 但 ttl_days 非正整数" % sid)
        elif auth == "contract":
            if kind != "local-compiled":
                issues.append("源 %s 为 contract 级但 kind 非 local-compiled" % sid)
            if labelled:
                issues.append("源 %s 为 contract 级却要求外部来源标注（合同级即本地真源）" % sid)
            if pol not in FRESH_CONTRACT:
                issues.append("源 %s 为 contract 级但时效策略非法：%s（需 stale_after）"
                              % (sid, pol or "(缺)"))
    order = [str(x) for x in (decl.get("query_order") or [])]
    ids = [str(s.get("id")) for s in rows]
    if sorted(order) != sorted(ids):
        issues.append("query_order 与 sources 不是同一集合（缺 %s / 多 %s）"
                      % (sorted(set(ids) - set(order)), sorted(set(order) - set(ids))))
    else:
        pos = {sid: i for i, sid in enumerate(order)}
        ref_idx = [pos[i] for i in ids if _auth(rows, i) == "reference"]
        con_idx = [pos[i] for i in ids if _auth(rows, i) == "contract"]
        if ref_idx and con_idx and max(con_idx) > min(ref_idx):
            issues.append("query_order 未把全部合同级排在参考级之前（查询有序被破坏）")
    prom_raw = decl.get("promotion")
    prom: Dict[str, Any] = prom_raw if isinstance(prom_raw, dict) else {}
    if tuple(prom.get("evidence_tiers") or ()) != TIERS:
        issues.append("promotion.evidence_tiers 与判据不一致（期望 %s）" % "/".join(TIERS))
    if tuple(prom.get("triggers") or ()) != TRIGGERS:
        issues.append("promotion.triggers 与判据不一致（期望 %s）" % "/".join(TRIGGERS))
    if not str(prom.get("rule") or "").strip():
        issues.append("promotion 缺 rule（晋升标准必须成文）")
    if str(prom.get("on_missing_evidence") or "") != "stay-reference":
        issues.append("promotion.on_missing_evidence 必须为 stay-reference（缺证据不得转正）")
    rev_raw = decl.get("review")
    rev: Dict[str, Any] = rev_raw if isinstance(rev_raw, dict) else {}
    if not (rev.get("machine_gates") or []):
        issues.append("review 缺 machine_gates（消化审核必须列机检项）")
    if not str(rev.get("rule") or "").strip():
        issues.append("review 缺 rule（消化审核规则必须成文）")
    cog_raw = decl.get("cognition")
    cog: Dict[str, Any] = cog_raw if isinstance(cog_raw, dict) else {}
    fid = str(cog.get("filter_module") or "")
    if not fid:
        issues.append("cognition 缺 filter_module（认知裁剪须指定执行模块）")
    elif fid not in _module_ids(root):
        issues.append("cognition.filter_module 指向不在册模块：%s" % fid)
    log = load_log(root)
    if not log:
        issues.append("缺消化记录 %s（修复指引：见 docs/knowledge.md）" % LOG_REL)
    elif str(log.get("schema") or "") != LOG_SCHEMA:
        issues.append("消化记录 schema 不匹配（期望 %s）" % LOG_SCHEMA)
    stats = {"sources": len(rows),
             "contract": sum(1 for s in rows if s.get("authority") == "contract"),
             "reference": sum(1 for s in rows if s.get("authority") == "reference"),
             "order": order, "transforms": len(log.get("entries") or [])}
    return issues, warns, stats


def verify_transform(root: str = ".") -> Tuple[List[str], List[str], Dict[str, Any]]:
    """消化记录校验 → (issues, warns, stats)。"""
    issues: List[str] = []
    warns: List[str] = []
    log = load_log(root)
    entries = log.get("entries") or []
    refs = reference_ids(root)
    for i, e in enumerate(entries):
        tag = "记录 #%d" % (i + 1)
        if not isinstance(e, dict):
            issues.append("%s 非对象" % tag)
            continue
        for k in REQUIRED_ENTRY:
            if k not in e:
                issues.append("%s 缺必填字段：%s" % (tag, k))
        src = str(e.get("from") or "")
        if src and src not in refs:
            issues.append("%s 的 from 不是已声明的参考级源：%s" % (tag, src))
        to = str(e.get("to") or "")
        if to:
            p = Path(root) / to
            if not p.is_file():
                issues.append("%s 的产物不存在：%s" % (tag, to))
            elif str(e.get("digest")) != sha256_file(str(p)):
                issues.append("%s 的产物摘要与记录不一致：%s"
                              "（产物已改，记录失效；修复指引：重新消化并更新 digest）" % (tag, to))
        ev = tuple(e.get("evidence") or ())
        if e.get("promoted"):
            missing = [t for t in TIERS if t not in ev]
            if missing:
                issues.append("%s 声明转正但缺证据档：%s" % (tag, "/".join(missing)))
            if not str(e.get("reviewed_by") or "").strip():
                issues.append("%s 声明转正但无复核人（消化审核未双签）" % tag)
        if "reuse_count" in e and not (isinstance(e["reuse_count"], int)
                                      and e["reuse_count"] >= 0):
            issues.append("%s 的 reuse_count 非非负整数（频次判据不可复算）" % tag)
        ra = str(e.get("reviewed_at") or "")
        if ra and not _DATED.match(ra):
            issues.append("%s 的 reviewed_at 非 YYYY-MM-DD" % tag)
    stats = {"entries": len(entries),
             "promoted": sum(1 for e in entries if isinstance(e, dict) and e.get("promoted"))}
    return issues, warns, stats
