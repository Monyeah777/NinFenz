//! 数据面：YAML / TOML / JSONL / GraphML / Mermaid。

use super::*;

/// 真源 `_data_jsonl`：**逐行**严格 JSON（空行跳过）；必填字段对每一行判。
pub(crate) fn data_jsonl(rel: &str, text: &str, spec: &Json) -> (Vec<String>, Json) {
    let mut issues: Vec<String> = Vec::new();
    let mut rows = 0i64;
    for (i, line) in text.lines().enumerate() {
        if line.trim().is_empty() {
            continue;
        }
        rows += 1;
        let obj = match strict_json(line) {
            Ok(v) => v,
            Err(e) => {
                issues.push(format!(
                    "数据件 {} 第 {} 行不是合法 JSON：{}（修复指引：一行一条）",
                    rel,
                    i + 1,
                    e
                ));
                continue;
            }
        };
        for f in sg_strs(spec, "required_fields") {
            if dig_ref(&obj, &f).is_none() {
                issues.push(format!(
                    "数据件 {} 第 {} 行缺必填字段 {}（修复指引：补字段）",
                    rel,
                    i + 1,
                    f
                ));
            }
        }
    }
    let min_rows = pyval::py_int_or(obj_get(spec, "min_rows"), 0);
    if min_rows > 0 && rows < min_rows {
        issues.push(format!(
            "数据件 {} 行数 {} < min_rows {}（修复指引：补样例或下调声明）",
            rel, rows, min_rows
        ));
    }
    (
        issues,
        Json::Object(vec![("rows".to_string(), Json::Int(rows))]),
    )
}

/// 真源 `_data_graphml`：XML 良构 + 节点/边计数（入口先拒 DTD/实体声明）。
pub(crate) fn data_graphml(rel: &str, text: &str, spec: &Json) -> (Vec<String>, Json) {
    if text.contains("<!DOCTYPE") || text.contains("<!ENTITY") {
        return (
            vec![format!(
                "数据件 {} 含 DTD/实体声明，拒绝解析（修复指引：去掉 DOCTYPE/ENTITY——导出工具重跑）",
                rel
            )],
            Json::Object(vec![]),
        );
    }
    let root_el = match crate::xmlmini::parse(text) {
        Ok(n) => n,
        Err(e) => {
            return (
                vec![format!(
                    "数据件 {} 不是良构 XML：{}（修复指引：修好 XML）",
                    rel, e
                )],
                Json::Object(vec![]),
            )
        }
    };
    // 真源先试 graphml 命名空间版 `.//g:node`，再退 `.//node`；两者在真语料上同值
    // （本线解析器只取局部名，与 `{*}` 通配同效）。
    let nodes = root_el.descendants("node").len() as i64;
    let edges = root_el.descendants("edge").len() as i64;
    let mut issues: Vec<String> = Vec::new();
    let min_nodes = pyval::py_int_or(obj_get(spec, "min_nodes"), 0);
    if min_nodes > 0 && nodes < min_nodes {
        issues.push(format!(
            "数据件 {} 节点数 {} < min_nodes {}（修复指引：补结构或下调声明）",
            rel, nodes, min_nodes
        ));
    }
    (
        issues,
        Json::Object(vec![
            ("nodes".to_string(), Json::Int(nodes)),
            ("edges".to_string(), Json::Int(edges)),
        ]),
    )
}

