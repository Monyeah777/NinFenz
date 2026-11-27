//! `output_forms` 的**格式结构校验器**（真源 `_check_*` 一族 + `_FORM_CHECK` 分派表）。
//!
//! 拆成独立件只为可读：口径与真源逐条对应，判据面不拆。
//!
//! **两个解析器是本线自带的**（真源用标准库，本线不用 Python 运行时）：
//! `jsonmini`（`json.loads` 口径 + 重复键）、`toml` crate（`tomllib` 口径）。
//! 越出子集即 fail-closed。

use crate::output_forms::{read_text, rel_path};
use crate::pyjson::Json;
use crate::pyval;
use std::path::Path;

fn obj_get<'a>(v: &'a Json, k: &str) -> Option<&'a Json> {
    match v {
        Json::Object(o) => o.iter().find(|(kk, _)| kk == k).map(|(_, vv)| vv),
        _ => None,
    }
}

fn as_str(v: Option<&Json>) -> String {
    match v {
        None | Some(Json::Null) => String::new(),
        Some(x) => pyval::plain_str(x),
    }
}

/// 真源 `_read_json` 的**判据面**版本（用 `jsonmini`，与 `json.loads` 同接受面）。
pub fn read_json(root: &Path, rel: &str) -> (Json, String) {
    let p = rel_path(root, rel);
    match std::fs::read(&p) {
        Err(e) => (Json::Null, format!("不可读：{}", e)),
        Ok(b) => {
            let text = String::from_utf8_lossy(&b).into_owned();
            match crate::jsonmini::parse(&text) {
                Ok(parsed) => (parsed.value, String::new()),
                Err(e) => (Json::Null, format!("JSON 解析失败：{}", e)),
            }
        }
    }
}

/// 真源 `_check_json`（含**重复键**判据——`serde_json` 会静默覆盖，故走 `jsonmini`）。
pub fn check_json(root: &Path, rel: &str) -> Vec<String> {
    let p = rel_path(root, rel);
    let raw = std::fs::read(&p)
        .map(|b| String::from_utf8_lossy(&b).into_owned())
        .unwrap_or_default();
    match crate::jsonmini::parse(&raw) {
        Err(e) => vec![format!("JSON 不可解析：{}", e)],
        Ok(parsed) => {
            let mut uniq: Vec<String> = parsed.dups.clone();
            uniq.sort();
            uniq.dedup();
            uniq.into_iter()
                .map(|d| format!("JSON 重复键：{}", d))
                .collect()
        }
    }
}

/// 真源 `_check_jsonl`。
pub fn check_jsonl(root: &Path, rel: &str) -> Vec<String> {
    let mut issues: Vec<String> = Vec::new();
    let text = read_text(root, rel);
    for (i, line) in text.lines().enumerate() {
        if line.trim().is_empty() {
            continue;
        }
        if let Err(e) = crate::jsonmini::parse(line) {
            issues.push(format!("第 {} 行非 JSON：{}", i + 1, e));
        }
    }
    issues
}

/// 真源 `_check_csv`。
pub fn check_csv(root: &Path, rel: &str) -> Vec<String> {
    let text = read_text(root, rel);
    if text.contains('\u{0}') {
        return vec!["含 NUL 字节（非文本 CSV）".to_string()];
    }
    let rows: Vec<Vec<String>> = crate::asset_contract::csv_rows(&text)
        .into_iter()
        .filter(|r| !r.is_empty())
        .collect();
    if rows.is_empty() {
        return vec!["空表".to_string()];
    }
    let width = rows[0].len();
    let mut issues: Vec<String> = if width == 0 {
        vec!["表头为空".to_string()]
    } else {
        Vec::new()
    };
    for (i, r) in rows.iter().enumerate().skip(1) {
        if r.len() != width {
            issues.push(format!(
                "第 {} 行字段数 {} ≠ 表头 {}",
                i + 1,
                r.len(),
                width
            ));
        }
    }
    let mut hdr = rows[0].clone();
    hdr.sort();
    hdr.dedup();
    if hdr.len() != width {
        issues.push("表头有重名列".to_string());
    }
    issues
}

/// 真源 `_check_markdown`。
pub fn check_markdown(root: &Path, rel: &str) -> Vec<String> {
    let text = read_text(root, rel);
    let mut issues: Vec<String> = Vec::new();
    if text.trim().is_empty() {
        issues.push("空档".to_string());
    }
    if text.matches("```").count() % 2 == 1 {
        issues.push("代码围栏未闭合（``` 奇数个）".to_string());
    }
    issues
}

