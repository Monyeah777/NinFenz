//! nf-evidence/1：证据随包、Ed25519 签名、离线验证。
//! 签名覆盖除 signature 外的全部字段（canonical JSON），不依赖网络/时间戳/CA。

use crate::canonical::{canonical_bytes, digest_value, sha256_hex};
use crate::error::{CoreError, OpOutcome};
use crate::fsutil;
use crate::ops::{opt_str, req_value, usage};
use crate::report::Report;
use crate::sdir;
use crate::schema::validate;
use crate::zipsec;
use ed25519_compact::{KeyPair, PublicKey, Seed, Signature};
use serde_json::{json, Map, Value};

pub const EVIDENCE_SCHEMA: &str = "nf-evidence/1";

fn hex_bytes(s: &str) -> Result<Vec<u8>, CoreError> {
    if s.len() % 2 != 0 {
        return Err(CoreError::new("NF-EVD-002").with_message("十六进制长度必须是偶数").with_exit(3));
    }
    let mut out = Vec::with_capacity(s.len() / 2);
    let b = s.as_bytes();
    let mut i = 0;
    while i < b.len() {
        let hi = (b[i] as char).to_digit(16);
        let lo = (b[i + 1] as char).to_digit(16);
        match (hi, lo) {
            (Some(h), Some(l)) => out.push(((h << 4) | l) as u8),
            _ => return Err(CoreError::new("NF-EVD-002").with_message("非法十六进制").with_exit(3)),
        }
        i += 2;
    }
    Ok(out)
}

fn to_hex(bytes: &[u8]) -> String {
    let mut s = String::with_capacity(bytes.len() * 2);
    for b in bytes {
        s.push_str(&format!("{b:02x}"));
    }
    s
}

fn seed_bytes(input: &str) -> Result<[u8; 32], CoreError> {
    let raw = hex_bytes(input)?;
    if raw.len() == 32 {
        let mut out = [0u8; 32];
        out.copy_from_slice(&raw);
        if out.iter().all(|b| *b == 0) {
            return Err(CoreError::new("NF-EVD-002").with_message("私钥种子不能全零").with_exit(3));
        }
        return Ok(out);
    }
    // 允许任意口令：确定性派生 32 字节种子（仅用于测试/本地设备密钥初始化，不是 KDF 承诺）
    let digest = sha256_hex(input.as_bytes());
    let raw = hex_bytes(&digest)?;
    let mut out = [0u8; 32];
    out.copy_from_slice(&raw);
    Ok(out)
}

fn keypair(seed: &str) -> Result<KeyPair, CoreError> {
    Ok(KeyPair::from_seed(Seed::new(seed_bytes(seed)?)))
}

fn signing_payload(evidence: &Value) -> Result<Vec<u8>, CoreError> {
    let mut v = evidence.clone();
    if let Some(m) = v.as_object_mut() {
        m.remove("signature");
    }
    canonical_bytes(&v)
}

pub fn sign_payload(seed: &str, payload: &[u8]) -> Result<Value, CoreError> {
    let kp = keypair(seed)?;
    let sig = kp.sk.sign(payload, None);
    let pub_bytes: &[u8] = kp.pk.as_ref();
    Ok(json!({
        "alg": "ed25519",
        "value": to_hex(sig.as_ref()),
        "public_key": to_hex(pub_bytes),
        "key_fingerprint": sha256_hex(pub_bytes)
    }))
}

