//! 差异与三方合并（diff / merge / rebuild）。
//!
//! 自 `sdir.rs` 按职责拆出：实现逐字搬运，逻辑与文案未改；公共 API 由父模块 `pub use` 保持原路径。

use super::parse::{str_field, walk};
use super::SDIR_SCHEMA;
use super::validate::validate_sdir_value;
use crate::canonical::digest_value;
use crate::error::{CoreError, OpOutcome};
use crate::ops::req_value;
use crate::report::Report;
use serde_json::{json, Map, Value};
use std::collections::{BTreeMap, BTreeSet};

pub(super) fn flat_map(root: &Value) -> BTreeMap<String, Value> {
    let mut flat: Vec<(&Value, Option<&Value>, usize)> = Vec::new();
    walk(root, None, &mut flat, 0);
    let mut m = BTreeMap::new();
    for (b, _, _) in flat {
        m.insert(str_field(b, "id").to_string(), b.clone());
    }
    m
}

pub(super) fn diff_value(from: &Value, to: &Value) -> Value {
    let a = flat_map(&from["blocks"][0]);
    let b = flat_map(&to["blocks"][0]);
    let mut changes: Vec<Value> = Vec::new();
    let mut added = 0u64;
    let mut removed = 0u64;
    let mut changed = 0u64;
    let mut moved = 0u64;
    for (id, av) in &a {
        match b.get(id) {
            None => {
                removed += 1;
                changes.push(json!({"kind": "removed", "block": id, "before": av.get("hash"), "after": null}));
            }
            Some(bv) => {
                if av.get("hash") != bv.get("hash") {
                    changed += 1;
                    changes.push(json!({"kind": "changed", "block": id, "before": av.get("hash"), "after": bv.get("hash")}));
                }
            }
        }
    }
    for (id, bv) in &b {
        if !a.contains_key(id) {
            added += 1;
            changes.push(json!({"kind": "added", "block": id, "before": null, "after": bv.get("hash")}));
        }
    }
    // 位置变化：父块 id 变化（同 hash）
    let parent_of = |root: &Value| -> BTreeMap<String, String> {
        let mut flat: Vec<(&Value, Option<&Value>, usize)> = Vec::new();
        walk(root, None, &mut flat, 0);
        let mut m = BTreeMap::new();
        for (b, p, _) in flat {
            m.insert(str_field(b, "id").to_string(), p.map(|x| str_field(x, "id").to_string()).unwrap_or_default());
        }
        m
    };
    let pa = parent_of(from);
    let pb = parent_of(to);
    for (id, bv) in &b {
        if let Some(av) = a.get(id) {
            if av.get("hash") == bv.get("hash") && pa.get(id) != pb.get(id) {
                moved += 1;
                changes.push(json!({"kind": "moved", "block": id, "before": pa.get(id), "after": pb.get(id)}));
            }
        }
    }
    json!({
        "schema": "nf-sdir-diff/1",
        "from": from.get("meta").and_then(|m| m.get("created_at")),
        "to": to.get("meta").and_then(|m| m.get("created_at")),
        "changes": changes,
        "summary": {"added": added, "removed": removed, "changed": changed, "moved": moved, "total": a.len().max(b.len()) as u64}
    })
}

pub fn diff_op(req: &Value) -> OpOutcome {
    let from = req_value(req, "from")?;
    let to = req_value(req, "to")?;
    Ok((0, diff_value(from, to)))
}

// ---------------- 三方合并 ----------------

#[derive(Clone)]
pub(super) struct Flat {
    block: Value,
    parent: String,
}

pub(super) fn flatten_with_parent(root: &Value) -> BTreeMap<String, Flat> {
    let mut flat: Vec<(&Value, Option<&Value>, usize)> = Vec::new();
    walk(root, None, &mut flat, 0);
    let mut m = BTreeMap::new();
    for (b, p, _) in flat {
        m.insert(
            str_field(b, "id").to_string(),
            Flat {
                block: b.clone(),
                parent: p.map(|x| str_field(x, "id").to_string()).unwrap_or_default(),
            },
        );
    }
    m
}

