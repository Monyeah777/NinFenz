use super::*;

pub(crate) fn as_int(j: &Json) -> Option<i64> {
    match j {
        Json::Int(i) => Some(*i),
        _ => None,
    }
}

pub(crate) fn as_f64(j: &Json) -> Option<f64> {
    match j {
        Json::Int(i) => Some(*i as f64),
        Json::Float(f) => Some(*f),
        _ => None,
    }
}

/// 真源 `check_schema_files` → `(issues, schemas)`。
pub(crate) fn check_schema_files(root: &Path) -> (Vec<String>, Vec<Json>) {
    let mut issues: Vec<String> = Vec::new();
    let mut schemas: Vec<Json> = Vec::new();
    if !root.join(SCHEMA_DIR).is_dir() {
        return (
            vec![format!("{}/ 缺失（协议层 IDL 未落盘）", SCHEMA_DIR)],
            schemas,
        );
    }
    for rel in crate::glob::expand(root, "protocol/schema/*.json") {
        let name = rel.rsplit('/').next().unwrap_or(&rel).to_string();
        let Some(data) = jsonread::read_file(root, &rel) else {
            issues.push(format!(
                "{}: JSON 解析失败（本线不复制 Python 异常文本）",
                name
            ));
            continue;
        };
        if !matches!(data, Json::Object(_)) {
            issues.push(format!("{}: schema 顶层非对象", name));
            continue;
        }
        for key in ["$id", "title", "type"] {
            if get(&data, key).is_none() {
                issues.push(format!("{}: schema 缺 {}", name, key));
            }
        }
        if py_str(get(&data, "$schema")) != DIALECT {
            issues.push(format!(
                "{}: $schema={} 与校验器实现的方言不一致（预期 {}；修复指引：改声明或先扩展校验器再改声明）",
                name,
                py_repr(get(&data, "$schema").unwrap_or(&Json::Null)),
                DIALECT
            ));
        }
        if py_str(get(&data, "type")) != "object" {
            issues.push(format!("{}: schema.type 应为 object", name));
        }
        if !matches!(get(&data, "properties"), Some(Json::Object(_))) {
            issues.push(format!("{}: schema.properties 缺失/非对象", name));
        }
        if let Some(req) = get(&data, "required") {
            if !matches!(req, Json::Array(_)) {
                issues.push(format!("{}: schema.required 非数组", name));
            }
        }
        issues.extend(subset_key_violations(&data, &name));
        schemas.push(data);
    }
    (issues, schemas)
}

/// 一张面的展开（共用子树清单缓存——见 [`discover`] 的性能注记）。
pub(crate) fn face(root: &Path, pats: &[&str], cache: &mut crate::glob::Cache) -> Vec<String> {
    let mut out = Vec::new();
    for p in pats {
        out.extend(cache.expand(root, p));
    }
    out
}

/// 真源 `discover` 的三张面（模式逐条展开，次序即真源次序）。
///
/// **性能**：三条模式的前缀都是 `community/`，若各走一遍文件系统，那棵最大的树要递归三遍。
/// 实测教训：不共用子树清单时 `schema-lint` 冷跑 396 ms，而真源未缓存冷算只要 142 ms。
/// 共用后一遍即可（`expand_with` 的 `trees` 按前缀记账）。
pub(crate) fn discover(
    root: &Path,
    cache: &mut crate::glob::Cache,
) -> (Vec<String>, Vec<String>, Vec<String>) {
    let module_docs = face(
        root,
        &["04_模块库/**/*.md", "community/*/modules/*.md"],
        cache,
    );
    let pipeline_docs = face(
        root,
        &["03_管线库/**/*.md", "community/*/pipelines/*.md"],
        cache,
    );
    let protocol_files = face(root, &["community/*/protocol.yaml"], cache);
    (module_docs, pipeline_docs, protocol_files)
}

#[derive(Default, Clone, Debug, PartialEq)]
pub(crate) struct LintStats {
    pub schema_files: usize,
    pub module_docs: usize,
    pub contract_covered: usize,
    pub pipelines: usize,
    pub protocols: usize,
    pub asset_entries: usize,
}

