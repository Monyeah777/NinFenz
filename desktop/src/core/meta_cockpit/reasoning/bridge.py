"""只读桥接层：把 NinFenz 驾驶舱 API 暴露给 reasoning 包。

本包**不修改**仓内其他模块，也不写任何 State/session 文件；只以相对导入读取：

- ``cognitive_cockpit.initial_state/execute_cluster``
- ``live_selector.unmet/candidate_families/available_keys/NEEDS``
- ``coherence.evaluate/new_issue_ids``
- ``constrained_loop.completion_gaps/complete``
- ``task_profile.build/repair_keys``
- ``method_memory.core_signature/normalize_history``
- ``calibration_ledger.initial_ledger``
- ``secret_guard.find``

``shadow_execute`` 永远是 deepcopy 影子执行：搜索/证书/归因阶段绝不触碰调用方
状态。全部输出只含 digest、键名与整数计数，不含 goal/artifact 原文。
"""

from __future__ import annotations

import copy
import hashlib
import json

from .. import (
    calibration_ledger,
    cognitive_cockpit as cockpit,
    coherence,
    constrained_loop,
    live_selector,
    method_memory,
    secret_guard,
    task_profile,
)

STATE_KEYS = (
    "goal",
    "artifact",
    "open_questions",
    "reference",
    "budget",
    "budget_state",
    "fallback",
    "task_type",
    "frame",
    "library",
)


NEEDS = tuple(live_selector.NEEDS)
MAX_ATOMS = 3
MAX_COST = 3


def canonical(value) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str
    ).encode("utf-8")


def digest(value) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def state_digest(state: dict) -> str:
    """状态指纹：关键语义字段排序 JSON 取 sha256；同 digest 即 transposition。

    刻意与 ``method_memory.core_signature`` 使用同一字段集，保证原型里的
    "状态合并" 与仓内 "循环检测" 对同一状态给出同一个指纹。
    """

    return digest({key: state.get(key) for key in STATE_KEYS})


def initial_state(prompt: str) -> dict:
    return cockpit.initial_state(prompt)


def execute_cluster(state: dict, cluster: list[str]) -> dict:
    return cockpit.execute_cluster(state, list(cluster))


def shadow_execute(state: dict, cluster: list[str]) -> dict:
    """deepcopy 影子执行：搜索阶段绝不触碰调用方状态。

    即使仓内 ``execute_cluster`` 内部已经是事务式副本，这里仍显式复制并
    校验输入状态指纹未变，避免未来实现变化把搜索污染成写操作。
    """

    shadow = copy.deepcopy(state)
    baseline = state_digest(shadow)
    result = cockpit.execute_cluster(shadow, list(cluster))
    if state_digest(shadow) != baseline:
        raise RuntimeError("executor mutated input state")
    return result


def coherence_new_issue_ids(before: dict, after: dict) -> list[str]:
    return list(coherence.new_issue_ids(before, after))


def complete(state: dict) -> bool:
    return constrained_loop.complete(state)


def completion_gaps(state: dict) -> list[str]:
    return constrained_loop.completion_gaps(state)


def unmet(state: dict) -> list[str]:
    return list(live_selector.unmet(state))


def available_keys(state: dict) -> set[str]:
    return set(live_selector.available_keys(state))


def coherence_issues(state: dict) -> list[dict]:
    return list(coherence.evaluate(state)["issues"])


def step_deficits(state: dict) -> dict:
    """确定性验证信号的原料：三组缺口计数。"""

    return {
        "unmet": unmet(state),
        "coherence": coherence_issues(state),
        "gaps": completion_gaps(state),
    }


def secret_find(value) -> list[dict]:
    return secret_guard.find(value)


def repair_keys(state: dict) -> list[str]:
    profile = task_profile.build(state.get("goal", ""))
    keys = set(task_profile.repair_keys(state, profile))
    keys |= set(coherence.repair_keys(state))
    return sorted(keys)


def preferred_atoms(state: dict) -> list[str]:
    return list(task_profile.build(state.get("goal", ""))["preferred_atoms"])


def profile(state: dict) -> dict:
    return task_profile.build(state.get("goal", ""))


def initial_ledger() -> dict:
    return calibration_ledger.initial_ledger()


def history_clusters(state: dict) -> list[list[str]]:
    """方法记忆命中信号：当前状态里已记录的历史方法簇。"""

    return [
        list(item.get("cluster", []))
        for item in method_memory.normalize_history(state)
        if isinstance(item, dict)
    ]


def candidate_actions(
    state: dict,
    *,
    max_len: int = MAX_ATOMS,
    direct_limit: int = 5,
    progress_limit: int = 12,
    max_cost: int = MAX_COST,
) -> list[dict]:
    """真实候选来源：``live_selector.candidate_families`` 的原子簇集合。

    只做纯结构投影（不调用模型），按 cluster 元组去重并排序，保证
    digest / 迭代顺序可复算。执行合法性由真正执行 ``execute_cluster`` 时
    fail-closed 判定，而不是在这里用模型打分筛选。
    """

    families = live_selector.candidate_families(
        state,
        max_len=max_len,
        direct_limit=direct_limit,
        progress_limit=progress_limit,
        max_cost=max_cost,
    )
    seen: set[tuple[str, ...]] = set()
    actions: list[dict] = []
    for family, kind in ((families["direct"], "direct"), (families["progress"], "progress")):
        for item in family:
            cluster = tuple(item["cluster"])
            if not cluster or len(cluster) > MAX_ATOMS or len(set(cluster)) != len(cluster):
                continue
            if cluster in seen:
                continue
            seen.add(cluster)
            actions.append(
                {
                    "cluster": list(cluster),
                    "cost": int(item["cost"]),
                    "resolves": list(item.get("resolves", [])),
                    "kind": kind,
                }
            )
    actions.sort(key=lambda item: item["cluster"])
    return actions


def state_head(state: dict) -> dict:
    """可安全写进 trace 的状态摘要：只有计数/键名/digest，绝不含目标原文。"""

    deficits = step_deficits(state)
    artifact = state.get("artifact", {})
    return {
        "state_digest": state_digest(state),
        "goal_digest": digest(state.get("goal", "")),
        "turn": int(state.get("turn", 0)),
        "unmet": list(deficits["unmet"]),
        "coherence_issues": sorted({item["id"] for item in deficits["coherence"]}),
        "completion_gaps": list(deficits["gaps"]),
        "artifact_keys": sorted(
            key for key, value in artifact.items() if value not in ("", [], {}, None, False)
        ),
    }
