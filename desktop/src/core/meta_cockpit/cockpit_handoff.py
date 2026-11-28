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


def _evidence_classes(
    evidence: list[str], all_excerpt_sources: set[str], excerpt_sources: set[str]
) -> tuple[list[str], list[str], list[str], set[str]]:
    """证据按「落地 / 未支撑 / 仅域范围」分类，并收集未解来源。"""
    grounded, unsupported, scoped = [], [], []
    unresolved_sources: set[str] = set()
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
    return grounded, unsupported, scoped, unresolved_sources


def _artifact_gaps(
    artifact: dict,
    grounded: list[str],
    scoped: list[str],
    unsupported: list[str],
    unresolved_sources: set[str],
) -> list[str]:
    gaps = []
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
    return gaps


def _gaps(
    state: dict,
    artifact: dict,
    grounded: list[str],
    scoped: list[str],
    unsupported: list[str],
    unresolved_sources: set[str],
) -> list[str]:
    gaps = list(ls.unmet(state))
    facets = task_profile.build_facet_agenda(state)
    gaps += ["task-facet:" + item for item in facets["gaps"]]
    gaps += ["coherence:" + item["id"] for item in coherence.issues(state)]
    gaps += _artifact_gaps(artifact, grounded, scoped, unsupported, unresolved_sources)
    return gaps


def _scope_only_sources(scoped: list[str], scope_sources: set[str]) -> list[str]:
    return sorted(
        {
            ref
            for item in scoped
            for ref in EVIDENCE_RE.findall(item)
            if ref in scope_sources
        }
    )


def _sections(artifact: dict, state: dict, grounded: list[str]) -> dict:
    return {
        "problem": artifact.get("representation") or state["goal"],
        "decomposition": copy.deepcopy(artifact.get("parts", [])),
        "relations": copy.deepcopy(artifact.get("relations", [])),
        "counterexamples": copy.deepcopy(artifact.get("risks", [])),
        "synthesis": copy.deepcopy(artifact.get("plan", [])),
        "resolutions": copy.deepcopy(artifact.get("resolutions", [])),
        "evidence": grounded,
        "open_questions": copy.deepcopy(state.get("open_questions", [])),
    }


def _provenance(
    artifact: dict,
    context: dict,
    grounded: list[str],
    unsupported: list[str],
    scoped: list[str],
    unresolved_sources: set[str],
) -> dict:
    return {
        "trace": copy.deepcopy(artifact.get("trace", [])),
        "grounded_evidence": grounded,
        "unsupported_evidence": unsupported,
        "scope_evidence": scoped,
        "source_registry_digest": hashlib.sha256(REGISTRY_BYTES).hexdigest(),
        "domain_index_digest": domain_sources.INDEX_DIGEST,
        "context_digest": context["dynamic_digest"],
        "evidence_excerpts": context["references"],
        "unresolved_sources": sorted(unresolved_sources),
        "scope_only_sources": _scope_only_sources(scoped, _scope_sources(context["references"])),
        "graph_context": {
            "matched_concepts": context["graph_slice"]["matched_concepts"],
            "nodes": context["graph_slice"]["domain_nodes"],
            "edges": [
                edge
                for edge in context["graph_slice"]["edges"]
                if edge["kind"] == "domain-prerequisite"
            ],
            "warnings": context["graph_slice"]["warnings"],
        },
    }


def _scope_sources(references: list[dict]) -> set[str]:
    return {item["source"] for item in references if item["role"] == "domain-scope"}


def _excerpt_sources(references: list[dict]) -> set[str]:
    return {
        item["source"]
        for item in references
        if item["role"] in {"content", "domain-content"}
    }


def build_handoff(state: dict, termination: str = "done") -> dict:
    secrets = secret_guard.find(state, "$.state")
    if secrets:
        raise ValueError(
            "sensitive data in handoff state: {}".format(",".join(item["path"] for item in secrets))
        )
    artifact = state["artifact"]
    context = context_pack.build_context_pack(state["goal"], state, [])
    scope_sources = _scope_sources(context["references"])
    excerpt_sources = _excerpt_sources(context["references"])
    all_excerpt_sources = scope_sources | excerpt_sources
    evidence = [str(item) for item in artifact.get("evidence", [])]
    grounded, unsupported, scoped, unresolved_sources = _evidence_classes(
        evidence, all_excerpt_sources, excerpt_sources
    )
    gaps = _gaps(state, artifact, grounded, scoped, unsupported, unresolved_sources)
    result = {
        "schema": "nf-cockpit-handoff/1",
        "goal": state["goal"],
        "state_digest": _digest(state),
        "sections": _sections(artifact, state, grounded),
        "provenance": _provenance(
            artifact, context, grounded, unsupported, scoped, unresolved_sources
        ),
        "gaps": sorted(set(gaps)),
        "task_projection": task_handoff.project(state),
    }
    result["abstention"] = abstention.build(state, result["gaps"], termination=termination)
    issues = [error.message for error in VALIDATOR.iter_errors(result)]
    if issues:
        raise ValueError("invalid handoff: {}".format("; ".join(issues)))
    return result


def _excerpt_lines(excerpts: list[dict]) -> list[str]:
    lines = []
    for item in excerpts:
        lines.append(
            f"- `{item['source']}:{item['line']}` `{item['path']}` "
            f"chars {item['char_start']}-{item['char_end']}\n  > {item['text']}"
        )
    return lines


def _graph_lines(graph_context: dict) -> list[str]:
    return [
        "- {} → {}（`{}`）".format(edge["from"], edge["to"], edge["source"])
        for edge in graph_context["edges"]
    ]


def _graph_warning_lines(graph_context: dict) -> list[str]:
    return [
        "- `{}`: {} `{}`".format(warning["source"], warning["kind"], " → ".join(warning["cycle"]))
        for warning in graph_context["warnings"]
    ]


def _abstention_lines(abstention: dict) -> list[str]:
    lines = [
        "- status：`{}`".format(abstention["status"]),
        "- human action：`{}`".format(str(abstention["human_action_required"]).lower()),
        "- repair keys：%s"
        % (", ".join(f"`{key}`" for key in abstention["repair_keys"]) or "暂无"),
    ]
    for reason in abstention["reasons"]:
        lines.append("- `{}`（{}）".format(reason["gap"], reason["kind"]))
    return lines


def render_markdown(handoff: dict) -> str:
    sections = handoff["sections"]

    def bullets(values) -> str:
        return "\n".join(f"- {value}" for value in values) or "- 暂无"

    graph_context = handoff["provenance"]["graph_context"]
    excerpt_text = "\n".join(_excerpt_lines(handoff["provenance"]["evidence_excerpts"])) or "- 暂无"
    graph_text = "\n".join(_graph_lines(graph_context)) or "- 暂无"
    warning_text = "\n".join(_graph_warning_lines(graph_context)) or "- 暂无"
    abstention_text = "\n".join(_abstention_lines(handoff["abstention"]))
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
