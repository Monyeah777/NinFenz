"""core.nfal 私有实现分片 2/3（对外只经 core.nfal 门面导入）：_infer、_infer_coll 等"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from core.nf_expr import LexError, ParseError, parse, strip_pos

from ._part1 import (
    _LIT_TYPES,
    FUNCS,
    NUMERIC,
    SCHEMA,
    UNKNOWN,
    SymbolTable,
    _infer_arith,
    _infer_cmp,
    _join,
    _pos_of,
    _ref_type,
    _rel_result,
    _require,
    diag,
)


def _infer(node: Any, sym: SymbolTable, diags: List[Dict[str, Any]]) -> str:
    if not isinstance(node, dict):
        return "unknown"
    k = node.get("k")
    if k == "lit":
        return _LIT_TYPES.get(str(node.get("t")), "unknown")
    if k == "ref":
        return _ref_type(node, sym, diags)
    if k in ("list", "map"):
        return _infer_coll(node, sym, diags)
    if k == "un":
        return _infer_un(node, sym, diags)
    if k == "cond":
        return _infer_cond(node, sym, diags)
    if k == "call":
        return _infer_call(node, sym, diags)
    if k == "bin":
        return _infer_bin(node, sym, diags)
    return "unknown"


def _infer_coll(node: Dict[str, Any], sym: SymbolTable, diags: List[Dict[str, Any]]) -> str:
    for it in node.get("items") or []:
        _infer(it, sym, diags)
    for key, val in node.get("entries") or []:
        _infer(key, sym, diags)
        _infer(val, sym, diags)
    return "list" if node.get("k") == "list" else "map"


def _infer_un(node: Dict[str, Any], sym: SymbolTable, diags: List[Dict[str, Any]]) -> str:
    t = _infer(node["x"], sym, diags)
    if node["op"] == "!":
        _require("bool", t, _pos_of(node), diags, "! 的操作数")
        return "unknown" if t == "unknown" else "bool"
    _require("int|number", t, _pos_of(node), diags, "一元 - 的操作数")
    if t == "unknown":
        return "unknown"
    return t if t in NUMERIC else "untyped"


def _infer_cond(node: Dict[str, Any], sym: SymbolTable, diags: List[Dict[str, Any]]) -> str:
    _infer(node["c"], sym, diags)
    a = _infer(node["t"], sym, diags)
    b = _infer(node["f"], sym, diags)
    return a if a == b else "untyped"


def _infer_call(node: Dict[str, Any], sym: SymbolTable, diags: List[Dict[str, Any]]) -> str:
    spec = FUNCS.get(str(node.get("fn")))
    if spec is None:
        diags.append(diag("E0304",
 "fail",
 "未登记函数 %s（函数集封闭）" % node.get("fn"),
 _pos_of(node)))
        for a in node.get("args") or []:
            _infer(a, sym, diags)
        return "unknown"
    wants, ret = spec
    args = node.get("args") or []
    if len(args) != len(wants):
        diags.append(diag("E0305", "fail", "%s 需要 %d 个参数，实为 %d"
                          % (node.get("fn"), len(wants), len(args)), _pos_of(node)))
    for i, a in enumerate(args):
        at = _infer(a, sym, diags)
        if i < len(wants):
            _require(wants[i], at, _pos_of(node), diags, "%s 第 %d 参数" % (node.get("fn"), i + 1))
    return ret


def _infer_bin(node: Dict[str, Any], sym: SymbolTable, diags: List[Dict[str, Any]]) -> str:
    op = node["op"]
    lt = _infer(node["l"], sym, diags)
    rt = _infer(node["r"], sym, diags)
    if op in ("&&", "||"):
        _require("bool", lt, _pos_of(node), diags, "%s 左操作数" % op)
        _require("bool", rt, _pos_of(node), diags, "%s 右操作数" % op)
        return _join(lt, rt)
    if op in ("==", "!=", "in"):
        return _rel_result(lt, rt)
    if op in ("<", "<=", ">", ">="):
        return _infer_cmp(node, lt, rt, diags)
    return _infer_arith(op, lt, rt, _pos_of(node), diags)


def infer_type(ast: Any, sym: SymbolTable) -> Tuple[str, List[Dict[str, Any]]]:
    """表达式 → (类型, 诊断)；类型词表见 _KIND_MAP（untyped 是合法值，不判死）。"""
    diags: List[Dict[str, Any]] = []
    return _infer(ast, sym, diags), diags


def check_condition(ast: Any, sym: SymbolTable) -> Tuple[str, List[Dict[str, Any]]]:
    """guard 判据：非 bool 即 fail；untyped 记 warn（后端 fail-closed 记 abstain）。"""
    t, diags = infer_type(ast, sym)
    if t == "untyped":
        diags.append(diag("E0310", "warn",
                          "guard 类型未收窄（untyped）：执行后端按 fail-closed 记 abstain",
 _pos_of(ast)))
    elif t not in ("bool", "unknown"):
        diags.append(diag("E0302", "fail", "guard 应为 bool，实为 %s" % t, _pos_of(ast)))
    return t, diags


def _exc_diag(exc: Exception) -> Dict[str, Any]:
    return diag("E0201", "fail", "表达式解析失败（pos %s）：%s"
                % (getattr(exc, "pos", 0), getattr(exc, "message", str(exc))), 0)


def check_expression(expr: str, sym: SymbolTable) -> Dict[str, Any]:
    """源码 → 检查报告（AST + 非 bool/untyped 判据 + 逐条诊断）。"""
    try:
        ast = parse(expr)
    except (ParseError, LexError) as exc:
        return {"schema": SCHEMA, "kind": "nfal-check", "expr": expr, "verdict": "fail",
                "diagnostics": [_exc_diag(exc)], "ast": None}
    t, diags = check_condition(ast, sym)
    verdict = "fail" if any(d["severity"] == "fail" for d in diags) else ("warn" if diags else "pas"
        "s")
    return {"schema": SCHEMA, "kind": "nfal-check", "expr": expr, "verdict": verdict,
            "guard_type": t, "diagnostics": diags, "ast": strip_pos(ast)}


# ------------------------------------------------------------------ 三值求值（Kleene）
def _ed(message: str, node: Any) -> Dict[str, Any]:
    return diag("E0401", "fail", message, _pos_of(node))


def _walk(env: Dict[str, Any], path: List[str]) -> Any:
    cur: Any = env
    for seg in path:
        if isinstance(cur, dict) and seg in cur:
            cur = cur[seg]
        else:
            return UNKNOWN
    return cur


def _num(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _bool3(v: Any) -> Optional[bool]:
    return v if isinstance(v, bool) else None


def _eval_logic(op: str, a: Any, b: Any, node: Dict[str, Any], diags: List[Dict[str, Any]]) -> Any:
    ba, bb = _bool3(a), _bool3(b)
    if a is UNKNOWN or b is UNKNOWN:
        other = bb if a is UNKNOWN else ba
        if other is False and op == "&&":
            return False
        if other is True and op == "||":
            return True
        return UNKNOWN
    if ba is None or bb is None:
        diags.append(_ed("%s 需要 bool 操作数" % op, node))
        return UNKNOWN
    return (ba and bb) if op == "&&" else (ba or bb)


def _eval_cmp(op: str, a: Any, b: Any, node: Dict[str, Any], diags: List[Dict[str, Any]]) -> Any:
    if not ((_num(a) and _num(b)) or (isinstance(a, str) and isinstance(b, str))):
        diags.append(_ed("%s 操作数不可比" % op, node))
        return UNKNOWN
    return {"<": a < b, "<=": a <= b, ">": a > b, ">=": a >= b}[op]


def _eval_in(a: Any, b: Any, node: Dict[str, Any], diags: List[Dict[str, Any]]) -> Any:
    if isinstance(b, (list, tuple, str, dict)):
        return a in b
    diags.append(_ed("in 右侧应为 list/map/string", node))
    return UNKNOWN


def _div(a: Any, b: Any, node: Dict[str, Any], diags: List[Dict[str, Any]], true_div: bool) -> Any:
    if b == 0:
        diags.append(_ed("除数为零", node))
        return UNKNOWN
    return (a / b) if true_div else (a % b)


def _eval_arith(op: str, a: Any, b: Any, node: Dict[str, Any], diags: List[Dict[str, Any]]) -> Any:
    if op == "+" and isinstance(a, str) and isinstance(b, str):
        return a + b
    if op == "+" and isinstance(a, list) and isinstance(b, list):
        return a + b
    if not (_num(a) and _num(b)):
        diags.append(_ed("%s 需要数值，实为 %s / %s"
                         % (op, type(a).__name__, type(b).__name__), node))
        return UNKNOWN
    if op == "+":
        return a + b
    if op == "-":
        return a - b
    if op == "*":
        return a * b
    if op == "/":
        return _div(a, b, node, diags, True)
    if op == "%":
        return _div(a, b, node, diags, False)
    diags.append(_ed("未知运算符 %s" % op, node))
    return UNKNOWN


def _apply(fn: str, args: List[Any]) -> Any:
    if fn == "size":
        return len(args[0])
    if fn == "contains":
        return args[1] in args[0]      # contains(容器, 元素)
    if fn == "has":
        return args[1] in args[0]
    if fn == "startsWith":
        return args[0].startswith(args[1])
    if fn == "int":
        return int(args[0])
    if fn == "string":
        return str(args[0])
    raise ValueError("未登记函数 %s（修复指引：函数集封闭，见 core.nfal.FUNCS）" % fn)


def evaluate(node: Any, env: Dict[str, Any], diags: List[Dict[str, Any]]) -> Any:
    """表达式 → 具体值或 UNKNOWN（类型不符记诊断并回 UNKNOWN，绝不静默通过）。"""
    if not isinstance(node, dict):
        return UNKNOWN
    k = node.get("k")
    if k == "lit":
        return node.get("v")
    if k == "ref":
        return _walk(env, list(node["path"]))
    if k == "list":
        return [evaluate(x, env, diags) for x in node.get("items") or []]
    if k == "map":
        return {evaluate(a,
 env,
 diags): evaluate(b,
 env,
 diags) for a,
 b in node.get("entries") or []}
    if k == "un":
        return _eval_un(node, env, diags)
    if k == "cond":
        return _eval_cond(node, env, diags)
    if k == "call":
        return _eval_call(node, env, diags)
    if k == "bin":
        return _eval_bin(node, env, diags)
    return UNKNOWN


def _eval_un(node: Dict[str, Any], env: Dict[str, Any], diags: List[Dict[str, Any]]) -> Any:
    v = evaluate(node["x"], env, diags)
    if v is UNKNOWN:
        return UNKNOWN
    if node["op"] == "!":
        if not isinstance(v, bool):
            diags.append(_ed("! 需要 bool，实为 %s" % type(v).__name__, node))
            return UNKNOWN
        return not v
    if not _num(v):
        diags.append(_ed("一元 - 需要数值，实为 %s" % type(v).__name__, node))
        return UNKNOWN
    return -v


def _eval_cond(node: Dict[str, Any], env: Dict[str, Any], diags: List[Dict[str, Any]]) -> Any:
    c = evaluate(node["c"], env, diags)
    if c is UNKNOWN:
        return UNKNOWN
    if not isinstance(c, bool):
        diags.append(_ed("条件表达式分支需要 bool", node))
        return UNKNOWN
    return evaluate(node["t"] if c else node["f"], env, diags)


def _eval_bin(node: Dict[str, Any], env: Dict[str, Any], diags: List[Dict[str, Any]]) -> Any:
    op = node["op"]
    a = evaluate(node["l"], env, diags)
    b = evaluate(node["r"], env, diags)
    if op in ("&&", "||"):
        return _eval_logic(op, a, b, node, diags)
    if a is UNKNOWN or b is UNKNOWN:
        return UNKNOWN
    if op in ("==", "!="):
        return (a == b) if op == "==" else (a != b)
    if op in ("<", "<=", ">", ">="):
        return _eval_cmp(op, a, b, node, diags)
    if op == "in":
        return _eval_in(a, b, node, diags)
    return _eval_arith(op, a, b, node, diags)


def _eval_call(node: Dict[str, Any], env: Dict[str, Any], diags: List[Dict[str, Any]]) -> Any:
    fn = str(node.get("fn"))
    if fn not in FUNCS:
        diags.append(_ed("未登记函数 %s（函数集封闭）" % fn, node))
        return UNKNOWN
    args = [evaluate(a, env, diags) for a in node.get("args") or []]
    if any(x is UNKNOWN for x in args):
        return UNKNOWN
    try:
        return _apply(fn, args)
    except (TypeError, ValueError, IndexError) as exc:
        diags.append(_ed("%s 参数不符：%s" % (fn, exc), node))
        return UNKNOWN