/// 真源 `_check_toml`（用 `toml` crate，对 `tomllib`）。
pub fn check_toml(root: &Path, rel: &str) -> Vec<String> {
    let text = read_text(root, rel);
    match toml::from_str::<toml::Value>(&text) {
        Ok(_) => Vec::new(),
        Err(e) => vec![format!("TOML 不可解析：{}", e)],
    }
}

/// 真源 `_check_yaml`（**收窄子集**良构判定：Tab 缩进 + 非映射项）。
pub fn check_yaml(root: &Path, rel: &str) -> Vec<String> {
    let text = read_text(root, rel);
    let mut issues: Vec<String> = Vec::new();
    for (i, line) in text.lines().enumerate() {
        let indent_len = line.len() - line.trim_start().len();
        if line[..indent_len].contains('\t') {
            issues.push(format!("第 {} 行用 Tab 缩进（YAML 禁 Tab）", i + 1));
        }
        let stripped = line.trim();
        if stripped.starts_with("- ") || stripped.is_empty() || stripped.starts_with('#') {
            continue;
        }
        if !line.contains(':') {
            let head: String = stripped.chars().take(40).collect();
            issues.push(format!(
                "第 {} 行非映射项（收窄子集要求 key: value）：{}",
                i + 1,
                head
            ));
        }
    }
    issues
}

/// 真源 `_check_vega_lite`。
pub fn check_vega_lite(root: &Path, rel: &str) -> Vec<String> {
    let (data, err) = read_json(root, rel);
    if !err.is_empty() {
        return vec![err];
    }
    let mut issues: Vec<String> = Vec::new();
    if !as_str(obj_get(&data, "$schema")).contains("vega-lite") {
        issues.push("缺 $schema（应为 vega-lite v5）".to_string());
    }
    let body_keys = [
        "mark", "layer", "hconcat", "vconcat", "concat", "facet", "spec", "repeat",
    ];
    if !body_keys.iter().any(|k| obj_get(&data, k).is_some()) {
        issues.push("缺 mark/layer 等绘图主体".to_string());
    }
    if obj_get(&data, "data").is_none() {
        issues.push("缺 data（图不能没有数据源）".to_string());
    }
    match obj_get(&data, "encoding") {
        Some(Json::Object(enc)) => {
            for (ch, spec) in enc {
                if !matches!(spec, Json::Object(_)) {
                    issues.push(format!("encoding.{} 非对象", ch));
                    continue;
                }
                let ch_keys = ["field", "aggregate", "value", "datum", "timeUnit", "bin"];
                if !ch_keys.iter().any(|k| obj_get(spec, k).is_some()) {
                    issues.push(format!(
                        "encoding.{} 无 field/aggregate/value（通道未绑定）",
                        ch
                    ));
                }
            }
        }
        Some(Json::Null) | None => {}
        _ => issues.push("encoding 非对象".to_string()),
    }
    issues
}

const MERMAID_KINDS: [&str; 10] = [
    "graph",
    "flowchart",
    "sequencediagram",
    "classdiagram",
    "erdiagram",
    "statediagram",
    "gantt",
    "pie",
    "journey",
    "mindmap",
];

/// 真源 `_check_mermaid`。
pub fn check_mermaid(root: &Path, rel: &str) -> Vec<String> {
    let text = read_text(root, rel);
    let lines: Vec<String> = text.lines().map(|l| l.trim_end().to_string()).collect();
    let body: Vec<&String> = lines
        .iter()
        .filter(|l| !l.trim().is_empty() && !l.trim().starts_with("%%"))
        .collect();
    if body.is_empty() {
        return vec!["空图".to_string()];
    }
    let head = body[0].trim().to_lowercase();
    if !MERMAID_KINDS.iter().any(|k| head.starts_with(k)) {
        let head40: String = body[0].trim().chars().take(40).collect();
        return vec![format!(
            "首行非已知图种：{}",
            pyval::py_repr(&Json::Str(head40))
        )];
    }
    Vec::new()
}

