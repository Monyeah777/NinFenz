//! Markdown 前导块与列表块的**唯一解析出处** —— 对应真源 `core/md_blocks.py` 与
//! `core/library_entries.py::parse_frontmatter`。
//!
//! 这两件是真源里被 `handover` / `postmortem` / `decisions` / `patterns` / `audit` 共用的叶子逻辑；
//! 真源自己也曾因「同一件事两份拷贝」而收口（`md_blocks.py` 的开头注释记着这段）。
//! 本线同样只留一份。

use crate::pyjson::Json;

/// `core.library_entries.parse_frontmatter` 的等价物 → `(frontmatter, 正文)`。
///
/// **注意它不是 YAML**：真源是自研极简解析器，规则与 `miniyaml` 不同——
/// ① 分隔点取**第一个冒号**（不要求后跟空格）；② 缩进行归给上一个键，`- ` 前缀被剥掉；
/// ③ 标量两侧的引号用 `strip("'\"")` 去掉。抄成 YAML 口径会在含冒号的键上分叉。
pub fn parse_frontmatter(text: &str) -> (Json, String) {
    if !text.starts_with("---") {
        return (Json::Object(Vec::new()), text.to_string());
    }
    let lines: Vec<&str> = text.lines().collect();
    let Some(end) = frontmatter_end(&lines) else {
        return (Json::Object(Vec::new()), text.to_string());
    };
    let body = lines[end + 1..].join("\n");
    (Json::Object(frontmatter_pairs(&lines, end)), body)
}

/// 前导块结束分隔行的行号（从第 2 行起找）。
fn frontmatter_end(lines: &[&str]) -> Option<usize> {
    for (i, ln) in lines.iter().enumerate().skip(1) {
        if ln.trim() == "---" {
            return Some(i);
        }
    }
    None
}

/// 前导块键值对：缩进续行归上一个键（`- ` 前缀剥掉），其余按首个冒号切键值。
fn frontmatter_pairs(lines: &[&str], end: usize) -> Vec<(String, Json)> {
    let mut pairs: Vec<(String, Json)> = Vec::new();
    let mut key: Option<String> = None;
    for ln in &lines[1..end] {
        if ln.trim().is_empty() || ln.trim().starts_with('#') {
            continue;
        }
        if (ln.starts_with("  ") || ln.starts_with('\t')) && key.is_some() {
            let k = key.clone().unwrap_or_default();
            fm_indented_item(&mut pairs, &k, ln);
            continue;
        }
        fm_key_value(&mut pairs, &mut key, ln);
    }
    pairs
}

/// 缩进续行：并入上一个键的列表（非列表时空值 → []，否则 → [旧值]）。
fn fm_indented_item(pairs: &mut Vec<(String, Json)>, k: &str, ln: &str) {
    let mut item = ln.trim().to_string();
    if let Some(rest) = item.strip_prefix("- ") {
        item = rest.trim().to_string();
    }
    let item = item.trim_matches(|c| c == '\'' || c == '"').to_string();
    let cur = pairs.iter().position(|(n, _)| *n == k);
    match cur {
        Some(idx) => match &mut pairs[idx].1 {
            Json::Array(a) => a.push(Json::Str(item)),
            other => {
                let prev = other.clone();
                let mut a = Vec::new();
                if !matches!(prev, Json::Null) {
                    a.push(prev);
                }
                a.push(Json::Str(item));
                pairs[idx].1 = Json::Array(a);
            }
        },
        None => {
            pairs.push((k.to_string(), Json::Array(vec![Json::Str(item)])));
        }
    }
}

/// 单行键值：首个冒号切分；值支持 `[a, b]` 与引号剥除。
fn fm_key_value(pairs: &mut Vec<(String, Json)>, key: &mut Option<String>, ln: &str) {
    if let Some(pos) = ln.find(':') {
        let k = ln[..pos].trim().to_string();
        let v = ln[pos + 1..].trim().to_string();
        *key = Some(k.clone());
        let value = fm_inline_list(&v);
        match pairs.iter_mut().find(|(n, _)| *n == k) {
            Some(slot) => slot.1 = value,
            None => pairs.push((k, value)),
        }
    }
}