impl LintStats {
    /// 进 `verify_report` / CLI 的 stats 字典（键序由 JSON 出口排序）。
    pub fn to_json(&self) -> Json {
        Json::Object(vec![
            (
                "schema_files".to_string(),
                Json::Int(self.schema_files as i64),
            ),
            (
                "module_docs".to_string(),
                Json::Int(self.module_docs as i64),
            ),
            (
                "contract_covered".to_string(),
                Json::Int(self.contract_covered as i64),
            ),
            ("pipelines".to_string(), Json::Int(self.pipelines as i64)),
            ("protocols".to_string(), Json::Int(self.protocols as i64)),
            (
                "asset_entries".to_string(),
                Json::Int(self.asset_entries as i64),
            ),
        ])
    }
}

/// 真源 `_lint_doc_cached` 的**无缓存实现**（缓存是纯函数优化，不改语义）。
pub(crate) fn lint_doc(
    text: &str,
    marker: &str,
    schema: Option<&Json>,
    prefix: &str,
    obj_key: &str,
) -> Option<Vec<String>> {
    let parsed = miniyaml::fence_yaml(text, marker)?;
    let want = if obj_key.is_empty() { marker } else { obj_key };
    let obj = match get(&parsed, want) {
        Some(v) => v.clone(),
        None => parsed,
    };
    let errs = match schema {
        Some(s) => subset_validate(&obj, s, PLACEHOLDER),
        None => Vec::new(),
    };
    Some(
        errs.into_iter()
            .map(|m| m.replace(PLACEHOLDER, prefix))
            .collect(),
    )
}

/// 真源 `_lint_obj_cached` 的**无缓存实现**。
pub(crate) fn lint_obj(obj: &Json, schema: Option<&Json>, prefix: &str) -> Vec<String> {
    let Some(s) = schema else { return Vec::new() };
    subset_validate(obj, s, PLACEHOLDER)
        .into_iter()
        .map(|m| m.replace(PLACEHOLDER, prefix))
        .collect()
}

pub(crate) fn read_text(root: &Path, rel: &str) -> Result<String, String> {
    std::fs::read_to_string(root.join(rel)).map_err(|e| e.to_string())
}

/// 真源 `scan`（＝ `_scan_impl`；派生缓存是纯函数优化，本线不实现）。
pub(crate) fn scan(root: &Path) -> (Vec<String>, LintStats) {
    let mut issues: Vec<String> = Vec::new();
    let (schema_issues, schemas) = check_schema_files(root);
    issues.extend(schema_issues);
    let by_name: Vec<(String, Json)> = schemas
        .iter()
        .filter_map(|s| {
            get(s, "$id").map(|id| {
                (
                    plain_str(id).rsplit('/').next().unwrap_or("").to_string(),
                    s.clone(),
                )
            })
        })
        .collect();
    let pick = |n: &str| by_name.iter().find(|(k, _)| k == n).map(|(_, v)| v.clone());

    let mut cache = crate::glob::Cache::new();
    let (module_docs, pipeline_docs, protocol_files) = discover(root, &mut cache);
    let contract_schema = pick("contract.schema.json");
    let module_schema = pick("module.schema.json");
    let pipeline_schema = pick("pipeline.schema.json");
    let protocol_schema = pick("protocol.schema.json");
    let asset_schema = pick("asset.schema.json");

    let contract_covered = lint_module_docs(root, &module_docs, contract_schema.as_ref(), &mut issues);

    let reg_modules: Vec<Json> = match jsonread::read_file(root, "desktop/src/core/registry.json") {
        Some(reg) => crate::pyval::arr_items(get(&reg, "modules"))
            .into_iter()
            .cloned()
            .collect(),
        None => {
            issues.push("registry.json 读取/解析失败（本线不复制 Python 异常文本）".to_string());
            Vec::new()
        }
    };
    if module_schema.is_some() {
        for entry in &reg_modules {
            issues.extend(lint_obj(entry, module_schema.as_ref(), "registry.modules"));
        }
    }

    lint_pipeline_docs(root, &pipeline_docs, pipeline_schema.as_ref(), &mut issues);

    lint_protocol_files(root, &protocol_files, protocol_schema.as_ref(), &mut issues);

    let prov_entries: Vec<Json> = match jsonread::read_file(root, "05_资产库/provenance.json") {
        Some(prov) => crate::pyval::arr_items(get(&prov, "assets"))
            .into_iter()
            .cloned()
            .collect(),
        None => {
            issues.push("provenance.json 读取/解析失败（本线不复制 Python 异常文本）".to_string());
            Vec::new()
        }
    };
    if asset_schema.is_some() {
        for (i, entry) in prov_entries.iter().enumerate() {
            issues.extend(lint_obj(
                entry,
                asset_schema.as_ref(),
                &format!("provenance.assets[{}]", i),
            ));
        }
    }

    (
        issues,
        LintStats {
            schema_files: schemas.len(),
            module_docs: module_docs.len(),
            contract_covered,
            pipelines: pipeline_docs.len(),
            protocols: protocol_files.len(),
            asset_entries: prov_entries.len(),
        },
    )
}

