use super::*;

pub(crate) fn display_io(code: &str, path: &str) -> CoreError {
    CoreError::new(code)
        .with_message(format!("路径缺失/不可读：{path}"))
        .with_exit(2)
}

pub(crate) fn load_manifest(root: &Path) -> Result<Option<Value>, CoreError> {
    let p = root.join("nf-pack.json");
    if p.is_file() {
        Ok(Some(fsutil::load_json_file(&p)?))
    } else {
        Ok(None)
    }
}

pub(crate) fn manifest_items(manifest: &Value) -> BTreeMap<String, Value> {
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

pub(crate) fn protocol_clause_text_digest(clause: &Value) -> Option<String> {
    clause
        .get("text")
        .and_then(|v| v.as_str())
        .map(|t| sha256_hex(t.as_bytes()))
}

pub(crate) fn load_protocol_doc(root: &Path, rel: &str) -> Option<Value> {
    let p = root.join(rel.replace('/', std::path::MAIN_SEPARATOR_STR));
    fsutil::load_json_file(&p).ok()
}

pub(crate) fn overlay_clause_ids(overlay: &Value) -> BTreeMap<String, Value> {
    overlay
        .get("clauses")
        .and_then(|v| v.as_object())
        .map(|m| m.iter().map(|(k, v)| (k.clone(), v.clone())).collect())
        .unwrap_or_default()
}

#[derive(Clone, Debug)]
pub(crate) struct ConflictPlan {
    pub(crate) id: String,
    pub(crate) value: Value,
    pub(crate) removed: Option<String>,
    pub(crate) added: Option<String>,
}

pub(crate) fn build_conflicts(
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
