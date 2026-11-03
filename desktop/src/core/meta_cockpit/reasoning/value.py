"""步级过程判定（step_verify）：可插拔、只读、幂等、无标量评分。

公开契约是 ``nf-step-verdict/1``（与架构文档 §6.1 对齐）：:

    {
      "schema": "nf-step-verdict/1",
      "turn": int, "step": int, "cluster": [atom_id, ...],
      "checks": [{"id": str, "ok": true|false|"unknown", "witness": sha256}],
      "mandatory": [check_id, ...],
      "verdict": "pass" | "fail" | "unknown",
      "gains": {"unmet": int, "coherence": int, "facet": int, "new_keys": int},
      "violations": [check_id, ...],
      "advisory": [{"source": str, "role": "external-advisory", "digest": sha256}],
      "no_score": true,
      "digest": sha256
    }

约定：

1. **没有 value / score / weights / components**：判定只有 pass/fail/unknown
   与整数 gains；外部证据只以 digest 出现，永不升级为本地事实。
2. **幂等**：同输入（含 turn/step）两次调用返回体逐字节一致；缓存只内部生效，
   不把 ``cache.hit`` 写进返回值。
3. 输入非法时 fail-closed：返回 verdict=fail 且 violations 含 ``invalid-state``，
   不抛异常、不回显状态内容。
"""

from __future__ import annotations

import copy
import hashlib
import json
from collections import OrderedDict
from typing import Callable

from . import bridge as nf

SCHEMA = "nf-step-verdict/1"
ROLE_EXTERNAL = "external-advisory"
CACHE_LIMIT = 512
MAX_ATOMS = nf.MAX_ATOMS

#: 必须为 true 才允许 verdict=pass 的检查项。
MANDATORY_CHECKS = (
    "state_valid",
    "unmet_not_regressed",
    "coherence_not_regressed",
    "facet_not_regressed",
)


def _canonical(value) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str
    ).encode("utf-8")


def _digest(value) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _witness(*, before: dict, after: dict, check_id: str, observed) -> str:
    return _digest(
        {
            "before": nf.state_digest(before),
            "after": nf.state_digest(after),
            "check": check_id,
            "observed": observed,
        }
    )


def _validate_state(state, label: str) -> None:
    if not isinstance(state, dict):
        raise ValueError(f"{label} state must be an object")
    if not isinstance(state.get("artifact"), dict):
        raise ValueError(f"{label} state must contain artifact object")
    nf.state_digest(state)


def _cluster_cost(cluster) -> int:
    contracts = nf.live_selector.CONTRACTS
    total = 0
    for atom_id in cluster:
        if atom_id not in contracts:
            raise ValueError("step references unknown atom")
        total += int(contracts[atom_id]["cost"])
    return total


def _counts(state: dict) -> dict:
    return {
        "unmet": len(nf.unmet(state)),
        "coherence": len(nf.coherence_issues(state)),
        "gaps": len(nf.completion_gaps(state)),
        "keys": len(nf.available_keys(state)),
    }


def _check(check_id: str, ok, *, before, after, observed) -> dict:
    return {
        "id": check_id,
        "ok": ok,
        "witness": _witness(before=before, after=after, check_id=check_id, observed=observed),
    }


