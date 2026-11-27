//! 基础读取 / 注册表载入与静态一致性核对。

use super::*;

/// 真源 `_rel(root, rel)`。
pub fn rel_path(root: &Path, rel: &str) -> std::path::PathBuf {
    root.join(rel.replace('/', std::path::MAIN_SEPARATOR_STR))
}

/// 真源 `_read_text_cached`（本线不移植缓存层：它是纯函数优化，不改结论）。
pub fn read_text(root: &Path, rel: &str) -> String {
    std::fs::read(rel_path(root, rel))
        .map(|b| String::from_utf8_lossy(&b).into_owned())
        .unwrap_or_default()
}

/// 真源 `_read_json` → `(值, 错误)`。
pub fn read_json(root: &Path, rel: &str) -> (Json, String) {
    let p = rel_path(root, rel);
    match std::fs::read(&p) {
        Err(e) => (Json::Null, format!("不可读：{}", e)),
        Ok(b) => {
            let text = String::from_utf8_lossy(&b).into_owned();
            match serde_json::from_str::<serde_json::Value>(&text) {
                Ok(v) => match crate::jsonread::convert(&v) {
                    Ok(j) => (j, String::new()),
                    Err(e) => (Json::Null, format!("JSON 解析失败：{}", e)),
                },
                Err(e) => (Json::Null, format!("JSON 解析失败：{}", e)),
            }
        }
    }
}

pub(crate) fn obj_get<'a>(v: &'a Json, k: &str) -> Option<&'a Json> {
    match v {
        Json::Object(o) => o.iter().find(|(kk, _)| kk == k).map(|(_, vv)| vv),
        _ => None,
    }
}

pub(crate) fn arr_of(v: Option<&Json>) -> Vec<Json> {
    match v {
        Some(Json::Array(a)) => a.clone(),
        _ => Vec::new(),
    }
}

// ---------------------------------------------------------------- 形态清单

/// 真源 `load_registry`。
pub fn load_registry(root: &Path) -> Json {
    let (data, _) = read_json(root, REGISTRY_REL);
    if matches!(data, Json::Object(_)) {
        data
    } else {
        Json::Object(vec![])
    }
}

/// 真源 `registry_verify`。
pub fn registry_verify(root: &Path) -> (Vec<String>, Json) {
    let mut issues: Vec<String> = Vec::new();
    let reg = load_registry(root);
    if !matches!(reg, Json::Object(_)) || matches!(&reg, Json::Object(o) if o.is_empty()) {
        return (
            vec![format!("{} 缺失或不可解析（形态清单是真源）", REGISTRY_REL)],
            Json::Object(vec![]),
        );
    }
    let schema = obj_get(&reg, "schema").cloned().unwrap_or(Json::Null);
    if !pyval::py_eq(&schema, &Json::Str("nf-output-forms/1".to_string())) {
        issues.push(format!(
            "schema 应为 nf-output-forms/1，实为 {}",
            pyval::py_repr(&schema)
        ));
    }
    let cats = arr_of(obj_get(&reg, "categories"));
    let cat_ids = form_category_ids(&cats);
    if cat_ids.is_empty() {
        issues.push("categories 为空（形态必须有类别归属）".to_string());
    }
    category_entry_issues(&cats, &mut issues);
    let forms = arr_of(obj_get(&reg, "forms"));
    let mut seen: Vec<String> = Vec::new();
    let mut per_cat: Vec<(String, i64)> = Vec::new();
    let mut per_tier: Vec<(String, i64)> = Vec::new();
    let mut per_status: Vec<(String, i64)> = Vec::new();
    let mut unreachable = 0i64;
    verify_forms(
        &forms,
        &cat_ids,
        &mut issues,
        &mut seen,
        &mut per_cat,
        &mut per_tier,
        &mut per_status,
        &mut unreachable,
    );
    let stats = Json::Object(vec![
        ("forms".to_string(), Json::Int(forms.len() as i64)),
        ("categories".to_string(), Json::Int(cat_ids.len() as i64)),
        (
            "by_category".to_string(),
            Json::Object(
                per_cat
                    .into_iter()
                    .map(|(k, v)| (k, Json::Int(v)))
                    .collect(),
            ),
        ),
        (
            "by_tier".to_string(),
            Json::Object(
                per_tier
                    .into_iter()
                    .map(|(k, v)| (k, Json::Int(v)))
                    .collect(),
            ),
        ),
        (
            "by_status".to_string(),
            Json::Object(
                per_status
                    .into_iter()
                    .map(|(k, v)| (k, Json::Int(v)))
                    .collect(),
            ),
        ),
        ("unreachable".to_string(), Json::Int(unreachable)),
    ]);
    (issues, stats)
}

