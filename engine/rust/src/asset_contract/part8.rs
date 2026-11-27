//! 聚合面：schema 自检 / load / scan。

use super::*;

// ---------------------------------------------------------------- 聚合 / 入口

/// 真源 `load`。
pub fn load(root: &Path) -> (Json, Vec<String>) {
    let p = root.join(DECL_REL);
    if !p.is_file() {
        return (
            Json::Object(vec![]),
            vec![format!(
                "缺数字资产契约声明 {}（修复指引：新建并写入 schema={} 与 data/code/script 三面）",
                DECL_REL, SCHEMA
            )],
        );
    }
    let text = match std::fs::read_to_string(&p) {
        Ok(s) => s,
        Err(e) => {
            return (
                Json::Object(vec![]),
                vec![format!(
                    "{} 不可读或不是合法 JSON：{}（修复指引：修好语法）",
                    DECL_REL, e
                )],
            )
        }
    };
    let doc = match strict_json(&text) {
        Ok(v) => v,
        Err(e) => {
            return (
                Json::Object(vec![]),
                vec![format!(
                    "{} 不可读或不是合法 JSON：{}（修复指引：修好语法）",
                    DECL_REL, e
                )],
            )
        }
    };
    if !matches!(doc, Json::Object(_)) || sg_str(&doc, "schema") != SCHEMA {
        return (
            Json::Object(vec![]),
            vec![format!(
                "{} schema 不匹配（期望 {}）（修复指引：改为声明件当前形态）",
                DECL_REL, SCHEMA
            )],
        );
    }
    (doc, Vec::new())
}

/// 真源 `scan(root, faces=())` → `(issues, warns, stats)`。
pub fn scan(root: &Path) -> (Vec<String>, Vec<String>, Json) {
    // 每次判据面起始构建可见件集合，结束清空（热 worker 不吞新件；单测夹具不受跨调用缓存影响）。
    crate::repo_paths::begin_scope(root);
    let out = scan_inner(root);
    crate::repo_paths::end_scope();
    out
}

pub(crate) fn scan_inner(root: &Path) -> (Vec<String>, Vec<String>, Json) {
    let (doc, mut issues) = load(root);
    let mut warns: Vec<String> = Vec::new();
    let mut counts: Vec<(String, i64)> = FACES.iter().map(|f| ((*f).to_string(), 0i64)).collect();
    if !issues.is_empty() {
        return (issues, warns, scan_stats(&counts, 0, 0, None));
    }
    // 真源同序：load → 登记册（D1，四面都判）→ 导出漂移（④）/ 声明自检（⑤，声明面整体判据）。
    issues.extend(registry_issues(root, &doc));
    issues.extend(export_drift(root));
    issues.extend(schema_self_check(root));
    let (files, no_schema) = scan_faces(root, &doc, &mut counts, &mut issues, &mut warns);
    let chains = scan_chains(&doc, &mut issues);
    (issues, warns, scan_stats(&counts, files, chains, Some(no_schema)))
}

/// 四面契约循环：逐面判据、计数面次与统计累加；返回 (files, no_schema)。
fn scan_faces(
    root: &Path,
    doc: &Json,
    counts: &mut [(String, i64)],
    issues: &mut Vec<String>,
    warns: &mut Vec<String>,
) -> (i64, i64) {
    let mut files = 0i64;
    let mut no_schema = 0i64;
    for face in FACES {
        let specs = match obj_get(doc, face) {
            Some(Json::Array(a)) => a.clone(),
            _ => Vec::new(),
        };
        for spec in specs {
            if !matches!(spec, Json::Object(_)) {
                issues.push(format!(
                    "契约 {} 面有非对象条目（修复指引：每条须是对象）",
                    face
                ));
                continue;
            }
            let (sub, s) = match face {
                "data" => check_data(root, &spec),
                "code" => {
                    // WARN 级治理面：由声明里 warn_rules 驱动，不进 issues（见 code_warns）。
                    warns.extend(code_warns(root, &spec));
                    check_code(root, &spec)
                }
                "index" => check_index(root, &spec),
                _ => check_script(root, &spec),
            };
            issues.extend(sub);
            if let Some(e) = counts.iter_mut().find(|(k, _)| k == face) {
                e.1 += 1;
            }
            files += pyval::py_int_or(obj_get(&s, "files"), 0);
            // 真源：stats["no_schema"] = int(stats.get("no_schema") or 0) + int(s.get(...) or 0)
            no_schema += pyval::py_int_or(obj_get(&s, "no_schema"), 0);
        }
    }
    (files, no_schema)
}

/// chains 面：逐条核对；返回链数。
fn scan_chains(doc: &Json, issues: &mut Vec<String>) -> i64 {
    let mut chains = 0i64;
    let specs: Vec<(String, Json)> = match obj_get(doc, "script") {
        Some(Json::Array(a)) => a.iter().map(|s| (sg_str(s, "id"), s.clone())).collect(),
        _ => Vec::new(),
    };
    if let Some(Json::Array(cs)) = obj_get(doc, "chains") {
        for c in cs {
            let empty = Json::Object(vec![]);
            let chain = if matches!(c, Json::Object(_)) {
                c
            } else {
                &empty
            };
            let (sub, _) = check_chain(&specs, chain);
            issues.extend(sub);
            chains += 1;
        }
    }
    chains
}

/// 汇总 stats：面次 + files/chains（+ 非早退时的 no_schema）。
fn scan_stats(
    counts: &[(String, i64)],
    files: i64,
    chains: i64,
    no_schema: Option<i64>,
) -> Json {
    let mut kv: Vec<(String, Json)> = counts
        .iter()
        .map(|(k, v)| (k.clone(), Json::Int(*v)))
        .collect();
    kv.push(("files".to_string(), Json::Int(files)));
    kv.push(("chains".to_string(), Json::Int(chains)));
    if let Some(ns) = no_schema {
        kv.push(("no_schema".to_string(), Json::Int(ns)));
    }
    Json::Object(kv)
}
