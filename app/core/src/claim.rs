//! nf-claim-ledger/1：把“声明”钉到 evidence sha；不把声明本身当事实。

use crate::canonical::{canonical_bytes, sha256_hex};
use crate::error::{CoreError, OpOutcome};
use crate::ops::{opt_str, req_value, usage};
use crate::schema::validate;
use serde_json::{json, Value};
use std::path::Path;

const SCHEMA: &str = "nf-claim-ledger/1";

fn is_hash(s: &str) -> bool {
    s.len() == 64 && s.chars().all(|c| c.is_ascii_hexdigit())
}

fn recalc(ledger: &mut Value) -> Result<String, CoreError> {
    if let Some(o) = ledger.as_object_mut() {
        o.remove("ledger_sha256");
        o.remove("signature");
    }
    let h = sha256_hex(&canonical_bytes(ledger)?);
    ledger.as_object_mut().unwrap().insert("ledger_sha256".into(), Value::String(h.clone()));
    Ok(h)
}

fn fresh(created_at: &str, ledger_id: &str) -> Value {
    json!({"schema": SCHEMA, "ledger_id": ledger_id, "created_at": created_at, "claims": [], "ledger_sha256": "0".repeat(64)})
}

pub fn claim_add(req: &Value) -> OpOutcome {
    let created_at = opt_str(req, "created_at")?.filter(|s| !s.is_empty()).ok_or_else(|| usage("claim-add 需要显式 created_at"))?;
    let claim = req_value(req, "claim")?;
    let mut ledger = match req.get("ledger") {
        Some(v) if v.is_object() => v.clone(),
        _ => fresh(created_at, opt_str(req, "ledger_id")?.unwrap_or("default")),
    };
    let issues = validate("nf-claim-ledger", &ledger);
    if !issues.is_empty() {
        return Err(CoreError::new("NF-CLM-001").with_message(format!("ledger 非法: {}", crate::schema::first_issue_text(&issues))).with_exit(1));
    }
    let id = claim.get("id").and_then(|v| v.as_str()).unwrap_or("");
    let statement = claim.get("statement").and_then(|v| v.as_str()).unwrap_or("");
    let status = claim.get("status").and_then(|v| v.as_str()).unwrap_or("");
    let evidence = claim.get("evidence_sha256").and_then(|v| v.as_str()).unwrap_or("");
    let source = claim.get("source").and_then(|v| v.as_str()).unwrap_or("");
    if id.is_empty() || statement.is_empty() || source.is_empty() || !is_hash(evidence) {
        return Err(CoreError::new("NF-CLM-001").with_message("claim 缺 id/statement/source 或 evidence_sha256 非法").with_exit(1));
    }
    if !matches!(status, "verified" | "unverified" | "rejected") {
        return Err(CoreError::new("NF-CLM-001").with_message("claim.status 非法").with_exit(1));
    }
    let claims = ledger.get_mut("claims").and_then(|v| v.as_array_mut()).unwrap();
    if claims.iter().any(|c| c.get("id").and_then(|v| v.as_str()) == Some(id)) {
        return Err(CoreError::new("NF-CLM-001").with_message("claim.id 重复").with_exit(1));
    }
    claims.push(json!({
        "id": id, "statement": statement, "status": status,
        "evidence_sha256": evidence, "source": source,
        "created_at": claim.get("created_at").and_then(|v| v.as_str()).unwrap_or(created_at)
    }));
    let h = recalc(&mut ledger)?;
    let issues = validate("nf-claim-ledger", &ledger);
    if !issues.is_empty() {
        return Err(CoreError::new("NF-CLM-001").with_message(format!("ledger 自检失败: {}", crate::schema::first_issue_text(&issues))).with_exit(1));
    }
    Ok((0, json!({"schema": SCHEMA, "ledger": ledger, "ledger_sha256": h})))
}

pub fn claim_verify(req: &Value) -> OpOutcome {
    let ledger = req_value(req, "ledger")?;
    let issues = validate("nf-claim-ledger", ledger);
    if !issues.is_empty() {
        return Ok((1, json!({"schema": "nf-claim-report/1", "ok": false, "errors": [crate::schema::first_issue_text(&issues)]})));
    }
    let mut calc = ledger.clone();
    let declared = calc.get("ledger_sha256").and_then(|v| v.as_str()).unwrap_or("").to_string();
    let actual = recalc(&mut calc)?;
    let mut errors = Vec::new();
    if declared != actual {
        errors.push("ledger_sha256 不匹配".to_string());
    }
    let mut checked = 0u64;
    if let Some(dir) = opt_str(req, "evidence_dir")?.filter(|s| !s.is_empty()) {
        for c in ledger.get("claims").and_then(|v| v.as_array()).into_iter().flatten() {
            let sha = c.get("evidence_sha256").and_then(|v| v.as_str()).unwrap_or("");
            let p = Path::new(dir).join(format!("{sha}.json"));
            match std::fs::read(&p) {
                Ok(bytes) => {
                    checked += 1;
                    if sha256_hex(&bytes) != sha {
                        errors.push(format!("evidence sha 不符: {}", p.display()));
                    }
                }
                Err(_) => errors.push(format!("evidence 缺失: {}", p.display())),
            }
        }
    }
    Ok((if errors.is_empty() { 0 } else { 1 }, json!({
        "schema": "nf-claim-report/1",
        "ok": errors.is_empty(),
        "ledger_sha256": actual,
        "claims": ledger.get("claims").and_then(|v| v.as_array()).map(|a| a.len()).unwrap_or(0),
        "evidence_checked": checked,
        "errors": errors
    })))
}

pub fn claim_add_op(req: &Value) -> OpOutcome { claim_add(req) }
pub fn claim_verify_op(req: &Value) -> OpOutcome { claim_verify(req) }
