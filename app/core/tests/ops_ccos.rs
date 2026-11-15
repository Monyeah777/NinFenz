//! CCOS 交接：ccos-build-task / ccos-import-result。

#[path = "common/mod.rs"]
mod common;

use common::*;
use nf_app_core::canonical::digest_value;
use nf_app_core::fixtures;
use nf_app_core::schema;
use serde_json::{json, Value};

fn budget() -> Value {
    json!({"max_tokens": 1000, "max_chars": 4000, "max_seconds": 60})
}

fn build(project: &Value) -> Value {
    run_ok(
        "ccos-build-task",
        &json!({
            "project": project,
            "task_id": "demo-task-0001",
            "created_at": "2026-01-01T00:00:00Z",
            "budget": budget(),
            "variables": {"tone": "warm"}
        }),
    )
}

fn result_for(task: &Value, review_state: &str) -> Value {
    json!({
        "schema": "ccos-result/1",
        "task_id": task["id"],
        "task_digest": digest_value(task).unwrap(),
        "status": "succeeded",
        "artifacts": [{
            "name": "result.md",
            "mime": "text/markdown",
            "path": "result.md",
            "sha256": fixtures::hex64('7'),
            "bytes": 10
        }],
        "evidence": [{"kind": "log", "ref": "run.log", "digest": fixtures::hex64('8')}],
        "report": {"summary": "ok", "issues": []},
        "provenance": {
            "engine": "ccos",
            "started_at": "2026-01-01T00:00:00Z",
            "finished_at": "2026-01-01T00:01:00Z"
        },
        "human_review": {"required": true, "state": review_state}
    })
}

#[test]
fn build_task_shape_and_refs() {
    let task = build(&fixtures::project());
    assert_eq!(schema::validate("ccos-task", &task).len(), 0);
    assert_eq!(task["schema"], "ccos-task/1");
    assert_eq!(task["id"], "demo-task-0001");
    assert_eq!(task["created_at"], "2026-01-01T00:00:00Z");
    assert_eq!(task["pack"]["id"], "demo-pack");
    assert_eq!(task["protocol"]["id"], "demo-proto");
    assert_eq!(task["pipeline"]["id"], "demo-graph");
    assert_eq!(task["pipeline"]["version"], "1.0.0");
    assert_eq!(task["md_spec"]["id"], "demo-spec");
    assert_eq!(task["policy"]["network"], false);
    assert_eq!(task["policy"]["secrets"], "ccos-only");
    assert_eq!(task["provenance"]["project_id"], "demo-project");
    assert_eq!(task["provenance"]["app_version"], "0.1.0");
    assert_eq!(task["provenance"]["project_digest"].as_str().unwrap().len(), 64);
}

#[test]
fn build_task_requires_validated_status() {
    let mut project = fixtures::project();
    project["status"] = json!("draft");
    let env = run_err(
        "ccos-build-task",
        &json!({
            "project": project,
            "task_id": "demo-task-0001",
            "created_at": "2026-01-01T00:00:00Z",
            "budget": budget()
        }),
        1,
        "NF-CCOS-001",
    );
    assert_eq!(env.result.unwrap()["verdict"], "fail");
}

#[test]
fn build_task_rejects_secret_variables() {
    let env = dispatch(
        "ccos-build-task",
        &json!({
            "project": fixtures::project(),
            "task_id": "demo-task-0001",
            "created_at": "2026-01-01T00:00:00Z",
            "budget": budget(),
            "variables": {"api_key": "sk-xxx"}
        }),
    );
    assert_eq!(env.exit, 3);
    assert_eq!(env.error.as_ref().unwrap()["code"], "NF-CCOS-003");
}

#[test]
fn build_task_rejects_absolute_path_variable() {
    let env = dispatch(
        "ccos-build-task",
        &json!({
            "project": fixtures::project(),
            "task_id": "demo-task-0001",
            "created_at": "2026-01-01T00:00:00Z",
            "budget": budget(),
            "variables": {"path": "D:/secret/x.txt"}
        }),
    );
    assert_eq!(env.exit, 3);
    assert_eq!(env.error.as_ref().unwrap()["code"], "NF-CCOS-003");
}

#[test]
fn build_task_created_at_must_be_rfc3339() {
    let env = dispatch(
        "ccos-build-task",
        &json!({
            "project": fixtures::project(),
            "task_id": "demo-task-0001",
            "created_at": "2026-01-01",
            "budget": budget()
        }),
    );
    assert_eq!(env.exit, 1);
    assert_eq!(env.error.as_ref().unwrap()["code"], "NF-CCOS-001");
}

#[test]
fn import_result_pending_review_warns_exit0() {
    let task = build(&fixtures::project());
    let result = result_for(&task, "pending");
    let r = run_ok("ccos-import-result", &json!({"task": task, "result": result}));
    assert_eq!(r["status"], "succeeded");
    assert_eq!(r["review"]["state"], "pending");
    assert!(r["issues"]
        .as_array()
        .unwrap()
        .iter()
        .any(|i| i["code"] == "NF-CCOS-004" && i["severity"] == "warn"));
}

#[test]
fn import_result_approved_has_no_review_issue() {
    let task = build(&fixtures::project());
    let result = result_for(&task, "approved");
    let r = run_ok("ccos-import-result", &json!({"task": task, "result": result}));
    assert_eq!(r["review"]["state"], "approved");
    assert_eq!(r["issues"].as_array().unwrap().len(), 0);
}

#[test]
fn import_result_digest_mismatch_is_exit1() {
    let task = build(&fixtures::project());
    let mut result = result_for(&task, "approved");
    result["task_digest"] = json!(fixtures::hex64('0'));
    let env = run_err("ccos-import-result", &json!({"task": task, "result": result}), 1, "NF-CCOS-002");
    assert_eq!(env.result.unwrap()["verdict"], "fail");
}

#[test]
fn import_result_task_id_mismatch_is_exit1() {
    let task = build(&fixtures::project());
    let mut result = result_for(&task, "approved");
    result["task_id"] = json!("other-task-0001");
    run_err("ccos-import-result", &json!({"task": task, "result": result}), 1, "NF-CCOS-002");
}

#[test]
fn import_result_unsafe_artifact_path_is_exit1() {
    let task = build(&fixtures::project());
    let mut result = result_for(&task, "approved");
    result["artifacts"][0]["path"] = json!("../escape/result.md");
    let env = run_err("ccos-import-result", &json!({"task": task, "result": result}), 1, "NF-CCOS-001");
    assert_eq!(env.result.unwrap()["verdict"], "fail");
}

#[test]
fn import_result_absolute_artifact_path_rejected() {
    let task = build(&fixtures::project());
    let mut result = result_for(&task, "approved");
    result["artifacts"][0]["path"] = json!("D:/abs/result.md");
    let env = dispatch("ccos-import-result", &json!({"task": task, "result": result}));
    assert_eq!(env.exit, 3);
    assert_eq!(env.error.as_ref().unwrap()["code"], "NF-CCOS-003");
}

#[test]
fn import_result_secret_rejected_exit3() {
    let task = build(&fixtures::project());
    let mut result = result_for(&task, "approved");
    result["report"]["summary"] = json!("token sk-abc123");
    let env = dispatch("ccos-import-result", &json!({"task": task, "result": result}));
    assert_eq!(env.exit, 3);
    assert_eq!(env.error.as_ref().unwrap()["code"], "NF-CCOS-003");
}
