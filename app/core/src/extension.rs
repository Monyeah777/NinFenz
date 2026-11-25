//! nf-extension/1：声明式扩展清单；不执行代码。

use crate::canonical::canonical_bytes;
use crate::error::{CoreError, OpOutcome};
use crate::ops::{opt_str, req_value, usage};
use crate::schema::validate;
use serde_json::{json, Value};
use std::path::Path;

fn check(manifest: &Value, strict: bool) -> Result<Value, CoreError> {
    let issues = validate("nf-extension", manifest);
    if !issues.is_empty() {
        return Err(CoreError::new("NF-EXT-003").with_message(crate::schema::first_issue_text(&issues)).with_exit(1));
    }
    for bad in ["exec", "script", "entry", "code", "network", "secret"] {
        if manifest.get(bad).is_some() {
            return Err(CoreError::new("NF-EXT-003").with_message(format!("禁止字段 {bad}")).with_exit(1));
        }
    }
    if let Some(caps) = manifest.get("capabilities").and_then(|v| v.as_array()) {
        for c in caps.iter().filter_map(|v| v.as_str()) {
            if matches!(c, "exec" | "network" | "secret" | "filesystem") {
                return Err(CoreError::new("NF-EXT-003").with_message(format!("禁止 capability {c}")).with_exit(1));
            }
        }
    }
    let sig = manifest.get("signature");
    if sig.is_none() && strict {
        return Err(CoreError::new("NF-EXT-003").with_message("strict 模式拒绝未签名扩展").with_exit(1));
    }
    if let Some(sig) = sig {
        let mut unsigned = manifest.clone();
        unsigned.as_object_mut().unwrap().remove("signature");
        crate::evidence::verify_payload(sig, &canonical_bytes(&unsigned)?)
            .map_err(|_| CoreError::new("NF-EXT-003").with_message("扩展签名不符").with_exit(1))?;
    }
    Ok(json!({"id": manifest.get("id"), "type": manifest.get("type"), "capabilities": manifest.get("capabilities"), "signed": sig.is_some()}))
}

pub fn extension_list(req: &Value) -> OpOutcome {
    let dir = opt_str(req, "dir")?.ok_or_else(|| usage("extension-list 需要 dir"))?;
    let strict = req.get("strict").and_then(|v| v.as_bool()).unwrap_or(true);
    let root = Path::new(dir);
    if !root.is_dir() {
        return Ok((0, json!({"schema": "nf-extension-list/1", "extensions": [], "dir": dir})));
    }
    let mut out = Vec::new();
    let mut entries: Vec<_> = std::fs::read_dir(root).map_err(|e| CoreError::new("NF-EXT-003").with_message(e.to_string()).with_exit(1))?.filter_map(|e| e.ok()).collect();
    entries.sort_by_key(|e| e.file_name());
    for e in entries {
        let p = e.path().join("nf-extension.json");
        if !p.is_file() { continue; }
        let bytes = std::fs::read(&p).map_err(|e| CoreError::new("NF-EXT-003").with_message(e.to_string()).with_exit(1))?;
        let v: Value = serde_json::from_slice(&bytes).map_err(|e| CoreError::new("NF-EXT-003").with_message(e.to_string()).with_exit(1))?;
        match check(&v, strict) {
            Ok(info) => out.push(json!({"path": p.display().to_string(), "info": info})),
            Err(e) => out.push(json!({"path": p.display().to_string(), "error": e.code, "message": e.message})),
        }
    }
    Ok((0, json!({"schema": "nf-extension-list/1", "dir": dir, "extensions": out})))
}

pub fn extension_verify(req: &Value) -> OpOutcome {
    let manifest = req_value(req, "manifest")?;
    let strict = req.get("strict").and_then(|v| v.as_bool()).unwrap_or(true);
    match check(manifest, strict) {
        Ok(info) => Ok((0, json!({"schema": "nf-extension-report/1", "ok": true, "info": info}))),
        Err(e) => Ok((1, json!({"schema": "nf-extension-report/1", "ok": false, "error": e.code, "message": e.message}))),
    }
}

pub fn extension_apply(req: &Value) -> OpOutcome {
    let manifest = req_value(req, "manifest")?;
    let strict = req.get("strict").and_then(|v| v.as_bool()).unwrap_or(true);
    let info = check(manifest, strict)?;
    let config = manifest.get("config").cloned().unwrap_or_else(|| json!({}));
    Ok((0, json!({"schema": "nf-extension-apply/1", "ok": true, "info": info, "config": config})))
}

pub fn extension_list_op(req: &Value) -> OpOutcome { extension_list(req) }
pub fn extension_verify_op(req: &Value) -> OpOutcome { extension_verify(req) }
pub fn extension_apply_op(req: &Value) -> OpOutcome { extension_apply(req) }
