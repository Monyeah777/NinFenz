//! 协议件版本史头（rfc-heads）判据。
//!
//! 自 `contracts.rs` 按族拆出：判据实现逐字搬运，逻辑与文案未改；由父模块 glob 引入分派面。

use crate::jsonread;
use crate::pyval::{arr_items, get, obj_is_empty, py_str, str_list};
use std::path::Path;

// ---------------------------------------------------------------- rfc-heads

pub(super) const RFC_INDEX_REL: &str = "protocol/rfc_index.json";
pub(super) const RFC_CATEGORIES: [&str; 4] = [
    "Standards Track",
    "Informational",
    "Experimental",
    "Process",
];
/// 真源头格式用的分隔符与占位符（`—` 是 U+2014，不是 `-`）。
pub(super) const DASHES: [&str; 2] = ["—", "-"];

/// 真源 `_c_rfc_heads`：协议件 RFC 头 + supersede 链。
pub(super) fn rfc_heads(root: &Path) -> (bool, String) {
    let (issues, stats) = rfc_scan(root);
    let ok = issues.is_empty();
    let detail = if ok {
        format!("RFC 件 {} · 链 {}", stats.docs, stats.chains)
    } else {
        issues
            .iter()
            .take(2)
            .cloned()
            .collect::<Vec<_>>()
            .join("; ")
    };
    (ok, detail)
}

#[derive(Default, Clone, Debug)]
pub(super) struct RfcStats {
    docs: usize,
    chains: usize,
}

pub(super) struct RfcHead {
    pub(super) rfc: String,
    pub(super) cat: String,
    pub(super) date: String,
    pub(super) status: String,
    pub(super) supby: String,
    pub(super) last_updated: String,
}

pub(super) fn rfc_head_re() -> &'static regex::Regex {
    static RE: std::sync::OnceLock<regex::Regex> = std::sync::OnceLock::new();
    RE.get_or_init(|| {
        regex::Regex::new(concat!(
            r"\*\*RFC\*\*:\s*(?P<rfc>NF-\d{4})\s*·\s*\*\*Category\*\*:\s*(?P<cat>[^·]+?)\s*·\s*",
            r"\*\*Date\*\*:\s*(?P<date>[\d-]+)\s*·\s*\*\*Status\*\*:\s*(?P<status>[^·]+?)\s*·\s*",
            r"\*\*Supersedes\*\*:\s*(?P<sup>[^·]+?)\s*·\s*\*\*Superseded by\*\*:\s*(?P<supby>[^·\n]+)"
        ))
        .expect("RFC 头正则固定合法")
    })
}

pub(super) fn rfc_updated_re() -> &'static regex::Regex {
    static RE: std::sync::OnceLock<regex::Regex> = std::sync::OnceLock::new();
    RE.get_or_init(|| {
        regex::Regex::new(r">\s*最后更新：\s*([\d-]+)").expect("「最后更新」正则固定合法")
    })
}

/// 真源 `parse_head`：只取文档头 8 行内的 RFC 头。
pub(super) fn parse_head(text: &str) -> Option<RfcHead> {
    let head = text.lines().take(8).collect::<Vec<_>>().join("\n");
    let caps = rfc_head_re().captures(&head)?;
    let g = |n: &str| {
        caps.name(n)
            .map(|m| m.as_str().trim().to_string())
            .unwrap_or_default()
    };
    Some(RfcHead {
        rfc: g("rfc"),
        cat: g("cat"),
        date: g("date"),
        status: g("status"),
        supby: g("supby"),
        last_updated: rfc_updated_re()
            .captures(&head)
            .map(|c| c[1].to_string())
            .unwrap_or_default(),
    })
}

