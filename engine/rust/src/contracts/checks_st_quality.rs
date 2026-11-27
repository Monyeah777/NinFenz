//! ST 制卡质量（st-quality）判据。
//!
//! 自 `contracts.rs` 按族拆出：判据实现逐字搬运，逻辑与文案未改；由父模块 glob 引入分派面。

use crate::jsonread;
use crate::pyjson::Json;
use crate::pyval::{arr_is_empty, arr_items, get, obj_is_empty, py_str, str_list};
use std::path::Path;

// ---------------------------------------------------------------- st-quality

pub(super) const ST_REL: &str = "protocol/st_quality.json";
pub(super) const ST_SCHEMA: &str = "nf-st-quality/1";
pub(super) const ST_ARTIFACT_REL: &str = "docs/examples/mvu-output/mvu_variables.json";

/// 真源 `_c_st_quality`：把 `st_quality.scan` 的三元组压成契约裁决。
pub(super) fn st_quality(root: &Path) -> (bool, String) {
    match st_quality_scan(root) {
        Ok((issues, _warns, stats)) => {
            let ok = issues.is_empty();
            let detail = if ok {
                let lv = |k: &str| {
                    stats
                        .by_level
                        .iter()
                        .find(|(n, _)| n == k)
                        .map(|(_, v)| *v)
                        .unwrap_or(0)
                };
                format!(
                    "规则 {} 条（M {} / S {} / R {}）· 落产物判 {}",
                    stats.rules,
                    lv("M"),
                    lv("S"),
                    lv("R"),
                    stats.artifact_checked
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
        // 真源此处由 `_run_impl` 的 except 兜住。**错误路径的措辞不做逐字节承诺**：
        // 只在输入损坏（非法 JSON / 非对象）时可达，当前语料走不到。
        Err(e) => (false, format!("契约执行异常：{}", e)),
    }
}

#[derive(Default, Clone, Debug)]
pub(super) struct StStats {
    rules: usize,
    by_level: Vec<(String, i64)>,
    artifact_checked: usize,
}

/// 真源 `st_quality.scan` 的等价物。
pub(super) fn st_quality_scan(root: &Path) -> Result<(Vec<String>, Vec<String>, StStats), String> {
    let mut issues: Vec<String> = Vec::new();
    let mut warns: Vec<String> = Vec::new();
    let mut stats = StStats::default();

    let path = root.join(ST_REL);
    if !path.is_file() {
        return Ok((vec![format!("缺 ST 制卡质量规范 {}", ST_REL)], warns, stats));
    }
    let d = jsonread::read_file(root, ST_REL).ok_or_else(|| format!("{} 不是合法 JSON", ST_REL))?;
    let Json::Object(_) = &d else {
        return Err(format!("{} 不是对象", ST_REL));
    };
    if obj_is_empty(&d) {
        // 真源 `if not d:` —— 空对象与缺件同判
        return Ok((vec![format!("缺 ST 制卡质量规范 {}", ST_REL)], warns, stats));
    }

    let levels = str_list(get(&d, "level_vocabulary"));
    let scopes = str_list(get(&d, "scope_vocabulary"));
    let checks = str_list(get(&d, "check_vocabulary"));
    st_vocab_issues(&d, &levels, &scopes, &checks, &mut issues);

    let mut seen: Vec<String> = Vec::new();
    st_level_slots(&levels, &mut stats);
    let mut arts: Vec<String> = Vec::new();
    st_rules_scan(
        &d, &levels, &scopes, &mut seen, &mut arts, &mut stats, &mut issues,
    );
    st_art_checks(root, &arts, &mut issues);
    issues.extend(check_checklist(root, &d));
    st_pending_warns(&d, &mut warns);
    stats.rules = seen.len();
    stats.artifact_checked = arts.len();
    Ok((issues, warns, stats))
}

/// 规范顶层：schema 号 + 三张词表 + draft 待补清单。
fn st_vocab_issues(
    d: &Json,
    levels: &[String],
    scopes: &[String],
    checks: &[String],
    issues: &mut Vec<String>,
) {
    if py_str(get(d, "schema")) != ST_SCHEMA {
        issues.push(format!("规范 schema 不匹配（期望 {}）", ST_SCHEMA));
    }
    if levels != ["M", "S", "R"] {
        issues.push("level 词表必须为 M/S/R".into());
    }
    if scopes != ["C", "W", "V", "X"] {
        issues.push("scope 词表必须为 C/W/V/X".into());
    }
    if checks != ["declaration", "artifact"] {
        issues.push("check 词表必须为 declaration/artifact".into());
    }
    if py_str(get(d, "status")) == "draft" && arr_is_empty(get(d, "pending")) {
        issues.push("status=draft 但 pending 为空——草案必须写明还差什么".into());
    }
}

/// 按 level 词表初始化分布计数槽。
fn st_level_slots(levels: &[String], stats: &mut StStats) {
    for k in levels {
        if !stats.by_level.iter().any(|(n, _)| n == k) {
            stats.by_level.push((k.clone(), 0));
        }
    }
}

/// 规则面：id 唯一 + scope/level 词表与前缀 + 必填字段 + artifact 规则收集。
fn st_rules_scan(
    d: &Json,
    levels: &[String],
    scopes: &[String],
    seen: &mut Vec<String>,
    arts: &mut Vec<String>,
    stats: &mut StStats,
    issues: &mut Vec<String>,
) {
    for r in arr_items(get(d, "rules")) {
        let (rid, tag) = st_rule_identity(&r, seen, issues);
        st_rule_fields_issues(&r, &tag, &rid, levels, scopes, stats, issues);
        if py_str(get(&r, "check")) == "artifact" {
            arts.push(rid);
        }
    }
}

/// 规则 id 面：返回 (id, 报错用标签)，并登记去重。
fn st_rule_identity(
    r: &Json,
    seen: &mut Vec<String>,
    issues: &mut Vec<String>,
) -> (String, String) {
    let rid = py_str(get(r, "id"));
    let tag = if rid.is_empty() {
        "(无名)".to_string()
    } else {
        rid.clone()
    };
    if seen.contains(&rid) {
        issues.push(format!("规则 id 重复：{}", rid));
    }
    seen.push(rid.clone());
    (rid, tag)
}

/// 规则字段面：scope / level / rule-basis-check。
fn st_rule_fields_issues(
    r: &Json,
    tag: &str,
    rid: &str,
    levels: &[String],
    scopes: &[String],
    stats: &mut StStats,
    issues: &mut Vec<String>,
) {
    let scope = py_str(get(r, "scope"));
    if !scopes.contains(&scope) {
        issues.push(format!("{} scope 越词表：{}", tag, scope));
    } else if !rid.is_empty() && !rid.starts_with(&scope) {
        issues.push(format!(
            "{} 的 id 前缀与 scope 不一致（应 {} 开头）",
            tag, scope
        ));
    }
    let lv = py_str(get(r, "level"));
    if !levels.contains(&lv) {
        issues.push(format!("{} level 越词表：{}", tag, lv));
    } else if let Some(slot) = stats.by_level.iter_mut().find(|(n, _)| *n == lv) {
        slot.1 += 1;
    }
    for k in ["rule", "basis", "check"] {
        if py_str(get(r, k)).trim().is_empty() {
            issues.push(format!("{} 缺必填字段：{}", tag, k));
        }
    }
}

/// artifact 类规则的附加核对（V2 走样本件检查）。
fn st_art_checks(root: &Path, arts: &[String], issues: &mut Vec<String>) {
    for rid in arts {
        if rid == "V2" {
            issues.extend(check_v2(root));
        }
    }
}

/// 草案待补项的 warns。
fn st_pending_warns(d: &Json, warns: &mut Vec<String>) {
    if !arr_is_empty(get(d, "pending")) {
        let p = arr_items(get(d, "pending"));
        let head: Vec<String> = p.iter().take(2).map(|v| py_str(Some(v))).collect();
        warns.push(format!(
            "规范为草案：{} 项待补（{}）",
            p.len(),
            head.join("；")
        ));
    }
}

/// 真源 `_check_v2`：`initial` 键集合必须 ⊆ 变量名集合。
pub(super) fn check_v2(root: &Path) -> Vec<String> {
    let path = root.join(ST_ARTIFACT_REL);
    if !path.is_file() {
        return Vec::new();
    }
    let Some(doc) = jsonread::read_file(root, ST_ARTIFACT_REL) else {
        return Vec::new();
    };
    // 真源 `str(v.get("name"))` **没有** `or ""` 兜底 ⇒ 缺 name 时是字面量 "None"
    let names: Vec<String> = arr_items(get(&doc, "variables"))
        .iter()
        .map(|v| match get(v, "name") {
            Some(Json::Str(s)) => s.clone(),
            Some(Json::Null) | None => "None".to_string(),
            Some(other) => py_str(Some(other)),
        })
        .collect();
    let init = match get(&doc, "initial") {
        Some(Json::Object(p)) => p.clone(),
        _ => Vec::new(),
    };
    let mut extra: Vec<String> = init
        .iter()
        .map(|(k, _)| k.clone())
        .filter(|k| !names.contains(k))
        .collect();
    extra.sort();
    if extra.is_empty() {
        Vec::new()
    } else {
        vec![format!(
            "V2：初始值含未声明变量 {}（initial 与变量表不一一对应）",
            extra.join("、")
        )]
    }
}

/// 真源 `_check_checklist`：清单必须覆盖全部规则 id。
pub(super) fn check_checklist(root: &Path, d: &Json) -> Vec<String> {
    let rel = py_str(get(d, "checklist"));
    if rel.is_empty() {
        return vec!["缺 checklist 字段——人工自查清单必须登记（否则 S 级规则无处落地）".into()];
    }
    let path = root.join(&rel);
    if !path.is_file() {
        return vec![format!("自查清单不存在：{}", rel)];
    }
    let Ok(text) = std::fs::read_to_string(&path) else {
        return vec![format!("自查清单不存在：{}", rel)];
    };
    let mut miss: Vec<String> = Vec::new();
    for r in arr_items(get(d, "rules")) {
        // 真源 `str(r.get("id"))`：缺 id → "None"（真值）⇒ 会去找 "| None |"
        let rid = match get(r, "id") {
            Some(Json::Str(s)) => s.clone(),
            Some(Json::Null) | None => "None".to_string(),
            Some(other) => py_str(Some(other)),
        };
        if !rid.is_empty() && !text.contains(&format!("| {} |", rid)) {
            miss.push(rid);
        }
    }
    if miss.is_empty() {
        Vec::new()
    } else {
        vec![format!("自查清单未覆盖规则：{}", miss.join("、"))]
    }
}
