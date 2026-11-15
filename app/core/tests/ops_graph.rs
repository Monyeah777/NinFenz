//! 管线图：graph-validate（L0+L1）/ graph-compile（拓扑序与 digest）。

#[path = "common/mod.rs"]
mod common;

use common::*;
use nf_app_core::canonical::digest_with_excludes;
use nf_app_core::fixtures;
use nf_app_core::schema;
use serde_json::{json, Value};

#[test]
fn graph_validate_fixture_passes() {
    let r = run_ok("graph-validate", &json!({"graph": fixtures::graph()}));
    assert_eq!(r["verdict"], "pass");
    assert_eq!(r["target"]["kind"], "pipeline-graph");
    assert_eq!(r["target"]["ref"], "demo-graph");
    assert_eq!(r["summary"]["error"], 0);
}

#[test]
fn graph_validate_cycle_detected() {
    let mut graph = fixtures::graph();
    graph["edges"].as_array_mut().unwrap().push(json!({
        "id": "E99", "from": "N05", "to": "N02", "from_port": "o", "to_port": "i", "type": "data"
    }));
    let env = run_err("graph-validate", &json!({"graph": graph}), 1, "NF-GRF-004");
    assert!(env.result.unwrap()["issues"]
        .as_array()
        .unwrap()
        .iter()
        .any(|i| i["code"] == "NF-GRF-004"));
}

#[test]
fn graph_validate_duplicate_node_id() {
    let mut graph = fixtures::graph();
    graph["nodes"].as_array_mut().unwrap().push(json!({
        "id": "N01", "kind": "stage", "title": "重复", "ports": {"in": [], "out": []}
    }));
    let env = run_err("graph-validate", &json!({"graph": graph}), 1, "NF-GRF-002");
    assert_eq!(env.result.unwrap()["verdict"], "fail");
}

#[test]
fn graph_validate_bad_port() {
    let mut graph = fixtures::graph();
    graph["edges"][0]["from_port"] = json!("nope");
    let env = run_err("graph-validate", &json!({"graph": graph}), 1, "NF-GRF-003");
    assert!(env.result.unwrap()["issues"]
        .as_array()
        .unwrap()
        .iter()
        .any(|i| i["code"] == "NF-GRF-003"));
}

#[test]
fn graph_validate_required_stage_missing() {
    let mut graph = fixtures::graph();
    graph["settings"]["required_stages"] = json!(["N01", "N99"]);
    let env = run_err("graph-validate", &json!({"graph": graph}), 1, "NF-GRF-005");
    assert_eq!(env.result.unwrap()["verdict"], "fail");
}

#[test]
fn graph_validate_simple_mode_forbids_branch() {
    let mut graph = fixtures::graph();
    graph["mode"] = json!("simple");
    graph["nodes"].as_array_mut().unwrap().push(json!({
        "id": "N09", "kind": "branch", "title": "分支", "ports": {"in": ["i"], "out": ["a", "b"]}
    }));
    graph["edges"].as_array_mut().unwrap().push(json!({
        "id": "E90", "from": "N03", "to": "N09", "from_port": "o", "to_port": "i", "type": "data"
    }));
    let env = run_err("graph-validate", &json!({"graph": graph}), 1, "NF-GRF-006");
    assert!(env.result.unwrap()["issues"]
        .as_array()
        .unwrap()
        .iter()
        .any(|i| i["code"] == "NF-GRF-006"));
}

#[test]
fn graph_validate_weight_on_illegal_node() {
    let mut graph = fixtures::graph();
    graph["nodes"].as_array_mut().unwrap().push(json!({
        "id": "N07", "kind": "gate", "title": "门", "ports": {"in": ["i"], "out": ["o"]}
    }));
    graph["edges"].as_array_mut().unwrap().push(json!({
        "id": "E91", "from": "N05", "to": "N07", "from_port": "o", "to_port": "i", "type": "data"
    }));
    graph["weights"]["N07"] = json!(10);
    let env = run_err("graph-validate", &json!({"graph": graph}), 1, "NF-GRF-007");
    assert!(env.result.unwrap()["issues"]
        .as_array()
        .unwrap()
        .iter()
        .any(|i| i["code"] == "NF-GRF-007"));
}

#[test]
fn graph_compile_plan_shape_and_topo_order() {
    let r = run_ok(
        "graph-compile",
        &json!({"graph": fixtures::graph(), "spec": fixtures::spec()}),
    );
    assert_eq!(r["schema"], "nf-assembly-plan/1");
    let steps = r["steps"].as_array().unwrap();
    assert_eq!(steps.len(), 3);
    let ids: Vec<&str> = steps.iter().map(|s| s["id"].as_str().unwrap()).collect();
    assert_eq!(ids, vec!["S01", "S02", "S03"]);
    let nodes: Vec<&str> = steps.iter().map(|s| s["node"].as_str().unwrap()).collect();
    assert_eq!(nodes, vec!["N02", "N04", "N05"]);
    assert_eq!(steps[0]["stage"], "N01");
    assert_eq!(steps[1]["stage"], "N03");
    assert_eq!(steps[2]["stage"], "N03");
    assert_eq!(steps[0]["module"], "mod-setting");
    assert_eq!(steps[0]["weight"], 30);
    assert_eq!(steps[2]["inputs"], json!(["o"]));
    assert_eq!(r["slots"], json!(["SLT-01", "SLT-02", "SLT-03"]));
    assert_eq!(r["modules"].as_array().unwrap().len(), 3);
    assert_eq!(r["output"]["form"], "md");
    assert_eq!(r["settings"]["seed"], 7);
    assert_eq!(r["pipeline"]["id"], "demo-graph");
    assert_eq!(r["pipeline"]["version"], "1.0.0");
}

