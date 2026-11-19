"""Row/refinement-typed template checking (typechecker-zoo idea, small core).

A template is an open/closed row of named slots. Each slot is required or
optional and may carry length/pattern refinements. Errors carry a path so a UI
can attach them to the exact slot.
"""
from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

SCHEMA = "nf-typed-template/1"


@dataclass(frozen=True)
class SlotType:
    id: str
    required: bool = True
    kind: str = "text"
    min_len: int = 0
    max_len: int | None = None
    pattern: str | None = None

    def check(self, value: Any, path: str) -> list[dict[str, Any]]:
        if self.kind == "list":
            if not isinstance(value, list):
                return [{"code": "TYPE", "path": path, "message": "expected list"}]
            return []
        if not isinstance(value, str):
            return [{"code": "TYPE", "path": path, "message": "expected text"}]
        out = []
        n = len(value.strip())
        if n < self.min_len:
            out.append({"code": "MIN_LEN", "path": path, "message": f"{n} < {self.min_len}"})
        if self.max_len is not None and n > self.max_len:
            out.append({"code": "MAX_LEN", "path": path, "message": f"{n} > {self.max_len}"})
        if self.pattern and not re.search(self.pattern, value):
            out.append({"code": "PATTERN", "path": path, "message": "pattern mismatch"})
        return out


@dataclass(frozen=True)
class RowType:
    fields: Mapping[str, SlotType]
    open: bool = True


@dataclass
class CheckResult:
    valid: bool
    diagnostics: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"schema": SCHEMA, "valid": self.valid, "diagnostics": self.diagnostics}


def check_record(record: Mapping[str, Any], row: RowType) -> CheckResult:
    diags: list[dict[str, Any]] = []
    for key, spec in row.fields.items():
        if key not in record:
            if spec.required:
                diags.append({"code": "MISSING", "path": key, "message": "required"})
            continue
        diags.extend(spec.check(record[key], key))
    if not row.open:
        for key in sorted(set(record) - set(row.fields)):
            diags.append({"code": "EXTRA", "path": key, "message": "unexpected slot"})
    return CheckResult(not diags, diags)
