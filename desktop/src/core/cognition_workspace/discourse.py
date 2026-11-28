"""话语状态（nf-discourse-state/1）：认知工作台 L0 的唯一真源。

状态只记「问题/假设/张力/未答问题/已做动作」五类事实，不记结论质量、不打分。
digest = sha256(canonical(state 去掉 digest 字段))，任何一步改动都会换 digest。
"""
from __future__ import annotations

import copy
import hashlib
import json
from typing import Any

SCHEMA = "nf-discourse-state/1"
GUIDE = "修复指引："


def canonical(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":")).encode("utf-8")


def digest_of(obj: Any) -> str:
    return hashlib.sha256(canonical(obj)).hexdigest()


def text_digest(text: str) -> str:
    return hashlib.sha256(str(text).encode("utf-8")).hexdigest()


def new(problem: str, session_id: str = "", steps_max: int = 24) -> dict[str, Any]:
    """开一个新的 discourse（问题陈述必填）。"""
    if not str(problem).strip():
        raise ValueError("问题陈述不能为空（" + GUIDE + "给一句能被反驳的问题）")
    if not isinstance(steps_max, int) or steps_max < 1:
        raise ValueError("steps_max 必须是 ≥1 的整数（" + GUIDE + "默认 24）")
    state: dict[str, Any] = {
        "schema": SCHEMA,
        "session_id": session_id or digest_of({"problem": problem, "seed": 0})[:16],
        "problem": {"statement": str(problem), "digest": text_digest(problem)},
        "assumptions": [],
        "tensions": [],
        "open_questions": [],
        "moves": [],
        "budget": {"steps_max": steps_max, "steps_used": 0},
        "status": "open",
    }
    state["digest"] = digest_of(state)
    return state


def _bump(state: dict[str, Any]) -> None:
    state["budget"]["steps_used"] = len(state["moves"])
    state["digest"] = digest_of({k: v for k, v in state.items() if k != "digest"})


def _delta_restated(state: dict[str, Any], delta: dict[str, Any]) -> None:
    state["problem"] = {"statement": str(delta.get("statement")
                                         or state["problem"]["statement"]),
                        "digest": str(delta["after_digest"])}
    state["open_questions"].append({"kind": "restated", "changed_terms":
                                    list(delta["changed_terms"])})


def _delta_suspended(state: dict[str, Any], delta: dict[str, Any]) -> None:
    state["assumptions"].append({"id": str(delta["assumption_id"]),
                                 "status": "suspended",
                                 "reason": str(delta["reason"])})


def _delta_revived(state: dict[str, Any], delta: dict[str, Any]) -> None:
    for item in state["assumptions"]:
        if item["id"] == delta["assumption_id"]:
            item["status"] = "active"
            item["reason"] = str(delta["reason"])
            break
    else:
        state["assumptions"].append({"id": str(delta["assumption_id"]),
                                     "status": "active",
                                     "reason": str(delta["reason"])})


def _delta_concept(state: dict[str, Any], delta: dict[str, Any]) -> None:
    state["open_questions"].append({"kind": "concept", "concept": str(delta["concept"]),
                                    "distinctions": list(delta["distinctions"])})


def _delta_tension(state: dict[str, Any], delta: dict[str, Any]) -> None:
    state["tensions"].append({"between": list(delta["between"]),
                              "statement": str(delta["statement"])})


def _delta_open_question(state: dict[str, Any], delta: dict[str, Any]) -> None:
    kind = str(delta["kind"])
    item = {"kind": kind}
    for key in ("hypothesis", "expected_observation", "case", "near_miss",
                "claim", "breaks", "objection", "reasons"):
        if key in delta:
            item[key] = delta[key]
    state["open_questions"].append(item)


def _delta_mapping(state: dict[str, Any], delta: dict[str, Any]) -> None:
    state["open_questions"].append({"kind": "analogy", "source": str(delta["source"]),
                                    "target": str(delta["target"]),
                                    "preserved": list(delta["preserved"]),
                                    "broken": list(delta["broken"])})


def _delta_stakeholder(state: dict[str, Any], delta: dict[str, Any]) -> None:
    state["open_questions"].append({"kind": "perspective",
                                    "perspective": str(delta["perspective"]),
                                    "obligations": list(delta["obligations"])})


def _delta_provenance(state: dict[str, Any], delta: dict[str, Any]) -> None:
    state["open_questions"].append({"kind": "genealogy", "origin": str(delta["origin"]),
                                    "lineage": list(delta["lineage"])})


def _delta_subquestions(state: dict[str, Any], delta: dict[str, Any]) -> None:
    state["open_questions"].append({"kind": "decomposition",
                                    "subquestions": list(delta["subquestions"])})


def _delta_commitment(state: dict[str, Any], delta: dict[str, Any]) -> None:
    state["open_questions"].append({"kind": "commitment", "claim": str(delta["claim"]),
                                    "evidence_standard": str(delta["evidence_standard"])})


