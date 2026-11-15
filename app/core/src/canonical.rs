//! nf-canonical/1：与 Python json.dumps(obj, ensure_ascii=False, sort_keys=True,
//! separators=(",", ":"), allow_nan=False) 的 UTF-8 字节逐字节一致。禁 float。

use crate::error::CoreError;
use crate::limits::limits;
use serde_json::{Number, Value};
use sha2::{Digest, Sha256};

pub fn sha256_hex(bytes: &[u8]) -> String {
    let mut h = Sha256::new();
    h.update(bytes);
    let out = h.finalize();
    let mut s = String::with_capacity(64);
    for b in out {
        s.push_str(&format!("{b:02x}"));
    }
    s
}

pub fn canonical_bytes(v: &Value) -> Result<Vec<u8>, CoreError> {
    let mut s = String::new();
    encode(v, &mut s, "$", 1)?;
    Ok(s.into_bytes())
}

pub fn canonical_string(v: &Value) -> Result<String, CoreError> {
    let mut s = String::new();
    encode(v, &mut s, "$", 1)?;
    Ok(s)
}

pub fn digest_value(v: &Value) -> Result<String, CoreError> {
    Ok(sha256_hex(&canonical_bytes(v)?))
}

/// 带剔除路径的摘要。路径形式：顶层键名（"history"）、"$.a.b" 或 "/a/b"。
pub fn digest_with_excludes(v: &Value, excludes: &[String]) -> Result<String, CoreError> {
    let mut clone = v.clone();
    for ex in excludes {
        delete_path(&mut clone, ex);
    }
    digest_value(&clone)
}

/// 摘要兜底（仅用于非法 canonical 的待校验对象给报告填 target.digest）。
pub fn digest_allow_float(v: &Value) -> String {
    let mut s = String::new();
    let _ = encode_allow_float(v, &mut s, "$", 1);
    sha256_hex(s.as_bytes())
}

fn delete_path(v: &mut Value, path: &str) {
    let parts: Vec<String> = if let Some(rest) = path.strip_prefix("$.") {
        rest.split('.').map(|s| s.to_string()).collect()
    } else if let Some(rest) = path.strip_prefix('/') {
        rest.split('/').filter(|s| !s.is_empty()).map(|s| s.to_string()).collect()
    } else {
        vec![path.to_string()]
    };
    let mut cur = v;
    for (i, p) in parts.iter().enumerate() {
        let last = i + 1 == parts.len();
        match cur {
            Value::Object(map) => {
                if last {
                    map.remove(p);
                    return;
                }
                match map.get_mut(p) {
                    Some(next) => cur = next,
                    None => return,
                }
            }
            Value::Array(arr) => {
                if let Ok(idx) = p.parse::<usize>() {
                    if idx >= arr.len() {
                        return;
                    }
                    if last {
                        arr.remove(idx);
                        return;
                    }
                    cur = &mut arr[idx];
                } else {
                    return;
                }
            }
            _ => return,
        }
    }
}

fn encode(v: &Value, out: &mut String, path: &str, depth: u64) -> Result<(), CoreError> {
    if depth > limits().json_max_depth {
        return Err(CoreError::new("NF-SEC-003")
            .with_message(format!("JSON 嵌套深度超过 {}（path={path}）", limits().json_max_depth))
            .at(path));
    }
    match v {
        Value::Null => out.push_str("null"),
        Value::Bool(b) => out.push_str(if *b { "true" } else { "false" }),
        Value::Number(n) => encode_number(n, out, path)?,
        Value::String(s) => encode_string(s, out),
        Value::Array(arr) => {
            out.push('[');
            for (i, item) in arr.iter().enumerate() {
                if i > 0 {
                    out.push(',');
                }
                encode(item, out, &format!("{path}[{i}]"), depth + 1)?;
            }
            out.push(']');
        }
        Value::Object(map) => {
            out.push('{');
            let mut keys: Vec<&String> = map.keys().collect();
            keys.sort();
            for (i, k) in keys.iter().enumerate() {
                if i > 0 {
                    out.push(',');
                }
                encode_string(k, out);
                out.push(':');
                encode(&map[*k], out, &obj_path(path, k), depth + 1)?;
            }
            out.push('}');
        }
    }
    Ok(())
}

fn encode_allow_float(v: &Value, out: &mut String, path: &str, depth: u64) -> Result<(), CoreError> {
    if depth > limits().json_max_depth {
        return Err(CoreError::new("NF-SEC-003").at(path));
    }
    match v {
        Value::Number(n) => out.push_str(&n.to_string()),
        Value::Array(arr) => {
            out.push('[');
            for (i, item) in arr.iter().enumerate() {
                if i > 0 {
                    out.push(',');
                }
                encode_allow_float(item, out, &format!("{path}[{i}]"), depth + 1)?;
            }
            out.push(']');
        }
        Value::Object(map) => {
            out.push('{');
            let mut keys: Vec<&String> = map.keys().collect();
            keys.sort();
            for (i, k) in keys.iter().enumerate() {
                if i > 0 {
                    out.push(',');
                }
                encode_string(k, out);
                out.push(':');
                encode_allow_float(&map[*k], out, &obj_path(path, k), depth + 1)?;
            }
            out.push('}');
        }
        other => encode(other, out, path, depth)?,
    }
    Ok(())
}

