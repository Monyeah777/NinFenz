use super::*;

pub(crate) const DECL_REL: &str = "protocol/knowledge_sources.json";

pub(crate) const LOG_REL: &str = "protocol/transform_log.json";

pub(crate) const SCHEMA: &str = "nf-knowledge-sources/1";

pub(crate) const LOG_SCHEMA: &str = "nf-transform-log/1";

pub(crate) const AUTHORITIES: [&str; 2] = ["contract", "reference"];

pub(crate) const KINDS: [&str; 2] = ["local-compiled", "external-retrieval"];

pub(crate) const VISIBILITIES: [&str; 3] = ["public", "internal", "restricted"];

pub(crate) const TIERS: [&str; 3] = ["machine-checkable", "reproducible", "externally-attestable"];

pub(crate) const TRIGGERS: [&str; 3] = ["reuse-frequency", "author-mark", "machine-check-pass"];

pub(crate) const FRESH_CONTRACT: [&str; 1] = ["stale_after"];

pub(crate) const FRESH_REFERENCE: [&str; 2] = ["ttl", "no-cache"];

pub(crate) const REQUIRED_SRC: [&str; 6] = [
    "id",
    "authority",
    "kind",
    "locator",
    "requires_source_label",
    "visibility",
];

pub(crate) fn module_id_re() -> &'static regex::Regex {
    static RE: std::sync::OnceLock<regex::Regex> = std::sync::OnceLock::new();
    RE.get_or_init(|| {
        regex::Regex::new(r"(?m)^\s*id:\s*(M\d+|事件:M\d+|通用:M\d+)\s*$")
            .expect("模块 id 正则固定合法")
    })
}

/// 真源 `_read_json`（**不吞解析异常**）。`Ok(None)` = 文件不在场。
pub(crate) fn read_json(root: &Path, rel: &str) -> Result<Option<Json>, String> {
    if !root.join(rel).is_file() {
        return Ok(None);
    }
    jsonread::read_file(root, rel)
        .map(Some)
        .ok_or_else(|| format!("{} 不是合法 JSON", rel))
}

/// 真源 `_module_ids`。
pub(crate) fn module_ids(root: &Path) -> BTreeSet<String> {
    let mut out = BTreeSet::new();
    for pat in ["04_模块库/*/*.md", "community/*/modules/*.md"] {
        for rel in crate::glob::expand(root, pat) {
            let Ok(text) = std::fs::read_to_string(root.join(&rel)) else {
                continue;
            };
            for c in module_id_re().captures_iter(&text) {
                out.insert(c[1].to_string());
            }
        }
    }
    out
}

pub(crate) fn sources(decl: &Json) -> Vec<Json> {
    arr_items(get(decl, "sources"))
        .into_iter()
        .cloned()
        .collect()
}

/// 真源 `_auth`。
pub(crate) fn auth_of(rows: &[Json], sid: &str) -> String {
    for s in rows {
        if py_str(get(s, "id")) == sid {
            return py_str(get(s, "authority"));
        }
    }
    String::new()
}

pub(crate) struct KnowledgeScan {
    /// 真源 `_read_json` 抛异常时整条判据记 error——本线同样如实上报
    pub status: Option<&'static str>,
    pub issues: Vec<String>,
    pub warns: Vec<String>,
    pub stats: Json,
}

pub(crate) fn empty_stats() -> Json {
    Json::Object(Vec::new())
}

