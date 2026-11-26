//! nf-contract-ir/1：从 nf-md-spec/1 + 可选 nf-protocol-pack/1 编译合同，
//! 再做有限域/已赋值校验。不生成自由文本，不依赖 Z3。

use crate::canonical::digest_value;
use crate::error::{CoreError, OpOutcome};
use crate::ops::req_value;
use crate::schema::validate;
use regex::Regex;
use serde_json::{json, Map, Value};
use std::collections::{BTreeMap, BTreeSet};

fn slot_type(kind: &str) -> &'static str {
    match kind {
        "list" => "list",
        "table" => "table",
        "json" => "ref",
        _ => "string",
    }
}

fn escape_regex(value: &str) -> String {
    let mut out = String::new();
    for ch in value.chars() {
        if ".^$|?*+()[]{}".contains(ch) {
            out.push('\\');
        }
        out.push(ch);
    }
    out
}

fn map_constraints(arr: &[Value]) -> (Vec<Value>, Vec<String>) {
    let mut constraints = Vec::new();
    let mut depends = Vec::new();
    for c in arr {
        let op = c.get("op").and_then(|v| v.as_str()).unwrap_or("");
        let value = c.get("value").cloned().unwrap_or(Value::Null);
        match op {
            "min_chars" => constraints.push(json!({"op": "min", "value": value})),
            "max_chars" | "max_tokens" => constraints.push(json!({"op": "max", "value": value})),
            "non_empty" => constraints.push(json!({"op": "required"})),
            "pattern" => constraints.push(json!({"op": "pattern", "value": value})),
            "starts_with" => {
                let pattern = format!("^{}", escape_regex(value.as_str().unwrap_or("")));
                constraints.push(json!({"op": "pattern", "value": pattern}));
            }
            "ends_with" => {
                let pattern = format!("{}$", escape_regex(value.as_str().unwrap_or("")));
                constraints.push(json!({"op": "pattern", "value": pattern}));
            }
            "depends_on" => {
                if let Some(reference) = value.as_str() {
                    depends.push(reference.to_string());
                    constraints.push(json!({"op": "depends_on", "ref": reference}));
                }
            }
            _ => {}
        }
    }
    (constraints, depends)
}

fn compile_value(req: &Value) -> Result<Value, CoreError> {
    let spec = req_value(req, "spec")?;
    if spec.get("schema").and_then(|v| v.as_str()) != Some("nf-md-spec/1") {
        return Err(CoreError::new("NF-CON-001").with_message("spec 必须是 nf-md-spec/1").with_exit(1));
    }
    let protocol = req.get("protocol").filter(|v| !v.is_null());
    if let Some(p) = protocol {
        if p.get("schema").and_then(|v| v.as_str()) != Some("nf-protocol-pack/1") {
            return Err(CoreError::new("NF-CON-001").with_message("protocol 必须是 nf-protocol-pack/1").with_exit(1));
        }
    }
    let fields = protocol
        .and_then(|p| p.get("fields"))
        .and_then(|v| v.as_array())
        .cloned()
        .unwrap_or_default();
    let slots = spec
        .get("slots")
        .and_then(|v| v.as_array())
        .ok_or_else(|| CoreError::new("NF-CON-001").with_message("spec 缺 slots").with_exit(1))?;
    let mut compiled = Vec::new();
    let mut edges = Vec::new();
    for slot in slots {
        let id = slot.get("id").and_then(|v| v.as_str()).unwrap_or("");
        if id.is_empty() {
            return Err(CoreError::new("NF-CON-001").with_message("slot 缺 id").with_exit(1));
        }
        let label = slot.get("name").and_then(|v| v.as_str()).unwrap_or(id);
        let field = fields.iter().find(|f| f.get("label").and_then(|v| v.as_str()) == Some(label));
        let enum_values: Vec<String> = field
            .and_then(|f| f.get("options"))
            .and_then(|v| v.as_array())
            .map(|a| a.iter().filter_map(|x| x.as_str().map(ToString::to_string)).collect())
            .unwrap_or_default();
        let (mut constraints, depends) = map_constraints(
            slot.get("constraints").and_then(|v| v.as_array()).map(|a| a.as_slice()).unwrap_or(&[]),
        );
        for dep in &depends {
            edges.push(json!({"from": dep, "to": id, "kind": "depends_on"}));
        }
        if let Some(visible) = slot.get("visible_if").and_then(|v| v.as_object()) {
            if let Some(source) = visible.get("slot").and_then(|v| v.as_str()) {
                edges.push(json!({"from": source, "to": id, "kind": "visible_if"}));
                constraints.push(json!({"op": "depends_on", "ref": source}));
            }
        }
        let mut entry = Map::new();
        entry.insert("id".into(), json!(id));
        entry.insert("type".into(), json!(slot_type(slot.get("kind").and_then(|v| v.as_str()).unwrap_or("text"))));
        entry.insert("required".into(), json!(slot.get("required").and_then(|v| v.as_bool()).unwrap_or(true)));
        entry.insert("section".into(), slot.get("section").cloned().unwrap_or_else(|| json!("SEC-01")));
        entry.insert("label".into(), json!(label));
        entry.insert("constraints".into(), Value::Array(constraints));
        if !enum_values.is_empty() {
            entry.insert("enum_values".into(), json!(enum_values));
        }
        if let Some(f) = field {
            if let Some(fid) = f.get("id").and_then(|v| v.as_str()) {
                entry.insert("protocol_field".into(), json!(fid));
            }
            if let Some(default) = f.get("default").and_then(|v| v.as_str()) {
                entry.insert("default".into(), json!(default));
            }
        }
        if !depends.is_empty() {
            entry.insert("depends_on".into(), json!(depends));
        }
        compiled.push(Value::Object(entry));
    }
    let mut source = json!({ "spec_digest": digest_value(spec)? });
    if let Some(p) = protocol {
        if let Ok(digest) = digest_value(p) {
            source.as_object_mut().unwrap().insert("protocol_digest".into(), json!(digest));
        }
    }
    let mut ir = json!({
        "schema": "nf-contract-ir/1",
        "contract_version": 1,
        "source": source,
        "slots": compiled,
        "graph": {"edges": edges}
    });
    let digest = digest_value(&ir)?;
    ir.as_object_mut().unwrap().insert("digest".into(), json!(digest));
    let issues = validate("nf-contract-ir", &ir);
    if !issues.is_empty() {
        return Err(CoreError::new("NF-CON-001").with_message(crate::schema::first_issue_text(&issues)).with_exit(1));
    }
    Ok(ir)
}

