"""asset_contract 私有子模块 _ast：代码面 AST 判据：可证空指针解引用（同语句序列内 None 解引用）。

门面 core.asset_contract 按原 API 重新导出；本文件只承载实现，不改变对外面。
"""
from __future__ import annotations

import ast



# ---------------------------------------------------------------- 代码面
def _walk_scope(node: ast.AST) -> Iterable[ast.AST]:
    """遍历作用域内节点，**不进入**嵌套函数/lambda（各自另算，避免跨作用域误判）。"""
    stack = [node]
    while stack:
        cur = stack.pop()
        if isinstance(cur, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)):
            continue
        yield cur
        stack.extend(ast.iter_child_nodes(cur))



def _assigned_names(node: ast.AST) -> set:
    out = set()
    for n in _walk_scope(node):
        if isinstance(n, ast.Assign):
            out |= {t.id for t in n.targets if isinstance(t, ast.Name)}
        elif isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name):
            out.add(n.target.id)
        elif isinstance(n, ast.AugAssign) and isinstance(n.target, ast.Name):
            out.add(n.target.id)
        elif isinstance(n, (ast.For, ast.AsyncFor)) and isinstance(n.target, ast.Name):
            out.add(n.target.id)
        elif isinstance(n, ast.withitem) and isinstance(n.optional_vars, ast.Name):
            out.add(n.optional_vars.id)
    return out



def _is_none(node: Optional[ast.AST]) -> bool:
    return isinstance(node, ast.Constant) and node.value is None



def _assigns_none(stmt: ast.AST, name: str) -> bool:
    """该赋值语句是否把 name 明确置为 None（可证）。"""
    if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1:
        tgt = stmt.targets[0]
        return isinstance(tgt, ast.Name) and tgt.id == name and _is_none(stmt.value)
    if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
        return stmt.target.id == name and _is_none(stmt.value)
    return False



def _guard(stmt: ast.AST) -> Optional[Tuple[str, str]]:
    """识别 `x is None` / `x is not None` → (名字, is-none | is-not-none)。"""
    test = getattr(stmt, "test", None)
    if not isinstance(test, ast.Compare) or len(test.ops) != 1 or len(test.comparators) != 1:
        return None
    if not isinstance(test.left, ast.Name) or not _is_none(test.comparators[0]):
        return None
    if isinstance(test.ops[0], ast.Is):
        return (test.left.id, "is-none")
    if isinstance(test.ops[0], ast.IsNot):
        return (test.left.id, "is-not-none")
    return None



def _always_exits(stmts: List[ast.stmt]) -> bool:
    if not stmts:
        return False
    last = stmts[-1]
    if isinstance(last, (ast.Return, ast.Raise, ast.Continue, ast.Break)):
        return True
    return (isinstance(last, ast.If) and bool(last.orelse)
            and _always_exits(last.body) and _always_exits(last.orelse))



