//! 装配与校验：assemble / validate（L0/L1/L2）。

#[path = "common/mod.rs"]
mod common;

use common::*;
use nf_app_core::canonical::{canonical_bytes, sha256_hex};
use nf_app_core::fixtures;
use serde_json::json;

fn plan() -> serde_json::Value {
    run_ok(
        "graph-compile",
        &json!({"graph": fixtures::graph(), "spec": fixtures::spec()}),
    )
}

fn inputs_full() -> serde_json::Value {
    json!({"SLT-01": "法师", "SLT-02": "塔", "SLT-03": "正文内容。"})
}

#[test]
fn assemble_success_and_meta() {
    let plan = plan();
    let r = run_ok(
        "assemble",
        &json!({"plan": plan, "spec": fixtures::spec(), "inputs": inputs_full()}),
    );
    let markdown = r["markdown"].as_str().unwrap();
    assert!(markdown.starts_with("## 开场\n"));
    assert!(markdown.contains("法师"));
    assert!(markdown.contains("## 正文"));
    assert!(markdown.ends_with('\n'));
    let meta = &r["meta"];
    assert_eq!(meta["schema"], "nf-assemble-result/1");
    assert_eq!(meta["plan_digest"], plan["digest"]);
    assert_eq!(meta["spec_digest"].as_str().unwrap().len(), 64);
    assert_eq!(
        meta["markdown_digest"].as_str().unwrap(),
        sha256_hex(markdown.as_bytes())
    );
    assert_eq!(meta["slots"].as_array().unwrap().len(), 3);
    assert_eq!(meta["slots"][0]["id"], "SLT-01");
    assert_eq!(meta["slots"][0]["section"], "SEC-01");
    assert_eq!(meta["slots"][0]["chars"], 2);
    assert_eq!(meta["slots"][1]["chars"], 1);
    assert!(meta["slots"][2]["chars"].as_u64().unwrap() > 0);
    assert_eq!(meta["missing"].as_array().unwrap().len(), 0);
    assert_eq!(nf_app_core::schema::validate("nf-assemble-result", meta).len(), 0);
}

#[test]
fn assemble_missing_required_slot_is_exit1() {
    let plan = plan();
    let env = run_err(
        "assemble",
        &json!({"plan": plan, "spec": fixtures::spec(), "inputs": {"SLT-02": "塔", "SLT-03": "x"}}),
        1,
        "NF-ASM-002",
    );
    assert_eq!(env.result.unwrap()["verdict"], "fail");
}

#[test]
fn assemble_plan_digest_mismatch_is_exit1() {
    let mut plan = plan();
    plan["digest"] = json!(fixtures::hex64('0'));
    run_err(
        "assemble",
        &json!({"plan": plan, "spec": fixtures::spec(), "inputs": inputs_full()}),
        1,
        "NF-ASM-001",
    );
}

#[test]
fn assemble_plan_schema_violation_is_exit1() {
    let mut plan = plan();
    plan["steps"] = json!([]);
    run_err(
        "assemble",
        &json!({"plan": plan, "spec": fixtures::spec(), "inputs": inputs_full()}),
        1,
        "NF-ASM-003",
    );
}

#[test]
fn assemble_block_replaces_section_preserving_other_bytes() {
    let plan = plan();
    let spec = fixtures::spec();
    let full = run_ok(
        "assemble",
        &json!({"plan": plan, "spec": spec, "inputs": inputs_full()}),
    );
    let base = format!(
        "# 前置自定义字节：保留我\n\n{}",
        full["markdown"].as_str().unwrap()
    );
    let r = run_ok(
        "assemble",
        &json!({
            "plan": plan,
            "spec": spec,
            "inputs": {"SLT-01": "法师", "SLT-02": "塔", "SLT-03": "替换后的正文。"},
            "block": "SEC-02",
            "base_markdown": base,
        }),
    );
    let markdown = r["markdown"].as_str().unwrap();
    assert!(markdown.contains("## 开场"));
    assert!(markdown.contains("法师"));
    assert!(markdown.contains("替换后的正文。"));
    assert!(markdown.starts_with("# 前置自定义字节：保留我\n\n"));
    assert_eq!(r["meta"]["block"], "SEC-02");
    assert_eq!(r["meta"]["markdown_digest"], sha256_hex(markdown.as_bytes()));
    let slots = r["meta"]["slots"].as_array().unwrap();
    assert_eq!(slots.len(), 3);
    assert_eq!(slots[0]["chars"], 0);
    assert!(slots[2]["chars"].as_u64().unwrap() > 0);
    assert_eq!(nf_app_core::schema::validate("nf-assemble-result", &r["meta"]).len(), 0);
}

#[test]
fn assemble_block_requires_base_markdown() {
    let plan = plan();
    run_err(
        "assemble",
        &json!({"plan": plan, "spec": fixtures::spec(), "inputs": inputs_full(), "block": "SEC-02"}),
        1,
        "NF-ASM-004",
    );
}

