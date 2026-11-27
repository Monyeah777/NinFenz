use super::*;

/// promotion / review / cognition 三段声明的成文性核对。
pub(crate) fn check_sections(decl: &Json, root: &Path, issues: &mut Vec<String>) {
    let sub = |k: &str| -> Json {
        get(&decl, k)
            .filter(|v| matches!(v, Json::Object(_)))
            .cloned()
            .unwrap_or_else(empty_stats)
    };
    let prom = sub("promotion");
    if crate::pyval::str_list(get(&prom, "evidence_tiers")) != TIERS {
        issues.push(format!(
            "promotion.evidence_tiers 与判据不一致（期望 {}）",
            TIERS.join("/")
        ));
    }
    if crate::pyval::str_list(get(&prom, "triggers")) != TRIGGERS {
        issues.push(format!(
            "promotion.triggers 与判据不一致（期望 {}）",
            TRIGGERS.join("/")
        ));
    }
    if py_str(get(&prom, "rule")).trim().is_empty() {
        issues.push("promotion 缺 rule（晋升标准必须成文）".to_string());
    }
    if py_str(get(&prom, "on_missing_evidence")) != "stay-reference" {
        issues.push(
            "promotion.on_missing_evidence 必须为 stay-reference（缺证据不得转正）".to_string(),
        );
    }
    let rev = sub("review");
    if arr_items(get(&rev, "machine_gates")).is_empty() {
        issues.push("review 缺 machine_gates（消化审核必须列机检项）".to_string());
    }
    if py_str(get(&rev, "rule")).trim().is_empty() {
        issues.push("review 缺 rule（消化审核规则必须成文）".to_string());
    }
    let cog = sub("cognition");
    let fid = py_str(get(&cog, "filter_module"));
    if fid.is_empty() {
        issues.push("cognition 缺 filter_module（认知裁剪须指定执行模块）".to_string());
    } else if !module_ids(root).contains(&fid) {
        issues.push(format!("cognition.filter_module 指向不在册模块：{}", fid));
    }
}

/// 消化记录读取 + schema 核对；返回条目数。IO 错误按调用方约定上抛。
pub(crate) fn load_transforms(root: &Path, issues: &mut Vec<String>) -> Result<usize, String> {
    let log = match read_json(root, LOG_REL) {
        Ok(Some(l)) => Some(l),
        Ok(None) => None,
        Err(e) => return Err(e),
    };
    let transforms = match &log {
        None => {
            issues.push(format!(
                "缺消化记录 {}（修复指引：见 docs/knowledge.md）",
                LOG_REL
            ));
            0
        }
        Some(l) => {
            if py_str(get(l, "schema")) != LOG_SCHEMA {
                issues.push(format!("消化记录 schema 不匹配（期望 {}）", LOG_SCHEMA));
            }
            arr_items(get(l, "entries")).len()
        }
    };
    Ok(transforms)
}

/// scan 的 stats 结构。
pub(crate) fn knowledge_stats(rows: &[Json], order: &[String], transforms: usize) -> Json {
    Json::Object(vec![
        ("sources".to_string(), Json::Int(rows.len() as i64)),
        (
            "contract".to_string(),
            Json::Int(
                rows.iter()
                    .filter(|s| py_str(get(s, "authority")) == "contract")
                    .count() as i64,
            ),
        ),
        (
            "reference".to_string(),
            Json::Int(
                rows.iter()
                    .filter(|s| py_str(get(s, "authority")) == "reference")
                    .count() as i64,
            ),
        ),
        (
            "order".to_string(),
            Json::Array(order.iter().cloned().map(Json::Str).collect()),
        ),
        ("transforms".to_string(), Json::Int(transforms as i64)),
    ])
}

/// Python `str(list[str])`。
pub(crate) fn py_list(v: &[String]) -> String {
    let inner: Vec<String> = v.iter().map(|s| format!("'{}'", s)).collect();
    format!("[{}]", inner.join(", "))
}

// ---------------------------------------------------------------- 消化记录 / 频率台账

pub(crate) const USAGE_REL: &str = "protocol/knowledge_usage.json";

pub(crate) const USAGE_SCHEMA: &str = "nf-knowledge-usage/1";

