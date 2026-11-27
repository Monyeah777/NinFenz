use super::*;

pub(crate) const INDEX_REL: &str = "library/INDEX.md";

pub(crate) const ALIAS_REL: &str = "library/ALIAS.md";

pub(crate) const REQUIRED_KEYS: [&str; 3] = ["id", "type", "title"];

pub(crate) const RECOMMENDED_KEYS: [&str; 7] = [
    "description",
    "license",
    "sources",
    "generated",
    "status",
    "tags",
    "author",
];

pub(crate) const STATUSES: [&str; 3] = ["active", "deprecated", "superseded"];

pub(crate) const BEGIN_INDEX: &str = "<!-- BEGIN GENERATED: library-index -->";

pub(crate) const END_INDEX: &str = "<!-- END GENERATED: library-index -->";

pub(crate) const BEGIN_MIRROR: &str = "<!-- BEGIN GENERATED: library-mirror -->";

pub(crate) const END_MIRROR: &str = "<!-- END GENERATED: library-mirror -->";

/// 真源 `license_gate.ALLOWED`（10 条许可词表）。
pub(crate) const ALLOWED: [&str; 10] = [
    "MIT",
    "Apache-2.0",
    "BSD-3-Clause",
    "BSD-2-Clause",
    "ISC",
    "CC-BY-4.0",
    "CC-BY-SA-4.0",
    "CC0-1.0",
    "专有",
    "未声明",
];

/// 真源 `MIRRORS`（双端镜像前缀；raw = 喂 AI，blob = 给人点开）。
/// ⚠️ blob 前缀**取真源常量**，不要用字符串推导——两个前缀的形态并不对称。
pub(crate) const MIRRORS: [(&str, &str, &str, &str); 2] = [
    (
        "github",
        "https://raw.githubusercontent.com/Monyeah777/NinFenz/main/",
        "https://github.com/Monyeah777/NinFenz/blob/main/",
        "",
    ),
    (
        "gitee",
        "https://gitee.com/monyeah777/ninfenz/raw/main/",
        "https://gitee.com/monyeah777/ninfenz/blob/main/",
        "",
    ),
];

pub(crate) fn is_date(s: &str) -> bool {
    static RE: std::sync::OnceLock<regex::Regex> = std::sync::OnceLock::new();
    let re =
        RE.get_or_init(|| regex::Regex::new(r"^\d{4}-\d{2}-\d{2}$").expect("日期正则固定合法"));
    re.is_match(s)
}

pub(crate) fn is_hex64(s: &str) -> bool {
    static RE: std::sync::OnceLock<regex::Regex> = std::sync::OnceLock::new();
    let re = RE.get_or_init(|| regex::Regex::new(r"^[0-9a-fA-F]{64}$").expect("摘要正则固定合法"));
    re.is_match(s)
}

pub(crate) struct LibVerify {
    pub issues: Vec<String>,
    pub warns: Vec<String>,
    pub stats: Json,
}

/// 真源 `verify(root, key=None, …)`。
pub(crate) fn verify(root: &Path) -> LibVerify {
    let mut issues: Vec<String> = Vec::new();
    let mut warns: Vec<String> = Vec::new();
    let rows: Vec<Entry> = library_entries::entries(root);
    let mut ids: Vec<String> = rows.iter().map(|e| e.id.clone()).collect();
    ids.sort();
    ids.dedup();

    for e in &rows {
        if check_entry_basics(e, &ids, &mut issues, &mut warns) {
            check_entry_attestation(e, root, &mut issues, &mut warns);
        }
    }

    let active = rows
        .iter()
        .filter(|e| {
            let s = py_str(get(&e.fm, "status"));
            (if s.is_empty() {
                "active".to_string()
            } else {
                s
            }) == "active"
        })
        .count();
    let stats = Json::Object(vec![
        ("entries".to_string(), Json::Int(rows.len() as i64)),
        (
            "ids".to_string(),
            Json::Array(ids.into_iter().map(Json::Str).collect()),
        ),
        ("active".to_string(), Json::Int(active as i64)),
        (
            "warns".to_string(),
            Json::Array(warns.iter().map(|w| Json::Str(w.clone())).collect()),
        ),
    ]);
    LibVerify {
        issues,
        warns,
        stats,
    }
}

/// 条目 frontmatter 的字段面核对（缺键 / id 一致 / 许可 / 状态 / 取代 / 日期）。
pub(crate) fn check_entry_basics(
    e: &Entry,
    ids: &[String],
    issues: &mut Vec<String>,
    warns: &mut Vec<String>,
) -> bool {
    let fm = &e.fm;
    let eid = &e.id;
    if !entry_identity_issues(e, fm, eid, issues) {
        return false;
    }
    let st = entry_license_status_issues(eid, fm, issues);
    entry_supersede_issues(eid, fm, ids, &st, issues);
    if !crate::pyval::py_truthy(get(fm, "sources").unwrap_or(&Json::Null)) {
        warns.push(format!("{} 缺 sources（provenance 未声明）", eid));
    }
    entry_date_issues(eid, fm, issues);
    true
}

