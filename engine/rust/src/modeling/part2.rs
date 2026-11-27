use super::*;

/// 真源 `verify_normative` → `(issues, normative_count, informative_count)`。
pub(crate) fn verify_normative(root: &Path) -> (Vec<String>, usize, usize) {
    let mut issues = Vec::new();
    let Some(doc) = read(root, NORM_REL) else {
        return (vec![format!("缺规范/说明件名单 {}", NORM_REL)], 0, 0);
    };
    if crate::pyval::obj_is_empty(&doc) {
        return (vec![format!("缺规范/说明件名单 {}", NORM_REL)], 0, 0);
    }
    if py_str(get(&doc, "schema")) != NORM_SCHEMA {
        issues.push(format!("规范件名单 schema 不匹配（期望 {}）", NORM_SCHEMA));
    }
    let checks = check_ids(root);
    let receipts = receipt_ids(root);
    let mut norm_paths: Vec<String> = Vec::new();
    for item in arr_items(get(&doc, "normative")) {
        let entry = if matches!(item, Json::Object(_)) {
            item.clone()
        } else {
            Json::Object(vec![("path".to_string(), Json::Str(plain_str(item)))])
        };
        let rel = py_str(get(&entry, "path"));
        norm_paths.push(rel.clone());
        if rel.is_empty() {
            issues.push("规范件条目缺 path".to_string());
            continue;
        }
        if !root.join(&rel).is_file() {
            issues.push(format!("规范件不存在：{}", rel));
            continue;
        }
        if receipts.contains(&rel) {
            continue;
        }
        let covered: Vec<String> = arr_items(get(&entry, "covered_by"))
            .iter()
            .map(|c| plain_str(c))
            .collect();
        if covered.is_empty() {
            issues.push(format!(
                "规范件既未被回执锚定也无 covered_by：{}（修复指引：跑 nf receipts --write，或显式声明 covered_by）",
                rel
            ));
            continue;
        }
        for c in covered {
            if let Some(cap) = judge_check_re().captures(&c) {
                if !checks.contains(&cap[1]) {
                    issues.push(format!(
                        "规范件 {} 的 covered_by 指向不存在的 check：{}",
                        rel, c
                    ));
                }
            }
        }
    }

    let mut info_hits: BTreeSet<String> = BTreeSet::new();
    for g in arr_items(get(&doc, "informative"))
        .iter()
        .map(|v| plain_str(v))
    {
        // 真源 `pat = g + "/*" if g.endswith("/**") else g` —— 是**在 g 后面追加** `/*`，
        // 不是把 `/**` 换成 `/*`（`docs/**` → `docs/**/*`）。抄成后者会丢掉 `**`，
        // 说明件数从 2352 掉到 75，且**不会**被 ok/not-ok 察觉（只错一个计数）。
        let pat = if g.ends_with("/**") {
            format!("{}/*", g)
        } else {
            g.clone()
        };
        let hits = crate::glob::expand(root, &pat);
        for h in hits {
            info_hits.insert(h);
        }
    }
    for rel in &info_hits {
        if receipts.contains(rel) {
            issues.push(format!("说明件被回执锚定（等于把解释当规范）：{}", rel));
        }
    }
    let norm_set: BTreeSet<String> = norm_paths.iter().cloned().collect();
    let mut overlap: Vec<String> = info_hits.intersection(&norm_set).cloned().collect();
    overlap.sort();
    for rel in overlap {
        issues.push(format!("同一件既列规范又列说明：{}", rel));
    }
    (issues, norm_paths.len(), info_hits.len())
}

