use serde_json::json;

mod common;
use common::{dispatch, run_ok};

fn macro_value() -> serde_json::Value {
    json!({
        "schema": "nf-macro/1",
        "id": "demo-macro",
        "title": "demo",
        "steps": [
            {"id": "S01", "action": "import", "params": {}},
            {"id": "S02", "action": "assemble", "params": {}},
            {"id": "S03", "action": "export", "params": {"format": "md"}}
        ],
        "digest": "a".repeat(64)
    })
}

#[test]
fn validates_and_plans_dry_run() {
    let checked = run_ok("macro-validate", &json!({"macro": macro_value()}));
    assert_eq!(checked["schema"], "nf-macro-report/1");
    let plan = run_ok("macro-plan", &json!({"macro": macro_value()}));
    assert_eq!(plan["schema"], "nf-macro-plan/1");
    assert_eq!(plan["dry_run"], true);
    assert_eq!(plan["writes"], json!([]));
    assert_eq!(plan["steps"].as_array().unwrap().len(), 3);
}

#[test]
fn rejects_duplicate_step_ids() {
    let mut value = macro_value();
    value["steps"][2]["id"] = json!("S01");
    let env = dispatch("macro-validate", &json!({"macro": value}));
    assert_eq!(env.exit, 1);
    assert_eq!(env.error.unwrap()["code"], "NF-MAC-001");
}
