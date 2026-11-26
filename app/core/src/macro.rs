//! nf-macro/1：语义动作序列的校验与 dry-run 计划；不做坐标点击。

use crate::error::{CoreError, OpOutcome};
use crate::ops::req_value;
use crate::schema::validate;
use serde_json::{json, Value};
use std::collections::BTreeSet;

fn check(macro_value: &Value) -> Result<Value, CoreError> {
    let issues = validate("nf-macro", macro_value);
    if !issues.is_empty() {
        return Err(CoreError::new("NF-MAC-001").with_message(crate::schema::first_issue_text(&issues)).with_exit(1));
    }
    let steps = macro_value.get("steps").and_then(|v| v.as_array()).cloned().unwrap_or_default();
    let mut ids = BTreeSet::new();
    for step in &steps {
        let id = step.get("id").and_then(|v| v.as_str()).unwrap_or("");
        if !ids.insert(id.to_string()) {
            return Err(CoreError::new("NF-MAC-001").with_message(format!("宏步骤 id 重复：{id}")).with_exit(1));
        }
    }
    Ok(json!({
        "schema": "nf-macro-report/1",
        "id": macro_value.get("id"),
        "title": macro_value.get("title"),
        "steps": steps,
        "dry_run": true
    }))
}

pub fn validate_op(req: &Value) -> OpOutcome {
    let macro_value = req_value(req, "macro")?;
    Ok((0, check(macro_value)?))
}

pub fn plan_op(req: &Value) -> OpOutcome {
    let macro_value = req_value(req, "macro")?;
    let checked = check(macro_value)?;
    let steps = checked.get("steps").and_then(|v| v.as_array()).cloned().unwrap_or_default();
    let plan: Vec<Value> = steps
        .iter()
        .map(|step| json!({
            "id": step.get("id"),
            "action": step.get("action"),
            "params": step.get("params").cloned().unwrap_or_else(|| json!({})),
            "result": "planned"
        }))
        .collect();
    Ok((0, json!({
        "schema": "nf-macro-plan/1",
        "id": macro_value.get("id"),
        "title": macro_value.get("title"),
        "dry_run": true,
        "steps": plan,
        "writes": []
    })))
}
