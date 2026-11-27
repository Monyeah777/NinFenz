use super::*;

pub fn pack_diff(req: &Value) -> OpOutcome {
    let old_root = resolve_path(req_str(req, "old_root")?);
    let new_root = resolve_path(req_str(req, "new_root")?);
    let old_manifest = match load_manifest(&old_root)? {
        Some(m) => m,
        None => {
            return Ok((
                1,
                failure_report(
                    "L0",
                    &Value::Null,
                    "pack",
                    "old",
                    "NF-PCK-001",
                    "$.old_root.nf-pack.json",
                    "old_root 缺少 nf-pack.json",
                ),
            ))
        }
    };
    let new_manifest = match load_manifest(&new_root)? {
        Some(m) => m,
        None => {
            return Ok((
                1,
                failure_report(
                    "L0",
                    &Value::Null,
                    "pack",
                    "new",
                    "NF-PCK-001",
                    "$.new_root.nf-pack.json",
                    "new_root 缺少 nf-pack.json",
                ),
            ))
        }
    };
    for (name, manifest) in [("old", &old_manifest), ("new", &new_manifest)] {
        if let Some(report) = schema_report(
            "nf-pack",
            manifest,
            "NF-PCK-001",
            "L0",
            "pack",
            &ref_id(manifest, "id"),
        ) {
            return Ok((1, report));
        }
        let v = verify_manifest(if name == "old" { &old_root } else { &new_root }, manifest)?;
        if !v.issues.is_empty() {
            let mut report = Report::new("L0", manifest, "pack", &ref_id(manifest, "id"));
            for (code, path, message) in &v.issues {
                report.error(code, path, message);
            }
            return Ok((1, report.to_value()));
        }
    }
    let old_id = old_manifest.get("id").and_then(|v| v.as_str()).unwrap_or("");
    let new_id = new_manifest.get("id").and_then(|v| v.as_str()).unwrap_or("");
    if old_id != new_id {
        return Ok((
            1,
            failure_report(
                "L0",
                &old_manifest,
                "pack",
                old_id,
                "NF-PCK-001",
                "$.id",
                "old_root 与 new_root 的 pack id 不一致",
            ),
        ));
    }
    let old_items = manifest_items(&old_manifest);
    let new_items = manifest_items(&new_manifest);
    let old_tree = dir_tree(&old_root)?;
    let new_tree = dir_tree(&new_root)?;

    let mut added: Vec<Value> = Vec::new();
    let mut removed: Vec<Value> = Vec::new();
    let mut modified: Vec<Value> = Vec::new();
    for (path, item) in &new_items {
        match old_items.get(path) {
            None => added.push(json!({
                "path": path,
                "sha256": item.get("sha256").cloned().unwrap_or(Value::Null),
                "size": item.get("size").cloned().unwrap_or(Value::Null),
            })),
            Some(old) => {
                let os = old.get("sha256").and_then(|v| v.as_str()).unwrap_or("");
                let ns = item.get("sha256").and_then(|v| v.as_str()).unwrap_or("");
                if os != ns {
                    modified.push(json!({
                        "path": path,
                        "sha256": os,
                        "new_sha256": ns,
                    }));
                }
            }
        }
    }
    for (path, item) in &old_items {
        if !new_items.contains_key(path) {
            removed.push(json!({
                "path": path,
                "sha256": item.get("sha256").cloned().unwrap_or(Value::Null),
            }));
        }
    }
    added.sort_by(|a, b| a["path"].as_str().cmp(&b["path"].as_str()));
    removed.sort_by(|a, b| a["path"].as_str().cmp(&b["path"].as_str()));
    modified.sort_by(|a, b| a["path"].as_str().cmp(&b["path"].as_str()));

    let mut breaking = !removed.is_empty();
    for m in &modified {
        let path = m["path"].as_str().unwrap_or("");
        let kind = new_items
            .get(path)
            .and_then(|i| i.get("kind"))
            .and_then(|v| v.as_str())
            .unwrap_or("");
        if kind == "protocol" || kind == "md-spec" {
            breaking = true;
        }
    }
    let old_v = old_manifest.get("version").and_then(|v| v.as_str()).unwrap_or("0.0.0");
    let new_v = new_manifest.get("version").and_then(|v| v.as_str()).unwrap_or("0.0.0");
    if let (Some(a), Some(b)) = (parse_semver(old_v), parse_semver(new_v)) {
        if a.0 != b.0 {
            breaking = true;
        }
    }

    let projects: Vec<String> = req
        .get("projects")
        .and_then(|v| v.as_array())
        .map(|arr| {
            let mut ids: Vec<String> = arr
                .iter()
                .filter(|p| {
                    p.get("refs")
                        .and_then(|r| r.get("base_pack"))
                        .and_then(|b| b.get("id"))
                        .and_then(|v| v.as_str())
                        == Some(old_id)
                })
                .filter_map(|p| p.get("id").and_then(|v| v.as_str()).map(|s| s.to_string()))
                .collect();
            ids.sort();
            ids.dedup();
            ids
        })
        .unwrap_or_default();

    let mut overlay_keys: BTreeSet<String> = BTreeSet::new();
    let touched: Vec<&Value> = added.iter().chain(removed.iter()).chain(modified.iter()).collect();
    for item in touched {
        let path = item["path"].as_str().unwrap_or("");
        let kind = if let Some(i) = new_items.get(path) {
            i.get("kind")
        } else {
            old_items.get(path).and_then(|i| i.get("kind"))
        }
        .and_then(|v| v.as_str())
        .unwrap_or("");
        match kind {
            "protocol" => {
                overlay_keys.insert("clauses".into());
                overlay_keys.insert("params".into());
            }
            "pipeline" => {
                overlay_keys.insert("presets".into());
            }
            "assets" => {
                overlay_keys.insert("custom_assets".into());
            }
            _ => {}
        }
    }

    let merge_actions: Vec<Value> = added
        .iter()
        .map(|i| json!({"kind": "take_new", "path": i["path"], "reason": "new file"}))
        .chain(modified.iter().map(|i| {
            json!({"kind": "merge", "path": i["path"], "reason": "content changed"})
        }))
        .chain(removed.iter().map(|i| {
            json!({"kind": "defer", "path": i["path"], "reason": "removed upstream"})
        }))
        .collect();
    let update = json!({
        "schema": "nf-pack-update/1",
        "from": {"id": old_id, "version": old_v, "tree": old_tree},
        "to": {"id": new_id, "version": new_v, "tree": new_tree},
        "changes": {"added": added, "removed": removed, "modified": modified},
        "impact": {
            "breaking": breaking,
            "projects": projects,
            "overlay_keys": overlay_keys.into_iter().collect::<Vec<String>>(),
        },
        "merge": {"actions": merge_actions, "on_conflict": "require_user"},
        "conflicts": [],
        "policy": {"auto_merge": true, "backup": true, "rollback": true},
    });
    if let Some(report) = schema_report(
        "nf-pack-update",
        &update,
        "NF-PCK-001",
        "L0",
        "pack-update",
        "$",
    ) {
        return Ok((1, report));
    }
    Ok((0, update))
}
