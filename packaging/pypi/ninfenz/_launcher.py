"""`nf` console script 入口（Python 发行包形态）。

wheel 内的仓库树是**构建时注入**的（见根 `setup.py` 的 `build_py` 钩子）：本模块只负责把
bundled `scripts/nf.py` 当模块加载并转调它的 `cli(argv)` —— 源码树与安装树跑的是**同一份**
`scripts/nf.py`，不存在第二份 CLI 副本。

为什么不用 `runpy.run_path(..., run_name="__main__")`：那会走到 nf.py 末尾的
`sys.exit(cli(sys.argv[1:]))`，退出码/异常路径要再兜一层；直接调 `cli(argv)` 与其
`__main__` 分支等价的返回值语义，且不污染模块命名空间。
"""
from __future__ import annotations

import importlib.util
import os
import sys
from typing import Any, Optional


def _payload_root() -> str:
    return os.path.dirname(os.path.abspath(__file__))


def _load_bundled_cli() -> Any:
    path = os.path.join(_payload_root(), "scripts", "nf.py")
    if not os.path.isfile(path):
        sys.stderr.write("nf: 发行包内缺 scripts/nf.py（构建钩子未注入？请重装/重构建）\n")
        return None
    spec = importlib.util.spec_from_file_location("ninfenz._bundled_nf_cli", path)
    if spec is None or spec.loader is None:
        sys.stderr.write("nf: 无法加载发行包内的 scripts/nf.py（模块规格为空）\n")
        return None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def main(argv: Optional[list] = None) -> int:
    """console script 入口：参数与 `nf ...` 完全一致，返回退出码。"""
    args = list(sys.argv[1:] if argv is None else argv)
    module = _load_bundled_cli()
    if module is None:
        return 2
    sys.argv = ["nf"] + args
    return int(module.cli(args))


if __name__ == "__main__":                                    # 直接 python -m 时也走同一入口
    raise SystemExit(main())
