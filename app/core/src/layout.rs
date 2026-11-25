//! 版式感知接入：适配器提供页/词/框，本模块做阅读顺序、段落、标题、脚注与块级溯源。
//! 不猜未提供的版式信息；每块带 page/bbox，缺失则显式不给。

use crate::error::{CoreError, OpOutcome};
use crate::ops::{opt_str, usage};
use crate::sdir::{assemble_sdir, Node};
use serde_json::{json, Map, Value};

#[derive(Clone)]
struct Word {
    text: String,
    x: f64,
    y: f64,
    w: f64,
    h: f64,
}

#[derive(Clone)]
struct Line {
    words: Vec<Word>,
    x0: f64,
    y0: f64,
    x1: f64,
    y1: f64,
    size: f64,
    col: u8,
}

fn is_cjk(c: char) -> bool {
    matches!(c as u32, 0x2E80..=0x9FFF | 0xAC00..=0xD7AF)
}

fn join_words(words: &[Word]) -> String {
    let mut out = String::new();
    let mut prev: Option<char> = None;
    for w in words {
        let t = w.text.trim();
        if t.is_empty() {
            continue;
        }
        let first = t.chars().next().unwrap_or(' ');
        if let Some(p) = prev {
            if !(is_cjk(p) || is_cjk(first)) {
                out.push(' ');
            }
        }
        out.push_str(t);
        prev = t.chars().last();
    }
    out
}

fn parse_word(v: &Value) -> Option<Word> {
    let text = v.get("text")?.as_str()?.to_string();
    if text.trim().is_empty() {
        return None;
    }
    let x = v.get("x")?.as_f64()?;
    let y = v.get("y")?.as_f64()?;
    let w = v.get("w").and_then(|v| v.as_f64()).unwrap_or(1.0);
    let h = v.get("h").or_else(|| v.get("size")).and_then(|v| v.as_f64()).unwrap_or(10.0);
    Some(Word { text, x, y, w, h })
}

fn build_lines(page: &Value, width: f64) -> Vec<Line> {
    let mut words: Vec<Word> = page
        .get("words")
        .and_then(|v| v.as_array())
        .map(|a| a.iter().filter_map(parse_word).collect())
        .unwrap_or_default();
    let col_of = |x: f64| if x > width * 0.45 { 2u8 } else { 1u8 };
    words.sort_by(|a, b| col_of(a.x).cmp(&col_of(b.x)).then(a.y.partial_cmp(&b.y).unwrap_or(std::cmp::Ordering::Equal)).then(a.x.partial_cmp(&b.x).unwrap_or(std::cmp::Ordering::Equal)));
    let mut lines: Vec<Line> = Vec::new();
    for w in words {
        let tol = (w.h * 0.4).max(2.0);
        let wcol = col_of(w.x);
        if let Some(last) = lines.last_mut() {
            if last.col == wcol && (w.y - last.y0).abs() <= tol {
                last.x0 = last.x0.min(w.x);
                last.x1 = last.x1.max(w.x + w.w);
                last.y1 = last.y1.max(w.y + w.h);
                last.size = last.size.max(w.h);
                last.words.push(w);
                continue;
            }
        }
        lines.push(Line { x0: w.x, y0: w.y, x1: w.x + w.w, y1: w.y + w.h, size: w.h, col: wcol, words: vec![w] });
    }
    for l in lines.iter_mut() {
        l.words.sort_by(|a, b| a.x.partial_cmp(&b.x).unwrap_or(std::cmp::Ordering::Equal));
    }
    lines
}

fn median_size(lines: &[Line]) -> f64 {
    let mut v: Vec<f64> = lines.iter().map(|l| l.size).collect();
    v.sort_by(|a, b| a.partial_cmp(b).unwrap_or(std::cmp::Ordering::Equal));
    if v.is_empty() { 10.0 } else { v[v.len() / 2] }
}

fn heading_level(size: f64, body: f64) -> Option<u64> {
    if size > body * 1.55 { Some(1) } else if size > body * 1.28 { Some(2) } else if size > body * 1.12 { Some(3) } else { None }
}

fn bbox(x0: f64, y0: f64, x1: f64, y1: f64) -> Value {
    json!({
        "x": x0.max(0.0).round() as u64,
        "y": y0.max(0.0).round() as u64,
        "w": (x1 - x0).max(0.0).round() as u64,
        "h": (y1 - y0).max(0.0).round() as u64
    })
}

fn set_page(n: &mut Node, page: u64) {
    if n.page.is_none() {
        n.page = Some(page);
    }
    for c in n.children.iter_mut() {
        set_page(c, page);
    }
}

fn footnote_label(s: &str) -> Option<String> {
    let t = s.trim();
    if !t.starts_with('[') { return None; }
    let end = t.find(']')?;
    Some(t[1..end].to_string())
}

