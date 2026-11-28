"""Generate Kotlin/TypeScript data types from frozen App view contracts.

The schema is the source of truth; generated files are checked in by the caller
and verified by tests, so App/core cannot drift silently.
"""
from __future__ import annotations

from core.research.contracts import SCHEMAS

_TYPES = {"string": "String", "bool": "Boolean", "int": "Int",
          "SlotView[]": "List<SlotView>", "string[]": "List<String>",
          "RecipeRef": "RecipeRef"}
_TS_TYPES = {"string": "string", "bool": "boolean", "int": "number",
             "SlotView[]": "SlotView[]", "string[]": "string[]",
             "RecipeRef": "RecipeRef"}


def _check(name: str, fields: list[tuple[str, str, bool]]) -> None:
    if not name.isidentifier():
        raise ValueError("bad type name: " + name)
    seen = set()
    for field, typ, _optional in fields:
        if not field.isidentifier() or field in seen:
            raise ValueError("bad or duplicate field: " + name + "." + field)
        seen.add(field)
        if typ not in _TYPES:
            raise ValueError("unsupported type: " + typ)


def kotlin(name: str) -> str:
    fields = SCHEMAS[name]
    _check(name, fields)
    lines = ["data class " + name + "("]
    for i, (field, typ, optional) in enumerate(fields):
        comma = "," if i + 1 < len(fields) else ""
        kt = _TYPES[typ] + ("?" if optional else "")
        lines.append(f"    val {field}: {kt}{comma}")
    lines.append(")")
    return "\n".join(lines) + "\n"


def typescript(name: str) -> str:
    fields = SCHEMAS[name]
    _check(name, fields)
    lines = ["export interface " + name + " {"]
    for field, typ, optional in fields:
        lines.append(f"  {field}{'?' if optional else ''}: {_TS_TYPES[typ]};")
    lines.append("}")
    return "\n".join(lines) + "\n"


def all_kotlin() -> str:
    return "\n".join(kotlin(n) for n in SCHEMAS)


def all_typescript() -> str:
    return "\n".join(typescript(n) for n in SCHEMAS)
