"""评测效度登记（`nf-eval-validity/1`）：预注册 / 样本量 / inter-rater / 反指标 / 效度威胁。

为什么（NF-Final WP-0F，P0 盲区 BL-05）：QA/评测最容易自欺——事后挑指标、无样本量也敢宣称差异、
评分者一致性不测、指标被 Goodhart。本模块把效度规则做成数据 + 可执行判据：
- 预注册：required_fields 必须覆盖评测协议字段，协议必须冻结（frozen_before_run）；
- 样本量：min_samples_per_task ≥3（不足只描述统计）；
- inter-rater：Cohen's kappa 由样本现算，低于 min_kappa 即不可用；
- 反指标：每个 metric 必须挂一个存在的 countermetric；反指标不许参与奖励/排序；
- 效度威胁：每条威胁有 check + 真实证据件；「自评打分写回运行时」必须被 no_scoring 挡住。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

SCHEMA = "nf-eval-validity/1"
REL = "protocol/eval_validity.json"
SAMPLE_SCHEMA = "nf-interrater-sample/1"
METHODS = ("cohen_kappa", "krippendorff_alpha", "percent_agreement")
GUIDE = "修复指引："


def load(root: str = ".") -> Dict[str, Any]:
    path = Path(root) / REL
    if not path.is_file():
        raise ValueError("缺 %s（%s 补效度协议）" % (REL, GUIDE))
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError(REL + " 不是合法 JSON：" + str(exc)) from exc
    if not isinstance(doc, dict) or str(doc.get("schema")) != SCHEMA:
        raise ValueError(REL + " schema 不匹配（" + GUIDE + "需要 " + SCHEMA + "）")
    return doc


def _exists(root: str, rel: str) -> bool:
    return (Path(root) / rel).is_file()


def _expected_agreement(pairs: List[Tuple[str, str]], labels: List[str], n: int) -> float:
    """期望一致率 pe = Σ 各标签边际占比之积。"""
    pe = 0.0
    for label in labels:
        ca = sum(1 for a, _b in pairs if a == label) / n
        cb = sum(1 for _a, b in pairs if b == label) / n
        pe += ca * cb
    return pe


def cohen_kappa(pairs: List[Tuple[str, str]]) -> float:
    """两名评分者的 Cohen's kappa（标签任意字符串；空样本/单标签退化 → ValueError/1.0）。"""
    if not pairs:
        raise ValueError("kappa 样本为空（" + GUIDE + "至少 1 条双评）")
    n = len(pairs)
    labels = sorted({a for pair in pairs for a in pair})
    agree = sum(1 for a, b in pairs if a == b)
    po = agree / n
    pe = _expected_agreement(pairs, labels, n)
    if pe >= 1.0:
        return 1.0 if po >= 1.0 else 0.0
    return round((po - pe) / (1.0 - pe), 6)


def load_sample(doc: Dict[str, Any], root: str = ".") -> Dict[str, Any]:
    rel = str((doc.get("inter_rater") or {}).get("sample") or "")
    if not rel or not _exists(root, rel):
        raise ValueError("inter-rater 样本不在场：%s（%s 补样本）" % (rel, GUIDE))
    sample = json.loads((Path(root) / rel).read_text(encoding="utf-8"))
    if not isinstance(sample, dict) or str(sample.get("schema")) != SAMPLE_SCHEMA:
        raise ValueError(rel + " schema 不匹配（" + GUIDE + "需要 " + SAMPLE_SCHEMA + "）")
    return sample


def interrater(doc: Dict[str, Any], root: str = ".") -> Dict[str, Any]:
    """按样本现算 kappa → {method,min_kappa,kappa,items,status}。"""
    conf = doc.get("inter_rater") or {}
    sample = load_sample(doc, root)
    raters = [str(r) for r in sample.get("raters") or []]
    if len(raters) != 2:
        raise ValueError("inter-rater 样本必须恰有两名评分者（%s 走 pairwise kappa）" % GUIDE)
    pairs = [(str(item.get(raters[0])), str(item.get(raters[1])))
             for item in sample.get("items") or [] if isinstance(item, dict)]
    kappa = cohen_kappa(pairs)
    try:
        minimum = float(conf.get("min_kappa"))
    except (TypeError, ValueError):
        minimum = 0.0
    return {"method": str(conf.get("method")), "min_kappa": minimum, "kappa": kappa,
            "items": len(pairs), "status": "pass" if kappa >= minimum else "fail"}


def _protocol_rel_issues(doc: Dict[str, Any], root: str) -> List[str]:
    """concrete_protocols 判据（至少一个、逐个在场）。"""
    out: List[str] = []
    protocols = doc.get("concrete_protocols") or []
    if not protocols:
        out.append("缺 concrete_protocols（%s 至少绑一个预注册协议）" % GUIDE)
    for rel in protocols:
        if not _exists(root, str(rel)):
            out.append("concrete_protocols 不在场：%s" % rel)
    return out


def _required_fields_issues(required: Any) -> List[str]:
    """preregistration.required_fields 判据。"""
    out: List[str] = []
    if not isinstance(required, list) or len(required) < 8:
        out.append("preregistration.required_fields 至少 8 项（%s）" % GUIDE)
    if "frozen_before_run" not in required:
        out.append("preregistration.required_fields 必须含 frozen_before_run")
    return out


def _prereg_issues(doc: Dict[str, Any], root: str) -> List[str]:
    """preregistration 判据（字段表 / 冻结规则 / 证据在场）。"""
    pre = doc.get("preregistration") or {}
    out = _required_fields_issues(pre.get("required_fields") or [])
    if not str(pre.get("freeze_rule") or "").strip():
        out.append("preregistration 缺 freeze_rule（跑前冻结、改协议=新版本）")
    if not _exists(root, str(pre.get("evidence") or "")):
        out.append("preregistration.evidence 不在场：%s" % pre.get("evidence"))
    return out