/// 真源 `_check_dot`。
pub fn check_dot(root: &Path, rel: &str) -> Vec<String> {
    let text = read_text(root, rel);
    let mut issues: Vec<String> = Vec::new();
    let re = regex::Regex::new(r"(?m)^\s*(strict\s+)?(di)?graph\b").expect("固定合法");
    if !re.is_match(&text) {
        issues.push("缺 digraph/graph 头".to_string());
    }
    let open = text.matches('{').count();
    let close = text.matches('}').count();
    if open != close {
        issues.push(format!("花括号不配对（{{ {} / }} {}）", open, close));
    }
    issues
}

/// 真源 `_check_quant_metrics`：**宣称的引擎必须真实存在**（宣称≠实现）。
pub fn check_quant_metrics(root: &Path, rel: &str) -> Vec<String> {
    let mut issues = check_json(root, rel);
    let (data, err) = read_json(root, rel);
    if !err.is_empty() || !matches!(data, Json::Object(_)) {
        if !err.is_empty() {
            issues.push(err);
        }
        return issues;
    }
    let entries: Vec<Json> = match obj_get(&data, "metrics") {
        Some(Json::Array(a)) => a.clone(),
        _ => Vec::new(),
    };
    let declared: Vec<Json> = match obj_get(&data, "declared_only") {
        Some(Json::Array(a)) => a.clone(),
        _ => Vec::new(),
    };
    for m in entries.iter().chain(declared.iter()) {
        if !matches!(m, Json::Object(_)) {
            issues.push(format!("条目非对象：{}", pyval::py_repr(m)));
            continue;
        }
        let mid = match obj_get(m, "id") {
            Some(v) if pyval::py_truthy(v) => pyval::plain_str(v),
            _ => "?".to_string(),
        };
        let eng = as_str(obj_get(m, "engine"));
        if !eng.is_empty() {
            let (modname, fnname) = match eng.split_once(':') {
                Some((a, b)) => (a.to_string(), b.to_string()),
                None => (eng.clone(), String::new()),
            };
            if modname != "quant_metrics"
                || !crate::output_tables::QUANT_METRICS_NAMES.contains(&fnname.as_str())
            {
                issues.push(format!(
                    "{}: 宣称 engine={}，但 core/quant_metrics 无该实现（宣称≠实现）",
                    mid, eng
                ));
            }
        }
        if as_str(obj_get(m, "verifiable")) == "T4" && eng.is_empty() {
            issues.push(format!("{}: 标 T4（可复算）却无 engine", mid));
        }
        let params: Vec<String> = match obj_get(m, "required_params") {
            Some(Json::Array(a)) => a.iter().map(pyval::plain_str).collect(),
            _ => Vec::new(),
        };
        if pyval::py_truthy(
            &obj_get(m, "annual_factor_required")
                .cloned()
                .unwrap_or(Json::Null),
        ) && !params.iter().any(|p| p == "annual_factor")
        {
            issues.push(format!(
                "{}: 需年化因子却未列入 required_params（口径四要素不全）",
                mid
            ));
        }
    }
    let names: Vec<String> = entries
        .iter()
        .map(|m| match obj_get(m, "id") {
            Some(v) => pyval::plain_str(v),
            None => pyval::py_str(None),
        })
        .collect();
    let mut expected: Vec<String> = match obj_get(&data, "annual_factors") {
        Some(Json::Object(o)) => o.iter().map(|(k, _)| k.clone()).collect(),
        _ => Vec::new(),
    };
    expected.sort();
    let mut want = vec![
        "daily".to_string(),
        "monthly".to_string(),
        "weekly".to_string(),
    ];
    want.sort();
    if expected != want {
        issues.push(format!(
            "annual_factors 键集应为 daily/weekly/monthly，实为 {}",
            pyval::py_repr_list(
                &expected
                    .iter()
                    .map(|s| Json::Str(s.clone()))
                    .collect::<Vec<_>>()
            )
        ));
    }
    let mut uniq = names.clone();
    uniq.sort();
    uniq.dedup();
    if uniq.len() != entries.len() {
        issues.push("metrics 存在重复 id".to_string());
    }
    issues
}

