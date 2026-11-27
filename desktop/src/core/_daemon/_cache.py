"""daemon 私有子模块 _cache：热进程层：响应缓存、监听代际、常驻语料同步、源码指纹重载、命令执行。

门面 core.daemon 按原 API 重新导出；本文件只承载实现，不改变对外面。
"""
from __future__ import annotations

import os
import threading
from typing import Any, Dict, Optional

from core import response_cache as _rc

from ._cli import _cli_module
from ._const import RESIDENT_ENV_OFF



def reset_process_caches() -> None:
    """清空**按路径/根键**的进程缓存（内容键缓存保留，见模块 docstring 的「新鲜度」）。

    只在守护进程里逐请求调用——让热进程与「新起进程」看到同一份仓库事实。
    """
    try:
        from core import pack_combo
        pack_combo.cache_clear()
    except Exception:                                    # noqa: BLE001 - 缓存清理不得影响命令
        pass  # best-effort 显式忽略（清理/探测失败不影响主流程）
    try:
        from core import registry_loader
        registry_loader.load_registry.cache_clear()
    except Exception:                                    # noqa: BLE001
        pass  # best-effort 显式忽略（清理/探测失败不影响主流程）
    try:
        from core import asset_contract
        asset_contract.clear_repo_files_cache()
    except Exception:                                    # noqa: BLE001
        pass  # best-effort 显式忽略（清理/探测失败不影响主流程）



#: CLI 模块缓存（含源码指纹）：守护最怕「代码改了还在跑旧逻辑」——见 `_sync_code`。
_CLI_CACHE: Dict[str, Any] = {}


_CACHE_STATS = _rc.STATS

#: 当前监听件（`serve_forever(watch=True)` 装；单测可注入假件）。
_WATCHER: Optional[Any] = None

#: `_WATCHER` 的**唯一写入口**（2026-10-10 审计 N8，P2）：此前 `session_watch._install` 直接写
#: `daemon._WATCHER`——跨模块可变全局没有所有权，谁都能改、没人能断言。现在写只走 `set_watcher`
#: （进程内 mutex 保证换手原子）；读仍无锁（CPython 引用读写原子，换手期间读到旧/新都是完整
#: 对象，健康判据由 `_watch_generation` 的 `healthy` 兜住）。
_WATCH_LOCK = threading.Lock()



def set_watcher(watcher: Optional[Any]) -> None:
    """登记/注销本进程的树代际来源（**唯一写入口**）。"""
    global _WATCHER
    with _WATCH_LOCK:
        _WATCHER = watcher



def _watch_generation() -> Optional[int]:
    """当前「树代际」；**None ＝ 不可用**（没有监听件 / 不健康）→ 一律不缓存、不命中。"""
    w = _WATCHER
    if w is None or not getattr(w, "healthy", False):
        return None
    return int(w.generation)



def _sync_resident(root: Path) -> None:
    """按监听给出的**确知变更**维护常驻语料层（`conformance_scan._RESIDENT`）。

    fail-closed 三条：① 没有监听 / 监听不健康 → 常驻层整批作废且不安装；② 监听说不清变了什么
    （缓冲溢出、路径解不出、只跳代际）→ 整批作废重建；③ 只有「确知哪些路径变了」才做精确失效。

    依据（2026-09-29 实测）：不加这一层，改一个文件之后守护的第一条重命令要 **1.6–2.0 s**
    （整棵语料重新枚举 + 重读，而真正变了的只有一件）；加上之后只失效被改的那几件。
    """
    from core import conformance_scan as csc
    if os.environ.get(RESIDENT_ENV_OFF):
        if csc.resident_active():        # 显式关闭：整批作废且不再收录（诊断/对照用）
            csc.clear_resident()
        return
    w = _WATCHER
    if w is None or not getattr(w, "healthy", False):
        if csc.resident_active():
            csc.clear_resident()
        return
    if not csc.resident_active():
        csc.install_resident(root)
    take = getattr(w, "take_changes", None)
    if take is None:                     # 不提供「确知变更面」的监听件 → 当说不清（整批作废）
        csc.clear_resident()
        csc.install_resident(root)
        return
    paths, unknown = take()
    if unknown:
        csc.clear_resident()
        csc.install_resident(root)
    elif paths:
        csc.drop_resident(paths)



def cache_stats() -> Dict[str, Any]:
    """响应缓存观测面（供 `nf daemon status` 与单测）。"""
    gen = _watch_generation()
    from core import conformance_scan as _csc
    from core import disk_cache as _dc
    return {"enabled": gen is not None, "generation": gen,
            "entries": _rc.entries(), **dict(_CACHE_STATS),
            # 持久缓存的写失败观测（审计 N7）：缓存写不进是降级，须可判别而不是静默吞掉。
            "disk_cache": _dc.store_failures(),
            # 常驻语料层的规模也一并报出来：它是「不重读」的账本，出问题时第一个要看的就是它。
            "resident": _csc.resident_stats()}



def reset_response_cache() -> None:
    """清空响应缓存（监听件报溢出/不可用时调用——宁可全废，不可错答）。"""
    _rc.clear()



def _load_cli(root: Path):
    mod = _CLI_CACHE.get("mod")
    if mod is None:
        mod = _cli_module(root)
        _CLI_CACHE["mod"] = mod
    return mod
