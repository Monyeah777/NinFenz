//! 项目：project-validate（引用/状态机/评审绑定）。

use crate::error::OpOutcome;
use crate::ops::{float_issue, ref_id, req_value};
use crate::report::Report;
use crate::schema::validate;
use serde_json::Value;

pub fn validate_project(project: &Value) -> Report {
    let mut report = Report::new("L0", project, "project", &ref_id(project, "id"));
    let issues = validate("nf-project", project);
    report.extend_schema_issues("NF-VAL-001", &issues);
    float_issue(&mut report, project, "NF-VAL-001");

    let status = project.get("status").and_then(|v| v.as_str()).unwrap_or("");
    let has_assembly = project
        .get("refs")
        .and_then(|r| r.get("assembly"))
        .is_some();
    if matches!(status, "assembled" | "validated" | "exported" | "reviewed") && !has_assembly {
        report.error(
            "NF-VAL-001",
            "$.refs.assembly",
            "状态已到 assembled 之后，必须给 assembly 引用（path/sha256/digest，见 nf-project schema）",
        );
    }
    let history: Vec<Value> = project
        .get("history")
        .and_then(|v| v.as_array())
        .cloned()
        .unwrap_or_default();
    if status == "exported" || status == "reviewed" {
        let has_export = history
            .iter()
            .any(|h| h.get("op").and_then(|v| v.as_str()) == Some("export"));
        if !has_export {
            report.error(
                "NF-VAL-001",
                "$.history",
                "状态 exported/reviewed 要求 history 含 op=export 记录",
            );
        }
    }
    let review = project.get("review").cloned().unwrap_or(Value::Null);
    let review_state = review.get("state").and_then(|v| v.as_str()).unwrap_or("none");
    if status == "reviewed" {
        let has_review_op = history
            .iter()
            .any(|h| h.get("op").and_then(|v| v.as_str()) == Some("review"));
        if !has_review_op {
            report.error(
                "NF-VAL-001",
                "$.history",
                "状态 reviewed 要求 history 含 op=review 记录",
            );
        }
    }
    if status == "reviewed" && review_state != "approved" {
        report.error(
            "NF-VAL-001",
            "$.review.state",
            "状态 reviewed 要求 review.state=approved",
        );
    }
    if review_state == "approved" {
        for field in ["reviewer", "note", "subject_digest"] {
            if review.get(field).is_none() {
                report.error(
                    "NF-VAL-001",
                    &format!("$.review.{field}"),
                    &format!("评审 approved 必须带 {field}（绑定被批对象）"),
                );
            }
        }
    }
    if status == "reviewed" && review.get("subject_digest").is_none() {
        report.error(
            "NF-VAL-001",
            "$.review.subject_digest",
            "评审批准必须绑定 subject_digest，改一处即失效",
        );
    }
    let _ = history;
    report
}

pub fn project_validate(req: &Value) -> OpOutcome {
    let project = req_value(req, "project")?;
    Ok((0, validate_project(project).to_value()))
}
