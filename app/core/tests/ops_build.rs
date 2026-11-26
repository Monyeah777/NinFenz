use serde_json::{json, Value};

mod common;
use common::run_ok;

fn graph(key: &str, sha: &str) -> Value {
    json!({
        "schema": "nf-build-graph/1",
        "plan_sha": sha,
        "environment": {
            "core_version": "0.1.0",
            "schema_version": "nf-sdir/1+nf-build-graph/1",
            "font_hashes": [],
            "locale": "und",
            "fixed_mtime": "1980-01-01T00:00:00Z"
        },
        "nodes": [
            {"id": "in:0", "kind": "input", "input_hashes": [], "cache_key": key},
            {"id": "t:0", "kind": "transform", "op": "render:md", "input_hashes": [key], "cache_key": key}
        ],
        "edges": [{"from": "in:0", "to": "t:0", "port": "sdir"}],
        "outputs": [{"node": "t:0", "path": "result.md", "sha256": sha, "bytes": 10, "format": "md"}]
    })
}

#[test]
fn build_journal_validates_fixture() {
    let journal: Value = serde_json::from_str(include_str!("../../fixtures/schema/valid/nf-build/journal.json")).unwrap();
    let out = run_ok("build-journal", &json!({"journal": journal}));
    assert_eq!(out["schema"], "nf-build/1");
    assert_eq!(out["verdict"], "unverified");
}

#[test]
fn build_why_explains_cache_key_change() {
    let a = "a".repeat(64);
    let b = "b".repeat(64);
    let out = run_ok("build-why", &json!({"old_graph": graph(&a, &a), "new_graph": graph(&b, &b)}));
    assert_eq!(out["schema"], "nf-build-why/1");
    assert_eq!(out["rebuild"], json!(["result.md"]));
    assert!(out["reasons"].as_array().unwrap().iter().any(|r| r["reason"] == "cache-key"));
}