fn constraint_int(c: &Value, key: &str) -> Option<i64> {
    c.get(key).and_then(|v| v.as_i64())
}

fn check_slot(slot: &Value, assignments: &BTreeMap<String, String>) -> Vec<Value> {
    let id = slot.get("id").and_then(|v| v.as_str()).unwrap_or("");
    let required = slot.get("required").and_then(|v| v.as_bool()).unwrap_or(true);
    let value = assignments.get(id).cloned().unwrap_or_default();
    let mut issues = Vec::new();
    if value.trim().is_empty() {
        if required {
            issues.push(json!({
                "slot": id, "code": "NF-CON-002",
                "message": "必填槽位为空",
                "fix": format!("填写 {id}")
            }));
        }
        return issues;
    }
    if let Some(enum_values) = slot.get("enum_values").and_then(|v| v.as_array()) {
        let allowed: Vec<&str> = enum_values.iter().filter_map(|v| v.as_str()).collect();
        if !allowed.is_empty() && !allowed.contains(&value.as_str()) {
            issues.push(json!({
                "slot": id, "code": "NF-CON-002",
                "message": "取值不在枚举域",
                "fix": format!("选择：{}", allowed.join(" / "))
            }));
        }
    }
    let chars = value.chars().count() as i64;
    for c in slot.get("constraints").and_then(|v| v.as_array()).into_iter().flatten() {
        let op = c.get("op").and_then(|v| v.as_str()).unwrap_or("");
        match op {
            "min" => {
                if let Some(min) = constraint_int(c, "value") {
                    if chars < min {
                        issues.push(json!({"slot": id, "code": "NF-CON-002", "message": format!("长度 {chars} < 最小 {min}"), "fix": format!("补足 {id} 至少 {min} 字")}));
                    }
                }
            }
            "max" => {
                if let Some(max) = constraint_int(c, "value") {
                    if chars > max {
                        issues.push(json!({"slot": id, "code": "NF-CON-002", "message": format!("长度 {chars} > 最大 {max}"), "fix": format!("压缩 {id} 到 {max} 字内")}));
                    }
                }
            }
            "len" => {
                if let Some(len) = constraint_int(c, "value") {
                    if chars != len {
                        issues.push(json!({"slot": id, "code": "NF-CON-002", "message": format!("长度 {chars} != {len}"), "fix": format!("把 {id} 调到 {len} 字")}));
                    }
                }
            }
            "pattern" => {
                if let Some(pattern) = c.get("value").and_then(|v| v.as_str()) {
                    match Regex::new(pattern) {
                        Ok(re) if !re.is_match(&value) => issues.push(json!({"slot": id, "code": "NF-CON-002", "message": "不匹配 pattern", "fix": format!("按 {} 修正 {id}", pattern)})),
                        Err(_) => issues.push(json!({"slot": id, "code": "NF-CON-002", "message": "约束 pattern 非法", "fix": "修 spec 里的 pattern"})),
                        _ => {}
                    }
                }
            }
            "equals" => {
                if let Some(expected) = c.get("value").and_then(|v| v.as_str()) {
                    if value != expected {
                        issues.push(json!({"slot": id, "code": "NF-CON-002", "message": format!("取值必须等于 {expected}"), "fix": format!("把 {id} 改为 {expected}")}));
                    }
                }
            }
            "one_of" => {
                if let Some(options) = c.get("value").and_then(|v| v.as_str()) {
                    if !options.split('|').any(|option| option == value) {
                        issues.push(json!({"slot": id, "code": "NF-CON-002", "message": "取值不在 one_of", "fix": format!("选择：{options}")}));
                    }
                }
            }
            "depends_on" => {
                if let Some(reference) = c.get("ref").and_then(|v| v.as_str()) {
                    if assignments.get(reference).map(|v| v.trim().is_empty()).unwrap_or(true) {
                        issues.push(json!({"slot": id, "code": "NF-CON-002", "message": format!("依赖槽位为空：{reference}"), "fix": format!("先填写 {reference}")}));
                    }
                }
            }
            _ => {}
        }
    }
    issues
}

