//! nf-ai-run/1：离线/CCOS 交接的 AI 编排记录；不存密钥、不直连模型。

use crate::error::{CoreError, OpOutcome};
use crate::ops::req_value;
use crate::schema::validate;
use serde_json::{json, Value};

fn has_secret(value: &Value) -> bool {
    match value {
        Value::Object(map) => map.iter().any(|(key, child)| {
            let lower = key.to_ascii_lowercase();
            matches!(lower.as_str(), "api_key" | "apikey" | "token" | "authorization" | "secret")
                || has_secret(child)
        }),
        Value::Array(items) => items.iter().any(has_secret),
        _ => false,
    }
}

pub fn plan(req: &Value) -> OpOutcome {
    let project_id = req.get("project_id").and_then(|v| v.as_str()).ok_or_else(|| crate::ops::usage("ai-plan 需要 project_id"))?;
    let sections = req.get("sections").and_then(|v| v.as_array()).cloned().unwrap_or_default();
    if sections.is_empty() {
        return Err(CoreError::new("NF-AI-001").with_message("ai-plan 需要 sections").with_exit(1));
    }
    let tasks: Vec<Value> = sections.iter().enumerate().map(|(index, section)| {
        let title = section.as_str().map(ToString::to_string).or_else(|| section.get("title").and_then(|v| v.as_str()).map(ToString::to_string)).unwrap_or_else(|| format!("节 {}", index + 1));
        json!({"id": format!("T{:02}", index + 1), "title": title, "status": "planned"})
    }).collect();
    let run = json!({
        "schema": "nf-ai-run/1",
        "id": req.get("id").and_then(|v| v.as_str()).unwrap_or("run-plan"),
        "project_id": project_id,
        "status": "queued",
        "model": req.get("model").and_then(|v| v.as_str()).unwrap_or("ccos-task"),
        "params": req.get("params").cloned().unwrap_or_else(|| json!({})),
        "seed": req.get("seed").and_then(|v| v.as_i64()).unwrap_or(0),
        "elapsed_ms": 0,
        "usage": {"input_tokens": 0, "output_tokens": 0},
        "tasks": tasks,
        "created_at": 0
    });
    let issues = validate("nf-ai-run", &run);
    if !issues.is_empty() {
        return Err(CoreError::new("NF-AI-001").with_message(crate::schema::first_issue_text(&issues)).with_exit(1));
    }
    Ok((0, run))
}

pub fn verify(req: &Value) -> OpOutcome {
    let run = req_value(req, "run")?;
    let issues = validate("nf-ai-run", run);
    if !issues.is_empty() {
        return Err(CoreError::new("NF-AI-001").with_message(crate::schema::first_issue_text(&issues)).with_exit(1));
    }
    if has_secret(run) {
        return Err(CoreError::new("NF-AI-002").with_message("AI 记录含密钥字段").with_exit(3));
    }
    Ok((0, json!({
        "schema": "nf-ai-run-report/1",
        "ok": true,
        "id": run.get("id"),
        "status": run.get("status"),
        "tasks": run.get("tasks").and_then(|v| v.as_array()).map(|a| a.len()).unwrap_or(0)
    })))
}

pub fn plan_op(req: &Value) -> OpOutcome { plan(req) }
pub fn verify_op(req: &Value) -> OpOutcome { verify(req) }
