use super::*;

impl past::Visitor for Collector<'_> {
    fn visit_stmt(&mut self, node: past::Stmt) {
        let ln = self.ls.line_of(u32::from(node.range().start()));
        let d = self.depth;
        self.collect_stmt(&node, ln, d);
        let d2 = self.enter();
        debug_assert_eq!(d, d2);
        self.generic_visit_stmt(node);
        self.exit();
    }

    fn visit_expr(&mut self, node: past::Expr) {
        let d = self.depth;
        if let past::Expr::Call(c) = &node {
            let ln = self.ls.line_of(u32::from(node.range().start()));
            let shell = c.keywords.iter().any(|k| {
                k.arg
                    .as_ref()
                    .map(|a| a.as_str() == "shell")
                    .unwrap_or(false)
                    && matches!(&k.value, past::Expr::Constant(kk)
                        if matches!(kk.value, past::Constant::Bool(true)))
            });
            self.push(d, Ev::Call(ln, unparse_expr(&c.func), shell));
        }
        self.enter();
        self.generic_visit_expr(node);
        self.exit();
    }

    // ---- 其余顶层钩子：既要**深度**、又要**自己下钻** ----
    //
    // ⚠️ 实测（2026-10-04，逐构造探针）：`rustpython-ast` 生成的 visitor 里，
    // 下列 `generic_visit_*` 是**空实现**（不下钻）：`comprehension` / `arguments` / `arg` /
    // `keyword` / `alias` / `withitem` / `match_case` / 若干 pattern·type_param。
    // 而 CPython 的 `ast.walk` 会遍历**全部** `_fields`——故这些路径上的 `Call` 会被漏收
    // （探针实测漏掉：`with ... as x:` 的 `context_expr`、关键字参数值、推导式的 `if`）。
    // 这里按 **CPython 的 `_fields` 顺序**补下钻，否则 (深度, 前序) 排序不再等于 BFS 序。

    fn visit_comprehension(&mut self, node: past::Comprehension) {
        self.enter();
        d_comprehension(self, node);
        self.exit();
    }
    fn visit_excepthandler(&mut self, node: past::ExceptHandler) {
        self.enter();
        self.generic_visit_excepthandler(node);
        self.exit();
    }
    fn visit_arguments(&mut self, node: past::Arguments) {
        self.enter();
        d_arguments(self, node);
        self.exit();
    }
    fn visit_arg(&mut self, node: past::Arg) {
        self.enter();
        d_arg(self, node);
        self.exit();
    }
    fn visit_keyword(&mut self, node: past::Keyword) {
        self.enter();
        d_keyword(self, node);
        self.exit();
    }
    fn visit_alias(&mut self, _node: past::Alias) {
        self.enter();
        // `alias` 无子节点
        self.exit();
    }
    fn visit_withitem(&mut self, node: past::WithItem) {
        self.enter();
        d_withitem(self, node);
        self.exit();
    }
    fn visit_match_case(&mut self, node: past::MatchCase) {
        self.enter();
        d_match_case(self, node);
        self.exit();
    }
    fn visit_pattern(&mut self, node: past::Pattern) {
        self.enter();
        self.generic_visit_pattern(node);
        self.exit();
    }
    fn visit_type_param(&mut self, node: past::TypeParam) {
        self.enter();
        self.generic_visit_type_param(node);
        self.exit();
    }
}

