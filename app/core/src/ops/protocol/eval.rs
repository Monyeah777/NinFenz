use super::*;

pub(crate) fn value_to_text(v: &Value) -> Result<String, CoreError> {
    match v {
        Value::String(s) => Ok(s.clone()),
        Value::Number(n) => {
            if n.is_i64() || n.is_u64() {
                Ok(n.to_string())
            } else {
                Err(CoreError::new("NF-PRT-005")
                    .with_message("字段值含浮点数（禁 float）")
                    .with_exit(3))
            }
        }
        Value::Bool(b) => Ok(if *b { "true" } else { "false" }.to_string()),
        Value::Null => Ok(String::new()),
        _ => Err(CoreError::new("NF-PRT-005")
            .with_message("字段值类型不支持（只允许 string/int/bool/null）")
            .with_exit(3)),
    }
}

pub(crate) fn field_default(pack: &Value, fid: &str) -> Option<Value> {
    pack.get("fields")
        .and_then(|v| v.as_array())
        .and_then(|arr| {
            arr.iter()
                .find(|f| f.get("id").and_then(|v| v.as_str()) == Some(fid))
        })
        .and_then(|f| f.get("default").cloned())
        .filter(|v| !v.is_null())
}

pub(crate) fn require_field(pack: &Value, fid: &str) -> bool {
    pack.get("fields")
        .and_then(|v| v.as_array())
        .and_then(|arr| {
            arr.iter()
                .find(|f| f.get("id").and_then(|v| v.as_str()) == Some(fid))
        })
        .and_then(|f| f.get("required"))
        .and_then(|v| v.as_bool())
        .unwrap_or(false)
}

pub(crate) fn expr_error(message: impl Into<String>) -> CoreError {
    CoreError::new("NF-PRT-005")
        .with_message(message.into())
        .with_exit(3)
}

pub(crate) fn resolve_operand(v: &Value, values: &Map<String, Value>) -> Result<Value, CoreError> {
    match v {
        Value::Object(m) => {
            if m.contains_key("op") {
                eval_expr(v, values)
            } else if let Some(f) = m.get("field").and_then(|x| x.as_str()) {
                Ok(values.get(f).cloned().unwrap_or(Value::Null))
            } else {
                Err(expr_error("无法识别的操作数"))
            }
        }
        other => Ok(other.clone()),
    }
}

pub(crate) fn args_of(expr: &Value) -> Vec<Value> {
    let mut args: Vec<Value> = expr
        .get("args")
        .and_then(|v| v.as_array())
        .cloned()
        .unwrap_or_default();
    if args.is_empty() {
        if let Some(f) = expr.get("field") {
            args.push(json!({"field": f}));
            if let Some(v) = expr.get("value") {
                args.push(v.clone());
            }
        }
    }
    args
}