def _head_exprs(stmt: ast.AST) -> List[ast.AST]:
    """语句**自身**要立刻求值的表达式（复合语句只取条件/迭代表达式，不含子块）。

    子块由 _scan_block 带各自状态扫描；这里只取头部表达式，避免把「分支里先重新赋值再解引用」
    错判成外层 None 的解引用（宁少勿滥）。
    """
    if isinstance(stmt, (ast.If, ast.While)):
        return [stmt.test]
    if isinstance(stmt, (ast.For, ast.AsyncFor)):
        return [stmt.iter]
    if isinstance(stmt, (ast.With, ast.AsyncWith)):
        return [i.context_expr for i in stmt.items]
    if isinstance(stmt, (ast.Try, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        return []
    return [stmt]



def _derefs(stmt: ast.AST, names: set) -> List[int]:
    """该语句头部对「当前可证为 None」的名字做的解引用行号（属性/下标/调用）。"""
    out = []
    for head in _head_exprs(stmt):
        for n in _walk_scope(head):
            if (isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name)
                    and n.value.id in names):
                out.append(n.lineno)
            elif (isinstance(n, ast.Subscript) and isinstance(n.value, ast.Name)
                  and n.value.id in names):
                out.append(n.lineno)
            elif isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in names:
                out.append(n.lineno)
    return out



def _scan_block(stmts: List[ast.stmt], cur: set, rel: str,
                out: List[Tuple[str, int, str]]) -> set:
    """顺序扫描一个语句块；**不跨分支并入**（只判同一序列内可证的 None 解引用）。

    复合语句（if/for/while/with/try）只在各自子块里检测，不把子块的 None 状态并回外层；
    分支里可能发生的重新赋值则从外层状态里扣除（保守方向：宁少勿滥）。
    """
    cur = set(cur)
    for st in stmts:
        for lineno in _derefs(st, cur):
            out.append((rel, lineno, ",".join(sorted(cur))))
        if isinstance(st, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
            for name in _assigned_names(st):
                (cur.add if _assigns_none(st, name) else cur.discard)(name)
        elif isinstance(st, ast.Assert):
            g = _guard(st)
            if g and g[1] == "is-not-none":
                cur.discard(g[0])
        elif isinstance(st, ast.If):
            g = _guard(st)
            if g and g[1] == "is-not-none":
                _scan_block(st.body, cur - {g[0]}, rel, out)
                _scan_block(st.orelse, cur, rel, out)
            elif g and g[1] == "is-none":
                _scan_block(st.body, cur, rel, out)
                _scan_block(st.orelse, cur - {g[0]}, rel, out)
            else:
                _scan_block(st.body, cur, rel, out)
                _scan_block(st.orelse, cur, rel, out)
            if g and g[1] == "is-none" and _always_exits(st.body):
                cur.discard(g[0])
            cur -= _assigned_names(st)
        elif isinstance(st, (ast.For, ast.AsyncFor, ast.While, ast.With, ast.AsyncWith)):
            _scan_block(st.body, cur, rel, out)
            cur -= _assigned_names(st)
        elif isinstance(st, ast.Try):
            _scan_block(st.body, cur, rel, out)
            for handler in st.handlers:
                _scan_block(handler.body, cur, rel, out)
            _scan_block(st.orelse, cur, rel, out)
            _scan_block(st.finalbody, cur, rel, out)
            cur -= _assigned_names(st)
    return cur



def _none_deref(tree: ast.AST, rel: str) -> List[str]:
    """可证空指针：x = None（或默认参数 None）之后在同一语句序列里解引用 x。"""
    out: List[Tuple[str, int, str]] = []
    seeds: List[Any] = [(list(getattr(tree, "body", [])), set())]
    for fn in ast.walk(tree):
        if isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            default_none = set()
            pos = list(fn.args.posonlyargs) + list(fn.args.args)
            pos_defaults = list(fn.args.defaults)
            # 位置默认值对应**尾部**参数（python 语义）——首版错配到头部，把普通形参也当成
            # None 默认（实测 json_schema._check 假红 37 条）；kw_defaults 与 kwonlyargs 一一对应。
            pairs: List[Tuple[ast.arg,
 Any]] = list(zip(pos[len(pos) - len(pos_defaults):],
 pos_defaults))
            pairs += list(zip(fn.args.kwonlyargs, fn.args.kw_defaults))
            for arg, default in pairs:
                if _is_none(default):
                    default_none.add(arg.arg)
            seeds.append((fn.body, default_none))
    for body, seed in seeds:
        _scan_block(body, seed, rel, out)
    msgs = []
    seen = set()
    for rel_name, lineno, names in sorted(out, key=lambda x: x[1]):
        if (lineno, names) in seen:
            continue
        seen.add((lineno, names))
        msgs.append("代码件 %s 第 %d 行解引用可证为 None 的 %s（修复指引：解引用前判空，或把初始值"
                    "改成真实对象——同一语句序列内没有任何重新赋值）" % (rel_name, lineno, names))
    return msgs
