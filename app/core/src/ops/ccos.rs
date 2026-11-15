//! CCOS 交接：ccos-build-task / ccos-import-result（A6）。

use crate::canonical::{digest_value, sha256_hex};
use crate::error::{CoreError, OpOutcome};
use crate::ops::{float_issue, ref_id, req_str, req_value};
use crate::ops::project::validate_project;
use crate::report::Report;
use crate::schema::validate;
use serde_json::{json, Map, Value};

fn created_at_ok(s: &str) -> bool {
    let re = regex::Regex::new(
        r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(\\.[0-9]+)?(Z|[+-][0-9]{2}:[0-9]{2})$",
    )
    .expect("created_at 正则");
    re.is_match(s)
}

fn secret_hit(value: &Value) -> Option<(String, String)> {
    match value {
        Value::Object(m) => {
            for (k, v) in m.iter() {
                let lower = k.to_ascii_lowercase();
                let parts: Vec<&str> = lower
                    .split(|c: char| c == '_' || c == '-' || c == '.')
                    .collect();
                let banned_exact = matches!(
                    lower.as_str(),
                    "password"
                        | "passwd"
                        | "secret"
                        | "token"
                        | "apikey"
                        | "authorization"
                        | "credential"
                );
                let banned_part = parts.iter().any(|p| {
                    matches!(
                        *p,
                        "password" | "passwd" | "secret" | "token" | "credential" | "authorization"
                    )
                });
                let banned_pair = parts.windows(2).any(|w| {
                    matches!(
                        (w[0], w[1]),
                        ("api", "key") | ("private", "key") | ("access", "key")
                    )
                });
                if banned_exact || banned_part || banned_pair {
                    return Some((format!("[key:{k}]"), format!("禁止的密钥形状字段名 {k}")));
                }
                if let Some(hit) = secret_hit(v) {
                    return Some(hit);
                }
            }
            None
        }
        Value::Array(arr) => {
            for (i, v) in arr.iter().enumerate() {
                if let Some((p, r)) = secret_hit(v) {
                    return Some((format!("[{i}]{p}"), r));
                }
            }
            None
        }
        Value::String(s) => {
            let trimmed = s.trim();
            let abs = trimmed.starts_with('/')
                || trimmed.starts_with("\\\\")
                || (trimmed.len() >= 3
                    && trimmed.as_bytes()[0].is_ascii_alphabetic()
                    && trimmed.as_bytes()[1] == b':'
                    && (trimmed.as_bytes()[2] == b'\\' || trimmed.as_bytes()[2] == b'/'));
            if abs && !trimmed.is_empty() {
                return Some(("[]".into(), "禁止携带绝对路径".into()));
            }
            let at_token_start = |needle: &str| {
                s.starts_with(needle) || s.contains(&format!(" {needle}"))
            };
            for needle in ["sk-", "ghp_", "AKIA", "Bearer ", "-----BEGIN"] {
                if at_token_start(needle) {
                    return Some(("[]".into(), format!("禁止的密钥形状内容（{needle}）")));
                }
            }
            None
        }
        _ => None,
    }
}

fn path_ok(p: &str) -> bool {
    crate::fsutil::validate_rel_path(p).is_ok()
}

fn ccos_report(target: &Value, kind: &str, code: &str, path: &str, message: &str) -> Value {
    let mut report = Report::new("L0", target, kind, &ref_id(target, "id"));
    report.error(code, path, message);
    report.to_value()
}

