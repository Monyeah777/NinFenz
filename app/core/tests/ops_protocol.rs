//! 协议：protocol-validate / protocol-render（占位符 + 规则 DSL）。

#[path = "common/mod.rs"]
mod common;

use common::*;
use nf_app_core::fixtures;
use serde_json::{json, Value};

fn clause_text(r: &Value, index: usize) -> String {
    r["clauses"][index]["text"].as_str().unwrap().to_string()
}

#[test]
fn protocol_validate_fixture_passes() {
    let r = run_ok("protocol-validate", &json!({"pack": fixtures::protocol_pack()}));
    assert_eq!(r["schema"], "nf-validate-report/1");
    assert_eq!(r["verdict"], "pass");
    assert_eq!(r["target"]["kind"], "protocol-pack");
    assert_eq!(r["target"]["ref"], "demo-proto");
    assert_eq!(r["summary"]["error"], 0);
}

#[test]
fn protocol_validate_duplicate_field_id() {
    let mut pack = fixtures::protocol_pack();
    pack["fields"].as_array_mut().unwrap().push(json!({
        "id": "F-001", "clause": "C-001", "label": "重复", "type": "text", "required": false
    }));
    let env = run_err("protocol-validate", &json!({"pack": pack}), 1, "NF-PRT-002");
    assert_eq!(env.result.unwrap()["verdict"], "fail");
}

#[test]
fn protocol_validate_unknown_placeholder() {
    let mut pack = fixtures::protocol_pack();
    pack["clauses"][0]["text"] = json!("角色 {{F-999}}。");
    let env = run_err("protocol-validate", &json!({"pack": pack}), 1, "NF-PRT-004");
    assert!(env.result.unwrap()["issues"]
        .as_array()
        .unwrap()
        .iter()
        .any(|i| i["code"] == "NF-PRT-004"));
}

#[test]
fn protocol_validate_unknown_rule_op() {
    let mut pack = fixtures::protocol_pack();
    pack["rules"][0]["expr"] = json!({"op": "eval", "value": "x"});
    let env = run_err("protocol-validate", &json!({"pack": pack}), 1, "NF-PRT-005");
    assert!(env.result.unwrap()["issues"]
        .as_array()
        .unwrap()
        .iter()
        .any(|i| i["code"] == "NF-PRT-005"));
}

#[test]
fn protocol_render_success() {
    let r = run_ok(
        "protocol-render",
        &json!({
            "pack": fixtures::protocol_pack(),
            "values": {"F-001": "法师", "F-002": "塔", "F-003": "冷"}
        }),
    );
    let clauses = r["clauses"].as_array().unwrap();
    assert_eq!(clauses.len(), 2);
    assert_eq!(clauses[0]["id"], "C-001");
    assert_eq!(clause_text(&r, 0), "角色 法师 位于 塔。");
    assert_eq!(clause_text(&r, 1), "基调：冷。");
    assert_eq!(r["warnings"].as_array().unwrap().len(), 0);
}

#[test]
fn protocol_render_missing_required_is_exit1() {
    let env = run_err(
        "protocol-render",
        &json!({"pack": fixtures::protocol_pack(), "values": {"F-001": "法师"}}),
        1,
        "NF-PRT-003",
    );
    assert_eq!(env.result.unwrap()["verdict"], "fail");
}

#[test]
fn protocol_render_unknown_placeholder_is_exit1() {
    let mut pack = fixtures::protocol_pack();
    pack["clauses"][0]["text"] = json!("角色 {{F-404}}。");
    run_err(
        "protocol-render",
        &json!({"pack": pack, "values": {"F-001": "a", "F-002": "b"}}),
        1,
        "NF-PRT-004",
    );
}

#[test]
fn protocol_render_rule_violation_is_exit1() {
    let mut pack = fixtures::protocol_pack();
    pack["rules"] = json!([
        {"id": "R-009", "expr": {"op": "eq", "args": [{"field": "F-003"}, "暖"]}, "severity": "error", "message": "必须是暖调", "fix": "改基调"}
    ]);
    let env = run_err(
        "protocol-render",
        &json!({"pack": pack, "values": {"F-001": "a", "F-002": "b", "F-003": "冷"}}),
        1,
        "NF-PRT-005",
    );
    assert!(env.result.unwrap()["issues"]
        .as_array()
        .unwrap()
        .iter()
        .any(|i| i["code"] == "NF-PRT-005"));
}

#[test]
fn protocol_render_warn_rule_goes_to_warnings() {
    let mut pack = fixtures::protocol_pack();
    pack["rules"] = json!([
        {"id": "R-009", "expr": {"op": "eq", "args": [{"field": "F-003"}, "暖"]}, "severity": "warn", "message": "非暖调", "fix": "确认"}
    ]);
    let r = run_ok(
        "protocol-render",
        &json!({"pack": pack, "values": {"F-001": "a", "F-002": "b", "F-003": "冷"}}),
    );
    assert_eq!(r["warnings"].as_array().unwrap().len(), 1);
    assert_eq!(r["warnings"][0]["severity"], "warn");
}

#[test]
fn protocol_render_default_applies_for_optional_field() {
    let r = run_ok(
        "protocol-render",
        &json!({"pack": fixtures::protocol_pack(), "values": {"F-001": "a", "F-002": "b"}}),
    );
    assert_eq!(clause_text(&r, 1), "基调：冷。");
}

#[test]
fn protocol_render_compat_range_rejects_exit3() {
    let mut pack = fixtures::protocol_pack();
    pack["proto_version"] = json!(3);
    run_err(
        "protocol-render",
        &json!({"pack": pack, "values": {}}),
        3,
        "NF-PRT-006",
    );
}

#[test]
fn protocol_validate_compat_range_reports_exit1() {
    let mut pack = fixtures::protocol_pack();
    pack["proto_version"] = json!(3);
    let env = run_err("protocol-validate", &json!({"pack": pack}), 1, "NF-PRT-006");
    assert!(env.result.unwrap()["issues"]
        .as_array()
        .unwrap()
        .iter()
        .any(|i| i["code"] == "NF-PRT-006"));
}

#[test]
fn protocol_render_type_mismatch_is_exit3() {
    let env = dispatch(
        "protocol-render",
        &json!({
            "pack": fixtures::protocol_pack(),
            "values": {"F-001": {"nested": true}, "F-002": "b"}
        }),
    );
    assert_eq!(env.exit, 3);
    assert_eq!(env.error.as_ref().unwrap()["code"], "NF-PRT-005");
}

#[test]
fn protocol_validate_dangling_field_clause() {
    let mut pack = fixtures::protocol_pack();
    pack["fields"][0]["clause"] = json!("C-999");
    let env = run_err("protocol-validate", &json!({"pack": pack}), 1, "NF-PRT-001");
    assert!(env.result.unwrap()["issues"]
        .as_array()
        .unwrap()
        .iter()
        .any(|i| i["code"] == "NF-PRT-001"));
}
