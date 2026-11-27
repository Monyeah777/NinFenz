use super::*;

// ---------------------------------------------------------------- 判据

/// 真源 `_is_none`。
pub(crate) fn is_none(node: Option<&past::Expr>) -> bool {
    matches!(node, Some(past::Expr::Constant(c)) if matches!(c.value, past::Constant::None))
}

/// 真源 `_assigns_none`。
pub(crate) fn assigns_none(stmt: &past::Stmt, name: &str) -> bool {
    match stmt {
        past::Stmt::Assign(a) if a.targets.len() == 1 => match &a.targets[0] {
            past::Expr::Name(n) => n.id.as_str() == name && is_none(Some(a.value.as_ref())),
            _ => false,
        },
        past::Stmt::AnnAssign(a) => match a.target.as_ref() {
            past::Expr::Name(n) => n.id.as_str() == name && is_none(a.value.as_deref()),
            _ => false,
        },
        _ => false,
    }
}

/// 真源 `_guard` → `(名字, "is-none"|"is-not-none")`。
pub(crate) fn guard(stmt: &past::Stmt) -> Option<(String, &'static str)> {
    let test = match stmt {
        past::Stmt::If(i) => &i.test,
        past::Stmt::While(w) => &w.test,
        past::Stmt::Assert(a) => &a.test,
        _ => return None,
    };
    let past::Expr::Compare(c) = test.as_ref() else {
        return None;
    };
    if c.ops.len() != 1 || c.comparators.len() != 1 {
        return None;
    }
    let past::Expr::Name(left) = c.left.as_ref() else {
        return None;
    };
    if !is_none(Some(&c.comparators[0])) {
        return None;
    }
    match &c.ops[0] {
        past::CmpOp::Is => Some((left.id.to_string(), "is-none")),
        past::CmpOp::IsNot => Some((left.id.to_string(), "is-not-none")),
        _ => None,
    }
}

/// 真源 `_always_exits`。
pub(crate) fn always_exits(stmts: &[past::Stmt]) -> bool {
    let Some(last) = stmts.last() else {
        return false;
    };
    match last {
        past::Stmt::Return(_)
        | past::Stmt::Raise(_)
        | past::Stmt::Continue(_)
        | past::Stmt::Break(_) => true,
        past::Stmt::If(i) => {
            !i.orelse.is_empty() && always_exits(&i.body) && always_exits(&i.orelse)
        }
        _ => false,
    }
}

/// `_head_exprs` 的三种去向：若/循环的条件、with 的 context_expr、其余整条语句。
pub(crate) enum Head {
    Exprs(Vec<past::Expr>),
    Whole(past::Stmt),
}

/// 真源 `_head_exprs`。
pub(crate) fn head_exprs(stmt: &past::Stmt) -> Head {
    match stmt {
        past::Stmt::If(i) => Head::Exprs(vec![i.test.as_ref().clone()]),
        past::Stmt::While(w) => Head::Exprs(vec![w.test.as_ref().clone()]),
        past::Stmt::For(f) => Head::Exprs(vec![f.iter.as_ref().clone()]),
        past::Stmt::AsyncFor(f) => Head::Exprs(vec![f.iter.as_ref().clone()]),
        past::Stmt::With(w) => {
            Head::Exprs(w.items.iter().map(|i| i.context_expr.clone()).collect())
        }
        past::Stmt::AsyncWith(w) => {
            Head::Exprs(w.items.iter().map(|i| i.context_expr.clone()).collect())
        }
        past::Stmt::Try(_)
        | past::Stmt::FunctionDef(_)
        | past::Stmt::AsyncFunctionDef(_)
        | past::Stmt::ClassDef(_) => Head::Exprs(Vec::new()),
        _ => Head::Whole(stmt.clone()),
    }
}

/// 收集"对当前可证为 None 的名字的解引用"行号。
pub(crate) struct DerefCollector<'a> {
    pub(crate) names: &'a BTreeSet<String>,
    pub(crate) ls: &'a crate::pyast::LineStarts,
    pub(crate) out: Vec<u32>,
}

impl DerefCollector<'_> {
    pub(crate) fn look(&mut self, e: &past::Expr) {
        match e {
            past::Expr::Attribute(a) => {
                if let past::Expr::Name(n) = a.value.as_ref() {
                    if self.names.contains(n.id.as_str()) {
                        self.out.push(line_of(e, self.ls));
                    }
                }
            }
            past::Expr::Subscript(s) => {
                if let past::Expr::Name(n) = s.value.as_ref() {
                    if self.names.contains(n.id.as_str()) {
                        self.out.push(line_of(e, self.ls));
                    }
                }
            }
            past::Expr::Call(c) => {
                if let past::Expr::Name(n) = c.func.as_ref() {
                    if self.names.contains(n.id.as_str()) {
                        self.out.push(line_of(e, self.ls));
                    }
                }
            }
            _ => {}
        }
    }
}

