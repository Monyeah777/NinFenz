use super::*;

pub fn protocol_render(req: &Value) -> OpOutcome {
    let pack = req_value(req, "pack")?;
    let values = match req.get("values") {
        None | Some(Value::Null) => Map::new(),
        Some(Value::Object(m)) => m.clone(),
        Some(_) => return Err(usage("请求字段 values 必须是 object")),
    };
    let explain = req.get("explain").and_then(|v| v.as_bool()).unwrap_or(false);
    let mut explain_out: Vec<Value> = Vec::new();
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
            let value = if explain {
                let mut trace: Vec<Value> = Vec::new();
                let value = eval_expr_traced(expr, &values, &mut trace, &format!("$.rules[{i}].expr"))?;
                explain_out.push(json!({"rule": rid, "value": value, "trace": trace}));
                value
            } else {
                eval_expr(expr, &values)?
            };
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
        let mut value = report.to_value();
        if explain {
            value["explain"] = Value::Array(explain_out);
        }
        return Ok((1, value));
    }
    let mut result = json!({"clauses": rendered, "warnings": warnings});
    if explain {
        result["explain"] = Value::Array(explain_out);
    }
    Ok((0, result))
}
