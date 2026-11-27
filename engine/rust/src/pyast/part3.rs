use super::*;

/// 真源 `_ast_facts`：解析失败 → `None`（对应真源 `except SyntaxError: got = None`）。
pub(crate) fn purity_facts(text: &str) -> Option<PurityFacts> {
    let suite = parse(text, Mode::Module, "<nf>").ok()?;
    let ls = LineStarts::new(text);
    let mut c = Collector {
        ls: &ls,
        depth: 0,
        seq: 0,
        evs: Vec::new(),
        guarded: BTreeSet::new(),
    };
    match &suite {
        past::Mod::Module(m) => {
            for st in &m.body {
                c.visit_stmt(st.clone());
            }
        }
        past::Mod::Expression(e) => c.visit_expr(e.body.as_ref().clone()),
        // 本线只用 `Mode::Module` 解析；其余两种形态不产事实
        _ => {}
    }
    // 按 (深度, 前序) 排序 == BFS 序
    c.evs.sort_by_key(|(d, s, _)| (*d, *s));

    let mut out = PurityFacts {
        raises: Vec::new(),
        guarded: c.guarded,
        modules: Vec::new(),
        sinks: Vec::new(),
    };
    for (_, _, ev) in c.evs {
        match ev {
            Ev::Raise(l, m) => out.raises.push(RaiseFact { lineno: l, msg: m }),
            Ev::Import(v) => out.modules.extend(v),
            Ev::ImportFrom(m, l) => out.modules.push((m, l)),
            Ev::Call(l, c, s) => out.sinks.push(SinkFact {
                lineno: l,
                call: c,
                shell_true: s,
            }),
        }
    }
    Some(out)
}

// ---------------------------------------------------------------- 差分对账入口

/// 真源 `purity_scan.IMPORT_SCAN` 的三条面。
pub(crate) const IMPORT_SCAN: [&str; 3] = [
    "desktop/src/core/*.py",
    "scripts/*.py",
    ".github/scripts/*.py",
];

/// 把 `_ast_facts` 的事实导成 JSON（供与真源**逐文件**差分对账）。
///
/// 形状：`{ "<相对路径>": {"raises": [[行, 消息], …], "guarded": [行, …],
///                        "modules": [[模块, 行], …], "sinks": [[行, 调用, shell], …]} }`
pub(crate) fn facts_dump(root: &std::path::Path) -> crate::pyjson::Json {
    use crate::pyjson::Json;
    let mut out: Vec<(String, Json)> = Vec::new();
    let mut rels: Vec<String> = Vec::new();
    for pat in IMPORT_SCAN {
        rels.extend(crate::glob::expand(root, pat));
    }
    rels.sort();
    rels.dedup();
    for rel in rels {
        let Ok(text) = std::fs::read_to_string(root.join(&rel)) else {
            continue;
        };
        let Some(f) = purity_facts(&text) else {
            out.push((rel, Json::Null));
            continue;
        };
        let raises = Json::Array(
            f.raises
                .iter()
                .map(|r| Json::Array(vec![Json::Int(r.lineno as i64), Json::Str(r.msg.clone())]))
                .collect(),
        );
        let guarded = Json::Array(f.guarded.iter().map(|l| Json::Int(*l as i64)).collect());
        let modules = Json::Array(
            f.modules
                .iter()
                .map(|(m, l)| Json::Array(vec![Json::Str(m.clone()), Json::Int(*l as i64)]))
                .collect(),
        );
        let sinks = Json::Array(
            f.sinks
                .iter()
                .map(|s| {
                    Json::Array(vec![
                        Json::Int(s.lineno as i64),
                        Json::Str(s.call.clone()),
                        Json::Bool(s.shell_true),
                    ])
                })
                .collect(),
        );
        out.push((
            rel,
            Json::Object(vec![
                ("raises".to_string(), raises),
                ("guarded".to_string(), guarded),
                ("modules".to_string(), modules),
                ("sinks".to_string(), sinks),
            ]),
        ));
    }
    Json::Object(out)
}