fn line_cells(line: &Line) -> Vec<(String, f64, f64)> {
    let mut cells: Vec<(String, f64, f64)> = Vec::new();
    let mut current: Vec<&Word> = Vec::new();
    let mut x0 = 0.0;
    let mut x1 = 0.0;
    for w in &line.words {
        if current.is_empty() {
            x0 = w.x;
            x1 = w.x + w.w;
            current.push(w);
            continue;
        }
        if w.x - x1 > (line.size * 2.2).max(12.0) {
            let text = join_words(&current.iter().map(|w| (*w).clone()).collect::<Vec<Word>>());
            cells.push((text, x0, x1));
            current.clear();
            x0 = w.x;
        }
        x1 = x1.max(w.x + w.w);
        current.push(w);
    }
    if !current.is_empty() {
        let text = join_words(&current.iter().map(|w| (*w).clone()).collect::<Vec<Word>>());
        cells.push((text, x0, x1));
    }
    cells
}

fn detect_tables(lines: &[Line]) -> std::collections::BTreeMap<usize, (Node, usize)> {
    let mut out = std::collections::BTreeMap::new();
    let mut i = 0usize;
    while i < lines.len() {
        let first = line_cells(&lines[i]);
        if first.len() < 2 || first.len() > 6 || lines[i].size > 24.0 || lines[i].col == 0 {
            i += 1;
            continue;
        }
        let mut j = i + 1;
        while j < lines.len() {
            let c = line_cells(&lines[j]);
            if c.len() != first.len() {
                break;
            }
            let aligned = c.iter().zip(first.iter()).all(|(a, b)| (a.1 - b.1).abs() <= 30.0);
            if !aligned {
                break;
            }
            j += 1;
        }
        if j - i >= 2 {
            let mut table = Node::new("table", "");
            table.attrs = json!({"columns": first.len() as u64, "header": true});
            let mut y0 = f64::MAX;
            let mut y1 = 0.0f64;
            for (ri, line) in lines[i..j].iter().enumerate() {
                let cells = line_cells(line);
                let mut tr = Node::new("table_row", "");
                tr.attrs = json!({"header": ri == 0});
                let mut rx0 = f64::MAX;
                let mut rx1 = 0.0f64;
                for (ci, (text, cx0, cx1)) in cells.iter().enumerate() {
                    let mut cell = Node::new("table_cell", text.clone());
                    cell.attrs = json!({"row": ri as u64, "col": ci as u64});
                    cell.bbox = Some(bbox(*cx0, line.y0, *cx1, line.y1));
                    tr.children.push(cell);
                    rx0 = rx0.min(*cx0);
                    rx1 = rx1.max(*cx1);
                }
                tr.bbox = Some(bbox(rx0, line.y0, rx1, line.y1));
                y0 = y0.min(line.y0);
                y1 = y1.max(line.y1);
                table.children.push(tr);
            }
            table.bbox = Some(bbox(first[0].1, y0, first.last().map(|c| c.2).unwrap_or(0.0), y1));
            out.insert(i, (table, j - i));
            i = j;
        } else {
            i += 1;
        }
    }
    out
}