fn encode_number(n: &Number, out: &mut String, path: &str) -> Result<(), CoreError> {
    if let Some(i) = n.as_i64() {
        out.push_str(&i.to_string());
        Ok(())
    } else if let Some(u) = n.as_u64() {
        out.push_str(&u.to_string());
        Ok(())
    } else {
        Err(CoreError::new("NF-E-006")
            .with_message(format!("canonical 禁止浮点数（path={path}）"))
            .at(path))
    }
}

fn encode_string(s: &str, out: &mut String) {
    out.push('"');
    for ch in s.chars() {
        match ch {
            '"' => out.push_str("\\\""),
            '\\' => out.push_str("\\\\"),
            '\u{08}' => out.push_str("\\b"),
            '\u{0c}' => out.push_str("\\f"),
            '\n' => out.push_str("\\n"),
            '\r' => out.push_str("\\r"),
            '\t' => out.push_str("\\t"),
            c if (c as u32) < 0x20 => out.push_str(&format!("\\u{:04x}", c as u32)),
            c => out.push(c),
        }
    }
    out.push('"');
}

pub fn obj_path(base: &str, key: &str) -> String {
    if key.is_empty() {
        format!("{base}[\"\"]")
    } else if key.chars().all(|c| c.is_ascii_alphanumeric() || c == '_' || c == '-')
        && !key.chars().next().unwrap().is_ascii_digit()
    {
        format!("{base}.{key}")
    } else {
        format!("{base}[{}]", serde_json::to_string(key).unwrap_or_default())
    }
}

/// 解析 JSON 输入（一次读完）：UTF-8 无 BOM、大小/深度上限。
pub fn parse_json_bytes(bytes: &[u8]) -> Result<Value, CoreError> {
    if bytes.len() as u64 > limits().json_max_bytes {
        return Err(CoreError::new("NF-SEC-003")
            .with_message(format!("JSON 输入超过大小上限 {} 字节", limits().json_max_bytes)));
    }
    if bytes.starts_with(&[0xEF, 0xBB, 0xBF]) {
        return Err(CoreError::new("NF-E-003")
            .with_message("JSON 输入带 UTF-8 BOM（nf-canonical/1 禁 BOM）"));
    }
    let text = std::str::from_utf8(bytes)
        .map_err(|e| CoreError::new("NF-E-003").with_message(format!("JSON 输入不是合法 UTF-8: {e}")))?;
    let value: Value = serde_json::from_str(text)
        .map_err(|e| CoreError::new("NF-E-003").with_message(format!("JSON 解析失败: {e}")))?;
    check_depth(&value, "$", 1)?;
    Ok(value)
}

pub fn check_depth(v: &Value, path: &str, depth: u64) -> Result<(), CoreError> {
    if depth > limits().json_max_depth {
        return Err(CoreError::new("NF-SEC-003")
            .with_message(format!("JSON 嵌套深度超过 {}（path={path}）", limits().json_max_depth))
            .at(path));
    }
    match v {
        Value::Array(arr) => {
            for (i, item) in arr.iter().enumerate() {
                check_depth(item, &format!("{path}[{i}]"), depth + 1)?;
            }
        }
        Value::Object(map) => {
            for (k, item) in map.iter() {
                check_depth(item, &obj_path(path, k), depth + 1)?;
            }
        }
        _ => {}
    }
    Ok(())
}

/// 找第一个 float 的路径（用于把「禁浮点」定位成校验 issue）。
pub fn find_float_path(v: &Value, path: &str) -> Option<String> {
    match v {
        Value::Number(n) => {
            if n.is_i64() || n.is_u64() {
                None
            } else {
                Some(path.to_string())
            }
        }
        Value::Array(arr) => arr.iter().enumerate().find_map(|(i, item)| {
            find_float_path(item, &format!("{path}[{i}]"))
        }),
        Value::Object(map) => map
            .iter()
            .find_map(|(k, item)| find_float_path(item, &obj_path(path, k))),
        _ => None,
    }
}

pub fn has_float(v: &Value) -> bool {
    find_float_path(v, "$").is_some()
}

/// 深拷贝并剔除字段（如 plan 的 digest），返回用于摘要的对象。
pub fn without_excludes(v: &Value, excludes: &[&str]) -> Value {
    let mut clone = v.clone();
    for ex in excludes {
        delete_path(&mut clone, ex);
    }
    clone
}
