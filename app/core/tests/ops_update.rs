//! Pack 更新 / Overlay：pack-diff / pack-merge / overlay-apply。

#[path = "common/mod.rs"]
mod common;

use common::*;
use nf_app_core::fixtures;
use serde_json::{json, Value};

struct Roots {
    base: std::path::PathBuf,
    new: std::path::PathBuf,
    _dir: std::path::PathBuf,
}

fn roots(tag: &str) -> (Roots, Value, Value) {
    let dir = tmpdir(tag);
    let base = dir.join("pack-v1");
    let new = dir.join("pack-v2");
    let m1 = fixtures::make_pack(&base, "demo-pack", "1.0.0", &fixtures::pack_v1_files()).unwrap();
    let m2 = fixtures::make_pack(&new, "demo-pack", "2.0.0", &fixtures::pack_v2_files()).unwrap();
    (
        Roots {
            base,
            new,
            _dir: dir,
        },
        m1,
        m2,
    )
}

#[test]
fn pack_diff_changes_and_impact() {
    let (r, _m1, _m2) = roots("diff");
    let update = run_ok(
        "pack-diff",
        &json!({"old_root": pstr(&r.base), "new_root": pstr(&r.new)}),
    );
    assert_eq!(update["schema"], "nf-pack-update/1");
    assert_eq!(update["from"]["version"], "1.0.0");
    assert_eq!(update["to"]["version"], "2.0.0");
    assert_eq!(update["from"]["tree"].as_str().unwrap().len(), 64);
    assert_eq!(update["to"]["tree"].as_str().unwrap().len(), 64);
    let changes = &update["changes"];
    assert_eq!(changes["added"][0]["path"], "docs/new.md");
    assert_eq!(changes["removed"][0]["path"], "docs/old.md");
    assert_eq!(changes["modified"][0]["path"], "protocol/demo-protocol.json");
    assert_eq!(update["impact"]["breaking"], true);
    assert!(update["impact"]["overlay_keys"]
        .as_array()
        .unwrap()
        .contains(&json!("clauses")));
    assert_eq!(update["merge"]["on_conflict"], "require_user");
    assert_eq!(update["merge"]["actions"].as_array().unwrap().len(), 3);
    assert_eq!(update["conflicts"].as_array().unwrap().len(), 0);
    assert_eq!(update["policy"]["auto_merge"], true);
}

#[test]
fn pack_diff_manifest_mismatch_is_exit1() {
    let (r, _m1, _m2) = roots("diff_bad");
    let mut manifest: Value =
        serde_json::from_slice(&std::fs::read(r.base.join("nf-pack.json")).unwrap()).unwrap();
    manifest["hashes"]["tree"] = json!(fixtures::hex64('0'));
    std::fs::write(
        r.base.join("nf-pack.json"),
        nf_app_core::canonical::canonical_bytes(&manifest).unwrap(),
    )
    .unwrap();
    run_err(
        "pack-diff",
        &json!({"old_root": pstr(&r.base), "new_root": pstr(&r.new)}),
        1,
        "NF-PCK-002",
    );
}

#[test]
fn pack_merge_applies_changes() {
    let (r, _m1, _m2) = roots("merge");
    let update = run_ok(
        "pack-diff",
        &json!({"old_root": pstr(&r.base), "new_root": pstr(&r.new)}),
    );
    let out = tmpdir("merge_out");
    let result = run_ok(
        "pack-merge",
        &json!({
            "update": update,
            "base_root": pstr(&r.base),
            "new_root": pstr(&r.new),
            "out_dir": pstr(&out),
        }),
    );
    assert_eq!(result["applied"], true);
    assert_eq!(result["conflicts"].as_array().unwrap().len(), 0);
    assert_eq!(result["result_tree"].as_str().unwrap().len(), 64);
    assert!(out.join("docs").join("new.md").is_file());
    assert!(!out.join("docs").join("old.md").exists());
    let protocol: Value =
        serde_json::from_slice(&std::fs::read(out.join("protocol").join("demo-protocol.json")).unwrap())
            .unwrap();
    assert!(protocol["clauses"][0]["text"]
        .as_str()
        .unwrap()
        .contains("v2"));
    assert!(out.join("nf-pack.json").is_file());
    let hashed = run_ok("pack-hash", &json!({"root": pstr(&out)}));
    assert_eq!(hashed["hashes"]["tree"], result["result_tree"]);
}

