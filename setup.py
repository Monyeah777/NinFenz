"""NinFenz wheel 构建钩子：把「仓库根真源」按最小 Python 运行面注入 `ninfenz/` 包内。

为什么需要这个钩子：NF 的真源是仓库根布局（`scripts/nf.py`、`desktop/src/core/`、
`protocol/schema/`），不是 Python 包布局。若把这几件**再提交一份**到
`packaging/pypi/ninfenz/`，就等于制造第二个手写副本，必然漂移（这正是 T1.1 审计里
「多面手写事实」的同型问题）。

做法：`build_py` 在 setuptools 正常拷完包源码之后，把仓库根下列件逐字节拷进
`build/lib/ninfenz/...`（wheel 视角即 `ninfenz/...`）：

- `scripts/nf.py`                      → `ninfenz/scripts/nf.py`
- `desktop/src/core/**`（不含缓存）     → `ninfenz/desktop/src/core/**`
- `protocol/schema/*.json`             → `ninfenz/protocol/schema/*.json`
- `protocol/facts.json`                → `ninfenz/protocol/facts.json`（版本/许可单一真源）

`scripts/check_pypi_package.py` 会在构建后**逐字节对账** wheel 内副本与仓库根原件；
`desktop/tests/test_pypi_package.py` 把这条对账作为常驻判据。
"""
from __future__ import annotations

import shutil
from pathlib import Path

from setuptools import setup
from setuptools.command.build_py import build_py as _build_py

ROOT = Path(__file__).resolve().parent
PKG = "ninfenz"

#: 单件注入（repo 相对路径 = wheel 内相对 ninfenz/ 的路径）
PAYLOAD_FILES = (
    "scripts/nf.py",
    "protocol/facts.json",
)
#: 整树注入（repo 相对目录 = wheel 内相对 ninfenz/ 的目录）
PAYLOAD_TREES = (
    "desktop/src/core",
    "protocol/schema",
    "scripts/nf_parser",
    "scripts/nf_cmds",
)
_SKIP_PARTS = {"__pycache__", ".pytest_cache", ".nf-cache", ".git"}
_SKIP_SUFFIX = {".pyc", ".pyo"}


def _copy_file(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dst)


class BuildPyWithPayload(_build_py):
    """build_py + 真源注入（幂等：每次构建整体覆盖 build/lib 下的目标文件）。"""

    def run(self) -> None:                                  # type: ignore[override]
        super().run()
        target = Path(self.build_lib) / PKG
        for rel in PAYLOAD_FILES:
            src = ROOT / rel
            if not src.is_file():
                raise SystemExit("构建失败：真源缺件 %s（wheel 最小运行面不完整）" % rel)
            _copy_file(src, target / rel)
        for rel_dir in PAYLOAD_TREES:
            base = ROOT / rel_dir
            if not base.is_dir():
                raise SystemExit("构建失败：真源缺目录 %s" % rel_dir)
            for src in sorted(base.rglob("*")):
                if not src.is_file():
                    continue
                if _SKIP_PARTS & set(src.parts) or src.suffix in _SKIP_SUFFIX:
                    continue
                _copy_file(src, target / rel_dir / src.relative_to(base))


setup(cmdclass={"build_py": BuildPyWithPayload})
