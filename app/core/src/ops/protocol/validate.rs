use super::*;

pub const OPS: &[&str] = &[
    "and", "or", "not", "eq", "ne", "gt", "gte", "lt", "lte", "in", "matches", "exists", "len",
];

pub(crate) fn field_id_ok(s: &str) -> bool {
    let b = s.as_bytes();
    b.len() == 5 && b[0] == b'F' && b[1] == b'-' && b[2].is_ascii_digit() && b[3].is_ascii_digit() && b[4].is_ascii_digit()
}

pub(crate) fn protocol_fields(pack: &Value) -> BTreeSet<String> {
    pack.get("fields")
        .and_then(|v| v.as_array())
        .map(|arr| {
            arr.iter()
                .filter_map(|f| f.get("id").and_then(|v| v.as_str()).map(|s| s.to_string()))
                .collect()
        })
        .unwrap_or_default()
}

pub(crate) fn walk_expr(
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

pub(crate) fn walk_operand(
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

pub(crate) fn placeholders(text: &str) -> Vec<String> {
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
