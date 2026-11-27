//! 认知族与条件先行（cognition / state-front）判据。
//!
//! 自 `contracts.rs` 按族拆出：判据实现逐字搬运，逻辑与文案未改；由父模块 glob 引入分派面。

use crate::jsonread;
use crate::pyjson::Json;
use crate::pyval::{arr_items, get, obj_is_empty, plain_str, py_int_or, py_str};
use std::path::Path;

// ---------------------------------------------------------------- cognition

pub(super) const GLOSSARY_REL: &str = "protocol/glossary.json";
pub(super) const MODES_REL: &str = "protocol/execution_modes.json";
pub(super) const G_SCHEMA: &str = "nf-glossary/1";
pub(super) const M_SCHEMA: &str = "nf-execution-modes/1";

/// 真源 `_c_cognition`：术语表 + 执行分档。
pub(super) fn cognition(root: &Path) -> (bool, String) {
    let (issues, g, m) = cognition_scan(root);
    let ok = issues.is_empty();
    let detail = if ok {
        format!(
            "术语 {} 条（使用面 {}）· 执行档 {}（合格实例 {}）",
            g.terms, g.uses, m.modes, m.instances_ok
        )
    } else {
        issues
            .iter()
            .take(2)
            .cloned()
            .collect::<Vec<_>>()
            .join("; ")
    };
    (ok, detail)
}

#[derive(Default, Clone, Debug)]
pub(super) struct GlossaryStats {
    terms: usize,
    uses: usize,
}

#[derive(Default, Clone, Debug)]
pub(super) struct ModesStats {
    modes: usize,
    instances_ok: usize,
}

/// 真源 `cognition.scan`。真源里那条 `_BLOCK` 正则**从未被使用**（真源自身的死代码），
/// 本线不移植——移植死代码等于把噪声固化。
pub(super) fn cognition_scan(root: &Path) -> (Vec<String>, GlossaryStats, ModesStats) {
    let (gi, _, gs) = verify_glossary(root);
    let (mi, _, ms) = verify_modes(root);
    let mut issues = gi;
    issues.extend(mi);
    (issues, gs, ms)
}

pub(super) fn doc_or_missing(root: &Path, rel: &str, missing_msg: String) -> Result<Json, Vec<String>> {
    if !root.join(rel).is_file() {
        return Err(vec![missing_msg]);
    }
    match jsonread::read_file(root, rel) {
        Some(d) if !obj_is_empty(&d) => Ok(d),
        _ => Err(vec![missing_msg]),
    }
}

/// 真源 `verify_glossary`。
pub(super) fn verify_glossary(root: &Path) -> (Vec<String>, Vec<String>, GlossaryStats) {
    let mut issues: Vec<String> = Vec::new();
    let mut stats = GlossaryStats::default();
    let Ok(doc) = doc_or_missing(root, GLOSSARY_REL, format!("缺术语表 {}", GLOSSARY_REL))
    else {
        return (
            vec![format!("缺术语表 {}", GLOSSARY_REL)],
            Vec::new(),
            stats,
        );
    };
    if py_str(get(&doc, "schema")) != G_SCHEMA {
        issues.push(format!("术语表 schema 不匹配（期望 {}）", G_SCHEMA));
    }
    if arr_items(get(&doc, "rules")).is_empty() {
        issues.push("术语表 rules 不得为空（登记纪律必须成文）".into());
    }
    let mut seen: Vec<String> = Vec::new();
    let mut uses = 0usize;
    for t in arr_items(get(&doc, "terms")) {
        glossary_term_issues(root, &t, &mut seen, &mut uses, &mut issues);
    }
    stats.terms = seen.len();
    stats.uses = uses;
    (issues, Vec::new(), stats)
}

/// 单条术语：非空 / 唯一 / 有定义 / source 逐字落地；used_in 逐件核对。
fn glossary_term_issues(
    root: &Path,
    t: &Json,
    seen: &mut Vec<String>,
    uses: &mut usize,
    issues: &mut Vec<String>,
) {
    let term = py_str(get(t, "term"));
    if term.is_empty() {
        issues.push("存在无 term 的条目".into());
        return;
    }
    if seen.contains(&term) {
        issues.push(format!("术语重复：{}", term));
    }
    seen.push(term.clone());
    if py_str(get(t, "definition")).trim().is_empty() {
        issues.push(format!("术语 {} 缺 definition", term));
    }
    glossary_source_issues(root, t, &term, issues);
    glossary_usage_issues(root, t, &term, uses, issues);
}

