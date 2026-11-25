//! 签名 Pack 发布：nf-pack-release/1（Ed25519 + 树摘要 + 版本/通道）。
//! 严格模式：签名/树不符直接拒绝；回滚/冻结由本地 trust store 拦截。

use crate::canonical::{canonical_bytes, digest_value};
use crate::error::{CoreError, OpOutcome};
use crate::evidence::{sign_payload, verify_payload};
use crate::fsutil;
use crate::ops::update;
use crate::ops::{opt_str, req_value, usage};
use crate::report::Report;
use crate::schema::validate;
use serde_json::{json, Value};
use std::path::Path;

fn is_hash64(s: &str) -> bool {
    s.len() == 64 && s.chars().all(|c| c.is_ascii_hexdigit())
}

fn signing_payload(release: &Value) -> Result<Vec<u8>, CoreError> {
    let mut v = release.clone();
    if let Some(m) = v.as_object_mut() {
        m.remove("signature");
    }
    canonical_bytes(&v)
}

fn trust_load(path: &str) -> Result<Value, CoreError> {
    let normalized = path.replace('\\', "/");
    let p = Path::new(&normalized);
    if !p.exists() {
        return Ok(json!({"schema": "nf-trust-store/1", "packs": {}}));
    }
    let v = fsutil::load_json_file(p)?;
    if v.get("schema").and_then(|x| x.as_str()) != Some("nf-trust-store/1")
        || !v.get("packs").map(|x| x.is_object()).unwrap_or(false)
    {
        return Err(CoreError::new("NF-PCK-007").with_message("Pack trust store 非法").with_exit(1));
    }
    Ok(v)
}

fn trust_check(report: &mut Report, pack_id: &str, release_version: u64, tree: &str, trust: &Value) {
    if let Some(e) = trust.get("packs").and_then(|p| p.get(pack_id)) {
        let tv = e.get("release_version").and_then(|v| v.as_u64()).unwrap_or(0);
        let tt = e.get("tree").and_then(|v| v.as_str()).unwrap_or("");
        if release_version < tv {
            report.error("NF-PCK-009", "$.release_version", &format!("回滚：{release_version} < 已冻结 {tv}"));
        } else if release_version == tv && tree != tt {
            report.error("NF-PCK-009", "$.pack.tree", "冻结：同版本但树摘要不同");
        }
    }
}