/// 形态条目的 id / 类别 / 档位 / 状态 / 规范入口 / 可达性实证核对。
pub(crate) fn verify_forms(
    forms: &[Json],
    cat_ids: &[String],
    issues: &mut Vec<String>,
    seen: &mut Vec<String>,
    per_cat: &mut Vec<(String, i64)>,
    per_tier: &mut Vec<(String, i64)>,
    per_status: &mut Vec<(String, i64)>,
    unreachable: &mut i64,
) {
    fn bump(v: &mut Vec<(String, i64)>, k: String) {
        match v.iter_mut().find(|(n, _)| *n == k) {
            Some(e) => e.1 += 1,
            None => v.push((k, 1)),
        }
    }
    for f in forms {
        if !matches!(f, Json::Object(_)) {
            issues.push(format!("forms 条目非对象：{}", pyval::py_repr(f)));
            continue;
        }
        let fid_v = obj_get(f, "id").cloned().unwrap_or(Json::Null);
        if !pyval::py_truthy(&fid_v) {
            issues.push(format!("forms 条目缺 id：{}", pyval::py_repr(f)));
            continue;
        }
        let fid = pyval::plain_str(&fid_v);
        form_entry_issues(
            f, &fid, cat_ids, seen, per_cat, per_tier, per_status, unreachable, issues,
        );
    }
}

/// categories 去重 id 表（保持出现序）。
fn form_category_ids(cats: &[Json]) -> Vec<String> {
    let mut cat_ids: Vec<String> = Vec::new();
    for c in cats {
        if let Some(Json::Str(id)) = obj_get(c, "id") {
            if !cat_ids.contains(id) {
                cat_ids.push(id.clone());
            }
        }
    }
    cat_ids
}

/// categories 条目：对象形态 + id/name 真值。
fn category_entry_issues(cats: &[Json], issues: &mut Vec<String>) {
    for c in cats {
        let ok = matches!(obj_get(c, "id"), Some(v) if pyval::py_truthy(v))
            && matches!(obj_get(c, "name"), Some(v) if pyval::py_truthy(v));
        if !matches!(c, Json::Object(_)) || !ok {
            issues.push(format!("categories 条目缺 id/name：{}", pyval::py_repr(c)));
        }
    }
}

/// 单条形态：id 唯一 / 类别 / 档位 / 状态 / spec.uri / 可达性实证 + 分面计数。
#[allow(clippy::too_many_arguments)]
fn form_entry_issues(
    f: &Json,
    fid: &str,
    cat_ids: &[String],
    seen: &mut Vec<String>,
    per_cat: &mut Vec<(String, i64)>,
    per_tier: &mut Vec<(String, i64)>,
    per_status: &mut Vec<(String, i64)>,
    unreachable: &mut i64,
    issues: &mut Vec<String>,
) {
    if seen.contains(&fid.to_string()) {
        issues.push(format!("形态 id 重复：{}", fid));
    }
    seen.push(fid.to_string());
    let (cat, tier, status) = form_vocab_issues(f, fid, cat_ids, issues);
    let spec = obj_get(f, "spec").cloned().unwrap_or(Json::Object(vec![]));
    let status_is_unfit = matches!(&status, Json::Str(s) if s == "unfit");
    if !status_is_unfit
        && !pyval::py_truthy(&obj_get(&spec, "uri").cloned().unwrap_or(Json::Null))
    {
        issues.push(format!("{} 缺规范入口 spec.uri（不适面才可空）", fid));
    }
    form_evidence_issues(f, fid, unreachable, issues);
    bump_count(per_cat, pyval::plain_str(&cat));
    bump_count(per_tier, format!("{}", pyval::py_str(Some(&tier))));
    bump_count(per_status, format!("{}", pyval::py_str(Some(&status))));
}

/// 类别 / 档位 / 状态 三张词表核对；返回原值供后续判据。
fn form_vocab_issues(
    f: &Json,
    fid: &str,
    cat_ids: &[String],
    issues: &mut Vec<String>,
) -> (Json, Json, Json) {
    let cat = obj_get(f, "category").cloned().unwrap_or(Json::Null);
    if !matches!(&cat, Json::Str(s) if cat_ids.contains(s)) {
        issues.push(format!("{} 类别未在册：{}", fid, pyval::py_repr(&cat)));
    }
    let tier = obj_get(f, "tier").cloned().unwrap_or(Json::Null);
    if !matches!(&tier, Json::Str(s) if TIERS.contains(&s.as_str())) {
        issues.push(format!(
            "{} 档位非法：{}（预期 {}）",
            fid,
            pyval::py_repr(&tier),
            TIERS.join("/")
        ));
    }
    let status = obj_get(f, "status").cloned().unwrap_or(Json::Null);
    if !matches!(&status, Json::Str(s) if STATUSES.contains(&s.as_str())) {
        issues.push(format!("{} 状态非法：{}", fid, pyval::py_repr(&status)));
    }
    (cat, tier, status)
}

/// 可达性实证：缺键必报；显式 false 计入 unreachable。
fn form_evidence_issues(f: &Json, fid: &str, unreachable: &mut i64, issues: &mut Vec<String>) {
    let ev = obj_get(f, "evidence")
        .cloned()
        .unwrap_or(Json::Object(vec![]));
    if obj_get(&ev, "reachable").is_none() {
        issues.push(format!(
            "{} 缺可达性实证 evidence.reachable（不伪造：查不到也要记 false）",
            fid
        ));
    } else if matches!(obj_get(&ev, "reachable"), Some(Json::Bool(false))) {
        *unreachable += 1;
    }
}

/// 分面计数 +1。
fn bump_count(v: &mut Vec<(String, i64)>, k: String) {
    match v.iter_mut().find(|(n, _)| *n == k) {
        Some(e) => e.1 += 1,
        None => v.push((k, 1)),
    }
}
