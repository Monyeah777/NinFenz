//! C ABI（CLI.md §5）：JSON over C ABI；panic → NULL + stderr；可重入（无共享可变全局）。

use crate::canonical::canonical_bytes;
use crate::cli;
use crate::error::{CoreError, Envelope};
use crate::ops;
use serde_json::Value;
use std::ffi::{c_char, CStr, CString};

static ABI: &[u8] = b"nf-app-core/1\0";

#[no_mangle]
pub extern "C" fn nf_app_core_abi_version() -> *const c_char {
    ABI.as_ptr() as *const c_char
}

fn panic_message(panic: &Box<dyn std::any::Any + Send>) -> String {
    if let Some(s) = panic.downcast_ref::<&str>() {
        (*s).to_string()
    } else if let Some(s) = panic.downcast_ref::<String>() {
        s.clone()
    } else {
        "unknown panic".to_string()
    }
}

fn call_inner(req_json: *const c_char) -> Result<Vec<u8>, CoreError> {
    if req_json.is_null() {
        return Err(CoreError::new("NF-E-003")
            .with_message("nf_app_core_call: req_json 为 NULL")
            .with_exit(2));
    }
    let cstr = unsafe { CStr::from_ptr(req_json) };
    let text = cstr.to_str().map_err(|_| {
        CoreError::new("NF-E-003")
            .with_message("nf_app_core_call: req_json 不是合法 UTF-8")
            .with_exit(2)
    })?;
    let req = crate::canonical::parse_json_bytes(text.as_bytes())?;
    let op = req
        .get("op")
        .and_then(|v| v.as_str())
        .ok_or_else(|| CoreError::new("NF-E-003").with_message("FFI 请求缺 op").with_exit(2))?;
    let params = match req.get("in") {
        None | Some(Value::Null) => Value::Object(serde_json::Map::new()),
        Some(v @ Value::Object(_)) => v.clone(),
        Some(_) => {
            return Err(CoreError::new("NF-E-003")
                .with_message("FFI 请求 in 必须是 object")
                .with_exit(2))
        }
    };
    let env = std::panic::catch_unwind(|| ops::dispatch(op, &params));
    let env = match env {
        Ok(e) => e,
        Err(panic) => {
            let msg = panic_message(&panic);
            eprintln!("nf-app-core(FFI): panic 兜底: {msg}");
            return Err(CoreError::new("NF-E-003")
                .with_message(format!("内部错误（panic 已兜底）：{msg}"))
                .with_exit(2));
        }
    };
    let mut value = env.to_value();
    value["op"] = Value::String(op.to_string());
    canonical_bytes(&value)
}

/// 正常错误也走信封；只有 panic/入参非法才返回 NULL。
#[no_mangle]
pub extern "C" fn nf_app_core_call(req_json: *const c_char) -> *mut c_char {
    match std::panic::catch_unwind(|| call_inner(req_json)) {
        Ok(Ok(bytes)) => match CString::new(bytes) {
            Ok(c) => c.into_raw(),
            Err(_) => std::ptr::null_mut(),
        },
        Ok(Err(err)) => {
            let op = "ffi";
            let env = Envelope::failure(&err, None);
            let mut value = env.to_value();
            value["op"] = Value::String(op.to_string());
            match canonical_bytes(&value)
                .ok()
                .and_then(|b| CString::new(b).ok())
            {
                Some(c) => c.into_raw(),
                None => std::ptr::null_mut(),
            }
        }
        Err(panic) => {
            let msg = panic_message(&panic);
            eprintln!("nf-app-core(FFI): panic 兜底: {msg}");
            std::ptr::null_mut()
        }
    }
}

#[no_mangle]
pub extern "C" fn nf_app_core_free(ptr: *mut c_char) {
    if ptr.is_null() {
        return;
    }
    unsafe {
        drop(CString::from_raw(ptr));
    }
}

#[allow(dead_code)]
fn _unused(_: &str) {
    let _ = cli::help_text();
}
