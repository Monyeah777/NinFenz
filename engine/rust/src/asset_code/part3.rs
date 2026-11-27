use super::*;

/// BFS 序的函数种子（真源 `for fn in ast.walk(tree)` 收集 `FunctionDef/AsyncFunctionDef`）。
pub(crate) struct SeedCollector {
    pub(crate) depth: usize,
    pub(crate) seq: usize,
    pub(crate) out: Vec<(usize, usize, Vec<past::Stmt>, BTreeSet<String>)>,
}

/// 真源 `default_none` 的推导（`pos` 的**尾部**参数配位置默认值 + kwonly 一一对应）。
pub(crate) fn default_none(args: &past::Arguments) -> BTreeSet<String> {
    let mut out = BTreeSet::new();
    for a in args.posonlyargs.iter().chain(args.args.iter()) {
        if is_none(a.default.as_deref()) {
            out.insert(a.def.arg.to_string());
        }
    }
    for a in &args.kwonlyargs {
        if is_none(a.default.as_deref()) {
            out.insert(a.def.arg.to_string());
        }
    }
    out
}

/// 真源 `_none_deref`。
pub(crate) fn none_deref(tree: &past::Mod, rel: &str, ls: &crate::pyast::LineStarts) -> Vec<String> {
    let mut out: Vec<(String, u32, String)> = Vec::new();
    let module_body: Vec<past::Stmt> = match tree {
        past::Mod::Module(m) => m.body.clone(),
        _ => Vec::new(),
    };
    let mut seeds: Vec<(Vec<past::Stmt>, BTreeSet<String>)> = vec![(module_body, BTreeSet::new())];
    let mut c = SeedCollector {
        depth: 0,
        seq: 0,
        out: Vec::new(),
    };
    let empty: Vec<past::Stmt> = Vec::new();
    let body = match tree {
        past::Mod::Module(m) => &m.body,
        _ => &empty,
    };
    for st in body {
        c.visit_stmt(st.clone());
    }
    let mut fns = c.out;
    fns.sort_by_key(|(d, s, _, _)| (*d, *s));
    for (_, _, body, dn) in fns {
        seeds.push((body, dn));
    }
    for (body, seed) in seeds {
        scan_block(&body, &seed, rel, ls, &mut out);
    }
    out.sort_by_key(|(_, lineno, _)| *lineno);
    let mut seen: BTreeSet<(u32, String)> = BTreeSet::new();
    let mut msgs = Vec::new();
    for (rel_name, lineno, names) in out {
        if seen.contains(&(lineno, names.clone())) {
            continue;
        }
        seen.insert((lineno, names.clone()));
        msgs.push(format!(
            "代码件 {} 第 {} 行解引用可证为 None 的 {}（修复指引：解引用前判空，或把初始值改成真实对象——同一语句序列内没有任何重新赋值）",
            rel_name, lineno, names
        ));
    }
    msgs
}

/// 真源 `_dotted`。
pub(crate) fn dotted(node: &past::Expr) -> String {
    match node {
        past::Expr::Name(n) => n.id.to_string(),
        past::Expr::Attribute(a) => {
            let base = dotted(&a.value);
            if base.is_empty() {
                a.attr.to_string()
            } else {
                format!("{}.{}", base, a.attr)
            }
        }
        _ => String::new(),
    }
}

/// BFS 序收集调用（真源 `_denied_calls` 用 `ast.walk`，顺序进 issues）。
pub(crate) struct CallCollector<'a> {
    pub(crate) depth: usize,
    pub(crate) seq: usize,
    pub(crate) ls: &'a crate::pyast::LineStarts,
    pub(crate) out: Vec<(usize, usize, u32, String)>,
}

