use nf_app_core::canonical::digest_value;
use serde_json::{json, Value};

mod common;
use common::{dispatch, run_ok};

fn seal(mut value: Value) -> Value {
    value.as_object_mut().unwrap().remove("digest");
    let digest = digest_value(&value).unwrap();
    value.as_object_mut().unwrap().insert("digest".into(), json!(digest));
    value
}

fn fragment(id: &str, text: &str, digest: Option<&str>) -> Value {
    seal(json!({
        "schema": "nf-fragment/1",
        "id": id,
        "title": id,
        "kind": "section",
        "blocks": [{"id": "b1", "type": "paragraph", "text": text}],
        "slots": [],
        "tags": [],
        "digest": digest.unwrap_or("")
    }))
}

fn composition(roots: Vec<&str>, fragments: &[Value]) -> Value {
    let refs: Vec<Value> = fragments.iter().map(|f| json!({"id": f["id"], "digest": f["digest"]})).collect();
    seal(json!({
        "schema": "nf-composition/1",
        "id": "demo",
        "roots": roots,
        "fragments": refs,
        "digest": ""
    }))
}

#[test]
fn renders_placeholders_conditions_and_each() {
    let f = fragment("opening", "{{#if tone=dark}}暗{{/if}}{{#each rows}}{{name}};{{/each}}你好 {{SLT-01}}", None);
    let c = composition(vec!["opening"], &[f.clone()]);
    let out = run_ok("compose-render", &json!({
        "composition": c,
        "fragments": [f],
        "values": {"tone": "dark", "SLT-01": "林某", "rows": [{"name": "A"}, {"name": "B"}]}
    }));
    assert_eq!(out["schema"], "nf-compose-result/1");
    assert_eq!(out["markdown"], "暗A;B;你好 林某
");
    assert_eq!(out["fragments"], 1);
}

#[test]
fn rejects_missing_fragment_and_digest_mismatch() {
    let f = fragment("opening", "x", None);
    let mut c = composition(vec!["opening"], &[f.clone()]);
    c["fragments"][0]["digest"] = json!("b".repeat(64));
    let env = dispatch("compose-validate", &json!({"composition": c, "fragments": [f]}));
    assert_eq!(env.exit, 1);
    assert_eq!(env.error.unwrap()["code"], "NF-CMP-002");
}

#[test]
fn rejects_cycles() {
    let a = fragment("fa", "{{>fb}}", None);
    let b = fragment("fb", "{{>fa}}", None);
    let c = composition(vec!["fa"], &[a.clone(), b.clone()]);
    let env = dispatch("compose-validate", &json!({"composition": c, "fragments": [a, b]}));
    assert_eq!(env.exit, 1);
    assert_eq!(env.error.unwrap()["code"], "NF-CMP-002");
}
