"""M7 计划案例库（digest-only）：跨会话复用"结构相同"任务的成功计划。

公开契约 ``nf-plan-memory/1``::

    {"schema": "nf-plan-memory/1",
     "contracts_digest": sha256,
     "records": {key: {"plan": [[atom_id, ...], ...], "trials": int,
                       "completions": int, "contra": int, "source_digest": sha256}}}

设计约束（与 Phase 1 "无标量评分"一致）：

1. **只存 digest 与原子 id**：``key`` 是结构签名的 sha256，``plan`` 只有
   ``atom_contracts`` 里的原子 id，``source_digest`` 是写入来源的状态/证书 fingerprint；
   不存 goal/artifact/prompt 内容文本，不存 ``value/score/weights`` 之类的标量。
2. ``key(state)`` 的结构签名 = ``available_keys + unmet + facet gaps``（排序后
   规范化取 sha256）。goal 原文只经由这些**结构投影**影响签名，不直接入库。
3. ``lookup`` 用 Beta 后验的 **10% 精确分位**（Lentz 连分式 + 二分 64 次；
   ``Beta(1+completions, 1+trials-completions)``）≥ 阈值才返回计划；证据不足一律
   miss。返回体**不含浮点下界**（只有 ``memory_hit/trials/completions/plan``），
   门限相关统计放在 ``stats()``，避免被调用方当排序分。
4. ``record`` **必须带 ``source_digest``**（调用方提供的状态/证书 digest，64 位 hex），
   无来源的写入一律拒绝；``contra`` 记录连续失败次数，``contra ≥ 2`` 置
   quarantine（``lookup`` 跳过，直到一次成功重置）。
5. ``contracts_digest`` 变化 → **先归档旧文件**（``<name>.drift-<epoch>.json`` 供审计）
   再全部失效（``stats().drift=True``）；文件损坏 → ``ValueError``（fail-closed）。
6. 复用只是 **steering 特征** ``memory_hit``（0/1），永远不替代验证：调用方拿到
   计划后仍要过 ``shadow_execute`` + ``nf-step-verdict/1``（见 counterfactual /
   certificate），写回最好只在 certificate.verify 通过后发生。
"""


from __future__ import annotations

import hashlib
import json
import math
import os
import tempfile
import time
from pathlib import Path

from . import bridge as nf

SCHEMA = "nf-plan-memory/1"
KEY_SCHEMA = "nf-plan-memory-key/1"
DEFAULT_THRESHOLD = 0.75
#: Beta 后验先验：Beta(1, 1)（a0 = b0 = 1）。
BETA_PRIOR = (1.0, 1.0)
#: 单侧下界分位：取 Beta 后验的 10% 分位（= 90% 单侧置信下界）。
LOWER_ALPHA = 0.1
#: 分位数值解（Lentz 连分式 + 二分）迭代次数；64 次足以到 1e-19。
QUANTILE_ITERATIONS = 64
#: 阈值比较的小数位：分位是数值解，取整到 1e-3 消除二分噪声（golden 值同口径）。
COMPARE_DECIMALS = 3
ROUND = 9
MAX_TRIALS = 1_000_000
#: 连续失败达到该次数即 quarantine（lookup 跳过）。
QUARANTINE_LIMIT = 2


def _is_int(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _is_hex_digest(value) -> bool:
    if not isinstance(value, str) or len(value) != 64:
        return False
    try:
        int(value, 16)
    except ValueError:
        return False
    return True


def canonical(value) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str
    ).encode("utf-8")


def digest(value) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def current_contracts_digest() -> str:
    """当前原子契约表的 digest（只读，取自仓内 ``live_selector``）。

    与证书模块共用同一来源：契约文件一变（atom id / requires / adds / cost），
    计划库与证书同时失效，不会出现"半新半旧"。
    """

    return str(nf.live_selector.CONTRACTS_DIGEST)


def _validate_state(state, label: str = "state") -> None:
    if not isinstance(state, dict):
        raise ValueError("{} must be an object".format(label))
    if not isinstance(state.get("artifact"), dict):
        raise ValueError("{} must contain artifact object".format(label))
    if not isinstance(state.get("goal"), str):
        raise ValueError("{} must contain goal string".format(label))


def _facet_gaps(state: dict) -> list[str]:
    return sorted(
        gap for gap in nf.completion_gaps(state) if isinstance(gap, str) and gap.startswith("facet:")
    )


