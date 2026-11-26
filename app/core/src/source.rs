//! nf-source/1 + nf-source-chain/1：本地来源条目、摘要与离线哈希链。

use crate::canonical::{digest_value, sha256_hex};
use crate::error::{CoreError, OpOutcome};
use crate::ops::{opt_str, req_value, usage};
use crate::schema::validate;
use serde_json::{json, Value};

fn excerpt(text: &str) -> String {
    text.chars().take(4096).collect()
}

fn source_from(text: &str, req: &Value) -> Result<Value, CoreError> {
    let excerpt = excerpt(text);
    if excerpt.trim().is_empty() {
        return Err(usage("来源正文不能为空"));
    }
    let sha = sha256_hex(excerpt.as_bytes());
    let id = opt_str(req, "id")?.map(ToString::to_string).unwrap_or_else(|| format!("src-{}", &sha[..12]));
    let mut source = json!({
        "schema": "nf-source/1",
        "id": id,
        "title": opt_str(req, "title")?.unwrap_or("未命名来源"),
        "fetched_at": req.get("fetched_at").and_then(|v| v.as_u64()).unwrap_or(0),
        "sha256": sha,
        "status": req.get("status").and_then(|v| v.as_str()).unwrap_or("unverified"),
        "excerpt": excerpt
    });
    if let Some(url) = opt_str(req, "url")? {
        source.as_object_mut().unwrap().insert("url".into(), json!(url));
    }
    if let Some(license) = opt_str(req, "license")? {
        source.as_object_mut().unwrap().insert("license".into(), json!(license));
    }
    let issues = validate("nf-source", &source);
    if !issues.is_empty() {
        return Err(CoreError::new("NF-SRC-001").with_message(crate::schema::first_issue_text(&issues)).with_exit(1));
    }
    Ok(source)
}

pub fn add(req: &Value) -> OpOutcome {
    let text = req.get("text").and_then(|v| v.as_str()).ok_or_else(|| usage("source-add 需要 text"))?;
    Ok((0, source_from(text, req)?))
}

pub fn verify(req: &Value) -> OpOutcome {
    let source = req_value(req, "source")?;
    let issues = validate("nf-source", source);
    if !issues.is_empty() {
        return Err(CoreError::new("NF-SRC-001").with_message(crate::schema::first_issue_text(&issues)).with_exit(1));
    }
    let text = source.get("excerpt").and_then(|v| v.as_str()).unwrap_or("");
    let actual = sha256_hex(text.as_bytes());
    let expected = source.get("sha256").and_then(|v| v.as_str()).unwrap_or("");
    if actual != expected {
        return Err(CoreError::new("NF-SRC-002").with_message("来源摘要与摘录不符").with_exit(1));
    }
    Ok((0, json!({"schema": "nf-source-report/1", "ok": true, "id": source.get("id"), "sha256": actual})))
}

pub fn chain_build(req: &Value) -> OpOutcome {
    let sources = req.get("sources").and_then(|v| v.as_array()).ok_or_else(|| usage("source-chain-build 需要 sources"))?;
    let mut entries = Vec::new();
    let mut prev = String::new();
    for source in sources {
        let issues = validate("nf-source", source);
        if !issues.is_empty() {
            return Err(CoreError::new("NF-SRC-001").with_message(crate::schema::first_issue_text(&issues)).with_exit(1));
        }
        let id = source.get("id").and_then(|v| v.as_str()).unwrap_or("");
        let sha = source.get("sha256").and_then(|v| v.as_str()).unwrap_or("");
        entries.push(json!({"id": id, "sha256": sha, "prev": prev}));
        prev = sha.to_string();
    }
    let head = prev;
    let mut chain = json!({
        "schema": "nf-source-chain/1",
        "entries": entries,
        "head": head
    });
    let digest = digest_value(&chain)?;
    chain.as_object_mut().unwrap().insert("digest".into(), json!(digest));
    let issues = validate("nf-source-chain", &chain);
    if !issues.is_empty() {
        return Err(CoreError::new("NF-SRC-001").with_message(crate::schema::first_issue_text(&issues)).with_exit(1));
    }
    Ok((0, chain))
}

pub fn chain_verify(req: &Value) -> OpOutcome {
    let chain = req_value(req, "chain")?;
    let issues = validate("nf-source-chain", chain);
    if !issues.is_empty() {
        return Err(CoreError::new("NF-SRC-001").with_message(crate::schema::first_issue_text(&issues)).with_exit(1));
    }
    let entries = chain.get("entries").and_then(|v| v.as_array()).cloned().unwrap_or_default();
    let mut prev = String::new();
    for (index, entry) in entries.iter().enumerate() {
        let entry_prev = entry.get("prev").and_then(|v| v.as_str()).unwrap_or("");
        if entry_prev != prev {
            return Ok((1, json!({"schema": "nf-source-chain-report/1", "ok": false, "break_at": index, "message": "prev 与上一环不符"})));
        }
        prev = entry.get("sha256").and_then(|v| v.as_str()).unwrap_or("").to_string();
    }
    let head = chain.get("head").and_then(|v| v.as_str()).unwrap_or("");
    if head != prev {
        return Ok((1, json!({"schema": "nf-source-chain-report/1", "ok": false, "break_at": entries.len(), "message": "head 与最后一环不符"})));
    }
    let mut unsigned = chain.clone();
    unsigned.as_object_mut().unwrap().remove("digest");
    let actual = digest_value(&unsigned)?;
    if actual != chain.get("digest").and_then(|v| v.as_str()).unwrap_or("") {
        return Ok((1, json!({"schema": "nf-source-chain-report/1", "ok": false, "break_at": entries.len(), "message": "链摘要不符"})));
    }
    Ok((0, json!({"schema": "nf-source-chain-report/1", "ok": true, "entries": entries.len(), "head": head})))
}

pub fn add_op(req: &Value) -> OpOutcome { add(req) }
pub fn verify_op(req: &Value) -> OpOutcome { verify(req) }
pub fn chain_build_op(req: &Value) -> OpOutcome { chain_build(req) }
pub fn chain_verify_op(req: &Value) -> OpOutcome { chain_verify(req) }