pub fn verify_payload(sig: &Value, payload: &[u8]) -> Result<(), CoreError> {
    if sig.get("alg").and_then(|v| v.as_str()) != Some("ed25519") {
        return Err(CoreError::new("NF-EVD-002").with_message("签名算法必须是 ed25519").with_exit(3));
    }
    let pk = hex_bytes(sig.get("public_key").and_then(|v| v.as_str()).unwrap_or(""))?;
    let sg = hex_bytes(sig.get("value").and_then(|v| v.as_str()).unwrap_or(""))?;
    if pk.len() != 32 || sg.len() != 64 {
        return Err(CoreError::new("NF-EVD-002").with_message("公钥或签名长度非法").with_exit(3));
    }
    if sha256_hex(&pk) != sig.get("key_fingerprint").and_then(|v| v.as_str()).unwrap_or("") {
        return Err(CoreError::new("NF-EVD-003").with_message("公钥指纹不匹配").with_exit(1));
    }
    let public = PublicKey::from_slice(&pk).map_err(|_| CoreError::new("NF-EVD-002").with_message("公钥非法").with_exit(3))?;
    let signature = Signature::from_slice(&sg).map_err(|_| CoreError::new("NF-EVD-002").with_message("签名非法").with_exit(3))?;
    public
        .verify(payload, &signature)
        .map_err(|e| CoreError::new("NF-EVD-003").with_message(format!("签名验证失败：{e}")).with_exit(1))
}

fn signature_of(evidence: &Value, seed: &str) -> Result<Value, CoreError> {
    let payload = signing_payload(evidence)?;
    sign_payload(seed, &payload)
}

fn lineage(sdir: &Value) -> Value {
    let mut out = Vec::new();
    for p in sdir.get("provenance").and_then(|v| v.as_array()).into_iter().flatten() {
        let mut m = Map::new();
        m.insert("block".into(), p.get("block").cloned().unwrap_or(Value::Null));
        m.insert("source_id".into(), p.get("source_id").cloned().unwrap_or(Value::Null));
        if let Some(page) = p.get("page") { m.insert("page".into(), page.clone()); }
        m.insert("transform".into(), p.get("transform").cloned().unwrap_or_else(|| json!(["unknown/1"])));
        if let Some(src) = sdir.get("sources").and_then(|v| v.as_array()).and_then(|a| a.iter().find(|s| s.get("id") == p.get("source_id"))) {
            m.insert("source_sha".into(), src.get("bytes_sha").cloned().unwrap_or(Value::Null));
        }
        out.push(Value::Object(m));
    }
    json!({"block_lineage": out})
}

pub fn create(req: &Value) -> OpOutcome {
    let artifact_path = opt_str(req, "artifact_path")?.ok_or_else(|| usage("evidence-create 需要 artifact_path"))?;
    let bytes = fsutil::read_bytes(&std::path::Path::new(&artifact_path.replace('\\', "/")), crate::limits::limits().pack_max_file_bytes)?;
    let sdir = req_value(req, "sdir")?;
    let graph = req_value(req, "graph")?;
    let created_at = opt_str(req, "created_at")?.filter(|s| !s.is_empty()).ok_or_else(|| usage("evidence-create 需要显式 created_at"))?;
    let seed = opt_str(req, "private_key")?.ok_or_else(|| CoreError::new("NF-EVD-002").with_message("evidence-create 需要 private_key（32 字节种子或口令）").with_exit(3))?;
    let profile = opt_str(req, "profile")?.unwrap_or("default");
    let report = sdir::validate_sdir_value(sdir);
    let (errors, warnings, _) = report.counts();
    let input_shas: Vec<Value> = sdir
        .get("sources")
        .and_then(|v| v.as_array())
        .map(|a| a.iter().filter_map(|s| s.get("bytes_sha").cloned()).collect())
        .unwrap_or_default();
    if input_shas.is_empty() {
        return Err(CoreError::new("NF-EVD-001").with_message("SDIR 无来源摘要，无法形成证据").with_exit(1));
    }
    let mut ev = json!({
        "schema": EVIDENCE_SCHEMA,
        "artifact": {
            "path": artifact_path,
            "sha256": sha256_hex(&bytes),
            "bytes": bytes.len() as u64
        },
        "input_shas": input_shas,
        "plan_sha": graph.get("plan_sha").cloned().unwrap_or(Value::Null),
        "graph_sha": digest_value(graph)?,
        "validation": {
            "profile": profile,
            "validator": "nf-sdir-validate/1",
            "version": crate::CORE_VERSION,
            "errors": errors,
            "warnings": warnings
        },
        "provenance": lineage(sdir),
        "signature": Value::Null,
        "tool_versions": {
            "core": crate::CORE_VERSION,
            "schema": "nf-sdir/1+nf-build-graph/1+nf-evidence/1",
            "validators": ["nf-sdir-validate/1"]
        },
        "created_at": created_at
    });
    let sig = signature_of(&ev, seed)?;
    ev.as_object_mut().unwrap().insert("signature".into(), sig);
    let issues = validate("nf-evidence", &ev);
    if !issues.is_empty() {
        let mut rep = Report::new("L0", &ev, "evidence", "evidence");
        for i in issues { rep.error("NF-EVD-001", &i.path, &i.message); }
        return Ok((1, rep.to_value()));
    }
    Ok((0, ev))
}

