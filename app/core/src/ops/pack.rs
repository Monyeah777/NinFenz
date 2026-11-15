//! Pack 操作：pack-hash / pack-verify（以及 update 复用的清单核验）。

use crate::canonical::{digest_allow_float, digest_with_excludes};
use crate::error::{CoreError, OpOutcome};
use crate::fsutil;
use crate::ops::{float_issue, ref_id, req_str, resolve_path, schema_report};
use crate::report::Report;
use serde_json::{json, Value};
use std::path::Path;

#[derive(Clone, Debug)]
pub struct ManifestVerify {
    pub items: Vec<Value>,
    pub tree: String,
    pub issues: Vec<(String, String, String)>, // (code, path, message)
    pub count: u64,
}

pub fn parse_semver(v: &str) -> Option<(u64, u64, u64)> {
    let mut it = v.split('.');
    let a = it.next()?.parse().ok()?;
    let b = it.next()?.parse().ok()?;
    let c = it.next()?.parse().ok()?;
    if it.next().is_some() {
        return None;
    }
    Some((a, b, c))
}

pub fn manifest_digest(manifest: &Value) -> String {
    match digest_with_excludes(manifest, &[]) {
        Ok(d) => d,
        Err(_) => digest_allow_float(manifest),
    }
}

/// 逐 item 核验 manifest 与 root 的一致性（pack-verify / pack-diff / pack-merge 共用）。
pub fn verify_manifest(root: &Path, manifest: &Value) -> Result<ManifestVerify, CoreError> {
    let computed = fsutil::pack_items(root, Some(manifest))?;
    let mut issues: Vec<(String, String, String)> = Vec::new();
    let declared_tree = manifest
        .get("hashes")
        .and_then(|h| h.get("tree"))
        .and_then(|v| v.as_str())
        .unwrap_or("");
    if declared_tree != computed.tree {
        issues.push((
            "NF-PCK-002".into(),
            "$.hashes.tree".into(),
            format!("tree 摘要不符：清单 {declared_tree}，实际 {}", computed.tree),
        ));
    }
    let declared_count = manifest
        .get("hashes")
        .and_then(|h| h.get("count"))
        .and_then(|v| v.as_u64())
        .unwrap_or(0);
    if declared_count != computed.items.len() as u64 {
        issues.push((
            "NF-PCK-002".into(),
            "$.hashes.count".into(),
            format!(
                "count 不符：清单 {declared_count}，实际 {}",
                computed.items.len()
            ),
        ));
    }
    let mut computed_by_path: std::collections::BTreeMap<String, Value> =
        std::collections::BTreeMap::new();
    for item in &computed.items {
        let path = item["path"].as_str().unwrap_or("").to_string();
        computed_by_path.insert(path, item.clone());
    }
    let mut seen = std::collections::BTreeSet::new();
    if let Some(items) = manifest.get("items").and_then(|v| v.as_array()) {
        for (i, item) in items.iter().enumerate() {
            let path = item.get("path").and_then(|v| v.as_str()).unwrap_or("");
            if !seen.insert(path.to_string()) {
                issues.push((
                    "NF-PCK-001".into(),
                    format!("$.items[{i}].path"),
                    format!("manifest item path 重复：{path}"),
                ));
                continue;
            }
            match computed_by_path.get(path) {
                Some(actual) => {
                    let sha = item.get("sha256").and_then(|v| v.as_str()).unwrap_or("");
                    let size = item.get("size").and_then(|v| v.as_u64()).unwrap_or(0);
                    if sha != actual["sha256"].as_str().unwrap_or("") {
                        issues.push((
                            "NF-PCK-002".into(),
                            format!("$.items[{i}].sha256"),
                            format!("item {path} sha256 不符"),
                        ));
                    }
                    if size != actual["size"].as_u64().unwrap_or(0) {
                        issues.push((
                            "NF-PCK-002".into(),
                            format!("$.items[{i}].size"),
                            format!("item {path} size 不符"),
                        ));
                    }
                }
                None => issues.push((
                    "NF-PCK-002".into(),
                    format!("$.items[{i}].path"),
                    format!("manifest 声明的 item 不存在：{path}"),
                )),
            }
        }
    }
    for (path, _) in &computed_by_path {
        if !seen.contains(path) {
            issues.push((
                "NF-PCK-002".into(),
                "$.items".into(),
                format!("root 中存在未登记 item：{path}"),
            ));
        }
    }
    let count = computed.items.len() as u64;
    Ok(ManifestVerify {
        items: computed.items,
        tree: computed.tree,
        issues,
        count,
    })
}

pub fn pack_hash(req: &Value) -> OpOutcome {
    let root = resolve_path(req_str(req, "root")?);
    let manifest_path = root.join("nf-pack.json");
    let manifest = if manifest_path.is_file() {
        Some(fsutil::load_json_file(&manifest_path)?)
    } else {
        None
    };
    let computed = fsutil::pack_items(&root, manifest.as_ref())?;
    let result = json!({
        "items": computed.items,
        "hashes": {
            "tree": computed.tree,
            "count": computed.count,
        }
    });
    Ok((0, result))
}

/// pack 的 compat.min_app_version 检查（CONTRACT §8）。
pub fn check_min_app_version(manifest: &Value, report: &mut Report) {
    let min = manifest
        .get("compat")
        .and_then(|c| c.get("min_app_version"))
        .and_then(|v| v.as_str())
        .unwrap_or("0.0.0");
    if let (Some(want), Some(have)) = (parse_semver(min), parse_semver(crate::CORE_VERSION)) {
        if have < want {
            report.error(
                "NF-PCK-001",
                "$.compat.min_app_version",
                &format!(
                    "pack 要求 APP 版本 >= {min}，当前 {}（拒绝加载）",
                    crate::CORE_VERSION
                ),
            );
        }
    }
}

