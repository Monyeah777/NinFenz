"""产品发现登记（`nf-product/1`）：问题/JTBD + 价值假设 + 指标/反指标 + MVP + GTM。

为什么（NF-Final WP-0A，P1 盲区 BL-06）：NF 方向不能只靠「协议很完整」自证价值。本模块把
产品假设做成可核数据：
- 每个价值假设（H-xx）必须挂指标与**反指标**（防为指标而伤害价值），状态默认 unverified；
- `validated-external` 只允许在存在**真实访谈证据件**（`results/product/interviews/` 下的
  `nf-interview/1`）时成立——本仓不伪造访谈结论；
- MVP 范围/非目标、支持分级、定价假设、试点状态（external-open）逐条登记；
- 未做项进 open_items（OPEN-PRODUCT/OPEN-METRICS），与保证案例/RAID 的缺口同源。
纪律：不以外部背书作为质量论据（STRATEGY §3）；不写日历 SLA/价格承诺。
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List

SCHEMA = "nf-product/1"
REL = "protocol/product.json"
INTERVIEW_SCHEMA = "nf-interview/1"
INTERVIEW_DIR = "results/product/interviews"
STATUSES = ("unverified", "hypothesis", "validated-external", "rejected", "accepted-risk")
PILOT_STATUSES = ("external-open", "done-external", "not-started")
GUIDE = "修复指引："


def load(root: str = ".") -> Dict[str, Any]:
    path = Path(root) / REL
    if not path.is_file():
        raise ValueError("缺 %s（%s 补产品发现登记）" % (REL, GUIDE))
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError(REL + " 不是合法 JSON：" + str(exc)) from exc
    if not isinstance(doc, dict) or str(doc.get("schema")) != SCHEMA:
        raise ValueError(REL + " schema 不匹配（" + GUIDE + "需要 " + SCHEMA + "）")
    return doc


def _exists(root: str, rel: str) -> bool:
    return (Path(root) / str(rel)).exists()


def _interview_evidence(root: str) -> List[str]:
    """真实访谈证据件（只在 results/product/interviews/ 下、schema=nf-interview/1）。"""
    base = Path(root) / INTERVIEW_DIR
    if not base.is_dir():
        return []
    out = []
    for path in sorted(base.glob("*.json")):
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(doc, dict) and str(doc.get("schema")) == INTERVIEW_SCHEMA:
            out.append(str(path.relative_to(Path(root))).replace("\\", "/"))
    return out


def validate(doc: Dict[str, Any], root: str = ".") -> List[str]:
    issues: List[str] = []
    problem = doc.get("problem") or {}
    if not str(problem.get("statement") or "").strip():
        issues.append("problem 缺 statement")
    jtbd = problem.get("jtbd") or []
    jids = [str(j.get("id")) for j in jtbd if isinstance(j, dict)]
    if len(jtbd) < 2:
        issues.append("jtbd 至少 2 条（%s）" % GUIDE)
    if len(jids) != len(set(jids)):
        issues.append("jtbd id 重复：%s" % jids)
    for job in jtbd:
        if not isinstance(job, dict):
            issues.append("jtbd 含非对象")
            continue
        for field in ("when", "want", "so"):
            if not str(job.get(field) or "").strip():
                issues.append("%s 缺 %s（JTBD 三要素）" % (job.get("id"), field))
    metrics = doc.get("metrics") or []
    mids = [str(m.get("id")) for m in metrics if isinstance(m, dict)]
    if len(metrics) < 3:
        issues.append("metrics 至少 3 个（%s）" % GUIDE)
    if len(mids) != len(set(mids)):
        issues.append("metrics id 重复：%s" % mids)
    counters = {str(c.get("id")) for c in doc.get("countermetrics") or []
                if isinstance(c, dict)}
    if len(counters) < 2:
        issues.append("countermetrics 至少 2 个（防指标伤害价值）")
    for metric in metrics:
        if not isinstance(metric, dict):
            issues.append("metrics 含非对象")
            continue
        mid = str(metric.get("id"))
        for field in ("name", "definition", "source"):
            if not str(metric.get(field) or "").strip():
                issues.append("%s 缺 %s" % (mid, field))
        if str(metric.get("countermetric")) not in counters:
            issues.append("%s 未挂存在的反指标（%s）" % (mid, GUIDE))
    hyps = doc.get("value_hypotheses") or []
    if not hyps:
        issues.append("缺 value_hypotheses")
    evidence = _interview_evidence(root)
    for hyp in hyps:
        if not isinstance(hyp, dict):
            issues.append("value_hypotheses 含非对象")
            continue
        hid = str(hyp.get("id"))
        if str(hyp.get("status")) not in STATUSES:
            issues.append("%s 的 status 非法：%s" % (hid, hyp.get("status")))
        if str(hyp.get("metric")) not in mids:
            issues.append("%s 挂了不存在的指标：%s" % (hid, hyp.get("metric")))
        if str(hyp.get("countermetric")) not in counters:
            issues.append("%s 挂了不存在的反指标：%s" % (hid, hyp.get("countermetric")))
        if not str(hyp.get("owner") or "").strip():
            issues.append("%s 缺 owner" % hid)
        if str(hyp.get("status")) == "validated-external":
            refs = hyp.get("evidence") or []
            if not any(str(x).startswith(INTERVIEW_DIR + "/") for x in refs) \
                    or not evidence:
                issues.append("%s 标 validated-external 但没有真实访谈证据件（%s 不得伪造结论）"
                              % (hid, GUIDE))
        for rel in hyp.get("evidence") or []:
            if str(rel).startswith(INTERVIEW_DIR + "/"):
                continue
            if not _exists(root, str(rel)):
                issues.append("%s 的 evidence 不在场：%s" % (hid, rel))
    mvp = doc.get("mvp") or {}
    for field in ("in_scope", "out_of_scope", "success_criteria"):
        if not mvp.get(field):
            issues.append("mvp 缺 %s" % field)
    gtm = doc.get("gtm") or {}
    pricing = gtm.get("pricing_hypothesis") or {}
    if not str(pricing.get("model") or "").strip():
        issues.append("gtm.pricing_hypothesis 缺 model")
    pricing_text = "%s %s" % (pricing.get("model") or "", pricing.get("note") or "")
    if "SLA" in pricing_text and not any(m in pricing_text for m in ("不", "非", "无", "未")):
        issues.append("gtm 定价假设不得写 SLA 承诺（%s 改为「不承诺 SLA」）" % GUIDE)
    if re.search(r"\d+(?:\.\d+)?\s*%", pricing_text) and "不" not in pricing_text:
        issues.append("gtm 定价假设不得写百分比承诺（%s）" % GUIDE)
    tiers = gtm.get("support_tiers") or []
    if len(tiers) < 2:
        issues.append("support_tiers 至少 2 级")
    for tier in tiers:
        if not isinstance(tier, dict) or not str(tier.get("tier") or "").strip():
            issues.append("support_tiers 含无效条目")
    pilot = gtm.get("pilot") or {}
    if str(pilot.get("status")) not in PILOT_STATUSES:
        issues.append("gtm.pilot.status 非法：%s（外部试点用 external-open）"
                      % pilot.get("status"))
    interviews = doc.get("interviews") or {}
    if str(interviews.get("status")) not in ("planned-external", "done-external", "not-started"):
        issues.append("interviews.status 非法：%s" % interviews.get("status"))
    if int(interviews.get("target_count") or 0) < 3:
        issues.append("interviews.target_count 至少 3（访谈计划）")
    guide = str(interviews.get("guide") or "")
    if not guide or not _exists(root, guide):
        issues.append("interviews.guide 不在场：%s" % guide)
    opens = {str(o.get("id")) for o in doc.get("open_items") or [] if isinstance(o, dict)}
    for need in ("OPEN-PRODUCT",):
        if need not in opens:
            issues.append("open_items 必须含 %s（外部访谈未做不得隐去）" % need)
    boundary = " ".join(str(x) for x in doc.get("claims_boundary") or [])
    if "外部背书" not in boundary:
        issues.append("claims_boundary 必须写明不以外部背书作为质量论据")
    return issues


def summary(doc: Dict[str, Any], root: str = ".") -> Dict[str, Any]:
    hyps = [h for h in doc.get("value_hypotheses") or [] if isinstance(h, dict)]
    by_status: Dict[str, int] = {}
    for hyp in hyps:
        by_status[str(hyp.get("status"))] = by_status.get(str(hyp.get("status")), 0) + 1
    return {"jtbd": len((doc.get("problem") or {}).get("jtbd") or []),
            "hypotheses": len(hyps), "by_status": by_status,
            "metrics": len(doc.get("metrics") or []),
            "countermetrics": len(doc.get("countermetrics") or []),
            "interview_evidence": len(_interview_evidence(root)),
            "external_validated": by_status.get("validated-external", 0)}