/// 真源 `scan` → `(issues, warns, stats)`。
pub(crate) fn scan(root: &Path) -> KnowledgeScan {
    let mut issues: Vec<String> = Vec::new();
    let warns: Vec<String> = Vec::new();

    let decl = match read_json(root, DECL_REL) {
        Ok(Some(d)) => d,
        Ok(None) => {
            return KnowledgeScan {
                status: None,
                issues: vec![format!(
                    "缺知识源声明 {}（修复指引：见 docs/knowledge.md）",
                    DECL_REL
                )],
                warns,
                stats: empty_stats(),
            }
        }
        Err(e) => {
            return KnowledgeScan {
                status: Some("error"),
                issues: vec![e],
                warns,
                stats: empty_stats(),
            }
        }
    };
    if py_str(get(&decl, "schema")) != SCHEMA {
        issues.push(format!("知识源声明 schema 不匹配（期望 {}）", SCHEMA));
    }
    check_vocabularies(&decl, &mut issues);

    let rows = sources(&decl);
    if rows.is_empty() {
        issues.push(format!("未声明任何知识源（{}.sources 为空）", DECL_REL));
    }
    let mut seen: BTreeSet<String> = BTreeSet::new();
    for s in &rows {
        let sid = py_str(get(s, "id"));
        if seen.contains(&sid) {
            issues.push(format!("源 id 重复：{}", sid));
        }
        seen.insert(sid.clone());
        check_source_fields(s, &sid, root, &mut issues);
        check_source_authority(s, &sid, &mut issues);
    }

    let order = check_query_order(&decl, &rows, &mut issues);
    check_sections(&decl, root, &mut issues);

    let transforms = match load_transforms(root, &mut issues) {
        Ok(n) => n,
        Err(e) => {
            return KnowledgeScan {
                status: Some("error"),
                issues: vec![e],
                warns,
                stats: empty_stats(),
            }
        }
    };

    let stats = knowledge_stats(&rows, &order, transforms);
    KnowledgeScan {
        status: None,
        issues,
        warns,
        stats,
    }
}

/// 三个词表声明须与判据常量逐字一致。
pub(crate) fn check_vocabularies(decl: &Json, issues: &mut Vec<String>) {
    for (key, vocab) in [
        ("authority_vocabulary", AUTHORITIES.to_vec()),
        ("kind_vocabulary", KINDS.to_vec()),
        ("visibility_vocabulary", VISIBILITIES.to_vec()),
    ] {
        let got: Vec<String> = crate::pyval::str_list(get(&decl, key));
        if got != vocab {
            issues.push(format!(
                "{} 词表与判据不一致（期望 {}）",
                key,
                vocab.join("/")
            ));
        }
    }
}

/// 知识源必填字段 / 词表 / locator 在场性核对。
pub(crate) fn check_source_fields(s: &Json, sid: &str, root: &Path, issues: &mut Vec<String>) {
    for k in REQUIRED_SRC {
        if get(s, k).is_none() {
            issues.push(format!(
                "源 {} 缺必填字段：{}",
                if sid.is_empty() {
                    "(无名)"
                } else {
                    sid
                },
                k
            ));
        }
}
let auth = py_str(get(s, "authority"));
    let kind = py_str(get(s, "kind"));
    if !AUTHORITIES.contains(&auth.as_str()) {
        issues.push(format!("源 {} authority 越词表：{}", sid, auth));
    }
    if !KINDS.contains(&kind.as_str()) {
        issues.push(format!("源 {} kind 越词表：{}", sid, kind));
    }
    let vis = py_str(get(s, "visibility"));
    if !VISIBILITIES.contains(&vis.as_str()) {
        issues.push(format!("源 {} visibility 越词表：{}", sid, vis));
    }
    let loc = py_str(get(s, "locator"));
    if !loc.is_empty() && !root.join(&loc).exists() {
        issues.push(format!("源 {} 的 locator 不存在：{}（防纸面源）", sid, loc));
    }
}

/// 知识源 authority 级差与时效策略核对。
pub(crate) fn check_source_authority(s: &Json, sid: &str, issues: &mut Vec<String>) {
    let auth = py_str(get(s, "authority"));
    let kind = py_str(get(s, "kind"));
    let fresh = get(s, "freshness")
        .filter(|f| matches!(f, Json::Object(_)))
        .cloned()
        .unwrap_or_else(empty_stats);
    let pol = py_str(get(&fresh, "policy"));
    let labelled = py_truthy(get(s, "requires_source_label").unwrap_or(&Json::Null));
    if auth == "reference" {
        reference_source_issues(s, sid, &kind, &pol, labelled, &fresh, issues);
    } else if auth == "contract" {
        contract_source_issues(sid, &kind, &pol, labelled, issues);
    }
}