pub(crate) const REQUIRED_ENTRY: [&str; 6] = [
    "from",
    "to",
    "digest",
    "reviewed_by",
    "reviewed_at",
    "evidence",
];

pub(crate) fn is_dated(s: &str) -> bool {
    static RE: std::sync::OnceLock<regex::Regex> = std::sync::OnceLock::new();
    let re =
        RE.get_or_init(|| regex::Regex::new(r"^\d{4}-\d{2}-\d{2}$").expect("日期正则固定合法"));
    re.is_match(s)
}

/// Python `isinstance(v, int) and v >= 0` —— **`bool` 是 `int` 的子类**，故 `true`/`false` 都算通过。
pub(crate) fn is_nonneg_int(j: &Json) -> bool {
    match j {
        Json::Int(n) => *n >= 0,
        Json::Float(_) => false, // Python 的 isinstance(1.0, int) 为假
        Json::Bool(_) => true,   // 子类：True>=0 与 False>=0 都为真
        _ => false,
    }
}

/// 真源 `reference_ids`。
pub(crate) fn reference_ids(root: &Path) -> BTreeSet<String> {
    let decl = read_json(root, DECL_REL).ok().flatten();
    decl.map(|d| {
        sources(&d)
            .iter()
            .filter(|s| py_str(get(s, "authority")) == "reference")
            .map(|s| py_str(get(s, "id")))
            .collect()
    })
    .unwrap_or_default()
}

pub(crate) struct PairIssues {
    pub issues: Vec<String>,
    pub stats: Json,
}

/// 真源 `verify_transform` → `(issues, stats)`。
pub(crate) fn verify_transform(root: &Path) -> PairIssues {
    let log = match read_json(root, LOG_REL) {
        Ok(Some(l)) => l,
        Ok(None) => Json::Object(Vec::new()),
        Err(e) => {
            return PairIssues {
                issues: vec![e],
                stats: empty_stats(),
            }
        }
    };
    let entries = arr_items(get(&log, "entries"));
    let refs = reference_ids(root);
    let mut issues: Vec<String> = Vec::new();
    for (i, e) in entries.iter().enumerate() {
        let tag = format!("记录 #{}", i + 1);
        if !matches!(e, Json::Object(_)) {
            issues.push(format!("{} 非对象", tag));
            continue;
        }
        for k in REQUIRED_ENTRY {
            if get(e, k).is_none() {
                issues.push(format!("{} 缺必填字段：{}", tag, k));
            }
        }
        let src = py_str(get(e, "from"));
        if !src.is_empty() && !refs.contains(&src) {
            issues.push(format!("{} 的 from 不是已声明的参考级源：{}", tag, src));
        }
        let to = py_str(get(e, "to"));
        if !to.is_empty() {
            let p = root.join(&to);
            if !p.is_file() {
                issues.push(format!("{} 的产物不存在：{}", tag, to));
            } else {
                let live = std::fs::read(&p)
                    .map(|b| crate::merkle::hex(&crate::merkle::sha256(&b)))
                    .unwrap_or_default();
                if py_str(get(e, "digest")) != live {
                    issues.push(format!(
                        "{} 的产物摘要与记录不一致：{}（产物已改，记录失效；修复指引：重新消化并更新 digest）",
                        tag, to
                    ));
                }
            }
        }
        let ev: Vec<String> = arr_items(get(e, "evidence"))
            .iter()
            .map(|v| py_str(Some(v)))
            .collect();
        if py_truthy(get(e, "promoted").unwrap_or(&Json::Null)) {
            let missing: Vec<&str> = TIERS
                .iter()
                .copied()
                .filter(|t| !ev.contains(&t.to_string()))
                .collect();
            if !missing.is_empty() {
                issues.push(format!("{} 声明转正但缺证据档：{}", tag, missing.join("/")));
            }
            if py_str(get(e, "reviewed_by")).trim().is_empty() {
                issues.push(format!("{} 声明转正但无复核人（消化审核未双签）", tag));
            }
        }
        if let Some(rc) = get(e, "reuse_count") {
            if !is_nonneg_int(rc) {
                issues.push(format!(
                    "{} 的 reuse_count 非非负整数（频次判据不可复算）",
                    tag
                ));
            }
        }
        let ra = py_str(get(e, "reviewed_at"));
        if !ra.is_empty() && !is_dated(&ra) {
            issues.push(format!("{} 的 reviewed_at 非 YYYY-MM-DD", tag));
        }
    }
    let promoted = entries
        .iter()
        .filter(|e| {
            matches!(e, Json::Object(_)) && py_truthy(get(e, "promoted").unwrap_or(&Json::Null))
        })
        .count();
    let stats = Json::Object(vec![
        ("entries".to_string(), Json::Int(entries.len() as i64)),
        ("promoted".to_string(), Json::Int(promoted as i64)),
    ]);
    PairIssues { issues, stats }
}