fn check_release(release: &Value, pack_root: Option<&str>) -> (Report, Option<(String, u64, String)>) {
    let mut report = Report::new("L0", release, "pack-release", "release");
    if release.get("schema").and_then(|v| v.as_str()) != Some("nf-pack-release/1") {
        report.error("NF-PCK-007", "$.schema", "schema 必须是 nf-pack-release/1");
        return (report, None);
    }
    let pack = match release.get("pack").and_then(|v| v.as_object()) {
        Some(p) => p,
        None => {
            report.error("NF-PCK-007", "$.pack", "缺 pack 对象");
            return (report, None);
        }
    };
    let pack_id = pack.get("id").and_then(|v| v.as_str()).unwrap_or("");
    let pack_version = pack.get("version").and_then(|v| v.as_str()).unwrap_or("");
    let tree = pack.get("tree").and_then(|v| v.as_str()).unwrap_or("");
    let manifest_sha = pack.get("manifest_sha256").and_then(|v| v.as_str()).unwrap_or("");
    if pack_id.is_empty() || pack_version.is_empty() || !is_hash64(tree) || !is_hash64(manifest_sha) {
        report.error("NF-PCK-007", "$.pack", "pack.id/version/tree/manifest_sha256 缺失或非法");
    }
    let rv = release.get("release_version").and_then(|v| v.as_u64()).unwrap_or(0);
    if rv == 0 {
        report.error("NF-PCK-007", "$.release_version", "release_version 必须 >=1");
    }
    if release.get("created_at").and_then(|v| v.as_str()).unwrap_or("").is_empty() {
        report.error("NF-PCK-007", "$.created_at", "created_at 必填（确定性）");
    }
    let sig = release.get("signature").cloned().unwrap_or(Value::Null);
    match signing_payload(release) {
        Ok(payload) => {
            if let Err(e) = verify_payload(&sig, &payload) {
                report.error("NF-PCK-007", "$.signature", &format!("签名验证失败：{}", e.message));
            }
        }
        Err(e) => report.error("NF-PCK-007", "$", &e.message),
    }
    if let Some(root) = pack_root {
        let normalized = root.replace('\\', "/");
        let path = Path::new(&normalized);
        let manifest = match fsutil::load_json_file(&path.join("nf-pack.json")) {
            Ok(m) => m,
            Err(e) => {
                report.error("NF-PCK-008", "$.pack", &format!("读 Pack 清单失败：{}", e.message));
                return (report, None);
            }
        };
        for i in validate("nf-pack", &manifest) {
            report.error("NF-PCK-008", &i.path, &i.message);
        }
        if manifest.get("id").and_then(|v| v.as_str()) != Some(pack_id) {
            report.error("NF-PCK-008", "$.pack.id", "发布 id 与 Pack 清单不一致");
        }
        if manifest.get("version").and_then(|v| v.as_str()) != Some(pack_version) {
            report.error("NF-PCK-008", "$.pack.version", "发布 version 与 Pack 清单不一致");
        }
        match digest_value(&manifest) {
            Ok(d) if d != manifest_sha => report.error("NF-PCK-008", "$.pack.manifest_sha256", "清单摘要不一致"),
            Err(e) => report.error("NF-PCK-008", "$.pack.manifest_sha256", &e.message),
            _ => {}
        }
        match fsutil::pack_items(&path, Some(&manifest)) {
            Ok(items) if items.tree != tree => report.error("NF-PCK-008", "$.pack.tree", "发布树摘要与 Pack 不一致"),
            Err(e) => report.error("NF-PCK-008", "$.pack.tree", &e.message),
            _ => {}
        }
    }
    (report, Some((pack_id.to_string(), rv, tree.to_string())))
}

pub fn create(req: &Value) -> OpOutcome {
    let root = opt_str(req, "pack_root")?.ok_or_else(|| usage("pack-release-create 需要 pack_root"))?;
    let version = req.get("release_version").and_then(|v| v.as_u64()).ok_or_else(|| usage("需要 release_version"))?;
    let created_at = opt_str(req, "created_at")?.filter(|s| !s.is_empty()).ok_or_else(|| usage("需要显式 created_at"))?;
    let seed = opt_str(req, "private_key")?.ok_or_else(|| CoreError::new("NF-EVD-002").with_message("需要 private_key").with_exit(3))?;
    let channel = opt_str(req, "channel")?.unwrap_or("stable");
    let normalized = root.replace('\\', "/");
    let path = Path::new(&normalized);
    let manifest = fsutil::load_json_file(&path.join("nf-pack.json"))?;
    let issues = validate("nf-pack", &manifest);
    if !issues.is_empty() {
        let mut rep = Report::new("L0", &manifest, "nf-pack", "manifest");
        for i in issues {
            rep.error("NF-PCK-001", &i.path, &i.message);
        }
        return Ok((1, rep.to_value()));
    }
    let items = fsutil::pack_items(path, Some(&manifest))?;
    let mut release = json!({
        "schema": "nf-pack-release/1",
        "pack": {
            "id": manifest["id"],
            "version": manifest["version"],
            "kind": manifest["kind"],
            "tree": items.tree,
            "manifest_sha256": digest_value(&manifest)?
        },
        "release_version": version,
        "channel": channel,
        "created_at": created_at
    });
    let payload = canonical_bytes(&release)?;
    release.as_object_mut().unwrap().insert("signature".into(), sign_payload(seed, &payload)?);
    Ok((0, release))
}

