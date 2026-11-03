"""M9 可独立复核的搜索证书：把"这条计划确实能走通"固化成可重算的 digest 链。

公开契约 ``nf-cognition-certificate/1``::

    build(state0, plan, budget) -> certificate
    verify(cert) / verify(cert, state0=..., budget=...) ->
        {"status": "pass|fail|indeterminate", "ok": bool, "issues": [...]}

证书字段（**不含 goal/artifact/prompt 内容文本**；只有 digest、整数预算与原子 id）::

    {"schema": "nf-cognition-certificate/1",
     "contracts_digest": sha256,     # 原子契约表版本
     "policy_digest": sha256,        # 判定策略版本（mandatory checks / max_atoms / ...）
     "initial_digest": sha256,       # 初始状态指纹
     "actions": [[atom_id, ...], ...],
     "step_verdict_digests": [sha256, ...],   # 每步 nf-step-verdict/1 的 digest
     "final_digest": sha256,
     "checks": {"contract": bool, "coherence": bool, "complete": bool, "budget": bool},
     "budget": {"max_nodes": int, "max_depth": int, "unit_budget": int|null},
     "budget_digest": sha256,        # 由上面 budget 块重算（L1 即校验）
     "no_scoring": true,
     "digest": sha256}               # 以上全部内容的摘要

``verify`` 分两层（三值返回）：

**L1（不需要 state0，纯结构与摘要自洽）**
1. schema 精确匹配、唯一键白名单（未知字段即 fail）；
2. 所有 digest 字段是 64 位 hex，``digest`` 能由证书内容重算；
3. ``actions`` 与 ``step_verdict_digests`` 数量一致、原子 id 合法；
4. ``initial_digest`` 合法；
5. ``no_scoring`` 缺失或为 true（false 一律 fail）；
6. ``budget`` 整数合法，且 ``budget_digest`` 能**由证书里的 budget 块重算**。
   L1 通过但没给 state0 → ``indeterminate``（只能证明证书自身没被乱改）。

**L2（给 state0 时重新影子执行）**
- 重放 ``actions``：重算每步 verdict digest、终态 digest；
- **重算四类 checks** 并与证书里存的值逐项比较：
  ``contract``（每步可执行且 verdict=pass）、``coherence``（无新 issue）、
  ``complete``（终态 ``complete()``）、``budget``（actions 数/深度/原子数 ≤
  证书 budget 上限）；
- 重算与证书不一致 → ``fail``（``check-mismatch:*``）；任一项为 false →
  ``fail``（``check-false:*``，证书不能证明"走通"）；
- 给了调用方 budget 时再核对 ``budget_digest``；
- 全部一致 → ``pass``。

因此**证书里的 ``checks`` 从不被信任**：没有 state0 时最多只能到 indeterminate；
给了 state0 也一律重算。``ok`` 仅在 ``status="pass"`` 时为 true。
"""

from __future__ import annotations

import copy
import hashlib
import json

from . import budget as budget_mod
from . import bridge as nf
from . import value as prm

SCHEMA = "nf-cognition-certificate/1"
POLICY_SCHEMA = "nf-cert-policy/1"
BUDGET_SCHEMA = "nf-cert-budget/1"
MAX_ACTIONS = 12
MAX_BUDGET_NODES = 4096
REQUIRED_FIELDS = (
    "schema",
    "contracts_digest",
    "policy_digest",
    "initial_digest",
    "actions",
    "step_verdict_digests",
    "final_digest",
    "checks",
    "budget",
    "budget_digest",
    "digest",
)
#: 可选字段：``no_scoring`` 允许缺失（兼容旧证书），存在时必须是 true。
OPTIONAL_FIELDS = ("no_scoring",)
FIELDS = REQUIRED_FIELDS + OPTIONAL_FIELDS
CHECK_FIELDS = ("contract", "coherence", "complete", "budget")
BUDGET_FIELDS = ("max_nodes", "max_depth", "unit_budget")
FORBIDDEN_KEYS = frozenset({"reward", "q", "value", "score", "weights"})


def _is_int(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _canonical(value) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str
    ).encode("utf-8")


def _digest(value) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _is_hex_digest(value) -> bool:
    if not isinstance(value, str) or len(value) != 64:
        return False
    try:
        int(value, 16)
    except ValueError:
        return False
    return True