/// term 的定义 source：存在且逐字包含该术语。
fn glossary_source_issues(root: &Path, t: &Json, term: &str, issues: &mut Vec<String>) {
    let src = py_str(get(t, "source"));
    if !root.join(&src).is_file() {
        issues.push(format!("术语 {} 的 source 不存在：{}", term, src));
    } else if !read_text(root, &src).contains(term) {
        issues.push(format!(
            "术语 {} 未在其 source 中逐字出现：{}（定义必须落在真源里）",
            term, src
        ));
    }
}

/// used_in 面：每件须存在且逐字出现该术语；命中计入 uses。
fn glossary_usage_issues(
    root: &Path,
    t: &Json,
    term: &str,
    uses: &mut usize,
    issues: &mut Vec<String>,
) {
    // 真源 ui = t.get("used_in") or [] → 空串按假值落空表（不是「一项空路径」）
    let ui: Vec<String> = match get(t, "used_in") {
        Some(Json::Str(s)) if !s.is_empty() => vec![s.clone()],
        Some(Json::Array(a)) => a.iter().map(|v| plain_str(v)).collect(),
        _ => Vec::new(),
    };
    for rel in ui {
        if !root.join(&rel).is_file() {
            issues.push(format!("术语 {} 的 used_in 不存在：{}", term, rel));
        } else if !read_text(root, &rel).contains(term) {
            issues.push(format!(
                "术语 {} 的 used_in 未逐字出现该术语：{}（防登记没人用的行话）",
                term, rel
            ));
        } else {
            *uses += 1;
        }
    }
}

/// 真源 `verify_modes`。
pub(super) fn verify_modes(root: &Path) -> (Vec<String>, Vec<String>, ModesStats) {
    let mut issues: Vec<String> = Vec::new();
    let mut stats = ModesStats::default();
    let Ok(doc) = doc_or_missing(root, MODES_REL, format!("缺执行分档声明 {}", MODES_REL))
    else {
        return (
            vec![format!("缺执行分档声明 {}", MODES_REL)],
            Vec::new(),
            stats,
        );
    };
    if py_str(get(&doc, "schema")) != M_SCHEMA {
        issues.push(format!("执行分档 schema 不匹配（期望 {}）", M_SCHEMA));
    }
    let mut seen: Vec<String> = Vec::new();
    let mut insts = 0usize;
    for m in arr_items(get(&doc, "modes")) {
        let mid = py_str(get(m, "id"));
        if seen.contains(&mid) {
            issues.push(format!("mode id 重复：{}", mid));
        }
        seen.push(mid.clone());
        // 真源此处是 `str(b)`（无 falsy 兜底），故用 plain_str
        let blocks: Vec<String> = arr_items(get(m, "required_blocks"))
            .iter()
            .map(|b| plain_str(b))
            .collect();
        if blocks.is_empty() {
            issues.push(format!(
                "mode {} 缺 required_blocks（该档必备结构必须成文）",
                mid
            ));
        }
        let rows = arr_items(get(m, "instances"));
        if rows.is_empty() {
            issues.push(format!("mode {} 无实例（声明了档却没有件属于它）", mid));
        }
        for rel in rows.iter().map(|v| plain_str(v)) {
            if !root.join(&rel).is_file() {
                issues.push(format!("mode {} 的实例不存在：{}", mid, rel));
                continue;
            }
            let txt = read_text(root, &rel);
            let miss: Vec<String> = blocks
                .iter()
                .filter(|b| !txt.contains(*b))
                .cloned()
                .collect();
            if miss.is_empty() {
                insts += 1;
            } else {
                issues.push(format!(
                    "实例 {} 不属于 {} 档：缺结构块 {}",
                    rel,
                    mid,
                    miss.join("/")
                ));
            }
        }
    }
    stats.modes = seen.len();
    stats.instances_ok = insts;
    (issues, Vec::new(), stats)
}

pub(super) fn read_text(root: &Path, rel: &str) -> String {
    std::fs::read_to_string(root.join(rel)).unwrap_or_default()
}

// ---------------------------------------------------------------- state-front

pub(super) const STATE_FRONT_REL: &str = "protocol/state_front.json";
pub(super) const STATE_FRONT_SCHEMA: &str = "nf-state-front/1";
pub(super) const STATE_HEAD: &str = "## 状态块（条件先行摘要）";

