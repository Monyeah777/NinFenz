"""daemon 私有子模块 _cli：CLI 真源加载（按路径 import scripts/nf.py）。

门面 core.daemon 按原 API 重新导出；本文件只承载实现，不改变对外面。
"""
from __future__ import annotations

from pathlib import Path



def _cli_module(root: Path):
    """加载 CLI 真源 `scripts/nf.py`（与单测同一手法：按路径 import，不走包导入）。"""
    import importlib.util
    spec = importlib.util.spec_from_file_location("nfcli_daemon", Path(root) / "scripts" / "nf.py")
    if spec is None:
        raise RuntimeError("scripts/nf.py 路径无法构造加载规格（修复指引：确认 --root 指向 NF 仓库"
            "根，且 scripts/nf.py 在场）")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)          # type: ignore[union-attr]
    return mod
