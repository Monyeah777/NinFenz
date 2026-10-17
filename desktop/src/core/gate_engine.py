#!/usr/bin/env python3
"""门禁单进程引擎（骨架）——**只做编排，不改判据**。

定位（与计划 L-A 对应）
-----------------------
现状：`verify.sh` 是 bash 主执行体，靠 **42 次 `$PY3` 启动**、**125 次 `git diff`** 与
40 条各自独立的 heredoc 拼出来；实测全量 1462 s，其中 96% 是 check12 的 unittest。

本模块要证明的那一件事：**门禁的 40 条判据可以在一个进程里跑完**——
省掉的是进程启动税与重复读取，判据本身一个字都不动。

两条硬纪律（不可交易）
----------------------
1. **判据零改动**：本引擎不重新实现任何判定逻辑。凡是已有 `core.*` 实现的 check，
   一律**委托**给同一份实现（`verify.sh` 的 heredoc 也是调它），因此「引擎的结论」
   与「门禁的结论」同源；差异只可能来自编排，不可能来自判据。
2. **可比对**：输出行格式与 `verify.sh` 的 `ok/no/wn` **逐字同形**
   （`  [PASS] …` / `  [FAIL] …` / `  [WARN] …`），故可用同一解析器做逐 check 差分，
   等价性是**测出来的**而不是声称的（见 tests 里的 parity 用例）。

三级状态（与 verify.sh 对齐）
----------------------------
- `delegated`：委托 `core.*`，已是生产实现；
- `native`：本引擎内实现（目前仅用于纯结构性 check，逐一对照 verify.sh 手写）；
- `pending`：尚未迁入（仍在 bash 里），引擎如实报「未迁入」，**不假装绿**。

内容寻址 memo
--------------
键 = sha256(根 + check 名 + 代码面内容 + 声明的读面内容)。命中即跳过重算，
但**只在 `--memo` 打开时**——默认关闭，保证「引擎输出 ≡ 门禁输出」这条差分测试
永远测的是真跑，而不是回放。
"""
from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import os
import sys
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

#: 仓库根：本文件在 desktop/src/core/ 下，向上三级即根。
ROOT = Path(__file__).resolve().parents[3]
#: 让 `core.*` 可导入（与 verify.sh 的 heredoc 同一条纪律：
#: `sys.path.insert(0, os.path.join('desktop','src'))`）。引擎被当脚本直接跑时
#: 包路径尚未建立，故此处显式补上——与门禁侧的导入面完全一致。
_SRC = str(Path(__file__).resolve().parents[1])
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

# 必须在补好 sys.path **之后**才能 import core.*（引擎可被当脚本直接跑）。
from core import gate_inproc, gate_labels, gate_native  # noqa: E402
from core.gate_labels import Labels  # noqa: E402

#: 代码面：改了这些文件必须换键（沿用 disk_cache 的「算法面进键」纪律）。
CODE_FACE = ("desktop/src/core/gate_engine.py",)

PASS, FAIL, WARN = "PASS", "FAIL", "WARN"


@dataclass
class Verdict:
    """一条 check 的结论：逐条 verdict + 可选统计行。"""

    name: str
    title: str = ""                        # banner 文本（与 verify.sh 逐字一致，供差分对齐）
    status: str = PASS                     # PASS / FAIL / WARN / SKIP
    verdicts: list[tuple[str, str]] = field(default_factory=list)  # [(PASS/FAIL/WARN, 文案)]
    stats: dict[str, Any] = field(default_factory=dict)
    note: str = ""
    seconds: float = 0.0
    cached: bool = False

    @property
    def fails(self) -> int:
        return sum(1 for s, _ in self.verdicts if s == FAIL)

    @property
    def warns(self) -> int:
        return sum(1 for s, _ in self.verdicts if s == WARN)


# ---------------------------------------------------------------- 注册表

