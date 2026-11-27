//! Markdown 解析与块树装配（parse_markdown / build_tree / walk 等）。
//!
//! 自 `sdir.rs` 按职责拆出：实现逐字搬运，逻辑与文案未改；公共 API 由父模块 `pub use` 保持原路径。

use super::Node;
use crate::canonical::digest_value;
use crate::error::CoreError;
use serde_json::{json, Map, Value};
use std::collections::BTreeMap;

pub(super) fn is_hash64(s: &str) -> bool {
    s.len() == 64 && s.chars().all(|c| c.is_ascii_hexdigit() && !c.is_ascii_uppercase())
}

pub(super) fn str_field<'a>(v: &'a Value, key: &str) -> &'a str {
    v.get(key).and_then(|x| x.as_str()).unwrap_or("")
}

pub(super) fn slug(text: &str) -> String {
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

pub(super) fn fence_open(line: &str) -> Option<(char, usize, String)> {
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

pub(super) fn fence_close(line: &str, ch: char, n: usize) -> bool {
    let t = line.trim();
    let count = t.chars().take_while(|c| *c == ch).count();
    count >= n && t.chars().skip(n).all(|c| c == ch)
}

pub(super) fn heading(line: &str) -> Option<(usize, String)> {
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

pub(super) fn table_separator(line: &str) -> bool {
    let t = line.trim();
    t.contains('|') && t.contains('-') && t.chars().all(|c| matches!(c, '|' | '-' | ':' | ' '))
}

pub(super) fn split_row(line: &str) -> Vec<String> {
    let t = line.trim().trim_matches('|');
    t.split('|')
        .map(|c| c.trim().replace("\\|", "|"))
        .collect()
}

pub(super) fn list_item(line: &str) -> Option<(bool, String)> {
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
pub(super) fn parse_markdown(md: &str) -> Vec<Node> {
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

pub(super) fn assign_ids(nodes: &mut [Node], counter: &mut u64) {
    for n in nodes.iter_mut() {
        *counter += 1;
        n.id = format!("b{:04}", counter);
        assign_ids(&mut n.children, counter);
    }
}

pub(super) fn finalize(node: &mut Node) -> Result<Value, CoreError> {
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

pub(super) struct Arena {
    nodes: Vec<Node>,
    parent: Vec<usize>,
    level: Vec<usize>,
}

pub(super) fn build_tree(mut flat: Vec<Node>) -> (Node, Vec<(String, String)>) {
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

pub(super) fn find_block<'a>(v: &'a Value, id: &str) -> Option<&'a Value> {
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

pub(super) fn walk<'a>(v: &'a Value, parent: Option<&'a Value>, out: &mut Vec<(&'a Value, Option<&'a Value>, usize)>, depth: usize) {
    out.push((v, parent, depth));
    for c in v.get("children").and_then(|x| x.as_array()).into_iter().flatten() {
        walk(c, Some(v), out, depth + 1);
    }
}
