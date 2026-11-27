"""conformance_scan 私有子模块 _memo：只读调用作用域内的四层共享缓存（外层出口即清）。

门面 core.conformance_scan 按原 API 重新导出；本文件只承载实现，不改变对外面。
"""
from __future__ import annotations

import contextlib
from typing import Any, Dict, Optional, Tuple

#: 「一次**只读**扫描内共享语料」的**四层作用域缓存**（`read_memo()` 框定、出口即清；聚合入口都是
#: 纯读 ⇒ 冷却语义与「新起进程」一致）：读文本 / 列目录 / 按模式枚举 / 子树清单。实测一次
#: `evaluate` 打开 7833 次文件而只有 2354 个不同文件（70% 冗余读），并建过 5403 次 `scandir`。
_READ_MEMO: Optional[Dict[str, Any]] = None

_DIR_MEMO: Optional[Dict[Any, Any]] = None       # 键为 ("entries", path) 元组（与 _PAT_MEMO 串行会话隔离）

#: 与读缓存同生命周期的**逐件内容摘要**缓存（键＝文件）：输入面高度重叠，一次调用里每件只算一次。
_DIGEST_MEMO: Optional[Dict[str, bytes]] = None

# : 同生命周期的「按模式枚举」缓存：一次调用内同一 (root, pattern) 只走一遍文件系统（实测 44% 白走）
# 。
_PAT_MEMO: Optional[Dict[Tuple[str, str], Tuple[str, ...]]] = None

#: 同生命周期的「子树文件清单」缓存：键即目录 ⇒ 目录没变清单就一样。
_TREE_MEMO: Optional[Dict[str, Tuple[str, ...]]] = None



@contextlib.contextmanager
def read_memo():
    """框定「共享语料」的作用域（可嵌套；**嵌套＝细化，共享同一份缓存**）。

    冷却契约的边界是**最外层**那次只读调用（如 `regression_score.evaluate`）：出口统一清空，
    下个调用照常重新读盘。嵌套的 `read_memo()`（如 `quality_depth_scan.scan`）过去会另起一份
    空缓存，于是外层刚读过的语料在里面**又读一遍**——实测这样一次 evaluate 白开了上千次文件；
    现在嵌套只是同一只读调用内的细化，缓存共存但不越出最外层边界。

    安全性前提＝「作用域内只读」（本仓既有纪律：写路径在聚合**之后**才发生）。四个调用点
    （regression_score / quality_depth_scan / conformance_report / output_forms）都是纯读聚合入口。
    """
    global _READ_MEMO, _DIR_MEMO, _PAT_MEMO, _TREE_MEMO, _DIGEST_MEMO
    outermost = _READ_MEMO is None
    if outermost:
        _READ_MEMO, _DIR_MEMO, _PAT_MEMO, _TREE_MEMO, _DIGEST_MEMO = {}, {}, {}, {}, {}
    try:
        yield
    finally:
        if outermost:
            _READ_MEMO = _DIR_MEMO = _PAT_MEMO = _TREE_MEMO = _DIGEST_MEMO = None