fn verify_checks(ev: &Value, artifact_bytes: Option<&[u8]>) -> Report {
    let mut report = Report::new("L0", ev, "evidence", "evidence");
    for i in validate("nf-evidence", ev) {
        report.error("NF-EVD-001", &i.path, &i.message);
    }
    if report.has_error() {
        return report;
    }
    if let Some(bytes) = artifact_bytes {
        let sha = sha256_hex(bytes);
        if ev["artifact"]["sha256"].as_str() != Some(&sha) {
            report.error("NF-EVD-001", "$.artifact.sha256", "产物摘要与证据不一致（篡改或缺件）");
        }
        if ev["artifact"]["bytes"].as_u64() != Some(bytes.len() as u64) {
            report.error("NF-EVD-001", "$.artifact.bytes", "产物字节数与证据不一致");
        }
    }
    let sig = &ev["signature"];
    let pk_hex = sig["public_key"].as_str().unwrap_or("");
    let sig_hex = sig["value"].as_str().unwrap_or("");
    match (hex_bytes(pk_hex), hex_bytes(sig_hex)) {
        (Ok(pk), Ok(sg)) if pk.len() == 32 && sg.len() == 64 => {
            if sha256_hex(&pk) != sig["key_fingerprint"].as_str().unwrap_or("") {
                report.error("NF-EVD-003", "$.signature.key_fingerprint", "公钥指纹不匹配");
            }
            match (PublicKey::from_slice(&pk), Signature::from_slice(&sg)) {
                (Ok(public), Ok(signature)) => {
                    let payload = match signing_payload(ev) {
                        Ok(p) => p,
                        Err(e) => {
                            report.error("NF-EVD-001", "$", &e.message);
                            return report;
                        }
                    };
                    if let Err(e) = public.verify(&payload, &signature) {
                        report.error("NF-EVD-003", "$.signature", &format!("签名验证失败：{e}"));
                    }
                }
                _ => report.error("NF-EVD-002", "$.signature", "公钥或签名长度非法"),
            }
        }
        _ => report.error("NF-EVD-002", "$.signature", "公钥/签名不是合法十六进制"),
    }
    let lineage = ev["provenance"]["block_lineage"].as_array().cloned().unwrap_or_default();
    if lineage.is_empty() {
        report.error("NF-EVD-001", "$.provenance.block_lineage", "证据没有块级谱系");
    }
    let mut seen = std::collections::BTreeSet::new();
    for l in &lineage {
        let b = l.get("block").and_then(|v| v.as_str()).unwrap_or("");
        if b.is_empty() || !seen.insert(b.to_string()) {
            report.error("NF-EVD-001", "$.provenance.block_lineage", "块谱系 block 缺失或重复");
        }
    }
    report
}

pub fn verify(req: &Value) -> OpOutcome {
    let ev = req_value(req, "evidence")?;
    let artifact = match opt_str(req, "artifact_path")? {
        Some(p) => Some(fsutil::read_bytes(&std::path::Path::new(&p.replace('\\', "/")), crate::limits::limits().pack_max_file_bytes)?),
        None => None,
    };
    let report = verify_checks(ev, artifact.as_deref());
    let (e, w, _) = report.counts();
    let result = json!({
        "schema": "nf-evidence-verify/1",
        "ok": e == 0,
        "errors": e,
        "warnings": w,
        "checks": {
            "schema": true,
            "artifact": artifact.is_some(),
            "signature": e == 0,
            "lineage": !ev["provenance"]["block_lineage"].as_array().map(|a| a.is_empty()).unwrap_or(true)
        }
    });
    if e == 0 {
        Ok((0, result))
    } else {
        let mut rep = report;
        for i in rep.issues.iter_mut() {
            i.message = format!("{} {}", i.path, i.message);
        }
        let mut out = rep.to_value();
        out.as_object_mut().unwrap().insert("verify".into(), result);
        Ok((1, out))
    }
}

