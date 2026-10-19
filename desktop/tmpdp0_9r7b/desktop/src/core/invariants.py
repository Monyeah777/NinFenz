"""具名纯函数谓词的不变式登记册（机制借鉴 vivera formal-invariants.mjs:1-77 的**形式**）。

只提供机制：把不变式登记成**具名纯函数**并统一求值（每条返回 (ok, detail)），
不在此编造 NF 的 I1-I5 具体语义——具体条目在接线波次按既有协议件填入。
"""
from __future__ import annotations

from typing import Any, Callable, Dict, List, Tuple

Predicate = Callable[[Dict[str, Any]], Tuple[bool, str]]

_REGISTRY: Dict[str, Predicate] = {}


def register(name: str, fn: Predicate) -> None:
    """登记一条具名不变式（名重复即 raise，防静默覆盖）。"""
    if name in _REGISTRY:
        raise ValueError("不变式名重复：%s（修复指引：换名或复用既有条目）" % name)
    _REGISTRY[name] = fn


def registered() -> List[str]:
    return sorted(_REGISTRY)


def evaluate(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """逐条求值 → {ok, results:[{name, ok, detail}]}；任一失败即整体 ok=False。"""
    results = []
    for name in registered():
        try:
            ok, detail = _REGISTRY[name](ctx)
        except Exception as exc:                      # 谓词异常 = 该条不通过（不静默）
            ok, detail = False, "谓词异常：%s" % exc
        results.append({"name": name, "ok": bool(ok), "detail": detail})
    return {"ok": all(r["ok"] for r in results), "results": results}