/// 编码 / frontmatter 存在性 / 必填键 / id 一致；frontmatter 缺失返回 false。
fn entry_identity_issues(e: &Entry, fm: &Json, eid: &str, issues: &mut Vec<String>) -> bool {
    if !e.decode_issue.is_empty() {
        issues.push(format!("编码：{}（{}）", eid, e.decode_issue));
    }
    if crate::pyval::obj_is_empty(fm) {
        issues.push(format!(
            "{} 缺 YAML frontmatter（真源要求：type/id/title 起）",
            eid
        ));
        return false;
    }
    for k in REQUIRED_KEYS {
        if py_str(get(fm, k)).trim().is_empty() {
            issues.push(format!("{} frontmatter 缺必填键：{}", eid, k));
        }
    }
    if py_str(get(fm, "id")) != *eid {
        issues.push(format!(
            "{} frontmatter id 与文件名不一致：{}",
            eid,
            plain_str(get(fm, "id").unwrap_or(&Json::Null))
        ));
    }
    true
}

/// license 词表 + status（缺省 active）；返回 status。
fn entry_license_status_issues(eid: &str, fm: &Json, issues: &mut Vec<String>) -> String {
    let lic = py_str(get(fm, "license"));
    if !lic.is_empty() && !ALLOWED.contains(&lic.as_str()) {
        issues.push(format!("{} license 不在词表：{}", eid, lic));
    }
    let st = {
        let s = py_str(get(fm, "status"));
        if s.is_empty() {
            "active".to_string()
        } else {
            s
        }
    };
    if !STATUSES.contains(&st.as_str()) {
        issues.push(format!(
            "{} status 不在词表：{}（{}）",
            eid,
            st,
            STATUSES.join("/")
        ));
    }
    st
}

/// 取代关系：superseded 须带 superseded_by；目标须在册且不得自指。
fn entry_supersede_issues(eid: &str, fm: &Json, ids: &[String], st: &str, issues: &mut Vec<String>) {
    if st == "superseded" && py_str(get(fm, "superseded_by")).trim().is_empty() {
        issues.push(format!("{} status=superseded 但缺 superseded_by", eid));
    }
    let sb = py_str(get(fm, "superseded_by")).trim().to_string();
    if !sb.is_empty() && !ids.contains(&sb) {
        issues.push(format!("{} superseded_by 指向不存在的条目：{}", eid, sb));
    }
    if sb == *eid {
        issues.push(format!("{} superseded_by 指向自身（取代链成环）", eid));
    }
}

/// 日期键格式。
fn entry_date_issues(eid: &str, fm: &Json, issues: &mut Vec<String>) {
    for date_key in ["generated", "verified", "stale_after"] {
        let v = py_str(get(fm, date_key)).trim().to_string();
        if !v.is_empty() && !is_date(&v) {
            issues.push(format!("{} {} 非 YYYY-MM-DD：{}", eid, date_key, v));
        }
    }
}

/// 条目 attestation 面核对（摘要 / 内容漂移 / 签名锚未移植）+ 推荐键提示。
pub(crate) fn check_entry_attestation(
    e: &Entry,
    root: &Path,
    issues: &mut Vec<String>,
    warns: &mut Vec<String>,
) {
    let fm = &e.fm;
    let eid = &e.id;
    let att = py_str(get(fm, "attestation")).trim().to_string();
    if !att.is_empty() {
        let mut drifted = false;
        if !is_hex64(&att) {
            let head: String = att.chars().take(16).collect();
            issues.push(format!(
                "{} attestation 非 64 位十六进制摘要：{}",
                eid, head
            ));
        } else {
            let live = library_entries::entry_digest(root, &e.path);
            drifted = live != att.to_lowercase();
        }
        let scheme = py_str(get(fm, "anchor_scheme")).trim().to_string();
        if drifted {
            if !scheme.is_empty() {
                issues.push(format!(
                    "{} 签名锚已不覆盖当前内容（落锚后内容被改）（修复指引：重新 nf library attest <编号> 并分发新回执）",
                    eid
                ));
            } else {
                warns.push(format!(
                    "{} attestation 与当前内容不符（内容已改，需重签）",
                    eid
                ));
            }
        }
        if !scheme.is_empty() {
            // fail-closed：本线未移植 attest，**不当作通过**
            issues.push(format!(
                "{} 带签名锚 scheme={}，但本线未移植 core.attest.verify_digest_anchor（修复指引：该条须由 Python 侧 `nf library verify` 核；本线不冒充通过）",
                eid, scheme
            ));
        }
    }

    for k in RECOMMENDED_KEYS {
        if !library_entries::has_key(fm, k) {
            warns.push(format!("{} 缺推荐键：{}", eid, k));
        }
    }
}
