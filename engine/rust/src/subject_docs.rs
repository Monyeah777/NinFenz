//! 交接/复盘共用「声明 + 文档集合」加载骨架。
//!
//! handover 与 postmortem 门禁此前各写一份 Entry / decl / entries / check_ids / is_dated / is_check，
//! 审计规则 D-004（Rust 单文件重复 8 行块）把它们并到这里；各门禁只保留自己的判据。

use crate::jsonread;
use crate::mdblocks;
use crate::pyjson::Json;
use crate::pyval::{arr_items, get, obj_is_empty, plain_str, plain_str_opt, py_str, py_truthy};
use std::collections::BTreeSet;
use std::path::Path;


pub struct Entry {
    pub path: String,
    pub file: String,
    pub fm: Json,
    pub body: String,
}

pub fn decl(root: &Path, decl_rel: &str) -> Option<Json> {
    if !root.join(decl_rel).is_file() {
        return None;
    }
    jsonread::read_file(root, decl_rel).filter(|d| !obj_is_empty(d))
}

pub fn entries(root: &Path, glob: &str) -> Vec<Entry> {
    crate::glob::expand(root, glob)
        .into_iter()
        .map(|rel| {
            let text = std::fs::read_to_string(root.join(&rel)).unwrap_or_default();
            let (fm, body) = mdblocks::parse_frontmatter(&text);
            let file = rel.rsplit('/').next().unwrap_or(&rel).to_string();
            Entry {
                path: rel,
                file,
                fm,
                body,
            }
        })
        .collect()
}

pub fn check_ids(root: &Path) -> BTreeSet<String> {
    std::fs::read_to_string(root.join("verify.sh"))
        .map(|t| {
            check_id_re()
                .captures_iter(&t)
                .map(|c| c[1].to_string())
                .collect()
        })
        .unwrap_or_default()
}

pub fn is_dated(s: &str) -> bool {
    date_re().is_match(s)
}

pub fn is_check(s: &str) -> Option<String> {
    check_ref_re().captures(s).map(|c| c[1].to_string())
}

/// 真源 check_doc 前半段（handover/postmortem 逐行相同）：必填字段 / status 词表 / date 格式 / 正文章节齐。
pub fn check_frontmatter(
    d: &Json,
    e: &Entry,
    default_fields: &[&str],
    sections: &[&str],
) -> Vec<String> {
    let fm = &e.fm;
    let mut issues = Vec::new();
    let field_names = required_field_names(d, default_fields);
    for k in field_names {
        if !py_truthy(get(fm, &k).unwrap_or(&Json::Null)) {
            issues.push(format!("缺必填字段：{}", k));
        }
    }
    let vocab = status_vocab(d);
    subject_status_issue(&vocab, fm, &mut issues);
    subject_date_issue(fm, &mut issues);
    for sec in sections {
        if !e.body.contains(sec) {
            issues.push(format!("正文缺段落：{}", sec));
        }
    }
    issues
}

/// 必填字段表：声明缺省时落 default_fields。
fn required_field_names(d: &Json, default_fields: &[&str]) -> Vec<String> {
    let fields = arr_items(get(d, "required_fields"));
    if fields.is_empty() {
        default_fields.iter().map(|s| (*s).to_string()).collect()
    } else {
        fields.iter().map(|v| plain_str(v)).collect()
    }
}

/// status 词表：声明缺省时落 open/closed。
fn status_vocab(d: &Json) -> Vec<String> {
    let v = crate::pyval::str_list(get(d, "status_vocabulary"));
    if v.is_empty() {
        vec!["open".to_string(), "closed".to_string()]
    } else {
        v
    }
}

/// status 越词表判据。
fn subject_status_issue(vocab: &[String], fm: &Json, issues: &mut Vec<String>) {
    if !vocab.contains(&plain_str_opt(get(fm, "status"))) {
        issues.push(format!("status 越词表：{}", plain_str_opt(get(fm, "status"))));
    }
}

/// date 格式判据。
fn subject_date_issue(fm: &Json, issues: &mut Vec<String>) {
    if !is_dated(&py_str(get(fm, "date"))) {
        issues.push(format!("date 非 YYYY-MM-DD：{}", plain_str_opt(get(fm, "date"))));
    }
}

/// verify.sh 里 checkNN() 定义行。
pub(crate) fn check_id_re() -> &'static regex::Regex {
    static RE: std::sync::OnceLock<regex::Regex> = std::sync::OnceLock::new();
    RE.get_or_init(|| {
        regex::Regex::new(r"(?m)^check(\d+)\(\)\{").expect("check 定义正则固定合法")
    })
}

/// YYYY-MM-DD 日期。
pub(crate) fn date_re() -> &'static regex::Regex {
    static RE: std::sync::OnceLock<regex::Regex> = std::sync::OnceLock::new();
    RE.get_or_init(|| regex::Regex::new(r"^\d{4}-\d{2}-\d{2}$").expect("日期正则固定合法"))
}

/// checkN 引用（编号捕获）。
pub(crate) fn check_ref_re() -> &'static regex::Regex {
    static RE: std::sync::OnceLock<regex::Regex> = std::sync::OnceLock::new();
    RE.get_or_init(|| regex::Regex::new(r"^check(\d+)$").expect("判据引用正则固定合法"))
}