def deterministic_checks(before: dict, after: dict, cluster=()) -> dict:
    """确定性检查器：只产出 checks(ok) + 整数 gains，没有标量分数。"""

    cluster = list(cluster)
    if len(cluster) > MAX_ATOMS or len(set(cluster)) != len(cluster):
        raise ValueError("cluster must contain at most 3 unique atoms")
    _validate_state(before, "before")
    _validate_state(after, "after")
    cost = _cluster_cost(cluster)

    b = _counts(before)
    a = _counts(after)
    # completion_gaps = unmet + facet gaps + coherence issues（仓内定义）
    b_facet = max(0, b["gaps"] - b["unmet"] - b["coherence"])
    a_facet = max(0, a["gaps"] - a["unmet"] - a["coherence"])
    gains = {
        "unmet": b["unmet"] - a["unmet"],
        "coherence": b["coherence"] - a["coherence"],
        "facet": b_facet - a_facet,
        "new_keys": a["keys"] - b["keys"],
    }
    progress = gains["unmet"] + gains["coherence"] + gains["facet"] + gains["new_keys"]

    checks = [
        _check("state_valid", True, before=before, after=after, observed=cost),
        _check(
            "unmet_not_regressed",
            gains["unmet"] >= 0,
            before=before,
            after=after,
            observed=gains["unmet"],
        ),
        _check(
            "coherence_not_regressed",
            gains["coherence"] >= 0,
            before=before,
            after=after,
            observed=gains["coherence"],
        ),
        _check(
            "facet_not_regressed",
            gains["facet"] >= 0,
            before=before,
            after=after,
            observed=gains["facet"],
        ),
        _check(
            "progress_observed",
            True if progress > 0 else "unknown",
            before=before,
            after=after,
            observed=progress,
        ),
    ]
    by_id = {item["id"]: item for item in checks}
    violations = [
        check_id for check_id in MANDATORY_CHECKS if by_id[check_id]["ok"] is not True
    ]
    if violations:
        verdict = "fail"
    elif any(by_id[check_id]["ok"] == "unknown" for check_id in MANDATORY_CHECKS):
        verdict = "unknown"
    else:
        verdict = "pass"
    payload = {
        "schema": SCHEMA,
        "cluster": cluster,
        "checks": checks,
        "mandatory": list(MANDATORY_CHECKS),
        "verdict": verdict,
        "gains": gains,
        "violations": violations,
        "no_score": True,
    }
    payload["digest"] = _digest(payload)
    return payload


class ResultCache:
    """digest → verdict 的 LRU 缓存；命中与否不进入返回值（只内部统计）。"""

    def __init__(self, limit: int = CACHE_LIMIT) -> None:
        if not isinstance(limit, int) or isinstance(limit, bool) or limit < 1:
            raise ValueError("cache limit must be a positive integer")
        self.limit = limit
        self._store: OrderedDict[str, dict] = OrderedDict()
        self._stats = {"hits": 0, "misses": 0, "evictions": 0, "size": 0}

    def get(self, key: str) -> dict | None:
        if key in self._store:
            self._stats["hits"] += 1
            self._store.move_to_end(key)
            return copy.deepcopy(self._store[key])
        self._stats["misses"] += 1
        return None

    def put(self, key: str, value: dict) -> None:
        self._store[key] = copy.deepcopy(value)
        self._store.move_to_end(key)
        if len(self._store) > self.limit:
            self._store.popitem(last=False)
            self._stats["evictions"] += 1
        self._stats["size"] = len(self._store)

    def stats(self) -> dict:
        return dict(self._stats)

    def clear(self) -> None:
        self._store.clear()
        self._stats = {"hits": 0, "misses": 0, "evictions": 0, "size": 0}


def _serializable(value) -> bool:
    """严格 JSON 可序列化（不把对象/NaN 悄悄转成字符串/NaN）。"""

    try:
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    except (TypeError, ValueError):
        return False
    return True


