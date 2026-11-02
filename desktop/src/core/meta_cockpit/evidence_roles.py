"""Evidence-role readiness mapping for a cockpit turn.

This is a presence and trust report, not a relevance or quality score.
Every requested role resolves to source identifiers, excerpt digests, graph
edges, or an explicit missing/context-only/advisory-only state.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from . import epistemic_agenda

ROLE_TERMS = {
    "definition": ("定义", "术语", "概念", "边界", "范围", "命名"),
    "scope": ("scope", "范围", "适用", "边界"),
    "examples": ("例如", "示例", "比如", "案例", "样例"),
    "current-state": ("当前", "状态", "现状", "输入", "产物"),
    "events": ("事件", "日志", "时间", "触发", "信号"),
    "observable-signals": ("指标", "监控", "观测", "阈值", "告警", "检测"),
    "counterexamples": ("风险", "失败", "故障", "异常", "反例", "攻击", "回退"),
    "constraints": ("约束", "限制", "不允许", "必须", "边界"),
    "tradeoffs": ("取舍", "权衡", "成本", "优劣", "代价", "收益"),
    "fallback": ("回退", "恢复", "降级", "撤回", "失败"),
    "evidence": ("证据", "引用", "来源", "来源链", "核验"),
}

STRUCTURAL_ROLES = {
    "relations",
    "prerequisites",
    "budget",
    "acceptance-obligations",
    "unresolved-conflicts",
    "source-anchors",
    "current-state",
    "fallback",
}
KNOWN_ROLES = set(ROLE_TERMS) | STRUCTURAL_ROLES


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str
    ).encode("utf-8")


def digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _trust_status(refs: list[dict]) -> str:
    trusts = {item["trust"] for item in refs}
    if "local-trusted" in trusts:
        return "available"
    if "external-advisory" in trusts:
        return "advisory-only"
    if trusts:
        return "context-only"
    return "missing"


def _ref_role(role: str, refs: list[dict]) -> dict:
    terms = ROLE_TERMS.get(role)
    if terms is None:
        return {
            "role": role,
            "status": "missing",
            "source_ids": [],
            "excerpt_digests": [],
            "graph_edges": [],
        }
    matched = []
    for item in refs:
        explicit = item.get("matched_roles", [])
        if role in explicit:
            matched.append(item)
            continue
        haystack = (
            str(item.get("text", ""))
            + " "
            + " ".join(str(term) for term in item.get("matched_terms", []))
        ).casefold()
        if any(term.casefold() in haystack for term in terms):
            matched.append(item)
    return {
        "role": role,
        "status": _trust_status(matched),
        "source_ids": sorted({str(item["source"]) for item in matched}),
        "excerpt_digests": sorted({str(item["content_digest"]) for item in matched}),
        "graph_edges": [],
    }


def _structural_role(role: str, state: dict, context: dict) -> dict:
    artifact = state.get("artifact", {})
    graph = context.get("graph_slice", {})
    refs = context.get("references", [])
    edges = graph.get("edges", [])
    graph_edges: list[dict] = []
    source_ids: list[str] = []
    if role == "current-state":
        if state.get("artifact") or state.get("goal"):
            source_ids.append("session-state")
    elif role == "fallback":
        if state.get("fallback") or artifact.get("risks"):
            source_ids.append("session-state")
    elif role == "relations":
        graph_edges = [
            {"from": edge["from"], "to": edge["to"], "kind": edge["kind"], "source": edge["source"]}
            for edge in edges
            if edge["kind"] in {"nf-mapping", "state-relation"}
        ]
        if artifact.get("relations"):
            source_ids.append("session-state")
    elif role == "prerequisites":
        graph_edges = [
            {"from": edge["from"], "to": edge["to"], "kind": edge["kind"], "source": edge["source"]}
            for edge in edges
            if edge["kind"] == "domain-prerequisite"
        ]
    elif role == "budget":
        if state.get("budget") or state.get("budget_state"):
            source_ids.append("session-budget")
    elif role == "acceptance-obligations":
        if epistemic_agenda.build_agenda(state)["obligations"]:
            source_ids.append("epistemic-agenda")
    elif role == "unresolved-conflicts":
        if state.get("open_questions"):
            source_ids.append("open-questions")
        if graph.get("warnings"):
            source_ids.append("graph-warnings")
    elif role == "source-anchors":
        source_ids = sorted({str(item["source"]) for item in refs})
    available = bool(source_ids or graph_edges)
    if role == "unresolved-conflicts" and source_ids:
        status = "available"
    else:
        status = "available" if available else "missing"
    return {
        "role": role,
        "status": status,
        "source_ids": sorted(set(source_ids)),
        "excerpt_digests": [],
        "graph_edges": graph_edges,
    }


def build_role_inventory(state: dict, context: dict, requested: list[str]) -> dict:
    roles = sorted(set(requested))
    unknown = [role for role in roles if role not in KNOWN_ROLES]
    refs = context.get("references", [])
    items = []
    for role in roles:
        if role in STRUCTURAL_ROLES:
            item = _structural_role(role, state, context)
        else:
            item = _ref_role(role, refs)
        items.append(item)
    gaps = [
        item["role"]
        for item in items
        if item["status"] in {"missing", "context-only", "advisory-only"}
    ]
    return {
        "schema": "nf-evidence-roles/1",
        "requested": roles,
        "roles": items,
        "gaps": gaps,
        "unknown": unknown,
        "digest": digest(items),
        "no_scoring": True,
    }
