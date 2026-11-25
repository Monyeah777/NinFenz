//! nf-sdir/1：语义文档 IR（导入/校验/差异/三方合并）。
//! 设计约束：块有稳定 id + 内容 hash；关系闭包；可访问性显式 missing；块级溯源。
//! 本模块不猜版式：源适配器必须显式给出 transform 与来源摘要。

use crate::canonical::{digest_value, sha256_hex};
use crate::error::{CoreError, OpOutcome};
use crate::fsutil;
use crate::zipsec;
use regex::Regex;
use std::sync::OnceLock;
use crate::ops::{opt_str, req_value, usage};
use crate::report::Report;
use crate::schema::validate;
use serde_json::{json, Map, Value};
use std::collections::{BTreeMap, BTreeSet};

pub const SDIR_SCHEMA: &str = "nf-sdir/1";
pub const IMPORT_TRANSFORM: &str = "sdir-import/1";

fn is_hash64(s: &str) -> bool {
    s.len() == 64 && s.chars().all(|c| c.is_ascii_hexdigit() && !c.is_ascii_uppercase())
}

fn str_field<'a>(v: &'a Value, key: &str) -> &'a str {
    v.get(key).and_then(|x| x.as_str()).unwrap_or("")
}

#[derive(Clone, Debug)]
pub struct Node {
    pub id: String,
    pub btype: String,
    pub text: String,
    pub attrs: Value,
    pub children: Vec<Node>,
    pub page: Option<u64>,
    pub bbox: Option<Value>,
}

