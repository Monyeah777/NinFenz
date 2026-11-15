//! 导入/嗅探/映射：import-sniff / import / map-suggest。

#[path = "common/mod.rs"]
mod common;

use common::*;
use nf_app_core::fixtures;
use nf_app_core::zipsec;
use serde_json::json;

#[test]
fn sniff_markdown_by_extension_and_content() {
    let r = run_ok("import-sniff", &json!({"name": "note.md"}));
    assert_eq!(r["format"], "markdown");
    assert!(r["confidence"].as_u64().unwrap() >= 80);
    let cands = r["candidates"].as_array().unwrap();
    assert!(!cands.is_empty());
    assert_eq!(cands[0]["format"], "markdown");
}

#[test]
fn sniff_text_content_medium_confidence() {
    let dir = tmpdir("sniff_text");
    let p = write_file(&dir, "blob.dat", "hello world\nsecond line\n");
    let r = run_ok("import-sniff", &json!({"name": "blob.dat", "file": pstr(&p)}));
    assert_eq!(r["format"], "text");
    assert!(r["confidence"].as_u64().unwrap() < 60);
}

#[test]
fn sniff_unknown_format_fails() {
    let dir = tmpdir("sniff_unknown");
    let p = write_file(&dir, "blob.qqq", "");
    run_err(
        "import-sniff",
        &json!({"name": "blob.qqq", "file": pstr(&p)}),
        3,
        "NF-IMP-001",
    );
}

#[test]
fn sniff_zip_pack_detection() {
    let dir = tmpdir("sniff_nfpack");
    let entries = vec![
        ("nf-pack.json".to_string(), b"{}".to_vec()),
        ("a.txt".to_string(), b"a".to_vec()),
    ];
    let bytes = zipsec::zip_bytes(&entries).unwrap();
    let p = dir.join("sample.nfpack");
    std::fs::write(&p, &bytes).unwrap();
    let r = run_ok("import-sniff", &json!({"name": "sample.nfpack", "file": pstr(&p)}));
    assert_eq!(r["format"], "nfpack");
    assert_eq!(r["confidence"], 100);
}

#[test]
fn sniff_docx_is_unimplemented_adapter() {
    let dir = tmpdir("sniff_docx");
    let entries = vec![
        ("[Content_Types].xml".to_string(), b"<x/>".to_vec()),
        ("word/document.xml".to_string(), b"<y/>".to_vec()),
    ];
    let bytes = zipsec::zip_bytes(&entries).unwrap();
    let p = dir.join("sample.docx");
    std::fs::write(&p, &bytes).unwrap();
    run_err(
        "import-sniff",
        &json!({"name": "sample.docx", "file": pstr(&p)}),
        3,
        "NF-IMP-004",
    );
}

#[test]
fn import_markdown_structure() {
    let dir = tmpdir("import_md");
    let p = write_file(&dir, "doc.md", &fixtures::sample_markdown());
    let r = run_ok(
        "import",
        &json!({"file": pstr(&p), "source": {"kind": "file", "name": "doc.md"}}),
    );
    assert_eq!(r["schema"], "nf-import/1");
    assert_eq!(r["detected"]["format"], "markdown");
    assert_eq!(r["source"]["name"], "doc.md");
    assert_eq!(r["source"]["kind"], "file");
    assert_eq!(r["source"]["sha256"].as_str().unwrap().len(), 64);
    assert_eq!(r["structure"]["headings"].as_array().unwrap().len(), 2);
    assert_eq!(r["structure"]["headings"][0]["level"], 1);
    assert_eq!(r["structure"]["code_blocks"].as_array().unwrap().len(), 1);
    assert_eq!(r["structure"]["code_blocks"][0]["lang"], "rust");
    assert_eq!(r["structure"]["tables"].as_array().unwrap().len(), 1);
    assert_eq!(r["structure"]["tables"][0]["columns"], 2);
    assert_eq!(r["structure"]["tables"][0]["rows"], 1);
    assert!(r["text"].as_str().unwrap().contains("第一段"));
    assert_eq!(r["text_digest"].as_str().unwrap().len(), 64);
    assert_eq!(r["assets"].as_array().unwrap().len(), 0);
}

#[test]
fn import_text_low_confidence_warns_exit0() {
    let dir = tmpdir("import_text_low");
    let p = write_file(&dir, "blob.dat", "hello\n\nworld\n");
    let env = dispatch("import", &json!({"file": pstr(&p), "source": {"kind": "file", "name": "blob.dat"}}));
    assert_eq!(env.exit, 0);
    let r = env.result.unwrap();
    assert_eq!(r["structure"]["paragraphs"], 2);
    let warnings = r["warnings"].as_array().unwrap();
    assert!(warnings.iter().any(|w| w["code"] == "NF-IMP-002"));
}

#[test]
fn import_yaml_minimal_subset() {
    let dir = tmpdir("import_yaml");
    let p = write_file(&dir, "doc.yaml", &fixtures::sample_yaml());
    let r = run_ok("import", &json!({"file": pstr(&p), "source": {"kind": "file", "name": "doc.yaml"}}));
    assert_eq!(r["detected"]["format"], "yaml");
    assert_eq!(r["structure"]["paragraphs"], 3);
    assert!(r["text"].as_str().unwrap().contains("name: demo"));
}