@dataclass
class CheckSpec:
    num: int
    title: str                       # verify.sh 的 banner 文本（用于差分对齐）
    impl: Callable[[Path], Verdict]
    reads: tuple[str, ...] = ()      # 声明的读面（内容键用；空 = 未声明，键退化为代码面）
    kind: str = "native"             # delegated / native


REGISTRY: dict[int, CheckSpec] = {}


def check(num: int, title: str, reads: Sequence[str] = (), kind: str = "native"):
    def deco(fn: Callable[[Path], Verdict]) -> Callable[[Path], Verdict]:
        REGISTRY[num] = CheckSpec(num=num, title=title, impl=fn,
                                  reads=tuple(reads), kind=kind)
        return fn
    return deco


# ---------------------------------------------------------------- 输出面（与 verify.sh 同形）

def emit(v: Verdict, stream: Any = None) -> None:
    """按 verify.sh 的 `ok/no/wn` 同形打印。banner 也与 verify.sh 逐字一致。"""
    stream = stream or sys.stdout
    print(v.title, file=stream)
    for status, msg in v.verdicts:
        print("  [{}] {}".format(status, msg), file=stream)
    for k, val in v.stats.items():
        print("  [i] {}={}".format(k, val), file=stream)


# ---------------------------------------------------------------- 委托式 check 实现

def _read_registry_json(root: Path) -> Any:
    """读 registry.json（供 `gate_labels.resolve_shell_vars` 展开 `$v02`）。

    走本仓**唯一读点** `core.json_doc`（未校验的裸 `json.load` 会被
    `test_json_shape_contracts.UnguardedRatchetTest` 判红——它要求新读点都走这一层）。
    """
    from core import json_doc
    return json_doc.load(Path(root) / "desktop" / "src" / "core" / "registry.json",
                         dict, what="registry.json")


def _resolve_vars(text: str, root: Path) -> str:
    """把文案里已知的 shell 变量展开（薄封装：绑定 registry 读取面）。"""
    return gate_labels.resolve_shell_vars(text, root, read_json=_read_registry_json)


#: 读 verify.sh 失败的原因（诊断面；空 = 读到了）。
_MISSING_VERIFY_SH: list[str] = []


def _verify_sh() -> str | None:
    """读 verify.sh 文本（判据/文案的单源）。缺席即 None——引擎不猜。"""
    try:
        return (ROOT / "verify.sh").read_text(encoding="utf-8")
    except OSError as exc:      # 缺席即 None——调用方据此报「未取到真源」，不静默当通过
        _MISSING_VERIFY_SH.append(str(exc))
        return None


def _delegate(num: int, title: str, module: str, func: str,
              reads: Sequence[str], labels: Labels,
              show_stats: bool = False) -> Callable[[Path], Verdict]:
    """通用委托：调 `core.<module>.<func>(root)` → (issues, stats) → verdict 行。

    与 verify.sh 的语义逐条对齐：
      - `issues` 非空 → `no("…异常——" + 最后两行摘要)`，否则 `ok(label)`；
      - 无论上面结果如何，err==0 时再补一条 `ok(总结)`（verify.sh 的 `if [ $err -eq 0 ]` 分支）；
      - 退出码/统计行不进 verdict 面，只做统计信息。
    """

    def run(root: Path) -> Verdict:
        v = Verdict(name="check%d" % num, title=title, status=PASS)
        try:
            mod = importlib.import_module("core.{}".format(module))
            fn = getattr(mod, func)
        except Exception as exc:
            v.verdicts.append((FAIL, "{}异常——import 失败：{}".format(labels.success, exc)))
            v.status = FAIL
            return v
        try:
            res = fn(str(root))
        except Exception as exc:
            v.verdicts.append((FAIL, "{}异常——{}".format(labels.success, exc)))
            v.status = FAIL
            return v
        # 两种既有返回形状都要支持（都是生产实现的真实签名）：
        #   (issues, stats)          —— 多数 check
        #   (issues, warns, stats)   —— check40 的 asset_contract.scan
        warns: list[str] = []
        if isinstance(res, tuple) and len(res) == 3:
            issues, warns, stats = res
        elif isinstance(res, tuple) and len(res) == 2:
            issues, stats = res
        else:
            issues, stats = res, {}
        issues = list(issues or [])
        warns = list(warns or [])
        v.stats = {} if not show_stats else (
            {k: stats[k] for k in sorted(stats)} if isinstance(stats, dict) else {})
        for w in warns:
            v.verdicts.append((WARN, str(w)))
        if issues:
            tail = " ".join(str(i) for i in issues[-2:])
            v.verdicts.append((FAIL, "{}{}".format(labels.fail_prefix or "{}异常——".format(labels.success),
                                               tail)))
            v.status = FAIL
        else:
            for msg in labels.pass_lines:
                v.verdicts.append((PASS, _resolve_vars(msg, root)))
            if not v.verdicts:
                v.verdicts.append((PASS, "check%d 通过（verify.sh 未给文案）" % num))
        if warns and not issues:
            v.status = WARN
        return v

    return run