def _validate_state(state, label: str = "state0") -> None:
    if not isinstance(state, dict):
        raise ValueError("{} must be an object".format(label))
    if not isinstance(state.get("artifact"), dict):
        raise ValueError("{} must contain artifact object".format(label))
    if not isinstance(state.get("goal"), str):
        raise ValueError("{} must contain goal string".format(label))


def _validate_plan(plan) -> list[list[str]]:
    if not isinstance(plan, (list, tuple)) or not plan:
        raise ValueError("plan must be a non-empty sequence of clusters")
    if len(plan) > MAX_ACTIONS:
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


def contracts_digest() -> str:
    return str(nf.live_selector.CONTRACTS_DIGEST)


def policy_digest() -> str:
    """判定策略版本：mandatory checks / max_atoms / 契约版本，全部是结构常量。"""

    return _digest(
        {
            "schema": POLICY_SCHEMA,
            "max_atoms": int(nf.MAX_ATOMS),
            "mandatory": list(prm.MANDATORY_CHECKS),
            "contracts_digest": contracts_digest(),
            "verdict_schema": prm.SCHEMA,
        }
    )


# ---------------------------------------------------------------------- 预算
def budget_summary(budget) -> dict:
    if not isinstance(budget, budget_mod.Budget):
        raise ValueError("budget must be a Budget")
    return {
        "max_nodes": int(budget.max_nodes),
        "max_depth": int(budget.max_depth),
        "unit_budget": None if budget.unit_budget is None else int(budget.unit_budget),
    }


def _budget_digest_from_summary(summary: dict) -> str:
    return _digest({"schema": BUDGET_SCHEMA, **summary})


def budget_digest(budget) -> str:
    return _budget_digest_from_summary(budget_summary(budget))


def _validate_budget_summary(summary) -> list[str]:
    issues: list[str] = []
    if not isinstance(summary, dict) or set(summary) != set(BUDGET_FIELDS):
        return ["invalid-budget"]
    for field in ("max_nodes", "max_depth"):
        value = summary.get(field)
        if not _is_int(value) or not 1 <= value <= MAX_BUDGET_NODES:
            issues.append("invalid-budget:{}".format(field))
    unit = summary.get("unit_budget")
    if unit is not None and (not _is_int(unit) or unit < 1):
        issues.append("invalid-budget:unit_budget")
    return issues


def _budget_conserved(action_count: int, atom_count: int, summary: dict) -> bool:
    """预算守恒：实际 action 数（= 执行节点数/深度）与原子数 ≤ 证书 budget 上限。"""

    if action_count > summary["max_nodes"]:
        return False
    if action_count > summary["max_depth"]:
        return False
    unit = summary.get("unit_budget")
    if unit is not None and atom_count > unit:
        return False
    return True


def _resolve_budget(budget, state: dict | None = None):
    if budget is None:
        if state is None:
            return None
        return budget_mod.allocate_for(len(nf.completion_gaps(state)))
    if isinstance(budget, dict):
        return budget_mod.Budget(**budget)
    if not isinstance(budget, budget_mod.Budget):
        raise ValueError("budget must be a Budget or object")
    return budget


def _cert_digest(payload: dict) -> str:
    return _digest({key: payload[key] for key in FIELDS if key != "digest" and key in payload})


def _verdict(issues: list[str], replayed: bool) -> dict:
    """三值结果：有问题 → fail；完整重放通过 → pass；只做结构检查 → indeterminate。"""

    if issues:
        status = "fail"
    elif replayed:
        status = "pass"
    else:
        status = "indeterminate"
    return {"status": status, "ok": status == "pass", "issues": list(issues)}


