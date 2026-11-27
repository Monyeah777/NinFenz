use super::*;

/// R4：`raise` 里携带的消息（仅取字符串常量 / f-string 的常量段）。
pub(crate) struct RaiseFact {
    pub lineno: u32,
    pub msg: String,
}

/// R6：危险 sink 候选（行号 / 调用目标名 / 是否 `shell=True`）。
pub(crate) struct SinkFact {
    pub lineno: u32,
    pub call: String,
    pub shell_true: bool,
}

/// 真源 `_ast_facts` 的四元组。
pub(crate) struct PurityFacts {
    pub raises: Vec<RaiseFact>,
    pub guarded: BTreeSet<u32>,
    pub modules: Vec<(String, u32)>,
    pub sinks: Vec<SinkFact>,
}

/// 解析一份 Python 源码 → `Mod`（真源 `ast.parse` 的对应物）；语法坏 → `None`。
pub(crate) fn parse_module(text: &str) -> Option<rustpython_ast::Mod> {
    parse(text, Mode::Module, "<nf>").ok()
}

/// 行号表：源文本里每个 `\n` 之后的位置（用于把字节偏移换成 1-based 行号）。
///
/// **公开**：`asset_code`（代码面控制流分析）也要把 `n.lineno` 算出来。
pub(crate) struct LineStarts(pub Vec<u32>);

impl LineStarts {
    pub fn new(text: &str) -> Self {
        let mut v = vec![0u32];
        for (i, b) in text.bytes().enumerate() {
            if b == b'\n' {
                v.push(i as u32 + 1);
            }
        }
        LineStarts(v)
    }
    pub fn line_of(&self, offset: u32) -> u32 {
        // 最后一个 <= offset 的行起点
        match self.0.binary_search(&offset) {
            Ok(i) => i as u32 + 1,
            Err(i) => i as u32, // i>=1 因为 v[0]=0
        }
    }
}

/// 调用目标的渲染（真源用 `ast.unparse(node.func)`）。
///
/// 直接走 `rustpython-ast` 的 `impl Display for Expr`（它就是它的 unparser）。
///
/// **为什么不自己拼点号名**：那会**丢参数内容**——真源给出
/// `hashlib.sha256(p.read_bytes()).hexdigest` / `subject.replace('/', '__').replace`，
/// 自拼只给 `hashlib.sha256().hexdigest` / `subject.replace().replace`。
/// 逐文件对账当场暴露了 165 处差异（实测）。虽然这些差异**当时看**不影响判定
/// （判据只用「整串是否在 `DANGEROUS_CALLS`」与「末段是否在 `METHOD_SINKS`」），
/// 但"当时看"不是证据——**用真源同款的 unparse，才算把这段对齐**。
pub(crate) fn unparse_expr(e: &past::Expr) -> String {
    format!("{}", e)
}

/// 真源 `_try_guards_import`。
pub(crate) fn try_guards_import(t: &past::StmtTry) -> bool {
    for h in &t.handlers {
        let past::ExceptHandler::ExceptHandler(h) = h;
        // 裸 `except:` ⇒ 兜住了
        let Some(ty) = h.type_.as_deref() else {
            return true;
        };
        let hit =
            |id: &str| id == "ImportError" || id == "ModuleNotFoundError" || id == "Exception";
        match ty {
            past::Expr::Name(n) if hit(n.id.as_str()) => return true,
            past::Expr::Tuple(tup) => {
                for e in &tup.elts {
                    if let past::Expr::Name(n) = e {
                        if hit(n.id.as_str()) {
                            return true;
                        }
                    }
                }
            }
            _ => {}
        }
    }
    false
}

/// 收集一段语句里（深度任意）所有 `Import` / `ImportFrom` 的行号——真源这里用 `ast.walk`，
/// 但只塞进**集合**，故顺序无关。
pub(crate) struct ImportLinenos<'a> {
    pub(crate) ls: &'a LineStarts,
    pub(crate) out: Vec<u32>,
}

impl past::Visitor for ImportLinenos<'_> {
    fn visit_stmt(&mut self, node: past::Stmt) {
        match &node {
            past::Stmt::Import(i) => {
                for _ in &i.names {
                    self.out
                        .push(self.ls.line_of(u32::from(node.range().start())));
                }
            }
            past::Stmt::ImportFrom(_) => {
                self.out
                    .push(self.ls.line_of(u32::from(node.range().start())));
            }
            _ => {}
        }
        self.generic_visit_stmt(node);
    }
}

