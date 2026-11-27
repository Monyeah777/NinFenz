//! 其余源导入与融合（EPUB / doc / fuse / import_op）。
//!
//! 自 `sdir.rs` 按职责拆出：实现逐字搬运，逻辑与文案未改；公共 API 由父模块 `pub use` 保持原路径。

use super::imports::{assemble_sdir, import_markdown, source_from_request};
use super::Node;
use super::markup::{attr_value, import_docx, normalize_href, parse_html_blocks, strip_html};
use super::merge::{filter_array, filter_relations, flatten_with_parent, merge_array_by_key, merge_maps, merge_relations, rebuild, Flat};
use super::parse::{parse_markdown, str_field};
use super::validate::validate_sdir_value;
use crate::error::{CoreError, OpOutcome};
use crate::fsutil;
use crate::ops::{req_value, usage};
use crate::report::Report;
use crate::schema::validate;
use crate::zipsec;
use regex::Regex;
use serde_json::{json, Value};
use std::collections::{BTreeMap, BTreeSet};

pub fn import_epub(req: &Value) -> OpOutcome {
    let path = req
        .get("epub_path")
        .and_then(|v| v.as_str())
        .ok_or_else(|| usage("sdir-import 需要 epub_path"))?;
    let bytes = fsutil::read_bytes(std::path::Path::new(&path.replace('\\', "/")), crate::limits::limits().pack_max_file_bytes)?;
    let entries = zipsec::read_zip_bytes(&bytes)?;
    let container = entries
        .iter()
        .find(|e| e.name == "META-INF/container.xml")
        .ok_or_else(|| CoreError::new("NF-SDIR-003").with_message("EPUB 缺 META-INF/container.xml").with_exit(3))?;
    let container_xml = String::from_utf8(container.data.clone()).map_err(|_| CoreError::new("NF-SDIR-003").with_message("container.xml 非 UTF-8").with_exit(3))?;
    let opf_path = attr_value(&container_xml, "full-path")
        .ok_or_else(|| CoreError::new("NF-SDIR-003").with_message("container.xml 缺 rootfile full-path").with_exit(3))?;
    let opf = entries
        .iter()
        .find(|e| e.name == opf_path)
        .ok_or_else(|| CoreError::new("NF-SDIR-003").with_message(format!("EPUB 缺 OPF：{opf_path}")).with_exit(3))?;
    let opf_xml = String::from_utf8(opf.data.clone()).map_err(|_| CoreError::new("NF-SDIR-003").with_message("OPF 非 UTF-8").with_exit(3))?;
    let mut manifest: BTreeMap<String, String> = BTreeMap::new();
    for cap in Regex::new(r"(?is)<item\b([^>]*)>").unwrap().captures_iter(&opf_xml) {
        if let (Some(id), Some(href)) = (attr_value(&cap[1], "id"), attr_value(&cap[1], "href")) {
            manifest.insert(id, href);
        }
    }
    let base = match opf_path.rfind('/') {
        Some(p) => &opf_path[..p],
        None => "",
    };
    let mut flat: Vec<Node> = Vec::new();
    for cap in Regex::new(r"(?is)<itemref\b([^>]*)>").unwrap().captures_iter(&opf_xml) {
        let idref = match attr_value(&cap[1], "idref") {
            Some(v) => v,
            None => continue,
        };
        let href = match manifest.get(&idref) {
            Some(v) => v,
            None => continue,
        };
        let full = normalize_href(base, href);
        if let Some(entry) = entries.iter().find(|e| e.name == full) {
            if let Ok(xhtml) = String::from_utf8(entry.data.clone()) {
                flat.extend(parse_html_blocks(&xhtml));
            }
        }
    }
    if flat.is_empty() {
        return Err(CoreError::new("NF-SDIR-003").with_message("EPUB 无可读正文（检查 OPF/spine/XHTML）").with_exit(3));
    }
    let title = Regex::new(r"(?is)<dc:title[^>]*>(.*?)</dc:title>")
        .unwrap()
        .captures(&opf_xml)
        .and_then(|c| c.get(1))
        .map(|m| strip_html(m.as_str()))
        .unwrap_or_else(|| "未命名 EPUB".to_string());
    let normalized = path.replace('\\', "/");
    let default_name = std::path::Path::new(&normalized)
        .file_name()
        .and_then(|s| s.to_str())
        .unwrap_or("source.epub")
        .to_string();
    let source = source_from_request(req, &bytes, &default_name, "application/epub+zip")?;
    let sdir = assemble_sdir(req, flat, source, "epub", "epub-xhtml/1", None, &title)?;
    Ok((0, sdir))
}

