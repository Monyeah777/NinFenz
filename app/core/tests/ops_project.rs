//! 项目校验：refs 形状 / 状态机 / 评审绑定 / digest 剔除 history。

#[path = "common/mod.rs"]
mod common;

use common::*;
use nf_app_core::fixtures;
use serde_json::json;

#[test]
fn project_validate_fixture_passes() {
    let r = run_ok("project-validate", &json!({"project": fixtures::project()}));
    assert_eq!(r["verdict"], "pass");
    assert_eq!(r["target"]["kind"], "project");
    assert_eq!(r["target"]["ref"], "demo-project");
    assert_eq!(r["summary"]["error"], 0);
}

#[test]
fn project_validate_requires_assembly_after_assembled() {
    let mut project = fixtures::project();
    project["refs"]
        .as_object_mut()
        .unwrap()
        .remove("assembly");
    let env = run_err("project-validate", &json!({"project": project}), 1, "NF-VAL-001");
    assert_eq!(env.result.unwrap()["verdict"], "fail");
}

#[test]
fn project_validate_assembly_needs_five_fields() {
    let mut project = fixtures::project();
    project["refs"]["assembly"] = json!({"id": "demo-graph", "version": "1.0.0", "digest": fixtures::hex64('4')});
    run_err("project-validate", &json!({"project": project}), 1, "NF-VAL-001");
}

#[test]
fn project_validate_reviewed_requires_approved() {
    let mut project = fixtures::project();
    project["status"] = json!("reviewed");
    project["review"] = json!({"state": "pending"});
    project["history"] = json!([
        {"op": "validate", "digest": fixtures::hex64('5')},
        {"op": "export", "digest": fixtures::hex64('6')}
    ]);
    run_err("project-validate", &json!({"project": project}), 1, "NF-VAL-001");
}

#[test]
fn project_validate_approved_requires_binding_fields() {
    let mut project = fixtures::project();
    project["review"] = json!({"state": "approved"});
    let env = run_err("project-validate", &json!({"project": project}), 1, "NF-VAL-001");
    assert!(env.result.unwrap()["issues"]
        .as_array()
        .unwrap()
        .iter()
        .any(|i| i["path"].as_str().unwrap().contains("review.reviewer")));
}

#[test]
fn project_validate_schema_violation() {
    let mut project = fixtures::project();
    project["id"] = json!("Bad_ID");
    run_err("project-validate", &json!({"project": project}), 1, "NF-VAL-001");
}

#[test]
fn project_target_digest_excludes_history() {
    let one = run_ok("project-validate", &json!({"project": fixtures::project()}));
    let mut project = fixtures::project();
    project["history"]
        .as_array_mut()
        .unwrap()
        .push(json!({"op": "rollback", "at": "2026-01-01T00:00:00Z", "digest": fixtures::hex64('9')}));
    let two = run_ok("project-validate", &json!({"project": project}));
    assert_eq!(one["target"]["digest"], two["target"]["digest"]);
}
#[test]
fn project_validate_reviewed_with_review_and_export_history_passes() {
    let mut project = fixtures::project();
    project["status"] = json!("reviewed");
    project["review"] = json!({
        "state": "approved",
        "reviewer": "lead",
        "note": "通过",
        "subject_digest": fixtures::hex64('a')
    });
    project["history"] = json!([
        {"op": "validate", "digest": fixtures::hex64('5')},
        {"op": "export", "digest": fixtures::hex64('6')},
        {"op": "review", "digest": fixtures::hex64('7')}
    ]);
    let r = run_ok("project-validate", &json!({"project": project}));
    assert_eq!(r["verdict"], "pass");
}

#[test]
fn project_validate_reviewed_missing_review_op_fails() {
    let mut project = fixtures::project();
    project["status"] = json!("reviewed");
    project["review"] = json!({
        "state": "approved",
        "reviewer": "lead",
        "note": "通过",
        "subject_digest": fixtures::hex64('a')
    });
    project["history"] = json!([
        {"op": "validate", "digest": fixtures::hex64('5')},
        {"op": "export", "digest": fixtures::hex64('6')}
    ]);
    run_err("project-validate", &json!({"project": project}), 1, "NF-VAL-001");
}
