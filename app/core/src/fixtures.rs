//! 手写最小夹具（无随机、无时间戳）。供 golden-gen 与集成测试共用。

use crate::canonical::{canonical_bytes, sha256_hex};
use crate::error::CoreError;
use crate::fsutil;
use serde_json::{json, Value};
use std::path::Path;

pub fn hex64(ch: char) -> String {
    std::iter::repeat(ch).take(64).collect()
}

pub fn protocol_pack() -> Value {
    json!({
        "schema": "nf-protocol-pack/1",
        "id": "demo-proto",
        "version": "1.0.0",
        "title": "演示协议",
        "proto_version": 1,
        "clauses": [
            {
                "id": "C-001",
                "title": "角色",
                "level": "MUST",
                "text": "角色 {{F-001}} 位于 {{F-002}}。",
                "enabled": true,
                "fields": ["F-001", "F-002"]
            },
            {
                "id": "C-002",
                "title": "基调",
                "level": "SHOULD",
                "text": "基调：{{F-003}}。",
                "enabled": true,
                "fields": ["F-003"]
            }
        ],
        "fields": [
            {"id": "F-001", "clause": "C-001", "label": "角色名", "type": "text", "required": true, "default": "无名"},
            {"id": "F-002", "clause": "C-001", "label": "地点", "type": "text", "required": true},
            {"id": "F-003", "clause": "C-002", "label": "基调", "type": "enum", "required": false, "options": ["冷", "暖"], "default": "冷"}
        ],
        "rules": [
            {"id": "R-001", "expr": {"op": "exists", "field": "F-001"}, "severity": "error", "message": "必须给角色名", "fix": "补 F-001"},
            {"id": "R-002", "expr": {"op": "eq", "args": [{"field": "F-003"}, "冷"]}, "severity": "warn", "message": "基调为冷", "fix": "确认基调"}
        ],
        "examples": [
            {"id": "EX-01", "title": "示例", "keywords": ["角色"], "body": "角色示例正文"}
        ],
        "compat": {"protocol_min": 1, "protocol_max": 2, "app_min": "0.1.0"},
        "migrations": [{"from": 1, "to": 2, "steps": ["声明式迁移，不执行脚本"]}]
    })
}

pub fn graph() -> Value {
    json!({
        "schema": "nf-pipeline-graph/1",
        "id": "demo-graph",
        "version": "1.0.0",
        "title": "演示管线图",
        "mode": "pro",
        "nodes": [
            {"id": "N01", "kind": "stage", "title": "准备", "ports": {"in": [], "out": ["o"]}},
            {"id": "N02", "kind": "module", "title": "设定", "module_ref": {"id": "mod-setting", "version": "1.0.0", "digest": hex64('a')}, "ports": {"in": ["i"], "out": ["o"]}},
            {"id": "N03", "kind": "stage", "title": "生成", "ports": {"in": ["i"], "out": ["o"]}},
            {"id": "N04", "kind": "module", "title": "写作", "module_ref": {"id": "mod-writing"}, "ports": {"in": ["i"], "out": ["o"]}},
            {"id": "N05", "kind": "module", "title": "润色", "module_ref": {"id": "mod-polish"}, "ports": {"in": ["i"], "out": ["o"]}}
        ],
        "edges": [
            {"id": "E01", "from": "N01", "to": "N02", "from_port": "o", "to_port": "i", "type": "control"},
            {"id": "E02", "from": "N02", "to": "N03", "from_port": "o", "to_port": "i", "type": "data"},
            {"id": "E03", "from": "N03", "to": "N04", "from_port": "o", "to_port": "i", "type": "data"},
            {"id": "E04", "from": "N03", "to": "N05", "from_port": "o", "to_port": "i", "type": "data"},
            {"id": "E05", "from": "N04", "to": "N05", "from_port": "o", "to_port": "i", "type": "data"}
        ],
        "weights": {"N02": 30, "N03": 50, "N04": 60, "N05": 40},
        "params": {},
        "settings": {"required_stages": ["N01", "N03"], "seed": 7}
    })
}

pub fn spec() -> Value {
    json!({
        "schema": "nf-md-spec/1",
        "id": "demo-spec",
        "title": "演示规范",
        "domain": "demo",
        "version": "1.0.0",
        "heading_level": 2,
        "sections": [
            {"id": "SEC-01", "title": "开场", "order": 1, "required": true, "slots": ["SLT-01", "SLT-02"]},
            {"id": "SEC-02", "title": "正文", "order": 2, "required": true, "slots": ["SLT-03"]}
        ],
        "slots": [
            {"id": "SLT-01", "name": "角色", "section": "SEC-01", "kind": "text", "required": true, "constraints": [{"op": "min_chars", "value": 1}], "examples": [], "acceptance": ["A-01"], "budget": {"max_chars": 200}},
            {"id": "SLT-02", "name": "地点", "section": "SEC-01", "kind": "text", "required": false, "constraints": [], "examples": [], "acceptance": [], "budget": {"max_chars": 200}},
            {"id": "SLT-03", "name": "正文", "section": "SEC-02", "kind": "code", "required": true, "lang": "text", "constraints": [{"op": "non_empty"}], "examples": [], "acceptance": [], "budget": {"max_chars": 2000}}
        ],
        "constraints": [],
        "acceptance": [{"id": "A-01", "description": "角色名非空", "severity": "error"}],
        "references": [{"kind": "protocol", "ref": "demo-proto", "digest": hex64('b')}]
    })
}

