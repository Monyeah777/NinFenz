//! 索引面：check_index / 注册表一致性 / Frictionless 导出与漂移。

use super::*;

/// 包清单里单条 output 声明的核对（在场性 / schema / inputs）；返回计入 declared 的条数。
pub(crate) fn check_index_item(
    root: &Path,
    base: &str,
    rel: &str,
    item: &Json,
    declared: &mut std::collections::BTreeSet<String>,
    issues: &mut Vec<String>,
) -> i64 {
    let mut count = 0i64;
    if !matches!(item, Json::Object(_)) {
        return 0;
    }
    let pth = sg_str(item, "path");
    if pth.is_empty() {
        issues.push(format!(
            "包清单 {} 有一条无 path 的声明（修复指引：补 path）",
            rel
        ));
        return 0;
    }
    declared.insert(pth.clone());
    count += 1;
    if !root.join(&base).join(&pth).is_file() {
        issues.push(format!(
            "包清单 {} 声明的 {} 不在场（修复指引：补件或重跑 nf domain build）",
            rel, pth
        ));
    }
    let sch = sg_str(item, "schema");
    if !sch.is_empty() && !root.join(&base).join(&sch).is_file() {
        issues.push(format!(
            "包清单 {} 声明的 schema {} 不在场（修复指引：补件）",
            rel, sch
        ));
    }
    // 真源 `item.get("inputs") or ((item.get("recompute") or {}).get("inputs") or [])`
    let mut ins: Vec<String> = sg_strs(item, "inputs");
    if ins.is_empty() {
        let rec = sg(item, "recompute");
        if matches!(rec, Json::Object(_)) {
            ins = sg_strs(&rec, "inputs");
        }
    }
    for inp in &ins {
        if !root.join(&base).join(inp).is_file() {
            issues.push(format!(
                "包清单 {} 声明的输入 {} 不在场（修复指引：补件或改声明）",
                rel, inp
            ));
        }
    }
    count
}


/// 真源 `_registry_issues`：本册声明为数据的 `protocol/` 件必须已在
/// `protocol/data_contracts.json` 登记。
///
/// 为什么：仓库里已有「数据契约登记册」（ODCS 式：谁判 / 谁管 / 坏了怎么重建）。资产册再造一份
/// 「谁管」就是第二套词表——同型病。判据只问一句：**同一 artifact 不许只在资产册出现**。
pub fn registry_issues(root: &Path, doc: &Json) -> Vec<String> {
    // `targets` 为空 ⇒ 本册没有 protocol 真源件 ⇒ 登记册判据不适用（临时场景常见）。
    if protocol_data_targets(root, doc).is_empty() {
        return Vec::new();
    }
    let p = root.join("protocol/data_contracts.json");
    if !p.is_file() {
        return vec!["缺 protocol/data_contracts.json\
                     （修复指引：补登记册——本册有 protocol 真源件须登记）"
            .to_string()];
    }
    let reg = match std::fs::read_to_string(&p) {
        Err(e) => {
            return vec![format!(
                "protocol/data_contracts.json 不可读：{}（修复指引：修好 JSON）",
                e
            )]
        }
        Ok(t) => match strict_json(&t) {
            Err(e) => {
                return vec![format!(
                    "protocol/data_contracts.json 不可读：{}（修复指引：修好 JSON）",
                    e
                )]
            }
            Ok(v) => v,
        },
    };
    let mut arts: std::collections::BTreeSet<String> = std::collections::BTreeSet::new();
    if let Some(Json::Array(cs)) = obj_get(&reg, "contracts") {
        for c in cs {
            if matches!(c, Json::Object(_)) {
                arts.insert(sg_str(c, "artifact"));
            }
        }
    }
    let mut issues: Vec<String> = Vec::new();
    if let Some(Json::Array(specs)) = obj_get(doc, "data") {
        for spec in specs {
            for rel in resolve(root, spec) {
                if rel.starts_with("protocol/") && rel.ends_with(".json") && !arts.contains(&rel) {
                    issues.push(format!(
                        "资产 {} 未在 protocol/data_contracts.json 登记\
                         （修复指引：补一条契约——同一 artifact 不许只在资产册出现）",
                        rel
                    ));
                    break;
                }
            }
        }
    }
    issues
}

