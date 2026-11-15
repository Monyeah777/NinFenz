//! Pack 更新 / Overlay：pack-diff / pack-merge / overlay-apply（A4）。

use crate::canonical::{canonical_bytes, sha256_hex};
use crate::error::{CoreError, OpOutcome};
use crate::fsutil;
use crate::ops::pack::{dir_tree, parse_semver, verify_manifest};
use crate::ops::{ensure_out_dir, float_issue, ref_id, req_str, req_value, resolve_path, schema_report};
use crate::report::{failure_report, Report};
use serde_json::{json, Map, Value};
use std::collections::{BTreeMap, BTreeSet};
use std::path::Path;

fn display_io(code: &str, path: &str) -> CoreError {
    CoreError::new(code)
        .with_message(format!("路径缺失/不可读：{path}"))
        .with_exit(2)
}

fn load_manifest(root: &Path) -> Result<Option<Value>, CoreError> {
    let p = root.join("nf-pack.json");
    if p.is_file() {
        Ok(Some(fsutil::load_json_file(&p)?))
    } else {
        Ok(None)
    }
}

fn manifest_items(manifest: &Value) -> BTreeMap<String, Value> {
    manifest
        .get("items")
        .and_then(|v| v.as_array())
        .map(|arr| {
            arr.iter()
                .filter_map(|i| {
                    Some((i.get("path")?.as_str()?.to_string(), i.clone()))
                })
                .collect()
        })
        .unwrap_or_default()
}

fn protocol_clause_text_digest(clause: &Value) -> Option<String> {
    clause
        .get("text")
        .and_then(|v| v.as_str())
        .map(|t| sha256_hex(t.as_bytes()))
}

fn load_protocol_doc(root: &Path, rel: &str) -> Option<Value> {
    let p = root.join(rel.replace('/', std::path::MAIN_SEPARATOR_STR));
    fsutil::load_json_file(&p).ok()
}

fn overlay_clause_ids(overlay: &Value) -> BTreeMap<String, Value> {
    overlay
        .get("clauses")
        .and_then(|v| v.as_object())
        .map(|m| m.iter().map(|(k, v)| (k.clone(), v.clone())).collect())
        .unwrap_or_default()
}

#[derive(Clone, Debug)]
struct ConflictPlan {
    id: String,
    value: Value,
    removed: Option<String>,
    added: Option<String>,
}

