//! 导出：md / zip / json（确定性 zip）/ 越界与重名。

#[path = "common/mod.rs"]
mod common;

use common::*;
use nf_app_core::canonical::canonical_bytes;
use nf_app_core::zipsec;
use serde_json::json;

#[test]
fn export_md_writes_file_and_manifest() {
    let out = tmpdir("exp_md");
    let r = run_ok(
        "export",
        &json!({"markdown": "# 标题\n正文\n", "format": "md", "out_dir": pstr(&out), "manifest": true}),
    );
    assert_eq!(r["schema"], "nf-export-manifest/1");
    assert_eq!(r["format"], "md");
    let files = r["files"].as_array().unwrap();
    assert_eq!(files.len(), 1);
    assert_eq!(files[0]["name"], "result.md");
    let bytes = std::fs::read(out.join("result.md")).unwrap();
    assert_eq!(bytes, "# 标题\n正文\n".as_bytes());
    assert_eq!(files[0]["bytes"], bytes.len());
    assert_eq!(
        r["source"]["markdown_digest"],
        nf_app_core::canonical::sha256_hex(&bytes)
    );
    assert_eq!(r["source"]["plan_digest"].as_str().unwrap().len(), 64);
    assert_eq!(nf_app_core::schema::validate("nf-export-manifest", &r).len(), 0);
    assert!(out.join("manifest.json").is_file());
    let manifest: serde_json::Value =
        serde_json::from_slice(&std::fs::read(out.join("manifest.json")).unwrap()).unwrap();
    assert_eq!(manifest, r);
}

#[test]
fn export_json_canonicalizes() {
    let out = tmpdir("exp_json");
    let r = run_ok(
        "export",
        &json!({"result": {"markdown": "# t\n", "meta": {"schema": "x", "b": 2, "a": 1}}, "format": "json", "out_dir": pstr(&out)}),
    );
    let bytes = std::fs::read(out.join("result.json")).unwrap();
    let value: serde_json::Value = serde_json::from_slice(&bytes).unwrap();
    assert_eq!(value["meta"]["b"], 2);
    assert_eq!(bytes, canonical_bytes(&value).unwrap());
    assert_eq!(r["files"][0]["name"], "result.json");
    assert_eq!(r["source"]["markdown_digest"].as_str().unwrap().len(), 64);
}

#[test]
fn export_zip_is_deterministic_and_normalized() {
    let out1 = tmpdir("exp_zip1");
    let out2 = tmpdir("exp_zip2");
    let req = json!({"markdown": "# zip\n", "result": {"markdown": "# zip\n", "meta": {"schema": "m", "plan_digest": nf_app_core::fixtures::hex64('a'), "spec_digest": nf_app_core::fixtures::hex64('b')}}, "format": "zip", "out_dir": pstr(&out1)});
    let r1 = run_ok("export", &req);
    let mut req2 = req.clone();
    req2["out_dir"] = json!(pstr(&out2));
    let r2 = run_ok("export", &req2);
    assert_eq!(r1, r2);
    let z1 = std::fs::read(out1.join("result.zip")).unwrap();
    let z2 = std::fs::read(out2.join("result.zip")).unwrap();
    assert_eq!(z1, z2);
    let entries = zipsec::read_zip(&out1.join("result.zip")).unwrap();
    let names: Vec<&str> = entries.iter().map(|e| e.name.as_str()).collect();
    assert_eq!(names, vec!["result.md", "result.meta.json"]);
    let info = zipsec::inspect_zip(&z1).unwrap();
    for (_, mtime, mode, extra) in info {
        assert_eq!(mtime, "1980-01-01T00:00:00");
        assert_eq!(mode.map(|m| m & 0o777), Some(0o644));
        assert!(extra.is_none() || extra.unwrap().is_empty());
    }
    assert_eq!(r1["files"][0]["name"], "result.zip");
    assert_eq!(r1["files"][0]["sha256"], nf_app_core::canonical::sha256_hex(&z1));
    assert_eq!(r1["source"]["plan_digest"], nf_app_core::fixtures::hex64('a'));
    assert_eq!(r1["source"]["spec_digest"], nf_app_core::fixtures::hex64('b'));
}

#[test]
fn export_zip_duplicate_entry_is_exit1() {
    let out = tmpdir("exp_dup");
    let env = run_err(
        "export",
        &json!({
            "markdown": "# dup\n",
            "format": "zip",
            "out_dir": pstr(&out),
            "files": [{"path": "result.md", "content": "x"}]
        }),
        1,
        "NF-EXP-003",
    );
    assert_eq!(env.result.unwrap()["verdict"], "fail");
}

#[test]
fn export_traversal_is_exit3() {
    let out = tmpdir("exp_trav");
    run_err(
        "export",
        &json!({
            "markdown": "x",
            "format": "zip",
            "out_dir": pstr(&out),
            "files": [{"path": "../escape.txt", "content": "x"}]
        }),
        3,
        "NF-EXP-002",
    );
}

#[test]
fn export_docx_unavailable_is_exit4() {
    let out = tmpdir("exp_docx");
    run_err(
        "export",
        &json!({"markdown": "x", "format": "docx", "out_dir": pstr(&out)}),
        4,
        "NF-EXP-004",
    );
}

#[test]
fn export_unknown_format_is_exit3() {
    let out = tmpdir("exp_unknown");
    run_err(
        "export",
        &json!({"markdown": "x", "format": "rtf", "out_dir": pstr(&out)}),
        3,
        "NF-E-002",
    );
}

#[test]
fn export_missing_out_dir_is_exit2() {
    run_err(
        "export",
        &json!({"markdown": "x", "format": "md", "out_dir": "Z:/no/such/dir"}),
        2,
        "NF-E-004",
    );
}
#[test]
fn export_source_digests_explicit() {
    let out = tmpdir("exp_src");
    let r = run_ok(
        "export",
        &json!({
            "markdown": "# src\n",
            "format": "md",
            "out_dir": pstr(&out),
            "plan_digest": nf_app_core::fixtures::hex64('c'),
            "spec_digest": nf_app_core::fixtures::hex64('d')
        }),
    );
    assert_eq!(r["source"]["plan_digest"], nf_app_core::fixtures::hex64('c'));
    assert_eq!(r["source"]["spec_digest"], nf_app_core::fixtures::hex64('d'));
    assert_eq!(nf_app_core::schema::validate("nf-export-manifest", &r).len(), 0);
}
