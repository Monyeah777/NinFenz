"""NFA-L/R 规则层（P-A1）：JSON 事实 + 规则 → 定点推导，带 fuel 计量。

设计（沿用 NFA-L/1 的 JSON 风格，不发明新文本语法）：
  - 事实：{"pred": "edge", "args": ["a", "b"]}（**基**原子）；
  - 规则：{"head": {...}, "body": [{...}, {"guard": ["?X", "!=", "?Y"]}]}；
  - 变量：以 ? 开头的字符串（显式，避免与字面量混淆）；
  - fuel：**每完成一次规则实例化（body 全部匹配成功）记 1**；超限即停并如实报
    FUEL_EXHAUSTED（fail-closed：保留已达部分并标状态，绝不静默截断）。

纪律：同输入同输出（输出全排序）；纯标准库；只读。
"""
from __future__ import annotations

from typing import Any, Set

SCHEMA = "nf-nfal-rules/1"
GUARD_OPS = ("!=", "==", "<", "<=", ">", ">=")
#: 算子表（避免六分支链把圈复杂度顶上去）。
_OPS = {"!=": lambda a, b: a != b, "==": lambda a, b: a == b,
        "<": lambda a, b: a < b, "<=": lambda a, b: a <= b,
        ">": lambda a, b: a > b, ">=": lambda a, b: a >= b}
DEFAULT_FUEL = 100000


def is_var(x: Any) -> bool:
    """变量约定：以 ? 开头的字符串。"""
    return isinstance(x, str) and x.startswith("?")


def _atom_ok(a: Any) -> bool:
    return (isinstance(a, dict) and isinstance(a.get("pred"), str) and bool(a["pred"])
            and isinstance(a.get("args"), list))


def _validate_facts(doc: dict[str, Any], out: list[str]) -> None:
    for i, f in enumerate(doc.get("facts") or []):
        if not _atom_ok(f):
            out.append("facts[%d] 形状不合法（须含 pred 与 args）" % i)
        elif any(is_var(x) for x in f["args"]):
            out.append("facts[%d] 含变量：事实必须是基原子" % i)


def _validate_rules(doc: dict[str, Any], out: list[str]) -> None:
    for i, r in enumerate(doc.get("rules") or []):
        if not isinstance(r, dict) or not _atom_ok(r.get("head")):
            out.append("rules[%d] 缺 head 或形状不合法" % i)
            continue
        body = r.get("body")
        if not isinstance(body, list) or not body:
            out.append("rules[%d] body 须为非空数组" % i)
            continue
        for j, b in enumerate(body):
            if isinstance(b, dict) and "guard" in b:
                g = b["guard"]
                if not isinstance(g, list) or len(g) != 3 or g[1] not in GUARD_OPS:
                    out.append("rules[%d].body[%d] guard 须为 [左, 算子, 右]，算子 ∈ %s"
                               % (i, j, list(GUARD_OPS)))
            elif not _atom_ok(b):
                out.append("rules[%d].body[%d] 既非原子也非 guard" % (i, j))


def validate(doc: Any) -> list[str]:
    """形状校验 → 违例清单（空=合规）。fail-closed：缺字段/未知算子一律判违例。"""
    out: list[str] = []
    if not isinstance(doc, dict) or not doc:
        return ["规则文档缺失或非对象"]
    if doc.get("schema") != SCHEMA:
        out.append("schema 须为 %s，实为 %r" % (SCHEMA, doc.get("schema")))
    for key in ("facts", "rules"):
        if not isinstance(doc.get(key), list):
            out.append("%s 须为数组" % key)
    _validate_facts(doc, out)
    _validate_rules(doc, out)
    fuel = doc.get("fuel")
    if fuel is not None and (not isinstance(fuel, int) or fuel <= 0):
        out.append("fuel 须为正整数，实为 %r" % (fuel,))
    return out


def _guard_ok(g: list[Any], subst: dict[str, Any]) -> bool:
    left, op, right = g
    if is_var(left) and left not in subst:
        return False
    if is_var(right) and right not in subst:
        return False
    a = subst.get(left, left) if is_var(left) else left
    b = subst.get(right, right) if is_var(right) else right
    try:
        return bool(_OPS[op](a, b))
    except TypeError:          # 类型不可比 → 判不通过（而不是崩）
        return False


def _index(facts: Set[tuple[str, tuple[Any, ...]]]
           ) -> dict[str, list[tuple[Any, ...]]]:
    """事实集 → 按谓词分组（顺序稳定，供回溯匹配）。"""
    by_pred: dict[str, list[tuple[Any, ...]]] = {}
    for pred, args in sorted(facts):
        by_pred.setdefault(pred, []).append(args)
    return by_pred


