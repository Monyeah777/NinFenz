"""core.knowledge 私有实现分片：声明机检（scan）与消化记录校验（verify_transform）。

对外只经 core.knowledge 门面导入；本文件只承载实现，不改变对外面。
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Tuple

from ._part1 import (
    AUTHORITIES,
    DECL_REL,
    FRESH_CONTRACT,
    FRESH_REFERENCE,
    KINDS,
    LOG_REL,
    LOG_SCHEMA,
    REQUIRED_ENTRY,
    REQUIRED_SRC,
    SCHEMA,
    TIERS,
    TRIGGERS,
    VISIBILITIES,
    _DATED,
    _auth,
    _module_ids,
    load_decl,
    load_log,
    reference_ids,
    sha256_file,
    sources,
)


def _vocab_issues(decl: Dict[str, Any]) -> List[str]:
    """声明 schema 与三张词表判据。"""
    out: List[str] = []
    if str(decl.get("schema") or "") != SCHEMA:
        out.append("知识源声明 schema 不匹配（期望 %s）" % SCHEMA)
    for key, vocab in (("authority_vocabulary", AUTHORITIES),
                       ("kind_vocabulary", KINDS), ("visibility_vocabulary", VISIBILITIES)):
        if tuple(decl.get(key) or ()) != vocab:
            out.append("%s 词表与判据不一致（期望 %s）" % (key, "/".join(vocab)))
    return out


def _source_required_issues(s: Dict[str, Any], sid: str) -> List[str]:
    """源必填字段判据。"""
    out: List[str] = []
    for k in REQUIRED_SRC:
        if k not in s:
            out.append("源 %s 缺必填字段：%s" % (sid or "(无名)", k))
    return out


def _source_vocab_issues(s: Dict[str, Any], sid: str) -> List[str]:
    """源 authority/kind/visibility 词表判据。"""
    out: List[str] = []
    auth, kind = str(s.get("authority")), str(s.get("kind"))
    if auth not in AUTHORITIES:
        out.append("源 %s authority 越词表：%s" % (sid, auth))
    if kind not in KINDS:
        out.append("源 %s kind 越词表：%s" % (sid, kind))
    vis = str(s.get("visibility"))
    if vis not in VISIBILITIES:
        out.append("源 %s visibility 越词表：%s" % (sid, vis))
    return out


def _source_locator_issues(s: Dict[str, Any], sid: str, root: str) -> List[str]:
    """源 locator 在场判据（防纸面源）。"""
    loc = str(s.get("locator") or "")
    if loc and not (Path(root) / loc).exists():
        return ["源 %s 的 locator 不存在：%s（防纸面源）" % (sid, loc)]
    return []


def _source_reference_issues(sid: str, kind: str, labelled: bool, pol: str,
                             fresh: Dict[str, Any]) -> List[str]:
    """reference 级源判据（kind / 来源标注 / 时效策略 / ttl_days）。"""
    out: List[str] = []
    if kind != "external-retrieval":
        out.append("源 %s 为 reference 级但 kind 非 external-retrieval" % sid)
    if not labelled:
        out.append("源 %s 为 reference 级但未要求标注来源"
                   "（外部数据不得写死；修复指引：requires_source_label: true）" % sid)
    if pol not in FRESH_REFERENCE:
        out.append("源 %s 为 reference 级但时效策略非法：%s（需 %s）"
                   % (sid, pol or "(缺)", " / ".join(FRESH_REFERENCE)))
    elif pol == "ttl" and not (isinstance(fresh.get("ttl_days"), int)
                               and fresh["ttl_days"] > 0):
        out.append("源 %s 声明 ttl 但 ttl_days 非正整数" % sid)
    return out


def _source_contract_issues(sid: str, kind: str, labelled: bool, pol: str) -> List[str]:
    """contract 级源判据（kind / 来源标注 / 时效策略）。"""
    out: List[str] = []
    if kind != "local-compiled":
        out.append("源 %s 为 contract 级但 kind 非 local-compiled" % sid)
    if labelled:
        out.append("源 %s 为 contract 级却要求外部来源标注（合同级即本地真源）" % sid)
    if pol not in FRESH_CONTRACT:
        out.append("源 %s 为 contract 级但时效策略非法：%s（需 stale_after）"
                   % (sid, pol or "(缺)"))
    return out


def _source_fresh_issues(s: Dict[str, Any], sid: str) -> List[str]:
    """按 authority 分派 source 级判据（reference / contract）。"""
    fresh_raw = s.get("freshness")
    fresh: Dict[str, Any] = fresh_raw if isinstance(fresh_raw, dict) else {}
    pol = str(fresh.get("policy") or "")
    labelled = bool(s.get("requires_source_label"))
    auth = str(s.get("authority"))
    kind = str(s.get("kind"))
    if auth == "reference":
        return _source_reference_issues(sid, kind, labelled, pol, fresh)
    if auth == "contract":
        return _source_contract_issues(sid, kind, labelled, pol)
    return []


def _sources_issues(rows: List[Dict[str, Any]], root: str) -> List[str]:
    """逐源判据 + id 重复（判序：必填字段 → id 重复 → 词表 → locator → 分级时效）。"""
    out: List[str] = []
    seen: Dict[str, int] = {}
    for s in rows:
        sid = str(s.get("id") or "")
        out.extend(_source_required_issues(s, sid))
        if sid in seen:
            out.append("源 id 重复：%s" % sid)
        seen[sid] = seen.get(sid, 0) + 1
        out.extend(_source_vocab_issues(s, sid))
        out.extend(_source_locator_issues(s, sid, root))
        out.extend(_source_fresh_issues(s, sid))
    return out


def _order_rank_issues(order: List[str], ids: List[str],
                       rows: List[Dict[str, Any]]) -> List[str]:
    """合同级必须全部排在参考级之前（查询有序）。"""
    pos = {sid: i for i, sid in enumerate(order)}
    ref_idx = [pos[i] for i in ids if _auth(rows, i) == "reference"]
    con_idx = [pos[i] for i in ids if _auth(rows, i) == "contract"]
    if ref_idx and con_idx and max(con_idx) > min(ref_idx):
        return ["query_order 未把全部合同级排在参考级之前（查询有序被破坏）"]
    return []


def _order_issues(order: List[str], ids: List[str],
                  rows: List[Dict[str, Any]]) -> List[str]:
    """query_order 与 sources 集合一致性 + 排位判据。"""
    if sorted(order) != sorted(ids):
        return ["query_order 与 sources 不是同一集合（缺 %s / 多 %s）"
                % (sorted(set(ids) - set(order)), sorted(set(order) - set(ids)))]
    return _order_rank_issues(order, ids, rows)


def _promotion_issues(decl: Dict[str, Any]) -> List[str]:
    """promotion 晋升标准判据。"""
    prom_raw = decl.get("promotion")
    prom: Dict[str, Any] = prom_raw if isinstance(prom_raw, dict) else {}
    out: List[str] = []
    if tuple(prom.get("evidence_tiers") or ()) != TIERS:
        out.append("promotion.evidence_tiers 与判据不一致（期望 %s）" % "/".join(TIERS))
    if tuple(prom.get("triggers") or ()) != TRIGGERS:
        out.append("promotion.triggers 与判据不一致（期望 %s）" % "/".join(TRIGGERS))
    if not str(prom.get("rule") or "").strip():
        out.append("promotion 缺 rule（晋升标准必须成文）")
    if str(prom.get("on_missing_evidence") or "") != "stay-reference":
        out.append("promotion.on_missing_evidence 必须为 stay-reference（缺证据不得转正）")
    return out


def _review_issues(decl: Dict[str, Any]) -> List[str]:
    """review 消化审核判据。"""
    rev_raw = decl.get("review")
    rev: Dict[str, Any] = rev_raw if isinstance(rev_raw, dict) else {}
    out: List[str] = []
    if not (rev.get("machine_gates") or []):
        out.append("review 缺 machine_gates（消化审核必须列机检项）")
    if not str(rev.get("rule") or "").strip():
        out.append("review 缺 rule（消化审核规则必须成文）")
    return out


def _cognition_issues(decl: Dict[str, Any], root: str) -> List[str]:
    """cognition.filter_module 在册判据。"""
    cog_raw = decl.get("cognition")
    cog: Dict[str, Any] = cog_raw if isinstance(cog_raw, dict) else {}
    fid = str(cog.get("filter_module") or "")
    if not fid:
        return ["cognition 缺 filter_module（认知裁剪须指定执行模块）"]
    if fid not in _module_ids(root):
        return ["cognition.filter_module 指向不在册模块：%s" % fid]
    return []


def _log_issues(root: str) -> List[str]:
    """消化记录在场与 schema 判据。"""
    log = load_log(root)
    if not log:
        return ["缺消化记录 %s（修复指引：见 docs/knowledge.md）" % LOG_REL]
    if str(log.get("schema") or "") != LOG_SCHEMA:
        return ["消化记录 schema 不匹配（期望 %s）" % LOG_SCHEMA]
    return []


def _scan_stats(rows: List[Dict[str, Any]], order: List[str],
                log: Dict[str, Any]) -> Dict[str, Any]:
    """scan 统计面。"""
    return {"sources": len(rows),
            "contract": sum(1 for s in rows if s.get("authority") == "contract"),
            "reference": sum(1 for s in rows if s.get("authority") == "reference"),
            "order": order, "transforms": len(log.get("entries") or [])}


def scan(root: str = ".") -> Tuple[List[str], List[str], Dict[str, Any]]:
    """声明机检 → (issues, warns, stats)。"""
    issues: List[str] = []
    warns: List[str] = []
    decl = load_decl(root)
    if not decl:
        return ["缺知识源声明 %s（修复指引：见 docs/knowledge.md）" % DECL_REL], warns, {}
    issues.extend(_vocab_issues(decl))
    rows = sources(root)
    if not rows:
        issues.append("未声明任何知识源（%s.sources 为空）" % DECL_REL)
    issues.extend(_sources_issues(rows, root))
    order = [str(x) for x in (decl.get("query_order") or [])]
    ids = [str(s.get("id")) for s in rows]
    issues.extend(_order_issues(order, ids, rows))
    issues.extend(_promotion_issues(decl))
    issues.extend(_review_issues(decl))
    issues.extend(_cognition_issues(decl, root))
    log = load_log(root)
    issues.extend(_log_issues(root))
    return issues, warns, _scan_stats(rows, order, log)


def _transform_required_issues(e: Dict[str, Any], tag: str) -> List[str]:
    """消化记录必填字段判据。"""
    out: List[str] = []
    for k in REQUIRED_ENTRY:
        if k not in e:
            out.append("%s 缺必填字段：%s" % (tag, k))
    return out


def _transform_src_issues(e: Dict[str, Any], tag: str, refs: Any) -> List[str]:
    """from 必须是已声明的参考级源。"""
    src = str(e.get("from") or "")
    if src and src not in refs:
        return ["%s 的 from 不是已声明的参考级源：%s" % (tag, src)]
    return []


def _transform_product_issues(e: Dict[str, Any], tag: str, root: str) -> List[str]:
    """产物在场 + 摘要一致判据。"""
    to = str(e.get("to") or "")
    if not to:
        return []
    p = Path(root) / to
    if not p.is_file():
        return ["%s 的产物不存在：%s" % (tag, to)]
    if str(e.get("digest")) != sha256_file(str(p)):
        return ["%s 的产物摘要与记录不一致：%s"
                "（产物已改，记录失效；修复指引：重新消化并更新 digest）" % (tag, to)]
    return []


def _transform_promoted_issues(e: Dict[str, Any], tag: str) -> List[str]:
    """转正证据档与复核人判据。"""
    if not e.get("promoted"):
        return []
    out: List[str] = []
    ev = tuple(e.get("evidence") or ())
    missing = [t for t in TIERS if t not in ev]
    if missing:
        out.append("%s 声明转正但缺证据档：%s" % (tag, "/".join(missing)))
    if not str(e.get("reviewed_by") or "").strip():
        out.append("%s 声明转正但无复核人（消化审核未双签）" % tag)
    return out


def _transform_reuse_issues(e: Dict[str, Any], tag: str) -> List[str]:
    """reuse_count 复算判据。"""
    if "reuse_count" in e and not (isinstance(e["reuse_count"], int)
                                  and e["reuse_count"] >= 0):
        return ["%s 的 reuse_count 非非负整数（频次判据不可复算）" % tag]
    return []


def _transform_date_issues(e: Dict[str, Any], tag: str) -> List[str]:
    """reviewed_at 日期形状判据。"""
    ra = str(e.get("reviewed_at") or "")
    if ra and not _DATED.match(ra):
        return ["%s 的 reviewed_at 非 YYYY-MM-DD" % tag]
    return []


def _entry_issues(e: Any, i: int, root: str, refs: Any) -> List[str]:
    """单条消化记录全部判据。"""
    tag = "记录 #%d" % (i + 1)
    if not isinstance(e, dict):
        return ["%s 非对象" % tag]
    out = _transform_required_issues(e, tag)
    out.extend(_transform_src_issues(e, tag, refs))
    out.extend(_transform_product_issues(e, tag, root))
    out.extend(_transform_promoted_issues(e, tag))
    out.extend(_transform_reuse_issues(e, tag))
    out.extend(_transform_date_issues(e, tag))
    return out


def verify_transform(root: str = ".") -> Tuple[List[str], List[str], Dict[str, Any]]:
    """消化记录校验 → (issues, warns, stats)。"""
    issues: List[str] = []
    warns: List[str] = []
    log = load_log(root)
    entries = log.get("entries") or []
    refs = reference_ids(root)
    for i, e in enumerate(entries):
        issues.extend(_entry_issues(e, i, root, refs))
    stats = {"entries": len(entries),
             "promoted": sum(1 for e in entries if isinstance(e, dict) and e.get("promoted"))}
    return issues, warns, stats


