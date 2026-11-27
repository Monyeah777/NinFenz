use super::*;

pub(crate) const GLOB: &str = "decisions/ADR-*.md";

pub(crate) const INDEX_REL: &str = "decisions/INDEX.md";

pub(crate) const RECEIPTS_REL: &str = "protocol/RECEIPTS.json";

pub(crate) const BEGIN: &str = "<!-- BEGIN GENERATED: decisions-index -->";

pub(crate) const END: &str = "<!-- END GENERATED: decisions-index -->";

pub(crate) const STATUSES: [&str; 4] = ["proposed", "accepted", "superseded", "deprecated"];

pub(crate) const SECTIONS: [&str; 3] = ["## 背景", "## 决策", "## 后果"];

/// 真源 `_DASH = ("—", "-", "")`。
pub(crate) const DASHES: [&str; 3] = ["—", "-", ""];

pub(crate) struct Entry {
    pub(crate) file: String,
    pub(crate) path: String,
    pub(crate) fm: Json,
    pub(crate) body: String,
}

pub(crate) fn re_id() -> &'static regex::Regex {
    static RE: std::sync::OnceLock<regex::Regex> = std::sync::OnceLock::new();
    RE.get_or_init(|| regex::Regex::new(r"^ADR-(\d{4})$").expect("ADR id 正则固定合法"))
}

pub(crate) fn re_file_id() -> &'static regex::Regex {
    static RE: std::sync::OnceLock<regex::Regex> = std::sync::OnceLock::new();
    RE.get_or_init(|| regex::Regex::new(r"^ADR-(\d{4})-").expect("ADR 文件名正则固定合法"))
}

pub(crate) fn re_check() -> &'static regex::Regex {
    static RE: std::sync::OnceLock<regex::Regex> = std::sync::OnceLock::new();
    RE.get_or_init(|| regex::Regex::new(r"^check(\d+)$").expect("判据引用正则固定合法"))
}

pub(crate) fn re_adr() -> &'static regex::Regex {
    static RE: std::sync::OnceLock<regex::Regex> = std::sync::OnceLock::new();
    RE.get_or_init(|| regex::Regex::new(r"^ADR-\d{4}$").expect("ADR 引用正则固定合法"))
}

pub(crate) fn re_dated() -> &'static regex::Regex {
    static RE: std::sync::OnceLock<regex::Regex> = std::sync::OnceLock::new();
    RE.get_or_init(|| regex::Regex::new(r"^\d{4}-\d{2}-\d{2}$").expect("日期正则固定合法"))
}

// check 定义行正则。模式串含裸花括号，提为常量以免被朴素括号计数误判。
pub(crate) const CHECK_DEF_PAT: &str = r"(?m)^check(\d+)\(\)\{";

pub(crate) fn check_ids(root: &Path) -> BTreeSet<String> {
    static RE: std::sync::OnceLock<regex::Regex> = std::sync::OnceLock::new();
    let re =
        RE.get_or_init(|| regex::Regex::new(CHECK_DEF_PAT).expect("check 定义正则固定合法"));
    std::fs::read_to_string(root.join("verify.sh"))
        .map(|t| re.captures_iter(&t).map(|c| c[1].to_string()).collect())
        .unwrap_or_default()
}

pub(crate) fn receipt_ids(root: &Path) -> BTreeSet<String> {
    jsonread::read_file(root, RECEIPTS_REL)
        .map(|d| {
            arr_items(get(&d, "entries"))
                .iter()
                .map(|e| plain_str_opt(get(e, "id")))
                .collect()
        })
        .unwrap_or_default()
}

/// 真源 `entries`：按 id（缺则文件名）排序。
pub(crate) fn entries(root: &Path) -> Vec<Entry> {
    let mut out: Vec<Entry> = crate::glob::expand(root, GLOB)
        .into_iter()
        .map(|rel| {
            let text = std::fs::read_to_string(root.join(&rel)).unwrap_or_default();
            let (fm, body) = mdblocks::parse_frontmatter(&text);
            let file = rel.rsplit('/').next().unwrap_or(&rel).to_string();
            Entry {
                file,
                path: rel,
                fm,
                body,
            }
        })
        .collect();
    out.sort_by_key(|e| {
        let id = get(&e.fm, "id");
        if py_truthy(id.unwrap_or(&Json::Null)) {
            plain_str(id.unwrap())
        } else {
            e.file.clone()
        }
    });
    out
}

