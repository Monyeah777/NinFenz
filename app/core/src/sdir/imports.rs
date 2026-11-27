//! 源适配公共层与 Markdown 导入（source_from_request / import_markdown / assemble_sdir）。
//!
//! 自 `sdir.rs` 按职责拆出：实现逐字搬运，逻辑与文案未改；公共 API 由父模块 `pub use` 保持原路径。

use super::parse::*;
use super::{Node, IMPORT_TRANSFORM, SDIR_SCHEMA};
use super::validate::validate_sdir_value;
use crate::canonical::sha256_hex;
use crate::error::{CoreError, OpOutcome};
use crate::ops::{opt_str, usage};
use serde_json::{json, Map, Value};
use std::collections::{BTreeMap, BTreeSet};

pub fn source_from_request(req: &Value, bytes: &[u8], default_name: &str, default_mime: &str) -> Result<Value, CoreError> {
    let src = req.get("source").filter(|v| v.is_object());
    let name = src.and_then(|s| s.get("name")).and_then(|v| v.as_str()).unwrap_or(default_name);
    let mime = src.and_then(|s| s.get("mime")).and_then(|v| v.as_str()).unwrap_or(default_mime);
    let sha = sha256_hex(bytes);
    if let Some(given) = src.and_then(|s| s.get("bytes_sha")).and_then(|v| v.as_str()) {
        if given != sha {
            return Err(CoreError::new("NF-SDIR-002")
                .with_message(format!("source.bytes_sha {given} 与实际字节摘要 {sha} 不符"))
                .at("$.source.bytes_sha")
                .with_exit(1));
        }
    }
    let mut m = Map::new();
    m.insert("id".into(), Value::String("s1".into()));
    m.insert("name".into(), Value::String(name.to_string()));
    m.insert("mime".into(), Value::String(mime.to_string()));
    m.insert("bytes_sha".into(), Value::String(sha));
    m.insert("size".into(), Value::Number((bytes.len() as u64).into()));
    Ok(Value::Object(m))
}

pub(super) fn build_relations(root: &Value) -> (Vec<Value>, BTreeMap<String, String>) {
    let mut flat: Vec<(&Value, Option<&Value>, usize)> = Vec::new();
    walk(root, None, &mut flat, 0);
    let mut by_anchor: BTreeMap<String, String> = BTreeMap::new();
    for (b, _, _) in &flat {
        if str_field(b, "type") == "heading" {
            if let Some(a) = b.get("attrs").and_then(|x| x.get("anchor")).and_then(|x| x.as_str()) {
                by_anchor.insert(a.to_string(), str_field(b, "id").to_string());
            }
        }
    }
    let mut rels: Vec<Value> = Vec::new();
    let root_id = str_field(root, "id").to_string();
    for (b, _, _) in &flat {
        if str_field(b, "type") == "heading" {
            rels.push(json!({"from": root_id, "to": str_field(b, "id"), "kind": "toc"}));
        }
    }
    // 交叉引用：](#anchor)
    for (b, _, _) in &flat {
        let id = str_field(b, "id").to_string();
        let text = str_field(b, "text");
        let mut rest = text;
        while let Some(pos) = rest.find("](#") {
            let after = &rest[pos + 3..];
            if let Some(end) = after.find(')') {
                let anchor = &after[..end];
                if let Some(target) = by_anchor.get(anchor) {
                    rels.push(json!({"from": id, "to": target, "kind": "crossref"}));
                }
            }
            rest = &after;
        }
    }
    // 脚注：正文 [^label] -> footnote label
    let mut footnotes: BTreeMap<String, String> = BTreeMap::new();
    for (b, _, _) in &flat {
        if str_field(b, "type") == "footnote" {
            if let Some(label) = b.get("attrs").and_then(|x| x.get("label")).and_then(|x| x.as_str()) {
                footnotes.insert(label.to_string(), str_field(b, "id").to_string());
            }
        }
    }
    for (b, _, _) in &flat {
        let id = str_field(b, "id").to_string();
        let text = str_field(b, "text");
        let mut rest = text;
        while let Some(pos) = rest.find("[^") {
            let after = &rest[pos + 2..];
            if let Some(end) = after.find(']') {
                let label = &after[..end];
                if let Some(target) = footnotes.get(label) {
                    rels.push(json!({"from": id, "to": target, "kind": "footnote"}));
                }
            }
            rest = &after;
        }
    }
    // 图注：figure 紧跟 caption 文本以 "^ " 开头（此处只按顺序连接紧邻的 caption 类型）
    for i in 0..flat.len() {
        if str_field(flat[i].0, "type") == "figure" {
            if i + 1 < flat.len() && str_field(flat[i + 1].0, "type") == "caption" {
                rels.push(json!({"from": flat[i].0["id"], "to": flat[i + 1].0["id"], "kind": "caption"}));
            }
        }
    }
    (rels, by_anchor)
}