/// 真源 `_registry_issues` 里 `targets` 的那一步：本册数据面命中的 `protocol/**/*.json`。
pub(crate) fn protocol_data_targets(root: &Path, doc: &Json) -> Vec<String> {
    let mut out: Vec<String> = Vec::new();
    if let Some(Json::Array(specs)) = obj_get(doc, "data") {
        for spec in specs {
            for rel in resolve(root, spec) {
                if rel.starts_with("protocol/") && rel.ends_with(".json") {
                    out.push(rel);
                }
            }
        }
    }
    out
}

// ---------------------------------------------------------------- 导出面（S3）

/// 真源 `_FRIENDLY`：JSON Schema 类型名 → Frictionless Table Schema 类型名。
pub(crate) fn friendly_type(t: &str) -> &'static str {
    match t {
        "string" => "string",
        "integer" => "integer",
        "number" => "number",
        "boolean" => "boolean",
        "array" => "array",
        "object" => "object",
        "null" => "any",
        _ => "any",
    }
}

/// 真源 `frictionless_export`：把已声明的数据资产映射成 **Frictionless Data Package**。
///
/// 诚实边界：`fields` 是 JSON Schema `properties` 的**尽力映射**（类型名对齐 Frictionless
/// Table Schema），原始 JSON Schema 仍在 `x-nf-json-schema` 里逐字段保留——映射丢信息就是
/// 装饰，故不丢。只导出**资产面**（包产物/库索引），协议层真源不外发。
pub fn frictionless_export(root: &Path) -> (Json, Vec<String>) {
    let (doc, issues) = load(root);
    if !issues.is_empty() {
        return (Json::Object(vec![]), issues);
    }
    let mut res: Vec<Json> = Vec::new();
    if let Some(Json::Array(specs)) = obj_get(&doc, "data") {
        for spec in specs {
            if !matches!(spec, Json::Object(_)) {
                continue;
            }
            for rel in resolve(root, spec) {
                if rel.starts_with("protocol/") {
                    continue;
                }
                res.push(frictionless_item(root, &rel, spec));
            }
        }
    }
    let pkg = Json::Object(vec![
        ("profile".to_string(), Json::Str("data-package".to_string())),
        (
            "name".to_string(),
            Json::Str("ninfenz-asset-contracts".to_string()),
        ),
        (
            "title".to_string(),
            Json::Str("NinFenz 数字资产契约（Frictionless Data Package 导出）".to_string()),
        ),
        (
            "x-nf-generated-by".to_string(),
            Json::Str("nf asset contract --export".to_string()),
        ),
        (
            "x-nf-note".to_string(),
            Json::Str(
                "由已声明契约面确定性导出；领域包产物按同名 schema 约定带 fields 映射".to_string(),
            ),
        ),
        ("resources".to_string(), Json::Array(res)),
    ]);
    (pkg, Vec::new())
}