pub(super) fn intrinsic(v: &Value) -> String {
    let m = json!({
        "type": v.get("type").cloned().unwrap_or(Value::Null),
        "text": v.get("text").cloned().unwrap_or(Value::Null),
        "attrs": v.get("attrs").cloned().unwrap_or_else(|| json!({}))
    });
    digest_value(&m).unwrap_or_default()
}

pub(super) fn merge_maps(base: &BTreeMap<String, Flat>, ours: &BTreeMap<String, Flat>, theirs: &BTreeMap<String, Flat>) -> (BTreeMap<String, Flat>, Vec<Value>) {
    let mut ids: BTreeSet<String> = BTreeSet::new();
    for k in base.keys().chain(ours.keys()).chain(theirs.keys()) {
        ids.insert(k.clone());
    }
    let mut out = BTreeMap::new();
    let mut conflicts = Vec::new();
    for id in ids {
        let b = base.get(&id);
        let o = ours.get(&id);
        let t = theirs.get(&id);
        let bh = b.map(|x| intrinsic(&x.block));
        let oh = o.map(|x| intrinsic(&x.block));
        let th = t.map(|x| intrinsic(&x.block));
        let chosen = if oh == th {
            o.or(t)
        } else if oh == bh {
            t
        } else if th == bh {
            o
        } else {
            conflicts.push(json!({
                "block": id,
                "reason": "both-modified",
                "base": bh,
                "ours": oh,
                "theirs": th
            }));
            o.or(t)
        };
        if let Some(f) = chosen {
            out.insert(id, f.clone());
        }
    }
    (out, conflicts)
}

pub(super) fn rebuild(meta: &Value, sources: &Value, blocks: &BTreeMap<String, Flat>, relations: &Value, a11y: &Value, prov: &Value) -> Result<Value, CoreError> {
    // 用 parent 关系重建树；根是 parent 为空或 parent 不存在的块。
    let root_id = blocks
        .iter()
        .find(|(_, f)| f.parent.is_empty() || !blocks.contains_key(&f.parent))
        .map(|(id, _)| id.clone())
        .ok_or_else(|| CoreError::new("NF-SDIR-004").with_message("合并后没有根块").with_exit(1))?;
    let mut children: BTreeMap<String, Vec<String>> = BTreeMap::new();
    for (id, f) in blocks {
        if id != &root_id {
            let p = if blocks.contains_key(&f.parent) { f.parent.clone() } else { root_id.clone() };
            children.entry(p).or_default().push(id.clone());
        }
    }
    // 保持原顺序：按原 block 在各自输入中的出现序（用 id 排序作为确定性兜底）
    for v in children.values_mut() {
        v.sort();
    }
    fn build(id: &str, blocks: &BTreeMap<String, Flat>, children: &BTreeMap<String, Vec<String>>) -> Result<Value, CoreError> {
        let f = &blocks[id];
        let mut v = f.block.clone();
        v.as_object_mut().unwrap().remove("children");
        let mut cs: Vec<Value> = Vec::new();
        for c in children.get(id).map(|x| x.as_slice()).unwrap_or(&[]) {
            cs.push(build(c, blocks, children)?);
        }
        // 重算 hash（含 children hash）
        let child_hashes: Vec<Value> = cs.iter().map(|c| Value::String(str_field(c, "hash").to_string())).collect();
        let mut m = Map::new();
        m.insert("type".into(), v.get("type").cloned().unwrap_or(Value::Null));
        m.insert("text".into(), v.get("text").cloned().unwrap_or(Value::Null));
        m.insert("attrs".into(), v.get("attrs").cloned().unwrap_or_else(|| json!({})));
        m.insert("children".into(), Value::Array(child_hashes));
        let hash = digest_value(&Value::Object(m))?;
        v.as_object_mut().unwrap().insert("hash".into(), Value::String(hash));
        if !cs.is_empty() {
            v.as_object_mut().unwrap().insert("children".into(), Value::Array(cs));
        }
        Ok(v)
    }
    let root = build(&root_id, blocks, &children)?;
    Ok(json!({
        "schema": SDIR_SCHEMA,
        "meta": meta,
        "sources": sources,
        "blocks": [root],
        "relations": relations,
        "accessibility": a11y,
        "provenance": prov
    }))
}

