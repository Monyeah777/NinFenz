use super::*;

pub fn overlay_apply(req: &Value) -> OpOutcome {
    let base_root = resolve_path(req_str(req, "base_root")?);
    let overlay = req_value(req, "overlay")?;
    let out_dir = ensure_out_dir(req_str(req, "out_dir")?)?;
    if let Some(report) = schema_report(
        "nf-overlay",
        overlay,
        "NF-VAL-001",
        "L0",
        "overlay",
        &ref_id(overlay, "schema"),
    ) {
        return Ok((1, report));
    }
    let base_manifest = match load_manifest(&base_root)? {
        Some(m) => m,
        None => return Err(display_io("NF-E-004", "base_root/nf-pack.json")),
    };
    let base = overlay.get("base").cloned().unwrap_or(Value::Null);
    let computed_tree = dir_tree(&base_root)?;
    let mut problems: Vec<(String, String, String)> = Vec::new();
    if base.get("tree").and_then(|v| v.as_str()) != Some(computed_tree.as_str()) {
        problems.push((
            "NF-PCK-002".into(),
            "$.base.tree".into(),
            "overlay.base.tree 与 base_root 实况不符".into(),
        ));
    }
    if base.get("id").and_then(|v| v.as_str())
        != base_manifest.get("id").and_then(|v| v.as_str())
    {
        problems.push((
            "NF-PCK-002".into(),
            "$.base.id".into(),
            "overlay.base.id 与 base_root 清单不一致".into(),
        ));
    }
    if base.get("version").and_then(|v| v.as_str())
        != base_manifest.get("version").and_then(|v| v.as_str())
    {
        problems.push((
            "NF-PCK-002".into(),
            "$.base.version".into(),
            "overlay.base.version 与 base_root 清单不一致".into(),
        ));
    }
    if !problems.is_empty() {
        let mut report = Report::new("L0", overlay, "overlay", &ref_id(overlay, "schema"));
        for (code, path, msg) in &problems {
            report.error(code, path, msg);
        }
        return Ok((1, report.to_value()));
    }
    fsutil::copy_tree(&base_root, &out_dir)?;
    // 条款开关
    if let Some(items) = base_manifest.get("items").and_then(|v| v.as_array()) {
        for item in items {
            if item.get("kind").and_then(|v| v.as_str()) != Some("protocol") {
                continue;
            }
            let rel = item.get("path").and_then(|v| v.as_str()).unwrap_or("");
            let path = out_dir.join(rel.replace('/', std::path::MAIN_SEPARATOR_STR));
            if !path.is_file() {
                continue;
            }
            let mut doc = match fsutil::load_json_file(&path) {
                Ok(d) => d,
                Err(_) => continue,
            };
            let mut changed = false;
            if let Some(clauses) = doc.get_mut("clauses").and_then(|v| v.as_array_mut()) {
                for clause in clauses.iter_mut() {
                    let cid = clause
                        .get("id")
                        .and_then(|v| v.as_str())
                        .map(|s| s.to_string())
                        .unwrap_or_default();
                    if cid.is_empty() {
                        continue;
                    }
                    if let Some(ov) = overlay.get("clauses").and_then(|c| c.get(&cid)) {
                        if let Some(enabled) = ov.get("enabled").and_then(|v| v.as_bool()) {
                            clause["enabled"] = Value::Bool(enabled);
                            changed = true;
                        }
                        if let Some(pinned) = ov.get("text_sha256").and_then(|v| v.as_str()) {
                            let actual = clause
                                .get("text")
                                .and_then(|v| v.as_str())
                                .map(|t| sha256_hex(t.as_bytes()))
                                .unwrap_or_default();
                            if actual != pinned {
                                let mut report =
                                    Report::new("L0", overlay, "overlay", &ref_id(overlay, "schema"));
                                report.error(
                                    "NF-PCK-002",
                                    &format!("$.clauses.{}.text_sha256", cid),
                                    &format!("条款 {} 文本摘要与 base 实况不符", cid),
                                );
                                return Ok((1, report.to_value()));
                            }
                        }
                    }
                }
            }
            if changed {
                fsutil::write_json_canonical(&path, &doc)?;
            }
        }
    }
    // overlay 落盘
    crate::fsutil::write_json_canonical(&out_dir.join("overlay").join("nf-overlay.json"), overlay)?;
    // 自定义资产
    if let Some(assets) = overlay.get("custom_assets").and_then(|v| v.as_array()) {
        for (i, a) in assets.iter().enumerate() {
            let rel = a.get("path").and_then(|v| v.as_str()).unwrap_or("");
            if fsutil::validate_rel_path(rel).is_err() {
                return Err(CoreError::new("NF-PCK-002")
                    .with_message(format!("custom_assets[{i}].path 不安全：{rel}"))
                    .with_exit(3));
            }
            let src = base_root.join(rel.replace('/', std::path::MAIN_SEPARATOR_STR));
            if !src.is_file() {
                return Ok((
                    1,
                    failure_report(
                        "L0",
                        overlay,
                        "overlay",
                        "$",
                        "NF-PCK-002",
                        &format!("$.custom_assets[{i}].path"),
                        &format!("自定义资产源文件不存在：{rel}"),
                    ),
                ));
            }
            let bytes = std::fs::read(&src).map_err(|e| {
                CoreError::new("NF-E-004")
                    .with_message(format!("读自定义资产失败: {e}"))
                    .with_exit(2)
            })?;
            let want = a.get("sha256").and_then(|v| v.as_str()).unwrap_or("");
            if sha256_hex(&bytes) != want {
                return Ok((
                    1,
                    failure_report(
                        "L0",
                        overlay,
                        "overlay",
                        "$",
                        "NF-PCK-002",
                        &format!("$.custom_assets[{i}].sha256"),
                        &format!("自定义资产摘要不符：{rel}"),
                    ),
                ));
            }
            fsutil::write_bytes(
                &out_dir.join(rel.replace('/', std::path::MAIN_SEPARATOR_STR)),
                &bytes,
            )?;
        }
    }
    let tree = dir_tree(&out_dir)?;
    let _ = canonical_bytes(&Value::Null);
    let _ = float_issue;
    let _ = req_value;
    Ok((0, json!({"tree": tree, "base": base})))
}