#: 统计面白名单：只有这些 check 的 stats 值得进人读输出。
#: 为什么需要白名单（实测踩过）：check32 的 `quality_depth_scan` 统计里带
#: `domain_packs` / `payload_consumer` / `output_forms` 三张大表，直接打印会吐出
#: **百万行级** stdout——门禁输出是给人看的，统计默认不进输出面。
STATS_WHITELIST: frozenset = frozenset()


#: 走「进程内」的 check（L-A 主力）：这些 check 在 verify.sh 里的主体是
#: `"$PY3" - <<'PYEOF' … PYEOF`，源码逐字照抄进 `core.gate_inproc` 执行，
#: 省掉一次解释器启动。判据一字不改——退出码仍由 heredoc 自己的 sys.exit 决定。
#:
#: 其中 **8 / 16 / 35 是多 heredoc 形态**：走 `_inproc` 的「整段体优先」路径
#: （bash 的 if/then/else 与多条 heredoc 顺序真实执行），不再是「只取第一个 heredoc」。
INPROC_CHECKS: tuple[int, ...] = (13, 14, 15, 20, 30, 33, 34, 36, 39)

#: 「独立脚本」型 check：(脚本相对路径, check 号)。
#: 判据全在脚本里，bash 只转发退出码 ⇒ 引擎用 `runpy` 原地跑，省一层 bash + 一次启动。
SCRIPT_CHECKS: tuple[tuple[str, int], ...] = (("scripts/check37_knowledge.py", 37),)

#: **多 heredoc 形态仍留在 PENDING**（8 / 16 / 35）：它们的判据分布在 2 个 heredoc 上，
#: 而「整段 check 体进程内执行」需要 bash→Python 的语法转写（`for f in a.md b.md; do`
#: 这类 bash 独有语法在 Python 里就是语法错）。实测做到一半发现收益/风险比不划算：
#: 其失败文案的拼接口径（前缀 + `tail -N | tr`）必须逐字复刻才不破坏等价性，
#: 而这三条合计只值几秒。**宁可如实标未迁入，也不发一条与门禁不完全一致的判定。**

#: **本轮仍未迁入**：`8` —— 它的成功文案是**运行时拼出来的**（`${_bl_sum:-N/A}` 是
#: heredoc 算出的逐包行数摘要）。整段体路径能拿到它的 PASS/FAIL 判定，但拿不到那条
#: 文案（需要把 heredoc 算出的 shell 变量回填），故如实留在 PENDING，
#: 不发一条占位文案冒充门禁输出。


