"""app/schema/*.schema.json 的加载与本地结构校验（jsonschema 2020-12）。

注意：本地 jsonschema 只做结构面 pre-flight；语义面（引用/拓扑/预算/规则）的
最终权威是 Rust 核心的 validate 类 op。
"""

from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

from jsonschema import Draft202012Validator

from .paths import schema_dir


@lru_cache(maxsize=None)
def schema_names() -> tuple[str, ...]:
    return tuple(sorted(p.name[: -len(".schema.json")] for p in schema_dir().glob("*.schema.json")))


def _file_for(stem: str):
    return schema_dir() / f"{stem}.schema.json"


@lru_cache(maxsize=None)
def load_schema(stem: str) -> dict:
    path = _file_for(stem)
    if not path.is_file():
        raise KeyError(f"没有这个 schema: {stem}（可用: {', '.join(schema_names())}）")
    return json.loads(path.read_text(encoding="utf-8"))


@lru_cache(maxsize=None)
def validator(stem: str) -> Draft202012Validator:
    return Draft202012Validator(load_schema(stem))


def _pointer(parts: Any) -> str:
    out = ""
    for part in parts:
        if isinstance(part, int):
            out += f"[{part}]"
        else:
            out += "/" + str(part)
    return out or "$"


def validate(stem: str, doc: Any) -> list[dict]:
    """返回按 path 排序的结构错误列表 [{path,message}]；空列表 = 通过。"""
    errors = []
    for err in validator(stem).iter_errors(doc):
        errors.append({"path": _pointer(list(err.absolute_path)), "message": err.message})
    errors.sort(key=lambda e: (e["path"], e["message"]))
    return errors


def first_error(stem: str, doc: Any) -> dict | None:
    errors = validate(stem, doc)
    return errors[0] if errors else None
