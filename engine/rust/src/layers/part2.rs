use super::*;

/// L6：引擎阶不反向 import 入口面。
pub(crate) fn l6_issues(root: &Path, ctx: &mut GlobCtx, issues: &mut Vec<String>) {
    for rel in ctx.one("desktop/src/core/*.py") {
        let Ok(src) = std::fs::read_to_string(root.join(&rel)) else {
            continue;
        };
        for (lineno, name) in pysrc::entry_imports(&src) {
            issues.push(format!(
                "L6 引擎阶反向 import 入口面件：{}:{} import {}（修复指引：入口可替换，core 不得依赖它——改由 CLI 层注入）",
                rel, lineno, name
            ));
        }
    }
}

/// L7：退役阶不被在役阶依赖；status 须在词表内。
pub(crate) fn l7_issues(doc: &Json, tiers: &[&Json], issues: &mut Vec<String>) {
    let retired: HashSet<String> = tiers
        .iter()
        .filter(|t| plain_str_opt(get(t, "status")) == "retired")
        .map(|t| plain_str_opt(get(t, "id")))
        .collect();
    let status_vocab = str_list(get(doc, "vocabulary").and_then(|v| get(v, "status")));
    for tier in tiers {
        let status = plain_str_opt(get(tier, "status"));
        if status == "retired" {
            continue;
        }
        for dep in arr_items(get(tier, "depends_on")) {
            if retired.contains(&plain_str(dep)) {
                issues.push(format!(
                    "L7 在役阶 {} 依赖了退役阶 {}（修复指引：把该能力改依赖重分派后的阶）",
                    plain_str_opt(get(tier, "id")),
                    plain_str(dep)
                ));
            }
        }
        if !status_vocab.contains(&status) {
            issues.push(format!(
                "L7 阶 {} 的 status 越词表：{}",
                plain_str_opt(get(tier, "id")),
                status
            ));
        }
    }
}

/// L8：judged_by 须解析为现存 check 或已登记 assertion。
pub(crate) fn l8_issues(root: &Path, doc: &Json, tiers: &[&Json], issues: &mut Vec<String>) {
    let checks = verify_checks(root);
    let assertion_ids = assertion_id_set(root);
    for (owner, reference) in judge_refs(doc, tiers) {
        judge_ref_issues(&owner, &reference, &checks, &assertion_ids, issues);
    }
}

/// verify.sh 里的 check 定义编号集合（缺件 → 空集）。
fn verify_checks(root: &Path) -> HashSet<String> {
    if root.join(VERIFY_REL).exists() {
        std::fs::read_to_string(root.join(VERIFY_REL))
            .map(|t| {
                check_def_re()
                    .captures_iter(&t)
                    .map(|c| c[1].to_string())
                    .collect()
            })
            .unwrap_or_default()
    } else {
        HashSet::new()
    }
}

/// 断言表登记的 assertion id 集合（缺件 → 空集）。
fn assertion_id_set(root: &Path) -> HashSet<String> {
    if root.join(ASSERTIONS_REL).is_file() {
        jsonread::read_file(root, ASSERTIONS_REL)
            .map(|d| {
                arr_items(get(&d, "assertions"))
                    .iter()
                    .map(|a| plain_str_opt(get(a, "id")))
                    .collect()
            })
            .unwrap_or_default()
    } else {
        HashSet::new()
    }
}

/// 三处 judged_by 引用：阶 / 资产子级 / 纵切件。
fn judge_refs(doc: &Json, tiers: &[&Json]) -> Vec<(String, String)> {
    let mut refs: Vec<(String, String)> = Vec::new();
    for tier in tiers {
        for r in arr_items(get(tier, "judged_by")) {
            refs.push((plain_str_opt(get(tier, "id")), plain_str(r)));
        }
    }
    for lv in arr_items(get(doc, "asset_levels")) {
        for r in arr_items(get(lv, "judged_by")) {
            refs.push((plain_str_opt(get(lv, "id")), plain_str(r)));
        }
    }
    for comp in arr_items(get(doc, "crosscut").and_then(|c| get(c, "components"))) {
        for r in arr_items(get(comp, "judged_by")) {
            refs.push((plain_str_opt(get(comp, "id")), plain_str(r)));
        }
    }
    refs
}

/// 单条 judged_by：checkN 须在 verify.sh 内 / assertion:<id> 须已登记 / 其余形式非法。
fn judge_ref_issues(
    owner: &str,
    reference: &str,
    checks: &HashSet<String>,
    assertion_ids: &HashSet<String>,
    issues: &mut Vec<String>,
) {
    if let Some(c) = judge_check_re().captures(reference) {
        if !checks.contains(&c[1]) {
            issues.push(format!(
                "L8 {} 的判据 {} 在 {} 中不存在（修复指引：改指向真实 check）",
                owner, reference, VERIFY_REL
            ));
        }
    } else if let Some(rest) = reference.strip_prefix("assertion:") {
        if !assertion_ids.contains(rest) {
            issues.push(format!(
                "L8 {} 的判据 {} 未登记（修复指引：在 {} 补该断言）",
                owner, reference, ASSERTIONS_REL
            ));
        }
    } else {
        issues.push(format!(
            "L8 {} 的判据形式不合法：{}（修复指引：写成 checkN 或 assertion:<id>）",
            owner, reference
        ));
    }
}