/// 真源 `_c_state_front`：凡登记为 condition-first 的产物件，必须真的通过 `check_order`。
pub(super) fn state_front(root: &Path) -> (bool, String) {
    let (issues, stats) = state_front_scan(root);
    let ok = issues.is_empty();
    let detail = if ok {
        format!(
            "单件 {} · 族规则 {} · 族成员 {}",
            stats.declared, stats.family_rules, stats.family_members
        )
    } else {
        issues
            .iter()
            .take(2)
            .cloned()
            .collect::<Vec<_>>()
            .join("; ")
    };
    (ok, detail)
}

#[derive(Default, Clone, Debug)]
pub(super) struct StateFrontStats {
    declared: usize,
    family_rules: usize,
    family_members: usize,
}

pub(super) fn section_re() -> &'static regex::Regex {
    static RE: std::sync::OnceLock<regex::Regex> = std::sync::OnceLock::new();
    // 真源 `re.compile(r"^##\s+", re.M)` → Rust 的 (?m)
    RE.get_or_init(|| regex::Regex::new(r"(?m)^##\s+").expect("二级小节正则固定合法"))
}

/// 真源 `check_order`：状态块存在且位于**所有其它二级小节之前**。
pub(super) fn check_order(text: &str) -> Vec<String> {
    let Some(pos) = text.find(STATE_HEAD) else {
        return vec!["缺状态块——无状态文本代理可前置".into()];
    };
    let before = section_re()
        .find_iter(text)
        .filter(|m| m.start() < pos && !text[m.start()..].starts_with("## 状态块"))
        .count();
    if before > 0 {
        vec![format!(
            "状态块未前置：它出现在 {} 个二级小节之后（条件先行要求置于资料之前）",
            before
        )]
    } else {
        Vec::new()
    }
}

/// 真源 `state_front.scan`（其 `warns` 无消费者，本线不计）。
pub(super) fn state_front_scan(root: &Path) -> (Vec<String>, StateFrontStats) {
    let mut issues: Vec<String> = Vec::new();
    let mut stats = StateFrontStats::default();
    if !root.join(STATE_FRONT_REL).is_file() {
        return (vec![format!("缺条件先行声明 {}", STATE_FRONT_REL)], stats);
    }
    let Some(doc) = jsonread::read_file(root, STATE_FRONT_REL) else {
        return (vec![format!("缺条件先行声明 {}", STATE_FRONT_REL)], stats);
    };
    if py_str(get(&doc, "schema")) != STATE_FRONT_SCHEMA {
        issues.push("声明 schema 不匹配（期望 nf-state-front/1）".into());
    }
    let rows = arr_items(get(&doc, "declared"));
    let rules = arr_items(get(&doc, "family_rules"));

    let mut hits: Vec<String> = Vec::new();
    for r in &rules {
        hits.extend(family_rule_issues(root, r, &mut issues));
    }
    for rel in &hits {
        family_member_issues(root, rel, &mut issues);
    }
    for r in &rows {
        declared_row_issues(root, r, &mut issues);
    }
    stats.declared = rows.len();
    stats.family_rules = rules.len();
    stats.family_members = hits.len();
    (issues, stats)
}

/// 族规则：glob 非空 + 成员数达标；返回命中件供后续 condition-first 核对。
fn family_rule_issues(root: &Path, r: &Json, issues: &mut Vec<String>) -> Vec<String> {
    let g = py_str(get(r, "glob"));
    if g.is_empty() {
        issues.push("族规则缺 glob".into());
        return Vec::new();
    }
    let matched = crate::glob::expand(root, &g);
    let low = py_int_or(get(r, "min_members"), 1).max(0) as usize;
    if matched.len() < low {
        issues.push(format!(
            "族 {} 成员不足：{} < {}（修复指引：按 sources 重新生成）",
            g,
            matched.len(),
            low
        ));
    }
    matched
}

/// 族内件：condition-first 顺序核对。
fn family_member_issues(root: &Path, rel: &str, issues: &mut Vec<String>) {
    let bad = check_order(&read_text(root, rel));
    if !bad.is_empty() {
        issues.push(format!(
            "族内件未通过 condition-first：{}（{}）",
            rel, bad[0]
        ));
    }
}

/// 显式登记条目：path 非空 / 存在 / condition-first 顺序核对。
fn declared_row_issues(root: &Path, r: &Json, issues: &mut Vec<String>) {
    let rp = py_str(get(r, "path"));
    if rp.is_empty() {
        issues.push("声明条目缺 path".into());
        return;
    }
    if !root.join(&rp).is_file() {
        issues.push(format!("登记件不存在：{}", rp));
        return;
    }
    let bad = check_order(&read_text(root, &rp));
    if !bad.is_empty() {
        issues.push(format!(
            "登记为 condition-first 但未通过：{}（{}）",
            rp, bad[0]
        ));
    }
}
