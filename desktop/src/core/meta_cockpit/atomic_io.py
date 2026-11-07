"""Compatibility wrapper around the repository's atomic writer."""

from __future__ import annotations

from pathlib import Path

from core import atomic_write


def write_text(path: str | Path, text: str) -> None:
    atomic_write.write_text(path, text)