impl Node {
    pub(crate) fn new(btype: &str, text: impl Into<String>) -> Self {
        Node {
            id: String::new(),
            btype: btype.to_string(),
            text: text.into(),
            attrs: json!({}),
            children: Vec::new(),
            page: None,
            bbox: None,
        }
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
    if s.is_empty() {
        "section".to_string()
    } else {
        s
    }
}

fn fence_open(line: &str) -> Option<(char, usize, String)> {
    let t = line.trim_start();
    let ch = t.chars().next()?;
    if ch != '\u{60}' && ch != '~' {
        return None;
    }
    let n = t.chars().take_while(|c| *c == ch).count();
    if n < 3 {
        return None;
    }
    let info = t[n..].trim();
    Some((ch, n, info.split_whitespace().next().unwrap_or("").to_string()))
}

fn fence_close(line: &str, ch: char, n: usize) -> bool {
    let t = line.trim();
    let count = t.chars().take_while(|c| *c == ch).count();
    count >= n && t.chars().skip(n).all(|c| c == ch)
}

fn heading(line: &str) -> Option<(usize, String)> {
    let t = line.trim_end();
    let count = t.chars().take_while(|c| *c == '#').count();
    if !(1..=6).contains(&count) {
        return None;
    }
    let rest = &t[count..];
    if rest.is_empty() {
        return Some((count, String::new()));
    }
    if !rest.starts_with(' ') {
        return None;
    }
    Some((count, rest.trim().to_string()))
}

fn table_separator(line: &str) -> bool {
    let t = line.trim();
    t.contains('|') && t.contains('-') && t.chars().all(|c| matches!(c, '|' | '-' | ':' | ' '))
}

fn split_row(line: &str) -> Vec<String> {
    let t = line.trim().trim_matches('|');
    t.split('|')
        .map(|c| c.trim().replace("\\|", "|"))
        .collect()
}

fn list_item(line: &str) -> Option<(bool, String)> {
    let t = line.trim_start();
    if let Some(rest) = t.strip_prefix("- ").or_else(|| t.strip_prefix("* ")).or_else(|| t.strip_prefix("+ ")) {
        return Some((false, rest.trim().to_string()));
    }
    let mut digits = 0usize;
    for c in t.chars() {
        if c.is_ascii_digit() {
            digits += 1;
        } else {
            break;
        }
    }
    if digits == 0 {
        return None;
    }
    let rest = &t[digits..];
    if let Some(item) = rest.strip_prefix(". ").or_else(|| rest.strip_prefix(") ")) {
        return Some((true, item.trim().to_string()));
    }
    None
}

/// 解析 Markdown 为扁平节点（标题节点在层级装配时获得 children）。
fn parse_markdown(md: &str) -> Vec<Node> {
    let normalized = md.replace("\r\n", "\n").replace('\r', "\n");
    let lines: Vec<&str> = normalized.split('\n').collect();
    let mut flat: Vec<Node> = Vec::new();
    let mut i = 0usize;
    while i < lines.len() {
        let line = lines[i];
        if line.trim().is_empty() {
            i += 1;
            continue;
        }
        if let Some((ch, n, lang)) = fence_open(line) {
            let start = i + 1;
            let mut buf: Vec<&str> = Vec::new();
            i += 1;
            while i < lines.len() && !fence_close(lines[i], ch, n) {
                buf.push(lines[i]);
                i += 1;
            }
            if i < lines.len() {
                i += 1;
            }
            let mut node = Node::new("code", buf.join("\n"));
            node.attrs = json!({"lang": lang, "fence_lines": (i - start) as u64});
            flat.push(node);
            continue;
        }
        if let Some((level, text)) = heading(line) {
            let mut node = Node::new("heading", text);
            node.attrs = json!({"level": level as u64});
            flat.push(node);
            i += 1;
            continue;
        }
        if line.contains('|') && i + 1 < lines.len() && table_separator(lines[i + 1]) {
            let header = split_row(line);
            let mut rows: Vec<Vec<String>> = vec![header.clone()];
            i += 2;
            while i < lines.len() && lines[i].contains('|') && !lines[i].trim().is_empty() {
                rows.push(split_row(lines[i]));
                i += 1;
            }
            let cols = header.len();
            let mut table = Node::new("table", "");
            table.attrs = json!({"columns": cols as u64, "header": true});
            for (ri, row) in rows.iter().enumerate() {
                let mut tr = Node::new("table_row", "");
                tr.attrs = json!({"header": ri == 0});
                for ci in 0..cols {
                    let text = row.get(ci).cloned().unwrap_or_default();
                    let mut cell = Node::new("table_cell", text);
                    cell.attrs = json!({"row": ri as u64, "col": ci as u64});
                    tr.children.push(cell);
                }
                table.children.push(tr);
            }
            flat.push(table);
            continue;
        }
        if let Some((ordered, _)) = list_item(line) {
            let mut list = Node::new("list", "");
            list.attrs = json!({"ordered": ordered});
            while i < lines.len() {
                match list_item(lines[i]) {
                    Some((o, text)) if o == ordered => {
                        let mut item = Node::new("list_item", text);
                        item.attrs = json!({"ordered": ordered});
                        list.children.push(item);
                        i += 1;
                    }
                    _ => break,
                }
            }
            flat.push(list);
            continue;
        }
        if let Some(rest) = line.trim_start().strip_prefix("> ") {
            let mut buf = vec![rest.trim().to_string()];
            i += 1;
            while i < lines.len() {
                if let Some(next) = lines[i].trim_start().strip_prefix("> ") {
                    buf.push(next.trim().to_string());
                    i += 1;
                } else {
                    break;
                }
            }
            flat.push(Node::new("quote", buf.join("\n")));
            continue;
        }
        let trimmed = line.trim();
        if trimmed.starts_with("![") && trimmed.contains("](") && trimmed.ends_with(')') {
            let close = trimmed.find("](").unwrap_or(trimmed.len());
            let alt = &trimmed[2..close];
            let src = &trimmed[close + 2..trimmed.len() - 1];
            let mut node = Node::new("figure", alt);
            node.attrs = json!({"src": src});
            flat.push(node);
            i += 1;
            continue;
        }
        if trimmed.starts_with("[^") && trimmed.contains("]: ") {
            let close = trimmed.find("]: ").unwrap_or(trimmed.len());
            let label = &trimmed[2..close];
            let text = &trimmed[close + 3..];
            let mut node = Node::new("footnote", text);
            node.attrs = json!({"label": label});
            flat.push(node);
            i += 1;
            continue;
        }
        // 段落：吸收到空行/结构行之前
        let mut buf = vec![line.trim().to_string()];
        i += 1;
        while i < lines.len() {
            let l = lines[i];
            if l.trim().is_empty()
                || heading(l).is_some()
                || fence_open(l).is_some()
                || list_item(l).is_some()
                || l.trim_start().starts_with("> ")
                || (l.contains('|') && i + 1 < lines.len() && table_separator(lines[i + 1]))
            {
                break;
            }
            buf.push(l.trim().to_string());
            i += 1;
        }
        flat.push(Node::new("paragraph", buf.join("\n")));
    }
    flat
}

fn assign_ids(nodes: &mut [Node], counter: &mut u64) {
    for n in nodes.iter_mut() {
        *counter += 1;
        n.id = format!("b{:04}", counter);
        assign_ids(&mut n.children, counter);
    }
}

fn finalize(node: &mut Node) -> Result<Value, CoreError> {
    let mut children: Vec<Value> = Vec::new();
    for c in node.children.iter_mut() {
        children.push(finalize(c)?);
    }
    let child_hashes: Vec<Value> = children
        .iter()
        .map(|c| Value::String(str_field(c, "hash").to_string()))
        .collect();
    let mut m = Map::new();
    m.insert("type".into(), Value::String(node.btype.clone()));
    m.insert("text".into(), Value::String(node.text.clone()));
    m.insert("attrs".into(), node.attrs.clone());
    m.insert("children".into(), Value::Array(child_hashes));
    if let Some(p) = node.page {
        m.insert("page".into(), Value::Number(p.into()));
    }
    if let Some(b) = &node.bbox {
        m.insert("bbox".into(), b.clone());
    }
    let hash = digest_value(&Value::Object(m))?;
    let mut out = Map::new();
    out.insert("id".into(), Value::String(node.id.clone()));
    out.insert("type".into(), Value::String(node.btype.clone()));
    out.insert("text".into(), Value::String(node.text.clone()));
    out.insert("attrs".into(), node.attrs.clone());
    if !children.is_empty() {
        out.insert("children".into(), Value::Array(children));
    }
    if let Some(p) = node.page {
        out.insert("page".into(), Value::Number(p.into()));
    }
    if let Some(b) = &node.bbox {
        out.insert("bbox".into(), b.clone());
    }
    out.insert("hash".into(), Value::String(hash));
    Ok(Value::Object(out))
}

struct Arena {
    nodes: Vec<Node>,
    parent: Vec<usize>,
    level: Vec<usize>,
}

fn build_tree(mut flat: Vec<Node>) -> (Node, Vec<(String, String)>) {
    let mut arena = Arena { nodes: Vec::new(), parent: Vec::new(), level: Vec::new() };
    let root = Node::new("document", "");
    arena.nodes.push(root);
    arena.parent.push(usize::MAX);
    arena.level.push(0);
    let mut stack: Vec<usize> = vec![0];
    let mut heading_anchors: Vec<(String, String)> = Vec::new();
    for n in flat.drain(..) {
        let is_heading = n.btype == "heading";
        let lvl = n.attrs.get("level").and_then(|v| v.as_u64()).unwrap_or(0) as usize;
        if is_heading {
            while stack.len() > 1 {
                let top = *stack.last().unwrap();
                if arena.level[top] >= lvl {
                    stack.pop();
                } else {
                    break;
                }
            }
        }
        let parent = *stack.last().unwrap();
        let idx = arena.nodes.len();
        if is_heading {
            heading_anchors.push((n.id.clone(), slug(&n.text)));
        }
        arena.nodes.push(n);
        arena.parent.push(parent);
        arena.level.push(if is_heading { lvl } else { arena.level[parent] });
        if is_heading {
            stack.push(idx);
        }
    }
    // 把 arena 变成树：从后往前挂到 parent
    let mut children: BTreeMap<usize, Vec<usize>> = BTreeMap::new();
    for i in 1..arena.nodes.len() {
        children.entry(arena.parent[i]).or_default().push(i);
    }
    fn take(arena: &Arena, children: &BTreeMap<usize, Vec<usize>>, idx: usize) -> Node {
        let mut n = arena.nodes[idx].clone();
        if let Some(cs) = children.get(&idx) {
            n.children = cs.iter().map(|c| take(arena, children, *c)).collect();
        }
        n
    }
    let mut root_node = arena.nodes[0].clone();
    root_node.children = children
        .get(&0)
        .map(|cs| cs.iter().map(|c| take(&arena, &children, *c)).collect())
        .unwrap_or_default();
    (root_node, heading_anchors)
}

fn find_block<'a>(v: &'a Value, id: &str) -> Option<&'a Value> {
    if v.get("id").and_then(|x| x.as_str()) == Some(id) {
        return Some(v);
    }
    for c in v.get("children").and_then(|x| x.as_array()).into_iter().flatten() {
        if let Some(f) = find_block(c, id) {
            return Some(f);
        }
    }
    None
}

