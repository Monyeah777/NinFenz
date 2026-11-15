//! 协议包：protocol-validate / protocol-render（条款占位符 + 封闭规则 DSL）。

use crate::error::{CoreError, OpOutcome};
use crate::ops::{float_issue, ref_id, req_value, usage};
use crate::report::Report;
use crate::schema::regex_matches;
use serde_json::{json, Map, Value};
use std::collections::BTreeSet;

pub const OPS: &[&str] = &[
    "and", "or", "not", "eq", "ne", "gt", "gte", "lt", "lte", "in", "matches", "exists", "len",
];

fn field_id_ok(s: &str) -> bool {
    let b = s.as_bytes();
    b.len() == 5 && b[0] == b'F' && b[1] == b'-' && b[2].is_ascii_digit() && b[3].is_ascii_digit() && b[4].is_ascii_digit()
}

fn protocol_fields(pack: &Value) -> BTreeSet<String> {
    pack.get("fields")
        .and_then(|v| v.as_array())
        .map(|arr| {
            arr.iter()
                .filter_map(|f| f.get("id").and_then(|v| v.as_str()).map(|s| s.to_string()))
                .collect()
        })
        .unwrap_or_default()
}

fn walk_expr(
    expr: &Value,
    fields: &BTreeSet<String>,
    issues: &mut Vec<(String, String, String)>,
    path: &str,
) {
    let op = match expr.get("op").and_then(|v| v.as_str()) {
        Some(op) => op,
        None => {
            issues.push((
                "NF-PRT-005".into(),
                path.into(),
                "规则表达式缺 op".into(),
            ));
            return;
        }
    };
    if !OPS.contains(&op) {
        issues.push((
            "NF-PRT-005".into(),
            format!("{path}.op"),
            format!("规则 op {op} 不在白名单（fail-closed）"),
        ));
        return;
    }
    let args = expr.get("args").and_then(|v| v.as_array()).cloned().unwrap_or_default();
    match op {
        "and" | "or" => {
            if args.len() < 2 {
                issues.push((
                    "NF-PRT-005".into(),
                    format!("{path}.args"),
                    format!("op {op} 至少需要 2 个操作数"),
                ));
            }
        }
        "not" => {
            if args.len() != 1 {
                issues.push((
                    "NF-PRT-005".into(),
                    format!("{path}.args"),
                    "op not 需要 1 个操作数".into(),
                ));
            }
        }
        "exists" | "len" => {
            let has_field = expr
                .get("field")
                .and_then(|v| v.as_str())
                .is_some();
            if !has_field && args.len() != 1 {
                issues.push((
                    "NF-PRT-005".into(),
                    format!("{path}"),
                    format!("op {op} 需要 field 或 1 个操作数"),
                ));
            }
        }
        "in" => {
            if !expr.get("value").map(|v| v.is_array()).unwrap_or(false) {
                issues.push((
                    "NF-PRT-005".into(),
                    format!("{path}.value"),
                    "op in 需要数组 value".into(),
                ));
            }
        }
        _ => {
            let has_pair = expr.get("field").is_some() && expr.get("value").is_some();
            if args.len() != 2 && !has_pair {
                issues.push((
                    "NF-PRT-005".into(),
                    format!("{path}.args"),
                    format!("op {op} 需要 2 个操作数（或 field+value）"),
                ));
            }
        }
    }
    for (i, arg) in args.iter().enumerate() {
        walk_operand(arg, fields, issues, &format!("{path}.args[{i}]"));
    }
    if let Some(f) = expr.get("field").and_then(|v| v.as_str()) {
        if !field_id_ok(f) {
            issues.push((
                "NF-PRT-005".into(),
                format!("{path}.field"),
                format!("字段操作数格式非法：{f}"),
            ));
        } else if !fields.contains(f) {
            issues.push((
                "NF-PRT-001".into(),
                format!("{path}.field"),
                format!("引用了未声明的字段 {f}"),
            ));
        }
    }
}

