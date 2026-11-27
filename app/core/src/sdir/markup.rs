//! DOCX / HTML 导入适配器（parse_docx / parse_html_blocks 等）。
//!
//! 自 `sdir.rs` 按职责拆出：实现逐字搬运，逻辑与文案未改；公共 API 由父模块 `pub use` 保持原路径。

use super::imports::{assemble_sdir, source_from_request};
use super::Node;
use crate::error::{CoreError, OpOutcome};
use crate::fsutil;
use crate::ops::usage;
use crate::zipsec;
use regex::Regex;
use serde_json::{json, Value};
use std::sync::OnceLock;

pub(super) fn xml_unescape(s: &str) -> String {
    s.replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&quot;", "\"")
        .replace("&apos;", "'")
        .replace("&amp;", "&")
}

pub(super) fn docx_text(fragment: &str) -> String {
    static T: OnceLock<Regex> = OnceLock::new();
    let re = T.get_or_init(|| Regex::new(r"(?s)<w:t(?:\s[^>]*)?>(.*?)</w:t>").expect("w:t regex"));
    let mut out = String::new();
    for c in re.captures_iter(fragment) {
        out.push_str(&xml_unescape(&c[1]));
    }
    out
}

pub(super) fn docx_para_block(p: &str) -> Option<Node> {
    static STYLE: OnceLock<Regex> = OnceLock::new();
    static OUTLINE: OnceLock<Regex> = OnceLock::new();
    static DOCPR: OnceLock<Regex> = OnceLock::new();
    let style = STYLE
        .get_or_init(|| Regex::new(r#"<w:pStyle\s+w:val="([^"]+)""#).expect("pStyle"))
        .captures(p)
        .and_then(|c| c.get(1))
        .map(|m| m.as_str().to_string())
        .unwrap_or_default();
    let text = docx_text(p).trim().to_string();
    let alt = DOCPR
        .get_or_init(|| Regex::new(r#"<wp:docPr[^>]*\bdescr="([^"]*)""#).expect("docPr"))
        .captures(p)
        .and_then(|c| c.get(1))
        .map(|m| xml_unescape(m.as_str()))
        .unwrap_or_default();
    if text.is_empty() && alt.is_empty() && !p.contains("<w:drawing") {
        return None;
    }
    let level = OUTLINE
        .get_or_init(|| Regex::new(r#"<w:outlineLvl\s+w:val="([0-5])""#).expect("outlineLvl"))
        .captures(p)
        .and_then(|c| c.get(1))
        .and_then(|m| m.as_str().parse::<usize>().ok())
        .map(|v| v + 1)
        .or_else(|| {
            static H: OnceLock<Regex> = OnceLock::new();
            H.get_or_init(|| Regex::new(r"(?i)heading\s*([1-6])").expect("heading style"))
                .captures(&style)
                .and_then(|c| c.get(1))
                .and_then(|m| m.as_str().parse::<usize>().ok())
        });
    let mut node = if let Some(level) = level {
        let mut n = Node::new("heading", text);
        n.attrs = json!({"level": level});
        n
    } else if text.is_empty() && !alt.is_empty() {
        let mut n = Node::new("figure", alt);
        n.attrs = json!({"src": ""});
        n
    } else {
        Node::new("paragraph", text)
    };
    if p.contains("<w:numPr") && node.btype == "paragraph" {
        node.attrs = json!({"list_item": true});
    }
    Some(node)
}

pub(super) fn docx_table_block(tbl: &str) -> Node {
    static ROWS: OnceLock<Regex> = OnceLock::new();
    static CELLS: OnceLock<Regex> = OnceLock::new();
    let rows_re = ROWS.get_or_init(|| Regex::new(r"(?s)<w:tr[ >].*?</w:tr>").expect("w:tr"));
    let cells_re = CELLS.get_or_init(|| Regex::new(r"(?s)<w:tc[ >].*?</w:tc>").expect("w:tc"));
    let mut table = Node::new("table", "");
    let mut cols = 0usize;
    for row in rows_re.find_iter(tbl) {
        let is_header = row.as_str().contains("<w:tblHeader");
        let cells: Vec<&str> = cells_re.find_iter(row.as_str()).map(|m| m.as_str()).collect();
        cols = cols.max(cells.len());
        let mut tr = Node::new("table_row", "");
        tr.attrs = json!({"header": is_header});
        for cell in cells {
            let text = docx_text(cell).trim().to_string();
            let mut c = Node::new("table_cell", text);
            c.attrs = json!({"row": 0u64, "col": 0u64});
            tr.children.push(c);
        }
        if !tr.children.is_empty() {
            table.children.push(tr);
        }
    }
    let header = table
        .children
        .first()
        .and_then(|r| r.attrs.get("header"))
        .and_then(|v| v.as_bool())
        .unwrap_or(false);
    table.attrs = json!({"columns": cols as u64, "header": header});
    table
}

pub(super) fn parse_docx(document_xml: &str) -> Vec<Node> {
    static BLOCKS: OnceLock<Regex> = OnceLock::new();
    let re = BLOCKS.get_or_init(|| Regex::new(r"(?s)<w:tbl[ >].*?</w:tbl>|<w:p[ >].*?</w:p>").expect("docx blocks"));
    let mut flat: Vec<Node> = Vec::new();
    let mut list: Option<Node> = None;
    for m in re.find_iter(document_xml) {
        let frag = m.as_str();
        if frag.starts_with("<w:tbl") {
            if let Some(l) = list.take() {
                flat.push(l);
            }
            flat.push(docx_table_block(frag));
            continue;
        }
        if let Some(node) = docx_para_block(frag) {
            let is_list = node.attrs.get("list_item").and_then(|v| v.as_bool()).unwrap_or(false);
            if is_list {
                let mut item = node;
                item.btype = "list_item".to_string();
                item.attrs = json!({"ordered": false});
                let l = list.get_or_insert_with(|| {
                    let mut n = Node::new("list", "");
                    n.attrs = json!({"ordered": false});
                    n
                });
                l.children.push(item);
                continue;
            }
            if let Some(l) = list.take() {
                flat.push(l);
            }
            flat.push(node);
        }
    }
    if let Some(l) = list {
        flat.push(l);
    }
    flat
}

pub fn import_docx(req: &Value) -> OpOutcome {
    let path = req
        .get("docx_path")
        .and_then(|v| v.as_str())
        .ok_or_else(|| usage("sdir-import 需要 docx_path"))?;
    let bytes = fsutil::read_bytes(std::path::Path::new(&path.replace('\\', "/")), crate::limits::limits().pack_max_file_bytes)?;
    let entries = zipsec::read_zip_bytes(&bytes)?;
    let doc = entries
        .iter()
        .find(|e| e.name == "word/document.xml")
        .ok_or_else(|| CoreError::new("NF-SDIR-003").with_message("DOCX 缺 word/document.xml").with_exit(3))?;
    let xml = String::from_utf8(doc.data.clone()).map_err(|_| CoreError::new("NF-SDIR-003").with_message("document.xml 不是 UTF-8").with_exit(3))?;
    if xml.len() > 64 * 1024 * 1024 {
        return Err(CoreError::new("NF-SDIR-003").with_message("document.xml 超过 64 MiB").with_exit(3));
    }
    let lower = xml.to_ascii_lowercase();
    if lower.contains("<!doctype") || lower.contains("<!entity") {
        return Err(CoreError::new("NF-SEC-005").with_message("DOCX XML 含 DTD/ENTITY（禁用）").with_exit(3));
    }
    let flat = parse_docx(&xml);
    if flat.is_empty() {
        return Err(CoreError::new("NF-SDIR-003").with_message("DOCX 无可读块").with_exit(3));
    }
    let normalized = path.replace('\\', "/");
    let default_name = std::path::Path::new(&normalized)
        .file_name()
        .and_then(|s| s.to_str())
        .unwrap_or("source.docx")
        .to_string();
    let source = source_from_request(req, &bytes, &default_name, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")?;
    let sdir = assemble_sdir(req, flat, source, "docx", "docx-ooxml/1", None, "未命名文档")?;
    Ok((0, sdir))
}

pub(super) fn attr_value(tag: &str, name: &str) -> Option<String> {
    let pat = format!(r#"(?i)\b{}\s*=\s*"([^"]*)""#, regex::escape(name));
    Regex::new(&pat).ok()?.captures(tag).and_then(|c| c.get(1)).map(|m| m.as_str().to_string())
}

pub(super) fn html_unescape(s: &str) -> String {
    static NUM: OnceLock<Regex> = OnceLock::new();
    let re = NUM.get_or_init(|| Regex::new(r"&#(x?[0-9a-fA-F]+);").expect("numeric entity"));
    let mut out = String::new();
    let mut last = 0usize;
    for c in re.captures_iter(s) {
        out.push_str(&xml_unescape(&s[last..c.get(0).unwrap().start()]));
        let raw = &c[1];
        let code = if let Some(hex) = raw.strip_prefix('x').or_else(|| raw.strip_prefix('X')) {
            u32::from_str_radix(hex, 16).ok()
        } else {
            raw.parse::<u32>().ok()
        };
        if let Some(ch) = code.and_then(char::from_u32) {
            out.push(ch);
        }
        last = c.get(0).unwrap().end();
    }
    out.push_str(&xml_unescape(&s[last..]));
    out
}

pub(super) fn strip_html(s: &str) -> String {
    static TAGS: OnceLock<Regex> = OnceLock::new();
    let re = TAGS.get_or_init(|| Regex::new(r"(?s)<[^>]+>").expect("tags"));
    html_unescape(&re.replace_all(s, " ")).split_whitespace().collect::<Vec<_>>().join(" ")
}

pub(super) fn html_table(tbl: &str) -> Node {
    static ROWS: OnceLock<Regex> = OnceLock::new();
    static CELLS: OnceLock<Regex> = OnceLock::new();
    let rows_re = ROWS.get_or_init(|| Regex::new(r"(?s)<tr[^>]*>(.*?)</tr>").expect("tr"));
    let cells_re = CELLS.get_or_init(|| Regex::new(r"(?s)<t[hd][^>]*>(.*?)</t[hd]>").expect("td"));
    let mut table = Node::new("table", "");
    let mut cols = 0usize;
    for (ri, row) in rows_re.captures_iter(tbl).enumerate() {
        let cells: Vec<String> = cells_re.captures_iter(&row[1]).map(|c| strip_html(&c[1])).collect();
        cols = cols.max(cells.len());
        let mut tr = Node::new("table_row", "");
        tr.attrs = json!({"header": ri == 0 && row[0].contains("<th")});
        for text in cells {
            let mut c = Node::new("table_cell", text);
            c.attrs = json!({"row": ri as u64, "col": 0u64});
            tr.children.push(c);
        }
        table.children.push(tr);
    }
    let header = table.children.first().and_then(|r| r.attrs.get("header")).and_then(|v| v.as_bool()).unwrap_or(false);
    table.attrs = json!({"columns": cols as u64, "header": header});
    table
}

pub(super) fn parse_html_blocks(html: &str) -> Vec<Node> {
    static TAGS: OnceLock<Regex> = OnceLock::new();
    let tag_re = TAGS.get_or_init(|| Regex::new(r"(?is)<([a-z][a-z0-9]*)([^>]*)>").expect("html tag"));
    let lower = html.to_ascii_lowercase();
    let mut flat: Vec<Node> = Vec::new();
    let mut list: Option<Node> = None;
    let mut i = 0usize;
    while i < html.len() {
        let cap = match tag_re.captures_at(html, i) {
            Some(c) => c,
            None => break,
        };
        let whole = cap.get(0).unwrap();
        let name = cap[1].to_ascii_lowercase();
        let attrs = &cap[2];
        let after = whole.end();
        if !matches!(name.as_str(), "h1" | "h2" | "h3" | "h4" | "h5" | "h6" | "p" | "li" | "blockquote" | "pre" | "table" | "img") {
            i = after;
            continue;
        }
        if name == "img" {
            if let Some(l) = list.take() {
                flat.push(l);
            }
            let alt = attr_value(attrs, "alt").unwrap_or_default();
            let src = attr_value(attrs, "src").unwrap_or_default();
            let mut n = Node::new("figure", alt);
            n.attrs = json!({"src": src});
            flat.push(n);
            i = after;
            continue;
        }
        let close = format!("</{name}");
        let pos = match lower[after..].find(&close) {
            Some(p) => after + p,
            None => {
                i = after;
                continue;
            }
        };
        let end = match lower[pos..].find('>') {
            Some(p) => pos + p + 1,
            None => lower.len(),
        };
        let inner = &html[after..pos];
        match name.as_str() {
            "h1" | "h2" | "h3" | "h4" | "h5" | "h6" => {
                if let Some(l) = list.take() {
                    flat.push(l);
                }
                let level = name[1..].parse::<usize>().unwrap_or(2);
                let mut n = Node::new("heading", strip_html(inner));
                n.attrs = json!({"level": level});
                flat.push(n);
            }
            "p" => {
                if let Some(l) = list.take() {
                    flat.push(l);
                }
                flat.push(Node::new("paragraph", strip_html(inner)));
            }
            "li" => {
                let mut item = Node::new("list_item", strip_html(inner));
                item.attrs = json!({"ordered": false});
                let l = list.get_or_insert_with(|| {
                    let mut n = Node::new("list", "");
                    n.attrs = json!({"ordered": false});
                    n
                });
                l.children.push(item);
            }
            "blockquote" => {
                if let Some(l) = list.take() {
                    flat.push(l);
                }
                flat.push(Node::new("quote", strip_html(inner)));
            }
            "pre" => {
                if let Some(l) = list.take() {
                    flat.push(l);
                }
                flat.push(Node::new("code", html_unescape(inner.trim())));
            }
            "table" => {
                if let Some(l) = list.take() {
                    flat.push(l);
                }
                flat.push(html_table(inner));
            }
            _ => {}
        }
        i = end;
    }
    if let Some(l) = list {
        flat.push(l);
    }
    flat
}

pub(super) fn normalize_href(base: &str, href: &str) -> String {
    let href = href.split('#').next().unwrap_or(href).replace("%20", " ");
    let mut parts: Vec<&str> = base.split('/').filter(|s| !s.is_empty()).collect();
    for seg in href.split('/') {
        match seg {
            "" | "." => {}
            ".." => {
                parts.pop();
            }
            other => parts.push(other),
        }
    }
    parts.join("/")
}