/// 真源 `_check_domain_spec`。
pub fn check_domain_spec(root: &Path, rel: &str) -> Vec<String> {
    let mut issues = check_json(root, rel);
    let (data, err) = read_json(root, rel);
    if !err.is_empty() || !matches!(data, Json::Object(_)) {
        if !err.is_empty() {
            issues.push(err);
        }
        return issues;
    }
    let code = as_str(obj_get(&data, "code"));
    let subs: Vec<Json> = match obj_get(&data, "subdivisions") {
        Some(Json::Array(a)) => a.clone(),
        _ => Vec::new(),
    };
    if subs.len() != 12 {
        issues.push(format!("细分条目应为 12 条，实为 {}", subs.len()));
    }
    for (i, s) in subs.iter().enumerate() {
        let want = format!("{}-{:02}", code, i + 1);
        let got = obj_get(s, "id").cloned().unwrap_or(Json::Null);
        if !pyval::py_eq(&got, &Json::Str(want.clone())) {
            issues.push(format!(
                "第 {} 条 id 应为 {}，实为 {}",
                i + 1,
                want,
                pyval::py_repr(&got)
            ));
        }
        let anchor = as_str(obj_get(s, "anchor"));
        if !anchor.starts_with("http://") && !anchor.starts_with("https://") {
            issues.push(format!("{} 锚非绝对 URL", pyval::py_str(obj_get(s, "id"))));
        }
        let status = match obj_get(s, "anchor_status") {
            Some(Json::Null) | None => 0,
            Some(v) => pyval::py_int_or(Some(v), 0),
        };
        if status == 0 {
            issues.push(format!(
                "{} 锚缺可达性实测值（不得假装可达：探不到记 0 并在锚表注明）",
                pyval::py_str(obj_get(s, "id"))
            ));
        }
    }
    issues
}

/// 真源 `_check_domain_report`。
pub fn check_domain_report(root: &Path, rel: &str) -> Vec<String> {
    let mut issues = check_json(root, rel);
    let (data, err) = read_json(root, rel);
    if !err.is_empty() || !matches!(data, Json::Object(_)) {
        if !err.is_empty() {
            issues.push(err);
        }
        return issues;
    }
    let fam = as_str(obj_get(&data, "family"));
    if !crate::output_tables::DOMAIN_FAMILIES.contains(&fam.as_str()) {
        issues.push(format!(
            "度量族未在本仓引擎登记：{}（不得宣称可复算）",
            pyval::py_repr(&Json::Str(fam.clone()))
        ));
    }
    let metrics = obj_get(&data, "metrics")
        .cloned()
        .unwrap_or(Json::Object(vec![]));
    if as_str(obj_get(&metrics, "family")) != fam {
        issues.push("metrics.family 与报告 family 不一致".to_string());
    }
    let rows = match obj_get(&data, "sample_rows") {
        Some(Json::Null) | None => 0,
        Some(v) => pyval::py_int_or(Some(v), 0),
    };
    if rows < 1 {
        issues.push("样例规模为 0（无样例即无口径值）".to_string());
    }
    issues
}

/// 真源 `_FORM_CHECK` 分派：按形态取校验器并跑。
///
/// `combo-cert` 走 `_check_combo_cert`：**先跑 JSON 形态校验**，再叠 schema + 五不变量 +
/// 「摘要与实时复算一致」（真源同序：`issues = _check_json(root, rel)` 之后才判证书）。
pub fn form_check(form: &str, root: &Path, rel: &str) -> Option<Vec<String>> {
    let r: Vec<String> = match form {
        "json" | "json-schema" | "vega" | "json-graph-format" | "performance-report"
        | "concept-closure" | "system-card" => check_json(root, rel),
        "jsonl" => check_jsonl(root, rel),
        "csv" => check_csv(root, rel),
        "xml" | "svg" => crate::output_forms::check_xml(root, rel),
        "markdown" => check_markdown(root, rel),
        "toml" => check_toml(root, rel),
        "yaml" => check_yaml(root, rel),
        "vega-lite" => check_vega_lite(root, rel),
        "mermaid" => check_mermaid(root, rel),
        "graphviz-dot" => check_dot(root, rel),
        "graphml" => crate::output_forms::check_graphml(root, rel),
        "quant-metrics" => check_quant_metrics(root, rel),
        "domain-spec" => check_domain_spec(root, rel),
        "domain-report" => check_domain_report(root, rel),
        "combo-cert" => crate::output_forms_gen::check_combo_cert(root, rel, check_json(root, rel)),
        _ => return None,
    };
    Some(r)
}

#[cfg(test)]
#[path = "generated/output_forms_checks_gen.rs"]
mod output_forms_checks_gen;
