//! nf-backup/1：备份清单构建 / schema 校验 / 与 pack tree 口径一致。

use nf_app_core::backup;
use nf_app_core::fixtures;
use nf_app_core::schema;
use std::path::PathBuf;

fn tmpdir(tag: &str) -> PathBuf {
    let dir = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("target")
        .join("nf-backup-test")
        .join(tag);
    let _ = std::fs::remove_dir_all(&dir);
    std::fs::create_dir_all(&dir).unwrap();
    dir
}

#[test]
fn backup_build_matches_pack_tree_and_schema() {
    let dir = tmpdir("pack");
    fixtures::make_pack(
        &dir,
        "demo-pack",
        "1.0.0",
        &[
            ("a.txt".to_string(), "a".to_string()),
            ("protocol/p.json".to_string(), "{\"x\":1}".to_string()),
        ],
    )
    .unwrap();
    let backup = backup::build(&dir, Some("2026-01-01T00:00:00Z")).unwrap();
    assert_eq!(backup["schema"], "nf-backup/1");
    assert_eq!(backup["created_at"], "2026-01-01T00:00:00Z");
    let files = backup["files"].as_array().unwrap();
    assert_eq!(files.len(), 3);
    assert_eq!(files[0]["path"], "a.txt");
    assert!(files.iter().any(|f| f["path"] == "nf-pack.json"));
    assert_eq!(files[0]["sha256"].as_str().unwrap().len(), 64);
    let tree = nf_app_core::fsutil::pack_items(&dir, None).unwrap().tree;
    assert_eq!(backup["tree"], tree);
    assert_eq!(schema::validate("nf-backup", &backup).len(), 0);
}

#[test]
fn backup_without_created_at_is_valid() {
    let dir = tmpdir("no_ts");
    fixtures::make_pack(&dir, "demo-pack", "1.0.0", &[("a.txt".to_string(), "a".to_string())]).unwrap();
    let backup = backup::build(&dir, None).unwrap();
    assert!(backup.get("created_at").is_none());
    assert_eq!(schema::validate("nf-backup", &backup).len(), 0);
}

#[test]
fn backup_write_is_canonical_and_roundtrips() {
    let dir = tmpdir("write");
    fixtures::make_pack(&dir, "demo-pack", "1.0.0", &[("a.txt".to_string(), "a".to_string())]).unwrap();
    let out = dir.join("backup.json");
    let backup = backup::write(&dir, &out, Some("2026-01-01T00:00:00Z")).unwrap();
    let bytes = std::fs::read(&out).unwrap();
    assert_eq!(bytes, nf_app_core::canonical::canonical_bytes(&backup).unwrap());
    assert_eq!(schema::validate("nf-backup", &backup).len(), 0);
}

#[test]
fn backup_validator_rejects_wrong_shape() {
    let bad = serde_json::json!({"schema": "nf-backup/1", "tree": "x", "files": [], "count": 1});
    let issues = backup::validate(&bad);
    assert!(!issues.is_empty());
    assert!(issues.iter().any(|i| i.message.contains("tree") || i.message.contains("未知字段")));
}
