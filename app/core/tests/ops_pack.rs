//! Pack：pack-hash / pack-verify / tree 口径 / requires / 安全。

#[path = "common/mod.rs"]
mod common;

use common::*;
use nf_app_core::canonical::{canonical_bytes, sha256_hex};
use nf_app_core::fsutil::{validate_rel_path, walk_files};
use nf_app_core::fixtures;
use serde_json::{json, Value};

fn tree_of(items: &[Value]) -> String {
    let arr: Vec<Value> = items
        .iter()
        .map(|i| json!({"path": i["path"], "sha256": i["sha256"], "size": i["size"]}))
        .collect();
    sha256_hex(&canonical_bytes(&Value::Array(arr)).unwrap())
}

#[test]
fn pack_hash_items_and_tree() {
    let dir = tmpdir("pack_hash");
    let manifest = fixtures::make_pack(
        &dir,
        "demo-pack",
        "1.0.0",
        &[
            ("protocol/a.json".to_string(), "{\"x\":1}".to_string()),
            ("docs/b.md".to_string(), "# b\n".to_string()),
        ],
    )
    .unwrap();
    let r = run_ok("pack-hash", &json!({"root": pstr(&dir)}));
    let items = r["items"].as_array().unwrap();
    assert_eq!(items.len(), 2);
    assert_eq!(items[0]["path"], "docs/b.md");
    assert_eq!(items[1]["path"], "protocol/a.json");
    assert_eq!(items[0]["kind"], "docs");
    assert_eq!(items[1]["kind"], "protocol");
    assert_eq!(r["hashes"]["count"], 2);
    assert_eq!(r["hashes"]["tree"].as_str().unwrap(), tree_of(items));
    assert_eq!(
        r["hashes"]["tree"].as_str().unwrap(),
        manifest["hashes"]["tree"].as_str().unwrap()
    );
}

#[test]
fn pack_hash_excludes_manifest_and_signature() {
    let dir = tmpdir("pack_excl");
    fixtures::make_pack(&dir, "demo-pack", "1.0.0", &[("a.txt".to_string(), "a".to_string())]).unwrap();
    write_file(&dir, "nf-pack.sig", "sig");
    let r = run_ok("pack-hash", &json!({"root": pstr(&dir)}));
    let items = r["items"].as_array().unwrap();
    assert_eq!(items.len(), 1);
    assert_eq!(items[0]["path"], "a.txt");
}

#[test]
fn pack_verify_pass() {
    let dir = tmpdir("pack_verify_ok");
    fixtures::make_pack(&dir, "demo-pack", "1.0.0", &[("a.json".to_string(), "{\"a\":1}".to_string())]).unwrap();
    let r = run_ok("pack-verify", &json!({"root": pstr(&dir)}));
    assert_eq!(r["schema"], "nf-validate-report/1");
    assert_eq!(r["verdict"], "pass");
    assert_eq!(r["target"]["kind"], "pack");
    assert_eq!(r["target"]["ref"], "demo-pack");
    assert_eq!(r["summary"]["error"], 0);
    assert_eq!(r["target"]["digest"].as_str().unwrap().len(), 64);
}

#[test]
fn pack_verify_tampered_item_fails() {
    let dir = tmpdir("pack_verify_bad");
    fixtures::make_pack(&dir, "demo-pack", "1.0.0", &[("a.json".to_string(), "{\"a\":1}".to_string())]).unwrap();
    write_file(&dir, "a.json", "{\"a\":2}");
    let env = run_err("pack-verify", &json!({"root": pstr(&dir)}), 1, "NF-PCK-002");
    let report = env.result.unwrap();
    assert_eq!(report["verdict"], "fail");
    assert!(report["summary"]["error"].as_u64().unwrap() >= 1);
}

#[test]
fn pack_verify_missing_manifest() {
    let dir = tmpdir("pack_verify_missing");
    write_file(&dir, "a.txt", "a");
    run_err("pack-verify", &json!({"root": pstr(&dir)}), 1, "NF-PCK-001");
}