/// 单件资产 → Frictionless resource 条目（JSON Schema properties 尽力映射为 fields）。
pub(crate) fn frictionless_item(root: &Path, rel: &str, spec: &Json) -> Json {
    let mut item: Vec<(String, Json)> = vec![
        ("name".to_string(), Json::Str(rel.replace('/', "--"))),
        ("path".to_string(), Json::Str(rel.to_string())),
    ];
    let fmt = sg_str(spec, "format");
    if !fmt.is_empty() {
        item.push(("format".to_string(), Json::Str(fmt)));
    }
    let sch_rel = schema_of(root, &rel, spec);
    if !sch_rel.is_empty() {
        let (stext, err) = sread(root, &sch_rel);
        if err.is_none() {
            let sch = strict_json(&stext.unwrap_or_default())
                .unwrap_or_else(|_| Json::Object(vec![]));
            let keep = [
                "type",
                "required",
                "properties",
                "$schema",
                "title",
                "description",
            ];
            let mut sub: Vec<(String, Json)> = Vec::new();
            if let Json::Object(kv) = &sch {
                for k in keep.iter() {
                    if let Some((kk, vv)) = kv.iter().find(|(kk, _)| kk == k) {
                        sub.push((kk.clone(), vv.clone()));
                    }
                }
            }
            let sch_nonempty = matches!(&sch, Json::Object(kv) if !kv.is_empty());
            if sch_nonempty {
                item.push(("x-nf-json-schema".to_string(), Json::Object(sub)));
                item.push((
                    "x-nf-schema-source".to_string(),
                    Json::Str(sch_rel.clone()),
                ));
            }
            let mut props: Vec<(String, Json)> = match obj_get(&sch, "properties") {
                Some(Json::Object(o)) => o.clone(),
                _ => Vec::new(),
            };
            props.sort_by(|a, b| a.0.cmp(&b.0));
            let mut fields: Vec<Json> = Vec::new();
            for (k, v) in props {
                if !matches!(v, Json::Object(_)) {
                    continue;
                }
                let t = sg_str(&v, "type");
                fields.push(Json::Object(vec![
                    ("name".to_string(), Json::Str(k)),
                    ("type".to_string(), Json::Str(friendly_type(&t).to_string())),
                ]));
            }
            if !fields.is_empty() {
                item.push((
                    "schema".to_string(),
                    Json::Object(vec![("fields".to_string(), Json::Array(fields))]),
                ));
            }
        }
    }
    Json::Object(item)
}

pub fn export_drift(root: &Path) -> Vec<String> {
    let (live, errs) = frictionless_export(root);
    if !errs.is_empty() {
        return errs;
    }
    let p = root.join(EXPORT_REL);
    if !p.is_file() {
        return vec![format!(
            "④ 缺契约导出 {}（修复指引：nf asset contract --export）",
            EXPORT_REL
        )];
    }
    let disk = match std::fs::read_to_string(&p) {
        Err(e) => {
            return vec![format!(
                "④ {} 不可读：{}（修复指引：nf asset contract --export）",
                EXPORT_REL, e
            )]
        }
        Ok(t) => match strict_json(&t) {
            Err(e) => {
                return vec![format!(
                    "④ {} 不可读：{}（修复指引：nf asset contract --export）",
                    EXPORT_REL, e
                )]
            }
            Ok(v) => v,
        },
    };
    if crate::jsonread::json_eq(&disk, &live) {
        Vec::new()
    } else {
        vec![format!(
            "④ {} 与实时导出不一致（修复指引：nf asset contract --export）",
            EXPORT_REL
        )]
    }
}

// ---------------------------------------------------------------- 声明自检面（S2）

/// 真源 `_schema_self_check`（⑤）：声明必须过**可移植 schema**（规范要可执行，不做文档摆设）。
pub fn schema_self_check(root: &Path) -> Vec<String> {
    let sp = root.join(SCHEMA_REL);
    if !sp.is_file() {
        return vec![format!(
            "⑤ 缺可移植 schema {}（修复指引：补该件——对外可移植契约靠它定型）",
            SCHEMA_REL
        )];
    }
    let read = |p: &Path| -> Result<Json, String> {
        match std::fs::read_to_string(p) {
            Err(e) => Err(e.to_string()),
            Ok(t) => strict_json(&t),
        }
    };
    let doc = match read(&root.join(DECL_REL)) {
        Ok(v) => v,
        Err(e) => {
            return vec![format!(
                "⑤ 声明或 schema 不可读：{}（修复指引：修好 JSON）",
                e
            )]
        }
    };
    let sch = match read(&sp) {
        Ok(v) => v,
        Err(e) => {
            return vec![format!(
                "⑤ 声明或 schema 不可读：{}（修复指引：修好 JSON）",
                e
            )]
        }
    };
    json_schema::json_schema_check(&doc, &sch)
        .iter()
        .take(5)
        .map(|e| {
            format!(
                "⑤ 声明不符可移植 schema {}：{}（修复指引：改声明或改 schema——两者只能有一个对）",
                SCHEMA_REL, e
            )
        })
        .collect()
}
