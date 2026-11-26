use serde_json::json;

mod common;
use common::run_ok;

fn spec() -> serde_json::Value {
    json!({
        "schema": "nf-md-spec/1",
        "id": "demo-spec",
        "title": "Demo",
        "domain": "demo",
        "version": "0.1.0",
        "heading_level": 2,
        "sections": [{"id": "SEC-01", "title": "开场", "order": 1, "required": true, "slots": ["SLT-01"]}],
        "slots": [{
            "id": "SLT-01",
            "name": "主角",
            "section": "SEC-01",
            "kind": "text",
            "required": true,
            "constraints": [{"op": "non_empty"}, {"op": "min_chars", "value": 2}],
            "examples": ["林"],
            "acceptance": ["A-01"],
            "budget": {"max_chars": 40}
        }],
        "constraints": [],
        "acceptance": [{"id": "A-01", "description": "非空", "severity": "error"}],
        "references": [],
        "budget": {"max_total_chars": 40}
    })
}

#[test]
fn compile_makes_deterministic_ir_and_links_field() {
    let protocol = json!({
        "schema": "nf-protocol-pack/1",
        "id": "demo-protocol",
        "version": "0.1.0",
        "clauses": [],
        "fields": [{"id": "F-001", "label": "主角", "type": "text", "required": true, "default": "无名"}],
        "rules": [],
        "examples": [],
        "compat": {},
        "migrations": []
    });
    let req = json!({"spec": spec(), "protocol": protocol});
    let first = run_ok("contract-compile", &req);
    let second = run_ok("contract-compile", &req);
    assert_eq!(first["digest"], second["digest"]);
    assert_eq!(first["slots"][0]["protocol_field"], "F-001");
    assert_eq!(first["slots"][0]["default"], "无名");
    assert_eq!(first["schema"], "nf-contract-ir/1");
    assert!(first["source"].get("protocol_digest").is_some());
}

#[test]
fn compile_without_protocol_has_no_null_digest() {
    let ir = run_ok("contract-compile", &json!({"spec": spec()}));
    assert!(ir["source"].get("protocol_digest").is_none(), "{ir}");
}

#[test]
fn solve_reports_required_and_too_short() {
    let ir = run_ok("contract-compile", &json!({"spec": spec()}));
    let empty = run_ok("contract-solve", &json!({"contract": ir, "values": {"SLT-01": ""}}));
    assert_eq!(empty["satisfiable"], false);
    assert!(empty["unsat_core"].as_array().unwrap().iter().any(|v| v == "SLT-01"));
    assert!(empty["issues"].as_array().unwrap().iter().any(|i| i["code"] == "NF-CON-002"));

    let short = run_ok("contract-solve", &json!({"contract": ir, "values": {"SLT-01": "a"}}));
    assert_eq!(short["satisfiable"], false);

    let good = run_ok("contract-solve", &json!({"contract": ir, "values": {"SLT-01": "林某"}}));
    assert_eq!(good["satisfiable"], true, "{good}");
    let explained = run_ok("contract-explain", &json!({"result": good}));
    assert!(explained["lines"].as_array().unwrap().iter().any(|v| v.as_str().unwrap_or("").contains("可满足")));
}
