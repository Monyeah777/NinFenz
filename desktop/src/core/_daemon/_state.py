"""daemon 私有子模块 _state：守护状态文件（NF_HOME/daemon.json）：读/写/权限收紧/停用标记。

门面 core.daemon 按原 API 重新导出；本文件只承载实现，不改变对外面。
"""
from __future__ import annotations

import json
import os
import threading
from pathlib import Path

from ._const import PROTO, STATE_NAME

_STATE_WRITE_LOCK = threading.Lock()



def state_path() -> Path:
    """守护状态文件落点：`<NF_HOME>/daemon.json`（NF_HOME 约定只在 storage 里定义一次）。

    **不提供落点覆盖**（2026-10-17 实测结论）：曾尝试加 `NARRATIVE_FORGE_DAEMON_STATE`
    让并行 worker 各自隔离守护单例，三种粒度（整个 NF_HOME / 只 cache 共享 / 只状态文件）
    **全部与既有测试契约冲突**：
    - 切整个 NF_HOME ⇒ 丢 cache 预热，`quality_depth` 扫描器调用 8→9（判据红）；
    - 只切状态文件 ⇒ `test_daemon` / `test_launcher` / `test_daemon_parity` 里
      **断言 `daemon.json` 位置**的用例直接红（它们自设 NF_HOME 并期望状态就落在里面）。
    ⇒ 守护单例**不可隔离**，并行只能靠「把打守护的模块排到独占串行段」。
    """
    from core import storage
    return Path(storage.default_home()) / STATE_NAME



def read_state() -> Optional[Dict[str, Any]]:
    """读守护状态；文件缺失/不可解析/版本不符 → None（一律按「没有守护」处理）。"""
    from core import atomic_write
    try:
        with _STATE_WRITE_LOCK, atomic_write.lock_file(state_path(), what="守护状态读取"):
            doc = json.loads(atomic_write.read_text(state_path(), encoding="utf-8"))
    except (OSError, ValueError):  # 无状态文件/坏件 ⇒ None（调用方回退直跑）
        return None
    if not isinstance(doc, dict) or doc.get("proto") != PROTO:
        return None
    if not isinstance(doc.get("port"), int) or not doc.get("token"):
        return None
    return doc



def write_state(doc: Dict[str, Any]) -> None:
    """写状态文件（UTF-8 + LF；父目录按需创建）。空表 = 已停用标记。

    **权限**（2026-09-30 补）：状态文件里带**一次性令牌**，而令牌就是本守护的信任边界
    （module docstring：回环不是信任边界）。POSIX 上把它收紧到 `0600`（只给属主读写）——
    否则在多用户主机上，同机另一个用户读到令牌即可连回环口、以属主身份执行命令。
    Windows 上 ACL 随用户目录继承（`chmod` 无对应语义），故只在 posix 分支收紧。

    **并发安全**（2026-10-10 审计 N1，P1）：固定名两段写在 1200 次并发实测中失败 868 次、
    读者 12.9% 撕裂；现统一原子写（唯一临时名 + fsync + `replace` + 短重试）。
    下面再显式收紧一次兜底。
    """
    p = state_path()
    from core import atomic_write
    with _STATE_WRITE_LOCK, atomic_write.lock_file(p, what="守护状态"):
        atomic_write.write_text(p, json.dumps(doc, ensure_ascii=False, sort_keys=True) + "\n")
    _harden_perms(p)



def _harden_perms(path: Path) -> None:
    """POSIX：把含令牌的状态文件收紧到仅属主可读写；Windows 交回 ACL 继承。"""
    if os.name != "posix":
        return
    try:
        os.chmod(path, 0o600)
    except OSError:  # 尽力而为：权限收紧失败不阻断守护（文件系统可能不支持）
        pass



def clear_state() -> None:
    """停用标记：写入空表（不删文件——本仓删除面要过纯度登记，保持零新增 sink）。"""
    write_state({})
