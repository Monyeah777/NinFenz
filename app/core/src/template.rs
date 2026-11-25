//! 模板归纳 + 迁移：从多份 SDIR 统计稳定标题路径，生成槽位模板；
//! 迁移只补缺失的必需章节，不删除/改写已有块（0 丢失）。

use crate::canonical::digest_value;
use crate::error::{CoreError, OpOutcome};
use crate::ops::{opt_str, req_value, usage};
use crate::sdir::validate_sdir_value;
use serde_json::{json, Map, Value};
use std::collections::{BTreeMap, BTreeSet};

fn text_of(v: &Value) -> &str {
    v.get("text").and_then(|x| x.as_str()).unwrap_or("")
}

fn level_of(v: &Value) -> u64 {
    v.get("attrs").and_then(|a| a.get("level")).and_then(|x| x.as_u64()).unwrap_or(2)
}

fn walk_paths(root: &Value, stack: &mut Vec<String>, out: &mut Vec<(String, u64)>) {
    let ty = root.get("type").and_then(|x| x.as_str()).unwrap_or("");
    if ty == "heading" {
        let text = text_of(root).to_string();
        stack.push(text);
        out.push((stack.join("/"), level_of(root)));
    }
    for c in root.get("children").and_then(|x| x.as_array()).into_iter().flatten() {
        walk_paths(c, stack, out);
    }
    if ty == "heading" {
        stack.pop();
    }
}

fn slug(text: &str) -> String {
    let mut out = String::new();
    for c in text.chars() {
        if c.is_ascii_alphanumeric() {
            out.push(c.to_ascii_lowercase());
        } else if c.is_whitespace() || c == '-' || c == '_' {
            if !out.ends_with('-') {
                out.push('-');
            }
        } else if (c as u32) > 0x7f {
            out.push(c);
        }
    }
    let s = out.trim_matches('-').to_string();
    if s.is_empty() { "section".to_string() } else { s }
}

pub fn induce(req: &Value) -> OpOutcome {
    let docs = req
        .get("docs")
        .and_then(|v| v.as_array())
        .ok_or_else(|| usage("template-induce 需要 docs:[sdir]"))?;
    if docs.is_empty() {
        return Err(usage("docs 不能为空"));
    }
    let min_support = req.get("min_support").and_then(|v| v.as_u64()).unwrap_or(1).max(1) as usize;
    let mut counts: BTreeMap<String, (u64, u64)> = BTreeMap::new();
    for (i, d) in docs.iter().enumerate() {
        let report = validate_sdir_value(d);
        if report.has_error() {
            return Ok((1, report.to_value()));
        }
        let mut paths = Vec::new();
        walk_paths(&d["blocks"][0], &mut Vec::new(), &mut paths);
        let mut seen = BTreeSet::new();
        for (path, level) in paths {
            if !seen.insert(path.clone()) {
                continue;
            }
            let e = counts.entry(path).or_insert((0, level));
            e.0 += 1;
        }
        let _ = i;
    }
    let n = docs.len() as u64;
    let mut slots = Vec::new();
    let mut headings = Vec::new();
    let mut idx = 0u64;
    for (path, (count, level)) in &counts {
        if *count < min_support as u64 {
            continue;
        }
        idx += 1;
        let required = *count == n;
        headings.push(json!({"path": path, "level": level, "support": count}));
        slots.push(json!({
            "id": format!("S{idx:03}"),
            "path": path,
            "kind": "section",
            "level": level,
            "required": required,
            "support": count
        }));
    }
    Ok((0, json!({
        "schema": "nf-template-induction/1",
        "id": opt_str(req, "id")?.unwrap_or("induced"),
        "docs": n,
        "min_support": min_support,
        "headings": headings,
        "slots": slots,
        "summary": {"slots": idx, "required": slots.iter().filter(|s| s["required"].as_bool().unwrap_or(false)).count() as u64}
    })))
}

fn recompute(v: &mut Value) -> Result<String, CoreError> {
    let mut child_hashes: Vec<Value> = Vec::new();
    if let Some(cs) = v.get_mut("children").and_then(|x| x.as_array_mut()) {
        for c in cs.iter_mut() {
            child_hashes.push(Value::String(recompute(c)?));
        }
    }
    let m = json!({
        "type": v.get("type").cloned().unwrap_or(Value::Null),
        "text": v.get("text").cloned().unwrap_or(Value::Null),
        "attrs": v.get("attrs").cloned().unwrap_or_else(|| json!({})),
        "children": child_hashes
    });
    let h = digest_value(&m)?;
    v.as_object_mut().unwrap().insert("hash".into(), Value::String(h.clone()));
    Ok(h)
}

