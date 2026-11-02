"""Adapter from the cockpit's Draft 2020-12 call sites to core.json_schema."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

from core import json_schema

try:
    import jsonschema as _jsonschema
except ImportError:  # pragma: no cover - exercised in stdlib-only deployments
    _jsonschema = None


@dataclass(frozen=True)
class ValidationError:
    message: str


class Draft202012Validator:
    """Small compatibility surface used by the cockpit's schema contracts."""

    def __init__(self, schema: dict[str, Any]):
        self.schema = schema
        self._delegate = (
            _jsonschema.Draft202012Validator(schema) if _jsonschema is not None else None
        )

    def iter_errors(self, instance: Any) -> Iterator[ValidationError]:
        if self._delegate is not None:
            for item in self._delegate.iter_errors(instance):
                yield ValidationError(item.message)
            return
        unsupported: list[str] = []
        errors = json_schema.json_schema_check(instance, self.schema, unsupported=unsupported)
        for item in errors:
            yield ValidationError(item)
        for item in unsupported:
            yield ValidationError(
                f"不支持的 JSON Schema 关键字 {item}（修复指引：改用本仓支持的可判定子集）"
            )
