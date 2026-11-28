"""core.gate_engine 私有实现分片 2/2（对外只经 core.gate_engine 门面导入）：_digest_file 等"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from core import gate_inproc, gate_labels, repo_trust
from core.gate_labels import Labels

from ._part1 import (
    _MISSING_VERIFY_SH,
    CODE_FACE,
    FAIL,
    INPROC_CHECKS,
    PASS,
    PENDING,
    REGISTRY,
    SCRIPT_CHECKS,
    STATS_WHITELIST,
    CheckSpec,
    Verdict,
    _delegate,
    _DelegateSpec,
    _native_runner,
    _resolve_vars,
    _script,
    _trust_gate,
    emit,
)

from ._cli import (
    _apply_trust_env,
    _json_payload,
    _only_ids,
    _parser,
    _print_summary,
    _quiet_flags,
    _restore_trust_env,
)

# ---------------------------------------------------------------- 内容寻址 memo

def _digest_file(p: Path) -> str:
    try:
        return hashlib.sha256(p.read_bytes()).hexdigest()
    except OSError:
        return ""


def content_key(spec: CheckSpec, root: Path) -> str:
    """键 = 根 + check 名 + 代码面 + 声明读面（顺序稳定，缺失记空）。"""
    h = hashlib.sha256()
    h.update(str(root.resolve()).encode("utf-8"))
    h.update(b"\0gate_engine\0")
    for rel in CODE_FACE + tuple(spec.reads):
        h.update(rel.encode("utf-8"))
        h.update(b"\0")
        h.update(_digest_file(root / rel).encode("ascii"))
        h.update(b"\0")
    return h.hexdigest()


class Memo:
    """内容寻址 memo：只在 --memo 打开时生效；落点默认在 NF_HOME 之外的内存里。

    骨架阶段刻意**不落盘**：先把「同源 + 等价」证明做扎实，落盘缓存（L-C）留到有
    反例测试守着之后再开——顺序反了就是用缓存掩盖判据漂移。
    """

    def __init__(self) -> None:
        self.store: dict[str, dict[str, Any]] = {}
        self.hits = 0
        self.misses = 0

    def lookup(self, key: str) -> dict[str, Any] | None:
        got = self.store.get(key)
        if got is None:
            self.misses += 1
        else:
            self.hits += 1
        return got

    def put(self, key: str, value: dict[str, Any]) -> None:
        self.store[key] = value


#: 仓库根：本文件在 desktop/src/core/ 下，向上三级即根。
ROOT = Path(__file__).resolve().parents[4]


def _verify_sh() -> str | None:
    """读 verify.sh 文本（判据/文案的单源）。缺席即 None——引擎不猜。"""
    try:
        return (ROOT / "verify.sh").read_text(encoding="utf-8")
    except OSError as exc:      # 缺席即 None——调用方据此报「未取到真源」，不静默当通过
        _MISSING_VERIFY_SH.append(str(exc))
        return None


def _run_exact(num: int, title: str, labels: Labels, root: Path,
               body_text: str) -> Verdict:
    """整段 check 体进程内执行 → Verdict。"""
    v = Verdict(name="check%d" % num, title=title, status=PASS)
    _code, passes, out = gate_inproc.run_check_inproc(body_text, root, "check%d" % num)
    if not passes and "[FAIL]" not in out:
        # 成功分支是 `:`（空壳，如 check8 / check20）：正文没产出 PASS 文案，
        # 但**也没报 FAIL** ⇒ 判定通过。此时用从 verify.sh 抽到的成功文案补齐，
        # 否则与 bash 收尾那条 ok 对不上。
        passes = list(labels.pass_lines)
    for msg in passes:
        v.verdicts.append((PASS, _resolve_vars(msg, root)))
    if not v.verdicts:
        # 真失败：按 bash 的 `no "<前缀>$(tail -3 log | tr '\n' ' ')"` 逐字复刻——
        # **前缀要带**（bash 就是先打前缀，再拼 log 的末几行），
        # 且 log 要按 tail 截断（否则会把统计行也带进来，实测 check35 因此对不上）。
        tail = gate_inproc.tail(out, 3)
        v.verdicts.append((FAIL, "{}{}".format(labels.fail_prefix, tail) if tail else
                           "check%d：整段体既未产出 PASS 也未报 FAIL"
                           "（修复指引：核对 check 体）" % num))
        v.status = FAIL
    return v


def _run_heredoc(num: int, title: str, labels: Labels, root: Path,
                 text: str) -> Verdict:
    """退化路径：只跑首个 heredoc + 从 verify.sh 抽文案 → Verdict。"""
    v = Verdict(name="check%d" % num, title=title, status=PASS)
    got = gate_inproc.extract_heredoc(text, num)
    if not got:
        v.verdicts.append((FAIL, "check%d：verify.sh 里未找到 heredoc"
                                 "（修复指引：核对排版）" % num))
        v.status = FAIL
        return v
    src, logname = got
    code, out = gate_inproc.run_inproc(src, root, "check%d" % num)
    v.note = logname
    if code == 0:
        for msg in labels.pass_lines:
            v.verdicts.append((PASS, _resolve_vars(msg, root)))
        if not v.verdicts:      # 极端情形：verify.sh 未给任何成功文案
            v.verdicts.append((PASS, "check%d 通过（verify.sh 未给文案）" % num))
        return v
    # 与 bash 逐字同形：`no "<前缀>$(tail -3 log | tr '\n' ' ')"`。
    # 两处细节都不能省（都实测踩过）：
    #  ① 不能逐行发 FAIL——脚本自己写出的 `[FAIL] …` 行也是日志内容的一部分，
    #     bash 把它们（按 tail 截取后）**拼成一条**诊断串（check35 即三行拼一条）；
    #  ② 当那段拼接串**本身就以 `[FAIL]` 开头**时，**不再叠 `no` 的前缀**——
    #     bash 打出来就是对得上（前缀会把同一件事说两遍）。实测 check35 因此红了。
    tail = gate_inproc.tail(out, 3)
    if tail.lstrip().startswith("[FAIL]"):
        v.verdicts.append((FAIL, tail))
    else:
        v.verdicts.append((FAIL, "{}{}".format(labels.fail_prefix, tail)))
    v.status = FAIL
    return v


def _inproc(num: int, title: str, labels: Labels) -> Callable[[Path], Verdict]:
    """通用「进程内」执行体：优先跑**整段 check 体**，退化为只跑 heredoc。

    两条路径的取舍（实测驱动）：
      - **整段 check 体**（`gate_inproc.run_check_inproc`）最准确——bash 的
        `if/then/else`、`err=1` 累积、多条 heredoc 顺序都真实发生，故**多 heredoc 的
        check 16 / 35** 只有走它才与门禁一致；
      - 但它要求整段恰好是合法 Python。本仓不少 check 体含 bash 独有语法
        （如 `for f in a.md b.md; do`），**解析注定失败**；那些退回「只跑第一个 heredoc +
        从 verify.sh 抽文案」，并由 `test_gate_engine_parity` 逐字守等价。
    """
    body_text = gate_labels.check_body(_verify_sh() or "", num)
    try:
        compile(body_text, "<probe>", "exec")
        exact = True
    except SyntaxError:
        exact = False

    def run(root: Path) -> Verdict:
        refused = _trust_gate(num, title, root)
        if refused is not None:
            return refused
        if exact:
            return _run_exact(num, title, labels, root, body_text)
        return _run_heredoc(num, title, labels, root, _verify_sh() or "")

    return run


def _register_inproc() -> None:
    """登记全部「进程内」check（文案仍从 verify.sh 现读）。"""
    text = _verify_sh() or ""
    for num in INPROC_CHECKS:
        REGISTRY[num] = CheckSpec(
            num=num, title=gate_labels.banner(text, num), reads=(), kind="inproc",
            impl=_inproc(num, gate_labels.banner(text, num), gate_labels.parse_labels(text, num)),
        )
    for rel, num in SCRIPT_CHECKS:
        REGISTRY[num] = CheckSpec(
            num=num, title=gate_labels.banner(text, num), reads=(), kind="inproc",
            impl=_script(rel, num, gate_labels.banner(text, num),
                         gate_labels.parse_labels(text, num)),
        )


def _register_delegated() -> None:
    """登记已委托 core.* 的 check。

    **文案从 verify.sh 现读**（`parse_labels`），不手抄——手抄必然漂移：
    实测第一版引擎里 check27 等几条我抄的文案与 verify.sh 真实文案**不一致**
    （真实那条还含「阶梯归属互斥/接口子集/依赖向下 + raise 消息修复指引零缺失 + R3 去叙述」
    等 R8 内容）。既然判据与文案的单源都是 verify.sh，引擎就该读它。
    """
    specs = [
        (23, "asset_ledger", "verify_root"),
        (24, "module_lifecycle", "verify_modules"),
        (25, "knowledge_sig", "verify_reproducible"),
        (26, "semantic_conflict", "scan"),
        (27, "purity_scan", "scan"),
        (28, "schema_lint", "scan"),
        (29, "conformance_scan", "scan"),
        (31, "protocol_golden", "verify_golden"),
        (32, "quality_depth_scan", "scan"),
        (40, "asset_contract", "scan"),
        (45, "trust.gate", "scan"),
        (46, "trust.gate_g2", "scan"),
        (47, "trust.gate_g4", "scan"),
        (48, "trust.gate_dod", "scan"),
    ]
    text = _verify_sh() or ""
    for num, module, func in specs:
        labels = gate_labels.parse_labels(text, num)
        REGISTRY[num] = CheckSpec(
            num=num, title=gate_labels.banner(text, num), reads=(), kind="delegated",
            impl=_delegate(
                opts=_DelegateSpec(
                    num=num,
                    title=gate_labels.banner(text, num),
                    module=module,
                    func=func,
                    reads=(),
                    labels=labels,
                    show_stats=num in STATS_WHITELIST,
                ),
            ),
        )


def build_registry() -> None:
    """登记全部已迁入的 check。"""
    if REGISTRY:
        return
    t = _verify_sh() or ""
    REGISTRY[1] = CheckSpec(1, gate_labels.banner(t, 1),
                            _native_runner(1, t), (), "native")
    REGISTRY[3] = CheckSpec(3, gate_labels.banner(t, 3),
                            _native_runner(3, t), (), "native")
    _register_delegated()
    _register_inproc()


# ---------------------------------------------------------------- 执行

def run_checks(root: Path, only: Sequence[int] | None = None,
               memo: Memo | None = None, use_cache: bool = False) -> list[Verdict]:
    """跑 check → Verdict 列表。

    `use_cache=True`（2026-10-16 新增）：每条 check 走**子 check 内容寻址缓存**——
    按「上次观测到的真实读面」复核，等价则**不跑判据本体**，直接回上次的判定。
    语义由 `core/subcheck_cache.py` 守住（fail-closed：读面为空/含仓外/输入变或缺 ⇒ 重跑）。
    进程内 `memo` 保留：它省同一次运行里的重复，与跨进程的内容缓存互补。
    """
    build_registry()
    nums = sorted(only) if only else sorted(REGISTRY)
    out: list[Verdict] = []
    for n in nums:
        spec = REGISTRY.get(n)
        if spec is None:
            continue
        t0 = time.perf_counter()
        key = content_key(spec, root)
        payload = memo.lookup(key) if memo is not None else None
        if payload is not None:
            v = Verdict(**payload)
            v.cached = True
        elif use_cache:
            from core import subcheck_cache as sc
            # 依赖倒置（2026-10-16）：缓存模块只回「稳定字段字典」，由这里装成 Verdict——
            # 否则 subcheck_cache 要 import Verdict，与本函数的延迟 import 构成静态环
            # （被 test_coupling_metrics 的「零环」判据抓出，已修）。
            payload, state = sc.run_payload_cached(str(root), n, spec.impl, root)
            v = Verdict(**{k: payload.get(k) for k in
                           ("name", "status", "verdicts", "stats", "note") if k in payload})
            v.cached = (state == "hit")
        else:
            v = spec.impl(root)
            if memo is not None:
                memo.put(key, {"name": v.name, "status": v.status,
                               "verdicts": v.verdicts, "stats": v.stats,
                               "note": v.note, "cached": False})
        v.seconds = time.perf_counter() - t0
        out.append(v)
    return out


def _run_repeated(root: Path, only, m: Any, a) -> list[Verdict]:
    """按 --repeat 跑 N 遍 → 最后一遍结果（信任开关只在跑 check 区间内生效）。"""
    allv: list[Verdict] = []
    _saved_trust = _apply_trust_env(getattr(a, "trust_repo", False))
    try:
        for _ in range(max(1, a.repeat)):
            allv = run_checks(root, only, m)
            if not a.json and a.repeat > 1 and _ < a.repeat - 1:
                continue
    finally:
        _restore_trust_env(_saved_trust)
    return allv


def main(argv: Sequence[str] | None = None) -> int:
    a = _parser().parse_args(argv)
    quiet = _quiet_flags(a)
    root = ROOT
    only = _only_ids(a.only)
    m = Memo() if a.memo else None
    wall0 = time.perf_counter()
    allv = _run_repeated(root, only, m, a)
    wall = time.perf_counter() - wall0
    if a.json:
        print(json.dumps(_json_payload(allv, quiet, wall, m),
                         ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    build_registry()
    for v in allv:
        emit(v)
    pf = sum(v.fails for v in allv)
    _print_summary(allv, pf, wall, a, m, quiet)
    return 1 if pf else 0
