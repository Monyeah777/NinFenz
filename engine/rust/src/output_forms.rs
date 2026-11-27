//! 产出形态面（output forms）—— 与真源 `desktop/src/core/output_forms.py` 的 `scan` 对账。
//!
//! ## 移植面按消费者界定（有工具，不是猜的）
//!
//! 用了 [`tools/trace_call_closure.py`](../../tools/trace_call_closure.py) 从入口 `scan` 算模块内
//! 调用闭包（**跟随模块级分派表**——否则会低估，见下）。实测结果：
//!
//! | | |
//! |---|---|
//! | 真源规模 | 1,496 行 / 69 个函数 |
//! | **闭包内** | **67 个函数 / 约 1,113 行** |
//! | 闭包外 | **2 个**：`render_outputs`（写盘）、`write_baseline`（重签基线）——**都属写面** |
//!
//! ⚠️ 闭包必须**跟随 `_FORM_CHECK` 这张模块级分派表**：`_verify_pack` 以
//! `_FORM_CHECK.get(form)` 间接调用 15 个格式校验器；只看函数体内的直接引用会漏掉它们全部
//! （约 270 行）。这正是 `trace_call_closure.py` 里那段「跟随模块级 dict 字面量」的由来。
//!
//! ## 本文件当前进度（分块移植，逐块验证）
//!
//! - ✅ 常量 + `_rel` / `_read_*` / `load_registry` / `registry_verify` / `detect`
//! - ✅ `_check_xml` / `_xml_guard` / `_check_graphml`（用 `xmlmini`）
//! - ⏳ 其余格式校验器（`_check_json` 需 JSON 重复键检测；`_check_toml` 需 TOML 解析）
//! - ⏳ 包级产出清单（`_pack_dirs` / `shared_face_key` / `pack_slice_index` / `_verify_pack` …）
//! - ⏳ `index_verify` / `baseline_verify` / `meter` / 生成器 / `scan`

use crate::pyjson::Json;
use crate::pyval;
use std::path::Path;

pub const REGISTRY_REL: &str = "protocol/output_forms.json";
pub const BASELINE_REL: &str = "protocol/output_forms_baseline.json";
pub const INDEX_REL: &str = "outputs/INDEX.json";

/// 机检档位（递增）；档位 = **本仓可做的判定强度**，不是「格式有多高级」。
pub const TIERS: [&str; 5] = ["T0", "T1", "T2", "T3", "T4"];

/// 形态状态（对外可判定口径）——真源 `STATUSES`。
pub const STATUSES: [&str; 7] = [
    "supported",
    "absorbed",
    "planned",
    "deferred",
    "unfit",
    "reference",
    "unreachable",
];

/// 真源 `_EXT_FORM`。
const EXT_FORM: [(&str, &str); 20] = [
    (".json", "json"),
    (".jsonl", "jsonl"),
    (".ndjson", "jsonl"),
    (".yaml", "yaml"),
    (".yml", "yaml"),
    (".toml", "toml"),
    (".csv", "csv"),
    (".tsv", "csv"),
    (".xml", "xml"),
    (".md", "markdown"),
    (".mmd", "mermaid"),
    (".dot", "graphviz-dot"),
    (".gv", "graphviz-dot"),
    (".graphml", "graphml"),
    (".svg", "svg"),
    (".txt", "text"),
    (".proto", "protobuf-proto3"),
    (".graphql", "graphql-sdl"),
    (".ttl", "turtle"),
    (".sql", "sql-ddl"),
];

/// 真源 `_FORM_MAX_TIER`。
const FORM_MAX_TIER: [(&str, &str); 22] = [
    ("json", "T2"),
    ("jsonl", "T2"),
    ("yaml", "T2"),
    ("toml", "T2"),
    ("csv", "T2"),
    ("xml", "T1"),
    ("svg", "T1"),
    ("markdown", "T1"),
    ("text", "T0"),
    ("json-schema", "T2"),
    ("vega-lite", "T3"),
    ("mermaid", "T3"),
    ("graphviz-dot", "T3"),
    ("graphml", "T3"),
    ("json-graph-format", "T3"),
    ("quant-metrics", "T3"),
    ("performance-report", "T4"),
    ("concept-closure", "T4"),
    ("system-card", "T3"),
    ("domain-spec", "T3"),
    ("domain-report", "T4"),
    ("combo-cert", "T4"),
];

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

fn obj_get<'a>(v: &'a Json, k: &str) -> Option<&'a Json> {
    match v {
        Json::Object(o) => o.iter().find(|(kk, _)| kk == k).map(|(_, vv)| vv),
        _ => None,
    }
}

