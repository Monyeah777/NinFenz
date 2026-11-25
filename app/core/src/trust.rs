//! nf-trust-root/1：信任根 pin、轮换、吊销；Ed25519 签名验证。

use crate::canonical::sha256_hex;
use crate::error::{CoreError, OpOutcome};
use crate::ops::{opt_str, req_value, usage};
use crate::schema::validate;
use serde_json::{json, Value};

const SCHEMA: &str = "nf-trust-root/1";

fn is_hash(s: &str) -> bool { s.len() == 64 && s.chars().all(|c| c.is_ascii_hexdigit()) }

fn empty() -> Value { json!({"schema": SCHEMA, "roots": [], "revoked": []}) }

fn root_fingerprint(pk: &str) -> Result<String, CoreError> {
    if !is_hash(pk) { return Err(CoreError::new("NF-TRUST-001").with_message("public_key 非法").with_exit(1)); }
    let mut raw = Vec::with_capacity(32);
    let b = pk.as_bytes();
    let mut i = 0;
    while i < b.len() {
        let h = (b[i] as char).to_digit(16).ok_or_else(|| CoreError::new("NF-TRUST-001").with_message("public_key 非法"))?;
        let l = (b[i + 1] as char).to_digit(16).ok_or_else(|| CoreError::new("NF-TRUST-001").with_message("public_key 非法"))?;
        raw.push(((h << 4) | l) as u8);
        i += 2;
    }
    Ok(sha256_hex(&raw))
}

pub fn trust_root_add(req: &Value) -> OpOutcome {
    let mut trust = match req.get("trust") {
        Some(v) if v.is_object() => v.clone(),
        _ => empty(),
    };
    let root = req_value(req, "root")?;
    let id = root.get("id").and_then(|v| v.as_str()).unwrap_or("");
    let pk = root.get("public_key").and_then(|v| v.as_str()).unwrap_or("");
    let fp = root.get("fingerprint").and_then(|v| v.as_str()).unwrap_or("");
    if id.is_empty() || !is_hash(pk) || !is_hash(fp) {
        return Err(CoreError::new("NF-TRUST-001").with_message("root 缺 id 或 hash").with_exit(1));
    }
    if root_fingerprint(pk)? != fp {
        return Err(CoreError::new("NF-TRUST-001").with_message("fingerprint 与 public_key 不符").with_exit(1));
    }
    let roots = trust.get_mut("roots").and_then(|v| v.as_array_mut()).unwrap();
    if roots.iter().any(|r| r.get("id").and_then(|v| v.as_str()) == Some(id)) {
        return Err(CoreError::new("NF-TRUST-001").with_message("root.id 重复").with_exit(1));
    }
    roots.push(root.clone());
    let issues = validate("nf-trust-root", &trust);
    if !issues.is_empty() {
        return Err(CoreError::new("NF-TRUST-001").with_message(crate::schema::first_issue_text(&issues)).with_exit(1));
    }
    Ok((0, json!({"schema": SCHEMA, "trust": trust})))
}

pub fn trust_root_rotate(req: &Value) -> OpOutcome {
    let mut trust = req_value(req, "trust")?.clone();
    let old = opt_str(req, "old_id")?.filter(|s| !s.is_empty()).ok_or_else(|| usage("rotate 需要 old_id"))?;
    let new_root = req_value(req, "root")?.clone();
    let roots = trust.get_mut("roots").and_then(|v| v.as_array_mut()).ok_or_else(|| usage("trust 缺 roots"))?;
    let mut found = false;
    for r in roots.iter_mut() {
        if r.get("id").and_then(|v| v.as_str()) == Some(old) {
            r.as_object_mut().unwrap().insert("status".into(), Value::String("retired".into()));
            found = true;
        }
    }
    if !found { return Err(CoreError::new("NF-TRUST-001").with_message("old root 不存在").with_exit(1)); }
    roots.push(new_root);
    Ok((0, json!({"schema": SCHEMA, "trust": trust})))
}

pub fn trust_root_verify(req: &Value) -> OpOutcome {
    let trust = req_value(req, "trust")?;
    let issues = validate("nf-trust-root", trust);
    if !issues.is_empty() {
        return Ok((1, json!({"schema": "nf-trust-report/1", "ok": false, "errors": [crate::schema::first_issue_text(&issues)]})));
    }
    let fp = opt_str(req, "fingerprint")?.unwrap_or("");
    let revoked = trust.get("revoked").and_then(|v| v.as_array()).map(|a| a.iter().filter_map(|x| x.as_str()).any(|x| x == fp)).unwrap_or(false);
    let root = trust.get("roots").and_then(|v| v.as_array()).and_then(|a| a.iter().find(|r| r.get("fingerprint").and_then(|v| v.as_str()) == Some(fp)));
    let mut errors = Vec::new();
    if revoked { errors.push("fingerprint 已吊销".to_string()); }
    match root {
        None => errors.push("fingerprint 不在 trust root".to_string()),
        Some(r) => {
            let status = r.get("status").and_then(|v| v.as_str()).unwrap_or("");
            if status != "active" { errors.push(format!("root status={status}")); }
            if let (Some(payload), Some(sig)) = (req.get("payload"), req.get("signature")) {
                if crate::evidence::verify_payload(sig, payload.to_string().as_bytes()).is_err() {
                    errors.push("签名验证失败".to_string());
                }
            }
        }
    }
    Ok((if errors.is_empty() { 0 } else { 1 }, json!({
        "schema": "nf-trust-report/1", "ok": errors.is_empty(), "fingerprint": fp, "errors": errors
    })))
}

pub fn trust_root_revoke(req: &Value) -> OpOutcome {
    let mut trust = req_value(req, "trust")?.clone();
    let fp = opt_str(req, "fingerprint")?.filter(|s| is_hash(s)).ok_or_else(|| usage("revoke 需要 fingerprint"))?;
    let revoked = trust.get_mut("revoked").and_then(|v| v.as_array_mut()).unwrap();
    if !revoked.iter().any(|x| x.as_str() == Some(fp)) { revoked.push(Value::String(fp.to_string())); }
    for r in trust.get_mut("roots").and_then(|v| v.as_array_mut()).into_iter().flatten() {
        if r.get("fingerprint").and_then(|v| v.as_str()) == Some(fp) {
            r.as_object_mut().unwrap().insert("status".into(), Value::String("revoked".into()));
        }
    }
    Ok((0, json!({"schema": SCHEMA, "trust": trust})))
}

pub fn trust_root_add_op(req: &Value) -> OpOutcome { trust_root_add(req) }
pub fn trust_root_rotate_op(req: &Value) -> OpOutcome { trust_root_rotate(req) }
pub fn trust_root_verify_op(req: &Value) -> OpOutcome { trust_root_verify(req) }
pub fn trust_root_revoke_op(req: &Value) -> OpOutcome { trust_root_revoke(req) }