pub fn migrate(req: &Value) -> OpOutcome {
    let template = req_value(req, "template")?;
    let sdir = req_value(req, "sdir")?;
    let report = validate_sdir_value(sdir);
    if report.has_error() {
        return Ok((1, report.to_value()));
    }
    let mut out = sdir.clone();
    let mut paths = Vec::new();
    walk_paths(&sdir["blocks"][0], &mut Vec::new(), &mut paths);
    let existing: BTreeSet<String> = paths.into_iter().map(|(p, _)| p).collect();
    let mut added: Vec<(String, String, u64)> = Vec::new();
    let mut counter = 0u64;
    let root = out["blocks"][0].as_object_mut().unwrap();
    let children = root.entry("children").or_insert_with(|| json!([]));
    let arr = children.as_array_mut().unwrap();
    for slot in template.get("slots").and_then(|v| v.as_array()).into_iter().flatten() {
        if slot.get("required").and_then(|v| v.as_bool()) != Some(true) {
            continue;
        }
        let path = slot.get("path").and_then(|v| v.as_str()).unwrap_or("");
        if path.is_empty() || existing.contains(path) {
            continue;
        }
        counter += 1;
        let level = slot.get("level").and_then(|v| v.as_u64()).unwrap_or(2);
        let leaf = path.rsplit('/').next().unwrap_or(path);
        let id = format!("tpl{counter:04}");
        let mut h = Map::new();
        h.insert("id".into(), Value::String(id.clone()));
        h.insert("type".into(), Value::String("heading".into()));
        h.insert("text".into(), Value::String(leaf.to_string()));
        h.insert("attrs".into(), json!({"level": level, "anchor": slug(leaf)}));
        h.insert("hash".into(), Value::String("0".repeat(64)));
        arr.push(Value::Object(h));
        added.push((id, path.to_string(), level));
    }
    recompute(&mut out["blocks"][0])?;
    if !added.is_empty() {
        let source = out.get("sources").and_then(|v| v.as_array()).and_then(|a| a.first()).cloned()
            .ok_or_else(|| CoreError::new("NF-SDIR-002").with_message("模板迁移缺 source，无法写溯源").with_exit(1))?;
        let source_id = source.get("id").and_then(|v| v.as_str()).unwrap_or("").to_string();
        let source_sha = source.get("bytes_sha").and_then(|v| v.as_str()).unwrap_or("").to_string();
        let mut order = out.get("accessibility").and_then(|v| v.as_array())
            .map(|a| a.iter().filter_map(|x| x.get("reading_order").and_then(|v| v.as_u64())).max().unwrap_or(0) + 1)
            .unwrap_or(0);
        let lang = out.get("meta").and_then(|m| m.get("lang")).and_then(|v| v.as_str()).unwrap_or("und").to_string();
        for (id, path, level) in &added {
            let _ = path;
            out["accessibility"].as_array_mut().unwrap().push(json!({
                "block": id, "role": "heading", "header": format!("h{level}"),
                "reading_order": order, "lang": lang, "missing": []
            }));
            order += 1;
            out["provenance"].as_array_mut().unwrap().push(json!({
                "block": id, "source_id": source_id,
                "transform": ["template-migrate/1"], "input_hashes": [source_sha]
            }));
        }
    }
    let report = validate_sdir_value(&out);
    if report.has_error() {
        return Ok((1, report.to_value()));
    }
    let before: BTreeSet<String> = {
        let mut v = Vec::new();
        collect_ids(&sdir["blocks"][0], &mut v);
        v.into_iter().collect()
    };
    let after: BTreeSet<String> = {
        let mut v = Vec::new();
        collect_ids(&out["blocks"][0], &mut v);
        v.into_iter().collect()
    };
    let lost: Vec<String> = before.difference(&after).cloned().collect();
    Ok((0, json!({
        "schema": "nf-template-migration/1",
        "sdir": out,
        "added": added.iter().map(|(_, p, _)| p.clone()).collect::<Vec<_>>(),
        "lost_blocks": lost,
        "summary": {"added": added.len() as u64, "lost": lost.len() as u64}
    })))
}

fn collect_ids(v: &Value, out: &mut Vec<String>) {
    if let Some(id) = v.get("id").and_then(|x| x.as_str()) {
        out.push(id.to_string());
    }
    for c in v.get("children").and_then(|x| x.as_array()).into_iter().flatten() {
        collect_ids(c, out);
    }
}

#[derive(Default)]
struct SecStat {
    support: u64,
    order: u64,
    kinds: BTreeMap<String, u64>,
    min_chars: u64,
    max_chars: u64,
    example: String,
}

fn kind_of(ty: &str) -> &'static str {
    match ty {
        "list" | "list_item" => "list",
        "table" | "table_row" | "table_cell" => "table",
        "code" => "code",
        _ => "text",
    }
}