#[test]
fn import_yaml_alias_rejected() {
    let dir = tmpdir("import_yaml_alias");
    let p = write_file(
        &dir,
        "doc.yaml",
        "a: &anchor value\nb: *anchor\n",
    );
    run_err(
        "import",
        &json!({"file": pstr(&p), "source": {"kind": "file", "name": "doc.yaml"}}),
        3,
        "NF-SEC-004",
    );
}

#[test]
fn import_json_structure() {
    let dir = tmpdir("import_json");
    let p = write_file(&dir, "doc.json", "{\"a\":1,\"b\":[1,2]}\n");
    let r = run_ok("import", &json!({"file": pstr(&p), "source": {"kind": "file", "name": "doc.json"}}));
    assert_eq!(r["detected"]["format"], "json");
    assert_eq!(r["structure"]["paragraphs"], 1);
    assert_eq!(r["text"].as_str().unwrap(), "{\"a\":1,\"b\":[1,2]}\n");
}

#[test]
fn import_zip_assets() {
    let dir = tmpdir("import_zip");
    let entries = vec![
        ("b.txt".to_string(), b"b".to_vec()),
        ("a.txt".to_string(), b"aa".to_vec()),
    ];
    let bytes = zipsec::zip_bytes(&entries).unwrap();
    let p = dir.join("sample.zip");
    std::fs::write(&p, &bytes).unwrap();
    let r = run_ok("import", &json!({"file": pstr(&p), "source": {"kind": "file", "name": "sample.zip"}}));
    assert_eq!(r["detected"]["format"], "zip");
    let assets = r["assets"].as_array().unwrap();
    assert_eq!(assets.len(), 2);
    assert_eq!(assets[0]["path"], "a.txt");
    assert_eq!(assets[0]["size"], 2);
    assert!(r.get("text").is_none());
}

#[test]
fn import_unsupported_html_fails_closed() {
    let dir = tmpdir("import_html");
    let p = write_file(&dir, "index.html", "<!DOCTYPE html><html></html>");
    run_err(
        "import",
        &json!({"file": pstr(&p), "source": {"kind": "file", "name": "index.html"}}),
        3,
        "NF-IMP-004",
    );
}

#[test]
fn import_invalid_source_kind_is_validation_report() {
    let dir = tmpdir("import_badsource");
    let p = write_file(&dir, "doc.md", "# t\n");
    let env = dispatch(
        "import",
        &json!({"file": pstr(&p), "source": {"kind": "bogus", "name": "doc.md"}}),
    );
    assert_eq!(env.exit, 1);
    assert_eq!(env.error.as_ref().unwrap()["code"], "NF-IMP-001");
    assert_eq!(env.result.as_ref().unwrap()["verdict"], "fail");
}

#[test]
fn map_suggest_with_spec() {
    let dir = tmpdir("map_spec");
    // 追加第三个标题：spec 只有两个 section，第三个应进 unmapped
    let mut md = fixtures::sample_markdown();
    md.push_str("\n# 额外第三节\n\n内容。\n");
    let p = write_file(&dir, "doc.md", &md);
    let import = run_ok(
        "import",
        &json!({"file": pstr(&p), "source": {"kind": "file", "name": "doc.md"}}),
    );
    let r = run_ok(
        "map-suggest",
        &json!({"import": import, "spec": fixtures::spec()}),
    );
    let mappings = r["suggested"]["mappings"].as_array().unwrap();
    assert!(!mappings.is_empty());
    assert!(mappings
        .iter()
        .all(|m| m["confidence"].is_i64() || m["confidence"].is_u64()));
    assert!(mappings.iter().any(|m| m["to_kind"] == "section"));
    let unmapped = r["suggested"]["unmapped"].as_array().unwrap();
    assert!(unmapped.iter().any(|u| u.as_str().unwrap().starts_with("heading[")));
}

#[test]
fn map_suggest_without_spec_generates_draft_ids() {
    let dir = tmpdir("map_nospec");
    let p = write_file(&dir, "doc.md", &fixtures::sample_markdown());
    let import = run_ok(
        "import",
        &json!({"file": pstr(&p), "source": {"kind": "file", "name": "doc.md"}}),
    );
    let r = run_ok("map-suggest", &json!({"import": import}));
    let mappings = r["suggested"]["mappings"].as_array().unwrap();
    assert!(mappings.iter().any(|m| m["to_id"] == "SEC-01"));
    assert!(mappings.iter().all(|m| m["confidence"].as_u64().unwrap() <= 100));
}

#[test]
fn map_suggest_no_candidates_is_warn_exit0() {
    let dir = tmpdir("map_empty");
    let p = write_file(&dir, "empty.txt", "");
    let import = run_ok(
        "import",
        &json!({"file": pstr(&p), "source": {"kind": "file", "name": "empty.txt"}}),
    );
    let env = dispatch("map-suggest", &json!({"import": import}));
    assert_eq!(env.exit, 0);
    let r = env.result.unwrap();
    assert!(r["warnings"]
        .as_array()
        .unwrap()
        .iter()
        .any(|w| w["code"] == "NF-MAP-001"));
    assert_eq!(r["suggested"]["mappings"].as_array().unwrap().len(), 0);
}

#[test]
fn map_suggest_invalid_import_is_report() {
    let env = dispatch("map-suggest", &json!({"import": {"schema": "nf-import/1"}}));
    assert_eq!(env.exit, 1);
    assert_eq!(env.result.as_ref().unwrap()["verdict"], "fail");
}