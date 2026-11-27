use super::*;

pub(crate) const VOCAB_REL: &str = "protocol/vocabularies.json";

pub(crate) const NORM_REL: &str = "protocol/normative.json";

pub(crate) const DC_REL: &str = "protocol/data_contracts.json";

pub(crate) const RECEIPTS_REL: &str = "protocol/RECEIPTS.json";

pub(crate) const VOCAB_SCHEMA: &str = "nf-vocabularies/1";

pub(crate) const NORM_SCHEMA: &str = "nf-normative/1";

pub(crate) const DC_SCHEMA: &str = "nf-data-contracts/1";

pub(crate) fn read(root: &Path, rel: &str) -> Option<Json> {
    if !root.join(rel).is_file() {
        return None;
    }
    jsonread::read_file(root, rel)
}

/// 真源 `_as_values`：dict → 键；list → 元素 str；其余 → 空。
pub(crate) fn as_values(j: &Json) -> Vec<String> {
    match j {
        Json::Object(p) => p.iter().map(|(k, _)| k.clone()).collect(),
        Json::Array(a) => a.iter().map(plain_str).collect(),
        _ => Vec::new(),
    }
}

/// 真源 `_probe` → `(values, note)`。
pub(crate) fn probe(root: &Path, pr: &Json) -> (Vec<String>, String) {
    let kind = py_str(get(pr, "kind"));
    match kind.as_str() {
        "literal" => (Vec::new(), "literal（以本册为准）".to_string()),
        "python_attr" => {
            let module = plain_str_opt(get(pr, "module"));
            let attr = plain_str_opt(get(pr, "attr"));
            match pyconsts::lookup(&module, &attr) {
                Some(vals) => (
                    vals.iter().map(|s| (*s).to_string()).collect(),
                    "python_attr".to_string(),
                ),
                None => (
                    Vec::new(),
                    format!("python_attr 未登记：{}.{}", module, attr),
                ),
            }
        }
        "json_path" => {
            let rel = py_str(get(pr, "file"));
            let Some(mut doc) = read(root, &rel) else {
                return (
                    Vec::new(),
                    format!("json_path 断链：{}", py_str(get(pr, "path"))),
                );
            };
            for part in py_str(get(pr, "path")).split('.') {
                let next = match &doc {
                    Json::Object(p) => p.iter().find(|(k, _)| k == part).map(|(_, v)| v.clone()),
                    _ => None,
                };
                match next {
                    Some(v) => doc = v,
                    None => {
                        return (
                            Vec::new(),
                            format!("json_path 断链：{}", py_str(get(pr, "path"))),
                        )
                    }
                }
            }
            (as_values(&doc), "json_path".to_string())
        }
        other => (Vec::new(), format!("未知 probe.kind：{}", other)),
    }
}

/// 真源 `verify_vocabularies` → `(issues, schemes, literal_count)`。
pub(crate) fn verify_vocabularies(root: &Path) -> (Vec<String>, usize, usize) {
    let mut issues = Vec::new();
    let Some(doc) = read(root, VOCAB_REL) else {
        return (vec![format!("缺词表登记册 {}", VOCAB_REL)], 0, 0);
    };
    if crate::pyval::obj_is_empty(&doc) {
        return (vec![format!("缺词表登记册 {}", VOCAB_REL)], 0, 0);
    }
    if py_str(get(&doc, "schema")) != VOCAB_SCHEMA {
        issues.push(format!("词表登记册 schema 不匹配（期望 {}）", VOCAB_SCHEMA));
    }
    let mut statuses: Vec<String> = crate::pyval::str_list(get(&doc, "status_vocabulary"));
    statuses.sort();
    if statuses != ["active", "deprecated"] {
        issues.push("status 词表与判据不一致（期望 active/deprecated）".to_string());
    }
    let statuses = crate::pyval::str_list(get(&doc, "status_vocabulary"));
    let kinds = crate::pyval::str_list(get(&doc, "probe_kinds"));

    let mut seen: BTreeSet<String> = BTreeSet::new();
    let mut literal = 0usize;
    for s in arr_items(get(&doc, "schemes")) {
        literal += vocab_scheme_issues(root, &s, &statuses, &kinds, &mut seen, &mut issues);
    }
    (issues, seen.len(), literal)
}

/// 单条词表：id 唯一 / status / 值集 / alias 撞车 / probe 与真源一致；返回是否 literal 计数（0 或 1）。
fn vocab_scheme_issues(
    root: &Path,
    s: &Json,
    statuses: &[String],
    kinds: &[String],
    seen: &mut BTreeSet<String>,
    issues: &mut Vec<String>,
) -> usize {
    let sid = py_str(get(s, "id"));
    if seen.contains(&sid) {
        issues.push(format!("词表 id 重复：{}", sid));
    }
    seen.insert(sid.clone());
    if !statuses.contains(&plain_str_opt(get(s, "status"))) {
        issues.push(format!(
            "词表 {} status 越词表：{}",
            sid,
            plain_str_opt(get(s, "status"))
        ));
    }
    let vals: Vec<String> = arr_items(get(s, "values"))
        .iter()
        .map(|v| plain_str(v))
        .collect();
    vocab_value_issues(&sid, &vals, s, issues);
    let pr = get(s, "probe")
        .filter(|v| matches!(v, Json::Object(_)))
        .cloned()
        .unwrap_or(Json::Object(Vec::new()));
    if !kinds.contains(&py_str(get(&pr, "kind"))) {
        issues.push(format!(
            "词表 {} 的 probe.kind 不在册：{}",
            sid,
            plain_str_opt(get(&pr, "kind"))
        ));
        return 0;
    }
    let (live, note) = probe(root, &pr);
    if py_str(get(&pr, "kind")) == "literal" {
        return 1;
    }
    if live.is_empty() {
        issues.push(format!("词表 {} 的真源取不到（{}）", sid, note));
        return 0;
    }
    vocab_drift_issue(&sid, &vals, &live, issues);
    0
}

/// 值集面：至少两个值、无重复、alias 不得与值撞车。
fn vocab_value_issues(sid: &str, vals: &[String], s: &Json, issues: &mut Vec<String>) {
    if vals.len() < 2 {
        issues.push(format!("词表 {} 少于两个值（不成词表）", sid));
    }
    let uniq: BTreeSet<&String> = vals.iter().collect();
    if uniq.len() != vals.len() {
        issues.push(format!("词表 {} 值重复", sid));
    }
    for a in arr_items(get(s, "aliases")) {
        if vals.contains(&plain_str(a)) {
            issues.push(format!("词表 {} 的 alias 与值撞车：{}", sid, plain_str(a)));
        }
    }
}

/// 册值与真源值集漂移。
fn vocab_drift_issue(sid: &str, vals: &[String], live: &[String], issues: &mut Vec<String>) {
    let mut a = live.to_vec();
    let mut b = vals.to_vec();
    a.sort();
    b.sort();
    if a != b {
        issues.push(format!(
            "词表 {} 与真源漂移：册={} 真源={}",
            sid,
            b.join("/"),
            a.join("/")
        ));
    }
}
