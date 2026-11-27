"""core.gate_engine 私有实现分片 1/2（对外只经 core.gate_engine 门面导入）：_SRC、CODE_FACE 等"""

from __future__ import annotations

import importlib
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from core import gate_inproc, gate_labels, gate_native, repo_trust
from core.gate_labels import Labels

#: 让 `core.*` 可导入（与 verify.sh 的 heredoc 同一条纪律：
#: `sys.path.insert(0, os.path.join('desktop','src'))`）。引擎被当脚本直接跑时
#: 包路径尚未建立，故此处显式补上——与门禁侧的导入面完全一致。
_SRC = str(Path(__file__).resolve().parents[2])


if _SRC not in sys.path:
    sys.path.insert(0, _SRC)


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


@dataclass(frozen=True)
class _DelegateSpec:
    """参数对象（审计 C-007：把成组参数收成不可变对象）。"""
    num: int
    title: str
    module: str
    func: str
    reads: Sequence[str]
    labels: Labels
    show_stats: bool = False


def _delegate(opts: _DelegateSpec) -> Callable[[Path], Verdict]:
    """通用委托：调 `core.<module>.<func>(root)` → (issues, stats) → verdict 行。

    与 verify.sh 的语义逐条对齐：
      - `issues` 非空 → `no("…异常——" + 最后两行摘要)`，否则 `ok(label)`；
      - 无论上面结果如何，err==0 时再补一条 `ok(总结)`（verify.sh 的 `if [ $err -eq 0 ]` 分支）；
      - 退出码/统计行不进 verdict 面，只做统计信息。
    """

    num = opts.num
    title = opts.title
    module = opts.module
    func = opts.func
    labels = opts.labels
    show_stats = opts.show_stats

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


def _trust_gate(num: int, title: str, root: Path) -> Verdict | None:
    """H1（2026-10-22 安全审计）：执行目标仓库自带代码前的信任门。

    `nf verify` 的 inproc/script 面会把目标仓库 verify.sh 的 heredoc Python 当本机进程
    代码执行（CWE-94）。只有当前安装根自动可信；外部仓库即使伪造 origin 也**默认拒绝**，
    需显式 `--trust-repo`（NF_TRUST_REPO=1）。返回 None=放行；Verdict=拒绝并如实报 FAIL。
    （**不假装 PASS**：拒绝本身是协议面结论，与 bash 的判据不同形，但明确写出原因）。
    """
    ok, why = repo_trust.trust_status(str(root))
    if ok:
        return None
    v = Verdict(name=f"check{num}", title=title, status=FAIL)
    v.verdicts.append((FAIL, repo_trust.refusal_message(str(root), why)))
    return v


def _script(rel: str, num: int, title: str, labels: Labels) -> Callable[[Path], Verdict]:
    """「独立脚本」型 check：直接 `runpy` 跑该脚本，按退出码定胜负。

    适用面（本仓实测就一处）：check37 的门禁体是 `"$PY3" scripts/check37_knowledge.py`
    ——判据全在那个脚本里，bash 只是转发退出码 + 打两条 ok/no。故引擎也照做：
    **不重写脚本**、不碰它的判据，只是省掉一层 bash + 一次解释器启动。
    脚本自己调 `sys.exit(n)` 由 `gate_inproc.run_script` 收成返回值，**不杀门禁进程**。
    """
    def run(root: Path) -> Verdict:
        refused = _trust_gate(num, title, root)
        if refused is not None:
            return refused
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