pub fn keygen(req: &Value) -> OpOutcome {
    let seed = opt_str(req, "seed")?.ok_or_else(|| usage("evidence-keygen 需要 seed"))?;
    let kp = keypair(seed)?;
    let pub_bytes: &[u8] = kp.pk.as_ref();
    let seed_hex = to_hex(&seed_bytes(seed)?);
    Ok((0, json!({
        "schema": "nf-evidence-key/1",
        "seed": seed_hex,
        "public_key": to_hex(pub_bytes),
        "key_fingerprint": sha256_hex(pub_bytes)
    })))
}


pub fn pack(req: &Value) -> OpOutcome {
    let artifact_path = opt_str(req, "artifact_path")?.ok_or_else(|| usage("evidence-pack 需要 artifact_path"))?;
    let out_path = opt_str(req, "out_path")?.ok_or_else(|| usage("evidence-pack 需要 out_path"))?;
    let ev = req_value(req, "evidence")?;
    let bytes = fsutil::read_bytes(std::path::Path::new(&artifact_path.replace('\\', "/")), crate::limits::limits().pack_max_file_bytes)?;
    let sha = sha256_hex(&bytes);
    if ev["artifact"]["sha256"].as_str() != Some(&sha) {
        return Err(CoreError::new("NF-EVD-001").with_message("证据与待打包产物摘要不一致").with_exit(1));
    }
    let name = std::path::Path::new(&artifact_path.replace('\\', "/"))
        .file_name()
        .and_then(|s| s.to_str())
        .unwrap_or("artifact.bin")
        .to_string();
    let version = req.get("version").and_then(|v| v.as_u64()).unwrap_or(1);
    if version == 0 {
        return Err(CoreError::new("NF-EVD-005").with_message("证据包 version 必须 >=1").with_exit(1));
    }
    let evidence_canonical = canonical_bytes(ev)?;
    let evidence_sha = sha256_hex(&evidence_canonical);
    let evidence_bytes = {
        let mut b = evidence_canonical;
        b.push(b'\n');
        b
    };
    let artifact_inner = format!("artifact/{name}");
    let package_id = sha256_hex(format!("{artifact_inner}:{sha}").as_bytes());
    let manifest = json!({
        "schema": "nf-evidence-package/1",
        "package_id": package_id,
        "version": version,
        "artifact": {"path": artifact_inner, "sha256": sha, "bytes": bytes.len() as u64},
        "evidence_sha": evidence_sha
    });
    let mut mb = canonical_bytes(&manifest)?;
    mb.push(b'\n');
    let mut entries: Vec<(String, Vec<u8>)> = vec![
        (format!("artifact/{name}"), bytes),
        ("evidence.json".to_string(), evidence_bytes),
        ("manifest.json".to_string(), mb),
    ];
    entries.sort_by(|a, b| a.0.cmp(&b.0));
    let zip = zipsec::zip_bytes(&entries)?;
    fsutil::write_bytes(std::path::Path::new(&out_path.replace('\\', "/")), &zip)?;
    Ok((0, json!({
        "schema": "nf-evidence-package/1",
        "path": out_path,
        "sha256": sha256_hex(&zip),
        "bytes": zip.len() as u64,
        "package_id": package_id,
        "version": version,
        "artifact": manifest["artifact"].clone()
    })))
}

struct PackageParts {
    ev: Value,
    mf: Value,
    art: Vec<u8>,
    zip_sha: String,
}

