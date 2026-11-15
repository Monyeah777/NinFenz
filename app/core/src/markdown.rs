//! Markdown 结构抽取（标题/段落/代码块/表格），确定性、无外依赖。
//! 首版适配器口径：ATX 标题（# 1-6）、围栏（三个反引号或三个波浪号）、GFM 表格（竖线分隔 + 分隔行）。

use crate::error::CoreError;
use crate::limits::limits;
use serde_json::{json, Value};

#[derive(Clone, Debug, Default)]
pub struct MarkdownStructure {
    pub headings: Vec<Value>,
    pub paragraphs: u64,
    pub code_blocks: Vec<Value>,
    pub tables: Vec<Value>,
}

fn imp_limit(message: impl Into<String>) -> CoreError {
    CoreError::new("NF-IMP-003").with_message(message.into()).with_exit(3)
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
    let lang = info.split_whitespace().next().unwrap_or("").to_string();
    Some((ch, n, lang))
}

fn is_fence_close(line: &str, ch: char, n: usize) -> bool {
    let t = line.trim();
    let count = t.chars().take_while(|c| *c == ch).count();
    count >= n && t.chars().skip(n).all(|c| c == ch)
}

fn heading_level(line: &str) -> Option<(usize, String)> {
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

fn is_table_separator(line: &str) -> bool {
    let t = line.trim();
    if !t.contains('-') || !t.contains('|') {
        return false;
    }
    t.chars().all(|c| matches!(c, '|' | '-' | ':' | ' '))
        && t.chars().filter(|c| *c == '-').count() >= 1
}

fn table_columns(line: &str) -> u64 {
    let t = line.trim().trim_matches('|');
    t.split('|').count() as u64
}

pub fn extract(text: &str) -> Result<MarkdownStructure, CoreError> {
    let l = limits();
    let lines: Vec<&str> = text.split('\n').collect();
    let mut st = MarkdownStructure::default();
    let mut i = 0usize;
    let mut in_para = false;
    while i < lines.len() {
        let line = lines[i];
        let line_no = i + 1;
        if let Some((ch, n, lang)) = fence_open(line) {
            if in_para {
                st.paragraphs += 1;
                in_para = false;
            }
            i += 1;
            let mut content_lines: u64 = 0;
            while i < lines.len() {
                if is_fence_close(lines[i], ch, n) {
                    break;
                }
                content_lines += 1;
                if content_lines > l.markdown_max_fence_lines {
                    return Err(imp_limit(format!(
                        "代码块行数超过上限 {}（行 {line_no}）",
                        l.markdown_max_fence_lines
                    )));
                }
                i += 1;
            }
            if i < lines.len() {
                i += 1;
            }
            st.code_blocks.push(json!({
                "lang": lang,
                "lines": content_lines,
            }));
            if st.code_blocks.len() as u64 > l.import_max_code_blocks {
                return Err(imp_limit(format!(
                    "代码块数超过上限 {}",
                    l.import_max_code_blocks
                )));
            }
            continue;
        }
        if let Some((level, title)) = heading_level(line) {
            if in_para {
                st.paragraphs += 1;
                in_para = false;
            }
            st.headings.push(json!({
                "line": line_no,
                "level": level,
                "text": title,
            }));
            if st.headings.len() as u64 > l.import_max_headings {
                return Err(imp_limit(format!(
                    "标题数超过上限 {}",
                    l.import_max_headings
                )));
            }
            i += 1;
            continue;
        }
        if line.contains('|') && i + 1 < lines.len() && is_table_separator(lines[i + 1]) {
            if in_para {
                st.paragraphs += 1;
                in_para = false;
            }
            let cols = table_columns(line);
            let mut rows: u64 = 0;
            i += 2;
            while i < lines.len() && lines[i].contains('|') && !lines[i].trim().is_empty() {
                rows += 1;
                i += 1;
            }
            st.tables.push(json!({"columns": cols, "rows": rows}));
            if st.tables.len() as u64 > l.import_max_tables {
                return Err(imp_limit(format!(
                    "表格数超过上限 {}",
                    l.import_max_tables
                )));
            }
            continue;
        }
        if line.trim().is_empty() {
            if in_para {
                st.paragraphs += 1;
                in_para = false;
            }
        } else {
            in_para = true;
        }
        i += 1;
    }
    if in_para {
        st.paragraphs += 1;
    }
    Ok(st)
}

/// 纯文本适配器：只数段落，不识别标题/代码块/表格。
pub fn plain_structure(text: &str) -> MarkdownStructure {
    let mut paragraphs = 0u64;
    let mut in_para = false;
    for line in text.split('\n') {
        if line.trim().is_empty() {
            if in_para {
                paragraphs += 1;
                in_para = false;
            }
        } else {
            in_para = true;
        }
    }
    if in_para {
        paragraphs += 1;
    }
    MarkdownStructure {
        headings: Vec::new(),
        paragraphs,
        code_blocks: Vec::new(),
        tables: Vec::new(),
    }
}