/// reference 级源：kind / 来源标注 / 时效策略 / ttl_days。
#[allow(clippy::too_many_arguments)]
fn reference_source_issues(
    s: &Json,
    sid: &str,
    kind: &str,
    pol: &str,
    labelled: bool,
    fresh: &Json,
    issues: &mut Vec<String>,
) {
    if kind != "external-retrieval" {
        issues.push(format!(
            "源 {} 为 reference 级但 kind 非 external-retrieval",
            sid
        ));
    }
    if !labelled {
        issues.push(format!(
            "源 {} 为 reference 级但未要求标注来源（外部数据不得写死；修复指引：requires_source_label: true）",
            sid
        ));
    }
    if !FRESH_REFERENCE.contains(&pol) {
        issues.push(format!(
            "源 {} 为 reference 级但时效策略非法：{}（需 {}）",
            sid,
            if pol.is_empty() {
                "(缺)".to_string()
            } else {
                pol.to_string()
            },
            FRESH_REFERENCE.join(" / ")
        ));
    } else if pol == "ttl" {
        let ok = matches!(get(s, "freshness"), Some(Json::Object(_)))
            && matches!(get(fresh, "ttl_days"), Some(Json::Int(n)) if *n > 0);
        if !ok {
            issues.push(format!("源 {} 声明 ttl 但 ttl_days 非正整数", sid));
        }
    }
}

/// contract 级源：kind / 不要求外部标注 / 时效策略。
fn contract_source_issues(sid: &str, kind: &str, pol: &str, labelled: bool, issues: &mut Vec<String>) {
    if kind != "local-compiled" {
        issues.push(format!(
            "源 {} 为 contract 级但 kind 非 local-compiled",
            sid
        ));
    }
    if labelled {
        issues.push(format!(
            "源 {} 为 contract 级却要求外部来源标注（合同级即本地真源）",
            sid
        ));
    }
    if !FRESH_CONTRACT.contains(&pol) {
        issues.push(format!(
            "源 {} 为 contract 级但时效策略非法：{}（需 stale_after）",
            sid,
            if pol.is_empty() {
                "(缺)".to_string()
            } else {
                pol.to_string()
            }
        ));
    }
}

/// query_order 与 sources 同集合 + 合同级须排参考级之前；返回 order 供 stats。
pub(crate) fn check_query_order(decl: &Json, rows: &[Json], issues: &mut Vec<String>) -> Vec<String> {
    let order: Vec<String> = crate::pyval::str_list(get(&decl, "query_order"));
    let ids: Vec<String> = rows.iter().map(|s| py_str(get(s, "id"))).collect();
    let order_sorted: BTreeSet<String> = order.iter().cloned().collect();
    let ids_sorted: BTreeSet<String> = ids.iter().cloned().collect();
    if order_sorted != ids_sorted {
        let mut missing: Vec<String> = ids_sorted.difference(&order_sorted).cloned().collect();
        let mut extra: Vec<String> = order_sorted.difference(&ids_sorted).cloned().collect();
        missing.sort();
        extra.sort();
        issues.push(format!(
            "query_order 与 sources 不是同一集合（缺 {} / 多 {}）",
            py_list(&missing),
            py_list(&extra)
        ));
    } else {
        let pos: Vec<(String, usize)> = order
            .iter()
            .cloned()
            .enumerate()
            .map(|(i, s)| (s, i))
            .collect();
        let at = |sid: &String| {
            pos.iter()
                .find(|(s, _)| s == sid)
                .map(|(_, i)| *i)
                .unwrap_or(0)
        };
        let ref_idx: Vec<usize> = ids
            .iter()
            .filter(|i| auth_of(&rows, i) == "reference")
            .map(at)
            .collect();
        let con_idx: Vec<usize> = ids
            .iter()
            .filter(|i| auth_of(&rows, i) == "contract")
            .map(at)
            .collect();
        if !ref_idx.is_empty() && !con_idx.is_empty() {
            let max_con = con_idx.iter().copied().max().unwrap_or(0);
            let min_ref = ref_idx.iter().copied().min().unwrap_or(0);
            if max_con > min_ref {
                issues
                    .push("query_order 未把全部合同级排在参考级之前（查询有序被破坏）".to_string());
            }
        }
    }
    order
}
