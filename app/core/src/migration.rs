//! nf-migration/1：数据/格式迁移计划与执行；不可逆需显式 confirm。

use crate::error::{CoreError, OpOutcome};
use crate::ops::{opt_str, req_value, usage};
use crate::schema::validate;
use serde_json::{json, Value};

const SCHEMA: &str = "nf-migration/1";

fn plan_for(from: &str, to: &str) -> Option<Value> {
    match (from, to) {
        ("nf-doc/1", "nf-sdir/1") => Some(json!({
            "schema": SCHEMA, "from_schema": from, "to_schema": to,
            "steps": [{"id": "nf-doc-to-sdir", "kind": "sdir-doc-adapter", "from": from, "to": to, "reversible": false}],
            "losses": [], "reversible": false
        })),
        ("nf-sdir/1", "nf-sdir/1") => Some(json!({
            "schema": SCHEMA, "from_schema": from, "to_schema": to,
            "steps": [{"id": "noop", "kind": "noop", "from": from, "to": to, "reversible": true}],
            "losses": [], "reversible": true
        })),
        _ => None,
    }
}

pub fn migrate_plan(req: &Value) -> OpOutcome {
    let from = opt_str(req, "from_schema")?.filter(|s| !s.is_empty()).ok_or_else(|| usage("migrate-plan 需要 from_schema"))?;
    let to = opt_str(req, "to_schema")?.filter(|s| !s.is_empty()).ok_or_else(|| usage("migrate-plan 需要 to_schema"))?;
    let plan = plan_for(from, to).ok_or_else(|| CoreError::new("NF-MIG-001").with_message(format!("没有 {from} -> {to} 的迁移路径")).with_exit(1))?;
    let issues = validate("nf-migration", &plan);
    if !issues.is_empty() {
        return Err(CoreError::new("NF-MIG-001").with_message(crate::schema::first_issue_text(&issues)).with_exit(1));
    }
    Ok((0, json!({"schema": SCHEMA, "plan": plan})))
}

pub fn migrate_apply(req: &Value) -> OpOutcome {
    let plan = req_value(req, "plan")?;
    let issues = validate("nf-migration", plan);
    if !issues.is_empty() {
        return Err(CoreError::new("NF-MIG-001").with_message(crate::schema::first_issue_text(&issues)).with_exit(1));
    }
    let from = plan.get("from_schema").and_then(|v| v.as_str()).unwrap_or("");
    let to = plan.get("to_schema").and_then(|v| v.as_str()).unwrap_or("");
    let reversible = plan.get("reversible").and_then(|v| v.as_bool()).unwrap_or(false);
    if !reversible && req.get("confirm").and_then(|v| v.as_bool()) != Some(true) {
        return Err(CoreError::new("NF-MIG-001").with_message("不可逆迁移需要 confirm=true").with_exit(1));
    }
    let doc = req_value(req, "doc")?;
    match (from, to) {
        ("nf-doc/1", "nf-sdir/1") => {
            let created_at = opt_str(req, "created_at")?.filter(|s| !s.is_empty()).ok_or_else(|| usage("迁移需要显式 created_at"))?;
            let mut sub = json!({"doc": doc, "created_at": created_at, "lang": req.get("lang").cloned().unwrap_or(json!("und"))});
            if let Some(s) = req.get("source") { sub.as_object_mut().unwrap().insert("source".into(), s.clone()); }
            let (code, sdir) = crate::sdir::import_doc(&sub)?;
            if code != 0 { return Ok((code, sdir)); }
            Ok((0, json!({"schema": "nf-migration-result/1", "from_schema": from, "to_schema": to, "sdir": sdir, "losses": []})))
        }
        ("nf-sdir/1", "nf-sdir/1") => Ok((0, json!({"schema": "nf-migration-result/1", "from_schema": from, "to_schema": to, "sdir": doc, "losses": []}))),
        _ => Err(CoreError::new("NF-MIG-001").with_message("迁移路径不支持").with_exit(1)),
    }
}

pub fn migrate_plan_op(req: &Value) -> OpOutcome { migrate_plan(req) }
pub fn migrate_apply_op(req: &Value) -> OpOutcome { migrate_apply(req) }