pub fn project() -> Value {
    json!({
        "schema": "nf-project/1",
        "id": "demo-project",
        "title": "演示项目",
        "refs": {
            "base_pack": {"id": "demo-pack", "version": "1.0.0", "tree": hex64('c')},
            "protocol": {"id": "demo-proto", "version": "1.0.0", "digest": hex64('d')},
            "graph": {"id": "demo-graph", "version": "1.0.0", "digest": hex64('1'), "path": "pipeline/demo-graph.json", "sha256": hex64('e')},
            "spec": {"id": "demo-spec", "version": "1.0.0", "digest": hex64('2'), "path": "spec/demo-spec.json", "sha256": hex64('f')},
            "assembly": {"id": "demo-graph", "version": "1.0.0", "digest": hex64('4'), "path": "plan.json", "sha256": hex64('3')}
        },
        "status": "validated",
        "review": {"state": "pending"},
        "history": [{"op": "validate", "digest": hex64('5')}]
    })
}

pub fn overlay(base_tree: &str, pack_id: &str, pack_version: &str) -> Value {
    json!({
        "schema": "nf-overlay/1",
        "base": {"id": pack_id, "version": pack_version, "tree": base_tree},
        "clauses": {
            "C-001": {"enabled": false},
            "C-002": {"enabled": true, "text_sha256": sha256_hex("基调：{{F-003}}。".as_bytes())}
        },
        "params": {"tone": "warm"},
        "presets": [{"id": "preset-a", "name": "预设甲", "graph": hex64('6')}],
        "custom_assets": []
    })
}

pub fn sample_markdown() -> String {
    let fence = "\u{60}".repeat(3);
    [
        "# 演示文档",
        "",
        "第一段说明文字。",
        "",
        "## 小节",
        "",
        "| 列A | 列B |",
        "| --- | --- |",
        "| 1 | 2 |",
        "",
        &format!("{fence}rust"),
        "let x = 1;",
        &fence,
        "",
    ]
    .join("\n")
}

pub fn sample_text() -> String {
    "第一段。\n\n第二段。\n".to_string()
}

pub fn sample_yaml() -> String {
    "# 演示 yaml\nname: demo\nitems:\n  - one\n  - two\nnested:\n  key: value\n".to_string()
}

pub fn write_file(dir: &Path, rel: &str, content: &str) -> Result<(), CoreError> {
    fsutil::write_bytes(
        &dir.join(rel.replace('/', std::path::MAIN_SEPARATOR_STR)),
        content.as_bytes(),
    )
}

/// 写一个最小 pack 目录（先写内容文件，再按 pack-hash 口径写 nf-pack.json）。
pub fn make_pack(
    dir: &Path,
    id: &str,
    version: &str,
    files: &[(String, String)],
) -> Result<Value, CoreError> {
    std::fs::create_dir_all(dir)
        .map_err(|e| CoreError::new("NF-E-004").with_message(format!("建目录失败: {e}")).with_exit(2))?;
    for (rel, content) in files {
        write_file(dir, rel, content)?;
    }
    let computed = fsutil::pack_items(dir, None)?;
    let manifest = json!({
        "schema": "nf-pack/1",
        "id": id,
        "version": version,
        "kind": "base",
        "title": format!("{id} {version}"),
        "items": computed.items,
        "hashes": {"tree": computed.tree, "count": computed.count},
        "requires": [],
        "compat": {"min_app_version": "0.1.0", "schema_version": 1},
    });
    let bytes = canonical_bytes(&manifest)?;
    fsutil::write_bytes(&dir.join("nf-pack.json"), &bytes)?;
    Ok(manifest)
}

pub fn canon_text(value: &Value) -> String {
    String::from_utf8(canonical_bytes(value).expect("canonical")).expect("utf8")
}

pub fn pack_v1_files() -> Vec<(String, String)> {
    vec![
        ("protocol/demo-protocol.json".to_string(), canon_text(&protocol_pack())),
        ("pipeline/demo-graph.json".to_string(), canon_text(&graph())),
        ("spec/demo-spec.json".to_string(), canon_text(&spec())),
        ("docs/old.md".to_string(), "# 旧文档\n".to_string()),
    ]
}

pub fn pack_v2_files() -> Vec<(String, String)> {
    let mut protocol = protocol_pack();
    protocol["clauses"][0]["text"] = Value::String("角色 {{F-001}} 位于 {{F-002}}（v2）。".into());
    vec![
        ("protocol/demo-protocol.json".to_string(), canon_text(&protocol)),
        ("pipeline/demo-graph.json".to_string(), canon_text(&graph())),
        ("spec/demo-spec.json".to_string(), canon_text(&spec())),
        ("docs/new.md".to_string(), "# 新文档\n".to_string()),
    ]
}
