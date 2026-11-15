"""nf-canonical/1 与摘要（CONTRACT §2）。

canonical bytes = UTF-8(json.dumps(value, ensure_ascii=False, sort_keys=True,
separators=(",", ":"), allow_nan=False))；禁浮点、禁非字符串键。
digest = sha256(canonical_bytes) 的 64 位小写十六进制。

本模块是 Python 侧独立实现（oracle），不依赖 Rust 核心；测试用它和核心对账。
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

MAX_JSON_DEPTH = 64


class CanonicalError(ValueError):
    """值不可 canonical（浮点/非字符串键/超深/非法类型）。"""


class JsonParseError(ValueError):
    """输入 JSON 非法（语法/重复键/NaN/超深）。"""


def _check_value(value: Any, depth: int, path: str) -> None:
    if depth > MAX_JSON_DEPTH:
        raise CanonicalError(f"JSON 深度超过 {MAX_JSON_DEPTH}: {path}")
    if value is None or isinstance(value, bool):
        return
    if isinstance(value, int):
        return
    if isinstance(value, float):
        raise CanonicalError(f"禁止浮点（canonical 只允许整数）: {path}")
    if isinstance(value, str):
        return
    if isinstance(value, (list, tuple)):
        for i, item in enumerate(value):
            _check_value(item, depth + 1, f"{path}/{i}")
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise CanonicalError(f"对象键必须是字符串: {path}/{key!r}")
            _check_value(item, depth + 1, f"{path}/{key}")
        return
    raise CanonicalError(f"不支持的类型 {type(value).__name__}: {path}")


def canonical_bytes(value: Any) -> bytes:
    _check_value(value, 0, "")
    try:
        text = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:  # pragma: no cover - 已由 _check_value 拦住
        raise CanonicalError(str(exc)) from exc
    return text.encode("utf-8")


def canonical_text(value: Any) -> str:
    return canonical_bytes(value).decode("utf-8")


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def digest(value: Any) -> str:
    return sha256_hex(canonical_bytes(value))


def digest_excluding(value: dict, exclude: list[str] | tuple[str, ...] = ()) -> str:
    """剔除顶层字段后的 canonical digest（CONTRACT §7 摘要排除）。"""
    if not isinstance(value, dict):
        raise CanonicalError("digest_excluding 只接受对象")
    dropped = set(exclude) | {"x-digest-exclude"}
    declared = value.get("x-digest-exclude")
    if isinstance(declared, list):
        dropped |= {str(x) for x in declared}
    body = {k: v for k, v in value.items() if k not in dropped}
    return digest(body)


def _reject_float(text: str) -> Any:
    raise JsonParseError(f"禁止浮点数值（canonical 只允许整数）: {text}")


def _reject_constant(text: str) -> Any:
    raise JsonParseError(f"禁止 NaN/Infinity: {text}")


def _pairs_hook(pairs: list) -> dict:
    seen: set = set()
    for key, _ in pairs:
        if key in seen:
            raise JsonParseError(f"重复键: {key}")
        seen.add(key)
    return dict(pairs)


def loads_strict(data: bytes | str, *, max_depth: int = MAX_JSON_DEPTH) -> Any:
    """严格解析 JSON：UTF-8（禁 BOM）、禁重复键、禁 float/NaN、限深度。"""
    if isinstance(data, bytes):
        if data.startswith(b"\xef\xbb\xbf"):
            raise JsonParseError("禁止 UTF-8 BOM")
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise JsonParseError(f"非 UTF-8 输入: {exc}") from exc
    else:
        text = data
    try:
        value = json.loads(
            text,
            object_pairs_hook=_pairs_hook,
            parse_float=_reject_float,
            parse_constant=_reject_constant,
        )
    except RecursionError as exc:
        raise JsonParseError(f"JSON 深度超过上限 {max_depth}") from exc
    except json.JSONDecodeError as exc:
        raise JsonParseError(f"JSON 语法错误: {exc}") from exc
    if _depth(value) > max_depth:
        raise JsonParseError(f"JSON 深度超过上限 {max_depth}")
    return value


def _depth(value: Any) -> int:
    if isinstance(value, dict):
        return 1 + max((_depth(v) for v in value.values()), default=0)
    if isinstance(value, list):
        return 1 + max((_depth(v) for v in value), default=0)
    return 1
