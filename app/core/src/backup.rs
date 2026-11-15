//! nf-backup/1：pack 应用前备份清单（本地数据目录，不进 canonical 产物链）。
//! 字段：schema/tree/files[{path,sha256}]/created_at?；created_at 由调用方显式给（人读，可缺）。
//! tree 口径与 pack-hash 一致（排除 manifest/签名）；files 列出全部文件（含 nf-pack.json，便于完整恢复）。

use crate::canonical::{canonical_bytes, sha256_hex};
use crate::error::CoreError;
use crate::fsutil;
use crate::schema::SchemaIssue;
use serde_json::{json, Map, Value};
use std::path::Path;

pub fn build(root: &Path, created_at: Option<&str>) -> Result<Value, CoreError> {
    let entries = fsutil::walk_files(root)?;
    let mut files: Vec<Value> = Vec::new();
    for e in &entries {
        let bytes = std::fs::read(&e.abs).map_err(|err| {
            CoreError::new("NF-E-004")
                .with_message(format!("读取备份文件失败 {}: {err}", e.abs.display()))
                .with_exit(2)
        })?;
        files.push(json!({
            "path": e.rel,
            "sha256": sha256_hex(&bytes),
        }));
    }
    files.sort_by(|a, b| a["path"].as_str().cmp(&b["path"].as_str()));
    let tree = fsutil::pack_items(root, None)?.tree;
    let mut m = Map::new();
    m.insert("schema".into(), Value::String("nf-backup/1".into()));
    if let Some(at) = created_at {
        m.insert("created_at".into(), Value::String(at.to_string()));
    }
    m.insert("tree".into(), Value::String(tree));
    m.insert("files".into(), Value::Array(files));
    Ok(Value::Object(m))
}

pub fn validate(backup: &Value) -> Vec<SchemaIssue> {
    crate::schema::validate("nf-backup", backup)
}

/// 写备份清单到指定路径（canonical 字节，无尾换行）；返回清单本身。
pub fn write(root: &Path, out_path: &Path, created_at: Option<&str>) -> Result<Value, CoreError> {
    let backup = build(root, created_at)?;
    let issues = validate(&backup);
    if !issues.is_empty() {
        return Err(CoreError::new("NF-E-002")
            .with_message(format!(
                "备份清单未通过 nf-backup schema 自检: {}",
                crate::schema::first_issue_text(&issues)
            ))
            .with_exit(3));
    }
    fsutil::write_bytes(out_path, &canonical_bytes(&backup)?)?;
    Ok(backup)
}