/// 真源 `verify_contracts` → `(issues, contracts_count)`。
pub(crate) fn verify_contracts(root: &Path) -> (Vec<String>, usize) {
    let mut issues = Vec::new();
    let Some(doc) = read(root, DC_REL) else {
        return (vec![format!("缺数据契约登记 {}", DC_REL)], 0);
    };
    if crate::pyval::obj_is_empty(&doc) {
        return (vec![format!("缺数据契约登记 {}", DC_REL)], 0);
    }
    if py_str(get(&doc, "schema")) != DC_SCHEMA {
        issues.push(format!("数据契约登记 schema 不匹配（期望 {}）", DC_SCHEMA));
    }
    let statuses = crate::pyval::str_list(get(&doc, "status_vocabulary"));
    let prefixes = crate::pyval::str_list(get(&doc, "rule_prefixes"));
    if prefixes != ["check", "assertion:"] {
        issues.push("rule_prefixes 与判据不一致（期望 check / assertion:）".to_string());
    }
    let checks = check_ids(root);
    let assertion_ids: BTreeSet<String> = read(root, "protocol/assertions.json")
        .map(|d| {
            arr_items(get(&d, "assertions"))
                .iter()
                .map(|a| plain_str_opt(get(a, "id")))
                .collect()
        })
        .unwrap_or_default();

    let mut seen: BTreeSet<String> = BTreeSet::new();
    for c in arr_items(get(&doc, "contracts")) {
        let cid = py_str(get(c, "id"));
        if seen.contains(&cid) {
            issues.push(format!("契约 id 重复：{}", cid));
        }
        seen.insert(cid.clone());
        let art = py_str(get(c, "artifact"));
        if art.is_empty() || !root.join(&art).is_file() {
            issues.push(format!(
                "契约 {} 的 artifact 不存在：{}",
                cid,
                if art.is_empty() {
                    "(缺)"
                } else {
                    art.as_str()
                }
            ));
        }
        if !statuses.contains(&plain_str_opt(get(c, "status"))) {
            issues.push(format!(
                "契约 {} status 越词表：{}",
                cid,
                plain_str_opt(get(c, "status"))
            ));
        }
        if py_str(get(c, "owner")).trim().is_empty() {
            issues.push(format!("契约 {} 缺 owner（无人认领的契约不许登记）", cid));
        }
        if py_str(get(c, "freshness")).trim().is_empty() {
            issues.push(format!("契约 {} 缺 freshness（重建动作必须写明）", cid));
        }
        let rule = py_str(get(c, "quality_rule"));
        if let Some(rest) = rule.strip_prefix("check") {
            if !checks.contains(rest) {
                issues.push(format!(
                    "契约 {} 的 quality_rule 指向不存在的 check：{}",
                    cid, rule
                ));
            }
        } else if let Some(rest) = rule.strip_prefix("assertion:") {
            if !assertion_ids.contains(rest) {
                issues.push(format!(
                    "契约 {} 的 quality_rule 指向不存在的断言：{}",
                    cid, rule
                ));
            }
        } else {
            issues.push(format!(
                "契约 {} 的 quality_rule 无法解析（须 checkN 或 assertion:<id>）：{}",
                cid,
                if rule.is_empty() {
                    "(缺)"
                } else {
                    rule.as_str()
                }
            ));
        }
    }
    (issues, seen.len())
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

pub(crate) fn judge_check_re() -> &'static regex::Regex {
    static RE: std::sync::OnceLock<regex::Regex> = std::sync::OnceLock::new();
    RE.get_or_init(|| regex::Regex::new(r"^check(\d+)$").expect("判据引用正则固定合法"))
}

pub(crate) fn receipt_ids(root: &Path) -> BTreeSet<String> {
    read(root, RECEIPTS_REL)
        .map(|d| {
            arr_items(get(&d, "entries"))
                .iter()
                .map(|e| plain_str_opt(get(e, "id")))
                .collect()
        })
        .unwrap_or_default()
}

/// 真源 `modeling.scan` 的三段聚合（本契约只要 issues 与三个计数）。
pub(crate) struct ModelingScan {
    pub issues: Vec<String>,
    pub schemes: usize,
    pub normative: usize,
    pub informative_files: usize,
    pub contracts: usize,
}

pub(crate) fn scan(root: &Path) -> ModelingScan {
    let (mut issues, schemes, _literal) = verify_vocabularies(root);
    let (ni, normative, informative_files) = verify_normative(root);
    let (ci, contracts) = verify_contracts(root);
    issues.extend(ni);
    issues.extend(ci);
    ModelingScan {
        issues,
        schemes,
        normative,
        informative_files,
        contracts,
    }
}
