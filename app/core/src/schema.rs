//! 手写 JSON Schema 语义校验器：只覆盖 app/schema/*.json 实际使用的关键字子集
//!（type/const/enum/pattern/minLength/minimum/maximum/minItems/items/properties/
//! required/additionalProperties/$ref/$defs/oneOf），不依赖 jsonschema crate。

use crate::canonical::obj_path;
use regex::Regex;
use serde_json::Value;
use std::collections::BTreeMap;
use std::sync::OnceLock;

pub const SCHEMA_NAMES: &[&str] = &[
    "nf-pack",
    "nf-import",
    "nf-doc",
    "nf-md-spec",
    "nf-pipeline-graph",
    "nf-protocol-pack",
    "nf-assembly-plan",
    "nf-validate-report",
    "nf-assemble-result",
    "nf-export-manifest",
    "nf-backup",
    "nf-template",
    "nf-pack-update",
    "nf-overlay",
    "nf-project",
    "ccos-task",
    "ccos-result",
    "nf-sdir",
    "nf-build-graph",
    "nf-evidence",
    "nf-extension",
    "nf-claim-ledger",
    "nf-budget",
    "nf-migration",
    "nf-audit",
    "nf-trust-root",
    "nf-report",
    "nf-preset",
    "nf-portable",
    "nf-review",
    "nf-handoff",
    "nf-library",
    "nf-activity",
];

macro_rules! embed_schemas {
    ($($name:literal => $path:literal),* $(,)?) => {{
        let mut m: BTreeMap<&'static str, Value> = BTreeMap::new();
        $(
            m.insert($name, serde_json::from_str(include_str!($path)).expect(concat!("schema ", $name, " 非法 JSON")));
        )*
        m
    }};
}

pub fn schemas() -> &'static BTreeMap<&'static str, Value> {
    static S: OnceLock<BTreeMap<&'static str, Value>> = OnceLock::new();
    S.get_or_init(|| {
        embed_schemas!(
            "nf-pack" => "../../schema/nf-pack.schema.json",
            "nf-import" => "../../schema/nf-import.schema.json",
            "nf-doc" => "../../schema/nf-doc.schema.json",
            "nf-md-spec" => "../../schema/nf-md-spec.schema.json",
            "nf-pipeline-graph" => "../../schema/nf-pipeline-graph.schema.json",
            "nf-protocol-pack" => "../../schema/nf-protocol-pack.schema.json",
            "nf-assembly-plan" => "../../schema/nf-assembly-plan.schema.json",
            "nf-validate-report" => "../../schema/nf-validate-report.schema.json",
            "nf-assemble-result" => "../../schema/nf-assemble-result.schema.json",
            "nf-export-manifest" => "../../schema/nf-export-manifest.schema.json",
            "nf-backup" => "../../schema/nf-backup.schema.json",
            "nf-template" => "../../schema/nf-template.schema.json",
            "nf-pack-update" => "../../schema/nf-pack-update.schema.json",
            "nf-overlay" => "../../schema/nf-overlay.schema.json",
            "nf-project" => "../../schema/nf-project.schema.json",
            "ccos-task" => "../../schema/ccos-task.schema.json",
            "ccos-result" => "../../schema/ccos-result.schema.json",
            "nf-sdir" => "../../schema/nf-sdir.schema.json",
            "nf-build-graph" => "../../schema/nf-build-graph.schema.json",
            "nf-evidence" => "../../schema/nf-evidence.schema.json",
            "nf-extension" => "../../schema/nf-extension.schema.json",
            "nf-claim-ledger" => "../../schema/nf-claim-ledger.schema.json",
            "nf-budget" => "../../schema/nf-budget.schema.json",
            "nf-migration" => "../../schema/nf-migration.schema.json",
            "nf-audit" => "../../schema/nf-audit.schema.json",
            "nf-trust-root" => "../../schema/nf-trust-root.schema.json",
            "nf-report" => "../../schema/nf-report.schema.json",
            "nf-preset" => "../../schema/nf-preset.schema.json",
            "nf-portable" => "../../schema/nf-portable.schema.json",
            "nf-review" => "../../schema/nf-review.schema.json",
            "nf-handoff" => "../../schema/nf-handoff.schema.json",
            "nf-library" => "../../schema/nf-library.schema.json",
            "nf-activity" => "../../schema/nf-activity.schema.json",
        )
    })
}

pub fn schema(name: &str) -> Option<&'static Value> {
    schemas().get(name)
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct SchemaIssue {
    pub path: String,
    pub message: String,
}

impl SchemaIssue {
    fn new(path: impl Into<String>, message: impl Into<String>) -> Self {
        SchemaIssue {
            path: path.into(),
            message: message.into(),
        }
    }
}

