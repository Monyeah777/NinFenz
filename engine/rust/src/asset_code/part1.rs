use super::*;

/// 真源 `_walk_scope` 的"不进"集合。
pub(crate) fn is_scope_boundary_stmt(s: &past::Stmt) -> bool {
    matches!(
        s,
        past::Stmt::FunctionDef(_) | past::Stmt::AsyncFunctionDef(_) | past::Stmt::ClassDef(_)
    )
}

// ---------------------------------------------------------------- 名字收集

/// 真源 `_assigned_names`（结果是无序集合，故遍历序无关）。
pub(crate) struct NameCollector {
    pub(crate) out: BTreeSet<String>,
}

impl past::Visitor for NameCollector {
    fn visit_stmt(&mut self, node: past::Stmt) {
        if is_scope_boundary_stmt(&node) {
            return; // 不进入嵌套作用域
        }
        match &node {
            past::Stmt::Assign(a) => {
                for t in &a.targets {
                    if let past::Expr::Name(n) = t {
                        self.out.insert(n.id.to_string());
                    }
                }
            }
            past::Stmt::AnnAssign(a) => {
                if let past::Expr::Name(n) = a.target.as_ref() {
                    self.out.insert(n.id.to_string());
                }
            }
            past::Stmt::AugAssign(a) => {
                if let past::Expr::Name(n) = a.target.as_ref() {
                    self.out.insert(n.id.to_string());
                }
            }
            past::Stmt::For(f) => {
                if let past::Expr::Name(n) = f.target.as_ref() {
                    self.out.insert(n.id.to_string());
                }
            }
            past::Stmt::AsyncFor(f) => {
                if let past::Expr::Name(n) = f.target.as_ref() {
                    self.out.insert(n.id.to_string());
                }
            }
            _ => {}
        }
        self.generic_visit_stmt(node);
    }

    fn visit_expr(&mut self, node: past::Expr) {
        if matches!(node, past::Expr::Lambda(_)) {
            return;
        }
        self.generic_visit_expr(node);
    }

    fn visit_withitem(&mut self, node: past::WithItem) {
        if let Some(v) = &node.optional_vars {
            if let past::Expr::Name(n) = v.as_ref() {
                self.out.insert(n.id.to_string());
            }
        }
        d_withitem(self, node);
    }

    // 其余钩子：既补下钻，又不跨作用域
    fn visit_comprehension(&mut self, node: past::Comprehension) {
        d_comprehension(self, node);
    }
    fn visit_arguments(&mut self, node: past::Arguments) {
        d_arguments(self, node);
    }
    fn visit_arg(&mut self, node: past::Arg) {
        if let Some(a) = &node.annotation {
            self.visit_expr(a.as_ref().clone());
        }
    }
    fn visit_keyword(&mut self, node: past::Keyword) {
        d_keyword(self, node);
    }
    fn visit_alias(&mut self, _n: past::Alias) {}
    fn visit_match_case(&mut self, node: past::MatchCase) {
        d_match_case(self, node);
    }
    fn visit_pattern(&mut self, node: past::Pattern) {
        self.generic_visit_pattern(node);
    }
    fn visit_type_param(&mut self, node: past::TypeParam) {
        self.generic_visit_type_param(node);
    }
    fn visit_excepthandler(&mut self, node: past::ExceptHandler) {
        self.generic_visit_excepthandler(node);
    }
}

impl past::Visitor for DerefCollector<'_> {
    fn visit_stmt(&mut self, node: past::Stmt) {
        if is_scope_boundary_stmt(&node) {
            return;
        }
        self.generic_visit_stmt(node);
    }
    fn visit_expr(&mut self, node: past::Expr) {
        if matches!(node, past::Expr::Lambda(_)) {
            return;
        }
        self.look(&node);
        self.generic_visit_expr(node);
    }
    fn visit_comprehension(&mut self, node: past::Comprehension) {
        d_comprehension(self, node);
    }
    fn visit_arguments(&mut self, node: past::Arguments) {
        d_arguments(self, node);
    }
    fn visit_arg(&mut self, node: past::Arg) {
        if let Some(a) = &node.annotation {
            self.visit_expr(a.as_ref().clone());
        }
    }
    fn visit_keyword(&mut self, node: past::Keyword) {
        d_keyword(self, node);
    }
    fn visit_alias(&mut self, _n: past::Alias) {}
    fn visit_withitem(&mut self, node: past::WithItem) {
        d_withitem(self, node);
    }
    fn visit_match_case(&mut self, node: past::MatchCase) {
        d_match_case(self, node);
    }
    fn visit_pattern(&mut self, node: past::Pattern) {
        self.generic_visit_pattern(node);
    }
    fn visit_type_param(&mut self, node: past::TypeParam) {
        self.generic_visit_type_param(node);
    }
    fn visit_excepthandler(&mut self, node: past::ExceptHandler) {
        self.generic_visit_excepthandler(node);
    }
}