/// L10：生成区须与实时渲染一致。
pub(crate) fn l10_issues(root: &Path, doc: &Json, issues: &mut Vec<String>) {
    if !root.join(DOC_REL).exists() {
        issues.push(format!(
            "L10 缺阶梯文档 {}（修复指引：补件并跑 nf layers --write）",
            DOC_REL
        ));
    } else {
        let body = std::fs::read_to_string(root.join(DOC_REL)).unwrap_or_default();
        let got = region_of(&body);
        let want = render_markdown(doc);
        match got {
            None => issues.push(format!(
                "L10 {} 缺生成区标记 {} / {}（修复指引：补标记后跑 nf layers --write）",
                DOC_REL, MARK_BEGIN, MARK_END
            )),
            Some(g) if g.trim() != want.trim() => issues.push(format!(
                "L10 {} 生成区与实时渲染不一致（修复指引：跑 nf layers --write 刷新）",
                DOC_REL
            )),
            Some(_) => {}
        }
    }
}

/// 真源 `_walk` 的等价物（含 `walked` / `reported_cycles` 两个集合与后序标脏）。
pub(crate) struct CycleWalker<'a> {
    pub(crate) order: &'a HashMap<String, i64>,
    pub(crate) graph: &'a HashMap<String, Vec<String>>,
    pub(crate) walked: HashSet<String>,
    pub(crate) reported: HashSet<String>,
    pub(crate) issues: &'a mut Vec<String>,
}

impl CycleWalker<'_> {
    pub(crate) fn walk(&mut self, tid: &str, stack: &[String]) {
        if stack.iter().any(|s| s == tid) {
            let mut path: Vec<String> = stack.to_vec();
            path.push(tid.to_string());
            let joined = path.join(" → ");
            if !self.reported.contains(&joined) {
                self.reported.insert(joined.clone());
                self.issues.push(format!(
                    "L4 依赖图存在环：{}（修复指引：断开上行依赖）",
                    joined
                ));
            }
            return;
        }
        if self.walked.contains(tid) {
            return;
        }
        let deps = self.graph.get(tid).cloned().unwrap_or_default();
        for dep in deps {
            if self.order.contains_key(&dep) {
                let mut next: Vec<String> = stack.to_vec();
                next.push(tid.to_string());
                self.walk(&dep, &next);
            }
        }
        self.walked.insert(tid.to_string());
    }
}

/// 真源 `_region_of`：取生成区正文；缺标记 → `None`。
pub(crate) fn region_of(text: &str) -> Option<String> {
    if !text.contains(MARK_BEGIN) || !text.contains(MARK_END) {
        return None;
    }
    let after = text.splitn(2, MARK_BEGIN).nth(1)?;
    Some(after.splitn(2, MARK_END).next()?.to_string())
}

// ---------------------------------------------------------------- 渲染器

/// 真源 `_table`。
pub(crate) fn table(rows: &[Vec<String>], header: &[&str]) -> Vec<String> {
    let mut out = vec![
        format!("| {} |", header.join(" | ")),
        format!("|{}|", vec!["---"; header.len()].join("|")),
    ];
    for r in rows {
        out.push(format!("| {} |", r.join(" | ")));
    }
    out
}

pub(crate) fn backtick_join(items: &[&Json]) -> String {
    items
        .iter()
        .map(|g| format!("`{}`", plain_str(g)))
        .collect::<Vec<_>>()
        .join("、")
}