pub fn validate(schema_name: &str, instance: &Value) -> Vec<SchemaIssue> {
    let root = match schema(schema_name) {
        Some(s) => s,
        None => {
            return vec![SchemaIssue::new("$", format!("内部错误：未知 schema {schema_name}"))];
        }
    };
    let mut out = Vec::new();
    validate_at(root, instance, "$", root, &mut out, 0);
    out
}

pub fn validate_with_prefix(
    schema_name: &str,
    instance: &Value,
    prefix: &str,
) -> Vec<SchemaIssue> {
    let mut issues = validate(schema_name, instance);
    for i in &mut issues {
        i.path = format!("{prefix}{}", if i.path == "$" { "" } else { &i.path[1..] });
    }
    issues
}

fn type_matches(type_name: &str, v: &Value) -> bool {
    match type_name {
        "object" => v.is_object(),
        "array" => v.is_array(),
        "string" => v.is_string(),
        "boolean" => v.is_boolean(),
        "null" => v.is_null(),
        "integer" => match v {
            Value::Number(n) => n.is_i64() || n.is_u64(),
            _ => false,
        },
        "number" => v.is_number(),
        _ => false,
    }
}

fn json_type(v: &Value) -> &'static str {
    match v {
        Value::Null => "null",
        Value::Bool(_) => "boolean",
        Value::Number(n) => {
            if n.is_i64() || n.is_u64() {
                "integer"
            } else {
                "number"
            }
        }
        Value::String(_) => "string",
        Value::Array(_) => "array",
        Value::Object(_) => "object",
    }
}

fn resolve_ref<'a>(root: &'a Value, r: &str) -> Option<&'a Value> {
    let path = r.strip_prefix("#/")?;
    let mut cur = root;
    for seg in path.split('/') {
        let seg = seg.replace("~1", "/").replace("~0", "~");
        cur = cur.get(&seg)?;
    }
    Some(cur)
}