#[test]
fn graph_compile_digest_verifies() {
    let r = run_ok(
        "graph-compile",
        &json!({"graph": fixtures::graph(), "spec": fixtures::spec()}),
    );
    assert_eq!(schema::validate("nf-assembly-plan", &r).len(), 0);
    let declared = r["digest"].as_str().unwrap();
    let actual = digest_with_excludes(&r, &["digest".to_string()]).unwrap();
    assert_eq!(declared, actual);
}

#[test]
fn graph_compile_tie_break_is_code_point_order() {
    // 两个 module 同时就绪且插入顺序是 N07 在前：Kahn 按 id 码点序应取 N06 先。
    let graph = json!({
        "schema": "nf-pipeline-graph/1",
        "id": "tie-graph",
        "version": "1.0.0",
        "mode": "pro",
        "nodes": [
            {"id": "N01", "kind": "stage", "title": "S", "ports": {"in": [], "out": ["o"]}},
            {"id": "N07", "kind": "module", "title": "M7", "module_ref": {"id": "mod-7"}, "ports": {"in": ["i"], "out": []}},
            {"id": "N06", "kind": "module", "title": "M6", "module_ref": {"id": "mod-6"}, "ports": {"in": ["i"], "out": []}}
        ],
        "edges": [
            {"id": "E01", "from": "N01", "to": "N07", "from_port": "o", "to_port": "i", "type": "data"},
            {"id": "E02", "from": "N01", "to": "N06", "from_port": "o", "to_port": "i", "type": "data"}
        ],
        "weights": {},
        "params": {},
        "settings": {"required_stages": ["N01"]}
    });
    let r = run_ok("graph-compile", &json!({"graph": graph}));
    let nodes: Vec<&str> = r["steps"]
        .as_array()
        .unwrap()
        .iter()
        .map(|s| s["node"].as_str().unwrap())
        .collect();
    assert_eq!(nodes, vec!["N06", "N07"]);
}

#[test]
fn graph_compile_invalid_graph_is_report() {
    let mut graph = fixtures::graph();
    graph["edges"][0]["to"] = json!("N99");
    let env = run_err("graph-compile", &json!({"graph": graph}), 1, "NF-GRF-003");
    assert_eq!(env.result.unwrap()["verdict"], "fail");
}

#[test]
fn graph_compile_deterministic_twice() {
    let req = json!({"graph": fixtures::graph(), "spec": fixtures::spec()});
    let one = canon(&run_ok("graph-compile", &req));
    let two = canon(&run_ok("graph-compile", &req));
    assert_eq!(one, two);
}

#[test]
fn graph_validate_unreachable_node() {
    let mut graph = fixtures::graph();
    graph["nodes"].as_array_mut().unwrap().push(json!({
        "id": "N08", "kind": "module", "title": "孤岛", "module_ref": {"id": "mod-orphan"},
        "ports": {"in": ["i"], "out": ["o"]}
    }));
    let env = run_err("graph-validate", &json!({"graph": graph}), 1, "NF-GRF-005");
    let report: Value = env.result.unwrap();
    assert!(report["issues"]
        .as_array()
        .unwrap()
        .iter()
        .any(|i| i["code"] == "NF-GRF-005"));
}
#[test]
fn graph_compile_module_without_upstream_stage_is_error() {
    // 入口是 module（无上游 stage）：合法 DAG，但模块所属阶段不可推导 → NF-GRF-005
    let graph = json!({
        "schema": "nf-pipeline-graph/1",
        "id": "no-stage-upstream",
        "version": "1.0.0",
        "mode": "pro",
        "nodes": [
            {"id": "N01", "kind": "module", "title": "M1", "module_ref": {"id": "mod-1"}, "ports": {"in": [], "out": ["o"]}},
            {"id": "N02", "kind": "stage", "title": "S", "ports": {"in": ["i"], "out": ["o"]}},
            {"id": "N03", "kind": "module", "title": "M3", "module_ref": {"id": "mod-3"}, "ports": {"in": ["i"], "out": []}}
        ],
        "edges": [
            {"id": "E01", "from": "N01", "to": "N02", "from_port": "o", "to_port": "i", "type": "data"},
            {"id": "E02", "from": "N02", "to": "N03", "from_port": "o", "to_port": "i", "type": "data"}
        ],
        "weights": {},
        "params": {},
        "settings": {"required_stages": ["N02"]}
    });
    let env = run_err("graph-compile", &json!({"graph": graph}), 1, "NF-GRF-005");
    assert_eq!(env.result.unwrap()["verdict"], "fail");
}