pub fn import_layout(req: &Value) -> OpOutcome {
    opt_str(req, "created_at")?.filter(|s| !s.is_empty()).ok_or_else(|| usage("layout-import 需要显式 created_at"))?;
    let pages = req.get("pages").and_then(|v| v.as_array()).ok_or_else(|| usage("layout-import 需要 pages:[{number,width,height,words}]"))?;
    if pages.is_empty() {
        return Err(usage("pages 不能为空"));
    }
    let src = req.get("source").and_then(|v| v.as_object()).ok_or_else(|| usage("layout-import 需要 source{name,mime,bytes_sha,size}"))?;
    let name = src.get("name").and_then(|v| v.as_str()).unwrap_or("source.pdf");
    let mime = src.get("mime").and_then(|v| v.as_str()).unwrap_or("application/pdf");
    let bytes_sha = src.get("bytes_sha").and_then(|v| v.as_str()).unwrap_or("");
    if bytes_sha.len() != 64 || !bytes_sha.chars().all(|c| c.is_ascii_hexdigit()) {
        return Err(CoreError::new("NF-SDIR-002").with_message("source.bytes_sha 必须是 64 位十六进制").with_exit(1));
    }
    let size = src.get("size").and_then(|v| v.as_u64()).unwrap_or(0);
    let mut source = Map::new();
    source.insert("id".into(), Value::String("s1".into()));
    source.insert("name".into(), Value::String(name.to_string()));
    source.insert("mime".into(), Value::String(mime.to_string()));
    source.insert("bytes_sha".into(), Value::String(bytes_sha.to_string()));
    source.insert("size".into(), Value::Number(size.into()));
    source.insert("pages".into(), Value::Number((pages.len() as u64).into()));

    let mut flat: Vec<Node> = Vec::new();
    for (pi, page) in pages.iter().enumerate() {
        let num = page.get("number").and_then(|v| v.as_u64()).unwrap_or(pi as u64 + 1);
        let width = page.get("width").and_then(|v| v.as_f64()).unwrap_or(612.0);
        let height = page.get("height").and_then(|v| v.as_f64()).unwrap_or(792.0);
        let mut lines = build_lines(page, width);
        if lines.is_empty() {
            continue;
        }
        let body = median_size(&lines);
        for l in lines.iter_mut() {
            l.col = if l.x0 < width * 0.45 && l.x1 > width * 0.72 { 0 } else if l.x0 < width * 0.45 { 1 } else { 2 };
        }
        lines.sort_by(|a, b| a.col.cmp(&b.col).then(a.y0.partial_cmp(&b.y0).unwrap_or(std::cmp::Ordering::Equal)).then(a.x0.partial_cmp(&b.x0).unwrap_or(std::cmp::Ordering::Equal)));
        let mut current: Option<Node> = None;
        let mut current_key: (u8, u64) = (0, 0);
        let flush = |current: &mut Option<Node>, flat: &mut Vec<Node>| {
            if let Some(n) = current.take() {
                if !n.text.trim().is_empty() {
                    flat.push(n);
                }
            }
        };
        let tables = detect_tables(&lines);
        let mut footnotes: Vec<Node> = Vec::new();
        let mut idx = 0usize;
        while idx < lines.len() {
            if let Some((mut table, skip)) = tables.get(&idx).cloned() {
                flush(&mut current, &mut flat);
                set_page(&mut table, num);
                flat.push(table);
                idx += skip;
                continue;
            }
            let l = &lines[idx];
            idx += 1;
            let text = join_words(&l.words);
            if text.trim().is_empty() {
                continue;
            }
            let is_foot = l.y0 > height * 0.82 && (l.size < body * 0.96 || footnote_label(&text).is_some());
            if is_foot {
                flush(&mut current, &mut flat);
                let mut n = Node::new("footnote", text.trim().to_string());
                n.page = Some(num);
                n.bbox = Some(bbox(l.x0, l.y0, l.x1, l.y1));
                if let Some(label) = footnote_label(&text) {
                    n.attrs = json!({"label": label});
                }
                footnotes.push(n);
                continue;
            }
            if let Some(level) = heading_level(l.size, body).filter(|_| text.chars().count() <= 80) {
                flush(&mut current, &mut flat);
                let mut n = Node::new("heading", text.trim().to_string());
                n.attrs = json!({"level": level});
                n.page = Some(num);
                n.bbox = Some(bbox(l.x0, l.y0, l.x1, l.y1));
                flat.push(n);
                continue;
            }
            let key = (l.col, num);
            let same = current.is_some() && current_key == key;
            let gap = current.as_ref().and_then(|n| n.bbox.as_ref()).and_then(|b| {
                let y = b.get("y").and_then(|v| v.as_f64())?;
                let h = b.get("h").and_then(|v| v.as_f64())?;
                Some(l.y0 - (y + h))
            }).unwrap_or(999.0);
            if same && gap <= l.size * 2.0 {
                if let Some(n) = current.as_mut() {
                    if !n.text.is_empty() {
                        let prev_last = n.text.chars().last().unwrap_or(' ');
                        let first = text.chars().next().unwrap_or(' ');
                        if !(is_cjk(prev_last) || is_cjk(first)) {
                            n.text.push(' ');
                        }
                    }
                    n.text.push_str(text.trim());
                    if let Some(b) = n.bbox.as_ref() {
                        let x = b.get("x").and_then(|v| v.as_f64()).unwrap_or(l.x0);
                        let y = b.get("y").and_then(|v| v.as_f64()).unwrap_or(l.y0);
                        let w = b.get("w").and_then(|v| v.as_f64()).unwrap_or(0.0);
                        let h = b.get("h").and_then(|v| v.as_f64()).unwrap_or(0.0);
                        n.bbox = Some(bbox(x.min(l.x0), y.min(l.y0), (x + w).max(l.x1), (y + h).max(l.y1)));
                    }
                }
            } else {
                flush(&mut current, &mut flat);
                let mut n = Node::new("paragraph", text.trim().to_string());
                n.page = Some(num);
                n.bbox = Some(bbox(l.x0, l.y0, l.x1, l.y1));
                current = Some(n);
                current_key = key;
            }
        }
        flush(&mut current, &mut flat);
        flat.extend(footnotes);
    }
    if flat.is_empty() {
        return Err(CoreError::new("NF-SDIR-003").with_message("版式输入没有可读词/行").with_exit(3));
    }
    let source_value = Value::Object(source);
    let sdir = assemble_sdir(req, flat, source_value, "pdf", "pdf-layout/1", None, "未命名 PDF")?;
    Ok((0, sdir))
}

pub fn layout_import_op(req: &Value) -> OpOutcome { import_layout(req) }
