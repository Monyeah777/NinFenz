//! YAML 最小子集解析器（仅供 nf-import 的 yaml 适配器使用）。
//! 支持：块式 mapping / sequence / 单双引号与裸标量 / 整行注释。
//! 安全：禁别名与锚点（NF-SEC-004，fail-closed），缩进深度上限；不使用流式集合（值按字符串处理）。

use crate::error::CoreError;
use crate::limits::limits;
use serde_json::{Map, Value};

#[derive(Clone, Debug)]
struct Line {
    indent: usize,
    content: String,
    line_no: usize,
}

fn yaml_invalid(line_no: usize, msg: impl Into<String>) -> CoreError {
    CoreError::new("NF-IMP-001")
        .with_message(format!("yaml 解析失败（行 {line_no}）: {}", msg.into()))
        .with_exit(3)
}

fn preprocess(text: &str) -> Result<Vec<Line>, CoreError> {
    let mut out = Vec::new();
    for (i, raw) in text.split('\n').enumerate() {
        let line_no = i + 1;
        let raw = raw.trim_end_matches('\r');
        let mut indent = 0usize;
        for ch in raw.chars() {
            match ch {
                ' ' => indent += 1,
                '\t' => {
                    return Err(yaml_invalid(line_no, "缩进不允许 tab"));
                }
                _ => break,
            }
        }
        if indent > raw.chars().count() {
            return Err(yaml_invalid(line_no, "缩进异常"));
        }
        let content = raw[indent..].trim_end().to_string();
        if content.is_empty() || content.starts_with('#') {
            continue;
        }
        if content == "---" || content == "..." {
            continue;
        }
        let depth = indent / 2;
        if depth as u64 > limits().yaml_max_depth {
            return Err(CoreError::new("NF-SEC-003")
                .with_message(format!("yaml 缩进深度超过上限 {}", limits().yaml_max_depth))
                .with_exit(3));
        }
        check_aliases(line_no, &content)?;
        out.push(Line {
            indent,
            content,
            line_no,
        });
    }
    Ok(out)
}

fn check_aliases(line_no: usize, content: &str) -> Result<(), CoreError> {
    let bytes = content.as_bytes();
    for (i, b) in bytes.iter().enumerate() {
        if *b != b'*' && *b != b'&' {
            continue;
        }
        // 在引号内不判定（简化：用前后字符判断 token 起始）
        let prev_ok = i == 0 || matches!(bytes[i - 1], b' ' | b'\t' | b'[' | b',' | b'{' | b'-');
        let next = bytes.get(i + 1).copied().unwrap_or(0);
        if prev_ok && (next.is_ascii_alphanumeric() || next == b'_') {
            return Err(CoreError::new("NF-SEC-004")
                .with_message(format!(
                    "yaml 别名/锚点不受支持（行 {line_no}）；请改用 JSON 或展开 YAML"
                ))
                .with_exit(3));
        }
    }
    if content.starts_with("<<") {
        return Err(CoreError::new("NF-SEC-004")
            .with_message(format!("yaml merge key 不受支持（行 {line_no}）"))
            .with_exit(3));
    }
    Ok(())
}

fn split_key(content: &str, line_no: usize) -> Option<(String, String)> {
    let mut in_single = false;
    let mut in_double = false;
    let mut prev = '\0';
    for (i, ch) in content.char_indices() {
        match ch {
            '\'' if !in_double && prev != '\\' => in_single = !in_single,
            '"' if !in_single && prev != '\\' => in_double = !in_double,
            ':' if !in_single && !in_double => {
                let next = content[i + 1..].chars().next();
                if next.is_none() || next == Some(' ') {
                    let key = content[..i].trim().to_string();
                    let value = content[i + 1..].trim().to_string();
                    return Some((key, value));
                }
            }
            _ => {}
        }
        prev = ch;
    }
    let _ = line_no;
    None
}

fn scalar(raw: &str, line_no: usize) -> Result<Value, CoreError> {
    let s = raw.trim();
    if s.is_empty() {
        return Ok(Value::Null);
    }
    if (s.starts_with('"') && s.ends_with('"') && s.len() >= 2)
        || (s.starts_with('\'') && s.ends_with('\'') && s.len() >= 2)
    {
        let inner = &s[1..s.len() - 1];
        let unescaped = inner.replace("\\\"", "\"").replace("\\n", "\n").replace("\\t", "\t");
        return Ok(Value::String(unescaped));
    }
    if matches!(s, "null" | "Null" | "NULL" | "~") {
        return Ok(Value::Null);
    }
    if matches!(s, "true" | "True" | "TRUE") {
        return Ok(Value::Bool(true));
    }
    if matches!(s, "false" | "False" | "FALSE") {
        return Ok(Value::Bool(false));
    }
    if let Ok(i) = s.parse::<i64>() {
        return Ok(Value::Number(i.into()));
    }
    if s.starts_with('[') || s.starts_with('{') {
        // 流式集合不在最小子集内：按字符串保留（文档口径），不静默丢内容。
        return Ok(Value::String(s.to_string()));
    }
    let _ = line_no;
    Ok(Value::String(s.to_string()))
}