impl past::Visitor for SeedCollector {
    fn visit_stmt(&mut self, node: past::Stmt) {
        let d = self.depth;
        let s = self.seq;
        self.seq += 1;
        match &node {
            past::Stmt::FunctionDef(f) => {
                let dn = default_none(&f.args);
                self.depth += 1;
                // 不进入嵌套函数体（各自另算），但 `<函数体>` 本身要收
                self.out.push((d, s, f.body.clone(), dn));
                self.depth -= 1;
                self.generic_visit_stmt(node);
                return;
            }
            past::Stmt::AsyncFunctionDef(f) => {
                let dn = default_none(&f.args);
                self.depth += 1;
                self.out.push((d, s, f.body.clone(), dn));
                self.depth -= 1;
                self.generic_visit_stmt(node);
                return;
            }
            _ => {}
        }
        self.depth += 1;
        self.generic_visit_stmt(node);
        self.depth -= 1;
    }
    fn visit_expr(&mut self, node: past::Expr) {
        // 真源只把 `FunctionDef` / `AsyncFunctionDef` 当种子（**不含 lambda**）
        self.seq += 1;
        self.depth += 1;
        self.generic_visit_expr(node);
        self.depth -= 1;
    }
    fn visit_comprehension(&mut self, node: past::Comprehension) {
        d_comprehension(self, node);
    }
    fn visit_arguments(&mut self, node: past::Arguments) {
        d_arguments(self, node);
    }
    fn visit_arg(&mut self, node: past::Arg) {
        if let Some(a) = &node.annotation {
            self.visit_expr(a.as_ref().clone());
        }
    }
    fn visit_keyword(&mut self, node: past::Keyword) {
        d_keyword(self, node);
    }
    fn visit_alias(&mut self, _n: past::Alias) {}
    fn visit_withitem(&mut self, node: past::WithItem) {
        d_withitem(self, node);
    }
    fn visit_match_case(&mut self, node: past::MatchCase) {
        d_match_case(self, node);
    }
    fn visit_pattern(&mut self, node: past::Pattern) {
        self.generic_visit_pattern(node);
    }
    fn visit_type_param(&mut self, node: past::TypeParam) {
        self.generic_visit_type_param(node);
    }
    fn visit_excepthandler(&mut self, node: past::ExceptHandler) {
        self.generic_visit_excepthandler(node);
    }
}

impl past::Visitor for CallCollector<'_> {
    fn visit_stmt(&mut self, node: past::Stmt) {
        self.depth += 1;
        self.generic_visit_stmt(node);
        self.depth -= 1;
    }
    fn visit_expr(&mut self, node: past::Expr) {
        let d = self.depth;
        let s = self.seq;
        self.seq += 1;
        if let past::Expr::Call(c) = &node {
            self.out
                .push((d, s, line_of(&node, self.ls), dotted(&c.func)));
        }
        self.depth += 1;
        self.generic_visit_expr(node);
        self.depth -= 1;
    }
    fn visit_comprehension(&mut self, node: past::Comprehension) {
        d_comprehension(self, node);
    }
    fn visit_arguments(&mut self, node: past::Arguments) {
        d_arguments(self, node);
    }
    fn visit_arg(&mut self, node: past::Arg) {
        if let Some(a) = &node.annotation {
            self.visit_expr(a.as_ref().clone());
        }
    }
    fn visit_keyword(&mut self, node: past::Keyword) {
        d_keyword(self, node);
    }
    fn visit_alias(&mut self, _n: past::Alias) {}
    fn visit_withitem(&mut self, node: past::WithItem) {
        d_withitem(self, node);
    }
    fn visit_match_case(&mut self, node: past::MatchCase) {
        d_match_case(self, node);
    }
    fn visit_pattern(&mut self, node: past::Pattern) {
        self.generic_visit_pattern(node);
    }
    fn visit_type_param(&mut self, node: past::TypeParam) {
        self.generic_visit_type_param(node);
    }
    fn visit_excepthandler(&mut self, node: past::ExceptHandler) {
        self.generic_visit_excepthandler(node);
    }
}

pub(crate) fn assigned_names(stmt: &past::Stmt) -> BTreeSet<String> {
    let mut c = NameCollector {
        out: BTreeSet::new(),
    };
    c.visit_stmt(stmt.clone());
    c.out
}
