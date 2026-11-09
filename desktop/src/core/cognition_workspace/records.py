"""只追加记录与重放：每一步都要能被复算回同一状态（否则记录只是日志）。

记录链：record{seq, move, delta, state_digest, prev}；
record.digest = sha256(canonical(record 去掉 digest))。
重放 = 从空状态逐步 apply，任何一步的 state_digest 与记录不符即判 invalid。
"""
from __future__ import annotations

import json
from typing import Any

from core import json_doc
from core.cognition_workspace import discourse as dc

SCHEMA = "nf-cog-records/1"
GUIDE = "修复指引："


def _record_digest(record: dict[str, Any]) -> str:
    return dc.digest_of({k: v for k, v in record.items() if k != "digest"})


def append(records: dict[str, Any], state: dict[str, Any], move_id: str,
           delta: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """执行一步：写记录 + 返回新状态（原子性：状态不合法就不写记录）。"""
    new_state = dc.append_move(state, move_id, delta)
    seq = len(new_state["moves"])
    record = {"seq": seq, "move": move_id, "delta": delta,
              "state_digest": new_state["digest"],
              "prev": records["records"][-1]["digest"] if records["records"] else ""}
    record["digest"] = _record_digest(record)
    new_records = json_doc.loads(json.dumps(records))
    new_records["records"].append(record)
    new_records["head"] = record["digest"]
    return new_records, new_state


def new_records(state: dict[str, Any]) -> dict[str, Any]:
    return {"schema": SCHEMA, "session_id": state["session_id"],
            "problem": state["problem"]["statement"],
            "steps_max": state["budget"]["steps_max"],
            "records": [], "head": ""}


def replay(records: Any, steps_max: int | None = None) -> dict[str, Any]:
    """从记录重放到最终状态 → {ok, state, issues}。"""
    res: dict[str, Any] = {"ok": False, "state": None, "issues": []}
    if not isinstance(records, dict) or str(records.get("schema") or "") != SCHEMA:
        res["issues"].append("记录 schema 不匹配（" + GUIDE + "需要 " + SCHEMA + "）")
        return res
    items = records.get("records")
    if not isinstance(items, list):
        res["issues"].append("records 必须是数组（" + GUIDE + "用 records.new_records 生成）")
        return res
    state = dc.new(str(records.get("problem") or ""),
                   session_id=records.get("session_id") or "",
                   steps_max=int(steps_max or records.get("steps_max") or 24))
    prev = ""
    for item in items:
        if not isinstance(item, dict):
            res["issues"].append("记录项不是对象（" + GUIDE + "重建记录）")
            return res
        if int(item.get("seq") or 0) != len(state["moves"]) + 1:
            res["issues"].append("记录序号不连续（" + GUIDE + "第 "
                                 + str(item.get("seq")) + " 条）")
            return res
        if str(item.get("prev") or "") != prev:
            res["issues"].append("记录链断在第 " + str(item.get("seq"))
                                 + " 条（" + GUIDE + "prev 必须等于上一条 digest）")
            return res
        if str(item.get("digest") or "") != _record_digest(item):
            res["issues"].append("记录 digest 不符（" + GUIDE + "记录被改过）")
            return res
        try:
            state = dc.append_move(state, str(item["move"]), dict(item["delta"]))
        except (KeyError, TypeError, ValueError) as exc:
            res["issues"].append("第 " + str(item.get("seq")) + " 条无法重放："
                                 + str(exc))
            return res
        if state["digest"] != str(item.get("state_digest") or ""):
            res["issues"].append("第 " + str(item.get("seq"))
                                 + " 条重放后状态 digest 不符（" + GUIDE + "状态被改过）")
            return res
        prev = str(item["digest"])
    if str(records.get("head") or "") != prev:
        res["issues"].append("head 与最后一条记录不符（" + GUIDE + "记录尾部被截断？）")
        return res
    res.update({"ok": True, "state": state})
    return res


def diff(a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
    """两次会话的记录差异（只列事实差异，不判优劣）。"""
    moves_a = [(r["move"], r["delta"].get("kind")) for r in a.get("records") or []]
    moves_b = [(r["move"], r["delta"].get("kind")) for r in b.get("records") or []]
    return {"schema": "nf-cog-diff/1",
            "a": {"session_id": a.get("session_id"), "moves": moves_a},
            "b": {"session_id": b.get("session_id"), "moves": moves_b},
            "only_in_a": [m for m in moves_a if m not in moves_b],
            "only_in_b": [m for m in moves_b if m not in moves_a],
            "same_sequence": moves_a == moves_b}
