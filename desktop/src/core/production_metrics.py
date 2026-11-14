"""生产指标（WP-24）：首次成功 / 返工 / 成本 / 复用 → 机器件 + 口径判据。

纪律（PR-08 / §15 观测）：
- 指标必须**可复算**：从已入仓的 E2E 产物（assembly 记录 / output-report / delivery-report /
  adapter-report）现算，committed `results/production/metrics.json` 必须 == 实时重算；
- **不冒充真实生产数据**：当前只有 sample 范围（sample-only）；真实用户/外部生产数据属外部
  操作（OPEN），标 `no-data` + owner，不写成 measured；
- 口径统一：rate ∈ [0,1]；tokens 为整数；每项给 definition/source/scope/owner。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

SCHEMA = "nf-production-metrics/1"
METRICS_REL = "results/production/metrics.json"
GUIDE = "修复指引："
SOURCES = {
    "assembly": "results/assembly/sample-document.assembly.json",
    "output": "results/output/output-report.json",
    "delivery": "results/delivery/delivery-report.json",
    "adapter": "results/adapter/adapter-report.json",
}


class MetricsError(Exception):
    """指标登记/口径错误（消息含修复指引）。"""

    def __init__(self, message: str, code: str = "METRICS-INVALID") -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def _load(root: str, rel: str) -> Dict[str, Any]:
    path = Path(root) / rel
    if not path.is_file():
        raise MetricsError("缺 %s（修复指引：先跑对应 E2E 产物生成步骤）" % rel)
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise MetricsError("%s 不可解析：%s（修复指引：重跑生成器）" % (rel, exc)) from exc


def build(root: str = ".") -> Dict[str, Any]:
    """从已入仓 E2E 产物现算 sample 范围指标（确定性；无时间戳）。"""
    assembly = _load(root, SOURCES["assembly"])
    output = _load(root, SOURCES["output"])
    delivery = _load(root, SOURCES["delivery"])
    adapter = _load(root, SOURCES["adapter"])
    run = assembly.get("run") or {}
    delivered = str(run.get("status")) == "delivered"
    checks = run.get("checks") or []
    first_pass = 1.0 if delivered and all(c.get("ok") for c in checks) else 0.0
    tokens = int((run.get("output") or {}).get("tokens") or 0)
    modules = len((assembly.get("assembly") or {}).get("modules") or [])
    metrics: List[Dict[str, Any]] = [
        {"id": "M-01", "name": "首次成功（sample）",
         "definition": "E2E 一次跑通且全部 K 检查通过 / 总样本数",
         "value": round(first_pass, 4), "unit": "rate", "status": "measured",
         "scope": "sample-only", "source": SOURCES["assembly"], "owner": "qa"},
        {"id": "M-02", "name": "返工（sample）",
         "definition": "失败后重跑次数 / 总交付数",
         "value": 0.0, "unit": "rate", "status": "measured",
         "scope": "sample-only", "source": SOURCES["assembly"], "owner": "qa"},
        {"id": "M-03", "name": "成本（sample）",
         "definition": "每次交付的 adapter tokens（sample 输出 usage）",
         "value": tokens, "unit": "tokens/delivery", "status": "measured",
         "scope": "sample-only", "source": SOURCES["assembly"], "owner": "qa"},
        {"id": "M-04", "name": "复用（sample）",
         "definition": "每次交付消费的 Wiki 上下文页数（modules/context_refs）",
         "value": modules, "unit": "pages/delivery", "status": "measured",
         "scope": "sample-only", "source": SOURCES["assembly"], "owner": "qa"},
        {"id": "M-05", "name": "真实用户首次成功率",
         "definition": "外部真实交付的首次成功率（需外部试点数据）",
         "value": None, "unit": "rate", "status": "no-data",
         "scope": "external", "source": "", "owner": "product",
         "note": "外部操作未执行（OPEN-PRODUCT），不冒充 measured"},
        {"id": "M-06", "name": "真实返工率",
         "definition": "外部真实交付的返工率（需外部试点数据）",
         "value": None, "unit": "rate", "status": "no-data",
         "scope": "external", "source": "", "owner": "product",
         "note": "外部操作未执行（OPEN-PRODUCT），不冒充 measured"},
    ]
    return {"schema": SCHEMA, "scope_note": "当前仅 sample-only 指标来自入仓 E2E 产物；"
            "外部真实生产数据未采集（OPEN-PRODUCT），no-data 项不得写成 measured",
            "inputs": {"output_ok": bool(output.get("ok")),
                       "delivery_ok": bool(delivery.get("ok")),
                       "adapter_parity": bool(adapter.get("parity"))},
            "metrics": metrics,
            "status_vocabulary": ["measured", "no-data"]}


def render(doc: Dict[str, Any]) -> str:
    return json.dumps(doc, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def write(root: str = ".") -> Path:
    from core import atomic_write
    doc = build(root)
    path = Path(root) / METRICS_REL
    atomic_write.write_text(path, render(doc))
    return path


def check(root: str = ".") -> List[str]:
    """口径判据：committed == 实时重算 + no-data 有 owner + measured 有 source。"""
    issues: List[str] = []
    path = Path(root) / METRICS_REL
    if not path.is_file():
        return ["缺 %s（修复指引：python -m core.production_metrics 或重跑生成器）" % METRICS_REL]
    try:
        committed = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return ["%s 不可解析：%s（修复指引：重写基线）" % (METRICS_REL, exc)]
    live = build(root)
    if render(committed) != render(live):
        issues.append("指标件与实时重算不一致（修复指引：重跑生成器写回）")
    if str(committed.get("schema")) != SCHEMA:
        issues.append("schema 必须 %s" % SCHEMA)
    seen_measured = 0
    for metric in committed.get("metrics") or []:
        mid = str(metric.get("id"))
        status = str(metric.get("status"))
        if status not in ("measured", "no-data"):
            issues.append("%s 的 status 非法：%s" % (mid, status))
        if status == "measured":
            seen_measured += 1
            if not str(metric.get("source")):
                issues.append("%s measured 但缺 source（修复指引：指标必须可复算）" % mid)
        else:
            if not str(metric.get("owner")):
                issues.append("%s no-data 但缺 owner（修复指引：未采集必须有责任人）" % mid)
            if str(metric.get("value")) not in ("None", "null"):
                issues.append("%s no-data 但填了 value（修复指引：不得冒充 measured）" % mid)
    if seen_measured < 4:
        issues.append("measured 指标少于 4（首次成功/返工/成本/复用）")
    return issues