pub fn fuse_op(req: &Value) -> OpOutcome {
    let sources = req
        .get("sources")
        .and_then(|v| v.as_array())
        .filter(|a| !a.is_empty())
        .ok_or_else(|| usage("sdir-fuse 需要非空 sources:[sdir]"))?;
    let first = &sources[0];
    let report = validate_sdir_value(first);
    if report.has_error() {
        return Ok((1, report.to_value()));
    }
    let mut current = first.clone();
    let mut all_sources: Value = first.get("sources").cloned().unwrap_or_else(|| json!([]));
    let mut conflicts: Vec<Value> = Vec::new();
    for (idx, next) in sources.iter().enumerate().skip(1) {
        let report = validate_sdir_value(next);
        if report.has_error() {
            return Ok((1, report.to_value()));
        }
        let cur = flatten_with_parent(&current["blocks"][0]);
        let nxt = flatten_with_parent(&next["blocks"][0]);
        let empty: BTreeMap<String, Flat> = BTreeMap::new();
        let (merged, mut c) = merge_maps(&empty, &cur, &nxt);
        for item in &mut c {
            if let Value::Object(m) = item {
                m.insert("source_index".into(), Value::Number((idx as u64).into()));
            }
        }
        conflicts.extend(c);
        let ids: BTreeSet<String> = merged.keys().cloned().collect();
        let relations = filter_relations(merge_relations(&current["relations"], &next["relations"]), &ids);
        let a11y = filter_array(merge_array_by_key(&current["accessibility"], &next["accessibility"], "block"), "block", &ids);
        let prov = filter_array(merge_array_by_key(&current["provenance"], &next["provenance"], "block"), "block", &ids);
        all_sources = merge_array_by_key(&all_sources, &next["sources"], "id");
        current = rebuild(&current["meta"], &all_sources, &merged, &relations, &a11y, &prov)?;
    }
    let out = json!({
        "schema": "nf-sdir-fusion/1",
        "sdir": current,
        "conflicts": conflicts,
        "summary": {"sources": sources.len() as u64, "conflicts": conflicts.len() as u64}
    });
    if out["conflicts"].as_array().map(|a| !a.is_empty()).unwrap_or(false) {
        let mut rep = Report::new("L0", &current, "sdir-fusion", "fusion");
        for c in out["conflicts"].as_array().unwrap() {
            rep.error("NF-SDIR-004", c.get("block").and_then(|v| v.as_str()).unwrap_or("$"), "多源融合存在未裁决差异");
        }
        let mut value = rep.to_value();
        value.as_object_mut().unwrap().insert("sdir".into(), out["sdir"].clone());
        value.as_object_mut().unwrap().insert("conflicts".into(), out["conflicts"].clone());
        Ok((1, value))
    } else {
        Ok((0, out))
    }
}
pub fn import_doc(req: &Value) -> OpOutcome {
    let doc = req_value(req, "doc")?;
    let issues = validate("nf-doc", doc);
    if !issues.is_empty() {
        return Err(CoreError::new("NF-SDIR-003")
            .with_message(format!("nf-doc 结构非法：{}", issues[0].message))
            .with_exit(1));
    }
    let mut md = String::new();
    let title = doc
        .get("meta")
        .and_then(|m| m.get("title"))
        .and_then(|v| v.as_str())
        .unwrap_or("未命名文档");
    for b in doc.get("blocks").and_then(|v| v.as_array()).into_iter().flatten() {
        let ty = str_field(b, "type");
        let text = str_field(b, "text");
        let title = str_field(b, "title");
        match ty {
            "section" => {
                md.push_str("## ");
                md.push_str(if title.is_empty() { text } else { title });
                md.push_str("\n\n");
            }
            "list" => {
                for line in text.split('\n') {
                    md.push_str("- ");
                    md.push_str(line.trim());
                    md.push('\n');
                }
                md.push('\n');
            }
            "table" => {
                md.push_str(text);
                md.push_str("\n\n");
            }
            "code" => {
                md.push_str("```\n");
                md.push_str(text);
                md.push_str("\n```\n\n");
            }
            "quote" => {
                for line in text.split('\n') {
                    md.push_str("> ");
                    md.push_str(line);
                    md.push('\n');
                }
                md.push('\n');
            }
            _ => {
                md.push_str(text);
                md.push_str("\n\n");
            }
        }
    }
    let flat = parse_markdown(&md);
    if flat.is_empty() {
        return Err(CoreError::new("NF-SDIR-003").with_message("nf-doc 无可用块").with_exit(3));
    }
    let bytes = crate::canonical::canonical_bytes(doc)?;
    let source = source_from_request(req, &bytes, "doc.nfdoc.json", "application/json")?;
    let sdir = assemble_sdir(req, flat, source, "nf-doc", "nf-doc-adapter/1", None, title)?;
    Ok((0, sdir))
}

pub fn import_op(req: &Value) -> OpOutcome {
    if req.get("markdown").is_some() {
        import_markdown(req)
    } else if req.get("docx_path").is_some() {
        import_docx(req)
    } else if req.get("epub_path").is_some() {
        import_epub(req)
    } else if req.get("doc").is_some() {
        import_doc(req)
    } else {
        Err(usage("sdir-import 需要 markdown、docx_path、epub_path 或 doc"))
    }
}
