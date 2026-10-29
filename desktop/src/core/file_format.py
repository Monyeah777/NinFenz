"""Fail-closed validation for local file extensions that NF accepts.

ASVS V5.2.2 requires the declared extension and the content to agree before a
file is processed. Text formats have no universal magic bytes, so this module
combines cheap signature checks with the same strict parsers used by the
runtime. Unknown extensions are not part of the accepted local file surface.
"""
from __future__ import annotations

import csv
import io
import tomllib
from collections.abc import Callable
from pathlib import Path
from typing import NoReturn
from xml.parsers import expat

from core import json_doc

_WASM_MAGIC = b"\x00asm"
_WASM_VERSIONS = {
    b"\x01\x00\x00\x00",  # WebAssembly core 1.0
    b"\x0d\x00\x01\x00",  # WebAssembly component model
}
_XML_DTD = (b"<!doctype", b"<!entity")
_GRAPHML_NS = "http://graphml.graphdrawing.org/xmlns"


def _invalid(source: str, detail: str, cause: Exception | None = None) -> NoReturn:
    raise ValueError(
        f"{source}: {detail}"
        "（修复指引：将文件转换为声明扩展名对应的格式，或修正扩展名后重试）"
    ) from cause


def _decode_utf8(raw: bytes, source: str) -> str:
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        _invalid(source, "内容不是有效 UTF-8", exc)
    if "\x00" in text:
        _invalid(source, "文本内容含 NUL 字节")
    return text


def _validate_json(raw: bytes, source: str) -> None:
    text = _decode_utf8(raw, source)
    try:
        json_doc.loads(text, None, what=source)
    except ValueError as exc:
        _invalid(source, "扩展名为 .json，但内容不是合法 JSON", exc)


def _validate_jsonl(raw: bytes, source: str) -> None:
    text = _decode_utf8(raw, source)
    for line_no, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            continue
        try:
            json_doc.loads(line, None, what=f"{source}:{line_no}")
        except ValueError as exc:
            _invalid(f"{source}:{line_no}", "扩展名为 .jsonl，但该行不是合法 JSON", exc)


def _validate_toml(raw: bytes, source: str) -> None:
    text = _decode_utf8(raw, source)
    try:
        tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        _invalid(source, "扩展名为 .toml，但内容不是合法 TOML", exc)


def _validate_yaml(raw: bytes, source: str) -> None:
    from core import conformance_scan

    text = _decode_utf8(raw, source)
    try:
        conformance_scan.load_yaml(text)
    except Exception as exc:
        _invalid(source, "扩展名为 YAML，但内容不是合法 YAML", exc)


def _validate_graphml(raw: bytes, source: str) -> None:
    lowered = raw.lower()
    if any(marker in lowered for marker in _XML_DTD):
        _invalid(source, "GraphML 不允许 DTD 或实体声明")
    parser = expat.ParserCreate(namespace_separator=" ")
    root: list[str] = []

    def start(name: str, _attrs: dict[str, str]) -> None:
        if not root:
            root.append(name)

    def reject_entity(*_args: object) -> int:
        return 0

    parser.StartElementHandler = start
    parser.EntityDeclHandler = reject_entity
    parser.ExternalEntityRefHandler = reject_entity
    try:
        parser.Parse(raw, True)
    except (expat.ExpatError, ValueError) as exc:
        _invalid(source, "扩展名为 .graphml，但内容不是合法 XML", exc)
    if not root or root[0] != f"{_GRAPHML_NS} graphml":
        _invalid(source, "XML 根元素不是 GraphML 命名空间下的 graphml")


def _validate_csv(raw: bytes, source: str) -> None:
    text = _decode_utf8(raw, source)
    try:
        list(csv.reader(io.StringIO(text), strict=True))
    except csv.Error as exc:
        _invalid(source, "扩展名为 .csv，但内容不是合法 CSV", exc)


def _validate_text(raw: bytes, source: str) -> None:
    _decode_utf8(raw, source)


def _validate_wasm(raw: bytes, source: str) -> None:
    if len(raw) < 8 or raw[:4] != _WASM_MAGIC or raw[4:8] not in _WASM_VERSIONS:
        _invalid(source, ".wasm magic/version 与扩展名不匹配")


_VALIDATORS: dict[str, Callable[[bytes, str], None]] = {
    ".json": _validate_json,
    ".jsonl": _validate_jsonl,
    ".toml": _validate_toml,
    ".yaml": _validate_yaml,
    ".yml": _validate_yaml,
    ".graphml": _validate_graphml,
    ".xml": _validate_graphml,
    ".csv": _validate_csv,
    ".md": _validate_text,
    ".markdown": _validate_text,
    ".txt": _validate_text,
    ".mmd": _validate_text,
    ".wasm": _validate_wasm,
}

SUPPORTED_SUFFIXES = frozenset(_VALIDATORS)


def validate_bytes(suffix: str, raw: bytes, source: str = "<bytes>") -> None:
    """Reject files whose extension is unsupported or disagrees with content."""
    normalized = str(suffix).lower()
    validator = _VALIDATORS.get(normalized)
    if validator is None:
        _invalid(source, f"不接受的本地文件扩展名 {normalized or '<none>'}")
    validator(bytes(raw), source)


def validate_file(path: str | Path, max_bytes: int | None = None) -> None:
    """Validate one local file by extension and bounded content."""
    target = Path(path)
    raw = target.read_bytes()
    if max_bytes is not None and len(raw) > int(max_bytes):
        _invalid(str(target), f"文件超过上限 {int(max_bytes)} 字节")
    validate_bytes(target.suffix, raw, str(target))


def decode_validated_text(suffix: str, raw: bytes, source: str = "<bytes>") -> str:
    """Validate one repository text file and return normalized UTF-8 text."""
    validate_bytes(suffix, raw, source)
    return raw.decode("utf-8").replace("\r\n", "\n").replace("\r", "\n")


__all__ = [
    "SUPPORTED_SUFFIXES",
    "decode_validated_text",
    "validate_bytes",
    "validate_file",
]
