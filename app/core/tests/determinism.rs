//! 确定性：同一请求两次运行 → 响应信封逐字节一致（NFR-DET）。

#[path = "common/mod.rs"]
mod common;

use common::*;
use nf_app_core::canonical::canonical_bytes;
use nf_app_core::fixtures;
use serde_json::{json, Value};

fn twice(op: &str, req: &Value) -> (Vec<u8>, Vec<u8>) {
    let one = dispatch(op, req);
    let two = dispatch(op, req);
    let a = canonical_bytes(&one.to_value()).unwrap();
    let b = canonical_bytes(&two.to_value()).unwrap();
    (a, b)
}

#[test]
fn deterministic_ops() {
    let dir = tmpdir("det_files");
    let md = write_file(&dir, "doc.md", &fixtures::sample_markdown());
    let import = run_ok(
        "import",
        &json!({"file": pstr(&md), "source": {"kind": "file", "name": "doc.md"}}),
    );
    let plan = run_ok(
        "graph-compile",
        &json!({"graph": fixtures::graph(), "spec": fixtures::spec()}),
    );
    let asm = run_ok(
        "assemble",
        &json!({"plan": plan, "spec": fixtures::spec(), "inputs": {"SLT-01": "a", "SLT-02": "b", "SLT-03": "c"}}),
    );
    let cases: Vec<(&str, Value)> = vec![
        ("canonical", json!({"value": {"b": [1, 2, {"z": "中", "a": "é"}], "a": 1}})),
        ("pack-hash", json!({"root": pstr(&dir)})),
        ("import-sniff", json!({"name": "doc.md", "file": pstr(&md)})),
        ("import", json!({"file": pstr(&md), "source": {"kind": "file", "name": "doc.md"}})),
        ("map-suggest", json!({"import": import, "spec": fixtures::spec()})),
        ("protocol-validate", json!({"pack": fixtures::protocol_pack()})),
        ("protocol-render", json!({"pack": fixtures::protocol_pack(), "values": {"F-001": "a", "F-002": "b"}})),
        ("graph-validate", json!({"graph": fixtures::graph()})),
        ("graph-compile", json!({"graph": fixtures::graph(), "spec": fixtures::spec()})),
        ("spec-validate", json!({"spec": fixtures::spec()})),
        ("assemble", json!({"plan": plan, "spec": fixtures::spec(), "inputs": {"SLT-01": "a", "SLT-02": "b", "SLT-03": "c"}})),
        ("validate", json!({"markdown": asm["markdown"], "spec": fixtures::spec(), "plan": plan, "level": "L1"})),
        ("ccos-build-task", json!({
            "project": fixtures::project(),
            "task_id": "demo-task-0001",
            "created_at": "2026-01-01T00:00:00Z",
            "budget": {"max_tokens": 1, "max_chars": 1, "max_seconds": 1}
        })),
        ("project-validate", json!({"project": fixtures::project()})),
    ];
    for (op, req) in cases {
        let (a, b) = twice(op, &req);
        assert_eq!(a, b, "{op} 两次响应不一致");
        assert!(!a.is_empty(), "{op} 响应为空");
    }
}

#[test]
fn deterministic_export_zip_bytes() {
    let dir1 = tmpdir("det_zip1");
    let dir2 = tmpdir("det_zip2");
    let req1 = json!({
        "result": {"markdown": "# x\n", "meta": {"schema": "m", "digest": fixtures::hex64('a')}},
        "format": "zip",
        "out_dir": pstr(&dir1)
    });
    let mut req2 = req1.clone();
    req2["out_dir"] = json!(pstr(&dir2));
    let r1 = run_ok("export", &req1);
    let r2 = run_ok("export", &req2);
    assert_eq!(r1["files"][0]["sha256"], r2["files"][0]["sha256"]);
    assert_eq!(
        std::fs::read(dir1.join("result.zip")).unwrap(),
        std::fs::read(dir2.join("result.zip")).unwrap()
    );
}

#[test]
fn reports_have_no_timestamps() {
    let r = run_ok("spec-validate", &json!({"spec": fixtures::spec()}));
    let text = canon(&r);
    for needle in ["\"at\"", "created_at", "timestamp", "T00:00:00"] {
        assert!(!text.contains(needle), "报告不应含时间戳字段 {needle}");
    }
}