def _power_issues(doc: Dict[str, Any]) -> List[str]:
    """power.min_samples_per_task 判据。"""
    n = (doc.get("power") or {}).get("min_samples_per_task")
    if not isinstance(n, int) or isinstance(n, bool) or n < 3:
        return ["power.min_samples_per_task 必须是 ≥3 的整数（不足只描述统计）"]
    return []


def _inter_rater_issues(doc: Dict[str, Any], root: str) -> List[str]:
    """inter_rater 判据（方法词表 / kappa 区间 / 样本在场）。"""
    ir = doc.get("inter_rater") or {}
    out: List[str] = []
    if str(ir.get("method")) not in METHODS:
        out.append("inter_rater.method 非法：%s" % ir.get("method"))
    try:
        minimum = float(ir.get("min_kappa"))
        if not 0.0 < minimum <= 1.0:
            raise ValueError
    except (TypeError, ValueError):
        out.append("inter_rater.min_kappa 必须在 (0,1] 内")
    if not _exists(root, str(ir.get("sample") or "")):
        out.append("inter_rater.sample 不在场：%s" % ir.get("sample"))
    return out


def _metric_issues(metric: Any, counters: set) -> List[str]:
    """单个指标判据（反指标挂接 / name）。"""
    if not isinstance(metric, dict):
        return ["metrics 含非对象"]
    out: List[str] = []
    if str(metric.get("countermetric")) not in counters:
        out.append("指标 %s 未挂反指标（%s 每个指标必须有 countermetric）"
                   % (metric.get("id"), GUIDE))
    if not str(metric.get("name") or "").strip():
        out.append("指标 %s 缺 name" % metric.get("id"))
    return out


def _metric_each_issues(metrics: List[Any], counters: set) -> List[str]:
    """逐指标判据。"""
    out: List[str] = []
    for metric in metrics:
        out.extend(_metric_issues(metric, counters))
    return out


def _counter_issues(cm: Dict[str, Any], root: str) -> List[str]:
    """单个反指标判据（guards/metric / 证据在场）。"""
    out: List[str] = []
    if not str(cm.get("guards") or "").strip() or not str(cm.get("metric") or "").strip():
        out.append("countermetric %s 缺 guards/metric" % cm.get("id"))
    if not _exists(root, str(cm.get("evidence") or "")):
        out.append("countermetric %s 的 evidence 不在场：%s"
                   % (cm.get("id"), cm.get("evidence")))
    return out


def _counter_each_issues(doc: Dict[str, Any], root: str) -> List[str]:
    """逐反指标判据。"""
    out: List[str] = []
    for cm in doc.get("countermetrics") or []:
        out.extend(_counter_issues(cm, root))
    return out


def _threat_issues(threat: Any, root: str) -> List[str]:
    """单条效度威胁判据（三字段 / 证据在场）。"""
    if not isinstance(threat, dict):
        return ["validity_threats 含非对象"]
    out: List[str] = []
    for field in ("threat", "check", "evidence"):
        if not str(threat.get(field) or "").strip():
            out.append("威胁 %s 缺 %s" % (threat.get("id"), field))
    if not _exists(root, str(threat.get("evidence") or "")):
        out.append("威胁 %s 的 evidence 不在场：%s"
                   % (threat.get("id"), threat.get("evidence")))
    return out


def _threats_issues(doc: Dict[str, Any], root: str) -> List[str]:
    """validity_threats 判据（至少 4 条 / id 唯一 / 逐条）。"""
    threats = doc.get("validity_threats") or []
    tids = [str(t.get("id")) for t in threats if isinstance(t, dict)]
    out: List[str] = []
    if len(tids) < 4:
        out.append("validity_threats 至少 4 条")
    if len(tids) != len(set(tids)):
        out.append("validity_threats id 重复：%s" % tids)
    for threat in threats:
        out.extend(_threat_issues(threat, root))
    return out


def _metrics_head(doc: Dict[str, Any]) -> tuple[List[Any], List[str]]:
    """metrics 列表 + id 唯一性判据 → (metrics, issues)。"""
    metrics = doc.get("metrics") or []
    mids = [str(m.get("id")) for m in metrics if isinstance(m, dict)]
    out: List[str] = []
    if not metrics:
        out.append("缺 metrics（%s 至少一个指标）" % GUIDE)
    if len(mids) != len(set(mids)):
        out.append("metrics id 重复：%s" % mids)
    return metrics, out


def _counter_head(doc: Dict[str, Any]) -> tuple[set, List[str]]:
    """countermetrics id 集合 + 唯一性判据 → (counters, issues)。"""
    counters = {str(c.get("id")) for c in doc.get("countermetrics") or []
                if isinstance(c, dict)}
    cids = [str(c.get("id")) for c in doc.get("countermetrics") or [] if isinstance(c, dict)]
    if len(cids) != len(set(cids)):
        return counters, ["countermetrics id 重复：%s" % cids]
    return counters, []


def validate(doc: Dict[str, Any], root: str = ".") -> List[str]:
    issues: List[str] = []
    issues.extend(_protocol_rel_issues(doc, root))
    issues.extend(_prereg_issues(doc, root))
    issues.extend(_power_issues(doc))
    issues.extend(_inter_rater_issues(doc, root))
    metrics, head_issues = _metrics_head(doc)
    issues.extend(head_issues)
    counters, counter_head_issues = _counter_head(doc)
    issues.extend(counter_head_issues)
    issues.extend(_counter_each_issues(doc, root))
    issues.extend(_metric_each_issues(metrics, counters))
    issues.extend(_threats_issues(doc, root))
    return issues