/// 行内值：空串 → []；`[a, b]` → 数组；其余按引号剥除的标量。
fn fm_inline_list(v: &str) -> Json {
    if v.is_empty() {
        Json::Array(Vec::new())
    } else if v.starts_with('[') && v.ends_with(']') {
        let inner = &v[1..v.len() - 1];
        Json::Array(
            inner
                .split(',')
                .map(|x| x.trim())
                .filter(|x| !x.is_empty())
                .map(|x| Json::Str(x.trim_matches(|c| c == '\'' || c == '"').to_string()))
                .collect(),
        )
    } else {
        Json::Str(v.trim_matches(|c| c == '\'' || c == '"').to_string())
    }
}

/// 真源 `md_blocks.bullet_blocks`：一条 bullet 含其后的缩进续行。
pub fn bullet_blocks(text: &str) -> Vec<String> {
    let mut blocks: Vec<String> = Vec::new();
    let mut cur: Vec<String> = Vec::new();
    let is_bullet = |l: &str| {
        let t = l.trim_start();
        (t.starts_with("- ") || t.starts_with("* ")) && t.len() > 2
    };
    for line in text.lines() {
        if is_bullet(line) {
            if !cur.is_empty() {
                blocks.push(cur.join("\n").trim().to_string());
            }
            cur = vec![line.to_string()];
        } else if !cur.is_empty() && !line.trim().is_empty() {
            cur.push(line.to_string());
        } else if !cur.is_empty() {
            blocks.push(cur.join("\n").trim().to_string());
            cur.clear();
        }
    }
    if !cur.is_empty() {
        blocks.push(cur.join("\n").trim().to_string());
    }
    blocks
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn frontmatter_splits_on_first_colon_not_colon_space() {
        // 真源口径：`key:value`、`key: 通用:M10` 都在**第一个冒号**处切
        let (fm, _) = parse_frontmatter("---\na:b\nc: 通用:M10\n---\nbody\n");
        assert_eq!(crate::pyval::get(&fm, "a"), Some(&Json::Str("b".into())));
        assert_eq!(
            crate::pyval::get(&fm, "c"),
            Some(&Json::Str("通用:M10".into()))
        );
    }

    #[test]
    fn frontmatter_list_forms_and_quote_stripping() {
        let (fm, body) =
            parse_frontmatter("---\nrefs: [a, b]\nnotes:\n  - one\n  - two\nq: 'x'\n---\nB\n");
        assert_eq!(
            crate::pyval::get(&fm, "refs"),
            Some(&Json::Array(vec![
                Json::Str("a".into()),
                Json::Str("b".into())
            ]))
        );
        assert_eq!(
            crate::pyval::get(&fm, "notes"),
            Some(&Json::Array(vec![
                Json::Str("one".into()),
                Json::Str("two".into())
            ]))
        );
        assert_eq!(crate::pyval::get(&fm, "q"), Some(&Json::Str("x".into())));
        assert_eq!(body, "B");
    }

    #[test]
    fn no_frontmatter_returns_original_text() {
        let (fm, body) = parse_frontmatter("plain text\n");
        assert!(matches!(fm, Json::Object(ref p) if p.is_empty()));
        assert_eq!(body, "plain text\n");
    }

    #[test]
    fn unterminated_frontmatter_is_not_frontmatter() {
        let (fm, body) = parse_frontmatter("---\na: 1\n");
        assert!(matches!(fm, Json::Object(ref p) if p.is_empty()));
        assert_eq!(body, "---\na: 1\n");
    }

    #[test]
    fn bullet_blocks_join_indented_continuations() {
        let got = bullet_blocks("- a\n  cont\n- b\n\n- c\n");
        assert_eq!(
            got,
            vec![
                "- a\n  cont".to_string(),
                "- b".to_string(),
                "- c".to_string()
            ]
        );
    }
}
