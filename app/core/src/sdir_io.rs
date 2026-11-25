//! SDIR 开放交换：canonical nf-sdir JSON 导出/载入。

use crate::canonical::{canonical_bytes, sha256_hex};
use crate::error::OpOutcome;
use crate::ops::req_value;
use crate::sdir::validate_sdir_value;
use serde_json::{json, Value};

pub fn sdir_export(req: &Value) -> OpOutcome {
    let sdir = req_value(req, "sdir")?;
    let report = validate_sdir_value(sdir);
    if report.has_error() { return Ok((1, report.to_value())); }
    let bytes = canonical_bytes(sdir)?;
    Ok((0, json!({"schema": "nf-sdir-export/1", "sha256": sha256_hex(&bytes), "json": sdir})))
}

pub fn sdir_load(req: &Value) -> OpOutcome {
    let sdir = req_value(req, "sdir")?;
    let report = validate_sdir_value(sdir);
    if report.has_error() { return Ok((1, report.to_value())); }
    Ok((0, json!({"schema": "nf-sdir/1", "sdir": sdir})))
}

pub fn sdir_export_op(req: &Value) -> OpOutcome { sdir_export(req) }
pub fn sdir_load_op(req: &Value) -> OpOutcome { sdir_load(req) }
