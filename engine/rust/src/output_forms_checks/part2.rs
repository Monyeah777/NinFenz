//! 图表与量化面检查（Mermaid / DOT / quant-metrics / domain-spec / domain-report）+ 形态分派表。

use super::*;

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
