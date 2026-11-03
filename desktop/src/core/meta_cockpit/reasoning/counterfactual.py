"""M8 步骤归因 + 最小充分计划：回答"这条计划里哪一步真的不能删"。

公开契约 ``nf-plan-attribution/1``::

    attribute(state, plan, budget=64) -> {
      "schema": "nf-plan-attribution/1",
      "plan": [...], "necessary": [...], "removed": [...],
      "minimal_plan": [...], "replay_digest": sha256}

- ``plan`` 是一串原子簇（``[[atom_id, ...], ...]``）；执行只走
  ``nf_bridge.shadow_execute``（deepcopy 影子执行），**不写调用方状态**。
- 对每一步做 leave-one-out：把该步从计划里删掉后重放剩余步骤，再用**有界
  greedy**（``budget`` 节点）尝试闭合缺口；能在预算内 complete → 该步不是必需。
- ``necessary`` / ``removed`` 是步骤下标（按原计划顺序）。``minimal_plan`` 是在
  ``removed`` 上再做一次贪心删除得到的子序列（保持原顺序），长度 ≤ 原计划。
  "充分"的判据与 leave-one-out 相同：重放 ``minimal_plan`` 后再用有界 greedy
  能在预算内 complete（结果里的 ``sufficiency`` 由调用方复算，见 bench2）。
- 无标量评分、无墙钟、无 RNG；``replay_digest`` 同输入两次一致。
"""

from __future__ import annotations

import copy
import hashlib
import json

from . import budget as budget_mod
from . import bridge as nf
from . import value as prm
from . import search

SCHEMA = "nf-plan-attribution/1"
MAX_PLAN_STEPS = 12
MAX_BUDGET = 256
MAX_DEPTH = 12
#: greedy 在预算边界停止的 termination：此时"没完成"≠"不可能完成"。
BUDGET_TERMINATIONS = frozenset({"max-nodes", "max-depth"})


def _is_int(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _canonical(value) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str
    ).encode("utf-8")


def _digest(value) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _validate_state(state) -> None:
    if not isinstance(state, dict):
        raise ValueError("state must be an object")
    if not isinstance(state.get("artifact"), dict):
        raise ValueError("state must contain artifact object")
    if not isinstance(state.get("goal"), str):
        raise ValueError("state must contain goal string")


def _validate_plan(plan) -> list[list[str]]:
    if not isinstance(plan, (list, tuple)) or not plan:
        raise ValueError("plan must be a non-empty sequence of clusters")
    if len(plan) > MAX_PLAN_STEPS:
        raise ValueError("plan has too many steps")
    contracts = nf.live_selector.CONTRACTS
    normalized: list[list[str]] = []
    for cluster in plan:
        if not isinstance(cluster, (list, tuple)) or not cluster:
            raise ValueError("each plan cluster must be a non-empty sequence")
        atoms = list(cluster)
        if len(atoms) > nf.MAX_ATOMS or len(set(atoms)) != len(atoms):
            raise ValueError("plan cluster must contain at most {} unique atoms".format(nf.MAX_ATOMS))
        for atom in atoms:
            if not isinstance(atom, str) or atom not in contracts:
                raise ValueError("plan references unknown atom")
        normalized.append(atoms)
    return normalized


def _validated_budget(budget) -> int:
    if not _is_int(budget) or not 1 <= budget <= MAX_BUDGET:
        raise ValueError("budget must be an integer in [1, {}]".format(MAX_BUDGET))
    return int(budget)


def replay(state: dict, plan: list[list[str]]) -> dict:
    """影子执行整条计划；返回 (ok, final_state, 每步 verdict/digest)。"""

    _validate_state(state)
    clusters = _validate_plan(plan)
    current = copy.deepcopy(state)
    verdicts: list[dict] = []
    for turn, cluster in enumerate(clusters, start=1):
        try:
            result = nf.shadow_execute(current, cluster)
        except Exception:  # noqa: BLE001 - 执行器异常 = 该步不可执行
            return {
                "ok": False,
                "reason": "execution-error",
                "turn": turn,
                "state": current,
                "verdicts": verdicts,
                "state_digest": nf.state_digest(current),
            }
        if (
            not isinstance(result, dict)
            or result.get("status") != "pass"
            or not isinstance(result.get("state"), dict)
        ):
            return {
                "ok": False,
                "reason": "execution-failed",
                "turn": turn,
                "state": current,
                "verdicts": verdicts,
                "state_digest": nf.state_digest(current),
            }
        new_state = result["state"]
        if nf.coherence_new_issue_ids(current, new_state):
            return {
                "ok": False,
                "reason": "coherence-pruned",
                "turn": turn,
                "state": current,
                "verdicts": verdicts,
                "state_digest": nf.state_digest(current),
            }
        verdict = prm.StepVerifier().step_verify(
            current,
            new_state,
            cluster,
            turn=int(new_state.get("turn", current.get("turn", 0))),
            step=turn,
        )
        if not isinstance(verdict, dict) or verdict.get("verdict") != "pass":
            return {
                "ok": False,
                "reason": "verdict-{}".format(verdict.get("verdict") if isinstance(verdict, dict) else "invalid"),
                "turn": turn,
                "state": current,
                "verdicts": verdicts,
                "state_digest": nf.state_digest(current),
            }
        verdicts.append(
            {
                "turn": turn,
                "cluster": list(cluster),
                "verdict": verdict["verdict"],
                "digest": verdict["digest"],
            }
        )
        current = new_state
    return {
        "ok": True,
        "reason": "replayed",
        "turn": len(clusters),
        "state": current,
        "verdicts": verdicts,
        "state_digest": nf.state_digest(current),
    }


