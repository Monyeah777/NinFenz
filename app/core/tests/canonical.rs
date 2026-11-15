//! canonical 与 Python json.dumps(ensure_ascii=False, sort_keys=True,
//! separators=(",",":"), allow_nan=False) 的逐字节对拍（期望值由 Python 3.11 生成后手写固化）。

#[path = "common/mod.rs"]
mod common;

use nf_app_core::canonical::{
    canonical_string, check_depth, digest_value, find_float_path, sha256_hex,
};
use nf_app_core::cli;
use serde_json::json;

#[test]
fn python_vector_basic() {
    let v = json!({"b": 1, "a": [true, null, "x"], "c": "é"});
    assert_eq!(
        canonical_string(&v).unwrap(),
        r#"{"a":[true,null,"x"],"b":1,"c":"é"}"#
    );
    assert_eq!(
        digest_value(&v).unwrap(),
        "f7b86c353ee8123c220c2c1c029f145c91f46fe517da4168518eceeff5fe2094"
    );
}

#[test]
fn python_vector_control_chars() {
    let s = "\u{00}\u{01}\u{08}\u{09}\u{0a}\u{0b}\u{0c}\u{0d}\u{1f}\\";
    let v = json!({ "s": s });
    assert_eq!(
        canonical_string(&v).unwrap(),
        r#"{"s":"\u0000\u0001\b\t\n\u000b\f\r\u001f\\"}"#
    );
    assert_eq!(
        digest_value(&v).unwrap(),
        "8bfa3643ad97b2744019c0b303a4066292752f8e50a83b1131187f2e3ab93e72"
    );
    assert_eq!(
        sha256_hex(canonical_string(&v).unwrap().as_bytes()),
        digest_value(&v).unwrap()
    );
}

#[test]
fn python_vector_control_quote() {
    let mut s = String::new();
    for c in [0u32, 1, 8, 9, 10, 11, 12, 13, 31] {
        s.push(char::from_u32(c).unwrap());
    }
    s.push('\\');
    s.push('"');
    let v = json!({ "s": s });
    assert_eq!(
        canonical_string(&v).unwrap(),
        r#"{"s":"\u0000\u0001\b\t\n\u000b\f\r\u001f\\\""}"#
    );
    assert_eq!(
        digest_value(&v).unwrap(),
        "b9926cf7d279c0ee9bb7be048a02ff50689b515d4f9aa7df9871339a347a48fe"
    );
}

#[test]
fn python_vector_u2028_emoji_space() {
    let v = json!({"z": "\u{2028}\u{2029}", "emoji": "😀", "space": "a b"});
    assert_eq!(
        canonical_string(&v).unwrap(),
        "{\"emoji\":\"😀\",\"space\":\"a b\",\"z\":\"\u{2028}\u{2029}\"}"
    );
    assert_eq!(
        digest_value(&v).unwrap(),
        "ba126ef38b41eb0ceb2162acd0bd3b71e46408c4bd2c1e2bc135f2d01bd72501"
    );
    let canon = canonical_string(&v).unwrap();
    assert!(!canon.contains("\\u2028"));
    assert!(!canon.contains("\\u2029"));
}

#[test]
fn python_vector_i64_u64_extremes() {
    let v = json!({"n": -9223372036854775808i64, "u": 18446744073709551615u64});
    assert_eq!(
        canonical_string(&v).unwrap(),
        r#"{"n":-9223372036854775808,"u":18446744073709551615}"#
    );
    assert_eq!(
        digest_value(&v).unwrap(),
        "cfd15503cc12655bb41cabd3fc1ad099e70e774cdbe6a70e2b39e4f8d54c96e1"
    );
}

#[test]
fn python_vector_nested_sort() {
    let v = json!({"k2": {"b": 2, "a": 1}, "k1": [{"y": 2, "x": 1}]});
    assert_eq!(
        canonical_string(&v).unwrap(),
        r#"{"k1":[{"x":1,"y":2}],"k2":{"a":1,"b":2}}"#
    );
    assert_eq!(
        digest_value(&v).unwrap(),
        "88d9349e619bbcff553f97ad00666cbff2831b52bc6e48ebf2ce9214cfe396cd"
    );
}

