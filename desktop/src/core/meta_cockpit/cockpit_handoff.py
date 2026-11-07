"""驾驶状态到生产产物的无评分交接面。"""

from __future__ import annotations

import copy
import hashlib
import json
import re
from pathlib import Path

from . import (
    abstention,
    coherence,
    context_pack,
    domain_sources,
    json_asset,
    secret_guard,
    task_handoff,
    task_profile,
)
from . import live_selector as ls
from . import schema_compat as jsonschema

BASE = Path(__file__).parent
REGISTRY_BYTES = (BASE / "nf_source_registry.json").read_bytes()
REGISTRY = json_asset.load_bytes(REGISTRY_BYTES)
SOURCE_IDS = {item["id"] for item in REGISTRY["sources"]} | set(domain_sources.BY_ID)
SCHEMA = json_asset.load(BASE / "cockpit_handoff.schema.json")
VALIDATOR = jsonschema.Draft202012Validator(SCHEMA)
EVIDENCE_RE = re.compile(r"(?:P03|NF-1|techdoc|M\d+|community:[^\s+§]+)")


def _digest(value) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def build_handoff(state: dict, termination: str = "done") -> dict:
    secrets = secret_guard.find(state, "$.state")
    if secrets:
        raise ValueError(
            "sensitive data in handoff state: {}".format(",".join(item["path"] for item in secrets))
        )
    artifact = state["artifact"]
    context = context_pack.build_context_pack(state["goal"], state, [])
    domain_edges = [
        edge for edge in context["graph_slice"]["edges"] if edge["kind"] == "domain-prerequisite"
    ]
    scope_sources = {
        item["source"] for item in context["references"] if item["role"] == "domain-scope"
    }
    excerpt_sources = {
        item["source"]
        for item in context["references"]
        if item["role"] in {"content", "domain-content"}
    }
    all_excerpt_sources = scope_sources | excerpt_sources
    evidence = [str(item) for item in artifact.get("evidence", [])]
    grounded, unsupported, scoped = [], [], []
    unresolved_sources = set()
    for item in evidence:
        refs = EVIDENCE_RE.findall(item)
        missing = {ref for ref in refs if ref not in all_excerpt_sources}
        unresolved_sources |= missing
        if not refs or missing or not all(ref in SOURCE_IDS for ref in refs):
            unsupported.append(item)
        elif all(ref in excerpt_sources for ref in refs):
            grounded.append(item)
        else:
            scoped.append(item)
    gaps = list(ls.unmet(state))
    facets = task_profile.build_facet_agenda(state)
    gaps += ["task-facet:" + item for item in facets["gaps"]]
    gaps += ["coherence:" + item["id"] for item in coherence.issues(state)]
    if unresolved_sources:
        gaps.append("evidence-without-excerpt")
    if scoped and not grounded:
        gaps.append("domain-scope-only")
    if unsupported:
        gaps.append("unsupported-evidence")
    if artifact.get("verified") and not grounded:
        gaps.append("verified-without-grounded-evidence")
    if artifact.get("plan") and not grounded:
        gaps.append("ungrounded-synthesis")
    sections = {
        "problem": artifact.get("representation") or state["goal"],
        "decomposition": copy.deepcopy(artifact.get("parts", [])),
        "relations": copy.deepcopy(artifact.get("relations", [])),
        "counterexamples": copy.deepcopy(artifact.get("risks", [])),
        "synthesis": copy.deepcopy(artifact.get("plan", [])),
        "resolutions": copy.deepcopy(artifact.get("resolutions", [])),
        "evidence": grounded,
        "open_questions": copy.deepcopy(state.get("open_questions", [])),
    }
    result = {
        "schema": "nf-cockpit-handoff/1",
        "goal": state["goal"],
        "state_digest": _digest(state),
        "sections": sections,
        "provenance": {
            "trace": copy.deepcopy(artifact.get("trace", [])),
            "grounded_evidence": grounded,
            "unsupported_evidence": unsupported,
            "scope_evidence": scoped,
            "source_registry_digest": hashlib.sha256(REGISTRY_BYTES).hexdigest(),
            "domain_index_digest": domain_sources.INDEX_DIGEST,
            "context_digest": context["dynamic_digest"],
            "evidence_excerpts": context["references"],
            "unresolved_sources": sorted(unresolved_sources),
            "scope_only_sources": sorted(
                {
                    ref
                    for item in scoped
                    for ref in EVIDENCE_RE.findall(item)
                    if ref in scope_sources
                }
            ),
            "graph_context": {
                "matched_concepts": context["graph_slice"]["matched_concepts"],
                "nodes": context["graph_slice"]["domain_nodes"],
                "edges": domain_edges,
                "warnings": context["graph_slice"]["warnings"],
            },
        },
        "gaps": sorted(set(gaps)),
        "task_projection": task_handoff.project(state),
    }
    result["abstention"] = abstention.build(state, result["gaps"], termination=termination)
    issues = [error.message for error in VALIDATOR.iter_errors(result)]
    if issues:
        raise ValueError("invalid handoff: {}".format("; ".join(issues)))
    return result


