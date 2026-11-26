use serde_json::json;

mod common;
use common::{dispatch, run_ok};

#[test]
fn adds_verifies_and_chains_sources() {
    let a = run_ok("source-add", &json!({"title": "A", "text": "alpha", "fetched_at": 1}));
    let b = run_ok("source-add", &json!({"title": "B", "text": "beta", "fetched_at": 2}));
    assert_eq!(a["schema"], "nf-source/1");
    assert_eq!(a["status"], "unverified");
    run_ok("source-verify", &json!({"source": a}));
    let chain = run_ok("source-chain-build", &json!({"sources": [a, b]}));
    assert_eq!(chain["schema"], "nf-source-chain/1");
    assert_eq!(chain["entries"][0]["prev"], "");
    assert_eq!(chain["entries"][1]["prev"], chain["entries"][0]["sha256"]);
    let report = run_ok("source-chain-verify", &json!({"chain": chain}));
    assert_eq!(report["ok"], true);
    assert_eq!(report["entries"], 2);
}

#[test]
fn tampered_chain_reports_break() {
    let a = run_ok("source-add", &json!({"title": "A", "text": "alpha", "fetched_at": 1}));
    let b = run_ok("source-add", &json!({"title": "B", "text": "beta", "fetched_at": 2}));
    let mut chain = run_ok("source-chain-build", &json!({"sources": [a, b]}));
    chain["entries"][1]["prev"] = json!("b".repeat(64));
    let env = dispatch("source-chain-verify", &json!({"chain": chain}));
    assert_eq!(env.exit, 1);
    assert_eq!(env.result.unwrap()["ok"], false);
}