// ---------------------------------------------------------------- 规模/复杂度度量（code_metrics）

/// 一个函数的度量：`(名字, 起行, 止行, 圈复杂度)`。
pub(crate) struct FnMetric {
    pub name: String,
    pub lineno: u32,
    pub end_lineno: u32,
    pub cc: i64,
    /// BFS 序还原用（真源 `worst_fn` 是**严格大于**才更新 ⇒ 并列时 walk 序在前者赢）
    pub depth: usize,
    pub seq: usize,
}

/// 遍历完备的度量收集器。
///
/// **为什么要"遍历完备"**：真源 `_fn_cc(fn)` 用 `ast.walk(fn)` 数该函数**子树**里的判定点。
/// 若漏下钻（`rustpython-ast` 那些空 generic），嵌套在关键字参数 / 推导式里的 `BoolOp` 或
/// `IfExp` 就会漏计 ⇒ 圈复杂度偏小 ⇒ 与冻结基线比较时**假绿**。故这里与 `Collector` 共用
/// 同一套下钻助手。
///
/// **为什么用栈**：真源对**每个**函数各 walk 一次，故嵌套函数体里的判定点会**同时**计进
/// 内外两层函数（`ast.walk(outer)` 会下钻到 inner）。用栈即可一次遍历复刻这一语义。
pub(crate) struct MetricFacts {
    pub fns: Vec<FnMetric>,
}

pub(crate) struct MetricCollector<'a> {
    pub(crate) ls: &'a LineStarts,
    pub(crate) stack: Vec<(String, u32, u32, i64, usize, usize)>,
    pub(crate) out: Vec<FnMetric>,
    pub(crate) depth: usize,
    pub(crate) seq: usize,
}

impl MetricCollector<'_> {
    pub(crate) fn bump(&mut self, n: i64) {
        for e in self.stack.iter_mut() {
            e.3 += n;
        }
    }
    pub(crate) fn entering_fn(&mut self, name: &str, start: u32, end: u32) {
        let d = self.depth;
        let s = self.seq;
        self.seq += 1;
        self.stack.push((name.to_string(), start, end, 1, d, s));
        self.depth += 1;
    }
    pub(crate) fn leaving_fn(&mut self) {
        self.depth -= 1;
        if let Some((name, lineno, end_lineno, cc, depth, seq)) = self.stack.pop() {
            self.out.push(FnMetric {
                name,
                lineno,
                end_lineno,
                cc,
                depth,
                seq,
            });
        }
    }
    /// 普通节点进出（只为**深度**正确）
    pub(crate) fn enter(&mut self) {
        self.seq += 1;
        self.depth += 1;
    }
    pub(crate) fn exit(&mut self) {
        self.depth -= 1;
    }
}

/// 真源 `code_metrics.metrics_of` 里与 AST 有关的部分：所有函数的 `(名, 起行, 止行, cc)`。
/// `None` = 语法不可解析（真源记 `syntax_error`）。
pub(crate) fn metric_facts(text: &str) -> Option<MetricFacts> {
    let suite = parse(text, Mode::Module, "<nf>").ok()?;
    let ls = LineStarts::new(text);
    let mut c = MetricCollector {
        ls: &ls,
        stack: Vec::new(),
        out: Vec::new(),
        depth: 0,
        seq: 0,
    };
    match &suite {
        past::Mod::Module(m) => {
            for st in &m.body {
                c.visit_stmt(st.clone());
            }
        }
        past::Mod::Expression(e) => c.visit_expr(e.body.as_ref().clone()),
        _ => {}
    }
    // (深度, 前序) 排序 == CPython `ast.walk` 的 BFS 序（真源 `worst_fn` 取严格大于，
    // 故并列时"谁先被 walk 到"决定 `worst_fn`）
    let mut fns = c.out;
    fns.sort_by_key(|f| (f.depth, f.seq));
    Some(MetricFacts { fns })
}
