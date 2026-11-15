//! 扩展口（计划 §17）单测：默认行为 + 未知输入 fail-closed。

use nf_app_core::ext::{
    builtin_adapters, Adapter, AllEnabled, BatchRunner, BuiltinAdapter, DslParser, FeatureGate,
    InMemoryTraceRecorder, LocalDirPublisher, NoopTraceRecorder, PackPublisher, Plugin,
    PluginRegistry, Provider, TraceEvent, TraceRecorder, UnconfiguredProvider,
};
use nf_app_core::fixtures;
use serde_json::{json, Value};
use std::path::PathBuf;

fn tmpdir(tag: &str) -> PathBuf {
    let dir = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("target")
        .join("nf-ext-test")
        .join(tag);
    let _ = std::fs::remove_dir_all(&dir);
    std::fs::create_dir_all(&dir).unwrap();
    dir
}

#[test]
fn adapter_registry_and_markdown_extract() {
    let adapters = builtin_adapters();
    assert_eq!(adapters.len(), 7);
    let names: Vec<&str> = adapters.iter().map(|a| a.format()).collect();
    assert!(names.contains(&"markdown"));
    assert!(names.contains(&"nfpack"));
    let md = BuiltinAdapter::new("markdown");
    let conf = md
        .sniff("doc.md", None, Some(fixtures::sample_markdown().as_bytes()))
        .expect("markdown 应被识别");
    assert!(conf >= 85);
    let draft = md.extract(fixtures::sample_markdown().as_bytes()).unwrap();
    assert_eq!(draft.structure.headings.len(), 2);
    assert!(draft.text.unwrap().contains("第一段"));
}

#[test]
fn adapter_unknown_format_fail_closed() {
    let fake = BuiltinAdapter::new("ocr");
    let err = fake.extract(b"x").unwrap_err();
    assert_eq!(err.code, "NF-IMP-004");
    assert_eq!(err.exit, 3);
    assert_eq!(fake.sniff("x.bin", None, None), None);
}

#[test]
fn pack_publisher_local_dir_roundtrip() {
    let src = tmpdir("pub_src");
    let dst = tmpdir("pub_dst");
    fixtures::make_pack(
        &src,
        "pub-pack",
        "1.0.0",
        &[("a.txt".to_string(), "a".to_string())],
    )
    .unwrap();
    let publisher = LocalDirPublisher::new(dst.clone());
    let (result, tree) = nf_app_core::ext::publisher_manifest(&publisher, &src).unwrap();
    assert_eq!(result["items"], 1);
    assert_eq!(tree.len(), 64);
    assert!(dst.join("a.txt").is_file());
    let src_tree = nf_app_core::fsutil::pack_items(&src, None).unwrap().tree;
    assert_eq!(tree, src_tree);
}

#[test]
fn provider_default_is_not_configured() {
    let provider = UnconfiguredProvider;
    assert_eq!(provider.name(), "unconfigured");
    assert!(provider.supports(&json!({"schema": "ccos-task/1"})));
    let err = provider.execute(&json!({})).unwrap_err();
    assert_eq!(err.code, "NF-E-005");
    assert_eq!(err.exit, 4);
}

#[test]
fn feature_gate_default_all_enabled() {
    let gate = AllEnabled;
    assert!(gate.enabled("assemble"));
    assert!(gate.enabled("not-a-feature"));
}

#[test]
fn trace_recorder_noop_and_memory() {
    let mut noop = NoopTraceRecorder;
    noop.record(TraceEvent {
        step: "s1".into(),
        elapsed_ms: 1,
        detail: None,
    });
    assert!(noop.events().is_empty());
    let mut mem = InMemoryTraceRecorder::default();
    mem.record(TraceEvent {
        step: "a".into(),
        elapsed_ms: 1,
        detail: None,
    });
    mem.record(TraceEvent {
        step: "b".into(),
        elapsed_ms: 2,
        detail: Some("x".into()),
    });
    assert_eq!(mem.events().len(), 2);
    assert_eq!(mem.events()[1].elapsed_ms, 2);
}

#[test]
fn dsl_parser_accepts_whitelist_and_rejects_unknown() {
    let expr = json!({"op": "and", "args": [
        {"op": "exists", "field": "F-001"},
        {"op": "eq", "args": [{"field": "F-002"}, "x"]}
    ]});
    let parsed = DslParser::parse_rule(&expr).unwrap();
    assert_eq!(parsed, expr);
    let err = DslParser::parse_rule(&json!({"op": "eval", "value": 1})).unwrap_err();
    assert_eq!(err.code, "NF-PRT-005");
    let nested = json!({"op": "not", "args": [{"op": "exec", "field": "F-001"}]});
    assert_eq!(
        DslParser::parse_rule(&nested).unwrap_err().code,
        "NF-PRT-005"
    );
    let bad_args = json!({"op": "and", "args": "nope"});
    assert_eq!(
        DslParser::parse_rule(&bad_args).unwrap_err().code,
        "NF-PRT-005"
    );
}

#[test]
fn batch_runner_aggregates_errors() {
    let items = vec![json!(1), json!(2), json!(3)];
    let outcome = BatchRunner::run(&items, |i, v| {
        if i == 1 {
            Err(nf_app_core::error::CoreError::new("NF-E-003").with_exit(2))
        } else {
            Ok(v.as_i64().unwrap() * 2)
        }
    });
    assert_eq!(outcome.results.len(), 3);
    assert_eq!(outcome.succeeded(), 2);
    assert_eq!(outcome.failed(), 1);
    assert_eq!(outcome.errors(), vec![(1, "NF-E-003".to_string())]);
    assert_eq!(outcome.results[2].1.as_ref().unwrap(), &6);
}

struct EchoPlugin;

impl Plugin for EchoPlugin {
    fn name(&self) -> &'static str {
        "echo"
    }
    fn call(&self, request: &Value) -> Result<Value, nf_app_core::error::CoreError> {
        Ok(json!({"echo": request}))
    }
}

#[test]
fn plugin_registry_rejects_unregistered() {
    let mut registry = PluginRegistry::default();
    let err = registry.call("echo", &json!({})).unwrap_err();
    assert_eq!(err.code, "NF-E-002");
    assert_eq!(err.exit, 3);
    registry.register(Box::new(EchoPlugin));
    assert_eq!(registry.names(), vec!["echo"]);
    let out = registry.call("echo", &json!({"a": 1})).unwrap();
    assert_eq!(out["echo"]["a"], 1);
}