#[test]
fn pack_merge_unresolved_conflict_is_exit1() {
    let (r, m1, _m2) = roots("merge_conflict");
    let update = run_ok(
        "pack-diff",
        &json!({"old_root": pstr(&r.base), "new_root": pstr(&r.new)}),
    );
    let overlay = fixtures::overlay(m1["hashes"]["tree"].as_str().unwrap(), "demo-pack", "1.0.0");
    let out = tmpdir("merge_conflict_out");
    let env = run_err(
        "pack-merge",
        &json!({
            "update": update,
            "base_root": pstr(&r.base),
            "new_root": pstr(&r.new),
            "overlay": overlay,
            "out_dir": pstr(&out),
        }),
        1,
        "NF-PCK-006",
    );
    let report = env.result.unwrap();
    assert_eq!(report["verdict"], "fail");
    assert!(report["issues"]
        .as_array()
        .unwrap()
        .iter()
        .any(|i| i["code"] == "NF-PCK-006"));
}

#[test]
fn pack_merge_decisions_take_new() {
    let (r, m1, _m2) = roots("merge_decide");
    let update = run_ok(
        "pack-diff",
        &json!({"old_root": pstr(&r.base), "new_root": pstr(&r.new)}),
    );
    let overlay = fixtures::overlay(m1["hashes"]["tree"].as_str().unwrap(), "demo-pack", "1.0.0");
    let out = tmpdir("merge_decide_out");
    // 先拿未裁决时的冲突 id
    let env = dispatch(
        "pack-merge",
        &json!({
            "update": update.clone(),
            "base_root": pstr(&r.base),
            "new_root": pstr(&r.new),
            "overlay": overlay.clone(),
            "out_dir": pstr(&out),
            "decisions": {}
        }),
    );
    assert_eq!(env.exit, 1);
    let report = env.result.unwrap();
    let ids: Vec<String> = report["issues"]
        .as_array()
        .unwrap()
        .iter()
        .map(|i| i["path"].as_str().unwrap().trim_start_matches("$.conflicts.").to_string())
        .collect();
    assert!(!ids.is_empty());
    let mut decisions = serde_json::Map::new();
    for id in &ids {
        decisions.insert(id.clone(), json!("take_new"));
    }
    let result = run_ok(
        "pack-merge",
        &json!({
            "update": update,
            "base_root": pstr(&r.base),
            "new_root": pstr(&r.new),
            "overlay": overlay,
            "out_dir": pstr(&out),
            "decisions": decisions,
        }),
    );
    assert_eq!(result["applied"], true);
    assert!(!result["conflicts"].as_array().unwrap().is_empty());
}

