//! nf-sdir 校验（validate_sdir_value / validate_op）。
//!
//! 自 `sdir.rs` 按职责拆出：实现逐字搬运，逻辑与文案未改；公共 API 由父模块 `pub use` 保持原路径。

use super::parse::{find_block, is_hash64, str_field, walk};
use crate::canonical::digest_value;
use crate::error::OpOutcome;
use crate::ops::req_value;
use crate::report::Report;
use crate::schema::validate;
use serde_json::{json, Map, Value};
use std::collections::{BTreeMap, BTreeSet};

pub fn validate_sdir_value(sdir: &Value) -> Report {
    let id = sdir.get("meta").and_then(|m| m.get("title")).and_then(|v| v.as_str()).unwrap_or("sdir");
    let mut report = Report::new("L0", sdir, "sdir", id);
    for i in validate("nf-sdir", sdir) {
        report.error("NF-SDIR-001", &i.path, &i.message);
    }
    if report.has_error() {
        return report;
    }
    let blocks = sdir.get("blocks").and_then(|v| v.as_array()).cloned().unwrap_or_default();
    if blocks.len() != 1 {
        report.error("NF-SDIR-001", "$.blocks", "SDIR 必须恰好有一个 document 根块");
        return report;
    }
    let root = &blocks[0];
    if str_field(root, "type") != "document" {
        report.error("NF-SDIR-001", "$.blocks[0].type", "根块类型必须是 document");
    }
    let mut flat: Vec<(&Value, Option<&Value>, usize)> = Vec::new();
    walk(root, None, &mut flat, 0);
    let mut ids: BTreeSet<String> = BTreeSet::new();
    let mut hashes: BTreeMap<String, String> = BTreeMap::new();
    for (b, parent, _) in &flat {
        let id = str_field(b, "id");
        if !ids.insert(id.to_string()) {
            report.error("NF-SDIR-002", &format!("$.blocks[id={id}]"), "块 id 重复");
        }
        let ty = str_field(b, "type");
        let ok_parent = match ty {
            "list_item" => parent.map(|p| str_field(p, "type") == "list").unwrap_or(false),
            "table_row" => parent.map(|p| str_field(p, "type") == "table").unwrap_or(false),
            "table_cell" => parent.map(|p| str_field(p, "type") == "table_row").unwrap_or(false),
            "caption" => true,
            _ => true,
        };
        if !ok_parent {
            report.error("NF-SDIR-001", &format!("$.blocks[id={id}].type"), "块类型与父块不匹配");
        }
        if ty == "heading" {
            let lvl = b.get("attrs").and_then(|x| x.get("level")).and_then(|x| x.as_u64()).unwrap_or(0);
            if !(1..=6).contains(&lvl) {
                report.error("NF-SDIR-001", &format!("$.blocks[id={id}].attrs.level"), "标题层级必须是 1-6");
            }
        }
        let hash = str_field(b, "hash").to_string();
        if !is_hash64(&hash) {
            report.error("NF-SDIR-002", &format!("$.blocks[id={id}].hash"), "块 hash 不是 64 位小写十六进制");
        }
        // 重新计算 hash（children 只取 child hash）
        let child_hashes: Vec<Value> = b
            .get("children")
            .and_then(|v| v.as_array())
            .map(|a| a.iter().map(|c| Value::String(str_field(c, "hash").to_string())).collect())
            .unwrap_or_default();
        let mut m = Map::new();
        m.insert("type".into(), Value::String(ty.to_string()));
        m.insert("text".into(), Value::String(str_field(b, "text").to_string()));
        m.insert("attrs".into(), b.get("attrs").cloned().unwrap_or_else(|| json!({})));
        m.insert("children".into(), Value::Array(child_hashes));
        if let Some(p) = b.get("page") {
            m.insert("page".into(), p.clone());
        }
        if let Some(bb) = b.get("bbox") {
            m.insert("bbox".into(), bb.clone());
        }
        match digest_value(&Value::Object(m)) {
            Ok(calc) if calc != hash => {
                report.error("NF-SDIR-002", &format!("$.blocks[id={id}].hash"), "块 hash 与内容不符（篡改或未重算）");
            }
            Err(e) => report.error("NF-SDIR-002", &format!("$.blocks[id={id}].attrs"), &e.message),
            _ => {}
        }
        hashes.insert(id.to_string(), hash);
    }
    let sources: BTreeMap<String, String> = sdir
        .get("sources")
        .and_then(|v| v.as_array())
        .map(|a| {
            a.iter()
                .map(|s| (str_field(s, "id").to_string(), str_field(s, "bytes_sha").to_string()))
                .collect()
        })
        .unwrap_or_default();
    let mut prov_blocks: BTreeSet<String> = BTreeSet::new();
    for p in sdir.get("provenance").and_then(|v| v.as_array()).into_iter().flatten() {
        let b = str_field(p, "block").to_string();
        prov_blocks.insert(b.clone());
        if !ids.contains(&b) {
            report.error("NF-SDIR-002", "$.provenance", "溯源引用了不存在的块");
        }
        let sid = str_field(p, "source_id");
        match sources.get(sid) {
            None => report.error("NF-SDIR-002", "$.provenance.source_id", "溯源 source_id 不在 sources"),
            Some(sha) => {
                let ok = p
                    .get("input_hashes")
                    .and_then(|v| v.as_array())
                    .map(|a| a.iter().any(|h| h.as_str() == Some(sha)))
                    .unwrap_or(false);
                if !ok {
                    report.error("NF-SDIR-002", "$.provenance.input_hashes", "溯源 input_hashes 未包含 source.bytes_sha");
                }
            }
        }
        if p.get("transform").and_then(|v| v.as_array()).map(|a| a.is_empty()).unwrap_or(true) {
            report.error("NF-SDIR-002", "$.provenance.transform", "每个块必须有非空 transform");
        }
    }
    for id in &ids {
        if !prov_blocks.contains(id) {
            report.error("NF-SDIR-002", &format!("$.provenance[id={id}]"), "块缺溯源（无溯源不能进 SDIR）");
        }
    }
    let mut a11y_blocks: BTreeSet<String> = BTreeSet::new();
    let mut orders: BTreeSet<u64> = BTreeSet::new();
    for a in sdir.get("accessibility").and_then(|v| v.as_array()).into_iter().flatten() {
        let b = str_field(a, "block").to_string();
        if !ids.contains(&b) {
            report.error("NF-SDIR-002", "$.accessibility", "可访问性引用了不存在的块");
        }
        if !a11y_blocks.insert(b.clone()) {
            report.error("NF-SDIR-002", "$.accessibility", "同一块有多条可访问性记录");
        }
        if let Some(o) = a.get("reading_order").and_then(|v| v.as_u64()) {
            if !orders.insert(o) {
                report.error("NF-SDIR-002", "$.accessibility.reading_order", "reading_order 重复");
            }
        } else {
            report.error("NF-SDIR-001", "$.accessibility.reading_order", "缺 reading_order");
        }
        if a.get("missing").and_then(|v| v.as_array()).is_none() {
            report.error("NF-SDIR-001", "$.accessibility.missing", "missing 必须显式给出（可为空数组）");
        }
    }
    for id in &ids {
        if !a11y_blocks.contains(id) {
            report.error("NF-SDIR-002", &format!("$.accessibility[id={id}]"), "块缺可访问性记录");
        }
    }
    for r in sdir.get("relations").and_then(|v| v.as_array()).into_iter().flatten() {
        let from = str_field(r, "from");
        let to = str_field(r, "to");
        if !ids.contains(from) || !ids.contains(to) {
            report.error("NF-SDIR-002", "$.relations", "关系端点不存在（悬空引用）");
        }
        if let Some(target) = find_block(root, to) {
            if str_field(r, "kind") == "crossref" && str_field(target, "type") != "heading" {
                report.error("NF-SDIR-002", "$.relations.kind", "crossref 目标必须是 heading");
            }
        }
    }
    report
}

pub fn validate_op(req: &Value) -> OpOutcome {
    let sdir = req_value(req, "sdir")?;
    let report = validate_sdir_value(sdir);
    if report.has_error() {
        Ok((1, report.to_value()))
    } else {
        Ok((0, report.to_value()))
    }
}
