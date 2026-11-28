//! license-verify：pin 公钥向量、篡改/版本拒绝、本地密钥往返、恒 exit 0。

#[path = "common/mod.rs"]
mod common;

use common::*;
use nf_app_core::license_entitlement::{parse_code, PINNED_PUBLIC_KEY_HEX};
use serde_json::json;

/// VECTEST-0001：production pin 公钥签发（batch=vector-2026-11-28, major=0）。
const VALID: &str = "NF1.eyJiYXRjaCI6InZlY3Rvci0yMDI2LTExLTI4IiwiZWRpdGlvbiI6InBybyIsImlzc3VlZF9hdCI6IjIwMjYtMTEtMjgiLCJtYWpvciI6MCwib3JkZXIiOiJWRUNURVNULTAwMDEiLCJwcm9kdWN0IjoibmYtbW9iaWxlIiwidiI6MX0.FmRD_bf6vwtTyAfDrgC1uUvi4Jsm3fcm116p2OT-XltbZr4sCLfrtLm_VJOPvmzYrWrZcf0Xr7NPMb0LCLV_Bg";
/// VECTEST-0003：同一把密钥，major=9（应被版本校验拒绝）。
const WRONG_MAJOR: &str = "NF1.eyJiYXRjaCI6InZlY3Rvci0yMDI2LTExLTI4IiwiZWRpdGlvbiI6InBybyIsImlzc3VlZF9hdCI6IjIwMjYtMTEtMjgiLCJtYWpvciI6OSwib3JkZXIiOiJWRUNURVNULTAwMDMiLCJwcm9kdWN0IjoibmYtbW9iaWxlIiwidiI6MX0.d9rW-VvStGRGFE3kd46gLNa_xulRzkX050BqB865iYTfwnxMkgqVmR69hwwGgtgUlpQqh1143TWNdbfrcTkACg";

/// 测试用 32 字节种子（hex；仅测试，不用于签发）。
const UNIT_SEED: &str = "1111111111111111111111111111111111111111111111111111111111111111";
const OTHER_SEED: &str = "2222222222222222222222222222222222222222222222222222222222222222";

fn b64u(raw: &[u8]) -> String {
    const T: &[u8; 64] = b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_";
    let mut out = String::new();
    let mut i = 0;
    while i + 3 <= raw.len() {
        let n = (u32::from(raw[i]) << 16) | (u32::from(raw[i + 1]) << 8) | u32::from(raw[i + 2]);
        out.push(T[((n >> 18) & 63) as usize] as char);
        out.push(T[((n >> 12) & 63) as usize] as char);
        out.push(T[((n >> 6) & 63) as usize] as char);
        out.push(T[(n & 63) as usize] as char);
        i += 3;
    }
    let rest = raw.len() - i;
    if rest == 1 {
        let n = u32::from(raw[i]) << 16;
        out.push(T[((n >> 18) & 63) as usize] as char);
        out.push(T[((n >> 12) & 63) as usize] as char);
    } else if rest == 2 {
        let n = (u32::from(raw[i]) << 16) | (u32::from(raw[i + 1]) << 8);
        out.push(T[((n >> 18) & 63) as usize] as char);
        out.push(T[((n >> 12) & 63) as usize] as char);
        out.push(T[((n >> 6) & 63) as usize] as char);
    }
    out
}

fn hex(raw: &str) -> Vec<u8> {
    let mut out = Vec::with_capacity(raw.len() / 2);
    let b = raw.as_bytes();
    let mut i = 0;
    while i + 1 < b.len() {
        let hi = (b[i] as char).to_digit(16).expect("hex");
        let lo = (b[i + 1] as char).to_digit(16).expect("hex");
        out.push(((hi << 4) | lo) as u8);
        i += 2;
    }
    out
}

#[test]
fn pinned_vector_verifies() {
    let r = run_ok("license-verify", &json!({"code": VALID}));
    assert_eq!(r["valid"], true, "向量必须通过：{r}");
    assert_eq!(r["edition"], "pro");
    assert_eq!(r["major"], 0);
    assert_eq!(r["order"], "VECTEST-0001");
    assert_eq!(r["batch"], "vector-2026-11-28");
    assert!(r["reason"].is_null());
}

#[test]
fn wrong_major_is_rejected_with_lic002() {
    let r = run_ok("license-verify", &json!({"code": WRONG_MAJOR}));
    assert_eq!(r["valid"], false);
    assert_eq!(r["code"], "NF-LIC-002");
    assert!(r["reason"].as_str().unwrap_or("").contains("大版本"));
}

#[test]
fn tampered_code_is_rejected_with_lic001() {
    let mut chars: Vec<char> = VALID.chars().collect();
    let last = chars.len() - 1;
    chars[last] = if chars[last] == 'A' { 'B' } else { 'A' };
    let tampered: String = chars.into_iter().collect();
    let r = run_ok("license-verify", &json!({"code": tampered}));
    assert_eq!(r["valid"], false);
    assert_eq!(r["code"], "NF-LIC-001");
}

#[test]
fn malformed_codes_are_rejected() {
    for code in ["", "NF1", "NF1.a.b", "NF2.abc.def", "NF1...", "看起来像码"] {
        let r = run_ok("license-verify", &json!({"code": code}));
        assert_eq!(r["valid"], false, "码 {code:?} 不应通过");
        assert_eq!(r["code"], "NF-LIC-001", "码 {code:?} 应报 NF-LIC-001");
    }
}

#[test]
fn local_key_roundtrip_matches_python_format() {
    // 用本地测试种子签一份码，验证 Rust 侧解析/验签与 issue_license.py 的码格式一致。
    let payload = json!({
        "v": 1,
        "product": "nf-mobile",
        "edition": "studio",
        "major": 0,
        "order": "UNIT-0001",
        "issued_at": "2026-11-28",
        "batch": "unit"
    });
    let raw = nf_app_core::canonical::canonical_bytes(&payload).expect("canonical");
    let sig = nf_app_core::evidence::sign_payload(UNIT_SEED, &raw).expect("sign");
    let pk = sig["public_key"].as_str().expect("pk").to_string();
    let sig_bytes = hex(sig["value"].as_str().expect("sig"));
    let code = format!("NF1.{}.{}", b64u(&raw), b64u(&sig_bytes));
    let claims = parse_code(&code, &pk).expect("本地码应通过");
    assert_eq!(claims.edition, "studio");
    assert_eq!(claims.order, "UNIT-0001");
    // 换一把公钥必须失败（防止 pin 被绕过）
    let other = nf_app_core::evidence::sign_payload(OTHER_SEED, &raw).expect("sign2");
    let other_pk = other["public_key"].as_str().expect("pk2");
    assert!(parse_code(&code, other_pk).is_err());
}

#[test]
fn pinned_key_is_configured() {
    assert_eq!(PINNED_PUBLIC_KEY_HEX.len(), 64, "pin 公钥必须是 32 字节 hex");
    assert!(PINNED_PUBLIC_KEY_HEX.chars().all(|c| c.is_ascii_hexdigit()));
}