pub(super) fn a11y_for(root: &Value, lang: &str) -> Value {
    let mut flat: Vec<(&Value, Option<&Value>, usize)> = Vec::new();
    walk(root, None, &mut flat, 0);
    let mut out: Vec<Value> = Vec::new();
    let mut order = 0u64;
    for (b, _, _) in &flat {
        let ty = str_field(b, "type");
        let id = str_field(b, "id").to_string();
        let mut missing: Vec<Value> = Vec::new();
        let role = match ty {
            "document" => "document",
            "heading" => "heading",
            "paragraph" => "paragraph",
            "list" => "list",
            "list_item" => "listitem",
            "table" => "table",
            "table_row" => "row",
            "table_cell" => "cell",
            "figure" => "img",
            "caption" => "caption",
            "footnote" => "doc-footnote",
            "footnote_ref" => "doc-noteref",
            "crossref" => "link",
            "citation" => "cite",
            "code" => "code",
            "math" => "math",
            "quote" => "blockquote",
            "section" => "region",
            "index" => "list",
            _ => "none",
        };
        let mut m = Map::new();
        m.insert("block".into(), Value::String(id.clone()));
        m.insert("role".into(), Value::String(role.into()));
        m.insert("reading_order".into(), Value::Number(order.into()));
        order += 1;
        if !lang.is_empty() {
            m.insert("lang".into(), Value::String(lang.to_string()));
        }
        if ty == "heading" {
            let lvl = b.get("attrs").and_then(|x| x.get("level")).and_then(|x| x.as_u64()).unwrap_or(2);
            m.insert("header".into(), Value::String(format!("h{lvl}")));
        }
        if ty == "figure" {
            let alt = str_field(b, "text");
            if alt.is_empty() {
                missing.push(Value::String("alt".into()));
            } else {
                m.insert("alt".into(), Value::String(alt.to_string()));
            }
        }
        if ty == "table" {
            let has_header = b
                .get("attrs")
                .and_then(|x| x.get("header"))
                .and_then(|x| x.as_bool())
                .unwrap_or(false);
            if !has_header {
                missing.push(Value::String("header".into()));
            }
        }
        m.insert("missing".into(), Value::Array(missing));
        out.push(Value::Object(m));
    }
    Value::Array(out)
}

pub(super) fn provenance_for(root: &Value, source_id: &str, bytes_sha: &str, parser: &str, page: Option<u64>) -> Value {
    let mut flat: Vec<(&Value, Option<&Value>, usize)> = Vec::new();
    walk(root, None, &mut flat, 0);
    let mut out: Vec<Value> = Vec::new();
    for (b, _, _) in &flat {
        let mut item = json!({
            "block": str_field(b, "id"),
            "source_id": source_id,
            "transform": [IMPORT_TRANSFORM, parser],
            "input_hashes": [bytes_sha]
        });
        let block_page = b.get("page").and_then(|v| v.as_u64()).or(page);
        if let Some(p) = block_page {
            item.as_object_mut().unwrap().insert("page".into(), Value::Number(p.into()));
        }
        if let Some(bb) = b.get("bbox") {
            item.as_object_mut().unwrap().insert("bbox".into(), bb.clone());
        }
        out.push(item);
    }
    Value::Array(out)
}

pub fn import_markdown(req: &Value) -> OpOutcome {
    let markdown = req
        .get("markdown")
        .and_then(|v| v.as_str())
        .ok_or_else(|| usage("sdir-import 需要 markdown 或 doc"))?;
    let created_at = req
        .get("created_at")
        .and_then(|v| v.as_str())
        .filter(|s| !s.is_empty())
        .ok_or_else(|| usage("sdir-import 需要显式 created_at（确定性）"))?;
    let source = source_from_request(req, markdown.as_bytes(), "source.md", "text/markdown")?;
    let source_id = str_field(&source, "id").to_string();
    let bytes_sha = str_field(&source, "bytes_sha").to_string();
    let mut flat = parse_markdown(markdown);
    let mut counter = 0u64;
    assign_ids(&mut flat, &mut counter);
    let (mut root, _anchors) = build_tree(flat);
    root.id = "b0000".to_string();
    // 标题 anchor + 唯一化
    let mut seen: BTreeSet<String> = BTreeSet::new();
    fn set_anchor(n: &mut Node, seen: &mut BTreeSet<String>) {
        if n.btype == "heading" {
            let base = slug(&n.text);
            let mut a = base.clone();
            let mut k = 2u64;
            while !seen.insert(a.clone()) {
                a = format!("{base}-{k}");
                k += 1;
            }
            if let Value::Object(m) = &mut n.attrs {
                m.insert("anchor".into(), Value::String(a));
            }
        }
        for c in n.children.iter_mut() {
            set_anchor(c, seen);
        }
    }
    set_anchor(&mut root, &mut seen);
    let root_val = finalize(&mut root)?;
    let title = opt_str(req, "title")?
        .map(|s| s.to_string())
        .filter(|s| !s.trim().is_empty())
        .unwrap_or_else(|| {
            root_val
                .get("children")
                .and_then(|v| v.as_array())
                .and_then(|a| a.iter().find(|b| str_field(b, "type") == "heading"))
                .map(|h| str_field(h, "text").to_string())
                .unwrap_or_else(|| "未命名文档".to_string())
        });
    let (relations, _) = build_relations(&root_val);
    let a11y = a11y_for(&root_val, opt_str(req, "lang")?.unwrap_or(""));
    let provenance = provenance_for(&root_val, &source_id, &bytes_sha, "markdown-parse/1", Some(1));
    let sdir = json!({
        "schema": SDIR_SCHEMA,
        "meta": {
            "title": title,
            "created_at": created_at,
            "generator": "nf-app-core/sdir-import/1",
            "source_format": "markdown",
            "lang": opt_str(req, "lang")?.unwrap_or("und")
        },
        "sources": [source],
        "blocks": [root_val],
        "relations": relations,
        "accessibility": a11y,
        "provenance": provenance
    });
    let report = validate_sdir_value(&sdir);
    if report.has_error() {
        return Ok((1, report.to_value()));
    }
    Ok((0, sdir))
}