# ---------------------------------------------------------------------- build
def build(state0: dict, plan, budget=None) -> dict:
    """影子执行计划并生成证书。

    执行失败（某步不可执行 / coherence 被剪枝 / verdict 非 pass）时 **fail-closed
    抛 ``ValueError``**：证书只描述"可执行且被判定通过"的计划，否则 checks 里必然
    有 false、无法作为完成证明。预算不足只让 ``checks.budget`` 为 false（证书仍可
    生成，verify 会拒）。
    """

    _validate_state(state0)
    clusters = _validate_plan(plan)
    resolved = _resolve_budget(budget, state0)
    summary = budget_summary(resolved)
    if summary["max_nodes"] > MAX_BUDGET_NODES:
        raise ValueError("budget max_nodes is too large")

    current = copy.deepcopy(state0)
    initial_digest = nf.state_digest(current)
    executed: list[list[str]] = []
    verdict_digests: list[str] = []
    for turn, cluster in enumerate(clusters, start=1):
        try:
            result = nf.shadow_execute(current, cluster)
        except Exception as exc:  # noqa: BLE001 - 执行异常 = 契约不成立
            raise ValueError("plan cannot be executed at step {}".format(turn)) from exc
        if (
            not isinstance(result, dict)
            or result.get("status") != "pass"
            or not isinstance(result.get("state"), dict)
        ):
            raise ValueError("plan cannot be executed at step {}".format(turn))
        new_state = result["state"]
        if nf.coherence_new_issue_ids(current, new_state):
            raise ValueError("plan introduces a coherence issue at step {}".format(turn))
        verdict = prm.StepVerifier().step_verify(
            current,
            new_state,
            cluster,
            turn=int(new_state.get("turn", current.get("turn", 0))),
            step=turn,
        )
        if not isinstance(verdict, dict) or verdict.get("verdict") != "pass":
            raise ValueError("plan fails step verdict at step {}".format(turn))
        executed.append(list(cluster))
        verdict_digests.append(str(verdict["digest"]))
        current = new_state

    final_digest = nf.state_digest(current)
    nodes_used = len(executed)
    atoms_used = sum(len(cluster) for cluster in executed)
    payload = {
        "schema": SCHEMA,
        "contracts_digest": contracts_digest(),
        "policy_digest": policy_digest(),
        "initial_digest": initial_digest,
        "actions": [list(cluster) for cluster in executed],
        "step_verdict_digests": verdict_digests,
        "final_digest": final_digest,
        "checks": {
            "contract": True,
            "coherence": True,
            "complete": bool(nf.complete(current)),
            "budget": bool(_budget_conserved(nodes_used, atoms_used, summary)),
        },
        "budget": summary,
        "budget_digest": _budget_digest_from_summary(summary),
        "no_scoring": True,
    }
    payload["digest"] = _cert_digest(payload)
    return payload


# ---------------------------------------------------------------------- verify L1
def _verify_structure(cert: dict) -> tuple[list[str], list[list[str]], list[str]]:
    """L1：纯结构与摘要自洽；返回 (issues, actions, verdict_digests)。"""

    issues: list[str] = []
    extra = sorted(set(cert) - set(FIELDS))
    for key in extra:
        issues.append("unexpected-key:{}".format(key))
    missing = [field for field in REQUIRED_FIELDS if field not in cert]
    for field in missing:
        issues.append("missing-key:{}".format(field))
    if missing:
        return issues, [], []
    if cert.get("schema") != SCHEMA:
        issues.append("schema-mismatch")
    if "no_scoring" in cert and cert.get("no_scoring") is not True:
        issues.append("no_scoring-not-true")
    for field in (
        "contracts_digest",
        "policy_digest",
        "initial_digest",
        "final_digest",
        "budget_digest",
        "digest",
    ):
        if not _is_hex_digest(cert.get(field)):
            issues.append("invalid-digest:{}".format(field))
    if cert.get("contracts_digest") != contracts_digest():
        issues.append("contracts-drift")
    if cert.get("policy_digest") != policy_digest():
        issues.append("policy-mismatch")
    contracts = nf.live_selector.CONTRACTS
    actions = cert.get("actions")
    if not isinstance(actions, list) or not actions or len(actions) > MAX_ACTIONS:
        issues.append("invalid-actions")
        actions = []
    else:
        for index, cluster in enumerate(actions):
            if (
                not isinstance(cluster, list)
                or not cluster
                or len(cluster) > nf.MAX_ATOMS
                or len(set(cluster)) != len(cluster)
                or any(not isinstance(atom, str) or atom not in contracts for atom in cluster)
            ):
                issues.append("invalid-action:{}".format(index))
    verdict_digests = cert.get("step_verdict_digests")
    if not isinstance(verdict_digests, list):
        issues.append("invalid-verdict-digests")
        verdict_digests = []
    else:
        if len(verdict_digests) != len(actions):
            issues.append("verdict-count-mismatch")
        for index, value in enumerate(verdict_digests):
            if not _is_hex_digest(value):
                issues.append("invalid-verdict-digest:{}".format(index))
    checks = cert.get("checks")
    if not isinstance(checks, dict) or set(checks) != set(CHECK_FIELDS):
        issues.append("invalid-checks")
    else:
        for field in CHECK_FIELDS:
            if not isinstance(checks.get(field), bool):
                issues.append("invalid-check:{}".format(field))
    summary = cert.get("budget")
    budget_issues = _validate_budget_summary(summary)
    issues.extend(budget_issues)
    if not budget_issues and _is_hex_digest(cert.get("budget_digest")):
        try:
            if _budget_digest_from_summary(summary) != cert.get("budget_digest"):
                issues.append("budget-digest-mismatch")
        except Exception:  # noqa: BLE001
            issues.append("budget-digest-uncomputable")
    try:
        if _cert_digest(cert) != cert.get("digest"):
            issues.append("digest-mismatch")
    except Exception:  # noqa: BLE001
        issues.append("digest-uncomputable")
    return issues, actions, verdict_digests


