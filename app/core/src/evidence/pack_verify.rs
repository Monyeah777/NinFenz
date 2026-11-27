use super::*;

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

pub(crate) struct PackageParts {
    ev: Value,
    mf: Value,
    art: Vec<u8>,
    zip_sha: String,
}

pub(crate) fn read_package(path: &str) -> Result<PackageParts, CoreError> {
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

pub(crate) fn check_manifest(parts: &PackageParts) -> Report {
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

pub(crate) fn trust_load(path: Option<&str>) -> Result<Value, CoreError> {
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

pub(crate) fn trust_check(report: &mut Report, mf: &Value, zip_sha: &str, trust: &Value) {
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
