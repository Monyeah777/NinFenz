//! nf-audit/1：append-only hash chain；只保证链内可检出，不承诺抗 root。

use crate::canonical::{canonical_bytes, sha256_hex};
use crate::error::{CoreError, OpOutcome};
use crate::ops::{opt_str, req_value, usage};
use crate::schema::validate;
use serde_json::{json, Value};

const SCHEMA: &str = "nf-audit/1";
const ZERO: &str = "0000000000000000000000000000000000000000000000000000000000000000";

fn empty() -> Value { json!({"schema": SCHEMA, "records": [], "head": ZERO}) }

fn audit_append(req: &Value) -> OpOutcome {
    let at = opt_str(req, "at")?.filter(|s| !s.is_empty()).ok_or_else(|| usage("audit-append 需要显式 at"))?;
    let actor = opt_str(req, "actor")?.filter(|s| !s.is_empty()).ok_or_else(|| usage("audit-append 需要 actor"))?;
    let action = opt_str(req, "action")?.filter(|s| !s.is_empty()).ok_or_else(|| usage("audit-append 需要 action"))?;
    let subject = opt_str(req, "subject_sha256")?.filter(|s| s.len() == 64).ok_or_else(|| usage("audit-append 需要 64 位 subject_sha256"))?;
    let mut audit = match req.get("audit") {
        Some(v) if v.is_object() => v.clone(),
        _ => empty(),
    };
    let prev = audit.get("head").and_then(|v| v.as_str()).unwrap_or(ZERO).to_string();
    let seq = audit.get("records").and_then(|v| v.as_array()).map(|a| a.len() as u64).unwrap_or(0);
    let mut rec = json!({"seq": seq, "at": at, "actor": actor, "action": action, "subject_sha256": subject, "prev_hash": prev});
    for key in ["reason", "before", "after", "undoable"] {
        if let Some(v) = req.get(key) { rec.as_object_mut().unwrap().insert(key.into(), v.clone()); }
    }
    let hash = sha256_hex(&canonical_bytes(&rec)?);
    let mut rec = rec;
    rec.as_object_mut().unwrap().insert("hash".into(), Value::String(hash.clone()));
    audit.get_mut("records").and_then(|v| v.as_array_mut()).unwrap().push(rec);
    audit.as_object_mut().unwrap().insert("head".into(), Value::String(hash.clone()));
    let issues = validate("nf-audit", &audit);
    if !issues.is_empty() {
        return Err(CoreError::new("NF-AUD-001").with_message(crate::schema::first_issue_text(&issues)).with_exit(1));
    }
    Ok((0, json!({"schema": SCHEMA, "audit": audit, "head": hash})))
}

fn audit_verify(req: &Value) -> OpOutcome {
    let audit = req_value(req, "audit")?;
    let issues = validate("nf-audit", audit);
    if !issues.is_empty() {
        return Ok((1, json!({"schema": "nf-audit-report/1", "ok": false, "errors": [crate::schema::first_issue_text(&issues)]})));
    }
    let mut prev = ZERO.to_string();
    let mut errors = Vec::new();
    let mut seq = 0u64;
    for r in audit.get("records").and_then(|v| v.as_array()).into_iter().flatten() {
        if r.get("seq").and_then(|v| v.as_u64()) != Some(seq) {
            errors.push(format!("seq 断裂: 期望 {seq}"));
        }
        if r.get("prev_hash").and_then(|v| v.as_str()) != Some(prev.as_str()) {
            errors.push(format!("prev_hash 断裂: seq {seq}"));
        }
        let mut calc = r.clone();
        calc.as_object_mut().unwrap().remove("hash");
        let want = sha256_hex(&canonical_bytes(&calc)?);
        if r.get("hash").and_then(|v| v.as_str()) != Some(want.as_str()) {
            errors.push(format!("hash 不符: seq {seq}"));
        }
        prev = want;
        seq += 1;
    }
    if audit.get("head").and_then(|v| v.as_str()) != Some(prev.as_str()) {
        errors.push("head 与末条 hash 不符".to_string());
    }
    Ok((if errors.is_empty() { 0 } else { 1 }, json!({
        "schema": "nf-audit-report/1",
        "ok": errors.is_empty(),
        "records": seq,
        "head": prev,
        "errors": errors
    })))
}

pub fn audit_append_op(req: &Value) -> OpOutcome { audit_append(req) }
pub fn audit_verify_op(req: &Value) -> OpOutcome { audit_verify(req) }
