use super::*;

pub fn pack_merge(req: &Value) -> OpOutcome {
    let update = req_value(req, "update")?;
    let base_root = resolve_path(req_str(req, "base_root")?);
    let new_root = resolve_path(req_str(req, "new_root")?);
    let out_dir = ensure_out_dir(req_str(req, "out_dir")?)?;
    if let Some(report) = schema_report(
        "nf-pack-update",
        update,
        "NF-PCK-001",
        "L0",
        "pack-update",
        "$",
    ) {
        return Ok((1, report));
    }
    let base_manifest = match load_manifest(&base_root)? {
        Some(m) => m,
        None => return Err(display_io("NF-E-004", "base_root/nf-pack.json")),
    };
    let new_manifest = match load_manifest(&new_root)? {
        Some(m) => m,
        None => return Err(display_io("NF-E-004", "new_root/nf-pack.json")),
    };
    let base_tree = dir_tree(&base_root)?;
    let new_tree = dir_tree(&new_root)?;
    let from_tree = update["from"]["tree"].as_str().unwrap_or("");
    let to_tree = update["to"]["tree"].as_str().unwrap_or("");
    if from_tree != base_tree || to_tree != new_tree {
        return Err(CoreError::new("NF-PCK-004")
            .with_message(format!(
                "base/new tree 与 update.from/to 不符：base {base_tree} vs {from_tree}，new {new_tree} vs {to_tree}"
            ))
            .with_exit(3));
    }
    // changes 交叉核验
    let old_items = manifest_items(&base_manifest);
    let new_items = manifest_items(&new_manifest);
    let computed_added: BTreeSet<String> = new_items
        .keys()
        .filter(|p| !old_items.contains_key(*p))
        .cloned()
        .collect();
    let computed_removed: BTreeSet<String> = old_items
        .keys()
        .filter(|p| !new_items.contains_key(*p))
        .cloned()
        .collect();
    let declared_added: BTreeSet<String> = update["changes"]["added"]
        .as_array()
        .map(|a| {
            a.iter()
                .filter_map(|x| x["path"].as_str().map(|s| s.to_string()))
                .collect()
        })
        .unwrap_or_default();
    let declared_removed: BTreeSet<String> = update["changes"]["removed"]
        .as_array()
        .map(|a| {
            a.iter()
                .filter_map(|x| x["path"].as_str().map(|s| s.to_string()))
                .collect()
        })
        .unwrap_or_default();
    if computed_added != declared_added || computed_removed != declared_removed {
        return Err(CoreError::new("NF-PCK-004")
            .with_message("update.changes 与 base/new 目录实况不符")
            .with_exit(3));
    }
    let overlay = match req.get("overlay") {
        None | Some(Value::Null) => None,
        Some(v @ Value::Object(_)) => {
            if let Some(report) =
                schema_report("nf-overlay", v, "NF-VAL-001", "L0", "overlay", &ref_id(v, "id"))
            {
                return Ok((1, report));
            }
            Some(v.clone())
        }
        Some(_) => return Err(crate::ops::usage("请求字段 overlay 必须是 object")),
    };
    let conflicts = build_conflicts(
        &base_root,
        &new_root,
        &old_items,
        &new_items,
        overlay.as_ref(),
    );
    let decisions = match req.get("decisions") {
        None | Some(Value::Null) => Map::new(),
        Some(Value::Object(m)) => m.clone(),
        Some(_) => return Err(crate::ops::usage("请求字段 decisions 必须是 object")),
    };
    let mut unresolved: Vec<Value> = Vec::new();
    let mut effective: BTreeMap<String, String> = BTreeMap::new();
    for c in &conflicts {
        let decision = decisions
            .get(&c.id)
            .and_then(|v| v.as_str())
            .unwrap_or("defer");
        if !matches!(decision, "keep_mine" | "take_new" | "defer") {
            return Err(crate::ops::usage(format!(
                "decisions[{}] 必须是 keep_mine/take_new/defer",
                c.id
            )));
        }
        if decision == "defer" {
            unresolved.push(c.value.clone());
        }
        effective.insert(c.id.clone(), decision.to_string());
    }
    if !unresolved.is_empty() {
        let mut report = Report::new("L0", update, "pack-update", "$");
        for c in &unresolved {
            report.error(
                "NF-PCK-006",
                &format!("$.conflicts.{}", c["id"].as_str().unwrap_or("")),
                &format!(
                    "冲突未裁决（{} {}）：请在冲突 UI 逐个决定",
                    c["kind"].as_str().unwrap_or(""),
                    c["path"].as_str().unwrap_or("")
                ),
            );
        }
        return Ok((1, report.to_value()));
    }

    // 决定每个输出路径的来源：new（含新增/修改）或 base（keep_mine/删除保留）
    let mut final_paths: BTreeSet<String> = BTreeSet::new();
    let mut keep_old: BTreeSet<String> = BTreeSet::new();
    let mut conflict_by_path: BTreeMap<String, (&ConflictPlan, String)> = BTreeMap::new();
    for c in &conflicts {
        let dec = effective.get(&c.id).cloned().unwrap_or_else(|| "defer".into());
        if let Some(p) = &c.removed {
            conflict_by_path.insert(p.clone(), (c, dec.clone()));
        }
    }
    for path in new_items.keys() {
        final_paths.insert(path.clone());
    }
    for (path, (c, dec)) in &conflict_by_path {
        match dec.as_str() {
            "take_new" => {
                if c.value["kind"] == "delete" || c.value["kind"] == "rename" {
                    final_paths.remove(path);
                } else {
                    final_paths.insert(path.clone());
                }
            }
            "keep_mine" => {
                final_paths.remove(path);
                keep_old.insert(path.clone());
                if c.value["kind"] == "rename" {
                    if let Some(added) = &c.added {
                        final_paths.remove(added);
                    }
                }
            }
            _ => {}
        }
    }
    // 清除 old out_dir 内容（out_dir 必须存在；只清理本 op 生成的 pack 文件）
    for entry in std::fs::read_dir(&out_dir)
        .map_err(|e| CoreError::new("NF-E-004").with_message(format!("读 out_dir 失败: {e}")).with_exit(2))?
        .flatten()
    {
        let p = entry.path();
        if p.is_dir() {
            let _ = std::fs::remove_dir_all(&p);
        } else {
            let _ = std::fs::remove_file(&p);
        }
    }
    for path in &final_paths {
        let src = new_root.join(path.replace('/', std::path::MAIN_SEPARATOR_STR));
        let bytes = std::fs::read(&src).map_err(|e| {
            CoreError::new("NF-E-004")
                .with_message(format!("读 new_root/{path} 失败: {e}"))
                .with_exit(2)
        })?;
        fsutil::write_bytes(&out_dir.join(path.replace('/', std::path::MAIN_SEPARATOR_STR)), &bytes)?;
    }
    for path in &keep_old {
        let src = base_root.join(path.replace('/', std::path::MAIN_SEPARATOR_STR));
        if src.is_file() {
            let bytes = std::fs::read(&src).map_err(|e| {
                CoreError::new("NF-E-004")
                    .with_message(format!("读 base_root/{path} 失败: {e}"))
                    .with_exit(2)
            })?;
            fsutil::write_bytes(&out_dir.join(path.replace('/', std::path::MAIN_SEPARATOR_STR)), &bytes)?;
        }
    }
    // 重写清单（按写出实况重建 items/tree）
    let mut rebuilt_manifest = new_manifest.clone();
    let computed = fsutil::pack_items(&out_dir, Some(&new_manifest))?;
    rebuilt_manifest["items"] = Value::Array(computed.items);
    rebuilt_manifest["hashes"]["tree"] = Value::String(computed.tree.clone());
    rebuilt_manifest["hashes"]["count"] = Value::Number((computed.count).into());
    fsutil::write_json_canonical(&out_dir.join("nf-pack.json"), &rebuilt_manifest)?;
    let result = json!({
        "applied": true,
        "conflicts": conflicts.iter().map(|c| c.value.clone()).collect::<Vec<Value>>(),
        "result_tree": computed.tree,
    });
    Ok((0, result))
}