/// 真源 `render_markdown`：把阶梯真源渲染成 markdown 生成区（确定性）。
pub(crate) fn render_markdown(doc: &Json) -> String {
    let mut lines: Vec<String> = Vec::new();
    lines.push("### 抽象轴：四阶".into());
    lines.push(String::new());
    let mut rows: Vec<Vec<String>> = Vec::new();
    for t in arr_items(get(doc, "tiers")) {
        rows.push(vec![
            format!("**{}**", plain_str_opt(get(t, "name"))),
            backtick_join(&arr_items(get(t, "source").and_then(|s| get(s, "globs")))),
            backtick_join(&arr_items(
                get(t, "interface").and_then(|s| get(s, "globs")),
            )),
            arr_items(get(t, "judged_by"))
                .iter()
                .map(|v| plain_str(v))
                .collect::<Vec<_>>()
                .join("、"),
            format!(
                "{}（{}）",
                plain_str_opt(get(t, "status")),
                plain_str_opt(get(t, "change_tier"))
            ),
        ]);
    }
    lines.extend(table(
        &rows,
        &[
            "阶",
            "真源面",
            "接口面（跨阶唯一可依赖）",
            "既有判据",
            "状态 / 变更档",
        ],
    ));
    lines.push(String::new());
    lines.push("### 资产阶五子级（同一格内异质，分开看代价）".into());
    lines.push(String::new());
    let mut rows2: Vec<Vec<String>> = Vec::new();
    for lv in arr_items(get(doc, "asset_levels")) {
        rows2.push(vec![
            format!("**{}**", plain_str_opt(get(lv, "name"))),
            backtick_join(&arr_items(get(lv, "globs"))),
            arr_items(get(lv, "judged_by"))
                .iter()
                .map(|v| plain_str(v))
                .collect::<Vec<_>>()
                .join("、"),
            py_str(get(lv, "note")),
        ]);
    }
    lines.extend(table(&rows2, &["子级", "真源面", "既有判据", "口径"]));
    lines.push(String::new());
    lines.push("### 入口面（只登记角色，永不作为真源）".into());
    lines.push(String::new());
    let mut rows3: Vec<Vec<String>> = Vec::new();
    for sf in arr_items(get(doc, "surfaces")) {
        rows3.push(vec![
            format!("**{}**", plain_str_opt(get(sf, "name"))),
            backtick_join(&arr_items(get(sf, "entries"))),
            arr_items(get(sf, "serves"))
                .iter()
                .map(|v| plain_str(v))
                .collect::<Vec<_>>()
                .join("、"),
            py_str(get(sf, "note")),
        ]);
    }
    lines.extend(table(&rows3, &["面", "入口件", "服务阶", "口径"]));
    lines.push(String::new());
    lines.push("### 验证纵切（贯穿四阶，不是层）".into());
    lines.push(String::new());
    let mut rows4: Vec<Vec<String>> = Vec::new();
    for comp in arr_items(get(doc, "crosscut").and_then(|c| get(c, "components"))) {
        rows4.push(vec![
            format!("**{}**", plain_str_opt(get(comp, "id"))),
            format!("`{}`", plain_str_opt(get(comp, "artifact"))),
            arr_items(get(comp, "judged_by"))
                .iter()
                .map(|v| plain_str(v))
                .collect::<Vec<_>>()
                .join("、"),
        ]);
    }
    lines.extend(table(&rows4, &["件", "落点", "既有判据"]));
    lines.push(String::new());
    lines.push(
        "> 本区由 `nf layers --write` 渲染，禁止手改；真源 = `protocol/LAYERS.json`。".into(),
    );
    lines.join("\n")
}

// ---------------------------------------------------------------- CLI 面

/// 真源 `scan`/`_scan_impl` → `(issues, stats)`。
pub(crate) fn scan(root: &Path) -> (Vec<String>, Json) {
    let doc = match load(root) {
        Ok(d) => d,
        Err(e) => {
            return (
                vec![e],
                Json::Object(vec![
                    ("tiers".into(), Json::Int(0)),
                    ("asset_levels".into(), Json::Int(0)),
                    ("surfaces".into(), Json::Int(0)),
                ]),
            )
        }
    };
    let issues = rule_issues(root, &doc);
    let stats = Json::Object(vec![
        (
            "tiers".into(),
            Json::Int(arr_items(get(&doc, "tiers")).len() as i64),
        ),
        (
            "asset_levels".into(),
            Json::Int(arr_items(get(&doc, "asset_levels")).len() as i64),
        ),
        (
            "surfaces".into(),
            Json::Int(arr_items(get(&doc, "surfaces")).len() as i64),
        ),
        (
            "crosscut".into(),
            Json::Int(
                arr_items(get(&doc, "crosscut").and_then(|c| get(c, "components"))).len() as i64,
            ),
        ),
        (
            "rules".into(),
            Json::Int(arr_items(get(&doc, "rules")).len() as i64),
        ),
        (
            "derived".into(),
            Json::Int(arr_items(get(&doc, "derived")).len() as i64),
        ),
    ]);
    (issues, stats)
}

/// `nf layers --verify --json` 的输出字节（`print` 的换行也含在内）。
pub(crate) fn verify_bytes(root: &Path) -> Vec<u8> {
    let (issues, stats) = scan(root);
    let doc = Json::Object(vec![
        ("kind".into(), Json::Str("layers-verify".into())),
        ("ok".into(), Json::Bool(issues.is_empty())),
        (
            "issues".into(),
            Json::Array(issues.iter().map(|s| Json::Str(s.clone())).collect()),
        ),
        ("stats".into(), stats),
    ]);
    doc.dumps_file().into_bytes()
}
