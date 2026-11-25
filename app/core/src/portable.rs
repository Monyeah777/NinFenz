//! nf-portable/1：全量可携带清单；不静默覆盖。

use crate::canonical::{canonical_bytes, sha256_hex};
use crate::error::CoreError;
use crate::error::OpOutcome;
use crate::fsutil;
use crate::ops::{opt_str, req_value, usage};
use crate::schema::validate;
use serde_json::{json, Value};
use std::path::Path;

fn is_hash(s: &str) -> bool { s.len() == 64 && s.chars().all(|c| c.is_ascii_hexdigit()) }

fn hex(s: &str) -> Result<Vec<u8>, CoreError> {
    if s.len() % 2 != 0 { return Err(CoreError::new("NF-PORT-001").with_message("data_hex 长度非法").with_exit(1)); }
    let b = s.as_bytes(); let mut out = Vec::with_capacity(s.len() / 2); let mut i = 0;
    while i < b.len() {
        let h = (b[i] as char).to_digit(16).ok_or_else(|| CoreError::new("NF-PORT-001").with_message("data_hex 非法"))?;
        let l = (b[i + 1] as char).to_digit(16).ok_or_else(|| CoreError::new("NF-PORT-001").with_message("data_hex 非法"))?;
        out.push(((h << 4) | l) as u8); i += 2;
    }
    Ok(out)
}

fn manifest(req: &Value) -> Result<Value, CoreError> {
    let created_at = opt_str(req, "created_at")?.filter(|s| !s.is_empty()).ok_or_else(|| usage("portable-export 需要 created_at"))?;
    let projects = req.get("projects").cloned().unwrap_or_else(|| json!([]));
    let packs = req.get("packs").cloned().unwrap_or_else(|| json!([]));
    for f in projects.as_array().into_iter().flatten().chain(packs.as_array().into_iter().flatten()) {
        if !is_hash(f.get("sha256").and_then(|v| v.as_str()).unwrap_or("")) {
            return Err(CoreError::new("NF-PORT-001").with_message("file.sha256 非法").with_exit(1));
        }
    }
    let mut m = json!({
        "schema": "nf-portable/1", "created_at": created_at,
        "projects": projects, "prefs": req.get("prefs").cloned().unwrap_or_else(|| json!({})),
        "packs": packs, "trust": req.get("trust").cloned().unwrap_or(Value::Null),
        "audit": req.get("audit").cloned().unwrap_or(Value::Null),
        "manifest_sha256": "0".repeat(64)
    });
    m.as_object_mut().unwrap().remove("manifest_sha256");
    let h = sha256_hex(&canonical_bytes(&m)?);
    m.as_object_mut().unwrap().insert("manifest_sha256".into(), Value::String(h));
    Ok(m)
}

pub fn portable_export(req: &Value) -> OpOutcome {
    let m = manifest(req)?;
    let issues = validate("nf-portable", &m);
    if !issues.is_empty() { return Err(CoreError::new("NF-PORT-001").with_message(crate::schema::first_issue_text(&issues)).with_exit(1)); }
    let mut zip_sha: Option<String> = None;
    if let Some(out) = opt_str(req, "out_path")?.filter(|s| !s.is_empty()) {
        let entries = req.get("contents").and_then(|v| v.as_array()).cloned().unwrap_or_default();
        if out.ends_with(".zip") || !entries.is_empty() {
            let mut files: Vec<(String, Vec<u8>)> = vec![("portable.json".to_string(), canonical_bytes(&m)?)];
            for e in entries {
                let path = e.get("path").and_then(|v| v.as_str()).unwrap_or("");
                let data = e.get("data_hex").and_then(|v| v.as_str()).unwrap_or("");
                if path.is_empty() || path.contains("..") || path.starts_with('/') {
                    return Err(CoreError::new("NF-PORT-001").with_message("contents.path 非法").with_exit(1));
                }
                files.push((path.to_string(), hex(data)?));
            }
            let bytes = crate::zipsec::zip_bytes(&files)?;
            zip_sha = Some(sha256_hex(&bytes));
            fsutil::write_bytes(Path::new(out), &bytes)?;
        } else {
            fsutil::write_bytes(Path::new(out), &canonical_bytes(&m)?)?;
        }
    }
    Ok((0, json!({"schema": "nf-portable-export/1", "portable": m, "manifest_sha256": m["manifest_sha256"], "zip_sha256": zip_sha})))
}

pub fn portable_import(req: &Value) -> OpOutcome {
    let from_zip;
    let portable = if let Some(zp) = opt_str(req, "zip_path")?.filter(|s| !s.is_empty()) {
        let entries = crate::zipsec::read_zip(Path::new(zp))?;
        let e = entries.iter().find(|e| e.name == "portable.json").ok_or_else(|| CoreError::new("NF-PORT-001").with_message("zip 缺 portable.json").with_exit(1))?;
        from_zip = serde_json::from_slice::<Value>(&e.data).map_err(|_| CoreError::new("NF-PORT-001").with_message("portable.json 非法").with_exit(1))?;
        &from_zip
    } else {
        req_value(req, "portable")?
    };
    let issues = validate("nf-portable", portable);
    if !issues.is_empty() { return Err(CoreError::new("NF-PORT-001").with_message(crate::schema::first_issue_text(&issues)).with_exit(1)); }
    let mut calc = portable.clone();
    let declared = calc.get("manifest_sha256").and_then(|v| v.as_str()).unwrap_or("").to_string();
    calc.as_object_mut().unwrap().remove("manifest_sha256");
    let actual = sha256_hex(&canonical_bytes(&calc)?);
    if declared != actual { return Err(CoreError::new("NF-PORT-001").with_message("manifest_sha256 不符").with_exit(1)); }
    let existing: Vec<String> = req.get("existing_ids").and_then(|v| v.as_array()).map(|a| a.iter().filter_map(|x| x.as_str().map(|s| s.to_string())).collect()).unwrap_or_default();
    let mut conflicts = Vec::new();
    for f in portable.get("projects").and_then(|v| v.as_array()).into_iter().flatten() {
        let p = f.get("path").and_then(|v| v.as_str()).unwrap_or("");
        let id = p.rsplit('/').next().unwrap_or(p).trim_end_matches(".nfproject.json");
        if existing.iter().any(|x| x == id) { conflicts.push(id.to_string()); }
    }
    Ok((0, json!({"schema": "nf-portable-import/1", "ok": true, "projects": portable.get("projects").map(|v| v.as_array().map(|a| a.len()).unwrap_or(0)).unwrap_or(0), "conflicts": conflicts, "requires_choice": !conflicts.is_empty()})))
}

pub fn portable_exit(req: &Value) -> OpOutcome {
    if req.get("confirm").and_then(|v| v.as_bool()) != Some(true) {
        return Err(CoreError::new("NF-PORT-001").with_message("exit 需要 confirm=true").with_exit(1));
    }
    Ok((0, json!({"schema": "nf-portable-exit/1", "ok": true, "delete_after_export": true, "note": "core 不直接删除；由调用方在导出成功后执行"})))
}

pub fn portable_export_op(req: &Value) -> OpOutcome { portable_export(req) }
pub fn portable_exit_op(req: &Value) -> OpOutcome { portable_exit(req) }
pub fn portable_import_op(req: &Value) -> OpOutcome { portable_import(req) }