pub(crate) enum Ev {
    Raise(u32, String),
    Import(Vec<(String, u32)>),
    ImportFrom(String, u32),
    Call(u32, String, bool),
}

/// ---- 共享的「补下钻」助手 ----
///
/// `rustpython-ast` 生成的 visitor 里这些 `generic_visit_*` 是**空实现**（见本文件顶部说明），
/// 故每个自写的 Visitor 都要补。**抽成函数是为了不让两份实现漂移**：
/// `Collector`（AST 事实）与 `MetricCollector`（规模/复杂度）共用同一套下钻。
pub(crate) fn d_comprehension<V: past::Visitor>(v: &mut V, node: past::Comprehension) {
    // CPython `comprehension._fields` = target, iter, ifs, is_async
    v.visit_expr(node.target.clone());
    v.visit_expr(node.iter.clone());
    for e in &node.ifs {
        v.visit_expr(e.clone());
    }
}

pub(crate) fn d_withitem<V: past::Visitor>(v: &mut V, node: past::WithItem) {
    // CPython `withitem._fields` = context_expr, optional_vars
    v.visit_expr(node.context_expr.clone());
    if let Some(x) = &node.optional_vars {
        v.visit_expr(x.as_ref().clone());
    }
}

pub(crate) fn d_keyword<V: past::Visitor>(v: &mut V, node: past::Keyword) {
    // CPython `keyword._fields` = arg, value（arg 只是名字）
    v.visit_expr(node.value.clone());
}

pub(crate) fn d_arg<V: past::Visitor>(v: &mut V, node: past::Arg) {
    // CPython `arg._fields` = arg, annotation, type_comment
    if let Some(a) = &node.annotation {
        v.visit_expr(a.as_ref().clone());
    }
}

pub(crate) fn d_arguments<V: past::Visitor>(v: &mut V, node: past::Arguments) {
    // CPython `arguments._fields` = posonlyargs, args, vararg, kwonlyargs,
    //                             kw_defaults, kwarg, defaults
    // rustpython 把 default 嵌在 `ArgWithDefault` 里、没有独立的 `defaults` 字段，
    // 故按 CPython 的字段顺序重排（先全部 annotation，再 kw_defaults，最后 defaults）。
    for a in &node.posonlyargs {
        v.visit_arg(a.def.clone());
    }
    for a in &node.args {
        v.visit_arg(a.def.clone());
    }
    if let Some(x) = &node.vararg {
        v.visit_arg(x.as_ref().clone());
    }
    for a in &node.kwonlyargs {
        v.visit_arg(a.def.clone());
    }
    for a in &node.kwonlyargs {
        if let Some(d) = &a.default {
            v.visit_expr(d.as_ref().clone());
        }
    }
    if let Some(k) = &node.kwarg {
        v.visit_arg(k.as_ref().clone());
    }
    for a in node.posonlyargs.iter().chain(node.args.iter()) {
        if let Some(d) = &a.default {
            v.visit_expr(d.as_ref().clone());
        }
    }
}

pub(crate) fn d_match_case<V: past::Visitor>(v: &mut V, node: past::MatchCase) {
    // CPython `match_case._fields` = pattern, guard, body
    v.visit_pattern(node.pattern.clone());
    if let Some(g) = &node.guard {
        v.visit_expr(g.as_ref().clone());
    }
    for st in &node.body {
        v.visit_stmt(st.clone());
    }
}

pub(crate) struct Collector<'a> {
    pub(crate) ls: &'a LineStarts,
    pub(crate) depth: usize,
    pub(crate) seq: usize,
    pub(crate) evs: Vec<(usize, usize, Ev)>,
    pub(crate) guarded: BTreeSet<u32>,
}

impl Collector<'_> {
    pub(crate) fn enter(&mut self) -> usize {
        let d = self.depth;
        self.depth += 1;
        d
    }
    pub(crate) fn exit(&mut self) {
        self.depth -= 1;
    }
    pub(crate) fn push(&mut self, d: usize, ev: Ev) {
        let s = self.seq;
        self.seq += 1;
        self.evs.push((d, s, ev));
    }
}