def _delta_evidence_standard(state: dict[str, Any], delta: dict[str, Any]) -> None:
    state["open_questions"].append({"kind": "evidence_standard",
                                    "claim_kind": str(delta["claim_kind"]),
                                    "required": list(delta["required"])})


_DELTA_HANDLERS = {
    "question_restated": _delta_restated,
    "assumption_suspended": _delta_suspended,
    "assumption_revived": _delta_revived,
    "concept_clarified": _delta_concept,
    "tension_added": _delta_tension,
    "hypothesis_proposed": _delta_open_question,
    "boundary_added": _delta_open_question,
    "counterexample_found": _delta_open_question,
    "objection_strengthened": _delta_open_question,
    "mapping_added": _delta_mapping,
    "stakeholder_added": _delta_stakeholder,
    "provenance_added": _delta_provenance,
    "subquestions_added": _delta_subquestions,
    "commitment_formed": _delta_commitment,
    "evidence_standard": _delta_evidence_standard,
}


def apply_delta(state: dict[str, Any], move_id: str, delta: dict[str, Any]) -> None:
    """把 frame_delta 落到状态上（只做最小事实记录，不做推理）。"""
    kind = str(delta["kind"])
    handler = _DELTA_HANDLERS.get(kind)
    if handler is None:
        raise ValueError("未知 frame_delta.kind：" + kind + "（" + GUIDE + "见 moves.DELTA_KINDS）")
    handler(state, delta)


def _shape_issues(state: Any) -> list[str] | None:
    """schema 与必填字段：问题非空即到此为止，None 表示可继续做语义校验。"""
    if not isinstance(state, dict) or str(state.get("schema") or "") != SCHEMA:
        return ["discourse schema 不匹配（" + GUIDE + "需要 " + SCHEMA + "）"]
    issues: list[str] = []
    for field in ("session_id", "problem", "assumptions", "tensions", "open_questions",
                  "moves", "budget", "status"):
        if field not in state:
            issues.append("缺字段 " + field + "（" + GUIDE + "用 discourse.new 生成，不手搓）")
    return issues or None


def _semantic_issues(state: dict[str, Any]) -> list[str]:
    """字段都在场后的状态语义校验。"""
    issues: list[str] = []
    if state["status"] not in ("open", "closed"):
        issues.append("status 只能是 open/closed（" + GUIDE + "close 用 session.close）")
    if not isinstance(state["problem"], dict) or "statement" not in state["problem"]:
        issues.append("problem 必须是 {statement, digest}（" + GUIDE + "重建状态）")
    if state["budget"].get("steps_used") != len(state["moves"]):
        issues.append("budget.steps_used 与 moves 数不一致（" + GUIDE + "手改过状态）")
    expected = digest_of({k: v for k, v in state.items() if k != "digest"})
    if state.get("digest") != expected:
        issues.append("digest 不匹配（" + GUIDE + "状态被改过——用重放重建）")
    return issues


def validate(state: Any) -> list[str]:
    """状态形状校验 → 问题列表（空 = 合法）。"""
    shape = _shape_issues(state)
    if shape is not None:
        return shape
    return _semantic_issues(state)


def append_move(state: dict[str, Any], move_id: str,
                delta: dict[str, Any]) -> dict[str, Any]:
    """把一次动作写进状态（返回新状态，不改原对象）。"""
    issues = validate(state)
    if issues:
        raise ValueError("状态不合法：" + "；".join(issues[:2]))
    if state["status"] != "open":
        raise ValueError("会话已关闭，不能再加动作（" + GUIDE + "新开一个 session）")
    if state["budget"]["steps_used"] >= state["budget"]["steps_max"]:
        raise ValueError("步数已到上限 " + str(state["budget"]["steps_max"])
                         + "（" + GUIDE + "收口或新开会话）")
    new_state = copy.deepcopy(state)
    apply_delta(new_state, move_id, delta)
    new_state["moves"].append({"seq": len(new_state["moves"]) + 1, "move": move_id,
                               "delta": delta})
    _bump(new_state)
    return new_state


def close(state: dict[str, Any], verdict: str = "") -> dict[str, Any]:
    new_state = copy.deepcopy(state)
    new_state["status"] = "closed"
    if verdict:
        new_state["verdict"] = str(verdict)
    _bump(new_state)
    return new_state


def summary(state: dict[str, Any]) -> dict[str, Any]:
    """只计数、不打分的摘要（给 CLI 用）。"""
    try:
        moves_used = len(state.get("moves") or [])
    except TypeError:  # pragma: no cover
        moves_used = 0
    return {"schema": SCHEMA, "session_id": state.get("session_id"),
            "status": state.get("status"),
            "moves_used": moves_used,
            "steps_max": (state.get("budget") or {}).get("steps_max"),
            "assumptions": len(state.get("assumptions") or []),
            "tensions": len(state.get("tensions") or []),
            "open_questions": len(state.get("open_questions") or []),
            "digest": state.get("digest")}
