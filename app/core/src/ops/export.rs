//! 导出：md / zip / json；docx/pdf 走导出器探测（缺 → NF-EXP-004 exit 4）。
//! zip 确定性：entry 按 path 码点升序、mtime 1980-01-01、权限 0644、无 extra field。

use crate::error::{CoreError, OpOutcome};
use crate::ops::{ensure_out_dir, opt_bool, opt_str, req_str, usage};
use crate::report::failure_report;
use crate::zipsec;
use serde_json::{json, Value};

fn is_hex64(s: &str) -> bool {
    s.len() == 64 && s.chars().all(|c| c.is_ascii_hexdigit() && !c.is_ascii_uppercase())
}

fn valid_rel_path(p: &str) -> bool {
    crate::fsutil::validate_rel_path(p).is_ok()
}

fn digest_or_empty(v: Option<&Value>) -> Option<String> {
    v.and_then(|x| x.as_str())
        .filter(|s| is_hex64(s))
        .map(|s| s.to_string())
}

/// 来源摘要：请求显式 > 旧 sources[{kind,ref,digest}] > result.meta > 空串摘要占位。
fn resolve_digest(
    req: &Value,
    key: &str,
    kind: &str,
    result: Option<&Value>,
) -> String {
    if let Some(d) = digest_or_empty(req.get(key)) {
        return d;
    }
    if let Some(arr) = req.get("sources").and_then(|v| v.as_array()) {
        for s in arr {
            if s.get("kind").and_then(|v| v.as_str()) == Some(kind) {
                if let Some(d) = digest_or_empty(s.get("digest")) {
                    return d;
                }
            }
        }
    }
    if let Some(result) = result {
        if let Some(meta) = result.get("meta") {
            let key_meta = format!("{key}");
            if let Some(d) = digest_or_empty(meta.get(&key_meta)) {
                return d;
            }
        }
    }
    crate::canonical::sha256_hex(b"")
}

fn markdown_digest_of(req: &Value, result: Option<&Value>, markdown: Option<&str>) -> String {
    if let Some(d) = digest_or_empty(req.get("markdown_digest")) {
        return d;
    }
    if let Some(arr) = req.get("sources").and_then(|v| v.as_array()) {
        for s in arr {
            if s.get("kind").and_then(|v| v.as_str()) == Some("markdown") {
                if let Some(d) = digest_or_empty(s.get("digest")) {
                    return d;
                }
            }
        }
    }
    if let Some(result) = result {
        if let Some(meta) = result.get("meta") {
            if let Some(d) = digest_or_empty(meta.get("markdown_digest")) {
                return d;
            }
        }
    }
    match markdown {
        Some(md) => crate::canonical::sha256_hex(md.as_bytes()),
        None => match result {
            Some(r) => crate::canonical::sha256_hex(
                &crate::canonical::canonical_bytes(r).unwrap_or_default(),
            ),
            None => crate::canonical::sha256_hex(b""),
        },
    }
}

fn export_failure(format: &str, code: &str, path: &str, message: &str) -> Value {
    failure_report(
        "L0",
        &Value::String(format.to_string()),
        "export",
        format,
        code,
        path,
        message,
    )
}

