//! `output_forms` 的**生成器面**：13 个确定性生成器 + 组合证书校验。
//!
//! 真源 `GENERATORS` 是**唯一入口**——渲染与复算共用同一函数（「不复算的渲染 = 手写，禁」）。
//! 本线照搬这一点：`_recompute_entry` 与形态校验都走 `dispatch`。
//!
//! **真语料只触发 4 个**（`domain-report` 100 · `combo-cert` 4 · `concept-closure` 1 ·
//! `performance-report` 1）；另外 9 个（vega / mermaid / graphml）真语料从不触发，但**同表可达**
//! ⇒ 一并移植，不留「可达但缺席」。

use crate::pyjson::Json;
use crate::pyval;
use std::path::Path;

/// 生成器产出的两种形态：JSON 文档 或 纯文本（Mermaid）。
#[derive(Clone, Debug)]
pub enum GenOut {
    Json(Json),
    Text(String),
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

fn s_of(v: Option<&Json>) -> String {
    match v {
        None | Some(Json::Null) => String::new(),
        Some(x) => pyval::plain_str(x),
    }
}

/// 真源 `_pkg_rel`：包内声明的相对路径 → 仓库相对路径。
///
/// ⚠️ 两道关键处理（我第一版只看了真源的**尾部**，漏了它们，实测当场红）：
/// 1. **先过形状判据** `_reject_escape_forms`（外来清单字段出自投稿者之手；真源注释记着
///    「把 `path` 写成 `../../../PWNED.mmd`，文件真的落到了仓库外」）——越界即 `Err`；
/// 2. `rel` 以 `community/` 开头、或 `_pkg` 为空时**原样返回**，不再拼包目录。
///    语料实况：`concept-closure` 的 `recompute.graph` 已是仓相对路径 ⇒ 再拼一层会变成
///    `community/<包>/community/<包>/…`，真源因此丢件。
pub fn pkg_rel(entry: &Json, rel: &str) -> Result<String, String> {
    crate::output_forms::reject_escape_forms(&Json::Str(rel.to_string()), "清单相对路径")?;
    let pkg = s_of(obj_get(entry, "_pkg"));
    if rel.starts_with("community/") || pkg.is_empty() {
        return Ok(rel.to_string());
    }
    Ok(format!("community/{}/{}", pkg, rel.trim_start_matches('/')))
}

/// `pkg_rel` 的早退糖：越界即让所在生成器返回该 issue（真源是异常，由复算层转成问题行）。
macro_rules! prel {
    ($entry:expr, $rel:expr) => {
        match pkg_rel($entry, $rel) {
            Ok(v) => v,
            Err(e) => return (None, vec![e]),
        }
    };
}

/// `recompute` / `render` 声明（真源 `entry.get("recompute") or entry.get("render")`）。
fn spec_of(entry: &Json) -> Json {
    match obj_get(entry, "recompute") {
        Some(v) if pyval::py_truthy(v) => v.clone(),
        _ => obj_get(entry, "render")
            .cloned()
            .unwrap_or(Json::Object(vec![])),
    }
}

fn spec_params(spec: &Json) -> Vec<(String, Json)> {
    match obj_get(spec, "params") {
        Some(Json::Object(o)) => o.clone(),
        _ => Vec::new(),
    }
}

fn spec_inputs(spec: &Json) -> Vec<String> {
    arr_of(obj_get(spec, "inputs"))
        .iter()
        .map(pyval::plain_str)
        .collect()
}

fn read_json_rel(root: &Path, rel: &str) -> Result<Json, String> {
    let text = std::fs::read_to_string(root.join(rel)).map_err(|e| e.to_string())?;
    crate::jsonmini::parse(&text)
        .map(|r| r.value)
        .map_err(|e| e.to_string())
}

/// 真源 `_gen_performance_report`。
pub fn gen_performance_report(root: &Path, entry: &Json) -> (Option<GenOut>, Vec<String>) {
    let spec = spec_of(entry);
    let inputs = spec_inputs(&spec);
    if inputs.is_empty() {
        return (
            None,
            vec!["声明可复算/可渲染但缺 inputs（无源即无功能）".to_string()],
        );
    }
    let src = prel!(entry, &inputs[0]);
    let series = match crate::quant_metrics::load_equity_curve(&root.join(&src)) {
        Ok(v) => v,
        Err(e) => return (None, vec![format!("输入 {} {}", src, e)]),
    };
    let params = spec_params(&spec);
    match crate::quant_metrics::performance_report(&series, &params) {
        Ok(v) => (Some(GenOut::Json(v)), Vec::new()),
        Err(e) => (None, vec![format!("复算异常 ValueError: {}", e)]),
    }
}

/// 真源 `_gen_concept_closure`。
pub fn gen_concept_closure(root: &Path, entry: &Json) -> (Option<GenOut>, Vec<String>) {
    use crate::concept_graph as cg;
    let spec = spec_of(entry);
    let graph_decl = match obj_get(&spec, "graph") {
        Some(v) if pyval::py_truthy(v) => pyval::plain_str(v),
        _ => cg::DEFAULT_ASSET.to_string(),
    };
    let graph_path = prel!(entry, &graph_decl);
    let target = s_of(obj_get(&spec, "target"));
    if target.is_empty() {
        return (None, vec!["声明可复算但缺 target".to_string()]);
    }
    let graph = match cg::load_graph(root, &graph_path) {
        Ok(g) => g,
        Err(_) => {
            return (
                None,
                vec![format!("概念图 {} 不可解析（无源）", graph_path)],
            );
        }
    };
    if matches!(&graph, Json::Object(o) if o.is_empty()) {
        return (
            None,
            vec![format!("概念图 {} 不可解析（无源）", graph_path)],
        );
    }
    let clos = match cg::closure(&graph, &target) {
        Ok(ids) => ids,
        Err(e) => return (None, vec![format!("复算异常 ClosureError: {}", e)]),
    };
    let mut closure: Vec<Json> = Vec::new();
    for x in &clos {
        match cg::resolve(&graph, x) {
            Ok(v) => closure.push(Json::Str(v)),
            Err(e) => return (None, vec![format!("复算异常 ClosureError: {}", e)]),
        }
    }
    let order = match cg::toposort(&graph) {
        Ok(v) => v,
        Err(e) => return (None, vec![format!("复算异常 ClosureError: {}", e)]),
    };
    let aliases = match cg::alias_map(&graph) {
        Ok(v) => {
            let mut a = v;
            a.sort();
            a
        }
        Err(e) => return (None, vec![format!("复算异常 ClosureError: {}", e)]),
    };
    (
        Some(GenOut::Json(Json::Object(vec![
            (
                "kind".to_string(),
                Json::Str("nf-concept-closure/1".to_string()),
            ),
            ("graph".to_string(), Json::Str(graph_path)),
            ("target".to_string(), Json::Str(target)),
            ("closure".to_string(), Json::Array(closure)),
            (
                "load_order".to_string(),
                Json::Array(order.into_iter().map(Json::Str).collect()),
            ),
            (
                "alias".to_string(),
                Json::Array(
                    aliases
                        .into_iter()
                        .map(|(k, v)| Json::Array(vec![Json::Str(k), Json::Str(v)]))
                        .collect(),
                ),
            ),
        ]))),
        Vec::new(),
    )
}

/// 真源 `_gen_vega`。
pub fn gen_vega(root: &Path, entry: &Json) -> (Option<GenOut>, Vec<String>) {
    let spec = spec_of(entry);
    let inputs = spec_inputs(&spec);
    if inputs.is_empty() {
        return (None, vec!["图表面缺 inputs".to_string()]);
    }
    let src = prel!(entry, &inputs[0]);
    let series = match crate::quant_metrics::load_equity_curve(&root.join(&src)) {
        Ok(v) => v,
        Err(e) => return (None, vec![format!("输入 {} {}", src, e)]),
    };
    let params = spec_params(&spec);
    let title = params
        .iter()
        .find(|(k, _)| k == "title")
        .map(|(_, v)| pyval::plain_str(v))
        .unwrap_or_else(|| {
            if s_of(obj_get(&spec, "id")) == "vega-drawdown" {
                "回撤曲线".to_string()
            } else {
                "净值曲线".to_string()
            }
        });
    let out = if s_of(obj_get(&spec, "id")) == "vega-drawdown" {
        crate::quant_metrics::vega_drawdown(&series, &title)
    } else {
        crate::quant_metrics::vega_equity_curve(&series, &title)
    };
    (Some(GenOut::Json(out)), Vec::new())
}

/// 真源 `_gen_mermaid`（返回**纯文本**）。
pub fn gen_mermaid(_root: &Path, entry: &Json) -> (Option<GenOut>, Vec<String>) {
    let spec = spec_of(entry);
    if s_of(obj_get(&spec, "id")) == "mermaid-declaration-flow" {
        return (
            Some(GenOut::Text(
                crate::quant_metrics::mermaid_declaration_flow(),
            )),
            Vec::new(),
        );
    }
    (
        None,
        vec![format!(
            "未登记 Mermaid 生成器：{}",
            pyval::py_repr(&Json::Str(s_of(obj_get(&spec, "id"))))
        )],
    )
}

/// 真源 `_gen_domain_report`。
pub fn gen_domain_report(root: &Path, entry: &Json) -> (Option<GenOut>, Vec<String>) {
    let spec = spec_of(entry);
    let inputs = spec_inputs(&spec);
    let mut params = spec_params(&spec);
    let family = params
        .iter()
        .find(|(k, _)| k == "family")
        .map(|(_, v)| pyval::plain_str(v))
        .unwrap_or_default();
    params.retain(|(k, _)| k != "family");
    if inputs.is_empty() || family.is_empty() {
        return (
            None,
            vec!["域报告缺 inputs 或 family（无源/无族即无功能）".to_string()],
        );
    }
    let src = prel!(entry, &inputs[0]);
    let rows = match crate::domain_metrics::load_rows(&root.join(&src)) {
        Ok(r) => r,
        Err(e) => return (None, vec![format!("输入 {} {}", src, e)]),
    };
    let metrics = match crate::domain_metrics::evaluate(&family, &rows, &params) {
        Ok(m) => m,
        Err(e) => return (None, vec![format!("复算异常 ValueError: {}", e)]),
    };
    let code = params
        .iter()
        .find(|(k, _)| k == "code")
        .map(|(_, v)| pyval::plain_str(v))
        .unwrap_or_default();
    let domain = params
        .iter()
        .find(|(k, _)| k == "domain")
        .map(|(_, v)| pyval::plain_str(v))
        .unwrap_or_default();
    (
        Some(GenOut::Json(Json::Object(vec![
            (
                "kind".to_string(),
                Json::Str("nf-domain-report/1".to_string()),
            ),
            ("code".to_string(), Json::Str(code)),
            ("domain".to_string(), Json::Str(domain)),
            ("family".to_string(), Json::Str(family)),
            ("sample".to_string(), Json::Str(inputs[0].clone())),
            ("sample_rows".to_string(), Json::Int(rows.len() as i64)),
            ("metrics".to_string(), metrics),
        ]))),
        Vec::new(),
    )
}

/// 真源 `_gen_vega_metrics`。
pub fn gen_vega_metrics(root: &Path, entry: &Json) -> (Option<GenOut>, Vec<String>) {
    let spec = match obj_get(entry, "render") {
        Some(v) if pyval::py_truthy(v) => v.clone(),
        _ => spec_of(entry),
    };
    let inputs = spec_inputs(&spec);
    if inputs.is_empty() {
        return (None, vec!["图表面缺 inputs".to_string()]);
    }
    let rel = prel!(entry, &inputs[0]);
    let data = match read_json_rel(root, &rel) {
        Ok(d) => d,
        Err(e) => return (None, vec![format!("输入 {} {}", inputs[0], e)]),
    };
    let metrics = match obj_get(&data, "metrics") {
        Some(Json::Object(o)) => o.clone(),
        _ => Vec::new(),
    };
    let mut sorted = metrics.clone();
    sorted.sort_by(|a, b| a.0.cmp(&b.0));
    let vals: Vec<Json> = sorted
        .iter()
        .filter_map(|(k, v)| match v {
            Json::Float(f) => Some(Json::Object(vec![
                ("metric".to_string(), Json::Str(k.clone())),
                ("value".to_string(), Json::Float(*f)),
            ])),
            Json::Int(i) => Some(Json::Object(vec![
                ("metric".to_string(), Json::Str(k.clone())),
                ("value".to_string(), Json::Float(*i as f64)),
            ])),
            _ => None, // 真源 `isinstance(v, (int, float)) and not isinstance(v, bool)`
        })
        .collect();
    if vals.is_empty() {
        return (None, vec!["报告里没有可画的标量指标".to_string()]);
    }
    let title = spec_params(&spec)
        .iter()
        .find(|(k, _)| k == "title")
        .map(|(_, v)| pyval::plain_str(v))
        .filter(|s| !s.is_empty())
        .unwrap_or_else(|| "域指标".to_string());
    (
        Some(GenOut::Json(Json::Object(vec![
            (
                "$schema".to_string(),
                Json::Str("https://vega.github.io/schema/vega-lite/v5.json".to_string()),
            ),
            ("description".to_string(), Json::Str(title)),
            (
                "data".to_string(),
                Json::Object(vec![("values".to_string(), Json::Array(vals))]),
            ),
            (
                "mark".to_string(),
                Json::Object(vec![("type".to_string(), Json::Str("bar".to_string()))]),
            ),
            (
                "encoding".to_string(),
                Json::Object(vec![
                    (
                        "x".to_string(),
                        Json::Object(vec![
                            ("field".to_string(), Json::Str("value".to_string())),
                            ("type".to_string(), Json::Str("quantitative".to_string())),
                            ("title".to_string(), Json::Str("口径值".to_string())),
                        ]),
                    ),
                    (
                        "y".to_string(),
                        Json::Object(vec![
                            ("field".to_string(), Json::Str("metric".to_string())),
                            ("type".to_string(), Json::Str("nominal".to_string())),
                            ("title".to_string(), Json::Str("指标".to_string())),
                            ("sort".to_string(), Json::Str("-x".to_string())),
                        ]),
                    ),
                ]),
            ),
        ]))),
        Vec::new(),
    )
}

/// 真源 `_gen_combo_cert`。
pub fn gen_combo_cert(root: &Path, entry: &Json) -> (Option<GenOut>, Vec<String>) {
    let spec = match obj_get(entry, "recompute") {
        Some(v) => v.clone(),
        None => Json::Object(vec![]),
    };
    let params = spec_params(&spec);
    let packs: Vec<String> = arr_of(params.iter().find(|(k, _)| k == "packs").map(|(_, v)| v))
        .iter()
        .map(pyval::plain_str)
        .collect();
    let mods: Vec<String> = arr_of(
        params
            .iter()
            .find(|(k, _)| k == "extra_modules")
            .map(|(_, v)| v),
    )
    .iter()
    .map(pyval::plain_str)
    .collect();
    if packs.is_empty() && mods.is_empty() {
        return (
            None,
            vec!["组合证书缺 packs/extra_modules（无输入即无复算）".to_string()],
        );
    }
    let mut cert = crate::pack_combo_core::combine_fresh(root, &packs, &mods, &[]);
    if let Json::Object(o) = &mut cert {
        if let Some(l) = params.iter().find(|(k, _)| k == "label").map(|(_, v)| v) {
            if pyval::py_truthy(l) {
                o.push(("label".to_string(), l.clone()));
            }
        }
        if let Some(n) = params.iter().find(|(k, _)| k == "note").map(|(_, v)| v) {
            if pyval::py_truthy(n) {
                o.push(("note".to_string(), n.clone()));
            }
        }
    }
    (Some(GenOut::Json(cert)), Vec::new())
}

/// 真源 `_combo_doc`。
fn combo_doc(root: &Path, entry: &Json) -> (Option<Json>, String) {
    let spec = match obj_get(entry, "render") {
        Some(Json::Object(o)) => o.clone(),
        _ => Vec::new(),
    };
    let rel = {
        let ins = arr_of(spec.iter().find(|(k, _)| k == "inputs").map(|(_, v)| v));
        if ins.is_empty() {
            "outputs/COMBO_CERT.json".to_string()
        } else {
            pyval::plain_str(&ins[0])
        }
    };
    // `combo_doc` 的返回形状是 `(Option<Json>, String)` ⇒ 不能走 `prel!`（那是 `(_, Vec<String>)`）
    let full = match pkg_rel(entry, &rel) {
        Ok(v) => v,
        Err(e) => return (None, e),
    };
    match read_json_rel(root, &full) {
        Ok(d) => (Some(d), String::new()),
        Err(e) => (None, format!("输入 {} {}", rel, e)),
    }
}

/// 真源 `_stack_pairs`：层栈两种历史形态兼容。
pub fn stack_pairs(stacks: Option<&Json>) -> Vec<(String, Vec<String>)> {
    match stacks {
        Some(Json::Array(a)) => a
            .iter()
            .filter_map(|r| match r {
                Json::Object(o) => Some((
                    s_of(o.iter().find(|(k, _)| k == "layer").map(|(_, v)| v)),
                    arr_of(o.iter().find(|(k, _)| k == "modules").map(|(_, v)| v))
                        .iter()
                        .map(pyval::plain_str)
                        .collect(),
                )),
                _ => None,
            })
            .collect(),
        Some(Json::Object(o)) => {
            let mut items = o.clone();
            items.sort_by(|a, b| a.0.cmp(&b.0));
            items
                .into_iter()
                .map(|(k, v)| (k, arr_of(Some(&v)).iter().map(pyval::plain_str).collect()))
                .collect()
        }
        _ => Vec::new(),
    }
}

/// 真源 `_gen_vega_layer_stack`。
pub fn gen_vega_layer_stack(root: &Path, entry: &Json) -> (Option<GenOut>, Vec<String>) {
    let (data, err) = combo_doc(root, entry);
    if !err.is_empty() {
        return (None, vec![err]);
    }
    let data = data.unwrap_or(Json::Object(vec![]));
    let rows: Vec<Json> = stack_pairs(obj_get(&data, "layer_stacks"))
        .into_iter()
        .map(|(k, v)| {
            Json::Object(vec![
                ("layer".to_string(), Json::Str(k)),
                ("modules".to_string(), Json::Int(v.len() as i64)),
            ])
        })
        .collect();
    if rows.is_empty() {
        return (None, vec!["证书无 layer_stacks（无可画数据）".to_string()]);
    }
    let title = {
        let rspec = obj_get(entry, "render")
            .cloned()
            .unwrap_or(Json::Object(vec![]));
        let t = spec_params(&rspec)
            .iter()
            .find(|(k, _)| k == "title")
            .map(|(_, v)| pyval::plain_str(v))
            .unwrap_or_default();
        if t.is_empty() {
            "层位堆叠".to_string()
        } else {
            t
        }
    };
    (
        Some(GenOut::Json(Json::Object(vec![
            (
                "$schema".to_string(),
                Json::Str("https://vega.github.io/schema/vega-lite/v5.json".to_string()),
            ),
            ("description".to_string(), Json::Str(title)),
            (
                "data".to_string(),
                Json::Object(vec![("values".to_string(), Json::Array(rows))]),
            ),
            (
                "mark".to_string(),
                Json::Object(vec![("type".to_string(), Json::Str("bar".to_string()))]),
            ),
            (
                "encoding".to_string(),
                Json::Object(vec![
                    (
                        "x".to_string(),
                        Json::Object(vec![
                            ("field".to_string(), Json::Str("layer".to_string())),
                            ("type".to_string(), Json::Str("nominal".to_string())),
                            ("title".to_string(), Json::Str("层位".to_string())),
                            ("sort".to_string(), Json::Null),
                        ]),
                    ),
                    (
                        "y".to_string(),
                        Json::Object(vec![
                            ("field".to_string(), Json::Str("modules".to_string())),
                            ("type".to_string(), Json::Str("quantitative".to_string())),
                            ("title".to_string(), Json::Str("模块数".to_string())),
                        ]),
                    ),
                ]),
            ),
        ]))),
        Vec::new(),
    )
}

/// 真源 `_gen_mermaid_layer_load`（纯文本）。
pub fn gen_mermaid_layer_load(root: &Path, entry: &Json) -> (Option<GenOut>, Vec<String>) {
    let (data, err) = combo_doc(root, entry);
    if !err.is_empty() {
        return (None, vec![err]);
    }
    let data = data.unwrap_or(Json::Object(vec![]));
    let mut lines = vec![
        "%% 组合包装载序（由 COMBO_CERT.json 确定性派生）".to_string(),
        "flowchart LR".to_string(),
    ];
    for (lay, mods) in stack_pairs(obj_get(&data, "layer_stacks")) {
        let tag = lay.replace('-', "");
        lines.push(format!("  {}[\"{}\"]", tag, lay));
        for (i, m) in mods.iter().enumerate() {
            let node = format!("{}_{}", tag, i);
            lines.push(format!("  {}[\"{}\"]", node, m));
            lines.push(format!("  {} --> {}", tag, node));
        }
    }
    (Some(GenOut::Text(lines.join("\n") + "\n")), Vec::new())
}

/// 真源 `_gen_graphml_module_deps`（纯文本）。
pub fn gen_graphml_module_deps(root: &Path, entry: &Json) -> (Option<GenOut>, Vec<String>) {
    let (data, err) = combo_doc(root, entry);
    if !err.is_empty() {
        return (None, vec![err]);
    }
    let data = data.unwrap_or(Json::Object(vec![]));
    let mods: Vec<String> = arr_of(obj_get(&data, "modules"))
        .iter()
        .map(pyval::plain_str)
        .collect();
    let explicit: Vec<String> =
        arr_of(obj_get(&data, "dependency_closure").and_then(|d| obj_get(d, "explicit")))
            .iter()
            .map(pyval::plain_str)
            .collect();
    let mut out = vec![
        "<?xml version=\"1.0\" encoding=\"UTF-8\"?>".to_string(),
        "<graphml xmlns=\"http://graphml.graphdrawing.org/xmlns\">".to_string(),
        "  <key id=\"layer\" for=\"node\" attr.name=\"layer\" attr.type=\"string\"/>".to_string(),
        "  <graph id=\"combo\" edgedefault=\"directed\">".to_string(),
    ];
    let pairs = stack_pairs(obj_get(&data, "layer_stacks"));
    for m in &mods {
        let mut lay = String::new();
        for (k, v) in &pairs {
            if v.contains(m) {
                lay = k.clone();
                break;
            }
        }
        out.push(format!(
            "    <node id=\"{}\"><data key=\"layer\">{}</data></node>",
            m, lay
        ));
    }
    for m in &mods {
        for dep in combo_module_inputs(root, m) {
            if explicit.contains(&dep) && dep != *m {
                out.push(format!("    <edge source=\"{}\" target=\"{}\"/>", m, dep));
            }
        }
    }
    out.push("  </graph>".to_string());
    out.push("</graphml>".to_string());
    (Some(GenOut::Text(out.join("\n") + "\n")), Vec::new())
}

/// 真源 `m_prov`。
pub fn m_prov(meta: &[(String, Json)], node: &str) -> String {
    let rec = meta
        .iter()
        .find(|(k, _)| k == node)
        .map(|(_, v)| v.clone())
        .unwrap_or(Json::Null);
    let p = s_of(obj_get(&rec, "provenance"));
    if p.is_empty() {
        "unknown".to_string()
    } else {
        p
    }
}

/// 真源 `_gen_mermaid_concept_dag`（纯文本）。
pub fn gen_mermaid_concept_dag(root: &Path, entry: &Json) -> (Option<GenOut>, Vec<String>) {
    use crate::concept_graph as cg;
    let spec = spec_of(entry);
    let graph_decl = match obj_get(&spec, "graph") {
        Some(v) if pyval::py_truthy(v) => pyval::plain_str(v),
        _ => cg::DEFAULT_ASSET.to_string(),
    };
    let graph_path = prel!(entry, &graph_decl);
    let graph = match cg::load_graph(root, &graph_path) {
        Ok(g) if !matches!(&g, Json::Object(o) if o.is_empty()) => g,
        _ => {
            return (
                None,
                vec![format!("概念图 {} 不可解析（无源）", graph_path)],
            )
        }
    };
    let prereq = cg::prereqs_of(&graph);
    let layer: Vec<(String, String)> = cg::node_meta(&graph)
        .into_iter()
        .map(|(n, m)| {
            let l = s_of(obj_get(&m, "layer"));
            (n, if l.is_empty() { "P00".to_string() } else { l })
        })
        .collect();
    let mut lines = vec![
        format!(
            "%% 概念前置图（由 {} 确定性派生；唯一机读真相在资产 §4 围栏块）",
            graph_path
        ),
        "flowchart TD".to_string(),
    ];
    let ids = cg::in_package_ids(&graph);
    let mut seen_layers: Vec<String> = Vec::new();
    for node in &ids {
        let lay = layer
            .iter()
            .find(|(n, _)| n == node)
            .map(|(_, l)| l.clone())
            .unwrap_or_else(|| "P00".to_string());
        if !seen_layers.contains(&lay) {
            seen_layers.push(lay);
        }
    }
    let mut sorted_layers = seen_layers.clone();
    sorted_layers.sort();
    for lay in &sorted_layers {
        let group: Vec<&String> = ids
            .iter()
            .filter(|n| layer.iter().find(|(nn, _)| nn == *n).map(|(_, l)| l) == Some(lay))
            .collect();
        if group.is_empty() {
            continue;
        }
        lines.push(format!("  subgraph {}[{}]", lay, lay));
        for n in group {
            lines.push(format!("    {}", n));
        }
        lines.push("  end".to_string());
    }
    for node in &ids {
        if let Some((_, pres)) = prereq.iter().find(|(k, _)| k == node) {
            for pre in pres {
                if pre.starts_with("C0") && pre == "C00" {
                    continue;
                }
                lines.push(format!("  {} --> {}", pre, node));
            }
        }
    }
    (Some(GenOut::Text(lines.join("\n") + "\n")), Vec::new())
}

/// 真源 `_gen_graphml_concept_dag`（纯文本）。
pub fn gen_graphml_concept_dag(root: &Path, entry: &Json) -> (Option<GenOut>, Vec<String>) {
    use crate::concept_graph as cg;
    let spec = spec_of(entry);
    let graph_decl = match obj_get(&spec, "graph") {
        Some(v) if pyval::py_truthy(v) => pyval::plain_str(v),
        _ => cg::DEFAULT_ASSET.to_string(),
    };
    let graph_path = prel!(entry, &graph_decl);
    let graph = match cg::load_graph(root, &graph_path) {
        Ok(g) if !matches!(&g, Json::Object(o) if o.is_empty()) => g,
        _ => {
            return (
                None,
                vec![format!("概念图 {} 不可解析（无源）", graph_path)],
            )
        }
    };
    let prereq = cg::prereqs_of(&graph);
    let meta = cg::node_meta(&graph);
    let mut out = vec![
        "<?xml version=\"1.0\" encoding=\"UTF-8\"?>".to_string(),
        "<graphml xmlns=\"http://graphml.graphdrawing.org/xmlns\">".to_string(),
        "  <key id=\"layer\" for=\"node\" attr.name=\"layer\" attr.type=\"string\"/>".to_string(),
        "  <key id=\"branch\" for=\"node\" attr.name=\"branch\" attr.type=\"string\"/>".to_string(),
        "  <key id=\"provenance\" for=\"edge\" attr.name=\"provenance\" attr.type=\"string\"/>"
            .to_string(),
        "  <graph id=\"concept-graph\" edgedefault=\"directed\">".to_string(),
    ];
    let mut nodes = cg::in_package_ids(&graph);
    let base = nodes.clone();
    for node in &base {
        if let Some((_, pres)) = prereq.iter().find(|(k, _)| k == node) {
            for pre in pres {
                if !nodes.contains(pre) {
                    nodes.push(pre.clone());
                }
            }
        }
    }
    for node in &nodes {
        let m = meta
            .iter()
            .find(|(k, _)| k == node)
            .map(|(_, v)| v.clone())
            .unwrap_or(Json::Null);
        out.push(format!("    <node id=\"{}\">", node));
        out.push(format!(
            "      <data key=\"layer\">{}</data>",
            s_of(obj_get(&m, "layer"))
        ));
        out.push(format!(
            "      <data key=\"branch\">{}</data>",
            s_of(obj_get(&m, "branch"))
        ));
        out.push("    </node>".to_string());
    }
    for node in &nodes {
        if let Some((_, pres)) = prereq.iter().find(|(k, _)| k == node) {
            for pre in pres {
                out.push(format!("    <edge source=\"{}\" target=\"{}\">", pre, node));
                out.push(format!(
                    "      <data key=\"provenance\">{}</data>",
                    m_prov(&meta, node)
                ));
                out.push("    </edge>".to_string());
            }
        }
    }
    out.push("  </graph>".to_string());
    out.push("</graphml>".to_string());
    (Some(GenOut::Text(out.join("\n") + "\n")), Vec::new())
}

/// 真源 `_gen_id`。
pub fn gen_id(entry: &Json) -> String {
    for key in ["recompute", "render"] {
        if let Some(spec) = obj_get(entry, key) {
            if let Json::Object(o) = spec {
                if let Some(v) = o.iter().find(|(k, _)| k == "id").map(|(_, v)| v) {
                    if pyval::py_truthy(v) {
                        return pyval::plain_str(v);
                    }
                }
            }
        }
    }
    String::new()
}

/// 真源 `GENERATORS` 登记表（**唯一入口**）。
pub fn dispatch(root: &Path, entry: &Json) -> (Option<GenOut>, Vec<String>) {
    match gen_id(entry).as_str() {
        "performance-report" => gen_performance_report(root, entry),
        "concept-closure" => gen_concept_closure(root, entry),
        "vega-equity-curve" | "vega-drawdown" => gen_vega(root, entry),
        "mermaid-declaration-flow" => gen_mermaid(root, entry),
        "mermaid-concept-dag" => gen_mermaid_concept_dag(root, entry),
        "graphml-concept-dag" => gen_graphml_concept_dag(root, entry),
        "domain-report" => gen_domain_report(root, entry),
        "vega-metrics" => gen_vega_metrics(root, entry),
        "combo-cert" => gen_combo_cert(root, entry),
        "vega-layer-stack" => gen_vega_layer_stack(root, entry),
        "mermaid-layer-load" => gen_mermaid_layer_load(root, entry),
        "graphml-module-deps" => gen_graphml_module_deps(root, entry),
        other => (None, vec![format!("未登记生成器：{}", other)]),
    }
}

/// 真源 `GENERATORS` 的键（13 个），供「登记齐全」判据用。
pub const GENERATOR_IDS: [&str; 13] = [
    "performance-report",
    "concept-closure",
    "vega-equity-curve",
    "vega-drawdown",
    "mermaid-declaration-flow",
    "mermaid-concept-dag",
    "graphml-concept-dag",
    "domain-report",
    "vega-metrics",
    "combo-cert",
    "vega-layer-stack",
    "mermaid-layer-load",
    "graphml-module-deps",
];

/// 真源 `_check_combo_cert`：schema + 五不变量（复算一致由 recompute 面判）。
pub fn check_combo_cert(root: &Path, rel: &str, json_issues: Vec<String>) -> Vec<String> {
    let mut issues = json_issues;
    let data = match read_json_rel(root, rel) {
        Ok(d) => d,
        Err(e) => {
            issues.push(e);
            return issues;
        }
    };
    if !matches!(data, Json::Object(_)) {
        return issues;
    }
    let schema = crate::jsonmini::parse(crate::output_tables::CERT_SCHEMA_JSON)
        .map(|r| r.value)
        .unwrap_or(Json::Object(vec![]));
    let (errs, unsup) = crate::json_schema::json_schema_check_unsup(&data, &schema);
    for e in errs.iter().take(4) {
        issues.push(format!("证书不合 schema：{}", e));
    }
    if !unsup.is_empty() {
        let mut u: Vec<String> = unsup.clone();
        u.sort();
        u.dedup();
        issues.push(format!(
            "证书校验器遇不支持关键字：{}",
            pyval::py_repr_list(
                &u.iter()
                    .take(2)
                    .map(|x| Json::Str(x.clone()))
                    .collect::<Vec<_>>()
            )
        ));
    }
    let entry = Json::Object(vec![(
        "recompute".to_string(),
        Json::Object(vec![(
            "params".to_string(),
            Json::Object(vec![
                (
                    "packs".to_string(),
                    obj_get(&data, "packs").cloned().unwrap_or(Json::Null),
                ),
                (
                    "extra_modules".to_string(),
                    obj_get(&data, "extra_modules")
                        .cloned()
                        .unwrap_or(Json::Null),
                ),
            ]),
        )]),
    )]);
    let (fresh, perr) = gen_combo_cert(root, &entry);
    match fresh {
        None => {
            for e in perr {
                issues.push(format!("复算失败：{}", e));
            }
        }
        Some(GenOut::Json(fresh)) => {
            if !matches!(obj_get(&fresh, "legal"), Some(Json::Bool(true))) {
                issues.push("组合非法（五不变量未全成立）".to_string());
            }
            let a = obj_get(&fresh, "digest").cloned().unwrap_or(Json::Null);
            let b = obj_get(&data, "digest").cloned().unwrap_or(Json::Null);
            if !crate::jsonread::json_eq(&a, &b) {
                issues.push("证书摘要与实时复算不一致（组合输入已变）".to_string());
            }
        }
        Some(GenOut::Text(_)) => {}
    }
    issues
}

/// 便捷：`pc.prof_get_module` 的再导出（供 `_combo_module_inputs` 一类调用点）。
pub fn prof_get_module(root: &Path, module_id: &str) -> Json {
    crate::pack_combo_core::prof_get_module(root, module_id)
}

/// 便捷：组合证书里某模块的 inputs。
pub fn combo_module_inputs(root: &Path, module_id: &str) -> Vec<String> {
    arr_of(obj_get(&prof_get_module(root, module_id), "inputs"))
        .iter()
        .map(pyval::plain_str)
        .collect()
}

#[cfg(test)]
#[path = "generated/output_forms_gen_gen.rs"]
mod output_forms_gen_gen;
