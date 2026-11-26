use serde_json::json;

mod common;
use common::{dispatch, run_ok};

#[test]
fn plans_queued_tasks_without_network() {
    let run = run_ok("ai-plan", &json!({
        "project_id": "p1",
        "sections": [{"title": "开场"}, {"title": "推进"}, {"title": "收束"}],
        "model": "ccos-task",
        "seed": 7
    }));
    assert_eq!(run["schema"], "nf-ai-run/1");
    assert_eq!(run["status"], "queued");
    assert_eq!(run["tasks"].as_array().unwrap().len(), 3);
    assert_eq!(run["usage"]["input_tokens"], 0);
    run_ok("ai-run-verify", &json!({"run": run}));
}

#[test]
fn rejects_nested_secret_fields() {
    let mut run = run_ok("ai-plan", &json!({"project_id": "p1", "sections": ["a"]}));
    run["params"] = json!({"nested": {"token": "x"}});
    let env = dispatch("ai-run-verify", &json!({"run": run}));
    assert_eq!(env.exit, 3);
    assert_eq!(env.error.unwrap()["code"], "NF-AI-002");
}