fn arr_of(v: Option<&Json>) -> Vec<Json> {
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
    let mut cat_ids: Vec<String> = Vec::new();
    for c in &cats {
        if let Some(Json::Str(id)) = obj_get(c, "id") {
            if !cat_ids.contains(id) {
                cat_ids.push(id.clone());
            }
        }
    }
    if cat_ids.is_empty() {
        issues.push("categories 为空（形态必须有类别归属）".to_string());
    }
    for c in &cats {
        let ok = matches!(obj_get(c, "id"), Some(v) if pyval::py_truthy(v))
            && matches!(obj_get(c, "name"), Some(v) if pyval::py_truthy(v));
        if !matches!(c, Json::Object(_)) || !ok {
            issues.push(format!("categories 条目缺 id/name：{}", pyval::py_repr(c)));
        }
    }
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
fn verify_forms(
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
        if seen.contains(&fid) {
            issues.push(format!("形态 id 重复：{}", fid));
        }
        seen.push(fid.clone());
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
        let spec = obj_get(f, "spec").cloned().unwrap_or(Json::Object(vec![]));
        let status_is_unfit = matches!(&status, Json::Str(s) if s == "unfit");
        if !status_is_unfit
            && !pyval::py_truthy(&obj_get(&spec, "uri").cloned().unwrap_or(Json::Null))
        {
            issues.push(format!("{} 缺规范入口 spec.uri（不适面才可空）", fid));
        }
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
        let cat_key = pyval::plain_str(&cat);
        bump(per_cat, cat_key);
        bump(per_tier, format!("{}", pyval::py_str(Some(&tier))));
        bump(per_status, format!("{}", pyval::py_str(Some(&status))));
    }
}

// ---------------------------------------------------------------- 形态识别

/// 真源 `detect` → `(form_id, tier)`。
pub fn detect(root: &Path, rel: &str) -> (String, String) {
    let p = rel_path(root, rel);
    let ext = p
        .extension()
        .map(|e| format!(".{}", e.to_string_lossy().to_lowercase()))
        .unwrap_or_default();
    let mut form = EXT_FORM
        .iter()
        .find(|(e, _)| *e == ext)
        .map(|(_, f)| (*f).to_string())
        .unwrap_or_else(|| "text".to_string());
    if ext == ".json" {
        let (data, _) = {
            let text = std::fs::read(&p)
                .map(|b| String::from_utf8_lossy(&b).into_owned())
                .unwrap_or_default();
            match serde_json::from_str::<serde_json::Value>(&text) {
                Ok(v) => (
                    crate::jsonread::convert(&v).unwrap_or(Json::Null),
                    String::new(),
                ),
                Err(e) => (Json::Null, e.to_string()),
            }
        };
        if matches!(data, Json::Object(_)) {
            let sch = match obj_get(&data, "$schema") {
                Some(Json::Null) | None => String::new(),
                Some(v) => pyval::plain_str(v),
            };
            if sch.contains("json-schema.org") {
                form = "json-schema".to_string();
            }
            let kind = match obj_get(&data, "kind") {
                Some(Json::Null) | None => String::new(),
                Some(v) => pyval::plain_str(v),
            };
            let schema_f = match obj_get(&data, "schema") {
                Some(Json::Null) | None => String::new(),
                Some(v) => pyval::plain_str(v),
            };
            if kind.starts_with("nf-domain-spec") {
                form = "domain-spec".to_string();
            } else if schema_f.starts_with("nf-combo/1") {
                form = "combo-cert".to_string();
            } else if kind.starts_with("nf-domain-report") {
                form = "domain-report".to_string();
            } else if kind.starts_with("nf-system-card") {
                form = "system-card".to_string();
            } else if sch.contains("vega-lite") {
                form = "vega-lite".to_string();
            } else if sch.contains("vega") {
                form = "vega".to_string();
            } else if kind.starts_with("nf-performance") {
                form = "performance-report".to_string();
            } else if kind.starts_with("nf-quant-metrics") {
                form = "quant-metrics".to_string();
            } else if kind.starts_with("nf-concept-closure") {
                form = "concept-closure".to_string();
            }
        }
    }
    let tier = FORM_MAX_TIER
        .iter()
        .find(|(f, _)| *f == form)
        .map(|(_, t)| (*t).to_string())
        .unwrap_or_else(|| "T1".to_string());
    (form, tier)
}

// ---------------------------------------------------------------- 声明产出路径

