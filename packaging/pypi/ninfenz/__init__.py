"""NinFenz Python 发行包（`pip install ninfenz`）的入口元数据。

**版本不在这里手写**：仓库单一真源是 `protocol/facts.json` 的 `release.cli_version`
（Wave 2 起由 `scripts/nf_facts.py` 生成，npm 包 / 站点 / CI 同读它）。本模块在**安装后**
从随包分发的 `protocol/facts.json` 读取 `__version__`；构建期（wheel METADATA）的
`pyproject.toml [project].version` 是声明位，由 `nf facts --check` 跨源不变量、
`scripts/check_pypi_package.py` 与 `desktop/tests/test_pypi_package.py` 三层钉死与真源一致。

路径回退说明：构建时本文件在源码树 `packaging/pypi/ninfenz/` 下（尚未注入 payload），
故依次尝试「同目录 protocol/facts.json」（安装后形态）与「../../../protocol/facts.json」
（源码树形态）。两种形态都读同一份文本，不产生第二个真源。
"""
from __future__ import annotations

import json
import os

__all__ = ["__version__"]


def _read_version() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    candidates = (
        os.path.join(here, "protocol", "facts.json"),
        os.path.join(here, os.pardir, os.pardir, os.pardir, "protocol", "facts.json"),
    )
    for path in candidates:
        try:
            with open(path, encoding="utf-8") as fh:
                version = (json.load(fh).get("release") or {}).get("cli_version")
        except (OSError, ValueError, TypeError):
            continue
        if version:
            return str(version)
    return "0.0.0"


__version__ = _read_version()