fn check_requires(root: &Path, manifest: &Value, report: &mut Report) {
    let requires = match manifest.get("requires").and_then(|v| v.as_array()) {
        Some(r) => r,
        None => return,
    };
    let self_id = manifest.get("id").and_then(|v| v.as_str()).unwrap_or("");
    let mut seen = std::collections::BTreeSet::new();
    for (i, dep) in requires.iter().enumerate() {
        let id = dep.get("id").and_then(|v| v.as_str()).unwrap_or("");
        let min = dep.get("min").and_then(|v| v.as_str()).unwrap_or("0.0.0");
        let max = dep.get("max").and_then(|v| v.as_str());
        if id == self_id {
            report.error(
                "NF-PCK-005",
                &format!("$.requires[{i}].id"),
                "requires 不允许引用自身",
            );
        }
        if !seen.insert(id.to_string()) {
            report.error(
                "NF-PCK-005",
                &format!("$.requires[{i}].id"),
                &format!("requires 重复依赖 {id}"),
            );
            continue;
        }
        let dep_root = match root.parent() {
            Some(p) => p.join(id),
            None => continue,
        };
        if !dep_root.is_dir() {
            report.warn(
                "NF-PCK-005",
                &format!("$.requires[{i}]"),
                &format!("依赖 {id} 未在本机安装，已跳过版本解析"),
            );
            continue;
        }
        let min_v = parse_semver(min).unwrap_or((0, 0, 0));
        let max_v = max.and_then(parse_semver);
        let mut found = false;
        let mut candidates: Vec<String> = Vec::new();
        if let Ok(rd) = std::fs::read_dir(&dep_root) {
            for ent in rd.flatten() {
                let version = ent.file_name().to_string_lossy().to_string();
                if let Some(v) = parse_semver(&version) {
                    candidates.push(version.clone());
                    let above_min = v >= min_v;
                    let below_max = max_v.map(|m| v <= m).unwrap_or(true);
                    if above_min && below_max {
                        found = true;
                    }
                }
            }
        }
        candidates.sort();
        if !found {
            report.error(
                "NF-PCK-005",
                &format!("$.requires[{i}]"),
                &format!(
                    "依赖 {id} 版本不满足要求（min={min}，max={}，本机候选: {}）",
                    max.unwrap_or("∞"),
                    candidates.join(",")
                ),
            );
        }
    }
}

pub fn pack_verify(req: &Value) -> OpOutcome {
    let root = resolve_path(req_str(req, "root")?);
    let manifest_path = root.join("nf-pack.json");
    let manifest = if manifest_path.is_file() {
        fsutil::load_json_file(&manifest_path)?
    } else {
        let report = crate::report::failure_report(
            "L0",
            &Value::Null,
            "pack",
            "$",
            "NF-PCK-001",
            "$.nf-pack.json",
            "缺少 nf-pack.json 清单",
        );
        return Ok((1, report));
    };
    let mut report = Report::new("L0", &manifest, "pack", &ref_id(&manifest, "id"));
    if let Some(issues) = {
        let v = crate::schema::validate("nf-pack", &manifest);
        if v.is_empty() {
            None
        } else {
            Some(v)
        }
    } {
        report.extend_schema_issues("NF-PCK-001", &issues);
    }
    float_issue(&mut report, &manifest, "NF-PCK-001");
    check_min_app_version(&manifest, &mut report);
    match verify_manifest(&root, &manifest) {
        Ok(v) => {
            for (code, path, message) in &v.issues {
                report.error(code, path, message);
            }
        }
        Err(e) => return Err(e),
    }
    check_requires(&root, &manifest, &mut report);
    Ok((0, report.to_value()))
}

/// 目录的 tree 摘要（不含 nf-pack.json / 签名件）。
pub fn dir_tree(root: &Path) -> Result<String, CoreError> {
    Ok(fsutil::pack_items(root, None)?.tree)
}

/// 读 manifest，缺文件时返回错误报告所需信息。
pub fn load_manifest(root: &Path) -> Result<Option<Value>, CoreError> {
    let p = root.join("nf-pack.json");
    if p.is_file() {
        Ok(Some(fsutil::load_json_file(&p)?))
    } else {
        Ok(None)
    }
}

pub fn schema_report_pack(manifest: &Value) -> Option<Value> {
    schema_report(
        "nf-pack",
        manifest,
        "NF-PCK-001",
        "L0",
        "pack",
        &ref_id(manifest, "id"),
    )
}

/// update 类 op 需要「目录 + 清单 + 核验」；返回 (manifest, tree)。
pub fn load_and_verify(root: &Path) -> Result<(Value, String), CoreError> {
    let manifest = match load_manifest(root)? {
        Some(m) => m,
        None => {
            return Err(CoreError::new("NF-E-004")
                .with_message(format!("目录缺少 nf-pack.json：{}", root.display()))
                .with_exit(2))
        }
    };
    let v = verify_manifest(root, &manifest)?;
    if !v.issues.is_empty() {
        let (code, path, message) = &v.issues[0];
        return Err(CoreError::new(code)
            .with_message(format!("{path}: {message}"))
            .at(path.clone())
            .with_exit(1));
    }
    Ok((manifest, v.tree))
}