pub fn ccos_build_task(req: &Value) -> OpOutcome {
    let project = req_value(req, "project")?;
    let project_report = validate_project(project);
    if project_report.has_error() {
        return Ok((1, project_report.to_value()));
    }
    let status = project.get("status").and_then(|v| v.as_str()).unwrap_or("");
    if !matches!(status, "validated" | "exported" | "reviewed") {
        return Ok((
            1,
            ccos_report(
                project,
                "project",
                "NF-CCOS-001",
                "$.status",
                "项目尚未 validated，不能生成 CCOS 任务",
            ),
        ));
    }
    let task_id = req_str(req, "task_id")?;
    let created_at = req_str(req, "created_at")?;
    if !created_at_ok(created_at) {
        return Ok((
            1,
            ccos_report(
                &Value::Null,
                "ccos-task",
                "NF-CCOS-001",
                "$.created_at",
                "created_at 必须是 RFC3339 时间戳（由调用方显式给出）",
            ),
        ));
    }
    let budget = req_value(req, "budget")?;
    if !budget.is_object() {
        return Err(crate::ops::usage("请求字段 budget 必须是 object"));
    }
    let refs = project.get("refs").cloned().unwrap_or(Value::Null);
    let base_pack = refs.get("base_pack").cloned().unwrap_or(Value::Null);
    let protocol = refs.get("protocol").cloned().unwrap_or(Value::Null);
    let assembly = refs.get("assembly").cloned().unwrap_or(Value::Null);
    let spec = refs.get("spec").cloned().unwrap_or(Value::Null);
    let variables = match req.get("variables") {
        None | Some(Value::Null) => json!({}),
        Some(v @ Value::Object(_)) => v.clone(),
        Some(_) => return Err(crate::ops::usage("请求字段 variables 必须是 object")),
    };
    let mut inputs: Vec<Value> = Vec::new();
    if let Some(arr) = req.get("inputs") {
        let arr = arr
            .as_array()
            .ok_or_else(|| crate::ops::usage("请求字段 inputs 必须是数组"))?;
        for (i, item) in arr.iter().enumerate() {
            let slot = item
                .get("slot")
                .and_then(|v| v.as_str())
                .ok_or_else(|| crate::ops::usage(format!("inputs[{i}].slot 缺失")))?;
            if !regex::Regex::new(r"^SLT-[0-9]{2,3}$")
                .expect("slot 正则")
                .is_match(slot)
            {
                return Err(crate::ops::usage(format!("inputs[{i}].slot 格式非法：{slot}")));
            }
            if item.get("value").is_none() {
                return Err(crate::ops::usage(format!("inputs[{i}].value 缺失")));
            }
            inputs.push(item.clone());
        }
    }
    let string_array = |key: &str| -> Result<Vec<Value>, CoreError> {
        match req.get(key) {
            None | Some(Value::Null) => Ok(Vec::new()),
            Some(Value::Array(a)) => {
                for v in a {
                    if !v.is_string() {
                        return Err(crate::ops::usage(format!("请求字段 {key} 必须是字符串数组")));
                    }
                }
                Ok(a.clone())
            }
            Some(_) => Err(crate::ops::usage(format!("请求字段 {key} 必须是数组"))),
        }
    };
    let constraints = string_array("constraints")?;
    let acceptance = string_array("acceptance")?;

    let task = json!({
        "schema": "ccos-task/1",
        "id": task_id,
        "created_at": created_at,
        "pack": {
            "id": base_pack.get("id").cloned().unwrap_or(Value::Null),
            "version": base_pack.get("version").cloned().unwrap_or(Value::Null),
            "tree": base_pack.get("tree").cloned().unwrap_or(Value::Null),
        },
        "protocol": {
            "id": protocol.get("id").cloned().unwrap_or(Value::Null),
            "version": protocol.get("version").cloned().unwrap_or(Value::Null),
            "digest": protocol.get("digest").cloned().unwrap_or(Value::Null),
        },
        "pipeline": {
            "id": assembly.get("id").cloned().unwrap_or(Value::Null),
            "version": assembly.get("version").cloned().unwrap_or(Value::Null),
            "digest": assembly.get("digest").cloned().unwrap_or(Value::Null),
        },
        "md_spec": {
            "id": spec.get("id").cloned().unwrap_or(Value::Null),
            "version": spec.get("version").cloned().unwrap_or(Value::Null),
            "digest": spec.get("digest").cloned().unwrap_or(Value::Null),
        },
        "inputs": inputs,
        "variables": variables,
        "constraints": constraints,
        "acceptance": acceptance,
        "budget": budget,
        "policy": {"network": false, "tools": ["assemble", "export"], "secrets": "ccos-only"},
        "provenance": {
            "project_id": project.get("id").cloned().unwrap_or(Value::Null),
            "project_digest": crate::report::target_digest(project),
            "app_version": crate::CORE_VERSION,
        },
    });
    let issues = validate("ccos-task", &task);
    if !issues.is_empty() {
        let mut report = Report::new("L0", &task, "ccos-task", task_id);
        report.extend_schema_issues("NF-CCOS-001", &issues);
        return Ok((1, report.to_value()));
    }
    let mut r = Report::new("L0", &task, "ccos-task", task_id);
    let _ = float_issue(&mut r, &task, "NF-CCOS-001");
    if let Some((path, reason)) = secret_hit(&task) {
        return Err(CoreError::new("NF-CCOS-003")
            .with_message(format!("任务含密钥/绝对路径（{path}{reason}）"))
            .with_exit(3));
    }
    // 二次确认：任何字符串值都不得是本机绝对路径（包内相对路径允许）
    Ok((0, task))
}

