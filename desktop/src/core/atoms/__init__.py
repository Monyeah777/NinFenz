"""原子层（门禁能力化重构 · 步骤1）：纯机器动作的**唯一出处**，只把输入变成数据。

分层边界（设计文档 §4.1）：

    原子   : 输入 → 数据         无业务属性、无 PASS/FAIL、无仓内路径知识
    能力   : 输入 → 谓词结果     有业务规则，仍不含文案
    Check  : 输入 → 判定 + 文案  文案来自真源（verify.sh 的 ok / no）

硬纪律（违反即回滚该步）：

- **原子不返回 PASS/FAIL/WARN/SKIP**，也不含业务文案——判定与文案留在能力层/Check 层。
  依据：一旦 file_exists 知道「缺了算 FAIL」，它就无法被复用来做「先探测再决定」，
  外部接入者也就拼不出自己的 Check（接口纪律 §5.2；本仓 purity_scan / asset_contract
  只回违规列表、判定在上层，是既有正例）。
- 同输入同输出；不写盘、无网络。唯一的**受控副作用**面是 proc（跑子进程 / 跑两遍），
  已在模块 docstring 里显式标注。
- 路径一律 pathlib.Path；**缺席返回 None / 空集合**，不抛异常——「缺席算不算失败」是
  调用方的决定，不是原子的决定。

为什么收敛成一层，而不是让每个扫描器各写一份：verify.sh 的 40 条 check 里大量动作是同一批
纯机器动作（判在场、算摘要、对集合、读 JSON），过去散落在 repo_face / json_doc 与各 check 的
heredoc 里。分散的代价不是「不好看」，而是**同一动作两侧口径不同**（例如忽略面各写一份，
2026-10-03 因此让三处判据同时假红）。收敛在这里之后，新 Check 只按需**组装**这些动作。

导入纪律：本包是**叶子层**。只许依赖 stdlib 与同层的叶子件（repo_face / json_doc /
json_schema / lazy_yaml）；不许反向 import core 的上层模块、scripts、tui、nf（test_atoms 守着）。
"""


# ---------------------------------------------------------------- 懒唤醒与激活登记
#: 已激活的原子名（`"<族>.<函数>"`）。设计意图：原子是**按需唤醒**的——包本身不在导入期拉任何
#: 子模块（PEP 562 的 `__getattr__` 才导入），且每次**真被调用**时登记一次。于是「哪些原子在
#: 生产路径上真的被利用了」从"看代码猜"变成可机读事实（`atoms.woken()`），供判据直接盯死代码。
_WOKEN: "set[str]" = set()
_SUBMODULES = ("code", "fs", "hash", "proc", "sets", "struct", "text")


def _wake(name: str) -> None:
    """登记一次原子激活（由各原子函数在入口调用；开销 = 一次 set.add）。"""
    _WOKEN.add(name)


def woken(clear: bool = False) -> "list[str]":
    """本次进程内已激活的原子名（排序，便于逐字节比对）。

    `clear=True` 时顺带清空登记：长驻进程（守护）在**每请求结束**调用一次，让下一轮请求从零
    开始观测（同一语义见 `daemon.reset_process_caches`——它清的是按路径缓存，这里清的是激活面）。
    """
    got = sorted(_WOKEN)
    if clear:
        _WOKEN.clear()
    return got


def __getattr__(name: str):
    """PEP 562：`atoms.fs` 这类属性访问**首次**才导入子模块（导入期零成本）。"""
    if name in _SUBMODULES:
        import importlib
        mod = importlib.import_module("." + name, __name__)
        globals()[name] = mod
        return mod
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