/// 真源 `_data_mmd`：首关键词须是合法 Mermaid 图型（结构判据，不解析图内容）。
pub(crate) fn data_mmd(rel: &str, text: &str) -> (Vec<String>, Json) {
    let mut first = String::new();
    for line in text.lines() {
        let s = line.trim();
        if !s.is_empty() && !s.starts_with("%%") {
            first = s.split_whitespace().next().unwrap_or("").to_string();
            break;
        }
    }
    if first.is_empty() {
        return (
            vec![format!(
                "数据件 {} 是空 Mermaid 图（修复指引：补图声明）",
                rel
            )],
            Json::Object(vec![]),
        );
    }
    let base: &str = if first.starts_with("xychart") || first.starts_with("block") {
        first.split('-').next().unwrap_or("")
    } else {
        &first
    };
    if !MMD_KINDS.contains(&first.as_str()) && !MMD_KINDS.contains(&base) {
        return (
            vec![format!(
                "数据件 {} 首关键词 {} 不是合法 Mermaid 图型（修复指引：用 graph/flowchart/sequenceDiagram 等）",
                rel,
                pyval::py_repr(&Json::Str(first))
            )],
            Json::Object(vec![]),
        );
    }
    (
        Vec::new(),
        Json::Object(vec![("kind".to_string(), Json::Str(first))]),
    )
}

/// 真源 `_check_data`。
pub fn check_data(root: &Path, spec: &Json) -> (Vec<String>, Json) {
    let sid = {
        let s = sg_str(spec, "id");
        if !s.is_empty() {
            s
        } else {
            let p = sg_str(spec, "path");
            if !p.is_empty() {
                p
            } else {
                let g = sg_str(spec, "glob");
                if !g.is_empty() {
                    g
                } else {
                    "?".to_string()
                }
            }
        }
    };
    let rels = resolve(root, spec);
    if rels.is_empty() {
        return (
            vec![format!(
                "数据契约 {} 未命中任何文件（修复指引：修正 path/glob —— 空气不是契约）",
                sid
            )],
            Json::Object(vec![("files".to_string(), Json::Int(0))]),
        );
    }
    let fmt = sg_str(spec, "format").to_lowercase();
    if !FORMATS.contains(&fmt.as_str()) {
        return (
            vec![format!(
                "数据契约 {} 的 format={} 不在词表 {}（修复指引：改用词表内格式）",
                sid,
                pyval::py_repr(&Json::Str(fmt)),
                FORMATS.join("/")
            )],
            Json::Object(vec![("files".to_string(), Json::Int(rels.len() as i64))]),
        );
    }
    let has_sha = pyval::py_truthy(&sg(spec, "sha256"));
    if has_sha && rels.len() != 1 {
        return (
            vec![format!(
                "数据契约 {} 声明了 sha256 却命中 {} 件（修复指引：sha256 只用于 path 单件）",
                sid,
                rels.len()
            )],
            Json::Object(vec![("files".to_string(), Json::Int(rels.len() as i64))]),
        );
    }
    let mut issues: Vec<String> = Vec::new();
    let mut stats: Vec<(String, Json)> = vec![
        ("files".to_string(), Json::Int(rels.len() as i64)),
        ("format".to_string(), Json::Str(fmt.clone())),
    ];
    for rel in &rels {
        let (text, err) = sread(root, rel);
        if let Some(e) = err {
            issues.push(e);
            continue;
        }
        let text = text.unwrap_or_default();
        let mut obj: Option<Json> = None;
        let (sub, s) = match fmt.as_str() {
            "json" => {
                let r = data_json(root, rel, &text, spec);
                obj = strict_json(&text).ok();
                r
            }
            "csv" => data_csv(rel, &text, spec),
            "markdown" => data_markdown(rel, &text, spec),
            "yaml" => data_yaml(root, rel, &text, spec),
            "toml" => data_toml(root, rel, &text, spec),
            "jsonl" => data_jsonl(rel, &text, spec),
            "graphml" => data_graphml(rel, &text, spec),
            "mmd" => data_mmd(rel, &text),
            _ => (
                Vec::new(),
                Json::Object(vec![(
                    "lines".to_string(),
                    Json::Int(pyval::splitlines_count(&text) as i64),
                )]),
            ),
        };
        issues.extend(sub);
        merge_format_stats(&mut stats, s);
        data_sha_link_issues(root, rel, spec, has_sha, &obj, &mut issues);
    }
    (issues, Json::Object(stats))
}