pub fn export(req: &Value) -> OpOutcome {
    let format = req_str(req, "format")?;
    let out_dir = req_str(req, "out_dir")?;
    if format == "pdf" {
        return Err(CoreError::new("NF-EXP-004")
            .with_message("PDF 导出未内置：用平台打印另存为 PDF（Android PrintManager / 桌面 javax.print），核心不产 PDF（OPEN）")
            .with_exit(4));
    }
    if !matches!(format, "md" | "zip" | "json" | "docx" | "skill") {
        return Err(CoreError::new("NF-E-002")
            .with_message(format!("未知导出格式 {format}（只支持 md/zip/json）"))
            .with_exit(3));
    }
    let markdown = opt_str(req, "markdown")?;
    let result = match req.get("result") {
        None | Some(Value::Null) => None,
        Some(v @ Value::Object(_)) => Some(v.clone()),
        Some(_) => return Err(usage("请求字段 result 必须是 object")),
    };
    if markdown.is_none() && result.is_none() {
        return Err(usage("请求必须给 markdown 或 result"));
    }
    let dir = ensure_out_dir(out_dir)?;

    // 额外文件（可选扩展口，用于 zip）
    let mut extra: Vec<(String, Vec<u8>)> = Vec::new();
    if let Some(arr) = req.get("files") {
        let arr = arr
            .as_array()
            .ok_or_else(|| usage("请求字段 files 必须是数组"))?;
        for (i, f) in arr.iter().enumerate() {
            let p = f
                .get("path")
                .and_then(|v| v.as_str())
                .ok_or_else(|| usage(format!("files[{i}].path 缺失")))?;
            if !valid_rel_path(p) {
                return Err(CoreError::new("NF-EXP-002")
                    .with_message(format!("导出路径越界/不安全：{p}"))
                    .at(format!("$.files[{i}].path"))
                    .with_exit(3));
            }
            let content = f
                .get("content")
                .and_then(|v| v.as_str())
                .ok_or_else(|| usage(format!("files[{i}].content 缺失（只支持文本文件）")))?;
            extra.push((p.to_string(), content.as_bytes().to_vec()));
        }
        extra.sort_by(|a, b| a.0.cmp(&b.0));
        for w in extra.windows(2) {
            if w[0].0 == w[1].0 {
                return Ok((
                    1,
                    export_failure(
                        format,
                        "NF-EXP-003",
                        &format!("$.files.{}", w[0].0),
                        &format!("zip entry 重名：{}", w[0].0),
                    ),
                ));
            }
        }
    }

    let source = json!({
        "plan_digest": resolve_digest(req, "plan_digest", "plan", result.as_ref()),
        "spec_digest": resolve_digest(req, "spec_digest", "spec", result.as_ref()),
        "markdown_digest": markdown_digest_of(req, result.as_ref(), markdown),
    });
    let mut files: Vec<Value> = Vec::new();
    match format {
        "md" => {
            let content = markdown
                .map(|s| s.to_string())
                .or_else(|| {
                    result
                        .as_ref()
                        .and_then(|r| r.get("markdown"))
                        .and_then(|v| v.as_str())
                        .map(|s| s.to_string())
                })
                .unwrap_or_default();
            let bytes = content.into_bytes();
            crate::fsutil::write_bytes(&dir.join("result.md"), &bytes)?;
            files.push(json!({
                "name": "result.md",
                "sha256": crate::canonical::sha256_hex(&bytes),
                "bytes": bytes.len() as u64,
            }));
        }
        "json" => {
            let value = match &result {
                Some(r) => r.clone(),
                None => json!({"markdown": markdown.unwrap_or("")}),
            };
            let bytes = crate::canonical::canonical_bytes(&value)?;
            crate::fsutil::write_bytes(&dir.join("result.json"), &bytes)?;
            files.push(json!({
                "name": "result.json",
                "sha256": crate::canonical::sha256_hex(&bytes),
                "bytes": bytes.len() as u64,
            }));
        }
        "zip" => {
            let mut entries: Vec<(String, Vec<u8>)> = Vec::new();
            if let Some(r) = &result {
                if let Some(md) = r.get("markdown").and_then(|v| v.as_str()) {
                    entries.push(("result.md".to_string(), md.as_bytes().to_vec()));
                }
                if let Some(meta) = r.get("meta") {
                    let bytes = crate::canonical::canonical_bytes(meta)?;
                    entries.push(("result.meta.json".to_string(), bytes));
                }
            } else if let Some(md) = markdown {
                entries.push(("result.md".to_string(), md.as_bytes().to_vec()));
            }
            for (p, b) in extra {
                if entries.iter().any(|e| e.0 == p) {
                    return Ok((
                        1,
                        export_failure(
                            format,
                            "NF-EXP-003",
                            &format!("$.files.{p}"),
                            &format!("zip entry 重名：{p}"),
                        ),
                    ));
                }
                entries.push((p, b));
            }
            entries.sort_by(|a, b| a.0.cmp(&b.0));
            let bytes = zipsec::zip_bytes(&entries)?;
            crate::fsutil::write_bytes(&dir.join("result.zip"), &bytes)?;
            files.push(json!({
                "name": "result.zip",
                "sha256": crate::canonical::sha256_hex(&bytes),
                "bytes": bytes.len() as u64,
            }));
        }
        "docx" => {
            let content = markdown
                .map(|s| s.to_string())
                .or_else(|| {
                    result
                        .as_ref()
                        .and_then(|r| r.get("markdown"))
                        .and_then(|v| v.as_str())
                        .map(|s| s.to_string())
                })
                .unwrap_or_default();
            let title = opt_str(req, "title")?.unwrap_or("NF Export");
            let bytes = crate::docx::build_docx(&content, title)?;
            crate::fsutil::write_bytes(&dir.join("result.docx"), &bytes)?;
            files.push(json!({
                "name": "result.docx",
                "sha256": crate::canonical::sha256_hex(&bytes),
                "bytes": bytes.len() as u64,
            }));
        }
        "skill" => {
            let md = markdown.or_else(|| {
                result
                    .as_ref()
                    .and_then(|r| r.get("markdown"))
                    .and_then(|v| v.as_str())
            });
            let meta = result.as_ref().and_then(|r| r.get("meta"));
            let project_id = opt_str(req, "project_id")?.unwrap_or("");
            let title = opt_str(req, "title")?.unwrap_or("");
            let bytes = crate::skillpack::build_skill_pack(
                project_id,
                title,
                md,
                meta,
                source["plan_digest"].as_str().unwrap_or(""),
                source["spec_digest"].as_str().unwrap_or(""),
                source["markdown_digest"].as_str().unwrap_or(""),
            )?;
            crate::fsutil::write_bytes(&dir.join("result.skill.zip"), &bytes)?;
            files.push(json!({
                "name": "result.skill.zip",
                "sha256": crate::canonical::sha256_hex(&bytes),
                "bytes": bytes.len() as u64,
            }));
        }
        _ => unreachable!(),
    }

    let manifest = json!({
        "schema": "nf-export-manifest/1",
        "format": format,
        "files": files,
        "source": source,
    });
    let issues = crate::schema::validate("nf-export-manifest", &manifest);
    if !issues.is_empty() {
        return Err(CoreError::new("NF-E-002")
            .with_message(format!(
                "导出清单未通过 nf-export-manifest schema 自检: {}",
                crate::schema::first_issue_text(&issues)
            ))
            .with_exit(3));
    }
    if opt_bool(req, "manifest")? {
        crate::fsutil::write_json_canonical(&dir.join("manifest.json"), &manifest)?;
    }
    Ok((0, manifest))
}