def _script(rel: str, num: int, title: str, labels: Labels) -> Callable[[Path], Verdict]:
    """「独立脚本」型 check：直接 `runpy` 跑该脚本，按退出码定胜负。

    适用面（本仓实测就一处）：check37 的门禁体是 `"$PY3" scripts/check37_knowledge.py`
    ——判据全在那个脚本里，bash 只是转发退出码 + 打两条 ok/no。故引擎也照做：
    **不重写脚本**、不碰它的判据，只是省掉一层 bash + 一次解释器启动。
    脚本自己调 `sys.exit(n)` 由 `gate_inproc.run_script` 收成返回值，**不杀门禁进程**。
    """
    def run(root: Path) -> Verdict:
        v = Verdict(name="check%d" % num, title=title, status=PASS)
        code, out = gate_inproc.run_script(root / rel, root, "check%d" % num)
        if code == 0:
            for msg in labels.pass_lines:
                v.verdicts.append((PASS, _resolve_vars(msg, root)))
            if not v.verdicts:
                v.verdicts.append((PASS, "check%d 通过（verify.sh 未给文案）" % num))
        else:
            v.verdicts.append((FAIL, "{}{}".format(labels.fail_prefix, gate_inproc.tail(out, 3))))
            v.status = FAIL
        return v
    return run


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
        v = Verdict(name="check%d" % num, title=title, status=PASS)
        text = _verify_sh() or ""
        if exact:
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
        else:
            # 与 bash 逐字同形：`no "<前缀>$(tail -3 log | tr '\n' ' ')"`。
            # 两处细节都不能省（都实测踩过）：
            #  ① 不能逐行发 FAIL——脚本自己写出的 `[FAIL] …` 行也是日志内容的一部分，
            #     bash 把它们（按 tail 截取后）**拼成一条**诊断串（check35 即三行拼一条）；
            #  ② 当那段拼接串**本身就以 `[FAIL]` 开头**时，**不再叠 `no` 的前缀**——
            #     bash 打出来就是对得上（前缀会把同一件事说两遍）。实测 check35 因此红了。
            tail = gate_inproc.tail(out, 3)
            prefix = labels.fail_prefix
            if tail.lstrip().startswith("[FAIL]"):
                v.verdicts.append((FAIL, tail))
            else:
                v.verdicts.append((FAIL, "{}{}".format(prefix, tail)))
            v.status = FAIL
        return v

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
    ]
    text = _verify_sh() or ""
    for num, module, func in specs:
        labels = gate_labels.parse_labels(text, num)
        REGISTRY[num] = CheckSpec(
            num=num, title=gate_labels.banner(text, num), reads=(), kind="delegated",
            impl=_delegate(num, gate_labels.banner(text, num), module, func, (), labels,
                           show_stats=(num in STATS_WHITELIST)),
        )



PENDING: dict[int, str] = {
    2: "重号 ID 全限定（含 awk 逐行类别判定）",
    4: "可见性边界（grep 多模式）",
    5: "质检门（grep 多模式）",
    6: "入口导航（grep + 目录统计）",
    7: "社区两包结构完整（find/sed/wc）",
    8: "社区资产行数溯源（判据分两个 heredoc + 成功文案为运行时拼接）",
    9: "模块-资产引用可寻址（awk）",
    10: "EXT 闭合 + 社区红线（grep×13）",
    11: "资产三方对账（bash scripts/reconcile_assets.sh）",
    12: "桌面核心单元测试 + py_compile（3035 tests，本工程主战场）",
    16: "契约仲裁门禁（判据分两个 heredoc：A 装配契约 + B 运行时寻址授权）",
    17: "质量治理门（unittest 单模块）",
    18: "导出契约门（unittest 2 模块）",
    19: "导出产物 schema 合规（unittest）",
    21: "registry 引用图闭合（unittest）",
    22: "导出物规范体检（unittest 3 模块）",
    35: "深化面门禁（失败面为 tail-3 拼接 + 子扫描统计，多段结构）",
    38: "出口自动化门禁（6 次解释器循环）",
}


