//! C ABI：abi_version / call / free（JSON over C ABI）。

use nf_app_core::ffi::{nf_app_core_abi_version, nf_app_core_call, nf_app_core_free};
use serde_json::Value;
use std::ffi::{CStr, CString};

unsafe fn call(req: &str) -> Value {
    let c = CString::new(req).unwrap();
    let out = nf_app_core_call(c.as_ptr());
    assert!(!out.is_null(), "正常错误也必须返回信封（非 NULL）");
    let text = CStr::from_ptr(out).to_str().unwrap().to_string();
    nf_app_core_free(out);
    let value: Value = serde_json::from_str(&text).unwrap();
    assert!(value.get("op").is_some(), "FFI 响应必须带 op 字段");
    value
}

#[test]
fn abi_version_is_static_string() {
    unsafe {
        let p = nf_app_core_abi_version();
        assert!(!p.is_null());
        assert_eq!(CStr::from_ptr(p).to_str().unwrap(), "nf-app-core/1");
    }
}

#[test]
fn ffi_canonical_ok() {
    unsafe {
        let v = call(r#"{"op":"canonical","in":{"value":{"b":1,"a":2}}}"#);
        assert_eq!(v["op"], "canonical");
        assert_eq!(v["ok"], true);
        assert_eq!(v["exit"], 0);
        assert_eq!(v["result"]["canonical"], "{\"a\":2,\"b\":1}");
        assert_eq!(v["result"]["digest"].as_str().unwrap().len(), 64);
    }
}

#[test]
fn ffi_error_envelope_for_unknown_op() {
    unsafe {
        let v = call(r#"{"op":"nope","in":{}}"#);
        assert_eq!(v["ok"], false);
        assert_eq!(v["exit"], 2);
        assert_eq!(v["error"]["code"], "NF-E-003");
    }
}

#[test]
fn ffi_float_rejected_as_report() {
    unsafe {
        let v = call(r#"{"op":"canonical","in":{"value":{"a":0.5}}}"#);
        assert_eq!(v["exit"], 1);
        assert_eq!(v["result"]["schema"], "nf-validate-report/1");
        assert_eq!(v["error"]["code"], "NF-E-006");
    }
}

#[test]
fn ffi_bad_json_returns_envelope() {
    unsafe {
        let v = call("{not json");
        assert_eq!(v["ok"], false);
        assert_eq!(v["exit"], 2);
    }
}

#[test]
fn ffi_null_and_free_are_safe() {
    unsafe {
        let v = call(r#"{"op":"canonical","in":{"value":1}}"#);
        assert_eq!(v["ok"], true);
        nf_app_core_free(std::ptr::null_mut());
    }
}
