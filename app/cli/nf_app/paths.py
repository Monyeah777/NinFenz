"""仓库路径发现（不写死盘符/用户名；可用 NF_APP_REPO_ROOT 覆盖）。"""

from __future__ import annotations

import os
from pathlib import Path


def repo_root() -> Path:
    env = os.environ.get("NF_APP_REPO_ROOT")
    if env:
        return Path(env).expanduser().resolve()
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "app" / "schema" / "error_codes.json").is_file():
            return parent
    return Path.cwd().resolve()


def app_dir() -> Path:
    return repo_root() / "app"


def schema_dir() -> Path:
    return app_dir() / "schema"


def fixtures_dir() -> Path:
    return app_dir() / "fixtures"


def cli_dir() -> Path:
    return app_dir() / "cli"


def tests_dir() -> Path:
    return app_dir() / "tests"


def limits() -> dict:
    import json

    return json.loads((schema_dir() / "limits.json").read_text(encoding="utf-8"))


def core_candidates(explicit: str | None = None) -> list[Path]:
    """按优先级返回可能的核心可执行文件路径。

    显式声明（--core / NF_APP_CORE）时只认声明路径，不静默回落到仓库内二进制
    （否则"指定一个不存在的核心"会悄悄用别的核心跑，属于假绿）。
    """
    names = ("nf-app-core.exe", "nf-app-core") if os.name == "nt" else ("nf-app-core", "nf-app-core.exe")
    declared = explicit or os.environ.get("NF_APP_CORE")
    if declared:
        path = Path(declared).expanduser()
        return [path / name for name in names] if path.is_dir() else [path]
    target = app_dir() / "core" / "target"
    return [target / profile / name for profile in ("release", "debug") for name in names]
