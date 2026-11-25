//! 内容复用图：跨项目按块内容摘要建立索引，并计算变更影响。
//! 索引只依赖块内容（type/text/attrs），不含绝对路径/时间戳；可离线重建。

use crate::canonical::digest_value;
use crate::error::OpOutcome;
use crate::ops::{req_value, usage};
use crate::sdir::validate_sdir_value;
use serde_json::{json, Value};
use std::collections::{BTreeMap, BTreeSet};

fn text_of(v: &Value) -> &str {
    v.get("text").and_then(|x| x.as_str()).unwrap_or("")
}
fn type_of(v: &Value) -> &str {
    v.get("type").and_then(|x| x.as_str()).unwrap_or("")
}
fn intrinsic(v: &Value) -> String {
    digest_value(&json!({
        "type": v.get("type").cloned().unwrap_or(Value::Null),
        "text": v.get("text").cloned().unwrap_or(Value::Null),
        "attrs": v.get("attrs").cloned().unwrap_or_else(|| json!({}))
    }))
    .unwrap_or_default()
}

fn collect<'a>(v: &'a Value, out: &mut Vec<&'a Value>) {
    out.push(v);
    for c in v.get("children").and_then(|x| x.as_array()).into_iter().flatten() {
        collect(c, out);
    }
}

pub fn index(req: &Value) -> OpOutcome {
    let projects = req
        .get("projects")
        .and_then(|v| v.as_array())
        .ok_or_else(|| usage("reuse-index 需要 projects:[{id,sdir}]"))?;
    let tolerant = req.get("tolerant").and_then(|v| v.as_bool()).unwrap_or(false);
    let mut errors: Vec<Value> = Vec::new();
    let mut map: BTreeMap<String, (String, String, BTreeSet<String>)> = BTreeMap::new();
    let mut per_project: BTreeMap<String, u64> = BTreeMap::new();
    for (i, p) in projects.iter().enumerate() {
        let id = p
            .get("id")
            .and_then(|v| v.as_str())
            .filter(|s| !s.is_empty())
            .ok_or_else(|| usage(format!("projects[{i}].id 缺失")))?;
        let sdir = p.get("sdir").ok_or_else(|| usage(format!("projects[{i}].sdir 缺失")))?;
        let report = validate_sdir_value(sdir);
        if report.has_error() {
            if tolerant {
                errors.push(json!({"project": id, "code": "NF-SDIR-001", "message": report.issues.iter().find(|x| x.severity == "error").map(|x| x.message.clone()).unwrap_or_default()}));
                continue;
            }
            return Ok((1, report.to_value()));
        }
        let mut blocks: Vec<&Value> = Vec::new();
        collect(&sdir["blocks"][0], &mut blocks);
        let mut seen: BTreeSet<String> = BTreeSet::new();
        for b in blocks {
            let h = intrinsic(b);
            if h.is_empty() || !seen.insert(h.clone()) {
                continue;
            }
            let e = map.entry(h).or_insert_with(|| (type_of(b).to_string(), text_of(b).to_string(), BTreeSet::new()));
            e.2.insert(id.to_string());
        }
        per_project.insert(id.to_string(), seen.len() as u64);
    }
    let blocks: Vec<Value> = map
        .iter()
        .map(|(h, (ty, text, projects))| {
            json!({"hash": h, "type": ty, "text": text, "projects": projects.iter().cloned().collect::<Vec<_>>()})
        })
        .collect();
    let reused = blocks.iter().filter(|b| b["projects"].as_array().map(|a| a.len() > 1).unwrap_or(false)).count();
    Ok((0, json!({
        "schema": "nf-reuse-index/1",
        "blocks": blocks,
        "projects": per_project,
        "errors": errors,
        "summary": {"blocks": blocks.len() as u64, "reused": reused as u64, "projects": per_project.len() as u64, "errors": errors.len() as u64}
    })))
}

pub fn impact(req: &Value) -> OpOutcome {
    let index = req_value(req, "index")?;
    let changed: BTreeSet<String> = req
        .get("changed")
        .and_then(|v| v.as_array())
        .map(|a| a.iter().filter_map(|x| x.as_str().map(|s| s.to_string())).collect())
        .unwrap_or_default();
    if changed.is_empty() {
        return Err(usage("reuse-impact 需要 changed:[hash]"));
    }
    let mut affected: BTreeMap<String, BTreeSet<String>> = BTreeMap::new();
    for b in index.get("blocks").and_then(|v| v.as_array()).into_iter().flatten() {
        let h = b.get("hash").and_then(|v| v.as_str()).unwrap_or("");
        if !changed.contains(h) {
            continue;
        }
        for pid in b.get("projects").and_then(|v| v.as_array()).into_iter().flatten() {
            if let Some(p) = pid.as_str() {
                affected.entry(p.to_string()).or_default().insert(h.to_string());
            }
        }
    }
    let out: Vec<Value> = affected
        .iter()
        .map(|(p, hs)| json!({"project": p, "blocks": hs.iter().cloned().collect::<Vec<_>>()}))
        .collect();
    Ok((0, json!({
        "schema": "nf-reuse-impact/1",
        "affected": out,
        "summary": {"projects": affected.len() as u64, "blocks": changed.len() as u64}
    })))
}

pub fn reuse_index_op(req: &Value) -> OpOutcome { index(req) }
pub fn reuse_impact_op(req: &Value) -> OpOutcome { impact(req) }