fn read_package(path: &str) -> Result<PackageParts, CoreError> {
    let bytes = fsutil::read_bytes(std::path::Path::new(&path.replace('\\', "/")), crate::limits::limits().zip_max_total_unpacked_bytes)?;
    let entries = zipsec::read_zip_bytes_allow_artifact(&bytes)?;
    let mut evidence: Option<Value> = None;
    let mut manifest: Option<Value> = None;
    let mut artifact: Option<Vec<u8>> = None;
    for e in &entries {
        if e.name == "evidence.json" {
            evidence = Some(crate::canonical::parse_json_bytes(&e.data)?);
        } else if e.name == "manifest.json" {
            manifest = Some(crate::canonical::parse_json_bytes(&e.data)?);
        } else if e.name.starts_with("artifact/") {
            if artifact.is_some() {
                return Err(CoreError::new("NF-EVD-001").with_message("证据包含多个 artifact").with_exit(1));
            }
            artifact = Some(e.data.clone());
        }
    }
    Ok(PackageParts {
        ev: evidence.ok_or_else(|| CoreError::new("NF-EVD-001").with_message("证据包缺 evidence.json").with_exit(1))?,
        mf: manifest.ok_or_else(|| CoreError::new("NF-EVD-001").with_message("证据包缺 manifest.json").with_exit(1))?,
        art: artifact.ok_or_else(|| CoreError::new("NF-EVD-001").with_message("证据包缺 artifact").with_exit(1))?,
        zip_sha: sha256_hex(&bytes),
    })
}

fn check_manifest(parts: &PackageParts) -> Report {
    let mut report = verify_checks(&parts.ev, Some(&parts.art));
    let mf = &parts.mf;
    if mf.get("schema").and_then(|v| v.as_str()) != Some("nf-evidence-package/1") {
        report.error("NF-EVD-005", "$.manifest.schema", "包清单 schema 不是 nf-evidence-package/1");
    }
    let version = mf.get("version").and_then(|v| v.as_u64()).unwrap_or(0);
    if version == 0 {
        report.error("NF-EVD-005", "$.manifest.version", "包 version 必须 >=1");
    }
    if sha256_hex(&parts.art) != mf["artifact"]["sha256"].as_str().unwrap_or("") {
        report.error("NF-EVD-001", "$.manifest.artifact.sha256", "包内产物摘要与 manifest 不符");
    }
    if sha256_hex(&crate::canonical::canonical_bytes(&parts.ev).unwrap_or_default()) != mf["evidence_sha"].as_str().unwrap_or("") {
        report.error("NF-EVD-001", "$.manifest.evidence_sha", "包内证据摘要与 manifest 不符");
    }
    let package_id = mf.get("package_id").and_then(|v| v.as_str()).unwrap_or("");
    let expected = sha256_hex(
        format!(
            "{}:{}",
            mf["artifact"]["path"].as_str().unwrap_or(""),
            mf["artifact"]["sha256"].as_str().unwrap_or("")
        )
        .as_bytes(),
    );
    if package_id.is_empty() || package_id != expected {
        report.error("NF-EVD-005", "$.manifest.package_id", "package_id 与 artifact.path/sha 不匹配");
    }
    report
}

fn trust_load(path: Option<&str>) -> Result<Value, CoreError> {
    match path {
        None => Ok(json!({"schema": "nf-trust-store/1", "packages": {}})),
        Some(p) => {
            let normalized = p.replace('\\', "/");
            let path = std::path::Path::new(&normalized);
            if !path.exists() {
                return Ok(json!({"schema": "nf-trust-store/1", "packages": {}}));
            }
            let v = fsutil::load_json_file(path)?;
            if v.get("schema").and_then(|x| x.as_str()) != Some("nf-trust-store/1")
                || !v.get("packages").map(|x| x.is_object()).unwrap_or(false)
            {
                return Err(CoreError::new("NF-EVD-005").with_message("信任库不是 nf-trust-store/1").with_exit(1));
            }
            Ok(v)
        }
    }
}