def _greedy_complete(state: dict, budget: int) -> dict:
    """有界 greedy：在 ``budget`` 个节点内尝试闭合剩余缺口。"""

    if nf.complete(state):
        return {"complete": True, "source": "already-complete", "steps": 0, "digest": nf.state_digest(state)}
    node_budget = budget_mod.Budget(
        max_nodes=int(budget),
        max_depth=min(MAX_DEPTH, max(3, int(budget))),
    )
    plane = search.SearchPlane(mode="best_first")
    report = plane.greedy(state=copy.deepcopy(state), budget=node_budget)
    actions = [list(item["cluster"]) for item in report.get("path", [])]
    termination = report.get("termination")
    return {
        "complete": bool(report.get("complete")),
        "source": "greedy",
        "steps": int(report.get("depth", 0)),
        "termination": termination,
        "saturated": termination in BUDGET_TERMINATIONS,
        "actions": actions,
        "final_digest": nf.state_digest(report["final"]) if isinstance(report.get("final"), dict) else None,
    }


def _sufficient(state: dict, plan: list[list[str]], budget: int) -> dict:
    """重放计划 + 有界 greedy 补充：sufficient / insufficient / unknown。

    - ``insufficient``：重放失败（某步不可执行/verdict 非 pass/coherence 剪枝），
      或 greedy 在非预算边界终止（no-actions/dead-end/...）——确定"不能完成"。
    - ``unknown``：greedy 因预算耗尽（max-nodes/max-depth）停止——**不能**据此判
      "必要"，只能记 unknown（research E 的 bounded 语义）。
    - ``sufficient``：greedy 在预算内 complete。

    空计划合法：表示"不预置任何步骤，直接让有界 greedy 尝试"。
    """

    if plan:
        played = replay(state, plan)
    else:
        played = {
            "ok": True,
            "reason": "empty-plan",
            "state": copy.deepcopy(state),
            "state_digest": nf.state_digest(state),
        }
    if not played["ok"]:
        return {
            "state": "insufficient",
            "replay_ok": False,
            "replay_reason": played["reason"],
            "greedy": None,
            "final_digest": played["state_digest"],
        }
    greedy = _greedy_complete(played["state"], budget)
    if greedy["complete"]:
        status = "sufficient"
    elif greedy.get("saturated"):
        status = "unknown"
    else:
        status = "insufficient"
    return {
        "state": status,
        "replay_ok": True,
        "replay_reason": "replayed",
        "greedy": greedy,
        "final_digest": played["state_digest"],
    }


def attribute(state: dict, plan, budget: int = 64) -> dict:
    """leave-one-out 必要性 + 贪心最小化；返回 ``nf-plan-attribution/1``。"""

    _validate_state(state)
    clusters = _validate_plan(plan)
    budget = _validated_budget(budget)
    initial_digest = nf.state_digest(state)

    baseline = _sufficient(state, clusters, budget)
    necessary: list[int] = []
    removed: list[int] = []
    unknown: list[int] = []
    for index in range(len(clusters)):
        variant = clusters[:index] + clusters[index + 1:]
        status = _sufficient(state, variant, budget)["state"]
        if status == "sufficient":
            removed.append(index)
        elif status == "unknown":
            # 预算耗尽不能判"必要"；只记 unknown。
            unknown.append(index)
        else:
            necessary.append(index)

    # 集合级贪心最小化：反复从后往前尝试删除，直到不动点。
    # 只有 status=sufficient 才删；unknown/insufficient 一律保留（保守）。
    keep = list(range(len(clusters)))
    changed = True
    rounds = 0
    while changed and keep and rounds <= len(clusters):
        rounds += 1
        changed = False
        for index in sorted(keep, reverse=True):
            trial = [item for item in keep if item != index]
            if _sufficient(state, [clusters[item] for item in trial], budget)["state"] == "sufficient":
                keep = trial
                changed = True
    minimal_plan = [clusters[item] for item in keep]
    minimal_state = _sufficient(state, minimal_plan, budget)["state"]
    minimal_sufficient = minimal_state == "sufficient"

    replay_payload = {
        "schema": SCHEMA,
        "initial_digest": initial_digest,
        "plan": clusters,
        "plan_digests": [nf.digest({"cluster": cluster}) for cluster in clusters],
        "necessary": necessary,
        "removed": removed,
        "unknown": unknown,
        "minimal_plan": minimal_plan,
        "minimal_sufficient": bool(minimal_sufficient),
        "bounded": True,
        "baseline": {
            "state": baseline["state"],
            "replay_ok": baseline["replay_ok"],
            "replay_reason": baseline["replay_reason"],
            "final_digest": baseline["final_digest"],
            "greedy": baseline["greedy"],
        },
    }
    return {
        "schema": SCHEMA,
        "plan": clusters,
        "necessary": necessary,
        "removed": removed,
        "unknown": unknown,
        "minimal_plan": minimal_plan,
        "minimal_sufficient": bool(minimal_sufficient),
        "bounded": True,
        "replay_digest": _digest(replay_payload),
    }