/// 真源 `_denied_calls`。
pub(crate) fn denied_calls(
    tree: &past::Mod,
    rel: &str,
    deny: &BTreeSet<String>,
    ls: &crate::pyast::LineStarts,
) -> Vec<String> {
    let mut c = CallCollector {
        depth: 0,
        seq: 0,
        ls,
        out: Vec::new(),
    };
    let empty: Vec<past::Stmt> = Vec::new();
    let body = match tree {
        past::Mod::Module(m) => &m.body,
        _ => &empty,
    };
    for st in body {
        c.visit_stmt(st.clone());
    }
    let mut calls = c.out;
    calls.sort_by_key(|(d, s, _, _)| (*d, *s));
    calls
        .into_iter()
        .filter(|(_, _, _, name)| !name.is_empty() && deny.contains(name))
        .map(|(_, _, lineno, name)| {
            format!(
                "代码件 {} 第 {} 行调用了禁用面 {}（修复指引：换用不执行任意代码的等价实现；确需保留须改声明并写明理由）",
                rel, lineno, name
            )
        })
        .collect()
}

/// 供 observed_paths 用：BFS 序收集调用 → (depth, seq, lineno, 被调名, 每个实参若是字符串常量)
/// （真源 st.walk 里看 open / Path / pathlib.Path 的**字符串字面量**实参）。
pub(crate) fn calls_with_args(
    tree: &past::Mod,
    ls: &crate::pyast::LineStarts,
) -> Vec<(usize, usize, u32, String, Vec<Option<String>>)> {
    struct C<'a> {
        depth: usize,
        seq: usize,
        ls: &'a crate::pyast::LineStarts,
        out: Vec<(usize, usize, u32, String, Vec<Option<String>>)>,
    }
    impl past::Visitor for C<'_> {
        fn visit_stmt(&mut self, node: past::Stmt) {
            self.depth += 1;
            self.generic_visit_stmt(node);
            self.depth -= 1;
        }
        fn visit_expr(&mut self, node: past::Expr) {
            let (d, s) = (self.depth, self.seq);
            self.seq += 1;
            if let past::Expr::Call(c) = &node {
                let args = c
                    .args
                    .iter()
                    .map(|a| match a {
                        past::Expr::Constant(k) => match &k.value {
                            past::Constant::Str(v) => Some(v.to_string()),
                            _ => None,
                        },
                        _ => None,
                    })
                    .collect();
                self.out
                    .push((d, s, line_of(&node, self.ls), dotted(&c.func), args));
            }
            self.depth += 1;
            self.generic_visit_expr(node);
            self.depth -= 1;
        }
        fn visit_comprehension(&mut self, n: past::Comprehension) {
            d_comprehension(self, n);
        }
        fn visit_arguments(&mut self, n: past::Arguments) {
            d_arguments(self, n);
        }
        fn visit_arg(&mut self, n: past::Arg) {
            if let Some(a) = &n.annotation {
                self.visit_expr(a.as_ref().clone());
            }
        }
        fn visit_keyword(&mut self, n: past::Keyword) {
            d_keyword(self, n);
        }
        fn visit_alias(&mut self, _n: past::Alias) {}
        fn visit_withitem(&mut self, n: past::WithItem) {
            d_withitem(self, n);
        }
        fn visit_match_case(&mut self, n: past::MatchCase) {
            d_match_case(self, n);
        }
        fn visit_pattern(&mut self, n: past::Pattern) {
            self.generic_visit_pattern(n);
        }
        fn visit_type_param(&mut self, n: past::TypeParam) {
            self.generic_visit_type_param(n);
        }
        fn visit_excepthandler(&mut self, n: past::ExceptHandler) {
            self.generic_visit_excepthandler(n);
        }
    }
    let empty: Vec<past::Stmt> = Vec::new();
    let body = match tree {
        past::Mod::Module(m) => &m.body,
        _ => &empty,
    };
    let mut c = C {
        depth: 0,
        seq: 0,
        ls,
        out: Vec::new(),
    };
    for st in body {
        c.visit_stmt(st.clone());
    }
    let mut out = c.out;
    // 真源 st.walk 是 BFS 序；observed_paths 的结果进集合，但保持 BFS 序以免下游依赖漂移
    out.sort_by_key(|(d, s, _, _, _)| (*d, *s));
    out
}