pub fn compile(req: &Value) -> OpOutcome {
    Ok((0, compile_value(req)?))
}

pub fn solve(req: &Value) -> OpOutcome {
    let contract = req_value(req, "contract")?;
    let issues = validate("nf-contract-ir", contract);
    if !issues.is_empty() {
        return Err(CoreError::new("NF-CON-001").with_message(crate::schema::first_issue_text(&issues)).with_exit(1));
    }
    let mut assignments = BTreeMap::new();
    if let Some(values) = req.get("values").and_then(|v| v.as_object()) {
        for (k, v) in values {
            if let Some(text) = v.as_str() {
                assignments.insert(k.clone(), text.to_string());
            }
        }
    }
    let slots = contract.get("slots").and_then(|v| v.as_array()).cloned().unwrap_or_default();
    for slot in &slots {
        let id = slot.get("id").and_then(|v| v.as_str()).unwrap_or("");
        if assignments.get(id).map(|v| v.trim().is_empty()).unwrap_or(true) {
            if let Some(default) = slot.get("default").and_then(|v| v.as_str()) {
                assignments.insert(id.to_string(), default.to_string());
            } else {
                assignments.entry(id.to_string()).or_insert_with(String::new);
            }
        }
    }
    let mut all_issues = Vec::new();
    let mut core = BTreeSet::new();
    for slot in &slots {
        let found = check_slot(slot, &assignments);
        for issue in &found {
            if let Some(slot_id) = issue.get("slot").and_then(|v| v.as_str()) {
                core.insert(slot_id.to_string());
            }
        }
        all_issues.extend(found);
    }
    let digest = contract.get("digest").and_then(|v| v.as_str()).unwrap_or("").to_string();
    Ok((0, json!({
        "schema": "nf-contract-result/1",
        "contract_digest": digest,
        "satisfiable": all_issues.is_empty(),
        "assignments": assignments,
        "issues": all_issues,
        "unsat_core": core.into_iter().collect::<Vec<_>>()
    })))
}

pub fn explain(req: &Value) -> OpOutcome {
    let result = if let Some(result) = req.get("result") {
        result.clone()
    } else {
        solve(req)?.1
    };
    let mut lines = Vec::new();
    if result.get("satisfiable").and_then(|v| v.as_bool()).unwrap_or(false) {
        lines.push("合同可满足".to_string());
    } else {
        lines.push("合同不可满足".to_string());
        for slot in result.get("unsat_core").and_then(|v| v.as_array()).into_iter().flatten() {
            lines.push(format!("核心槽位：{}", slot.as_str().unwrap_or("")));
        }
    }
    for issue in result.get("issues").and_then(|v| v.as_array()).into_iter().flatten() {
        lines.push(format!(
            "{}：{} / {}",
            issue.get("slot").and_then(|v| v.as_str()).unwrap_or(""),
            issue.get("message").and_then(|v| v.as_str()).unwrap_or(""),
            issue.get("fix").and_then(|v| v.as_str()).unwrap_or("")
        ));
    }
    Ok((0, json!({"schema": "nf-contract-explain/1", "result": result, "lines": lines})))
}

pub fn compile_op(req: &Value) -> OpOutcome { compile(req) }
pub fn solve_op(req: &Value) -> OpOutcome { solve(req) }
pub fn explain_op(req: &Value) -> OpOutcome { explain(req) }
