from __future__ import annotations

import copy
import re
from dataclasses import dataclass
from pathlib import Path

from core.meta_cockpit import coherence, context_pack, task_profile
from core.meta_cockpit import constrained_choice as cons
from core.meta_cockpit import live_selector as ls

SECRET_PATTERNS = (
    re.compile(r"(?i)(bearer\s+)[A-Za-z0-9._~+/=-]+"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{8,}\b"),
    re.compile(r"(?i)((?:token|api[_-]?key|secret)\s*[=:]\s*)[^\s,;]+"),
)


def safe_error(exc: Exception) -> str:
    if isinstance(exc, (ValueError, PermissionError, TimeoutError)):
        text = str(exc)
    else:
        text = type(exc).__name__
    for pattern in SECRET_PATTERNS:
        text = pattern.sub(lambda match: match.group(1) + "***" if match.lastindex else "***", text)
    return text


def stop(reason: str) -> dict:
    return {"choice": None, "reason": reason, "stop": True}


def completion_gaps(state: dict) -> list[str]:
    facet = task_profile.build_facet_agenda(state)
    coherent = coherence.evaluate(state)
    return (
        ls.unmet(state)
        + ["facet:" + item for item in facet["gaps"]]
        + ["coherence:" + item["id"] for item in coherent["issues"]]
    )


def complete(state: dict) -> bool:
    return not completion_gaps(state)


def first_policy(state: dict, candidates: list[dict]) -> dict:
    return (
        stop("no candidates")
        if not candidates
        else {"choice": 0, "reason": "first candidate", "stop": False}
    )


def source_snapshot_of(payload: dict) -> list[dict]:
    """上下文包 -> 来源快照（引用面 + 图切片面；contextual_policy 与 run 共用单源）。"""
    return [
        {
            "source": item["source"],
            "path": item["path"],
            "role": item["role"],
            "trust": item["trust"],
            "content_digest": item["content_digest"],
            "file_digest": item["file_digest"],
        }
        for item in payload["context"]["references"]
    ] + [
        {
            "source": item["source"],
            "path": item["path"],
            "role": "graph-source",
            "trust": "local-trusted",
            "content_digest": item["file_digest"],
            "file_digest": item["file_digest"],
        }
        for item in payload["graph_slice"]["sources"]
    ]


def external_context_of(payload: dict) -> bool:
    """上下文包 -> 是否含外部上下文源（同上，共用单源）。"""
    return any(
        source.get("kind") == "mcp-context-provider" for source in payload["context"]["sources"]
    )


def contextual_policy(adapter, providers: list | None = None):
    """把模型 adapter 接到候选上下文包，同时保持短响应协议。"""

    def policy(state: dict, candidates: list[dict]) -> dict:
        payload = cons.build_prompt_payload(state, candidates, providers=providers)
        context_digest = context_pack.digest(payload)
        context_units = payload["context"]["budget"]["estimated_units"]
        source_snapshot = source_snapshot_of(payload)
        external_context = external_context_of(payload)
        response = adapter(copy.deepcopy(payload))
        if isinstance(response, dict):
            wrapped = ContextualResponse(response)
            wrapped.context_digest = context_digest
            wrapped.context_units = context_units
            wrapped.source_snapshot = source_snapshot
            wrapped.external_context = external_context
            return wrapped
        return response

    policy.providers = providers
    return policy


class ContextualResponse(dict):
    context_digest: str
    context_units: int
    source_snapshot: list[dict]
    external_context: bool


# C901: this is the single transaction boundary for one session turn. Keeping
# validation, selection, execution, calibration and journal commit visible in
# one state machine preserves fail-closed ordering; lower-level logic is
# delegated to tested helpers and modules.
@dataclass(frozen=True)
class LoopOptions:
    """参数对象（审计 C-007：把成组参数收成不可变对象）。"""
    store_path: str | Path | None = None
    max_turns: int = 8
    state: dict | None = None
    journal_path: str | Path | None = None
    max_seconds: float | None = None
    max_context_units: int | None = None
    injections: dict[int, list[str]] | None = None