class StepVerifier:
    """step_verify 门面：确定性 checks + 只读外部 advisory(digest) + 内部缓存。"""

    def __init__(
        self,
        *,
        cache: ResultCache | None = None,
        external_providers: dict[str, Callable] | None = None,
    ) -> None:
        self.cache = cache if cache is not None else ResultCache()
        self._externals: dict[str, Callable] = {}
        for name, provider in (external_providers or {}).items():
            self.register_external(name, provider)

    @property
    def external_names(self) -> tuple[str, ...]:
        return tuple(sorted(self._externals))

    def register_external(self, name: str, provider: Callable) -> None:
        if not isinstance(name, str) or not name.strip():
            raise ValueError("external provider name must be a non-empty string")
        if not callable(provider):
            raise ValueError("external provider must be callable")
        if name in self._externals:
            raise ValueError("external provider already registered")
        self._externals[name] = provider

    def _cache_key(
        self, before: dict, after: dict, cluster: list[str], turn: int, step: int
    ) -> str:
        return _digest(
            {
                "schema": SCHEMA,
                "before": nf.state_digest(before),
                "after": nf.state_digest(after),
                "cluster": list(cluster),
                "turn": turn,
                "step": step,
                "providers": self.external_names,
            }
        )

    def _advisory(
        self, name: str, provider: Callable, before, after, cluster, context
    ) -> dict | None:
        before_copy = copy.deepcopy(before)
        after_copy = copy.deepcopy(after)
        context_copy = copy.deepcopy(context)
        try:
            raw = provider(before_copy, after_copy, tuple(cluster), context_copy)
        except Exception:  # noqa: BLE001 - 外部 provider 永不导致崩溃
            return None
        if not isinstance(raw, dict) or not _serializable(raw):
            return None
        mutated = (
            nf.state_digest(before_copy) != nf.state_digest(before)
            or nf.state_digest(after_copy) != nf.state_digest(after)
        )
        if mutated:
            return None
        # 只保留 digest+角色：外部证据永不携带可被误读为本地值的字段。
        return {
            "source": name,
            "role": ROLE_EXTERNAL,
            "digest": _digest({"provider": name, "output": raw}),
        }

    def _invalid_verdict(self, before, after, cluster, turn, step, reason) -> dict:
        checks = [
            {
                "id": "state_valid",
                "ok": False,
                "witness": _digest(
                    {"cluster": list(cluster), "turn": turn, "step": step, "reason": reason}
                ),
            }
        ]
        payload = {
            "schema": SCHEMA,
            "turn": int(turn),
            "step": int(step),
            "cluster": list(cluster),
            "checks": checks,
            "mandatory": list(MANDATORY_CHECKS),
            "verdict": "fail",
            "gains": {"unmet": 0, "coherence": 0, "facet": 0, "new_keys": 0},
            "violations": ["invalid-state"],
            "advisory": [],
            "no_score": True,
        }
        payload["digest"] = _digest(payload)
        return payload

    def step_verify(
        self,
        before: dict,
        after: dict,
        cluster=(),
        context: dict | None = None,
        *,
        turn: int | None = None,
        step: int | None = None,
    ) -> dict:
        """返回 ``nf-step-verdict/1``；幂等：缓存命中不改变返回体。"""

        cluster = list(cluster)
        if turn is None:
            if isinstance(after, dict) and isinstance(before, dict):
                turn = int(after.get("turn", before.get("turn", 0)))
            else:
                turn = 0
        if step is None:
            step = 0
        if not isinstance(turn, int) or isinstance(turn, bool) or turn < 0:
            return self._invalid_verdict(before, after, cluster, 0, step, "invalid-turn")
        if not isinstance(step, int) or isinstance(step, bool) or step < 0:
            return self._invalid_verdict(before, after, cluster, turn, 0, "invalid-step")
        key = None
        try:
            key = self._cache_key(before, after, cluster, turn, step)
        except Exception:  # noqa: BLE001 - 非法状态不缓存
            pass
        if key is not None:
            cached = self.cache.get(key)
            if cached is not None:
                return cached
        try:
            base = deterministic_checks(before, after, cluster)
        except Exception:  # noqa: BLE001 - fail-closed，不扩散异常/不回显内容
            result = self._invalid_verdict(before, after, cluster, turn, step, "invalid-state")
        else:
            advisories = [
                item
                for item in (
                    self._advisory(
                        name, self._externals[name], before, after, cluster, context
                    )
                    for name in self.external_names
                )
                if item is not None
            ]
            payload = {
                "schema": SCHEMA,
                "turn": int(turn),
                "step": int(step),
                "cluster": cluster,
                "checks": base["checks"],
                "mandatory": base["mandatory"],
                "verdict": base["verdict"],
                "gains": base["gains"],
                "violations": base["violations"],
                "advisory": advisories,
                "no_score": True,
            }
            payload["digest"] = _digest(payload)
            result = payload
        if key is not None:
            self.cache.put(key, result)
        return result


def step_verify(
    before: dict,
    after: dict,
    cluster=(),
    *,
    verifier: StepVerifier | None = None,
    turn: int | None = None,
    step: int | None = None,
) -> dict:
    """模块级便捷入口（默认无外部 provider、无共享缓存）。"""

    return (verifier or StepVerifier()).step_verify(
        before, after, cluster, turn=turn, step=step
    )