fn collect_sections(
    v: &Value,
    stack: &mut Vec<String>,
    stats: &mut BTreeMap<String, SecStat>,
    order: &mut u64,
) {
    let ty = v.get("type").and_then(|x| x.as_str()).unwrap_or("");
    if ty == "heading" {
        let text = text_of(v).to_string();
        stack.push(text);
        let path = stack.join("/");
        {
            let e = stats.entry(path.clone()).or_insert_with(|| {
                *order += 1;
                SecStat { support: 0, order: *order, min_chars: u64::MAX, max_chars: 0, ..Default::default() }
            });
            e.support += 1;
        }
        for c in v.get("children").and_then(|x| x.as_array()).into_iter().flatten() {
            if c.get("type").and_then(|x| x.as_str()) == Some("heading") {
                collect_sections(c, stack, stats, order);
            } else {
                let e = stats.get_mut(&path).unwrap();
                let k = kind_of(c.get("type").and_then(|x| x.as_str()).unwrap_or(""));
                *e.kinds.entry(k.to_string()).or_insert(0) += 1;
                let chars = text_of(c).chars().count() as u64;
                e.min_chars = e.min_chars.min(chars);
                e.max_chars = e.max_chars.max(chars);
                if e.example.is_empty() && chars > 0 {
                    e.example = text_of(c).chars().take(120).collect();
                }
            }
        }
        stack.pop();
    } else {
        for c in v.get("children").and_then(|x| x.as_array()).into_iter().flatten() {
            collect_sections(c, stack, stats, order);
        }
    }
}

pub fn induce_spec(req: &Value) -> OpOutcome {
    let docs = req
        .get("docs")
        .and_then(|v| v.as_array())
        .ok_or_else(|| usage("schema-induce 需要 docs:[sdir]"))?;
    if docs.is_empty() {
        return Err(usage("docs 不能为空"));
    }
    let min_support = req.get("min_support").and_then(|v| v.as_u64()).unwrap_or(1).max(1);
    let mut stats: BTreeMap<String, SecStat> = BTreeMap::new();
    let mut order = 0u64;
    for d in docs {
        let report = validate_sdir_value(d);
        if report.has_error() {
            return Ok((1, report.to_value()));
        }
        collect_sections(&d["blocks"][0], &mut Vec::new(), &mut stats, &mut order);
    }
    let n = docs.len() as u64;
    let mut entries: Vec<(&String, &SecStat)> = stats.iter().filter(|(_, s)| s.support >= min_support).collect();
    entries.sort_by_key(|(_, s)| s.order);
    let mut sections = Vec::new();
    let mut slots = Vec::new();
    for (i, (path, s)) in entries.iter().enumerate() {
        let sec_id = format!("SEC-{:02}", i + 1);
        let slot_id = format!("SLT-{:02}", i + 1);
        let title = path.rsplit('/').next().unwrap_or(path);
        let kind = s.kinds.iter().max_by_key(|(_, c)| *c).map(|(k, _)| k.clone()).unwrap_or_else(|| "text".to_string());
        let required = s.support == n;
        sections.push(json!({"id": sec_id, "title": title, "order": i as u64 + 1, "required": required, "slots": [slot_id.clone()]}));
        let max_chars = s.max_chars.max(1);
        let mut constraints = vec![json!({"op": "non_empty"})];
        if max_chars > 0 {
            constraints.push(json!({"op": "max_chars", "value": max_chars}));
        }
        slots.push(json!({
            "id": slot_id,
            "name": title,
            "section": sec_id,
            "kind": kind,
            "required": required,
            "constraints": constraints,
            "examples": if s.example.is_empty() { json!([]) } else { json!([s.example.clone()]) },
            "acceptance": ["A-01"],
            "budget": {"max_chars": max_chars}
        }));
    }
    let id = opt_str(req, "id")?.unwrap_or("induced-spec");
    let spec = json!({
        "schema": "nf-md-spec/1",
        "id": id,
        "title": opt_str(req, "title")?.unwrap_or("Induced Spec"),
        "domain": "induced",
        "version": "0.1.0",
        "heading_level": 2,
        "sections": sections,
        "slots": slots,
        "constraints": [],
        "acceptance": [{"id": "A-01", "description": "槽位非空且不超预算", "severity": "error"}],
        "references": [],
        "budget": {"max_total_chars": stats.values().map(|s| s.max_chars).sum::<u64>().max(1)}
    });
    let issues = crate::schema::validate("nf-md-spec", &spec);
    if !issues.is_empty() {
        let mut rep = crate::report::Report::new("L0", &spec, "md-spec", id);
        for i in issues {
            rep.error("NF-SPC-001", &i.path, &i.message);
        }
        return Ok((1, rep.to_value()));
    }
    Ok((0, spec))
}

pub fn induce_spec_op(req: &Value) -> OpOutcome { induce_spec(req) }

pub fn induce_op(req: &Value) -> OpOutcome { induce(req) }
pub fn migrate_op(req: &Value) -> OpOutcome { migrate(req) }