#[test]
fn assemble_block_section_absent_in_base_is_exit1() {
    let plan = plan();
    run_err(
        "assemble",
        &json!({
            "plan": plan,
            "spec": fixtures::spec(),
            "inputs": inputs_full(),
            "block": "SEC-02",
            "base_markdown": "# 别的文档\n\n没有目标节\n",
        }),
        1,
        "NF-ASM-004",
    );
}

#[test]
fn assemble_unknown_stage_is_exit1() {
    let plan = plan();
    run_err(
        "assemble",
        &json!({"plan": plan, "spec": fixtures::spec(), "inputs": inputs_full(), "stage": "N99"}),
        1,
        "NF-ASM-003",
    );
}

#[test]
fn assemble_known_stage_ok() {
    let plan = plan();
    let r = run_ok(
        "assemble",
        &json!({"plan": plan, "spec": fixtures::spec(), "inputs": inputs_full(), "stage": "N03"}),
    );
    assert_eq!(r["meta"]["stage"], "N03");
}

#[test]
fn assemble_writes_out_dir() {
    let plan = plan();
    let out = tmpdir("asm_out");
    let r = run_ok(
        "assemble",
        &json!({"plan": plan, "spec": fixtures::spec(), "inputs": inputs_full(), "out_dir": pstr(&out)}),
    );
    let md = std::fs::read_to_string(out.join("result.md")).unwrap();
    assert_eq!(md, r["markdown"].as_str().unwrap());
    let meta_bytes = std::fs::read(out.join("result.meta.json")).unwrap();
    assert_eq!(meta_bytes, canonical_bytes(&r["meta"]).unwrap());
}

#[test]
fn validate_l0_pass() {
    let plan = plan();
    let spec = fixtures::spec();
    let asm = run_ok(
        "assemble",
        &json!({"plan": plan, "spec": spec, "inputs": inputs_full()}),
    );
    let r = run_ok(
        "validate",
        &json!({"markdown": asm["markdown"], "spec": spec, "plan": plan, "level": "L0"}),
    );
    assert_eq!(r["verdict"], "pass");
    assert_eq!(r["level"], "L0");
    assert_eq!(r["target"]["kind"], "assembly");
    assert_eq!(r["summary"]["error"], 0);
}

#[test]
fn validate_l1_pass_with_acceptance_info() {
    let plan = plan();
    let spec = fixtures::spec();
    let asm = run_ok(
        "assemble",
        &json!({"plan": plan, "spec": spec, "inputs": inputs_full()}),
    );
    let r = run_ok(
        "validate",
        &json!({"markdown": asm["markdown"], "spec": spec, "plan": plan, "level": "L1"}),
    );
    assert_eq!(r["verdict"], "pass");
    assert_eq!(r["summary"]["error"], 0);
    assert!(r["issues"]
        .as_array()
        .unwrap()
        .iter()
        .any(|i| i["severity"] == "info" && i["message"].as_str().unwrap().contains("A-01")));
}

#[test]
fn validate_l1_constraint_failure() {
    let plan = plan();
    let spec = fixtures::spec();
    let markdown = "## 开场\n\n法师\n\n塔\n\n## 正文\n\n";
    let env = run_err(
        "validate",
        &json!({"markdown": markdown, "spec": spec, "plan": plan, "level": "L1"}),
        1,
        "NF-VAL-002",
    );
    assert_eq!(env.result.unwrap()["verdict"], "fail");
}

#[test]
fn validate_l0_missing_heading_fails() {
    let plan = plan();
    let spec = fixtures::spec();
    let env = run_err(
        "validate",
        &json!({"markdown": "# 只有一级标题\n", "spec": spec, "plan": plan, "level": "L0"}),
        1,
        "NF-VAL-001",
    );
    assert_eq!(env.result.unwrap()["verdict"], "fail");
}

#[test]
fn validate_l2_unavailable_is_exit4() {
    std::env::remove_var("NF_APP_L2_CMD");
    let plan = plan();
    let spec = fixtures::spec();
    let asm = run_ok(
        "assemble",
        &json!({"plan": plan, "spec": spec, "inputs": inputs_full()}),
    );
    let env = dispatch(
        "validate",
        &json!({"markdown": asm["markdown"], "spec": spec, "plan": plan, "level": "L2"}),
    );
    assert_eq!(env.exit, 4);
    assert_eq!(env.error.as_ref().unwrap()["code"], "NF-VAL-005");
}

#[test]
fn assemble_deterministic() {
    let req = json!({"plan": plan(), "spec": fixtures::spec(), "inputs": inputs_full()});
    let one = canon(&run_ok("assemble", &req));
    let two = canon(&run_ok("assemble", &req));
    assert_eq!(one, two);
}