# ---------------------------------------------------------------------- verify L2
def _verify_replay(
    cert: dict,
    state0: dict,
    actions: list[list[str]],
    verdict_digests: list[str],
    caller_budget,
) -> list[str]:
    """L2：重放 + 重算四类 checks 并与证书逐项比较。"""

    issues: list[str] = []
    if nf.state_digest(state0) != cert.get("initial_digest"):
        issues.append("initial-state-mismatch")
        return issues
    current = copy.deepcopy(state0)
    replayed: list[str] = []
    contract_ok = True
    coherence_ok = True
    for index, cluster in enumerate(actions):
        try:
            result = nf.shadow_execute(current, cluster)
        except Exception:  # noqa: BLE001
            issues.append("replay-execution-error:{}".format(index))
            contract_ok = False
            break
        if (
            not isinstance(result, dict)
            or result.get("status") != "pass"
            or not isinstance(result.get("state"), dict)
        ):
            issues.append("replay-execution-failed:{}".format(index))
            contract_ok = False
            break
        new_state = result["state"]
        if nf.coherence_new_issue_ids(current, new_state):
            coherence_ok = False
            issues.append("replay-coherence:{}".format(index))
            break
        verdict = prm.StepVerifier().step_verify(
            current,
            new_state,
            cluster,
            turn=int(new_state.get("turn", current.get("turn", 0))),
            step=index + 1,
        )
        if not isinstance(verdict, dict) or verdict.get("verdict") != "pass":
            contract_ok = False
            issues.append("replay-verdict-failed:{}".format(index))
            break
        replayed.append(str(verdict["digest"]))
        current = new_state

    if replayed != list(verdict_digests):
        issues.append("step-verdict-mismatch")
    if nf.state_digest(current) != cert.get("final_digest"):
        issues.append("final-digest-mismatch")
    if not contract_ok:
        complete_recomputed = False
    else:
        complete_recomputed = bool(
            coherence_ok and len(replayed) == len(actions) and nf.complete(current)
        )
    summary = cert.get("budget") if isinstance(cert.get("budget"), dict) else {}
    atoms_used = sum(len(cluster) for cluster in actions)
    try:
        budget_recomputed = _budget_conserved(len(actions), atoms_used, summary)
    except (KeyError, TypeError):
        budget_recomputed = False
    recomputed = {
        "contract": bool(contract_ok and len(replayed) == len(actions)),
        "coherence": bool(coherence_ok),
        "complete": complete_recomputed,
        "budget": bool(budget_recomputed),
    }
    stored = cert.get("checks", {})
    for field in CHECK_FIELDS:
        value = recomputed[field]
        if stored.get(field) is not value:
            issues.append("check-mismatch:{}".format(field))
        if not value:
            issues.append("check-false:{}".format(field))
    if caller_budget is not None:
        try:
            resolved = _resolve_budget(caller_budget)
            if budget_digest(resolved) != cert.get("budget_digest"):
                issues.append("budget-mismatch")
        except (TypeError, ValueError):
            issues.append("invalid-budget")
    return issues


def verify(cert, state0: dict | None = None, budget=None) -> dict:
    """L1 结构自洽 + （给 state0 时）L2 重放重算；见模块 docstring。"""

    if not isinstance(cert, dict):
        return _verdict(["not-an-object"], False)
    issues, actions, verdict_digests = _verify_structure(cert)
    if issues:
        return _verdict(issues, False)
    if state0 is None:
        return _verdict([], False)
    try:
        _validate_state(state0)
    except ValueError:
        return _verdict(["invalid-state0"], False)
    issues.extend(_verify_replay(cert, state0, actions, verdict_digests, budget))
    return _verdict(issues, True)
