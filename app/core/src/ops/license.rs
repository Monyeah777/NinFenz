//! Op license-verify：校验 Pro 离线授权码（不联网、不写盘）。
//!
//! 语义：查询而非校验产物——**总是 exit 0**，valid=false 时 result 带 reason/code，
//! 避免把「没有授权」当成协议错误（CLI.md §2 的 exit 1 语义留给产物校验）。

use crate::error::{CoreError, OpOutcome};
use crate::license_entitlement::{self, CURRENT_MAJOR};
use crate::ops::{req_str, usage};
use serde_json::{json, Value};

fn opt_u64(req: &Value, key: &str) -> Result<Option<u64>, CoreError> {
    match req.get(key) {
        None | Some(Value::Null) => Ok(None),
        Some(Value::Number(n)) => n
            .as_u64()
            .map(Some)
            .ok_or_else(|| usage(format!("请求字段 {key} 必须是非负整数"))),
        Some(_) => Err(usage(format!("请求字段 {key} 必须是非负整数"))),
    }
}

pub fn license_verify(req: &Value) -> OpOutcome {
    let code = req_str(req, "code")?;
    let expected_major = opt_u64(req, "app_major")?.unwrap_or(CURRENT_MAJOR);
    match license_entitlement::verify_pinned(code, expected_major) {
        Ok(claims) => Ok((
            0,
            json!({
                "schema": "nf-license-verify/1",
                "valid": true,
                "edition": claims.edition,
                "major": claims.major,
                "order": claims.order,
                "issued_at": claims.issued_at,
                "batch": claims.batch,
                "current_major": expected_major,
                "reason": Value::Null,
                "code": Value::Null
            }),
        )),
        Err(err) => Ok((
            0,
            json!({
                "schema": "nf-license-verify/1",
                "valid": false,
                "edition": Value::Null,
                "major": Value::Null,
                "order": Value::Null,
                "issued_at": Value::Null,
                "batch": Value::Null,
                "current_major": expected_major,
                "reason": err.message,
                "code": err.code
            }),
        )),
    }
}