pub(super) fn fidelity_for(root: &Value, source_format: &str, source_pages: u64, default_page: Option<u64>) -> Value {
    let mut flat: Vec<(&Value, Option<&Value>, usize)> = Vec::new();
    walk(root, None, &mut flat, 0);
    let mut counts: BTreeMap<String, u64> = BTreeMap::new();
    let mut unprovenanced = 0u64;
    for (b, _, _) in &flat {
        let ty = str_field(b, "type");
        *counts.entry(ty.to_string()).or_insert(0) += 1;
        if ty != "document" {
            let has_page = b.get("page").and_then(|v| v.as_u64()).or(default_page).is_some();
            let has_bbox = b.get("bbox").is_some();
            if !has_page || !has_bbox {
                unprovenanced += 1;
            }
        }
    }
    json!({
        "source_format": source_format,
        "source_pages": source_pages,
        "features": counts,
        "unprovenanced_blocks": unprovenanced,
        "losses": []
    })
}

pub(crate) fn assemble_sdir(
    req: &Value,
    mut flat: Vec<Node>,
    source: Value,
    source_format: &str,
    parser: &str,
    page: Option<u64>,
    default_title: &str,
) -> Result<Value, CoreError> {
    let created_at = req
        .get("created_at")
        .and_then(|v| v.as_str())
        .filter(|s| !s.is_empty())
        .ok_or_else(|| usage("sdir-import 需要显式 created_at（确定性）"))?;
    let source_id = str_field(&source, "id").to_string();
    let bytes_sha = str_field(&source, "bytes_sha").to_string();
    let mut counter = 0u64;
    assign_ids(&mut flat, &mut counter);
    let (mut root, _anchors) = build_tree(flat);
    root.id = "b0000".to_string();
    let mut seen: BTreeSet<String> = BTreeSet::new();
    fn set_anchor(n: &mut Node, seen: &mut BTreeSet<String>) {
        if n.btype == "heading" {
            let base = slug(&n.text);
            let mut a = base.clone();
            let mut k = 2u64;
            while !seen.insert(a.clone()) {
                a = format!("{base}-{k}");
                k += 1;
            }
            if let Value::Object(m) = &mut n.attrs {
                m.insert("anchor".into(), Value::String(a));
            }
        }
        for c in n.children.iter_mut() {
            set_anchor(c, seen);
        }
    }
    set_anchor(&mut root, &mut seen);
    let root_val = finalize(&mut root)?;
    let title = opt_str(req, "title")?
        .map(|s| s.to_string())
        .filter(|s| !s.trim().is_empty())
        .unwrap_or_else(|| {
            root_val
                .get("children")
                .and_then(|v| v.as_array())
                .and_then(|a| a.iter().find(|b| str_field(b, "type") == "heading"))
                .map(|h| str_field(h, "text").to_string())
                .filter(|s| !s.trim().is_empty())
                .unwrap_or_else(|| default_title.to_string())
        });
    let (relations, _) = build_relations(&root_val);
    let a11y = a11y_for(&root_val, opt_str(req, "lang")?.unwrap_or(""));
    let provenance = provenance_for(&root_val, &source_id, &bytes_sha, parser, page);
    let source_pages = source.get("pages").and_then(|v| v.as_u64()).unwrap_or(1);
    let fidelity = fidelity_for(&root_val, source_format, source_pages, page);
    let sdir = json!({
        "schema": SDIR_SCHEMA,
        "meta": {
            "title": title,
            "created_at": created_at,
            "generator": "nf-app-core/sdir-import/1",
            "source_format": source_format,
            "lang": opt_str(req, "lang")?.unwrap_or("und"),
            "fidelity": fidelity
        },
        "sources": [source],
        "blocks": [root_val],
        "relations": relations,
        "accessibility": a11y,
        "provenance": provenance
    });
    let report = validate_sdir_value(&sdir);
    if report.has_error() {
        return Err(CoreError::new("NF-SDIR-001")
            .with_message(format!("SDIR 自校验失败：{:?}", report.issues.first().map(|i| i.message.clone())))
            .with_exit(1));
    }
    Ok(sdir)
}