fn walk<'a>(v: &'a Value, parent: Option<&'a Value>, out: &mut Vec<(&'a Value, Option<&'a Value>, usize)>, depth: usize) {
    out.push((v, parent, depth));
    for c in v.get("children").and_then(|x| x.as_array()).into_iter().flatten() {
        walk(c, Some(v), out, depth + 1);
    }
}

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

fn build_relations(root: &Value) -> (Vec<Value>, BTreeMap<String, String>) {
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

fn a11y_for(root: &Value, lang: &str) -> Value {
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

fn provenance_for(root: &Value, source_id: &str, bytes_sha: &str, parser: &str, page: Option<u64>) -> Value {
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

fn fidelity_for(root: &Value, source_format: &str, source_pages: u64, default_page: Option<u64>) -> Value {
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

fn xml_unescape(s: &str) -> String {
    s.replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&quot;", "\"")
        .replace("&apos;", "'")
        .replace("&amp;", "&")
}

fn docx_text(fragment: &str) -> String {
    static T: OnceLock<Regex> = OnceLock::new();
    let re = T.get_or_init(|| Regex::new(r"(?s)<w:t(?:\s[^>]*)?>(.*?)</w:t>").expect("w:t regex"));
    let mut out = String::new();
    for c in re.captures_iter(fragment) {
        out.push_str(&xml_unescape(&c[1]));
    }
    out
}

fn docx_para_block(p: &str) -> Option<Node> {
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

fn docx_table_block(tbl: &str) -> Node {
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

fn parse_docx(document_xml: &str) -> Vec<Node> {
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

fn attr_value(tag: &str, name: &str) -> Option<String> {
    let pat = format!(r#"(?i)\b{}\s*=\s*"([^"]*)""#, regex::escape(name));
    Regex::new(&pat).ok()?.captures(tag).and_then(|c| c.get(1)).map(|m| m.as_str().to_string())
}

fn html_unescape(s: &str) -> String {
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

fn strip_html(s: &str) -> String {
    static TAGS: OnceLock<Regex> = OnceLock::new();
    let re = TAGS.get_or_init(|| Regex::new(r"(?s)<[^>]+>").expect("tags"));
    html_unescape(&re.replace_all(s, " ")).split_whitespace().collect::<Vec<_>>().join(" ")
}

fn html_table(tbl: &str) -> Node {
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

fn parse_html_blocks(html: &str) -> Vec<Node> {
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

fn normalize_href(base: &str, href: &str) -> String {
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

fn flat_map(root: &Value) -> BTreeMap<String, Value> {
    let mut flat: Vec<(&Value, Option<&Value>, usize)> = Vec::new();
    walk(root, None, &mut flat, 0);
    let mut m = BTreeMap::new();
    for (b, _, _) in flat {
        m.insert(str_field(b, "id").to_string(), b.clone());
    }
    m
}

fn diff_value(from: &Value, to: &Value) -> Value {
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
struct Flat {
    block: Value,
    parent: String,
}

fn flatten_with_parent(root: &Value) -> BTreeMap<String, Flat> {
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

fn intrinsic(v: &Value) -> String {
    let m = json!({
        "type": v.get("type").cloned().unwrap_or(Value::Null),
        "text": v.get("text").cloned().unwrap_or(Value::Null),
        "attrs": v.get("attrs").cloned().unwrap_or_else(|| json!({}))
    });
    digest_value(&m).unwrap_or_default()
}

fn merge_maps(base: &BTreeMap<String, Flat>, ours: &BTreeMap<String, Flat>, theirs: &BTreeMap<String, Flat>) -> (BTreeMap<String, Flat>, Vec<Value>) {
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

fn rebuild(meta: &Value, sources: &Value, blocks: &BTreeMap<String, Flat>, relations: &Value, a11y: &Value, prov: &Value) -> Result<Value, CoreError> {
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

fn merge_array_by_key(a: &Value, b: &Value, key: &str) -> Value {
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

fn filter_array(v: Value, key: &str, ids: &BTreeSet<String>) -> Value {
    Value::Array(
        v.as_array()
            .cloned()
            .unwrap_or_default()
            .into_iter()
            .filter(|item| item.get(key).and_then(|x| x.as_str()).map(|s| ids.contains(s)).unwrap_or(false))
            .collect(),
    )
}

fn filter_relations(v: Value, ids: &BTreeSet<String>) -> Value {
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

fn merge_relations(a: &Value, b: &Value) -> Value {
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