def _bind(body: list[dict[str, Any]], by_pred: dict[str, list[tuple[Any, ...]]],
          subst: dict[str, Any], on_solution, delta: dict[int, Any] | None = None,
          idx: int = 0) -> None:
    """回溯匹配规则体；每找到完整解回调 on_solution(解)。

    delta 非空时，**指定体位置**只在 delta 事实里取值（半朴素后端的核心；None 即朴素）。
    """
    if not body:
        on_solution(subst)
        return
    first, rest = body[0], body[1:]
    if "guard" in first:
        if _guard_ok(first["guard"], subst):
            _bind(rest, by_pred, subst, on_solution, delta, idx + 1)
        return
    facts = (delta or {}).get(idx)
    if facts is None:
        facts = by_pred.get(first["pred"], ())
    for fact in facts:
        s = dict(subst)
        ok = True
        for pat, val in zip(first["args"], fact):
            if is_var(pat):
                if pat in s and s[pat] != val:
                    ok = False
                    break
                s[pat] = val
            elif pat != val:
                ok = False
                break
        if ok:
            _bind(rest, by_pred, s, on_solution, delta, idx + 1)


def evaluate(doc: dict[str, Any], fuel: int | None = None) -> dict[str, Any]:
    """定点推导 → {status, facts, fuel_used, fuel_total, rounds}。

    status ∈ OK（达定点）/ FUEL_EXHAUSTED（燃料耗尽：结果**部分**且如实标记）/ INVALID。
    """
    issues = validate(doc)
    if issues:
        return {"status": "INVALID", "issues": issues, "facts": [],
                "fuel_used": 0, "fuel_total": 0, "rounds": 0}
    total = int(fuel if fuel is not None else (doc.get("fuel") or DEFAULT_FUEL))
    facts: Set[tuple[str, tuple[Any, ...]]] = set()
    for f in doc["facts"]:
        facts.add((f["pred"], tuple(f["args"])))
    rules = doc["rules"]
    used = 0
    exhausted = False
    rounds = 0
    while not exhausted:
        rounds += 1
        by_pred = _index(facts)
        new: Set[tuple[str, tuple[Any, ...]]] = set()
        for r in rules:
            head = r["head"]

            def _on_solution(subst: dict[str, Any], head=head) -> None:
                nonlocal used, exhausted
                if exhausted:
                    return
                used += 1
                if used > total:
                    exhausted = True
                    return
                new.add((head["pred"],
                         tuple(subst.get(a, a) if is_var(a) else a for a in head["args"])))

            _bind(r["body"], by_pred, {}, _on_solution)
            if exhausted:
                break
        added = new - facts
        facts |= added
        if exhausted:
            return {"status": "FUEL_EXHAUSTED",
                    "facts": sorted("%s(%s)" % (p, ",".join(str(x) for x in a)) for p, a in facts),
                    "fuel_used": used, "fuel_total": total, "rounds": rounds}
        if not added:
            break
    return {"status": "OK", "facts": _fmt(facts), "fuel_used": used,
            "fuel_total": total, "rounds": rounds}


def _body_facts(body: list[dict[str, Any]],
                subst: dict[str, Any]) -> tuple[tuple[str, tuple[Any, ...]], ...]:
    """把已绑定的规则体原子实例化成基事实（guard 不计），作为推导图的入边。"""
    out = []
    for b in body:
        if "guard" in b:
            continue
        out.append((b["pred"], tuple(subst.get(a, a) if is_var(a) else a for a in b["args"])))
    return tuple(out)


