"""夹具生成公共件（schema 正反样例 + sample-pack 共用）。"""

from __future__ import annotations

import copy
import json
from pathlib import Path

from nf_app.canonical import canonical_text, sha256_hex


def d(seed: str) -> str:
    """确定性假摘要（只满足 schema 的 64hex 约束，用于结构样例）。"""
    return sha256_hex(seed.encode("utf-8"))


def _write_lf(path: Path, text: str) -> None:
    """写 UTF-8 无 BOM + LF（Windows 上 Path.write_text 默认会转 CRLF，禁止）。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("utf-8"))


def write_json(path: Path, obj: dict) -> None:
    _write_lf(path, json.dumps(obj, ensure_ascii=False, indent=2) + "\n")


def write_canonical(path: Path, obj: dict) -> None:
    _write_lf(path, canonical_text(obj))


def mutate(base: dict, fn) -> dict:
    doc = copy.deepcopy(base)
    fn(doc)
    return doc