fn trust_check(report: &mut Report, mf: &Value, zip_sha: &str, trust: &Value) {
    let pid = mf.get("package_id").and_then(|v| v.as_str()).unwrap_or("");
    let version = mf.get("version").and_then(|v| v.as_u64()).unwrap_or(0);
    let entry = trust.get("packages").and_then(|p| p.get(pid));
    if let Some(e) = entry {
        let tv = e.get("version").and_then(|v| v.as_u64()).unwrap_or(0);
        let ts = e.get("sha256").and_then(|v| v.as_str()).unwrap_or("");
        if version < tv {
            report.error("NF-EVD-004", "$.manifest.version", &format!("回滚：包版本 {version} < 已冻结 {tv}"));
        } else if version == tv && zip_sha != ts {
            report.error("NF-EVD-004", "$.manifest", "冻结：同版本包摘要与信任库不一致");
        }
    }
}

pub fn verify_package(req: &Value) -> OpOutcome {
    let path = opt_str(req, "package_path")?.ok_or_else(|| usage("evidence-verify-package 需要 package_path"))?;
    let parts = read_package(path)?;
    let mut report = check_manifest(&parts);
    let trust = trust_load(opt_str(req, "trust_path")?)?;
    trust_check(&mut report, &parts.mf, &parts.zip_sha, &trust);
    let (e, w, _) = report.counts();
    let result = json!({
        "schema": "nf-evidence-verify/1",
        "ok": e == 0,
        "errors": e,
        "warnings": w,
        "package": true,
        "package_id": parts.mf.get("package_id"),
        "version": parts.mf.get("version"),
        "trusted": opt_str(req, "trust_path")?.is_some()
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
    let path = opt_str(req, "package_path")?.ok_or_else(|| usage("evidence-freeze 需要 package_path"))?;
    let trust_path = opt_str(req, "trust_path")?.ok_or_else(|| usage("evidence-freeze 需要 trust_path"))?;
    let allow_rollback = req.get("allow_rollback").and_then(|v| v.as_bool()).unwrap_or(false);
    let parts = read_package(path)?;
    let report = check_manifest(&parts);
    if report.has_error() {
        return Ok((1, report.to_value()));
    }
    let pid = parts.mf.get("package_id").and_then(|v| v.as_str()).unwrap_or("").to_string();
    let version = parts.mf.get("version").and_then(|v| v.as_u64()).unwrap_or(0);
    let mut trust = trust_load(Some(trust_path))?;
    let existing = trust.get("packages").and_then(|p| p.get(&pid)).cloned();
    if let Some(e) = &existing {
        let tv = e.get("version").and_then(|v| v.as_u64()).unwrap_or(0);
        let ts = e.get("sha256").and_then(|v| v.as_str()).unwrap_or("");
        if version < tv && !allow_rollback {
            return Err(CoreError::new("NF-EVD-004")
                .with_message(format!("拒绝回滚：{version} < {tv}（需要 allow_rollback=true）"))
                .with_exit(1));
        }
        if version == tv && parts.zip_sha != ts {
            return Err(CoreError::new("NF-EVD-004").with_message("拒绝冻结替换：同版本但包摘要不同").with_exit(1));
        }
    }
    let frozen_at = opt_str(req, "created_at")?.unwrap_or("").to_string();
    let entry = json!({
        "version": version,
        "sha256": parts.zip_sha,
        "evidence_sha": parts.mf["evidence_sha"].clone(),
        "frozen_at": frozen_at
    });
    trust
        .as_object_mut()
        .unwrap()
        .get_mut("packages")
        .unwrap()
        .as_object_mut()
        .unwrap()
        .insert(pid.clone(), entry);
    fsutil::write_json_canonical(std::path::Path::new(&trust_path.replace('\\', "/")), &trust)?;
    Ok((0, json!({
        "schema": "nf-trust-store/1",
        "package_id": pid,
        "version": version,
        "sha256": parts.zip_sha,
        "trust_path": trust_path
    })))
}


pub fn evidence_create_op(req: &Value) -> OpOutcome { create(req) }
pub fn evidence_verify_op(req: &Value) -> OpOutcome { verify(req) }
pub fn evidence_pack_op(req: &Value) -> OpOutcome { pack(req) }
pub fn evidence_verify_package_op(req: &Value) -> OpOutcome { verify_package(req) }
pub fn evidence_freeze_op(req: &Value) -> OpOutcome { freeze(req) }
pub fn evidence_keygen_op(req: &Value) -> OpOutcome { keygen(req) }
