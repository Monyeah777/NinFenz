//! 动态识别（形态 + 档位）/ 路径逃逸形态 / 清单声明路径 / XML 与 GraphML 检查。

use super::*;

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
        if let Some(f) = detect_json_form(&p) {
            form = f;
        }
    }
    let tier = FORM_MAX_TIER
        .iter()
        .find(|(f, _)| *f == form)
        .map(|(_, t)| (*t).to_string())
        .unwrap_or_else(|| "T1".to_string());
    (form, tier)
}

/// JSON 形态识别：读文件 → 归类（读不了 / 非对象 → None，保留扩展名形态）。
fn detect_json_form(p: &Path) -> Option<String> {
    let text = std::fs::read(p)
        .map(|b| String::from_utf8_lossy(&b).into_owned())
        .unwrap_or_default();
    let data = match serde_json::from_str::<serde_json::Value>(&text) {
        Ok(v) => crate::jsonread::convert(&v).unwrap_or(Json::Null),
        Err(_) => Json::Null,
    };
    json_form(&data)
}

/// 对象 → 形态 id：kind / schema / $schema 三处特征（真源 else-if 顺序）。
fn json_form(data: &Json) -> Option<String> {
    if !matches!(data, Json::Object(_)) {
        return None;
    }
    let sch = json_field_str(data, "$schema");
    if let Some(f) = json_kind_form(data, &sch) {
        return Some(f);
    }
    if sch.contains("json-schema.org") {
        return Some("json-schema".to_string());
    }
    None
}

/// 取对象字段的字符串值（缺键 / null → 空串）。
fn json_field_str(data: &Json, key: &str) -> String {
    match obj_get(data, key) {
        Some(Json::Null) | None => String::new(),
        Some(v) => pyval::plain_str(v),
    }
}

/// 特征链：domain / combo / report / card / vega / performance / quant / closure。
fn json_kind_form(data: &Json, sch: &str) -> Option<String> {
    let kind = json_field_str(data, "kind");
    let schema_f = json_field_str(data, "schema");
    if kind.starts_with("nf-domain-spec") {
        return Some("domain-spec".to_string());
    }
    if schema_f.starts_with("nf-combo/1") {
        return Some("combo-cert".to_string());
    }
    if kind.starts_with("nf-domain-report") {
        return Some("domain-report".to_string());
    }
    if kind.starts_with("nf-system-card") {
        return Some("system-card".to_string());
    }
    if sch.contains("vega-lite") {
        return Some("vega-lite".to_string());
    }
    if sch.contains("vega") {
        return Some("vega".to_string());
    }
    if kind.starts_with("nf-performance") {
        return Some("performance-report".to_string());
    }
    if kind.starts_with("nf-quant-metrics") {
        return Some("quant-metrics".to_string());
    }
    if kind.starts_with("nf-concept-closure") {
        return Some("concept-closure".to_string());
    }
    None
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
    let nodes = graphml_node_ids(&graphs);
    graphml_edge_issues(&graphs, &nodes, &mut issues);
    issues
}

/// GraphML 全部 node id。
fn graphml_node_ids(graphs: &[&crate::xmlmini::XNode]) -> Vec<String> {
    let mut nodes: Vec<String> = Vec::new();
    for g in graphs {
        for n in g.children_named("node") {
            if let Some(id) = n.attr("id") {
                nodes.push(id.to_string());
            }
        }
    }
    nodes
}

/// 边端点必须落在已声明节点集内。
fn graphml_edge_issues(
    graphs: &[&crate::xmlmini::XNode],
    nodes: &[String],
    issues: &mut Vec<String>,
) {
    for g in graphs {
        for e in g.children_named("edge") {
            for end in ["source", "target"] {
                let v = e.attr(end).unwrap_or("");
                if !nodes.iter().any(|n| n == v) {
                    issues.push(format!("边端点悬空：{}={}", end, v));
                }
            }
        }
    }
}