/// 真源 `_reject_escape_forms`：外来清单里的路径**形状**判据。
///
/// 产出面**比词法判据更严**：`~` 也算绝对写法拒（真源注释里写明了这一点）。
pub fn reject_escape_forms(rel: &Json, what: &str) -> Result<(), String> {
    let text = match rel {
        Json::Null => String::new(),
        v => pyval::plain_str(v),
    };
    if text.trim().is_empty() {
        return Err(format!(
            "{} 为空（修复指引：给出包内相对路径，如 outputs/REPORT.json）",
            what
        ));
    }
    let drive = regex::Regex::new(r"^[A-Za-z]:").expect("固定合法");
    if text.starts_with('\\')
        || text.starts_with('/')
        || drive.is_match(&text)
        || text.starts_with('~')
    {
        return Err(format!(
            "{} 含绝对/盘符写法 {}（修复指引：改为包内相对路径，如 outputs/x.json）",
            what,
            pyval::py_repr(&Json::Str(text))
        ));
    }
    let issue = crate::paths::path_syntax_issue(&text);
    if !issue.is_empty() {
        return Err(format!(
            "{} {} {}（修复指引：改为包内相对路径，勿用 `..` 段 / 盘符写法 / `文件:流` 备用数据流 / 控制字符 / 保留设备名）",
            what,
            issue,
            pyval::py_repr(&Json::Str(text))
        ));
    }
    Ok(())
}

/// 真源 `_declared_out_rel`：清单声明的产出路径 → 仓库相对路径（形状 + **包内包含性**双判据）。
pub fn declared_out_rel(root: &Path, pkg: &str, rel: &Json) -> Result<String, String> {
    reject_escape_forms(rel, "产出路径")?;
    let text = match rel {
        Json::Null => String::new(),
        v => pyval::plain_str(v),
    };
    let out_rel = if text.starts_with("community/") {
        text.clone()
    } else {
        format!("community/{}/{}", pkg, text.trim_start_matches('/'))
    };
    if let Err(e) = crate::paths::validate_path(root, &out_rel) {
        return Err(format!("产出路径越界：{}", e.0));
    }
    if !pkg.is_empty()
        && !crate::paths::contained(&root.join("community").join(pkg), &root.join(&out_rel))
    {
        return Err(format!(
            "产出路径越界：{} 不在本包目录内（修复指引：产出面只许落在 community/{}/ 下，勿指向其它包）",
            text, pkg
        ));
    }
    Ok(out_rel)
}

// ---------------------------------------------------------------- XML 面

/// 真源 `_xml_guard`。
pub fn xml_guard(text: &str) -> String {
    crate::xmlmini::dtd_guard(text)
}

/// 真源 `_check_xml`。
pub fn check_xml(root: &Path, rel: &str) -> Vec<String> {
    let text = read_text(root, rel);
    let guard = xml_guard(&text);
    if !guard.is_empty() {
        return vec![guard];
    }
    match crate::xmlmini::parse(&text) {
        Ok(_) => Vec::new(),
        Err(e) => vec![format!("XML 良构性失败：{}", e)],
    }
}

/// 真源 `_check_graphml`。
pub fn check_graphml(root: &Path, rel: &str) -> Vec<String> {
    let text = read_text(root, rel);
    let guard = xml_guard(&text);
    if !guard.is_empty() {
        return vec![format!("GraphML {}", guard)];
    }
    let r = match crate::xmlmini::parse(&text) {
        Ok(n) => n,
        Err(e) => return vec![format!("GraphML XML 解析失败：{}", e)],
    };
    let mut issues: Vec<String> = Vec::new();
    let tag = r.local();
    if tag != "graphml" {
        issues.push(format!("根元素应为 graphml，实为 {}", tag));
    }
    let graphs = r.descendants("graph");
    if graphs.is_empty() {
        issues.push("缺 <graph> 元素".to_string());
    }
    let mut nodes: Vec<String> = Vec::new();
    for g in &graphs {
        for n in g.children_named("node") {
            if let Some(id) = n.attr("id") {
                nodes.push(id.to_string());
            }
        }
    }
    for g in &graphs {
        for e in g.children_named("edge") {
            for end in ["source", "target"] {
                let v = e.attr(end).unwrap_or("");
                if !nodes.iter().any(|n| n == v) {
                    issues.push(format!("边端点悬空：{}={}", end, v));
                }
            }
        }
    }
    issues
}

#[cfg(test)]
#[path = "generated/output_forms_gen.rs"]
mod output_forms_gen;
