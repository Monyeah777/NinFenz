"""Bounded counterexample checks for template/assignment invariants (Holey idea).

No SMT: small explicit domains are enumerated, then the concrete checker is run.
`passed` means the checker rejected every generated counterexample.
"""
from __future__ import annotations

from typing import Any

from core.research.typed_template import RowType, SlotType, check_record

SCHEMA = "nf-property/1"


def check_max_len(max_len: int = 20) -> dict[str, Any]:
    value = "a" * (max_len + 1)
    row = RowType({"x": SlotType("x", max_len=max_len)}, open=True)
    diags = check_record({"x": value}, row).diagnostics
    ok = any(d["code"] == "MAX_LEN" for d in diags)
    return {"schema": SCHEMA, "property": "max_len",
            "status": "passed" if ok else "counterexample",
            "counterexample": {"length": len(value)}, "checks": diags}


def check_required() -> dict[str, Any]:
    row = RowType({"x": SlotType("x", required=True)}, open=True)
    diags = check_record({}, row).diagnostics
    ok = any(d["code"] == "MISSING" for d in diags)
    return {"schema": SCHEMA, "property": "required",
            "status": "passed" if ok else "counterexample",
            "counterexample": {}, "checks": diags}


def check_closed_row() -> dict[str, Any]:
    row = RowType({"x": SlotType("x")}, open=False)
    diags = check_record({"x": "v", "extra": "v"}, row).diagnostics
    ok = any(d["code"] == "EXTRA" for d in diags)
    return {"schema": SCHEMA, "property": "closed_row",
            "status": "passed" if ok else "counterexample",
            "counterexample": {"extra": "v"}, "checks": diags}
