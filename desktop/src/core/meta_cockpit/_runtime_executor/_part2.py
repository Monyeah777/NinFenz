"""core.runtime_executor 私有实现分片 2/2（对外只经 core.runtime_executor 门面导入）：eval_node"""

from __future__ import annotations

from ._part1 import (
    NODES,
)


def _criterion_row(c: dict, val, n: int) -> dict:
    dim = c["dimension"]
    if c["primitive"] == "invariant":
        ok = bool(val)
        got = 1.0 if bool(val) else 0.0
        missing = 0 if ok else 1
    elif c.get("unit") == "count":
        if val is None:
            got, ok = 0.0, False
        else:
            got = float(val)
            ok = (
                got <= c["threshold"]
                if c.get("direction") == "lower_better"
                else got >= c["threshold"]
            )
        missing = None
    elif val is None:
        return {"dimension": dim, "value": 0.0, "missing": n, "ok": False}
    else:
        got = float(val)
        missing = round((1 - got) * n)
        ok = got >= c["threshold"] and missing <= c.get("max_missing", 0)
    return {"dimension": dim, "value": got, "missing": missing, "ok": ok}


def eval_node(
    node_id: str, values: dict, n_by_dim: dict, skip: set[str] | None = None
) -> tuple[bool, list[dict]]:
    skip = skip or set()
    out: list[dict] = []
    for c in NODES[node_id]["criteria"]:
        dim = c["dimension"]
        if dim in skip:
            out.append({"dimension": dim, "skipped": True})
            continue
        out.append(_criterion_row(c, values.get(dim), int(n_by_dim.get(dim, 1))))
    return all(r.get("ok", True) for r in out), out