def _native_runner(num: int, verify_text: str) -> Callable[[Path], Verdict]:
    """把 `gate_native` 的纯结构判定包成引擎的 `-> Verdict` 形状。

    结构面之所以单独成件：它只做「逐条对照路径清单/不变式字样」，与编排无关；
    拆出去也让引擎回到本仓 `code_metrics` 的模块行数闸门之内。
    """
    fn = getattr(gate_native, "check%d" % num)

    def run(root: Path) -> Verdict:
        v = Verdict(name="check%d" % num, title=gate_labels.banner(verify_text, num), status=PASS)
        v.verdicts = list(fn(verify_text, root))
        if any(s == FAIL for s, _ in v.verdicts):
            v.status = FAIL
        return v

    return run


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


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="门禁单进程引擎（骨架）")
    ap.add_argument("--only", default="", help="逗号分隔的 check 号（默认全部已迁入）")
    ap.add_argument("--memo", action="store_true", help="打开内容寻址 memo（默认关）")
    ap.add_argument("--json", action="store_true", help="机器面")
    ap.add_argument("--repeat", type=int, default=1, help="连跑 N 遍（看 memo 收益）")
    ap.add_argument("--quiet-time", action="store_true",
                    help="输出里不带墙钟耗时（**确定性输出**用；见下）")
    a = ap.parse_args(argv)

    # 不确定性面**默认不进输出**（2026-10-15 实测教训）：`nf verify` 曾被
    # test_daemon_parity 抓到「直跑 vs 守护」输出逐字节不同（3480 vs 3478 字节），
    # 根因就是我在人读面里打了墙钟耗时——而守护与直跑的耗时必然不同。
    # 机器可比面的纪律是「同输入同字节」，故耗时只在显式要（--repeat>1）或在
    # 人读面且未被要求静默时才出现。
    quiet = a.quiet_time or os.environ.get("NF_VERIFY_QUIET_TIME") == "1"
    if os.environ.get("NF_VERIFY_QUIET_TIME") == "1":
        a.quiet_time = True

    root = ROOT
    only = [int(x) for x in a.only.split(",") if x.strip()] if a.only else None
    m = Memo() if a.memo else None

    allv: list[Verdict] = []
    wall0 = time.perf_counter()
    for _ in range(max(1, a.repeat)):
        allv = run_checks(root, only, m)
        if not a.json and a.repeat > 1 and _ < a.repeat - 1:
            continue
    wall = time.perf_counter() - wall0

    if a.json:
        payload: dict[str, Any] = {
            "checks": [{"name": v.name, "status": v.status, "cached": v.cached,
                        "fails": v.fails, "warns": v.warns} for v in allv],
            "pending": len(PENDING),
        }
        if not quiet:
            payload["wall_seconds"] = round(wall, 4)
            payload["memo"] = None if m is None else {"hits": m.hits, "misses": m.misses}
        else:
            payload["checks"] = [
                {"name": v.name, "status": v.status, "cached": v.cached,
                 "fails": v.fails, "warns": v.warns} for v in allv]
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
        return 0

    build_registry()
    for v in allv:
        emit(v)
    pf = sum(v.fails for v in allv)
    print("=" * 50)
    if quiet:
        print("引擎结果：已迁入 %d 条 / 未迁入 %d 条；FAIL=%d"
              % (len(allv), len(PENDING), pf))
    else:
        print("引擎结果：已迁入 %d 条 / 未迁入 %d 条；FAIL=%d WARN=%d"
              % (len(allv), len(PENDING), pf, sum(v.warns for v in allv)))
        print("墙钟 %.3f s（repeat=%d%s）"
              % (wall, a.repeat, "" if m is None else
                 "，memo 命中 %d / 未命中 %d" % (m.hits, m.misses)))
        for v in sorted(allv, key=lambda x: -x.seconds)[:5]:
            print("  最慢：%-10s %8.1f ms%s" % (v.name, v.seconds * 1000,
                                              "（memo）" if v.cached else ""))
    return 1 if pf else 0


if __name__ == "__main__":
    for _s in (sys.stdout, sys.stderr):
        if hasattr(_s, "reconfigure"):
            _s.reconfigure(encoding="utf-8")
    raise SystemExit(main())