fn walk_operand(
    v: &Value,
    fields: &BTreeSet<String>,
    issues: &mut Vec<(String, String, String)>,
    path: &str,
) {
    match v {
        Value::Object(m) => {
            if m.contains_key("op") {
                walk_expr(v, fields, issues, path);
            } else if let Some(f) = m.get("field").and_then(|x| x.as_str()) {
                if m.len() != 1 {
                    issues.push((
                        "NF-PRT-005".into(),
                        path.into(),
                        "字段操作数只允许 {field}".into(),
                    ));
                }
                if !field_id_ok(f) {
                    issues.push((
                        "NF-PRT-005".into(),
                        format!("{path}.field"),
                        format!("字段操作数格式非法：{f}"),
                    ));
                } else if !fields.contains(f) {
                    issues.push((
                        "NF-PRT-001".into(),
                        format!("{path}.field"),
                        format!("引用了未声明的字段 {f}"),
                    ));
                }
            } else {
                issues.push((
                    "NF-PRT-005".into(),
                    path.into(),
                    "无法识别的操作数（需 expr / {field} / 标量）".into(),
                ));
            }
        }
        _ => {}
    }
}

/// 协议包校验（protocol-validate 与 protocol-render 共用）。
pub fn validate_protocol(pack: &Value) -> Report {
    let mut report = Report::new("L0", pack, "protocol-pack", &ref_id(pack, "id"));
    let fields = protocol_fields(pack);
    let mut issues: Vec<(String, String, String)> = Vec::new();

    // 规则表达式语义（未知 op → NF-PRT-005）
    if let Some(rules) = pack.get("rules").and_then(|v| v.as_array()) {
        for (i, r) in rules.iter().enumerate() {
            if let Some(expr) = r.get("expr") {
                walk_expr(expr, &fields, &mut issues, &format!("$.rules[{i}].expr"));
            }
        }
    }
    for (code, path, msg) in &issues {
        report.error(code, path, msg);
    }

    let schema_issues = crate::schema::validate("nf-protocol-pack", pack);
    report.extend_schema_issues("NF-PRT-001", &schema_issues);
    float_issue(&mut report, pack, "NF-PRT-001");

    // id 唯一
    for (key, path, prefix_ok) in [
        ("clauses", "$.clauses", "C-"),
        ("fields", "$.fields", "F-"),
        ("rules", "$.rules", "R-"),
        ("examples", "$.examples", "EX-"),
    ] {
        let _ = prefix_ok;
        let mut seen = BTreeSet::new();
        if let Some(arr) = pack.get(key).and_then(|v| v.as_array()) {
            for (i, item) in arr.iter().enumerate() {
                if let Some(id) = item.get("id").and_then(|v| v.as_str()) {
                    if !seen.insert(id.to_string()) {
                        report.error(
                            "NF-PRT-002",
                            &format!("{path}[{i}].id"),
                            &format!("{key} id 重复：{id}"),
                        );
                    }
                }
            }
        }
    }

    let clause_ids: BTreeSet<String> = pack
        .get("clauses")
        .and_then(|v| v.as_array())
        .map(|a| {
            a.iter()
                .filter_map(|c| c.get("id").and_then(|v| v.as_str()).map(|s| s.to_string()))
                .collect()
        })
        .unwrap_or_default();

    // 引用完整性
    if let Some(fields_arr) = pack.get("fields").and_then(|v| v.as_array()) {
        for (i, f) in fields_arr.iter().enumerate() {
            if let Some(cid) = f.get("clause").and_then(|v| v.as_str()) {
                if !clause_ids.contains(cid) {
                    report.error(
                        "NF-PRT-001",
                        &format!("$.fields[{i}].clause"),
                        &format!("字段引用了不存在的条款 {cid}"),
                    );
                }
            }
        }
    }
    if let Some(clauses) = pack.get("clauses").and_then(|v| v.as_array()) {
        for (i, c) in clauses.iter().enumerate() {
            if let Some(fs) = c.get("fields").and_then(|v| v.as_array()) {
                for (j, f) in fs.iter().enumerate() {
                    if let Some(fid) = f.as_str() {
                        if !fields.contains(fid) {
                            report.error(
                                "NF-PRT-001",
                                &format!("$.clauses[{i}].fields[{j}]"),
                                &format!("条款引用了不存在的字段 {fid}"),
                            );
                        }
                    }
                }
            }
            if let Some(text) = c.get("text").and_then(|v| v.as_str()) {
                for ph in placeholders(text) {
                    if !fields.contains(&ph) {
                        report.error(
                            "NF-PRT-004",
                            &format!("$.clauses[{i}].text"),
                            &format!("条款文本含未声明占位符 {{{{{ph}}}}}"),
                        );
                    }
                }
            }
        }
    }

    // 兼容范围
    if let Some(compat) = pack.get("compat") {
        let pmin = compat.get("protocol_min").and_then(|v| v.as_i64());
        let pmax = compat.get("protocol_max").and_then(|v| v.as_i64());
        let pv = pack.get("proto_version").and_then(|v| v.as_i64());
        if let (Some(a), Some(b)) = (pmin, pmax) {
            if a > b {
                report.error(
                    "NF-PRT-006",
                    "$.compat.protocol_min",
                    "protocol_min 大于 protocol_max",
                );
            }
        }
        if let (Some(v), Some(a), Some(b)) = (pv, pmin, pmax) {
            if v < a || v > b {
                report.error(
                    "NF-PRT-006",
                    "$.proto_version",
                    &format!("proto_version {v} 不在兼容范围 [{a},{b}] 内"),
                );
            }
        }
    }
    if let Some(ms) = pack.get("migrations").and_then(|v| v.as_array()) {
        for (i, m) in ms.iter().enumerate() {
            if let (Some(a), Some(b)) = (
                m.get("from").and_then(|v| v.as_i64()),
                m.get("to").and_then(|v| v.as_i64()),
            ) {
                if a >= b {
                    report.error(
                        "NF-PRT-006",
                        &format!("$.migrations[{i}]"),
                        "migration 的 from 必须小于 to",
                    );
                }
            }
        }
    }
    report
}

