"""原子组合代数：seq / par / choice / identity + 规范化签名。"""

from __future__ import annotations

import json

from . import live_selector as ls


def atom(aid: str) -> dict:
    return {"op": "atom", "id": aid}


def seq(*parts: dict) -> dict:
    return {"op": "seq", "parts": list(parts)}


def par(*parts: dict) -> dict:
    return {"op": "par", "parts": list(parts)}


def choice(*parts: dict) -> dict:
    return {"op": "choice", "parts": list(parts)}


IDENTITY = {"op": "identity"}
ZERO = {"op": "zero"}
EMPTY: dict = {"pre": [], "adds": [], "removes": []}


def _canon(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def _compose(left: dict, right: dict) -> dict:
    pre = set(left["pre"]) | (set(right["pre"]) - set(left["adds"]))
    adds = (set(left["adds"]) | set(right["adds"])) - set(right["removes"])
    removes = set(left["removes"]) | set(right["removes"])
    return {"pre": sorted(pre), "adds": sorted(adds), "removes": sorted(removes)}


def _dedupe(sigs: list[dict]) -> list[dict]:
    d = {_canon(s): s for s in sigs}
    return [d[k] for k in sorted(d)]


def _flatten(node: dict, op: str) -> list[dict]:
    if node["op"] == op:
        out = []
        for p in node["parts"]:
            out += _flatten(p, op)
        return out
    return [node]


def _distribute_seq(parts: list[dict]) -> dict:
    for i, p in enumerate(parts):
        if p["op"] == "choice":
            return choice(*[_distribute_seq(parts[:i] + [b] + parts[i + 1 :]) for b in p["parts"]])
    return seq(*parts)


def _atom_signature(node: dict) -> dict:
    c = ls.CONTRACTS[node["id"]]
    return {
        "pre": sorted(c["requires"]),
        "adds": sorted(c["adds"]),
        "removes": sorted(c["removes"]),
    }


def _check_par_sigs(sigs: list[dict]) -> None:
    if any("choice" in s for s in sigs):
        raise ValueError("parallel over choice")
    for i, a in enumerate(sigs):
        wa = set(a["adds"]) | set(a["removes"])
        for b in sigs[i + 1 :]:
            wb = set(b["adds"]) | set(b["removes"])
            if wa & wb:
                raise ValueError("parallel write conflict")


def _union_sig(sigs: list[dict]) -> dict:
    return {
        "pre": sorted(set().union(*[set(x["pre"]) for x in sigs])) if sigs else [],
        "adds": sorted(set().union(*[set(x["adds"]) for x in sigs])) if sigs else [],
        "removes": sorted(set().union(*[set(x["removes"]) for x in sigs])) if sigs else [],
    }


def _par_signature(parts: list[dict]) -> dict:
    if not parts:
        return signature(IDENTITY)
    if len(parts) == 1:
        return signature(parts[0])
    sigs = [signature(p) for p in parts]
    if any("zero" in s for s in sigs):
        return {"zero": True}
    _check_par_sigs(sigs)
    return _union_sig(sigs)


def _seq_signature(parts: list[dict]) -> dict:
    branches = [EMPTY]
    for p in parts:
        s = signature(p)
        if "zero" in s:
            return {"zero": True}
        alts = s.get("choice", [s])
        branches = _dedupe([_compose(b, a) for b in branches for a in alts])
    return branches[0] if len(branches) == 1 else {"choice": branches}


def _choice_signature(parts: list[dict]) -> dict:
    sigs = []
    for p in parts:
        s = signature(p)
        if "zero" in s:
            continue
        sigs.extend(s.get("choice", [s]))
    sigs = _dedupe(sigs)
    if not sigs:
        return {"zero": True}
    return sigs[0] if len(sigs) == 1 else {"choice": sigs}


_NODE_HANDLERS = {
    "par": _par_signature,
    "seq": _seq_signature,
    "choice": _choice_signature,
}


def signature(node: dict) -> dict:
    op = node["op"]
    if op == "atom":
        return _atom_signature(node)
    if op == "identity":
        return {"pre": [], "adds": [], "removes": []}
    if op == "zero":
        return {"zero": True}

    raw = _flatten(node, op)
    parts = raw if op == "choice" else [p for p in raw if p["op"] != "identity"]
    handler = _NODE_HANDLERS.get(op)
    if handler is None:
        raise ValueError(f"unknown op: {op}")
    return handler(parts)


def equivalent(a: dict, b: dict) -> bool:
    try:
        return _canon(signature(a)) == _canon(signature(b))
    except ValueError:
        return False