/// 真源 `rfc.scan` 的等价物。
///
/// **未计算 `stats["statuses"]`**：真源算了它，但**全仓无消费者**，且对本契约的
/// `(ok, detail)` 与内容摘要均无影响。若日后他面要用，需在此补回。
pub(super) fn rfc_scan(root: &Path) -> (Vec<String>, RfcStats) {
    let mut issues: Vec<String> = Vec::new();
    let mut stats = RfcStats::default();
    let missing = || {
        format!(
            "缺 RFC 索引 {}（修复指引：见 protocol/rfc_index.json）",
            RFC_INDEX_REL
        )
    };

    if !root.join(RFC_INDEX_REL).is_file() {
        return (vec![missing()], stats);
    }
    let Some(idx) = jsonread::read_file(root, RFC_INDEX_REL) else {
        return (vec![missing()], stats);
    };
    if obj_is_empty(&idx) {
        return (vec![missing()], stats);
    }

    let mut vocab = str_list(get(&idx, "status_vocabulary"));
    if vocab.is_empty() {
        vocab.push("Active".to_string());
    }

    let mut seen: Vec<(String, String)> = Vec::new(); // rfc → rel（真源 dict：按 rfc 去重）
    let mut supby: Vec<(String, String)> = Vec::new(); // rfc → 被取代者

    check_rfc_docs(root, &idx, &vocab, &mut issues, &mut seen, &mut supby);

    for (rfc, target) in &supby {
        if !seen.iter().any(|(r, _)| r == target) {
            issues.push(format!(
                "{} 的 Superseded by 指向不在册的编号：{}",
                rfc, target
            ));
            continue;
        }
        let mut cur = target.clone();
        let mut hops = 0usize;
        while let Some((_, next)) = supby.iter().find(|(r, _)| r == &cur) {
            if hops >= supby.len() + 1 {
                break;
            }
            cur = next.clone();
            hops += 1;
            if cur == *rfc {
                issues.push(format!("supersede 链成环：{} → … → {}", rfc, rfc));
                break;
            }
        }
    }

    stats.docs = seen.len();
    stats.chains = supby.len();
    (issues, stats)
}

/// 逐条核对 RFC 索引项与文档头部（编号 / 类目 / 状态 / 日期 / 取代关系）。
fn check_rfc_docs(
    root: &Path,
    idx: &crate::pyjson::Json,
    vocab: &[String],
    issues: &mut Vec<String>,
    seen: &mut Vec<(String, String)>,
    supby: &mut Vec<(String, String)>,
) {
    for item in arr_items(get(&idx, "docs")) {
        let rel = py_str(get(item, "path"));
        let rfc = py_str(get(item, "rfc"));
        let p = root.join(&rel);
        if !p.is_file() {
            issues.push(format!("RFC 索引指向不存在的文档：{}", rel));
            continue;
        }
        if let Some(slot) = seen.iter_mut().find(|(r, _)| *r == rfc) {
            issues.push(format!("RFC 编号重复：{}（{} 与 {}）", rfc, slot.1, rel));
            slot.1 = rel.clone(); // 真源 `seen[rfc] = rel` 覆盖
        } else {
            seen.push((rfc.clone(), rel.clone()));
        }

        let text = std::fs::read_to_string(&p).unwrap_or_default();
        let Some(head) = parse_head(&text) else {
            issues.push(format!(
                "{} 缺 RFC 头（修复指引：见 docs 或 core/rfc.py 头格式）",
                rel
            ));
            continue;
        };
        let cat_idx = py_str(get(item, "category"));
        rfc_head_issues(&rel, &head, &rfc, &cat_idx, vocab, issues);
        let is_blank = DASHES.contains(&head.supby.as_str()) || head.supby.is_empty();
        if head.status == "Superseded" && is_blank {
            issues.push(format!("{} 标记 Superseded 但缺 Superseded by", rel));
        }
        if !is_blank {
            record_rfc_supersede(supby, &rfc, &head.supby);
        }
    }
}

/// 文档头面：RFC 编号 / Category / Status / Date / 索引 Category 与头部一致。
fn rfc_head_issues(
    rel: &str,
    head: &RfcHead,
    rfc: &str,
    cat_idx: &str,
    vocab: &[String],
    issues: &mut Vec<String>,
) {
    if head.rfc != rfc {
        issues.push(format!(
            "{} 头部 RFC 与索引不一致：头={} 索引={}",
            rel, head.rfc, rfc
        ));
    }
    if !RFC_CATEGORIES.contains(&head.cat.as_str()) {
        issues.push(format!(
            "{} Category 越词表：{}（{}）",
            rel,
            head.cat,
            RFC_CATEGORIES.join("/")
        ));
    }
    if !vocab.contains(&head.status) {
        issues.push(format!(
            "{} Status 越词表：{}（{}）",
            rel,
            head.status,
            vocab.join("/")
        ));
    }
    if !head.last_updated.is_empty() && head.date != head.last_updated {
        issues.push(format!(
            "{} Date 与「最后更新」不一致：RFC={} 最后更新={}",
            rel, head.date, head.last_updated
        ));
    }
    if !cat_idx.is_empty() && cat_idx != head.cat {
        issues.push(format!(
            "{} Category 索引与头部不一致：索引={} 头={}",
            rel, cat_idx, head.cat
        ));
    }
}

/// 取代链记录：同编号后者覆盖（真源 dict 语义）。
fn record_rfc_supersede(supby: &mut Vec<(String, String)>, rfc: &str, next: &str) {
    if let Some(slot) = supby.iter_mut().find(|(r, _)| *r == rfc) {
        slot.1 = next.to_string();
    } else {
        supby.push((rfc.to_string(), next.to_string()));
    }
}

