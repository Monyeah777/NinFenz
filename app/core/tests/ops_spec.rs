//! MD spec：spec-validate（order/双向一致/约束/acceptance）。

#[path = "common/mod.rs"]
mod common;

use common::*;
use nf_app_core::fixtures;
use serde_json::json;

#[test]
fn spec_validate_fixture_passes() {
    let r = run_ok("spec-validate", &json!({"spec": fixtures::spec()}));
    assert_eq!(r["verdict"], "pass");
    assert_eq!(r["target"]["kind"], "md-spec");
    assert_eq!(r["target"]["ref"], "demo-spec");
    assert_eq!(r["summary"]["error"], 0);
}

#[test]
fn spec_validate_order_duplicate() {
    let mut spec = fixtures::spec();
    spec["sections"][1]["order"] = json!(1);
    let env = run_err("spec-validate", &json!({"spec": spec}), 1, "NF-SPC-003");
    assert!(env.result.unwrap()["issues"]
        .as_array()
        .unwrap()
        .iter()
        .any(|i| i["code"] == "NF-SPC-003"));
}

#[test]
fn spec_validate_bidirectional_mismatch() {
    let mut spec = fixtures::spec();
    spec["sections"][0]["slots"] = json!(["SLT-01"]);
    let env = run_err("spec-validate", &json!({"spec": spec}), 1, "NF-SPC-002");
    assert_eq!(env.result.unwrap()["verdict"], "fail");
}

#[test]
fn spec_validate_duplicate_acceptance() {
    let mut spec = fixtures::spec();
    spec["acceptance"]
        .as_array_mut()
        .unwrap()
        .push(json!({"id": "A-01", "description": "重复", "severity": "warn"}));
    let env = run_err("spec-validate", &json!({"spec": spec}), 1, "NF-SPC-005");
    assert!(env.result.unwrap()["issues"]
        .as_array()
        .unwrap()
        .iter()
        .any(|i| i["code"] == "NF-SPC-005"));
}

#[test]
fn spec_validate_min_gt_max() {
    let mut spec = fixtures::spec();
    spec["slots"][0]["constraints"] = json!([
        {"op": "min_chars", "value": 50},
        {"op": "max_chars", "value": 10}
    ]);
    let env = run_err("spec-validate", &json!({"spec": spec}), 1, "NF-SPC-003");
    assert!(env.result.unwrap()["issues"]
        .as_array()
        .unwrap()
        .iter()
        .any(|i| i["code"] == "NF-SPC-003"));
}

#[test]
fn spec_validate_bad_pattern() {
    let mut spec = fixtures::spec();
    spec["slots"][0]["constraints"] = json!([{"op": "pattern", "value": "("}]);
    let env = run_err("spec-validate", &json!({"spec": spec}), 1, "NF-SPC-003");
    assert!(env.result.unwrap()["issues"]
        .as_array()
        .unwrap()
        .iter()
        .any(|i| i["code"] == "NF-SPC-003"));
}

#[test]
fn spec_validate_unknown_acceptance_ref() {
    let mut spec = fixtures::spec();
    spec["slots"][0]["acceptance"] = json!(["A-99"]);
    let env = run_err("spec-validate", &json!({"spec": spec}), 1, "NF-SPC-002");
    assert!(env.result.unwrap()["issues"]
        .as_array()
        .unwrap()
        .iter()
        .any(|i| i["code"] == "NF-SPC-002"));
}

#[test]
fn spec_validate_schema_violation() {
    let mut spec = fixtures::spec();
    spec["slots"][0]["kind"] = json!("unknown-kind");
    let env = run_err("spec-validate", &json!({"spec": spec}), 1, "NF-SPC-001");
    assert_eq!(env.result.unwrap()["verdict"], "fail");
}

#[test]
fn spec_validate_deterministic_report() {
    let spec = fixtures::spec();
    let one = canon(&run_ok("spec-validate", &json!({"spec": spec.clone()})));
    let two = canon(&run_ok("spec-validate", &json!({"spec": spec})));
    assert_eq!(one, two);
}
#[test]
fn spec_validate_budget_within_limits_passes() {
    let mut spec = fixtures::spec();
    spec["budget"] = json!({"max_total_chars": 5000, "max_total_tokens": 1000});
    let r = run_ok("spec-validate", &json!({"spec": spec}));
    assert_eq!(r["verdict"], "pass");
    assert_eq!(nf_app_core::schema::validate("nf-md-spec", &fixtures::spec()).len(), 0);
}

#[test]
fn spec_validate_budget_chars_exceeded() {
    let mut spec = fixtures::spec();
    spec["budget"] = json!({"max_total_chars": 10});
    let env = run_err("spec-validate", &json!({"spec": spec}), 1, "NF-SPC-004");
    assert!(env.result.unwrap()["issues"]
        .as_array()
        .unwrap()
        .iter()
        .any(|i| i["code"] == "NF-SPC-004"));
}

#[test]
fn spec_validate_budget_tokens_exceeded() {
    let mut spec = fixtures::spec();
    spec["slots"][0]["budget"] = json!({"max_chars": 100, "max_tokens": 500});
    spec["slots"][2]["budget"] = json!({"max_chars": 100, "max_tokens": 500});
    spec["budget"] = json!({"max_total_tokens": 100});
    run_err("spec-validate", &json!({"spec": spec}), 1, "NF-SPC-004");
}

#[test]
fn spec_validate_without_budget_does_not_judge_total() {
    let mut spec = fixtures::spec();
    spec["slots"][0]["budget"] = json!({"max_chars": 1000000, "max_tokens": 1000000});
    let r = run_ok("spec-validate", &json!({"spec": spec}));
    assert_eq!(r["verdict"], "pass");
}
