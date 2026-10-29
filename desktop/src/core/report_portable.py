"""Canonicalize checkout-specific paths before sealing machine reports."""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any


def portable(value: Any, root: str) -> Any:
    """Remove checkout-specific absolute roots from report values."""
    absolute = str(Path(root).resolve())
    variants = {absolute, os.path.abspath(root), os.path.realpath(root)}
    variants = tuple(
        candidate
        for item in variants
        for candidate in (
            item,
            item.replace("\\", "/"),
            item.replace("/", "\\"),
            item.replace("\\", "\\\\"),
        )
        if candidate
    )
    variants = tuple(sorted(variants, key=len, reverse=True))
    if isinstance(value, str):
        value = re.sub(r"(?<![A-Za-z0-9])(?:/(?:private/)?tmp/|"
                       r"/(?:private/)?var/folders/[^/]+/[^/]+/T/)[^/]+", "<root>", value)
        value = re.sub(
            r"(?i)(?<![A-Za-z0-9])[A-Z]:[\\/]{1,2}"
            r"(?:[^\\/\s\"']+[\\/]{1,2})*Temp[\\/]{1,2}[^\\/\s\"']+",
            "<root>",
            value,
        )
        for token in variants:
            value = value.replace(token, "<root>")
        return value
    if isinstance(value, list):
        return [portable(item, root) for item in value]
    if isinstance(value, dict):
        return {key: portable(item, root) for key, item in value.items()}
    return value


__all__ = ["portable"]