#[test]
fn pack_verify_invalid_manifest_field() {
    let dir = tmpdir("pack_verify_invalid");
    fixtures::make_pack(&dir, "demo-pack", "1.0.0", &[("a.txt".to_string(), "a".to_string())]).unwrap();
    let mut manifest: Value =
        serde_json::from_slice(&std::fs::read(dir.join("nf-pack.json")).unwrap()).unwrap();
    manifest["oops"] = json!(1);
    std::fs::write(dir.join("nf-pack.json"), canonical_bytes(&manifest).unwrap()).unwrap();
    run_err("pack-verify", &json!({"root": pstr(&dir)}), 1, "NF-PCK-001");
}

#[test]
fn pack_verify_requires_missing_is_warn_exit0() {
    let dir = tmpdir("pack_requires_warn");
    fixtures::make_pack(&dir, "demo-pack", "1.0.0", &[("a.txt".to_string(), "a".to_string())]).unwrap();
    let mut manifest: Value =
        serde_json::from_slice(&std::fs::read(dir.join("nf-pack.json")).unwrap()).unwrap();
    manifest["requires"] = json!([{"id": "dep-x", "min": "1.0.0"}]);
    std::fs::write(dir.join("nf-pack.json"), canonical_bytes(&manifest).unwrap()).unwrap();
    let env = dispatch("pack-verify", &json!({"root": pstr(&dir)}));
    assert_eq!(env.exit, 0);
    let report = env.result.unwrap();
    assert_eq!(report["verdict"], "warn");
    assert!(report["issues"]
        .as_array()
        .unwrap()
        .iter()
        .any(|i| i["code"] == "NF-PCK-005" && i["severity"] == "warn"));
}

#[test]
fn pack_verify_requires_version_out_of_range() {
    let dir = tmpdir("pack_requires_bad");
    let pack_dir = dir.join("pack");
    fixtures::make_pack(&pack_dir, "demo-pack", "1.0.0", &[("a.txt".to_string(), "a".to_string())]).unwrap();
    let mut manifest: Value =
        serde_json::from_slice(&std::fs::read(pack_dir.join("nf-pack.json")).unwrap()).unwrap();
    manifest["requires"] = json!([{"id": "dep-y", "min": "3.0.0"}]);
    std::fs::write(pack_dir.join("nf-pack.json"), canonical_bytes(&manifest).unwrap()).unwrap();
    std::fs::create_dir_all(dir.join("dep-y").join("2.0.0")).unwrap();
    std::fs::write(dir.join("dep-y").join("2.0.0").join("nf-pack.json"), b"{}").unwrap();
    let env = run_err("pack-verify", &json!({"root": pstr(&pack_dir)}), 1, "NF-PCK-005");
    let report = env.result.unwrap();
    assert_eq!(report["verdict"], "fail");
}

#[test]
fn rel_path_safety_matrix() {
    for bad in [
        "/abs",
        "../up",
        "a/../b",
        "a//b",
        "C:/x",
        "a\\b",
        "CON",
        "con.txt",
        "LPT9",
        "a\0b",
        "",
        "a/",
    ] {
        assert!(
            validate_rel_path(bad).is_err(),
            "应拒绝不安全路径 {bad:?}"
        );
    }
    for good in ["a.txt", "protocol/x.json", "a-b_c.zh.md", "深/层/文件.txt"] {
        assert!(validate_rel_path(good).is_ok(), "应接受 {good:?}");
    }
}

#[test]
fn hardlink_rejected() {
    let dir = tmpdir("pack_hardlink");
    std::fs::create_dir_all(&dir).unwrap();
    let a = dir.join("a.txt");
    std::fs::write(&a, b"x").unwrap();
    let linked = std::fs::hard_link(&a, dir.join("b.txt"));
    if linked.is_err() {
        // 文件系统不支持硬链时，用符号链接路径覆盖（Windows 需开发者模式）
        return;
    }
    let env = dispatch("pack-hash", &json!({"root": pstr(&dir)}));
    assert_eq!(env.exit, 3);
    assert_eq!(env.error.as_ref().unwrap()["code"], "NF-SEC-002");
    assert!(walk_files(&dir).is_err());
}

#[test]
fn pack_hash_missing_root_is_io_error() {
    let env = dispatch("pack-hash", &json!({"root": "Z:/definitely/not/here"}));
    assert_eq!(env.exit, 2);
    assert_eq!(env.error.as_ref().unwrap()["code"], "NF-E-004");
}