def render_markdown(handoff: dict) -> str:
    sections = handoff["sections"]

    def bullets(values) -> str:
        return "\n".join(f"- {value}" for value in values) or "- 暂无"

    excerpts = handoff["provenance"]["evidence_excerpts"]
    excerpt_lines = []
    for item in excerpts:
        excerpt_lines.append(
            f"- `{item['source']}:{item['line']}` `{item['path']}` "
            f"chars {item['char_start']}-{item['char_end']}\n  > {item['text']}"
        )
    excerpt_text = "\n".join(excerpt_lines) or "- 暂无"
    graph_context = handoff["provenance"]["graph_context"]
    graph_lines = [
        "- {} → {}（`{}`）".format(edge["from"], edge["to"], edge["source"])
        for edge in graph_context["edges"]
    ]
    graph_text = "\n".join(graph_lines) or "- 暂无"
    warning_lines = [
        "- `{}`: {} `{}`".format(warning["source"], warning["kind"], " → ".join(warning["cycle"]))
        for warning in graph_context["warnings"]
    ]
    warning_text = "\n".join(warning_lines) or "- 暂无"
    abstention = handoff["abstention"]
    abstention_lines = [
        "- status：`{}`".format(abstention["status"]),
        "- human action：`{}`".format(str(abstention["human_action_required"]).lower()),
        "- repair keys：%s"
        % (", ".join(f"`{key}`" for key in abstention["repair_keys"]) or "暂无"),
    ]
    for reason in abstention["reasons"]:
        abstention_lines.append("- `{}`（{}）".format(reason["gap"], reason["kind"]))
    abstention_text = "\n".join(abstention_lines)

    lines = [
        "# 认知驾驶交接",
        "",
        "> state digest：`{}`".format(handoff["state_digest"]),
        "",
        "## 目标",
        "",
        str(sections["problem"]),
        "",
        "## 策略状态",
        "",
        abstention_text,
        "",
        task_handoff.render_markdown(handoff["task_projection"]),
        "",
        "## 拆解",
        "",
        bullets(sections["decomposition"]),
        "",
        "## 关系",
        "",
        bullets(sections["relations"]),
        "",
        "## 反例与风险",
        "",
        bullets(sections["counterexamples"]),
        "",
        "## 综合",
        "",
        bullets(sections["synthesis"]),
        "",
        "## 冲突消解",
        "",
        bullets(sections["resolutions"]),
        "",
        "## 证据",
        "",
        bullets(sections["evidence"]),
        "",
        "## 证据摘录",
        "",
        excerpt_text,
        "",
        "## 域内概念关系",
        "",
        graph_text,
        "",
        "## 图警告",
        "",
        warning_text,
        "",
        "## 未解问题",
        "",
        bullets(sections["open_questions"]),
        "",
        "## 交接缺口",
        "",
        bullets(handoff["gaps"]),
        "",
    ]
    return "\n".join(lines)