pub fn ccos_import_result(req: &Value) -> OpOutcome {
    let task = req_value(req, "task")?;
    let result = req_value(req, "result")?;
    let task_issues = validate("ccos-task", task);
    if !task_issues.is_empty() {
        let mut report = Report::new("L0", task, "ccos-task", &ref_id(task, "id"));
        report.extend_schema_issues("NF-CCOS-001", &task_issues);
        return Ok((1, report.to_value()));
    }
    let result_issues = validate("ccos-result", result);
    if !result_issues.is_empty() {
        let mut report = Report::new("L0", result, "ccos-result", &ref_id(result, "task_id"));
        report.extend_schema_issues("NF-CCOS-001", &result_issues);
        return Ok((1, report.to_value()));
    }
    let task_id = task.get("id").and_then(|v| v.as_str()).unwrap_or("");
    let result_task_id = result.get("task_id").and_then(|v| v.as_str()).unwrap_or("");
    let task_digest = match digest_value(task) {
        Ok(d) => d,
        Err(_) => crate::canonical::digest_allow_float(task),
    };
    let declared = result.get("task_digest").and_then(|v| v.as_str()).unwrap_or("");
    let mut problems: Vec<(String, String, String)> = Vec::new();
    if result_task_id != task_id {
        problems.push((
            "NF-CCOS-002".into(),
            "$.task_id".into(),
            format!("task_id 不一致：任务 {task_id}，结果 {result_task_id}"),
        ));
    }
    if declared != task_digest {
        problems.push((
            "NF-CCOS-002".into(),
            "$.task_digest".into(),
            format!("task_digest 回钉不一致：声明 {declared}，实际 {task_digest}"),
        ));
    }
    if let Some(artifacts) = result.get("artifacts").and_then(|v| v.as_array()) {
        for (i, a) in artifacts.iter().enumerate() {
            let p = a.get("path").and_then(|v| v.as_str()).unwrap_or("");
            if !path_ok(p) {
                problems.push((
                    "NF-CCOS-001".into(),
                    format!("$.artifacts[{i}].path"),
                    format!("artifact 路径不安全（绝对/..）：{p}"),
                ));
            }
        }
    }
    if let Some((path, reason)) = secret_hit(result) {
        return Err(CoreError::new("NF-CCOS-003")
            .with_message(format!("结果含密钥/绝对路径（{path}{reason}）"))
            .with_exit(3));
    }
    if !problems.is_empty() {
        let mut report = Report::new("L0", result, "ccos-result", task_id);
        for (code, path, msg) in &problems {
            report.error(code, path, msg);
        }
        return Ok((1, report.to_value()));
    }
    let review_state = result["human_review"]["state"]
        .as_str()
        .unwrap_or("pending")
        .to_string();
    let mut issues: Vec<Value> = Vec::new();
    if review_state != "approved" {
        issues.push(json!({
            "code": "NF-CCOS-004",
            "severity": "warn",
            "message": "人审未完成（human_review.required 恒 true，需在 APP 内 approved）",
        }));
    }
    let status = result.get("status").and_then(|v| v.as_str()).unwrap_or("partial");
    let _ = Map::new();
    let _ = sha256_hex(b"");
    Ok((
        0,
        json!({
            "status": status,
            "review": {"state": review_state},
            "issues": issues,
        }),
    ))
}