pub(super) fn merge_array_by_key(a: &Value, b: &Value, key: &str) -> Value {
    let mut seen: BTreeMap<String, Value> = BTreeMap::new();
    for src in [a, b] {
        if let Some(arr) = src.as_array() {
            for item in arr {
                let k = item.get(key).and_then(|v| v.as_str()).unwrap_or("").to_string();
                seen.entry(k).or_insert_with(|| item.clone());
            }
        }
    }
    Value::Array(seen.into_values().collect())
}

pub(super) fn filter_array(v: Value, key: &str, ids: &BTreeSet<String>) -> Value {
    Value::Array(
        v.as_array()
            .cloned()
            .unwrap_or_default()
            .into_iter()
            .filter(|item| item.get(key).and_then(|x| x.as_str()).map(|s| ids.contains(s)).unwrap_or(false))
            .collect(),
    )
}

pub(super) fn filter_relations(v: Value, ids: &BTreeSet<String>) -> Value {
    Value::Array(
        v.as_array()
            .cloned()
            .unwrap_or_default()
            .into_iter()
            .filter(|item| {
                let from = item.get("from").and_then(|x| x.as_str()).unwrap_or("");
                let to = item.get("to").and_then(|x| x.as_str()).unwrap_or("");
                ids.contains(from) && ids.contains(to)
            })
            .collect(),
    )
}

pub(super) fn merge_relations(a: &Value, b: &Value) -> Value {
    let mut seen: BTreeMap<String, Value> = BTreeMap::new();
    for src in [a, b] {
        if let Some(arr) = src.as_array() {
            for item in arr {
                let k = format!(
                    "{}|{}|{}",
                    item.get("from").and_then(|v| v.as_str()).unwrap_or(""),
                    item.get("to").and_then(|v| v.as_str()).unwrap_or(""),
                    item.get("kind").and_then(|v| v.as_str()).unwrap_or("")
                );
                seen.entry(k).or_insert_with(|| item.clone());
            }
        }
    }
    Value::Array(seen.into_values().collect())
}

pub fn merge_op(req: &Value) -> OpOutcome {
    let base = req_value(req, "base")?;
    let ours = req_value(req, "ours")?;
    let theirs = req_value(req, "theirs")?;
    let b = flatten_with_parent(&base["blocks"][0]);
    let o = flatten_with_parent(&ours["blocks"][0]);
    let t = flatten_with_parent(&theirs["blocks"][0]);
    let (merged, mut conflicts) = merge_maps(&b, &o, &t);
    let meta = ours.get("meta").cloned().unwrap_or_else(|| json!({}));
    let sources = merge_array_by_key(&ours["sources"], &theirs["sources"], "id");
    let ids: BTreeSet<String> = merged.keys().cloned().collect();
    let relations = filter_relations(merge_relations(&ours["relations"], &theirs["relations"]), &ids);
    let a11y = filter_array(merge_array_by_key(&ours["accessibility"], &theirs["accessibility"], "block"), "block", &ids);
    let prov = filter_array(merge_array_by_key(&ours["provenance"], &theirs["provenance"], "block"), "block", &ids);
    let merged = rebuild(&meta, &sources, &merged, &relations, &a11y, &prov)?;
    let report = validate_sdir_value(&merged);
    if report.has_error() {
        for i in report.issues.iter().filter(|i| i.severity == "error") {
            conflicts.push(json!({"block": i.path, "reason": "invalid-merged", "message": i.message}));
        }
    }
    let out = json!({
        "schema": "nf-sdir-merge/1",
        "merged": merged,
        "conflicts": conflicts,
        "summary": {"conflicts": conflicts.len() as u64}
    });
    if out["conflicts"].as_array().map(|a| !a.is_empty()).unwrap_or(false) {
        let mut rep = Report::new("L0", &merged, "sdir-merge", "merge");
        for c in out["conflicts"].as_array().unwrap() {
            rep.error("NF-SDIR-004", c.get("block").and_then(|v| v.as_str()).unwrap_or("$"), "三方合并存在未裁决冲突");
        }
        let mut value = rep.to_value();
        value.as_object_mut().unwrap().insert("merged".into(), out["merged"].clone());
        value.as_object_mut().unwrap().insert("conflicts".into(), out["conflicts"].clone());
        Ok((1, value))
    } else {
        Ok((0, out))
    }
}
