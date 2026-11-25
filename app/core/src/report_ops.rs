//! nf-report/1：保真与可访问性报告（可复算，不伪造 contrast）。

use crate::canonical::{canonical_bytes, sha256_hex};
use crate::error::{CoreError, OpOutcome};
use crate::ops::req_value;
use crate::schema::validate;
use serde_json::{json, Value};
use std::collections::BTreeSet;

const SCHEMA: &str = "nf-report/1";

fn walk<'a>(v: &'a Value, out: &mut Vec<&'a Value>) {
    out.push(v);
    for c in v.get("children").and_then(|x| x.as_array()).into_iter().flatten() {
        walk(c, out);
    }
}

fn digest(v: &Value) -> Result<String, CoreError> { Ok(sha256_hex(&canonical_bytes(v)?)) }

fn item(code: &str, severity: &str, path: &str, message: &str, fix: &str) -> Value {
    json!({"code": code, "severity": severity, "path": path, "message": message, "fix": fix})
}

pub fn fidelity_report(req: &Value) -> OpOutcome {
    let sdir = req_value(req, "sdir")?;
    let report = crate::sdir::validate_sdir_value(sdir);
    if report.has_error() { return Ok((1, report.to_value())); }
    let mut blocks = Vec::new();
    if let Some(root) = sdir.get("blocks").and_then(|v| v.get(0)) { walk(root, &mut blocks); }
    let mut counts = std::collections::BTreeMap::new();
    let mut unprovenanced = 0u64;
    for b in &blocks {
        let ty = b.get("type").and_then(|v| v.as_str()).unwrap_or("");
        *counts.entry(ty.to_string()).or_insert(0u64) += 1;
        if ty != "document" && (b.get("page").is_none() || b.get("bbox").is_none()) {
            unprovenanced += 1;
        }
    }
    let fid = sdir.get("meta").and_then(|m| m.get("fidelity")).cloned().unwrap_or(Value::Null);
    let losses = fid.get("losses").and_then(|v| v.as_array()).cloned().unwrap_or_default();
    let source_format = fid.get("source_format").and_then(|v| v.as_str()).unwrap_or(sdir.get("meta").and_then(|m| m.get("source_format")).and_then(|v| v.as_str()).unwrap_or(""));
    let mut items = Vec::new();
    for l in &losses {
        items.push(item("NF-FID-001", "error", "$.meta.fidelity.losses", &l.to_string(), "修复导入或显式接受"));
    }
    let is_pdf = source_format == "pdf";
    if is_pdf && unprovenanced > 0 {
        items.push(item("NF-FID-001", "warn", "$.provenance", &format!("{unprovenanced} 块缺 page/bbox"), "补版式溯源"));
    }
    if fid.is_null() {
        items.push(item("NF-FID-001", "warn", "$.meta.fidelity", "缺少保真账本", "用新版导入重跑"));
    }
    let ok = !items.iter().any(|i| i["severity"] == "error");
    let out = json!({
        "schema": SCHEMA, "kind": "fidelity", "subject_sha256": digest(sdir)?,
        "ok": ok,
        "summary": {"source_format": source_format, "features": counts, "losses": losses.len(), "unprovenanced": unprovenanced},
        "items": items
    });
    let issues = validate("nf-report", &out);
    if !issues.is_empty() { return Err(CoreError::new("NF-FID-001").with_message(crate::schema::first_issue_text(&issues)).with_exit(1)); }
    Ok((if ok { 0 } else { 1 }, out))
}

pub fn a11y_report(req: &Value) -> OpOutcome {
    let sdir = req_value(req, "sdir")?;
    let report = crate::sdir::validate_sdir_value(sdir);
    if report.has_error() { return Ok((1, report.to_value())); }
    let mut blocks = Vec::new();
    if let Some(root) = sdir.get("blocks").and_then(|v| v.get(0)) { walk(root, &mut blocks); }
    let mut items = Vec::new();
    let lang = sdir.get("meta").and_then(|m| m.get("lang")).and_then(|v| v.as_str()).unwrap_or("und");
    if lang == "und" || lang.is_empty() {
        items.push(item("NF-A11Y-001", "error", "$.meta.lang", "文档未声明语言", "设置 lang"));
    }
    let mut last_level = 0u64;
    for b in &blocks {
        let ty = b.get("type").and_then(|v| v.as_str()).unwrap_or("");
        let id = b.get("id").and_then(|v| v.as_str()).unwrap_or("");
        if ty == "heading" {
            let level = b.get("attrs").and_then(|a| a.get("level")).and_then(|v| v.as_u64()).unwrap_or(1);
            if last_level > 0 && level > last_level + 1 {
                items.push(item("NF-A11Y-001", "error", &format!("$.blocks[{id}]"), &format!("标题跳级 {last_level}->{level}"), "改为连续层级"));
            }
            last_level = level;
        }
        if ty == "table" {
            let header = b.get("attrs").and_then(|a| a.get("header")).and_then(|v| v.as_bool()).unwrap_or(false);
            if !header { items.push(item("NF-A11Y-001", "error", &format!("$.blocks[{id}]"), "表缺表头", "设置 header=true")); }
        }
        if ty == "figure" && b.get("text").and_then(|v| v.as_str()).unwrap_or("").trim().is_empty() {
            items.push(item("NF-A11Y-001", "error", &format!("$.blocks[{id}]"), "图缺 alt", "补 alt"));
        }
    }
    let mut orders = BTreeSet::new();
    let mut missing = 0u64;
    for a in sdir.get("accessibility").and_then(|v| v.as_array()).into_iter().flatten() {
        if let Some(o) = a.get("reading_order").and_then(|v| v.as_u64()) {
            if !orders.insert(o) { items.push(item("NF-A11Y-001", "error", "$.accessibility.reading_order", "reading_order 重复", "重排")); }
        }
        if let Some(m) = a.get("missing").and_then(|v| v.as_array()) { missing += m.len() as u64; }
    }
    if missing > 0 { items.push(item("NF-A11Y-001", "warn", "$.accessibility.missing", &format!("{missing} 个显式缺失"), "补齐或确认")); }
    let blockers = items.iter().filter(|i| i["severity"] == "error").count();
    let ok = blockers == 0;
    let out = json!({
        "schema": SCHEMA, "kind": "a11y", "subject_sha256": digest(sdir)?,
        "ok": ok,
        "summary": {"blockers": blockers, "items": items.len(), "contrast": "not_checked"},
        "items": items
    });
    let issues = validate("nf-report", &out);
    if !issues.is_empty() { return Err(CoreError::new("NF-A11Y-001").with_message(crate::schema::first_issue_text(&issues)).with_exit(1)); }
    Ok((if ok { 0 } else { 1 }, out))
}

pub fn fidelity_report_op(req: &Value) -> OpOutcome { fidelity_report(req) }
pub fn a11y_report_op(req: &Value) -> OpOutcome { a11y_report(req) }