/// 真源 `scan` → `(issues, decisions, accepted, chains)`。
pub(crate) fn scan(root: &Path) -> (Vec<String>, usize, usize, usize) {
    let mut issues: Vec<String> = Vec::new();
    let rows = entries(root);
    if rows.is_empty() {
        return (vec![format!("未发现任何 ADR（{}）", GLOB)], 0, 0, 0);
    }
    let checks = check_ids(root);
    let receipts = receipt_ids(root);
    let has_receipts = root.join(RECEIPTS_REL).is_file();

    let mut ids: Vec<(String, String)> = Vec::new(); // id → file（真源 dict：同 id 覆盖）
    let mut supby: Vec<(String, String)> = Vec::new();
    for e in &rows {
        decision_entry_issue(
            e,
            &checks,
            &receipts,
            has_receipts,
            root,
            &mut issues,
            &mut ids,
            &mut supby,
        );
    }

    supersede_cycle_issues(&supby, &ids, &mut issues);
    supersedes_target_issues(&ids, &rows, &mut issues);

    let accepted = rows
        .iter()
        .filter(|e| plain_str_opt(get(&e.fm, "status")) == "accepted")
        .count();
    (issues, ids.len(), accepted, supby.len())
}

/// 逐条 ADR 的前置面核对（字段 / 状态 / 段落 / evidence / 回执锚定 / 取代关系）。
pub(crate) fn decision_entry_issue(
    e: &Entry,
    checks: &BTreeSet<String>,
    receipts: &BTreeSet<String>,
    has_receipts: bool,
    root: &Path,
    issues: &mut Vec<String>,
    ids: &mut Vec<(String, String)>,
    supby: &mut Vec<(String, String)>,
) {
    let fm = &e.fm;
    let name = &e.file;
    let did = py_str(get(fm, "id"));
    let tag = if did.is_empty() {
        name.clone()
    } else {
        did.clone()
    };
    if did.is_empty() {
        issues.push(format!("{} 缺 frontmatter id", name));
        return;
    }
    if !re_id().is_match(&did) {
        issues.push(format!("{} 的 id 不合法（须 ADR-四位数字）：{}", name, did));
    }
    entry_file_id_issues(name, &did, issues);
    entry_register_id(&did, name, ids, issues);
    let st = entry_field_issues(&tag, fm, issues);
    entry_section_issues(&tag, &e.body, issues);
    entry_evidence_issues(&tag, fm, root, checks, issues);
    entry_acceptance_issues(&tag, &st, has_receipts, &e.path, receipts, issues);
    entry_supersede_issues(&tag, &st, &did, fm, supby, issues);
}

/// 取代链核对：指向不在册 + 成环（hops 上限防死循环）。
fn supersede_cycle_issues(
    supby: &[(String, String)],
    ids: &[(String, String)],
    issues: &mut Vec<String>,
) {
    for (did, target) in supby {
        if !ids.iter().any(|(i, _)| i == target) {
            issues.push(format!(
                "{} 的 superseded_by 指向不在册编号：{}",
                did, target
            ));
            continue;
        }
        let mut cur = target.clone();
        let mut hops = 0usize;
        while let Some((_, next)) = supby.iter().find(|(i, _)| *i == cur) {
            if hops >= supby.len() + 1 {
                break;
            }
            cur = next.clone();
            hops += 1;
            if cur == *did {
                issues.push(format!("取代链成环：{} → … → {}", did, did));
                break;
            }
        }
    }
}

/// 每条 ADR 的 supersedes 指向必须在册（DASHES 占位不算目标）。
fn supersedes_target_issues(
    ids: &[(String, String)],
    rows: &[Entry],
    issues: &mut Vec<String>,
) {
    for (did, _) in ids {
        for other in rows {
            if &py_str(get(&other.fm, "id")) != did {
                continue;
            }
            let sup = py_str(get(&other.fm, "supersedes")).trim().to_string();
            if !DASHES.contains(&sup.as_str()) && !ids.iter().any(|(i, _)| *i == sup) {
                issues.push(format!("{} 的 supersedes 指向不在册编号：{}", did, sup));
            }
        }
    }
}