pub(crate) fn eval_expr(expr: &Value, values: &Map<String, Value>) -> Result<Value, CoreError> {
    let op = expr
        .get("op")
        .and_then(|v| v.as_str())
        .ok_or_else(|| expr_error("表达式缺 op"))?;
    if !OPS.contains(&op) {
        return Err(expr_error(format!("未知 op {op}")));
    }
    let raw_args = args_of(expr);
    match op {
        "and" | "or" => {
            if raw_args.len() < 2 {
                return Err(expr_error(format!("op {op} 至少需要 2 个操作数")));
            }
            let mut ok = op == "and";
            for a in &raw_args {
                match resolve_operand(a, values)? {
                    Value::Bool(b) => {
                        if op == "and" {
                            ok = ok && b;
                        } else {
                            ok = ok || b;
                        }
                    }
                    _ => return Err(expr_error(format!("op {op} 的操作数必须是 bool"))),
                }
            }
            Ok(Value::Bool(ok))
        }
        "not" => {
            if raw_args.len() != 1 {
                return Err(expr_error("op not 需要 1 个操作数"));
            }
            match resolve_operand(&raw_args[0], values)? {
                Value::Bool(b) => Ok(Value::Bool(!b)),
                _ => Err(expr_error("op not 的操作数必须是 bool")),
            }
        }
        "exists" => {
            let arg = raw_args
                .first()
                .ok_or_else(|| expr_error("op exists 缺操作数"))?;
            let fid = arg
                .get("field")
                .and_then(|v| v.as_str())
                .ok_or_else(|| expr_error("op exists 需要字段操作数"))?;
            Ok(Value::Bool(values.get(fid).map(|v| !v.is_null()).unwrap_or(false)))
        }
        "len" => {
            let arg = raw_args
                .first()
                .ok_or_else(|| expr_error("op len 缺操作数"))?;
            let v = resolve_operand(arg, values)?;
            let n = match &v {
                Value::String(s) => s.chars().count() as u64,
                Value::Array(a) => a.len() as u64,
                Value::Object(m) => m.len() as u64,
                _ => return Err(expr_error("op len 只接受 string/array/object")),
            };
            Ok(Value::Number(n.into()))
        }
        "in" => {
            let fid = expr
                .get("field")
                .and_then(|v| v.as_str())
                .ok_or_else(|| expr_error("op in 需要 field"))?;
            let arr = expr
                .get("value")
                .and_then(|v| v.as_array())
                .ok_or_else(|| expr_error("op in 需要数组 value"))?;
            let actual = values.get(fid).cloned().unwrap_or(Value::Null);
            Ok(Value::Bool(arr.iter().any(|v| v == &actual)))
        }
        "matches" => {
            if raw_args.len() != 2 {
                return Err(expr_error("op matches 需要 2 个操作数"));
            }
            let subject = resolve_operand(&raw_args[0], values)?;
            let pat = resolve_operand(&raw_args[1], values)?;
            let s = match subject {
                Value::String(s) => s,
                _ => return Err(expr_error("op matches 的被匹配值必须是 string")),
            };
            let p = match pat {
                Value::String(p) => p,
                _ => return Err(expr_error("op matches 的 pattern 必须是 string")),
            };
            let hit = regex_matches(&p, &s)
                .map_err(|e| expr_error(format!("matches 正则非法：{e}")))?;
            Ok(Value::Bool(hit))
        }
        _ => {
            if raw_args.len() != 2 {
                return Err(expr_error(format!("op {op} 需要 2 个操作数")));
            }
            let a = resolve_operand(&raw_args[0], values)?;
            let b = resolve_operand(&raw_args[1], values)?;
            match op {
                "eq" => Ok(Value::Bool(a == b)),
                "ne" => Ok(Value::Bool(a != b)),
                _ => {
                    let ord = compare_values(&a, &b, op)?;
                    Ok(Value::Bool(match op {
                        "gt" => ord,
                        "gte" => ord,
                        "lt" => !ord && a != b,
                        "lte" => !ord || a == b,
                        _ => return Err(expr_error(format!("未知 op {op}"))),
                    }))
                }
            }
        }
    }
}

pub(crate) fn eval_expr_traced(
    expr: &Value,
    values: &Map<String, Value>,
    trace: &mut Vec<Value>,
    path: &str,
) -> Result<Value, CoreError> {
    let value = eval_expr(expr, values)?;
    let op = expr.get("op").and_then(|v| v.as_str()).unwrap_or("");
    trace.push(json!({"path": path, "op": op, "value": value.clone()}));
    if let Some(args) = expr.get("args").and_then(|v| v.as_array()) {
        for (i, arg) in args.iter().enumerate() {
            let child_path = format!("{path}.args[{i}]");
            if arg.get("op").is_some() {
                eval_expr_traced(arg, values, trace, &child_path)?;
            } else {
                let operand = resolve_operand(arg, values)?;
                trace.push(json!({"path": child_path, "value": operand}));
            }
        }
    }
    Ok(value)
}

pub(crate) fn compare_values(a: &Value, b: &Value, op: &str) -> Result<bool, CoreError> {
    match (a, b) {
        (Value::Number(x), Value::Number(y)) => {
            let (xi, yi) = (x.as_i64(), y.as_i64());
            match (xi, yi) {
                (Some(xi), Some(yi)) => Ok(xi < yi),
                _ => Err(expr_error(format!("op {op} 不支持浮点比较"))),
            }
        }
        (Value::String(x), Value::String(y)) => Ok(x < y),
        _ => Err(expr_error(format!(
            "op {op} 类型不匹配：{} vs {}",
            type_name(a),
            type_name(b)
        ))),
    }
}

pub(crate) fn type_name(v: &Value) -> &'static str {
    match v {
        Value::Null => "null",
        Value::Bool(_) => "bool",
        Value::Number(_) => "number",
        Value::String(_) => "string",
        Value::Array(_) => "array",
        Value::Object(_) => "object",
    }
}
