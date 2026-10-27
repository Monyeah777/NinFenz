"""ParserCtx：只读构建上下文。"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ParserCtx:
    root: str
    version: str
    epilog: str
    os: Any