/// id 与文件名一致性。
fn entry_file_id_issues(name: &str, did: &str, issues: &mut Vec<String>) {
    match re_file_id().captures(name) {
        Some(c) if format!("ADR-{}", &c[1]) == did => {}
        _ => issues.push(format!("{} 的 id 与文件名不一致：{}", name, did)),
    }
}

/// id 登记（同 id → 后者覆盖文件，与真源 dict 语义一致）。
fn entry_register_id(did: &str, name: &str, ids: &mut Vec<(String, String)>, issues: &mut Vec<String>) {
    if let Some((_, prev)) = ids.iter().find(|(i, _)| *i == did) {
        issues.push(format!("ADR 编号重复：{}（{} 与 {}）", did, prev, name));
        if let Some(slot) = ids.iter_mut().find(|(i, _)| *i == did) {
            slot.1 = name.to_string();
        }
    } else {
        ids.push((did.to_string(), name.to_string()));
    }
}

/// 必填字段 / status 词表 / date 格式；返回 status。
fn entry_field_issues(tag: &str, fm: &Json, issues: &mut Vec<String>) -> String {
    for k in ["title", "status", "date", "evidence"] {
        if !py_truthy(get(fm, k).unwrap_or(&Json::Null)) {
            issues.push(format!("{} 缺必填字段：{}", tag, k));
        }
    }
    let st = py_str(get(fm, "status"));
    if !st.is_empty() && !STATUSES.contains(&st.as_str()) {
        issues.push(format!(
            "{} 的 status 越词表：{}（{}）",
            tag,
            st,
            STATUSES.join("/")
        ));
    }
    let date = py_str(get(fm, "date"));
    if !date.is_empty() && !re_dated().is_match(&date) {
        issues.push(format!("{} 的 date 非 YYYY-MM-DD：{}", tag, date));
    }
    st
}

/// 正文必备段落。
fn entry_section_issues(tag: &str, body: &str, issues: &mut Vec<String>) {
    for sec in SECTIONS {
        if !body.contains(sec) {
            issues.push(format!("{} 正文缺段落：{}", tag, sec));
        }
    }
}


/// 真源 `render_index`：投影表。
pub(crate) fn render_index(root: &Path) -> String {
    let mut out: Vec<String> = vec![
        BEGIN.to_string(),
        String::new(),
        "## 决策登记表（由各 ADR frontmatter 生成，勿手改）".to_string(),
        String::new(),
        "| 编号 | 标题 | 状态 | 日期 | 取代 |".to_string(),
        "|---|---|---|---|---|".to_string(),
    ];
    for e in entries(root) {
        let fm = &e.fm;
        let cell = |k: &str, default: String| -> String {
            match get(fm, k) {
                Some(v) => plain_str(v),
                None => default,
            }
        };
        // 真源 `fm.get("superseded_by") or "—"` —— 假值落横线
        let sb = match get(fm, "superseded_by") {
            Some(v) if py_truthy(v) => plain_str(v),
            _ => "—".to_string(),
        };
        out.push(format!(
            "| {} | {} | {} | {} | {} |",
            cell("id", e.file.clone()),
            cell("title", String::new()),
            cell("status", String::new()),
            cell("date", String::new()),
            sb
        ));
    }
    out.push(String::new());
    out.push(
        "> 真源 = `decisions/ADR-*.md` 的 frontmatter；本表为投影（`nf decisions reindex` 重建）。"
            .to_string(),
    );
    out.push(String::new());
    out.push(END.to_string());
    out.join("\n")
}

/// 真源 `check_projection`。
pub(crate) fn check_projection(root: &Path) -> Vec<String> {
    let p = root.join(INDEX_REL);
    if !p.is_file() {
        return vec![format!(
            "缺 {}（修复指引：nf decisions reindex）",
            INDEX_REL
        )];
    }
    let text = std::fs::read_to_string(&p).unwrap_or_default();
    if !text.contains(BEGIN) || !text.contains(END) {
        return vec![format!("{} 缺生成区标记", INDEX_REL)];
    }
    let i = text.find(BEGIN).unwrap_or(0);
    let j = text.find(END).unwrap_or(0) + END.len();
    if &text[i..j] == render_index(root) {
        Vec::new()
    } else {
        vec!["决策登记表与实时重算不一致（跑 nf decisions reindex）".to_string()]
    }
}