impl past::Visitor for MetricCollector<'_> {
    fn visit_stmt(&mut self, node: past::Stmt) {
        let r = node.range();
        let start = u32::from(r.start());
        // `end_lineno` 是**含**末字符的行；rustpython 的 range.end 是**排他**偏移 ⇒ 减一
        let end_off = u32::from(r.end()).saturating_sub(1);
        let start_line = self.ls.line_of(start);
        match &node {
            past::Stmt::FunctionDef(f) => {
                let end_line = self.ls.line_of(end_off);
                self.entering_fn(f.name.as_str(), start_line, end_line);
                self.generic_visit_stmt(node);
                self.leaving_fn();
                return;
            }
            past::Stmt::AsyncFunctionDef(f) => {
                let end_line = self.ls.line_of(end_off);
                self.entering_fn(f.name.as_str(), start_line, end_line);
                self.generic_visit_stmt(node);
                self.leaving_fn();
                return;
            }
            // 判定点（真源 `_fn_cc` 的集合里属 Stmt 的那些）
            past::Stmt::If(_)
            | past::Stmt::For(_)
            | past::Stmt::AsyncFor(_)
            | past::Stmt::While(_)
            | past::Stmt::With(_)
            | past::Stmt::AsyncWith(_)
            | past::Stmt::Assert(_) => self.bump(1),
            _ => {}
        }
        self.enter();
        self.generic_visit_stmt(node);
        self.exit();
    }

    fn visit_expr(&mut self, node: past::Expr) {
        match &node {
            past::Expr::IfExp(_) => self.bump(1),
            past::Expr::BoolOp(b) => {
                let extra = b.values.len() as i64 - 1;
                if extra > 0 {
                    self.bump(extra);
                }
            }
            _ => {}
        }
        self.enter();
        self.generic_visit_expr(node);
        self.exit();
    }

    fn visit_excepthandler(&mut self, node: past::ExceptHandler) {
        // 真源把 `ExceptHandler` 也算判定点
        self.bump(1);
        self.enter();
        self.generic_visit_excepthandler(node);
        self.exit();
    }

    fn visit_comprehension(&mut self, node: past::Comprehension) {
        self.enter();
        d_comprehension(self, node);
        self.exit();
    }
    fn visit_arguments(&mut self, node: past::Arguments) {
        self.enter();
        d_arguments(self, node);
        self.exit();
    }
    fn visit_arg(&mut self, node: past::Arg) {
        self.enter();
        d_arg(self, node);
        self.exit();
    }
    fn visit_keyword(&mut self, node: past::Keyword) {
        self.enter();
        d_keyword(self, node);
        self.exit();
    }
    fn visit_alias(&mut self, _node: past::Alias) {
        self.enter();
        self.exit();
    }
    fn visit_withitem(&mut self, node: past::WithItem) {
        self.enter();
        d_withitem(self, node);
        self.exit();
    }
    fn visit_match_case(&mut self, node: past::MatchCase) {
        self.enter();
        d_match_case(self, node);
        self.exit();
    }
    fn visit_pattern(&mut self, node: past::Pattern) {
        self.enter();
        self.generic_visit_pattern(node);
        self.exit();
    }
    fn visit_type_param(&mut self, node: past::TypeParam) {
        self.enter();
        self.generic_visit_type_param(node);
        self.exit();
    }
}


/// JoinedStr 的常量片段拼接（非常量片段忽略）。
fn joined_str_parts(js: &past::ExprJoinedStr) -> String {
    js.values
        .iter()
        .filter_map(|v| match v {
            past::Expr::Constant(k) => match &k.value {
                past::Constant::Str(s) => Some(s.to_string()),
                _ => None,
            },
            _ => None,
        })
        .collect()
}

impl Collector<'_> {
    /// 按语句类型收集事件（raise / import / import-from / try 守卫）。
    fn collect_stmt(&mut self, node: &past::Stmt, ln: u32, d: usize) {
        match node {
            past::Stmt::Raise(r) => self.collect_raise(r, ln, d),
            past::Stmt::Import(i) => self.collect_import(i, ln, d),
            past::Stmt::ImportFrom(f) => self.collect_import_from(f, ln, d),
            past::Stmt::Try(t) => self.collect_try(t),
            _ => {}
        }
    }

    /// raise：首个实参为常量 / 拼接串时记 Raise 事件。
    fn collect_raise(&mut self, r: &past::StmtRaise, ln: u32, d: usize) {
        let Some(exc) = &r.exc else { return };
        let past::Expr::Call(c) = exc.as_ref() else {
            return;
        };
        let Some(a0) = c.args.first() else { return };
        match a0 {
            past::Expr::Constant(k) => {
                if let past::Constant::Str(s) = &k.value {
                    self.push(d, Ev::Raise(ln, s.to_string()));
                }
            }
            past::Expr::JoinedStr(js) => {
                let parts = joined_str_parts(js);
                self.push(d, Ev::Raise(ln, parts));
            }
            _ => {}
        }
    }

    /// import：逐个别名取头部名。
    fn collect_import(&mut self, i: &past::StmtImport, ln: u32, d: usize) {
        let mut v = Vec::new();
        for a in &i.names {
            let head = a.name.split('.').next().unwrap_or("").to_string();
            v.push((head, ln));
        }
        self.push(d, Ev::Import(v));
    }

    /// from-import：绝对导入（level=0）且模块名在场。
    fn collect_import_from(&mut self, f: &past::StmtImportFrom, ln: u32, d: usize) {
        let level = f.level.map(|l| l.to_u32()).unwrap_or(0);
        if level == 0 {
            if let Some(m) = &f.module {
                let head = m.as_str().split('.').next().unwrap_or("").to_string();
                self.push(d, Ev::ImportFrom(head, ln));
            }
        }
    }

    /// try 守卫导入：body 里受守卫的 import 行号登记进 guarded。
    fn collect_try(&mut self, t: &past::StmtTry) {
        if try_guards_import(t) {
            for sub in &t.body {
                let mut c = ImportLinenos {
                    ls: self.ls,
                    out: Vec::new(),
                };
                c.visit_stmt(sub.clone());
                for l in c.out {
                    self.guarded.insert(l);
                }
            }
        }
    }
}