def plan_key(state: dict) -> str:
    """结构签名：available_keys + unmet + facet gaps（不含 goal/artifact 文本）。"""

    _validate_state(state)
    payload = {
        "schema": KEY_SCHEMA,
        "available_keys": sorted(nf.available_keys(state)),
        "unmet": sorted(nf.unmet(state)),
        "facet_gaps": _facet_gaps(state),
    }
    return digest(payload)


def _valid_plan_shape(plan) -> list[list[str]]:
    if not isinstance(plan, (list, tuple)) or not plan:
        raise ValueError("plan must be a non-empty sequence of clusters")
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


def _betacf(a: float, b: float, x: float) -> float:
    """正则化不完全 Beta 的连分式（modified Lentz，Numerical Recipes 6.4）。"""

    max_iterations = 200
    eps = 3e-14
    fpmin = 1e-300
    qab = a + b
    qap = a + 1.0
    qam = a - 1.0
    c = 1.0
    d = 1.0 - qab * x / qap
    if abs(d) < fpmin:
        d = fpmin
    d = 1.0 / d
    h = d
    for m in range(1, max_iterations + 1):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        if abs(d) < fpmin:
            d = fpmin
        c = 1.0 + aa / c
        if abs(c) < fpmin:
            c = fpmin
        d = 1.0 / d
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        if abs(d) < fpmin:
            d = fpmin
        c = 1.0 + aa / c
        if abs(c) < fpmin:
            c = fpmin
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < eps:
            break
    return h


def _betai(a: float, b: float, x: float) -> float:
    """正则化不完全 Beta 函数 I_x(a, b)（连续部分用 ``_betacf``）。"""

    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    log_bt = (
        math.lgamma(a + b)
        - math.lgamma(a)
        - math.lgamma(b)
        + a * math.log(x)
        + b * math.log1p(-x)
    )
    bt = math.exp(log_bt)
    if x < (a + 1.0) / (a + b + 2.0):
        return bt * _betacf(a, b, x) / a
    return 1.0 - bt * _betacf(b, a, 1.0 - x) / b


def beta_quantile(p: float, a: float, b: float, iterations: int = QUANTILE_ITERATIONS) -> float:
    """Beta(a, b) 的 p 分位（二分 64 次，确定性数值解）。"""

    if not isinstance(p, (int, float)) or isinstance(p, bool) or not 0.0 < float(p) < 1.0:
        raise ValueError("p must be in (0, 1)")
    if not math.isfinite(float(a)) or not math.isfinite(float(b)) or a <= 0 or b <= 0:
        raise ValueError("a and b must be positive finite numbers")
    if not _is_int(iterations) or iterations < 1:
        raise ValueError("iterations must be a positive integer")
    low, high = 0.0, 1.0
    for _ in range(iterations):
        mid = (low + high) / 2.0
        if _betai(float(a), float(b), mid) < float(p):
            low = mid
        else:
            high = mid
    return (low + high) / 2.0


def beta_lower(trials: int, completions: int) -> float:
    """Beta 后验的 10% 分位（90% 单侧下界），精确分位而非正态近似。

    ``Beta(BETA_PRIOR[0] + completions, BETA_PRIOR[1] + trials - completions)``
    的 ``LOWER_ALPHA`` 分位。全成功时：n=3→0.562、5→0.681、7→0.750、
    8→0.774、15→0.866（与 golden 值一致）。
    """

    for name, value in (("trials", trials), ("completions", completions)):
        if not _is_int(value) or value < 0:
            raise ValueError("{} must be a non-negative integer".format(name))
    if completions > trials:
        raise ValueError("completions must not exceed trials")
    if trials > MAX_TRIALS:
        raise ValueError("trials is too large")
    a = BETA_PRIOR[0] + completions
    b = BETA_PRIOR[1] + (trials - completions)
    return max(0.0, min(1.0, beta_quantile(LOWER_ALPHA, a, b)))