/// 真源 `verify_usage` → `(issues, stats)`。
pub(crate) fn verify_usage(root: &Path) -> PairIssues {
    let doc = match read_json(root, USAGE_REL) {
        Ok(Some(d)) => d,
        Ok(None) => Json::Object(Vec::new()),
        Err(e) => {
            return PairIssues {
                issues: vec![e],
                stats: empty_stats(),
            }
        }
    };
    if crate::pyval::obj_is_empty(&doc) {
        return PairIssues {
            issues: vec![format!(
                "缺频率台账 {}（修复指引：nf knowledge frequency --trace <file> --write）",
                USAGE_REL
            )],
            stats: empty_stats(),
        };
    }
    let mut issues: Vec<String> = Vec::new();
    if py_str(get(&doc, "schema")) != USAGE_SCHEMA {
        issues.push(format!("频率台账 schema 不匹配（期望 {}）", USAGE_SCHEMA));
    }
    let counts: Json = match get(&doc, "counts") {
        Some(c @ Json::Object(_)) => c.clone(),
        Some(_) => {
            issues.push("频率台账 counts 非对象".to_string());
            Json::Object(Vec::new())
        }
        None => {
            issues.push("频率台账 counts 非对象".to_string());
            Json::Object(Vec::new())
        }
    };
    let decl = read_json(root, DECL_REL).ok().flatten();
    let ids: BTreeSet<String> = decl
        .as_ref()
        .map(|d| sources(d).iter().map(|s| py_str(get(s, "id"))).collect())
        .unwrap_or_default();
    let mut int_sum = 0i64;
    if let Json::Object(pairs) = &counts {
        for (k, v) in pairs {
            if !ids.contains(k) {
                issues.push(format!("频率台账含未声明的源：{}（防幽灵频次）", k));
            }
            if !is_nonneg_int(v) {
                issues.push(format!("频率计数非非负整数：{}", k));
            }
            if let Json::Int(n) = v {
                int_sum += n;
            }
        }
    }
    if let Some(Json::Int(total)) = get(&doc, "total") {
        if *total != int_sum {
            issues.push("频率台账 total 与 counts 求和不一致（手改痕迹）".to_string());
        }
    }
    if let Ok(Some(log)) = read_json(root, LOG_REL) {
        for e in arr_items(get(&log, "entries")) {
            if !matches!(e, Json::Object(_)) || get(e, "reuse_count").is_none() {
                continue;
            }
            let from = py_str(get(e, "from"));
            let got = match &counts {
                Json::Object(p) => p.iter().find(|(k, _)| *k == from).map(|(_, v)| v.clone()),
                _ => None,
            };
            let want = get(e, "reuse_count").cloned().unwrap_or(Json::Null);
            if got.as_ref() != Some(&want) {
                issues.push(format!(
                    "频次不可复算：{} 的记录 reuse_count={}，频率台账={}（修复指引：按 trace 重算，不要手写频次）",
                    from,
                    crate::pyval::plain_str(&want),
                    got.as_ref().map(crate::pyval::plain_str).unwrap_or_else(|| "None".to_string())
                ));
            }
        }
    }
    let stats = Json::Object(vec![
        (
            "sources_with_usage".to_string(),
            Json::Int(match &counts {
                Json::Object(p) => p.len() as i64,
                _ => 0,
            }),
        ),
        ("events".to_string(), Json::Int(int_sum)),
    ]);
    PairIssues { issues, stats }
}