fn parse_block(lines: &[Line], idx: &mut usize, indent: usize) -> Result<Value, CoreError> {
    if *idx >= lines.len() {
        return Ok(Value::Null);
    }
    let is_seq = lines[*idx].content.starts_with("- ") || lines[*idx].content == "-";
    if is_seq {
        parse_seq(lines, idx, indent)
    } else {
        parse_map(lines, idx, indent)
    }
}

fn parse_seq(lines: &[Line], idx: &mut usize, indent: usize) -> Result<Value, CoreError> {
    let mut arr = Vec::new();
    while *idx < lines.len() {
        let line = &lines[*idx];
        if line.indent != indent || !(line.content.starts_with("- ") || line.content == "-") {
            break;
        }
        let rest = if line.content == "-" {
            String::new()
        } else {
            line.content[2..].trim().to_string()
        };
        let line_no = line.line_no;
        *idx += 1;
        if rest.is_empty() {
            if *idx < lines.len() && lines[*idx].indent > indent {
                let child_indent = lines[*idx].indent;
                arr.push(parse_block(lines, idx, child_indent)?);
            } else {
                arr.push(Value::Null);
            }
            continue;
        }
        if let Some((key, value)) = split_key(&rest, line_no) {
            let mut map = Map::new();
            let mut v = if value.is_empty() {
                if *idx < lines.len() && lines[*idx].indent > indent {
                    let child_indent = lines[*idx].indent;
                    parse_block(lines, idx, child_indent)?
                } else {
                    Value::Null
                }
            } else {
                scalar(&value, line_no)?
            };
            let _ = &mut v;
            map.insert(key, v);
            // 同一 sequence 项内的后续 mapping 行（缩进 > indent）
            if *idx < lines.len() && lines[*idx].indent > indent && !lines[*idx].content.starts_with("- ") {
                let child_indent = lines[*idx].indent;
                let extra = parse_map(lines, idx, child_indent)?;
                if let Value::Object(m) = extra {
                    for (k, val) in m {
                        if map.contains_key(&k) {
                            return Err(yaml_invalid(line_no, format!("重复键 {k}")));
                        }
                        map.insert(k, val);
                    }
                }
            }
            arr.push(Value::Object(map));
        } else {
            arr.push(scalar(&rest, line_no)?);
        }
    }
    Ok(Value::Array(arr))
}

fn parse_map(lines: &[Line], idx: &mut usize, indent: usize) -> Result<Value, CoreError> {
    let mut map = Map::new();
    while *idx < lines.len() {
        let line = &lines[*idx];
        if line.indent != indent {
            break;
        }
        if line.content.starts_with("- ") || line.content == "-" {
            break;
        }
        let line_no = line.line_no;
        let (key, value) = match split_key(&line.content, line_no) {
            Some(kv) => kv,
            None => return Err(yaml_invalid(line_no, format!("mapping 行缺少键值分隔: {}", line.content))),
        };
        if key.is_empty() {
            return Err(yaml_invalid(line_no, "空键"));
        }
        *idx += 1;
        let v = if value.is_empty() {
            if *idx < lines.len() && lines[*idx].indent > indent {
                let child_indent = lines[*idx].indent;
                parse_block(lines, idx, child_indent)?
            } else {
                Value::Null
            }
        } else {
            scalar(&value, line_no)?
        };
        if map.contains_key(&key) {
            return Err(yaml_invalid(line_no, format!("重复键 {key}")));
        }
        map.insert(key, v);
    }
    Ok(Value::Object(map))
}

/// 解析为 JSON Value（最小子集）。别名/锚点/merge key 一律拒绝（fail-closed）。
pub fn parse(text: &str) -> Result<Value, CoreError> {
    let lines = preprocess(text)?;
    if lines.is_empty() {
        return Ok(Value::Null);
    }
    let indent = lines[0].indent;
    let mut idx = 0usize;
    let value = parse_block(&lines, &mut idx, indent)?;
    if idx != lines.len() {
        return Err(yaml_invalid(
            lines[idx].line_no,
            "缩进不一致或存在无法归属的行",
        ));
    }
    Ok(value)
}

pub fn top_entries(value: &Value) -> u64 {
    match value {
        Value::Object(m) => m.len() as u64,
        Value::Array(a) => a.len() as u64,
        _ => 1,
    }
}