pub fn verify(req: &Value) -> OpOutcome {
    let release = req_value(req, "release")?;
    let (mut report, info) = check_release(release, opt_str(req, "pack_root")?);
    if let (Some((pid, rv, tree)), Some(tp)) = (&info, opt_str(req, "trust_path")?) {
        match trust_load(tp) {
            Ok(trust) => trust_check(&mut report, pid, *rv, tree, &trust),
            Err(e) => report.error("NF-PCK-007", "$.trust", &e.message),
        }
    }
    let (e, w, _) = report.counts();
    let result = json!({
        "schema": "nf-pack-release-verify/1",
        "ok": e == 0,
        "errors": e,
        "warnings": w,
        "pack_id": info.as_ref().map(|x| x.0.clone()),
        "release_version": info.as_ref().map(|x| x.1),
        "tree": info.as_ref().map(|x| x.2.clone())
    });
    if e == 0 {
        Ok((0, result))
    } else {
        let mut out = report.to_value();
        out.as_object_mut().unwrap().insert("verify".into(), result);
        Ok((1, out))
    }
}

pub fn freeze(req: &Value) -> OpOutcome {
    let release = req_value(req, "release")?;
    let trust_path = opt_str(req, "trust_path")?.ok_or_else(|| usage("pack-release-freeze 需要 trust_path"))?;
    let allow = req.get("allow_rollback").and_then(|v| v.as_bool()).unwrap_or(false);
    let (report, info) = check_release(release, opt_str(req, "pack_root")?);
    if report.has_error() {
        return Ok((1, report.to_value()));
    }
    let (pid, rv, tree) = info.unwrap();
    let mut trust = trust_load(trust_path)?;
    if let Some(e) = trust.get("packs").and_then(|p| p.get(&pid)) {
        let tv = e.get("release_version").and_then(|v| v.as_u64()).unwrap_or(0);
        let tt = e.get("tree").and_then(|v| v.as_str()).unwrap_or("");
        if rv < tv && !allow {
            return Err(CoreError::new("NF-PCK-009").with_message(format!("拒绝回滚：{rv} < {tv}")).with_exit(1));
        }
        if rv == tv && tree != tt {
            return Err(CoreError::new("NF-PCK-009").with_message("拒绝冻结替换：同版本不同树").with_exit(1));
        }
    }
    let frozen_at = opt_str(req, "created_at")?.unwrap_or("").to_string();
    trust
        .as_object_mut()
        .unwrap()
        .get_mut("packs")
        .unwrap()
        .as_object_mut()
        .unwrap()
        .insert(pid.clone(), json!({"release_version": rv, "tree": tree, "frozen_at": frozen_at}));
    fsutil::write_json_canonical(Path::new(&trust_path.replace('\\', "/")), &trust)?;
    Ok((0, json!({"schema": "nf-trust-store/1", "pack_id": pid, "release_version": rv, "tree": tree, "trust_path": trust_path})))
}

pub fn pack_update(req: &Value) -> OpOutcome {
    let release = req_value(req, "release")?;
    let (report, info) = check_release(release, opt_str(req, "pack_root")?);
    if report.has_error() {
        return Ok((1, report.to_value()));
    }
    if let (Some((pid, rv, tree)), Some(tp)) = (&info, opt_str(req, "trust_path")?) {
        let trust = trust_load(tp)?;
        let mut rep = Report::new("L0", release, "pack-release", "release");
        trust_check(&mut rep, pid, *rv, tree, &trust);
        if rep.has_error() {
            return Ok((1, rep.to_value()));
        }
    }
    update::pack_merge(req)
}

pub fn reload_op(req: &Value) -> OpOutcome { verify(req) }

pub fn create_op(req: &Value) -> OpOutcome { create(req) }
pub fn verify_op(req: &Value) -> OpOutcome { verify(req) }
pub fn freeze_op(req: &Value) -> OpOutcome { freeze(req) }
pub fn update_op(req: &Value) -> OpOutcome { pack_update(req) }
