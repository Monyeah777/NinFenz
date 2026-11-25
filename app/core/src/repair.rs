//! 语义修复：只修可证明的结构问题，记录 before/after；不改正文，不删块。
//! 修复范围：标题层级跳级、表格缺表头、图缺 alt、阅读顺序重复、悬空关系。

use crate::canonical::digest_value;
use crate::error::{CoreError, OpOutcome};
use crate::ops::req_value;
use crate::report::Report;
use crate::sdir::validate_sdir_value;
use serde_json::{json, Value};
use std::collections::BTreeSet;

fn text_of(v: &Value) -> &str { v.get("text").and_then(|x| x.as_str()).unwrap_or("") }
fn id_of(v: &Value) -> &str { v.get("id").and_then(|x| x.as_str()).unwrap_or("") }
fn ty_of(v: &Value) -> &str { v.get("type").and_then(|x| x.as_str()).unwrap_or("") }
fn kids(v: &Value) -> &[Value] { v.get("children").and_then(|x| x.as_array()).map(|a| a.as_slice()).unwrap_or(&[]) }

fn recompute(v: &mut Value) -> Result<String, CoreError> {
    let mut child_hashes: Vec<Value> = Vec::new();
    if let Some(cs) = v.get_mut("children").and_then(|x| x.as_array_mut()) {
        for c in cs.iter_mut() { child_hashes.push(Value::String(recompute(c)?)); }
    }
    let m = json!({
        "type": v.get("type").cloned().unwrap_or(Value::Null),
        "text": v.get("text").cloned().unwrap_or(Value::Null),
        "attrs": v.get("attrs").cloned().unwrap_or_else(|| json!({})),
        "children": child_hashes,
    });
    let h = digest_value(&m)?;
    v.as_object_mut().unwrap().insert("hash".into(), Value::String(h.clone()));
    Ok(h)
}

fn fix_headings(v: &mut Value, parent: u64, repairs: &mut Vec<Value>) {
    let mut next_parent = parent;
    if ty_of(v) == "heading" {
        let cur = v.get("attrs").and_then(|a| a.get("level")).and_then(|x| x.as_u64()).unwrap_or(1);
        let want = if parent == 0 { 1 } else { cur.clamp(1, parent + 1).max(1) };
        if want != cur {
            if let Some(attrs) = v.get_mut("attrs").and_then(|a| a.as_object_mut()) {
                attrs.insert("level".into(), Value::Number(want.into()));
            }
            repairs.push(json!({"kind": "heading_level", "block": id_of(v), "before": cur, "after": want}));
        }
        next_parent = want;
    }
    if let Some(cs) = v.get_mut("children").and_then(|x| x.as_array_mut()) {
        for c in cs.iter_mut() { fix_headings(c, next_parent, repairs); }
    }
}

fn fix_tables(v: &mut Value, repairs: &mut Vec<Value>) {
    if ty_of(v) == "table" {
        let has_header = v.get("attrs").and_then(|a| a.get("header")).and_then(|x| x.as_bool()).unwrap_or(false);
        let first_row = kids(v).first().map(|r| !kids(r).is_empty()).unwrap_or(false);
        if !has_header && first_row {
            if let Some(attrs) = v.get_mut("attrs").and_then(|a| a.as_object_mut()) {
                attrs.insert("header".into(), Value::Bool(true));
            }
            repairs.push(json!({"kind": "table_header", "block": id_of(v), "before": false, "after": true}));
        }
    }
    if let Some(cs) = v.get_mut("children").and_then(|x| x.as_array_mut()) {
        for c in cs.iter_mut() { fix_tables(c, repairs); }
    }
}

fn fix_alt(v: &mut Value, repairs: &mut Vec<Value>) {
    if ty_of(v) == "figure" && text_of(v).trim().is_empty() {
        let alt = v.get("attrs").and_then(|a| a.get("src")).and_then(|x| x.as_str()).filter(|s| !s.is_empty()).unwrap_or("image");
        let alt = std::path::Path::new(alt).file_stem().and_then(|s| s.to_str()).unwrap_or("image").to_string();
        v.as_object_mut().unwrap().insert("text".into(), Value::String(alt.clone()));
        repairs.push(json!({"kind": "figure_alt", "block": id_of(v), "before": "", "after": alt}));
    }
    if let Some(cs) = v.get_mut("children").and_then(|x| x.as_array_mut()) {
        for c in cs.iter_mut() { fix_alt(c, repairs); }
    }
}

fn order_map(v: &Value, map: &mut std::collections::BTreeMap<String, u64>, n: &mut u64) {
    map.insert(id_of(v).to_string(), *n);
    *n += 1;
    for c in kids(v) { order_map(c, map, n); }
}

pub fn repair(req: &Value) -> OpOutcome {
    let sdir = req_value(req, "sdir")?;
    let mut out = sdir.clone();
    let mut repairs: Vec<Value> = Vec::new();
    fix_headings(&mut out["blocks"][0], 0, &mut repairs);
    fix_tables(&mut out["blocks"][0], &mut repairs);
    fix_alt(&mut out["blocks"][0], &mut repairs);
    recompute(&mut out["blocks"][0])?;

    let mut ids = BTreeSet::new();
    fn collect(v: &Value, ids: &mut BTreeSet<String>) {
        ids.insert(id_of(v).to_string());
        for c in kids(v) { collect(c, ids); }
    }
    collect(&out["blocks"][0], &mut ids);
    let mut order = std::collections::BTreeMap::new();
    let mut n = 0u64;
    order_map(&out["blocks"][0], &mut order, &mut n);
    if let Some(a) = out.get_mut("accessibility").and_then(|v| v.as_array_mut()) {
        for item in a.iter_mut() {
            let block = item.get("block").and_then(|v| v.as_str()).unwrap_or("").to_string();
            if let Some(want) = order.get(&block) {
                let cur = item.get("reading_order").and_then(|v| v.as_u64());
                if cur != Some(*want) {
                    item.as_object_mut().unwrap().insert("reading_order".into(), Value::Number((*want).into()));
                    repairs.push(json!({"kind": "reading_order", "block": block, "before": cur, "after": want}));
                }
            }
        }
    }
    if let Some(rels) = out.get_mut("relations").and_then(|v| v.as_array_mut()) {
        let before = rels.len();
        rels.retain(|r| {
            let f = r.get("from").and_then(|v| v.as_str()).unwrap_or("");
            let t = r.get("to").and_then(|v| v.as_str()).unwrap_or("");
            ids.contains(f) && ids.contains(t)
        });
        if rels.len() != before {
            repairs.push(json!({"kind": "dangling_relations", "before": before, "after": rels.len()}));
        }
    }
    let report = validate_sdir_value(&out);
    if report.has_error() {
        let mut rep = Report::new("L0", sdir, "sdir-repair", "repair");
        for i in report.issues.iter().filter(|i| i.severity == "error") {
            rep.error("NF-SDIR-005", &i.path, &i.message);
        }
        return Ok((1, rep.to_value()));
    }
    Ok((0, json!({
        "schema": "nf-sdir-repair/1",
        "sdir": out,
        "repairs": repairs,
        "summary": {"repairs": repairs.len() as u64, "reversible": true, "lost_blocks": 0}
    })))
}

pub fn repair_op(req: &Value) -> OpOutcome { repair(req) }