fn placeholders(text: &str) -> Vec<String> {
    let mut out = Vec::new();
    let re = regex::Regex::new(r"\{\{([^{}]*)\}\}").expect("占位符正则");
    for cap in re.captures_iter(text) {
        out.push(cap[1].trim().to_string());
    }
    out
}

pub fn protocol_validate(req: &Value) -> OpOutcome {
    let pack = req_value(req, "pack")?;
    let report = validate_protocol(pack);
    Ok((0, report.to_value()))
}

fn value_to_text(v: &Value) -> Result<String, CoreError> {
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

fn field_default(pack: &Value, fid: &str) -> Option<Value> {
    pack.get("fields")
        .and_then(|v| v.as_array())
        .and_then(|arr| {
            arr.iter()
                .find(|f| f.get("id").and_then(|v| v.as_str()) == Some(fid))
        })
        .and_then(|f| f.get("default").cloned())
        .filter(|v| !v.is_null())
}

fn require_field(pack: &Value, fid: &str) -> bool {
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

fn expr_error(message: impl Into<String>) -> CoreError {
    CoreError::new("NF-PRT-005")
        .with_message(message.into())
        .with_exit(3)
}

fn resolve_operand(v: &Value, values: &Map<String, Value>) -> Result<Value, CoreError> {
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

fn args_of(expr: &Value) -> Vec<Value> {
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

fn eval_expr(expr: &Value, values: &Map<String, Value>) -> Result<Value, CoreError> {
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

fn compare_values(a: &Value, b: &Value, op: &str) -> Result<bool, CoreError> {
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

fn type_name(v: &Value) -> &'static str {
    match v {
        Value::Null => "null",
        Value::Bool(_) => "bool",
        Value::Number(_) => "number",
        Value::String(_) => "string",
        Value::Array(_) => "array",
        Value::Object(_) => "object",
    }
}

pub fn protocol_render(req: &Value) -> OpOutcome {
    let pack = req_value(req, "pack")?;
    let values = match req.get("values") {
        None | Some(Value::Null) => Map::new(),
        Some(Value::Object(m)) => m.clone(),
        Some(_) => return Err(usage("请求字段 values 必须是 object")),
    };
    // fail-closed：协议版本不在兼容范围直接拒绝（exit 3）
    if let (Some(pv), Some(compat)) = (
        pack.get("proto_version").and_then(|v| v.as_i64()),
        pack.get("compat"),
    ) {
        let pmin = compat.get("protocol_min").and_then(|v| v.as_i64());
        let pmax = compat.get("protocol_max").and_then(|v| v.as_i64());
        if let (Some(a), Some(b)) = (pmin, pmax) {
            if pv < a || pv > b {
                return Err(CoreError::new("NF-PRT-006")
                    .with_message(format!("proto_version {pv} 不在兼容范围 [{a},{b}] 内"))
                    .with_exit(3));
            }
        }
    }
    let report = validate_protocol(pack);
    if report.has_error() {
        return Ok((1, report.to_value()));
    }
    let fields = protocol_fields(pack);
    let mut warnings: Vec<Value> = Vec::new();
    let mut errors: Vec<(String, String, String)> = Vec::new();
    let mut rendered: Vec<Value> = Vec::new();
    if let Some(clauses) = pack.get("clauses").and_then(|v| v.as_array()) {
        for (i, clause) in clauses.iter().enumerate() {
            let cid = clause.get("id").and_then(|v| v.as_str()).unwrap_or("");
            let text = clause.get("text").and_then(|v| v.as_str()).unwrap_or("");
            let mut out = String::with_capacity(text.len());
            let mut rest = text;
            let re = regex::Regex::new(r"\{\{([^{}]*)\}\}").expect("占位符正则");
            loop {
                let cap = match re.captures(rest) {
                    Some(c) => c,
                    None => {
                        out.push_str(rest);
                        break;
                    }
                };
                let m = cap.get(0).unwrap();
                out.push_str(&rest[..m.start()]);
                let fid = cap[1].trim().to_string();
                if !field_id_ok(&fid) || !fields.contains(&fid) {
                    errors.push((
                        "NF-PRT-004".into(),
                        format!("$.clauses[{i}].text"),
                        format!("条款文本含未声明占位符 {{{{{fid}}}}}"),
                    ));
                    out.push_str(m.as_str());
                } else {
                    let val = values
                        .get(&fid)
                        .cloned()
                        .or_else(|| field_default(pack, &fid));
                    match val {
                        Some(v) => {
                            let text_v = value_to_text(&v)?;
                            out.push_str(&text_v);
                        }
                        None => {
                            if require_field(pack, &fid) {
                                errors.push((
                                    "NF-PRT-003".into(),
                                    format!("$.clauses[{i}].text"),
                                    format!("必填字段 {fid} 无值，条款 {cid} 无法渲染"),
                                ));
                            } else {
                                warnings.push(json!({
                                    "code": "NF-PRT-003",
                                    "severity": "warn",
                                    "message": format!("可选字段 {fid} 无值，占位符已渲染为空串"),
                                }));
                            }
                        }
                    }
                }
                rest = &rest[m.end()..];
            }
            rendered.push(json!({"id": cid, "text": out}));
        }
    }
    // 规则求值
    if let Some(rules) = pack.get("rules").and_then(|v| v.as_array()) {
        for (i, rule) in rules.iter().enumerate() {
            let rid = rule.get("id").and_then(|v| v.as_str()).unwrap_or("");
            let severity = rule.get("severity").and_then(|v| v.as_str()).unwrap_or("error");
            let expr = match rule.get("expr") {
                Some(e) => e,
                None => continue,
            };
            let value = eval_expr(expr, &values)?;
            let ok = match value {
                Value::Bool(b) => b,
                _ => return Err(expr_error(format!("规则 {rid} 求值结果不是 bool"))),
            };
            if !ok {
                if severity == "error" {
                    errors.push((
                        "NF-PRT-005".into(),
                        format!("$.rules[{i}]"),
                        format!(
                            "规则 {rid} 不满足：{}",
                            rule.get("message")
                                .and_then(|v| v.as_str())
                                .unwrap_or("")
                        ),
                    ));
                } else {
                    warnings.push(json!({
                        "code": "NF-PRT-005",
                        "severity": "warn",
                        "message": format!(
                            "规则 {rid} 未满足：{}",
                            rule.get("message").and_then(|v| v.as_str()).unwrap_or("")
                        ),
                    }));
                }
            }
        }
    }
    if !errors.is_empty() {
        let mut report = Report::new("L0", pack, "protocol-pack", &ref_id(pack, "id"));
        for (code, path, msg) in &errors {
            report.error(code, path, msg);
        }
        return Ok((1, report.to_value()));
    }
    Ok((
        0,
        json!({"clauses": rendered, "warnings": warnings}),
    ))
}