/// 从节点取 1-based 行号（真源 `n.lineno`）。
pub(crate) fn line_of<T: Ranged>(n: &T, ls: &crate::pyast::LineStarts) -> u32 {
    ls.line_of(u32::from(n.range().start()))
}

/// 真源 `_derefs`。
pub(crate) fn derefs(stmt: &past::Stmt, names: &BTreeSet<String>, ls: &crate::pyast::LineStarts) -> Vec<u32> {
    let mut c = DerefCollector {
        names,
        ls,
        out: Vec::new(),
    };
    match head_exprs(stmt) {
        Head::Exprs(v) => {
            for e in v {
                c.visit_expr(e);
            }
        }
        Head::Whole(s) => c.visit_stmt(s),
    }
    c.out
}

/// 真源 `_scan_block`。
pub(crate) fn scan_block(
    stmts: &[past::Stmt],
    cur: &BTreeSet<String>,
    rel: &str,
    ls: &crate::pyast::LineStarts,
    out: &mut Vec<(String, u32, String)>,
) -> BTreeSet<String> {
    let mut cur = cur.clone();
    for st in stmts {
        for lineno in derefs(st, &cur, ls) {
            out.push((
                rel.to_string(),
                lineno,
                cur.iter().cloned().collect::<Vec<_>>().join(","),
            ));
        }
        step_stmt(st, &mut cur, rel, ls, out);
    }
    cur
}

/// 单条语句对「可能为 None 的变量集」的流转（递归进入子块）。
pub(crate) fn step_stmt(
    st: &past::Stmt,
    cur: &mut BTreeSet<String>,
    rel: &str,
    ls: &crate::pyast::LineStarts,
    out: &mut Vec<(String, u32, String)>,
) {
    match st {
        past::Stmt::Assign(_) | past::Stmt::AnnAssign(_) | past::Stmt::AugAssign(_) => {
            for name in assigned_names(st) {
                if assigns_none(st, &name) {
                    cur.insert(name);
                } else {
                    cur.remove(&name);
                }
            }
        }
        past::Stmt::Assert(_) => {
            if let Some((n, kind)) = guard(st) {
                if kind == "is-not-none" {
                    cur.remove(&n);
                }
            }
        }
        past::Stmt::If(i) => {
            let g = guard(st);
            match &g {
                Some((n, "is-not-none")) => {
                    let mut sub = cur.clone();
                    sub.remove(n);
                    scan_block(&i.body, &sub, rel, ls, out);
                    scan_block(&i.orelse, &cur, rel, ls, out);
                }
                Some((n, "is-none")) => {
                    scan_block(&i.body, &cur, rel, ls, out);
                    let mut sub = cur.clone();
                    sub.remove(n);
                    scan_block(&i.orelse, &sub, rel, ls, out);
                }
                _ => {
                    scan_block(&i.body, &cur, rel, ls, out);
                    scan_block(&i.orelse, &cur, rel, ls, out);
                }
            }
            if let Some((n, "is-none")) = &g {
                if always_exits(&i.body) {
                    cur.remove(n);
                }
            }
            for name in assigned_names(st) {
                cur.remove(&name);
            }
        }
        past::Stmt::For(f) => {
            scan_block(&f.body, &cur, rel, ls, out);
            for name in assigned_names(st) {
                cur.remove(&name);
            }
        }
        past::Stmt::AsyncFor(f) => {
            scan_block(&f.body, &cur, rel, ls, out);
            for name in assigned_names(st) {
                cur.remove(&name);
            }
        }
        past::Stmt::While(w) => {
            scan_block(&w.body, &cur, rel, ls, out);
            for name in assigned_names(st) {
                cur.remove(&name);
            }
        }
        past::Stmt::With(w) => {
            scan_block(&w.body, &cur, rel, ls, out);
            for name in assigned_names(st) {
                cur.remove(&name);
            }
        }
        past::Stmt::AsyncWith(w) => {
            scan_block(&w.body, &cur, rel, ls, out);
            for name in assigned_names(st) {
                cur.remove(&name);
            }
        }
        past::Stmt::Try(t) => {
            scan_block(&t.body, &cur, rel, ls, out);
            for h in &t.handlers {
                let past::ExceptHandler::ExceptHandler(h) = h;
                scan_block(&h.body, &cur, rel, ls, out);
            }
            scan_block(&t.orelse, &cur, rel, ls, out);
            scan_block(&t.finalbody, &cur, rel, ls, out);
            for name in assigned_names(st) {
                cur.remove(&name);
            }
        }
        _ => {}
    }
}
