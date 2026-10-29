"""Bounded JSON reads for cockpit assets and untrusted runtime inputs."""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

from core import json_doc


def load(path: str | Path, expect: Any = dict, *, what: str = "") -> Any:
    return json_doc.load(path, expect, what=what)


def loads(text: str, expect: Any = dict, *, what: str = "JSON 文本") -> Any:
    return json_doc.loads(text, expect, what=what)


def load_bytes(data: bytes, expect: Any = dict, *, what: str = "JSON 字节") -> Any:
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError(f"{what} 不是 UTF-8（修复指引：重新导出为 UTF-8 JSON）") from exc
    return loads(text, expect, what=what)


def roundtrip(value: Any) -> Any:
    """Return a detached JSON-shaped copy without an unguarded JSON read site."""
    return copy.deepcopy(value)