#[test]
fn pack_merge_apply_then_reverse_restores_base_tree() {
    let (r, _m1, _m2) = roots("merge_roundtrip");
    let update = run_ok(
        "pack-diff",
        &json!({"old_root": pstr(&r.base), "new_root": pstr(&r.new)}),
    );
    let applied = tmpdir("merge_roundtrip_out");
    run_ok(
        "pack-merge",
        &json!({
            "update": update.clone(),
            "base_root": pstr(&r.base),
            "new_root": pstr(&r.new),
            "out_dir": pstr(&applied),
        }),
    );
    let base_tree = run_ok("pack-hash", &json!({"root": pstr(&r.base)}))["hashes"]["tree"].clone();
    let applied_tree = run_ok("pack-hash", &json!({"root": pstr(&applied)}))["hashes"]["tree"].clone();
    assert_ne!(applied_tree, base_tree, "apply 后 tree 必须变化");
    // 逆 update：from=v2, to=v1，changes 取交换
    let mut reverse = update.clone();
    reverse["from"] = update["to"].clone();
    reverse["to"] = update["from"].clone();
    let base_manifest: Value =
        serde_json::from_slice(&std::fs::read(r.base.join("nf-pack.json")).unwrap()).unwrap();
    let base_items = base_manifest["items"].as_array().unwrap();
    let mut added_back = Vec::new();
    for m in update["changes"]["removed"].as_array().unwrap() {
        let path = m["path"].as_str().unwrap();
        let size = base_items
            .iter()
            .find(|i| i["path"].as_str() == Some(path))
            .map(|i| i["size"].clone())
            .unwrap();
        added_back.push(json!({"path": m["path"], "sha256": m["sha256"], "size": size}));
    }
    reverse["changes"]["added"] = json!(added_back);
    let mut removed_back = Vec::new();
    for m in update["changes"]["added"].as_array().unwrap() {
        removed_back.push(json!({"path": m["path"], "sha256": m["sha256"]}));
    }
    reverse["changes"]["removed"] = json!(removed_back);
    let mut modified = Vec::new();
    for m in update["changes"]["modified"].as_array().unwrap() {
        modified.push(json!({
            "path": m["path"],
            "sha256": m["new_sha256"],
            "new_sha256": m["sha256"],
        }));
    }
    reverse["changes"]["modified"] = json!(modified);
    let rolled = tmpdir("merge_roundtrip_rolled");
    run_ok(
        "pack-merge",
        &json!({
            "update": reverse,
            "base_root": pstr(&r.new),
            "new_root": pstr(&r.base),
            "out_dir": pstr(&rolled),
        }),
    );
    let rolled_tree = run_ok("pack-hash", &json!({"root": pstr(&rolled)}))["hashes"]["tree"].clone();
    assert_eq!(rolled_tree, base_tree, "apply→逆 apply 后 tree 必须回到 base tree");
}

#[test]
fn pack_merge_tree_mismatch_is_exit3() {
    let (r, _m1, _m2) = roots("merge_tree");
    let update = run_ok(
        "pack-diff",
        &json!({"old_root": pstr(&r.base), "new_root": pstr(&r.new)}),
    );
    let out = tmpdir("merge_tree_out");
    let mut bad = update.clone();
    bad["from"]["tree"] = json!(fixtures::hex64('0'));
    run_err(
        "pack-merge",
        &json!({
            "update": bad,
            "base_root": pstr(&r.base),
            "new_root": pstr(&r.new),
            "out_dir": pstr(&out),
        }),
        3,
        "NF-PCK-004",
    );
}

#[test]
fn overlay_apply_toggles_clauses() {
    let (r, m1, _m2) = roots("overlay");
    let overlay = fixtures::overlay(m1["hashes"]["tree"].as_str().unwrap(), "demo-pack", "1.0.0");
    let out = tmpdir("overlay_out");
    let result = run_ok(
        "overlay-apply",
        &json!({"base_root": pstr(&r.base), "overlay": overlay, "out_dir": pstr(&out)}),
    );
    assert_eq!(result["tree"].as_str().unwrap().len(), 64);
    assert_eq!(result["base"]["id"], "demo-pack");
    assert!(out.join("overlay").join("nf-overlay.json").is_file());
    let protocol: Value =
        serde_json::from_slice(&std::fs::read(out.join("protocol").join("demo-protocol.json")).unwrap())
            .unwrap();
    assert_eq!(protocol["clauses"][0]["enabled"], false);
    assert_eq!(protocol["clauses"][1]["enabled"], true);
    let hashed = run_ok("pack-hash", &json!({"root": pstr(&out)}));
    assert_eq!(hashed["hashes"]["tree"], result["tree"]);
}

#[test]
fn overlay_apply_base_tree_mismatch_is_exit1() {
    let (r, m1, _m2) = roots("overlay_bad");
    let overlay = fixtures::overlay(&fixtures::hex64('0'), "demo-pack", "1.0.0");
    let out = tmpdir("overlay_bad_out");
    let env = run_err(
        "overlay-apply",
        &json!({"base_root": pstr(&r.base), "overlay": overlay, "out_dir": pstr(&out)}),
        1,
        "NF-PCK-002",
    );
    assert_eq!(env.result.unwrap()["verdict"], "fail");
    let _ = m1;
}