def evaluate_dag(doc: dict[str, Any], fuel: int | None = None) -> dict[str, Any]:
    """**第三后端**（gate-DAG 风格）：显式记录「谁推出谁」，再按依赖深度分层。

    与朴素/半朴素后端的差别只在**是否物化推导图**：事实集三者必须逐条相同（差分自检）。
    返回额外给出 graph 统计（节点/边/最大深度）——它是「规则 → 可调度 DAG」的桥。
    """
    issues = validate(doc)
    if issues:
        return {"status": "INVALID", "issues": issues, "facts": [],
                "fuel_used": 0, "fuel_total": 0, "rounds": 0,
                "graph": {"nodes": 0, "edges": 0, "depth": 0}}
    total = int(fuel if fuel is not None else (doc.get("fuel") or DEFAULT_FUEL))
    base: Set[tuple[str, tuple[Any, ...]]] = {
        (f["pred"], tuple(f["args"])) for f in doc["facts"]}
    facts = set(base)
    edges: dict[tuple[str, tuple[Any, ...]], Set[Any]] = {}
    counter: list[Any] = [0, total, False]
    rounds = 0
    while True:
        rounds += 1
        by_pred = _index(facts)
        new: Set[tuple[str, tuple[Any, ...]]] = set()
        for r in doc["rules"]:
            head = r["head"]

            def _on(subst: dict[str, Any], head=head) -> None:
                if counter[2]:
                    return
                counter[0] += 1
                if counter[0] > counter[1]:
                    counter[2] = True
                    return
                node = (head["pred"],
                        tuple(subst.get(a, a) if is_var(a) else a for a in head["args"]))
                new.add(node)
                deps = edges.setdefault(node, set())
                for bf in _body_facts(r["body"], subst):
                    if bf != node:
                        deps.add(bf)

            _bind(r["body"], by_pred, {}, _on)
            if counter[2]:
                break
        added = new - facts
        facts |= added
        if counter[2] or not added:
            break
    depth = 0
    memo: dict[Any, int] = {f: 0 for f in base}
    for _ in range(len(facts) + 1):
        changed = False
        for node, deps in edges.items():
            if node not in facts:
                continue
            d = 1 + max((memo.get(x, 0) for x in deps), default=0)
            if d > memo.get(node, 0):
                memo[node] = d
                changed = True
        if not changed:
            break
    depth = max(memo.values(), default=0)
    derived_edges = sum(len([d for d in deps if d in facts]) for deps in edges.values())
    return {"status": "FUEL_EXHAUSTED" if counter[2] else "OK", "facts": _fmt(facts),
            "fuel_used": counter[0], "fuel_total": total, "rounds": rounds,
            "graph": {"nodes": len(facts), "edges": derived_edges, "depth": depth}}


def _fmt(facts: Set[tuple[str, tuple[Any, ...]]]) -> list[str]:
    return sorted("%s(%s)" % (p, ",".join(str(x) for x in a)) for p, a in facts)


def _mk(head: dict[str, Any], new: Set[tuple[str, tuple[Any, ...]]],
        counter: list[Any]):
    """口径与朴素后端一致的「解 → 头部事实」回调（counter=[used, cap, exhausted]）。"""
    def _on(subst: dict[str, Any]) -> None:
        counter[0] += 1
        if counter[0] > counter[1]:
            counter[2] = True
            return
        new.add((head["pred"],
                 tuple(subst.get(a, a) if is_var(a) else a for a in head["args"])))
    return _on


def evaluate_seminaive(doc: dict[str, Any], fuel: int | None = None) -> dict[str, Any]:
    """**第二后端**（半朴素 delta 迭代）：语义等价、实例化更省。

    每轮只让「至少一个体原子」落在上一轮新增（delta）里，逐位置取并集。
    fuel 口径同为「规则实例化次数」；半朴素天然更省 ⇒ 紧燃料下用量与朴素不同，
    但**两者都达定点时事实集必须逐条相同**（差分自检见 tests.test_nfal_rules）。
    """
    issues = validate(doc)
    if issues:
        return {"status": "INVALID", "issues": issues, "facts": [],
                "fuel_used": 0, "fuel_total": 0, "rounds": 0}
    total = int(fuel if fuel is not None else (doc.get("fuel") or DEFAULT_FUEL))
    facts: Set[tuple[str, tuple[Any, ...]]] = {
        (f["pred"], tuple(f["args"])) for f in doc["facts"]}
    rules = doc["rules"]
    counter: list[Any] = [0, total, False]
    rounds = 0
    delta = set(facts)
    guard_only_done = False
    while True:
        rounds += 1
        by_pred = _index(facts)
        delta_idx = _index(delta)
        new: Set[tuple[str, tuple[Any, ...]]] = set()
        for r in rules:
            head = r["head"]
            positions = [i for i, b in enumerate(r["body"]) if "guard" not in b]
            if not positions:                      # 只有 guard 的规则：首轮按全量跑一次
                if not guard_only_done:
                    _bind(r["body"], by_pred, {}, _mk(head, new, counter))
                continue
            for i in positions:
                pat = r["body"][i]
                _bind(r["body"], by_pred, {}, _mk(head, new, counter),
                      delta={i: delta_idx.get(pat["pred"], [])})
                if counter[2]:
                    break
            if counter[2]:
                break
        guard_only_done = True
        added = new - facts
        facts |= added
        delta = added
        if counter[2] or not added:
            break
    return {"status": "FUEL_EXHAUSTED" if counter[2] else "OK", "facts": _fmt(facts),
            "fuel_used": counter[0], "fuel_total": total, "rounds": rounds}
