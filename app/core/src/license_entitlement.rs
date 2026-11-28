//! nf-license/1：Pro 离线授权码（签名码）解析与验签。
//!
//! 码格式：NF1.<base64url(payload)>.<base64url(ed25519_sig)>
//! payload（canonical JSON）：{"v":1,"product":"nf-mobile","edition":"pro",
//!   "major":0,"order":"...","issued_at":"YYYY-MM-DD","batch":"..."}
//!
//! 约束（离线红线）：不联网、无账号、无服务端；公钥 pin 在本模块，
//! 私钥只在作者本机（scripts/issue_license.py），绝不入库。
//! 设备绑定是 App 侧本地行为（首激活指纹 + 重绑计数），本模块不做跨设备黑名单。

use crate::canonical::parse_json_bytes;
use crate::error::CoreError;
use ed25519_compact::{PublicKey, Signature};
use serde_json::Value;

/// 生产公钥（由 scripts/issue_license.py --gen-key 生成；私钥离线保存）。
pub const PINNED_PUBLIC_KEY_HEX: &str =
    "436c89c2c36a1aa471ecd9bfdb4147bed064af1b555a281f7eccff166f24c3c7";

/// 当前大版本（买断按大版本；跨大版本需重新签发）。
pub const CURRENT_MAJOR: u64 = 0;

pub const CODE_PREFIX: &str = "NF1";
pub const PRODUCT: &str = "nf-mobile";
pub const EDITIONS: [&str; 3] = ["pro", "studio", "ccos"];

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct LicenseClaims {
    pub edition: String,
    pub major: u64,
    pub order: String,
    pub issued_at: String,
    pub batch: String,
}

fn bad(msg: impl Into<String>) -> CoreError {
    CoreError::new("NF-LIC-001").with_message(msg).with_exit(1)
}

fn mismatch(msg: impl Into<String>) -> CoreError {
    CoreError::new("NF-LIC-002").with_message(msg).with_exit(1)
}

/// 解码 base64url（无 padding，接受 -/_ 变体）。
pub fn b64url_decode(text: &str) -> Result<Vec<u8>, CoreError> {
    let mut out: Vec<u8> = Vec::with_capacity(text.len() * 3 / 4 + 3);
    let mut buf: u32 = 0;
    let mut bits: u32 = 0;
    for ch in text.bytes() {
        let val: u32 = match ch {
            b'A'..=b'Z' => u32::from(ch - b'A'),
            b'a'..=b'z' => u32::from(ch - b'a') + 26,
            b'0'..=b'9' => u32::from(ch - b'0') + 52,
            b'-' => 62,
            b'_' => 63,
            b'=' => continue,
            _ => return Err(bad("授权码含非法 base64url 字符")),
        };
        buf = ((buf << 6) | val) & 0x00FF_FFFF;
        bits += 6;
        if bits >= 8 {
            bits -= 8;
            out.push(((buf >> bits) & 0xFF) as u8);
        }
    }
    if bits >= 6 {
        return Err(bad("授权码 base64url 尾部不完整"));
    }
    Ok(out)
}

fn hex32(text: &str) -> Result<[u8; 32], CoreError> {
    if text.len() != 64 || !text.chars().all(|c| c.is_ascii_hexdigit()) {
        return Err(bad("公钥不是 32 字节 hex"));
    }
    let mut raw = [0u8; 32];
    for (i, slot) in raw.iter_mut().enumerate() {
        let byte = u8::from_str_radix(&text[i * 2..i * 2 + 2], 16)
            .map_err(|_| bad("公钥 hex 解析失败"))?;
        *slot = byte;
    }
    Ok(raw)
}

fn field<'a>(payload: &'a Value, key: &str) -> Result<&'a str, CoreError> {
    payload
        .get(key)
        .and_then(Value::as_str)
        .ok_or_else(|| bad(format!("授权码载荷缺字符串字段 {key}")))
}

/// 解析 + 验签 + 载荷校验（不检查大版本）。
pub fn parse_code(code: &str, public_key_hex: &str) -> Result<LicenseClaims, CoreError> {
    let code = code.trim();
    if code.is_empty() || code.len() > 2048 {
        return Err(bad("授权码为空或过长"));
    }
    let parts: Vec<&str> = code.split('.').collect();
    if parts.len() != 3 || parts[0] != CODE_PREFIX {
        return Err(bad("授权码格式非法（应为 NF1.<payload>.<sig>）"));
    }
    let payload_raw = b64url_decode(parts[1])?;
    let sig_raw = b64url_decode(parts[2])?;
    if sig_raw.len() != 64 {
        return Err(bad("授权码签名长度非法"));
    }
    let pk = hex32(public_key_hex)?;
    let public = PublicKey::from_slice(&pk).map_err(|_| bad("pin 的公钥非法"))?;
    let signature = Signature::from_slice(&sig_raw).map_err(|_| bad("授权码签名非法"))?;
    public
        .verify(&payload_raw, &signature)
        .map_err(|_| bad("授权码验签失败（码被改动或不属于本产品）"))?;
    let payload = parse_json_bytes(&payload_raw)?;
    validate_payload(&payload)
}

fn validate_payload(payload: &Value) -> Result<LicenseClaims, CoreError> {
    let version = payload.get("v").and_then(Value::as_u64).unwrap_or(0);
    if version != 1 {
        return Err(bad("授权码载荷版本不是 1"));
    }
    if field(payload, "product")? != PRODUCT {
        return Err(bad("授权码产品不是 nf-mobile"));
    }
    let edition = field(payload, "edition")?.to_string();
    if !EDITIONS.contains(&edition.as_str()) {
        return Err(bad(format!("授权码 edition 非法：{edition}")));
    }
    let major = payload
        .get("major")
        .and_then(Value::as_u64)
        .ok_or_else(|| bad("授权码载荷缺整数 major"))?;
    let order = field(payload, "order")?;
    if order.is_empty() || order.len() > 64 {
        return Err(bad("授权码 order 长度非法（1..=64）"));
    }
    let issued_at = field(payload, "issued_at")?;
    if issued_at.len() > 32 {
        return Err(bad("授权码 issued_at 过长"));
    }
    let batch = payload.get("batch").and_then(Value::as_str).unwrap_or("");
    if batch.len() > 64 {
        return Err(bad("授权码 batch 过长"));
    }
    Ok(LicenseClaims {
        edition,
        major,
        order: order.to_string(),
        issued_at: issued_at.to_string(),
        batch: batch.to_string(),
    })
}

/// 生产验签：pin 公钥 + 大版本匹配。
pub fn verify_pinned(code: &str, expected_major: u64) -> Result<LicenseClaims, CoreError> {
    let claims = parse_code(code, PINNED_PUBLIC_KEY_HEX)?;
    if claims.major != expected_major {
        return Err(mismatch(format!(
            "授权码大版本 {} 与当前大版本 {} 不符（大版本升级请换新码）",
            claims.major, expected_major
        )));
    }
    Ok(claims)
}