#[test]
fn python_vector_unicode_key_order() {
    let v = json!({"z": 1, "é": 2, "中": 3});
    assert_eq!(canonical_string(&v).unwrap(), r#"{"z":1,"é":2,"中":3}"#);
    assert_eq!(
        digest_value(&v).unwrap(),
        "7202ec34a8449cfdf3369d1604c5674ee8b3fb5b93957fbb087c51853355c0f5"
    );
}

#[test]
fn python_vector_float_rejected() {
    let v = json!({"a": 0.5});
    let err = canonical_string(&v).unwrap_err();
    assert_eq!(err.code, "NF-E-006");
    assert_eq!(find_float_path(&v, "$"), Some("$.a".to_string()));
}

#[test]
fn empty_containers_and_bools() {
    assert_eq!(canonical_string(&json!({})).unwrap(), "{}");
    assert_eq!(canonical_string(&json!([])).unwrap(), "[]");
    assert_eq!(canonical_string(&json!([true, false, null])).unwrap(), "[true,false,null]");
}

#[test]
fn del_and_u2028_not_escaped() {
    let v = json!({"d": "\u{7f}", "u": "\u{2028}"});
    let s = canonical_string(&v).unwrap();
    assert_eq!(s, "{\"d\":\"\u{7f}\",\"u\":\"\u{2028}\"}");
    assert!(!s.contains("\\u007f"));
    assert!(!s.contains("\\u2028"));
}

#[test]
fn canonical_deterministic() {
    let v = json!({"b": [1, 2, {"d": "x", "c": "y"}], "a": "中"});
    let one = canonical_string(&v).unwrap();
    let two = canonical_string(&v).unwrap();
    assert_eq!(one, two);
    assert_eq!(sha256_hex(one.as_bytes()), sha256_hex(two.as_bytes()));
}

#[test]
fn json_depth_limit() {
    let mut inner = serde_json::Value::Null;
    for _ in 0..70 {
        inner = json!([inner]);
    }
    let err = check_depth(&inner, "$", 1).unwrap_err();
    assert_eq!(err.code, "NF-SEC-003");
    assert_eq!(err.exit, 3);
}

#[test]
fn canonical_op_rejects_float_with_exit1_report() {
    let env = cli::run("canonical", br#"{"value":{"a":0.5}}"#);
    assert_eq!(env.exit, 1);
    assert!(!env.ok);
    assert_eq!(env.error.as_ref().unwrap()["code"], "NF-E-006");
    assert_eq!(
        env.result.as_ref().unwrap()["schema"].as_str(),
        Some("nf-validate-report/1")
    );
}

#[test]
fn canonical_op_ok_and_digest() {
    let env = cli::run("canonical", br#"{"value":{"a":1}}"#);
    assert_eq!(env.exit, 0);
    let r = env.result.unwrap();
    assert_eq!(r["canonical"].as_str(), Some(r#"{"a":1}"#));
    assert_eq!(
        r["digest"].as_str(),
        Some("015abd7f5cc57a2dd94b7590f04ad8084273905ee33ec5cebeae62276a97f862")
    );
}

#[test]
fn bom_input_rejected() {
    let mut bytes = vec![0xEF, 0xBB, 0xBF];
    bytes.extend_from_slice(br#"{"value":1}"#);
    let env = cli::run("canonical", &bytes);
    assert_eq!(env.exit, 2);
    assert_eq!(env.error.as_ref().unwrap()["code"], "NF-E-003");
}

#[test]
fn request_must_be_object() {
    let env = cli::run("canonical", b"[1,2]");
    assert_eq!(env.exit, 2);
    assert_eq!(env.error.as_ref().unwrap()["code"], "NF-E-003");
}
