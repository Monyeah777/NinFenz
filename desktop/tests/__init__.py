"""tests 包：套件级隔离（P1：单模块跑与全量跑必须看到同一初始态）。

背景（2026-10-17 实测）：`check12` 全量跑绿，但 `test_launcher` / `test_watch` **单模块跑会红**——
它们的判据依赖「守护不在跑」这个**进程外部状态**，而机器上可能留着上一轮测试/别的会话拉起的守护。
同一根因正是并行与分片「失败集合逐轮变化」的来源：守护是每 `NF_HOME` 一个的进程单例，
测试之间通过它共享了状态。

做法（最小侵入）：套件导入时若 `NARRATIVE_FORGE_HOME` 未指定，就指到**套件私有临时目录**；
退出时 best-effort 停掉该目录下的守护并删目录。于是：

1. 用例永远看不到用户真实的 `~/.NinFenz`（不会污染、也不会被它污染）；
2. 任何用例拉起的守护都落在临时 home，不会在机器上**泄漏进程**；
3. 单模块跑、全量跑、并行跑看到同一初始态——这是后续分片/并行的前提。

显式设置 `NARRATIVE_FORGE_HOME` 的用例（自己管隔离与还原的）**不受影响**：本文件只在
「未指定」时兜底，不覆盖、不还原别人的设置。
"""
import atexit
import os
import shutil
import tempfile

_ORIGINAL_HOME = os.environ.get("NARRATIVE_FORGE_HOME")
_SESSION_HOME = None

if _ORIGINAL_HOME is None:
    _SESSION_HOME = tempfile.mkdtemp(prefix="nf_tests_home_")
    os.environ["NARRATIVE_FORGE_HOME"] = _SESSION_HOME


def _cleanup() -> None:
    """退出时停掉套件内拉起的守护并删临时 home（best-effort，绝不掩盖测试结论）。"""
    global _SESSION_HOME
    if _SESSION_HOME is None:
        return
    home, _SESSION_HOME = _SESSION_HOME, None
    os.environ["NARRATIVE_FORGE_HOME"] = home
    try:
        import sys
        from pathlib import Path
        src = str(Path(__file__).resolve().parent.parent / "src")
        if src not in sys.path:
            sys.path.insert(0, src)
        from core import daemon as dm
        if dm.ping(timeout=1.0):
            dm.stop()
    except Exception:                     # noqa: BLE001 - 清理失败不该让闸门变红
        pass
    finally:
        shutil.rmtree(home, ignore_errors=True)


if _SESSION_HOME is not None:
    atexit.register(_cleanup)