/// 模块文档的 machine_contract schema 核对；返回命中覆盖的文档数。
pub(crate) fn lint_module_docs(
    root: &Path,
    module_docs: &[String],
    contract_schema: Option<&Json>,
    issues: &mut Vec<String>,
) -> usize {
    let mut contract_covered = 0usize;
    for rel in module_docs {
        let Ok(text) = read_text(root, rel) else {
            issues.push(format!("{}: 读取失败（本线不复制 Python 异常文本）", rel));
            continue;
        };
        let msgs = lint_doc(
            &text,
            "machine_contract",
            contract_schema,
            &format!("{} machine_contract", rel),
            "",
        );
        let Some(msgs) = msgs else { continue };
        contract_covered += 1;
        issues.extend(msgs);
    }
    contract_covered
}

/// 管线文档的 Pipeline 段 schema 核对。
pub(crate) fn lint_pipeline_docs(
    root: &Path,
    pipeline_docs: &[String],
    pipeline_schema: Option<&Json>,
    issues: &mut Vec<String>,
) {
    for rel in pipeline_docs {
        let Ok(text) = read_text(root, rel) else {
            issues.push(format!("{}: 读取失败（本线不复制 Python 异常文本）", rel));
            continue;
        };
        let msgs = lint_doc(
            &text,
            "Pipeline:",
            pipeline_schema,
            &format!("{} Pipeline", rel),
            "Pipeline",
        );
        match msgs {
            Some(m) => issues.extend(m),
            None => issues.push(format!("{}: Pipeline yaml 缺失/解析失败", rel)),
        }
    }
}

/// 领域包 protocol.yaml 的整份 schema 核对。
pub(crate) fn lint_protocol_files(
    root: &Path,
    protocol_files: &[String],
    protocol_schema: Option<&Json>,
    issues: &mut Vec<String>,
) {
    for rel in protocol_files {
        let text = match read_text(root, rel) {
            Ok(t) => t,
            Err(_) => {
                issues.push(format!(
                    "{}: protocol.yaml 解析失败（本线不复制 Python 异常文本）",
                    rel
                ));
                continue;
            }
        };
        match miniyaml::parse(&text) {
            Ok(data) => issues.extend(lint_obj(&data, protocol_schema, rel)),
            Err(_) => issues.push(format!(
                "{}: protocol.yaml 解析失败（本线不复制 Python 异常文本）",
                rel
            )),
        }
    }
}

// `protocol.yaml` 是**整份** YAML（不是围栏块）——真源走 `load_yaml_cached`，本线走 `miniyaml::parse`。
// 真源语料里这些文件以 `#` 注释开头、无 `---` 前导块，故可直接整份解析。

/// 供 `nf score` 用的信号：`schema_clean` = issues 条数。
pub(crate) fn issue_count(root: &Path) -> usize {
    scan(root).0.len()
}

/// 浮点辅助（供未来扩展；当前 stats 无浮点）。
#[allow(dead_code)]
pub(crate) fn round2(x: f64) -> f64 {
    pyfloat::round_to(x, 2)
}