class PlanMemory:
    """digest-only 计划案例库；路径可选（None = 纯内存）。"""

    def __init__(self, path=None, contracts_digest: str | None = None, *, threshold=DEFAULT_THRESHOLD):
        if path is not None and not isinstance(path, (str, os.PathLike)):
            raise ValueError("path must be a path-like object or None")
        if not isinstance(threshold, (int, float)) or isinstance(threshold, bool):
            raise ValueError("threshold must be a finite number in [0, 1]")
        if not math.isfinite(threshold) or not 0.0 <= float(threshold) <= 1.0:
            raise ValueError("threshold must be a finite number in [0, 1]")
        self.path = Path(path) if path is not None else None
        self.contracts_digest = (
            str(contracts_digest)
            if contracts_digest is not None
            else current_contracts_digest()
        )
        self.threshold = float(threshold)
        self._records: dict[str, dict] = {}
        self._hits = 0
        self._misses = 0
        self._drift = False
        self._loaded = False
        if self.path is not None and self.path.exists():
            self.load()

    # ------------------------------------------------------------------ 结构签名
    @staticmethod
    def key(state: dict) -> str:
        return plan_key(state)

    # ------------------------------------------------------------------ 查询
    def lookup(self, state: dict, threshold: float | None = None) -> dict | None:
        """Beta 10% 精确分位 ≥ 阈值才返回计划；quarantine 记录直接 miss。

        返回体只有 ``memory_hit/trials/completions/plan``：**不含浮点下界**，
        避免被调用方当作排序分。门限统计见 ``stats()["threshold"]``。
        """

        threshold = self.threshold if threshold is None else self._validated_threshold(threshold)
        key = self.key(state)
        record = self._records.get(key)
        if record is None:
            self._misses += 1
            return None
        if int(record.get("contra", 0)) >= QUARANTINE_LIMIT:
            self._misses += 1
            return None
        lower = beta_lower(int(record["trials"]), int(record["completions"]))
        # 分位是数值解：门限比较统一取整到 1e-3（0.749894 → 0.750）。
        if round(lower, COMPARE_DECIMALS) < round(threshold, COMPARE_DECIMALS):
            self._misses += 1
            return None
        self._hits += 1
        return {
            "memory_hit": True,
            "trials": int(record["trials"]),
            "completions": int(record["completions"]),
            "plan": [list(cluster) for cluster in record["plan"]],
        }

    def peek(self, state: dict, threshold: float | None = None) -> bool:
        """只读命中判定：语义同 ``lookup``，但**不推进** hits/misses 计数。

        供 ``ReasoningSession.begin_turn`` 的"只读"语义使用（不污染会话统计）。
        """

        threshold = self.threshold if threshold is None else self._validated_threshold(threshold)
        record = self._records.get(self.key(state))
        if record is None or int(record.get("contra", 0)) >= QUARANTINE_LIMIT:
            return False
        lower = beta_lower(int(record["trials"]), int(record["completions"]))
        return round(lower, COMPARE_DECIMALS) >= round(threshold, COMPARE_DECIMALS)

    def steering_features(self, state: dict, threshold: float | None = None) -> dict:
        """只进 steering 的特征：``memory_hit`` 0/1 + 结构签名 digest。

        注意：命中不等于"计划已被验证"；调用方必须重新影子执行 + 步级判定。
        """

        hit = self.lookup(state, threshold=threshold)
        return {
            "memory_hit": 1 if hit is not None else 0,
            "key_digest": self.key(state),
        }

    # ------------------------------------------------------------------ 记录
    def record(self, state: dict, plan, completed: bool, source_digest: str | None = None) -> dict:
        """记录一次尝试；``completed`` 必须是真实执行结果，不是预测。

        ``source_digest`` **必填**（调用方提供的状态/证书 fingerprint，64 位 hex）：
        没有来源的写入一律拒绝，避免"凭空写计划"绕过验证链。
        """

        if not isinstance(completed, bool):
            raise ValueError("completed must be a boolean")
        if not _is_hex_digest(source_digest):
            raise ValueError("source_digest is required and must be a 64-char hex digest")
        atoms = _valid_plan_shape(plan)
        key = self.key(state)
        record = self._records.get(key)
        if record is None:
            record = {
                "plan": atoms,
                "trials": 0,
                "completions": 0,
                "contra": 0,
                "source_digest": str(source_digest),
            }
            self._records[key] = record
        # plan 保持首次入库的顺序与内容；后续只累计证据（不静默替换计划）。
        record["trials"] = int(record["trials"]) + 1
        if completed:
            record["completions"] = int(record["completions"]) + 1
            record["contra"] = 0
        else:
            record["contra"] = int(record.get("contra", 0)) + 1
        record["source_digest"] = str(source_digest)
        return {
            "key": key,
            "trials": int(record["trials"]),
            "completions": int(record["completions"]),
            "contra": int(record["contra"]),
            "quarantined": int(record["contra"]) >= QUARANTINE_LIMIT,
        }

    # ------------------------------------------------------------------ 统计
    def stats(self) -> dict:
        return {
            "records": len(self._records),
            "hits": int(self._hits),
            "misses": int(self._misses),
            "drift": bool(self._drift),
            "quarantined": sum(
                1 for record in self._records.values() if int(record.get("contra", 0)) >= QUARANTINE_LIMIT
            ),
            "threshold": float(self.threshold),
        }

    # ------------------------------------------------------------------ 持久化
    def _payload(self) -> dict:
        records = {}
        for key in sorted(self._records):
            record = self._records[key]
            records[key] = {
                "plan": [list(cluster) for cluster in record["plan"]],
                "trials": int(record["trials"]),
                "completions": int(record["completions"]),
                "contra": int(record.get("contra", 0)),
                "source_digest": str(record.get("source_digest", "")),
            }
        return {
            "schema": SCHEMA,
            "contracts_digest": self.contracts_digest,
            "records": records,
        }

    def save(self):
        """原子写：同目录临时文件 + ``os.replace``；返回写入路径（无路径则 None）。"""

        if self.path is None:
            return None
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = canonical(self._payload())
        handle = tempfile.NamedTemporaryFile(
            mode="wb",
            dir=str(self.path.parent),
            prefix=self.path.name + ".",
            suffix=".tmp",
            delete=False,
        )
        try:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        finally:
            handle.close()
        os.replace(handle.name, self.path)
        return self.path

    def _archive(self, raw: bytes) -> Path:
        """把当前文件复制为 ``<name>.drift-<epoch>.json``（审计用）。"""

        if self.path is None:  # pragma: no cover - load 已保证有路径
            raise ValueError("memory path is not configured")
        epoch = int(time.time())
        while True:
            target = self.path.with_name(
                "{}.drift-{}{}".format(self.path.stem, epoch, self.path.suffix)
            )
            if not target.exists():
                break
            epoch += 1
        target.write_bytes(raw)
        return target

    def load(self):
        """读取并校验；损坏 / schema 不符 / 记录非法 → ``ValueError``（fail-closed）。"""

        if self.path is None:
            raise ValueError("memory path is not configured")
        raw = self.path.read_bytes()
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("plan memory file is corrupt") from exc
        if not isinstance(payload, dict) or payload.get("schema") != SCHEMA:
            raise ValueError("plan memory schema mismatch")
        stored_digest = payload.get("contracts_digest")
        if not isinstance(stored_digest, str) or not stored_digest:
            raise ValueError("plan memory contracts_digest is invalid")
        records = payload.get("records")
        if not isinstance(records, dict):
            raise ValueError("plan memory records are invalid")
        parsed: dict[str, dict] = {}
        for key, record in records.items():
            if not isinstance(key, str) or len(key) != 64:
                raise ValueError("plan memory key is invalid")
            try:
                int(key, 16)
            except ValueError as exc:
                raise ValueError("plan memory key is invalid") from exc
            if not isinstance(record, dict):
                raise ValueError("plan memory record is invalid")
            plan = _valid_plan_shape(record.get("plan"))
            trials = record.get("trials")
            completions = record.get("completions")
            if not _is_int(trials) or not _is_int(completions):
                raise ValueError("plan memory counters are invalid")
            if trials < 1 or completions < 0 or completions > trials:
                raise ValueError("plan memory counters are invalid")
            contra = record.get("contra", 0)
            if not _is_int(contra) or contra < 0:
                raise ValueError("plan memory contra counter is invalid")
            source = record.get("source_digest", "")
            if source != "" and not _is_hex_digest(source):
                raise ValueError("plan memory source_digest is invalid")
            parsed[key] = {
                "plan": plan,
                "trials": trials,
                "completions": completions,
                "contra": contra,
                "source_digest": source,
            }
        self._loaded = True
        if stored_digest != self.contracts_digest:
            # 契约漂移：先把旧文件归档（保留审计），再全部失效，不静默复用。
            self._archive(raw)
            self._records = {}
            self._drift = True
        else:
            self._records = parsed
            self._drift = False
        return self

    @staticmethod
    def _validated_threshold(threshold) -> float:
        if not isinstance(threshold, (int, float)) or isinstance(threshold, bool):
            raise ValueError("threshold must be a finite number in [0, 1]")
        if not math.isfinite(threshold) or not 0.0 <= float(threshold) <= 1.0:
            raise ValueError("threshold must be a finite number in [0, 1]")
        return float(threshold)