fn validate_at(
    sch: &Value,
    inst: &Value,
    path: &str,
    root: &Value,
    out: &mut Vec<SchemaIssue>,
    depth: usize,
) {
    if depth > 128 {
        out.push(SchemaIssue::new(path, "schema 校验递归过深"));
        return;
    }
    let obj = match sch {
        Value::Object(o) => o,
        Value::Bool(true) => return,
        Value::Bool(false) => {
            out.push(SchemaIssue::new(path, "该位置不允许任何值"));
            return;
        }
        _ => return,
    };

    if let Some(Value::String(r)) = obj.get("$ref") {
        if let Some(target) = resolve_ref(root, r) {
            validate_at(target, inst, path, root, out, depth + 1);
        } else {
            out.push(SchemaIssue::new(path, format!("schema $ref 无法解析: {r}")));
        }
        return;
    }

    if let Some(Value::Array(branches)) = obj.get("oneOf") {
        let mut matched = 0usize;
        let mut first_messages: Vec<String> = Vec::new();
        for b in branches {
            let mut tmp = Vec::new();
            validate_at(b, inst, path, root, &mut tmp, depth + 1);
            if tmp.is_empty() {
                matched += 1;
            } else if first_messages.is_empty() {
                first_messages = tmp.iter().map(|i| i.message.clone()).collect();
            }
        }
        if matched == 0 {
            out.push(SchemaIssue::new(
                path,
                format!(
                    "不匹配 oneOf 任一分支（实际类型 {}；首分支错误: {}）",
                    json_type(inst),
                    first_messages.join("; ")
                ),
            ));
            return;
        }
        if matched > 1 {
            out.push(SchemaIssue::new(path, "同时匹配 oneOf 多个分支（歧义）"));
            return;
        }
        return;
    }

    if let Some(t) = obj.get("type") {
        let ok = match t {
            Value::String(s) => type_matches(s, inst),
            Value::Array(ts) => ts.iter().any(|x| {
                x.as_str().map(|s| type_matches(s, inst)).unwrap_or(false)
            }),
            _ => true,
        };
        if !ok {
            out.push(SchemaIssue::new(
                path,
                format!("类型不匹配：期望 {}，实际 {}", t, json_type(inst)),
            ));
            return;
        }
    }

    if let Some(c) = obj.get("const") {
        if c != inst {
            out.push(SchemaIssue::new(
                path,
                format!("const 不匹配：期望 {c}，实际 {inst}"),
            ));
            return;
        }
    }

    if let Some(Value::Array(enums)) = obj.get("enum") {
        if !enums.iter().any(|e| e == inst) {
            out.push(SchemaIssue::new(
                path,
                format!("值 {inst} 不在 enum {} 内", Value::Array(enums.clone())),
            ));
            return;
        }
    }

    if let Value::String(s) = inst {
        if let Some(min) = obj.get("minLength").and_then(|v| v.as_u64()) {
            if (s.chars().count() as u64) < min {
                out.push(SchemaIssue::new(
                    path,
                    format!("字符串长度 {} 小于 minLength {min}", s.chars().count()),
                ));
            }
        }
        if let Some(Value::String(pat)) = obj.get("pattern") {
            match regex_matches(pat, s) {
                Ok(true) => {}
                Ok(false) => out.push(SchemaIssue::new(
                    path,
                    format!("字符串 {s:?} 不匹配 pattern {pat}"),
                )),
                Err(e) => out.push(SchemaIssue::new(
                    path,
                    format!("schema pattern {pat} 无法求值: {e}"),
                )),
            }
        }
    }

    if let Value::Number(n) = inst {
        let f = n.as_f64().unwrap_or(0.0);
        if let Some(min) = obj.get("minimum").and_then(|v| v.as_f64()) {
            if f < min {
                out.push(SchemaIssue::new(path, format!("数值 {f} 小于 minimum {min}")));
            }
        }
        if let Some(max) = obj.get("maximum").and_then(|v| v.as_f64()) {
            if f > max {
                out.push(SchemaIssue::new(path, format!("数值 {f} 大于 maximum {max}")));
            }
        }
    }

    if let Value::Array(arr) = inst {
        if let Some(min) = obj.get("minItems").and_then(|v| v.as_u64()) {
            if (arr.len() as u64) < min {
                out.push(SchemaIssue::new(
                    path,
                    format!("数组长度 {} 小于 minItems {min}", arr.len()),
                ));
            }
        }
        if let Some(items) = obj.get("items") {
            for (i, item) in arr.iter().enumerate() {
                validate_at(items, item, &format!("{path}[{i}]"), root, out, depth + 1);
            }
        }
    }

    if let Value::Object(map) = inst {
        let props = obj.get("properties").and_then(|p| p.as_object());
        if let Some(req) = obj.get("required").and_then(|r| r.as_array()) {
            for r in req {
                if let Some(key) = r.as_str() {
                    if !map.contains_key(key) {
                        out.push(SchemaIssue::new(
                            obj_path(path, key),
                            format!("缺少必填字段 {key}"),
                        ));
                    }
                }
            }
        }
        if let Some(props) = props {
            for (k, v) in map.iter() {
                if let Some(sub) = props.get(k) {
                    validate_at(sub, v, &obj_path(path, k), root, out, depth + 1);
                } else {
                    match obj.get("additionalProperties") {
                        Some(Value::Bool(false)) => out.push(SchemaIssue::new(
                            obj_path(path, k),
                            format!("未知字段 {k}（additionalProperties=false）"),
                        )),
                        Some(Value::Bool(true)) | None => {}
                        Some(sub) => {
                            validate_at(sub, v, &obj_path(path, k), root, out, depth + 1)
                        }
                    }
                }
            }
        } else if let Some(Value::Bool(false)) = obj.get("additionalProperties") {
            if !map.is_empty() {
                out.push(SchemaIssue::new(path, "该对象不允许任何字段"));
            }
        } else if let Some(sub) = obj.get("additionalProperties") {
            if !matches!(sub, Value::Bool(true)) {
                for (k, v) in map.iter() {
                    validate_at(sub, v, &obj_path(path, k), root, out, depth + 1);
                }
            }
        }
    }
}

/// JSON Schema 的 pattern 求值：支持常见 RE2 语法；pack 的路径 pattern 用了
/// 负向前瞻（Rust regex 不支持），按语义手工实现。
pub fn regex_matches(pattern: &str, s: &str) -> Result<bool, String> {
    if pattern.contains("(?!") {
        return special_pattern(pattern, s);
    }
    match Regex::new(pattern) {
        Ok(re) => Ok(re.is_match(s)),
        Err(e) => Err(format!("{e}")),
    }
}

fn special_pattern(pattern: &str, s: &str) -> Result<bool, String> {
    // 路径安全 pattern（pack item 与 project artifactRef 同族）：
    // ^(?!/)(?!.*(^|/)\.\.?/)(?!.*\u0000)[^\\]+$
    // 语义：非空、非绝对、无反斜杠、不含 NUL、无 . / .. 路径段。
    if pattern.contains("(?!/)") && pattern.contains("[^\\\\]+") {
        if s.is_empty() || s.starts_with('/') || s.contains('\0') || s.contains('\\') {
            return Ok(false);
        }
        for comp in s.split('/') {
            if comp == "." || comp == ".." {
                return Ok(false);
            }
        }
        return Ok(true);
    }
    Err(format!("不支持的负向前瞻 pattern: {pattern}"))
}

/// 便捷：返回首条错误的 "path: message"。
pub fn first_issue_text(issues: &[SchemaIssue]) -> String {
    match issues.first() {
        Some(i) => format!("{}: {}", i.path, i.message),
        None => String::new(),
    }
}