fn build_conflicts(
    old_root: &Path,
    new_root: &Path,
    old_items: &BTreeMap<String, Value>,
    new_items: &BTreeMap<String, Value>,
    overlay: Option<&Value>,
) -> Vec<ConflictPlan> {
    let mut raw: Vec<(String, String, Option<String>, Option<String>)> = Vec::new(); // (kind,path,old,new)
    let mut delete_paths: BTreeSet<String> = BTreeSet::new();
    let custom_paths: BTreeSet<String> = overlay
        .map(|o| {
            o.get("custom_assets")
                .and_then(|v| v.as_array())
                .map(|a| {
                    a.iter()
                        .filter_map(|x| x.get("path").and_then(|v| v.as_str()))
                        .map(|s| s.to_string())
                        .collect()
                })
                .unwrap_or_default()
        })
        .unwrap_or_default();
    let clause_overlay = overlay.map(overlay_clause_ids).unwrap_or_default();

    // 删除类
    for (path, item) in old_items {
        if new_items.contains_key(path) {
            continue;
        }
        let kind = item.get("kind").and_then(|v| v.as_str()).unwrap_or("");
        let hit_custom = custom_paths.contains(path);
        let hit_clause = kind == "protocol" && !clause_overlay.is_empty();
        if hit_custom || hit_clause {
            raw.push((
                "delete".into(),
                path.clone(),
                item.get("sha256").and_then(|v| v.as_str()).map(|s| s.to_string()),
                None,
            ));
            delete_paths.insert(path.clone());
        }
    }
    // 重命名类：删除 + 新增且 sha 相同
    let added: Vec<(String, String)> = new_items
        .iter()
        .filter(|(p, _)| !old_items.contains_key(*p))
        .map(|(p, i)| {
            (
                p.clone(),
                i.get("sha256").and_then(|v| v.as_str()).unwrap_or("").to_string(),
            )
        })
        .collect();
    for (path, item) in old_items {
        if new_items.contains_key(path) || delete_paths.contains(path) {
            continue;
        }
        let sha = item.get("sha256").and_then(|v| v.as_str()).unwrap_or("");
        for (_new_path, new_sha) in &added {
            if new_sha == sha && !sha.is_empty() {
                raw.push((
                    "rename".into(),
                    path.clone(),
                    Some(sha.to_string()),
                    Some(new_sha.clone()),
                ));
                break;
            }
        }
    }
    // schema 类：protocol 文件 clause 文本变化且 overlay 钉了旧 sha
    if !clause_overlay.is_empty() {
        for (path, new_item) in new_items {
            let old_item = match old_items.get(path) {
                Some(o) => o,
                None => continue,
            };
            let kind = new_item.get("kind").and_then(|v| v.as_str()).unwrap_or("");
            if kind != "protocol" {
                continue;
            }
            let old_sha = old_item.get("sha256").and_then(|v| v.as_str()).unwrap_or("");
            let new_sha = new_item.get("sha256").and_then(|v| v.as_str()).unwrap_or("");
            if old_sha == new_sha || old_sha.is_empty() {
                continue;
            }
            let old_doc = match load_protocol_doc(old_root, path) {
                Some(d) => d,
                None => continue,
            };
            let new_doc = load_protocol_doc(new_root, path);
            let old_clauses: BTreeMap<String, Value> = old_doc
                .get("clauses")
                .and_then(|v| v.as_array())
                .map(|a| {
                    a.iter()
                        .filter_map(|c| Some((c.get("id")?.as_str()?.to_string(), c.clone())))
                        .collect()
                })
                .unwrap_or_default();
            let new_clauses: BTreeMap<String, Value> = new_doc
                .as_ref()
                .and_then(|d| d.get("clauses"))
                .and_then(|v| v.as_array())
                .map(|a| {
                    a.iter()
                        .filter_map(|c| Some((c.get("id")?.as_str()?.to_string(), c.clone())))
                        .collect()
                })
                .unwrap_or_default();
            for (cid, ov) in clause_overlay.iter() {
                let pinned = ov.get("text_sha256").and_then(|v| v.as_str());
                let old_clause = match old_clauses.get(cid) {
                    Some(c) => c,
                    None => continue,
                };
                let old_text_sha = protocol_clause_text_digest(old_clause);
                if pinned.is_some() && pinned != old_text_sha.as_deref() {
                    continue;
                }
                let changed = match new_clauses.get(cid) {
                    None => true,
                    Some(nc) => protocol_clause_text_digest(nc) != old_text_sha,
                };
                if changed {
                    raw.push((
                        "schema".into(),
                        path.clone(),
                        Some(old_sha.to_string()),
                        Some(new_sha.to_string()),
                    ));
                    break;
                }
            }
        }
    }

    raw.sort_by(|a, b| a.0.cmp(&b.0).then_with(|| a.1.cmp(&b.1)));
    raw.dedup_by(|a, b| a.0 == b.0 && a.1 == b.1);
    raw.into_iter()
        .enumerate()
        .map(|(i, (kind, path, old_sha, new_sha))| {
            let id = format!("CFL-{:02}", i + 1);
            let mut m = Map::new();
            m.insert("id".into(), Value::String(id.clone()));
            m.insert("kind".into(), Value::String(kind.clone()));
            m.insert("path".into(), Value::String(path.clone()));
            if let Some(s) = &old_sha {
                m.insert("old_sha256".into(), Value::String(s.clone()));
            }
            if let Some(s) = &new_sha {
                m.insert("new_sha256".into(), Value::String(s.clone()));
            }
            m.insert(
                "options".into(),
                json!(["keep_mine", "take_new", "defer"]),
            );
            m.insert("default".into(), Value::String("defer".into()));
            let added = if kind == "rename" {
                new_items
                    .keys()
                    .find(|p| !old_items.contains_key(*p) && *p != &path)
                    .cloned()
            } else {
                None
            };
            let removed = if kind == "rename" || kind == "delete" {
                Some(path.clone())
            } else {
                None
            };
            ConflictPlan {
                id,
                value: Value::Object(m),
                removed,
                added,
            }
        })
        .collect()
}

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
