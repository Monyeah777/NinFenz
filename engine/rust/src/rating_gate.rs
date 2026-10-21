//! 内容分级门（`rating_gate`）—— 与真源 `desktop/src/core/rating_gate.py` 对账。
//!
//! 真源 = 条目 frontmatter 的 `rating:`，词表 = 声明件 `library/intake.json: rating.vocabulary`
//! （**以声明为准**，门禁自动跟随，不写死在代码里）。`unrated` 是**显式声明未分级**而非缺省：
//! 缺字段 = FAIL（分级是消费方选择的前提，不许沉默）。本门只判「声明在场且合规」，
//! **不替投稿人做适龄判断**（那是内容责任，不是机器责任）。
//!
//! 本模块是 `nf verify-report` 的 `rating` 判据，**不单独开 CLI 面**。

use crate::pyjson::Json;
use crate::pyval::{get, plain_str, py_str};
use std::collections::BTreeMap;
use std::path::Path;

pub const INTAKE_REL: &str = "library/intake.json";
const DEFAULT_VOCAB: [&str; 4] = ["general", "teen", "mature", "unrated"];

/// 真源 `vocabulary`：分级词表真源 = `library/intake.json` 的 `rating.vocabulary`（缺失即用默认值）。
pub fn vocabulary(root: &Path) -> Vec<String> {
    let Some(doc) = crate::library::intake_doc(root) else {
        return DEFAULT_VOCAB.iter().map(|s| (*s).to_string()).collect();
    };
    let got: Vec<String> = crate::pyval::arr_items(
        get(&doc, "rating").and_then(|r| get(r, "vocabulary")),
    )
    .iter()
    .map(|v| plain_str(v))
    .collect();
    if got.is_empty() {
        DEFAULT_VOCAB.iter().map(|s| (*s).to_string()).collect()
    } else {
        got
    }
}

pub struct RatingScan {
    pub issues: Vec<String>,
    pub stats: Json,
}

/// 真源 `scan` → `(issues, stats)`。
pub fn scan(root: &Path) -> RatingScan {
    let mut issues: Vec<String> = Vec::new();
    let vocab = vocabulary(root);
    let rows = crate::library::entry_rows(root);
    let mut counts: BTreeMap<String, i64> = BTreeMap::new();
    for (id, fm) in &rows {
        let rating = py_str(get(fm, "rating")).trim().to_string();
        if rating.is_empty() {
            issues.push(format!(
                "{} 缺 frontmatter `rating`（修复指引：取值为 {}；未定级写 unrated 而非留空——分级是消费方选择的前提）",
                id,
                vocab.join("/")
            ));
            continue;
        }
        if !vocab.contains(&rating) {
            issues.push(format!(
                "{} 的 rating 越词表：{}（允许：{}；词表真源 = {}）",
                id,
                rating,
                vocab.join("/"),
                INTAKE_REL
            ));
            continue;
        }
        *counts.entry(rating).or_insert(0) += 1;
    }

    // 声明面须在场（词表可声明，才谈得上「按声明判」）
    if root.join(INTAKE_REL).is_file() {
        let declared = crate::library::intake_doc(root)
            .map(|d| {
                crate::pyval::py_truthy(
                    get(&d, "rating").and_then(|r| get(r, "vocabulary")).unwrap_or(&Json::Null),
                )
            })
            .unwrap_or(false);
        if !declared {
            issues.push(format!(
                "{} 缺 rating.vocabulary 声明（修复指引：分级词表须成文，门禁按声明判而不写死）",
                INTAKE_REL
            ));
        }
    } else {
        issues.push(format!("缺 {}（修复指引：投稿闸门声明件须在场）", INTAKE_REL));
    }

    // Z3：把「声明在场」与「真被定级」拆成两个数（真源 scan 的口径）。
    // 未定级记号来自声明 rating.undecided，缺省 unrated。
    let tok = undecided_token(root);
    let n_unrated = *counts.get(&tok).unwrap_or(&0);
    let stats = Json::Object(vec![
        ("entries".to_string(), Json::Int(rows.len() as i64)),
        (
            "vocabulary".to_string(),
            Json::Array(vocab.into_iter().map(Json::Str).collect()),
        ),
        (
            "counts".to_string(),
            Json::Object(
                counts
                    .into_iter()
                    .map(|(k, v)| (k, Json::Int(v)))
                    .collect(),
            ),
        ),
        (
            "decided".to_string(),
            Json::Int(rows.len() as i64 - n_unrated),
        ),
        ("unrated".to_string(), Json::Int(n_unrated)),
        ("undecided_token".to_string(), Json::Str(tok)),
        ("issues".to_string(), Json::Int(issues.len() as i64)),
    ]);
    RatingScan { issues, stats }
}

/// 真源 `undecided_token`：「未定级」记号的声明真源（`rating.undecided`，缺省 `unrated`）。
pub fn undecided_token(root: &Path) -> String {
    crate::library::intake_doc(root)
        .and_then(|d| get(&d, "rating").and_then(|r| get(r, "undecided")).map(plain_str))
        .filter(|s| !s.is_empty())
        .unwrap_or_else(|| "unrated".to_string())
}

/// 真源 `decided` → `(issues, stats)`：内容**是否真被定级**（审计 Z3）。
///
/// `scan()` 判「声明在场且合词表」——显式 `unrated` 也算合格，于是覆盖率恒 100%；
/// 本判据判第二层：只声明未定级的件算不算数。策略真源 = `library/intake.json` 的
/// `rating.allow_unrated`（缺省 false ⇒ **fail-closed**）。
pub fn decided(root: &Path) -> RatingScan {
    let decl = crate::library::intake_doc(root).unwrap_or(Json::Object(vec![]));
    let allow = crate::pyval::py_truthy(
        get(&decl, "rating").and_then(|r| get(r, "allow_unrated")).unwrap_or(&Json::Null),
    );
    let tok = undecided_token(root);
    let rows = crate::library::entry_rows(root);
    let unrated_ids: Vec<String> = rows
        .iter()
        .filter(|(_, fm)| py_str(get(fm, "rating")).trim() == tok)
        .map(|(id, _)| id.clone())
        .collect();
    let mut issues: Vec<String> = Vec::new();
    if !unrated_ids.is_empty() && !allow {
        issues.push(format!(
            "馆藏 {} 件只声明「未定级」（{}）：{}（修复指引：给出真实分级；确需允许未定级，则在 {} 的 rating.allow_unrated=true 成文说明，不要用 100% 覆盖掩盖未定级）",
            unrated_ids.len(), tok,
            unrated_ids.iter().take(5).cloned().collect::<Vec<_>>().join("、"),
            INTAKE_REL
        ));
    }
    let stats = Json::Object(vec![
        ("entries".to_string(), Json::Int(rows.len() as i64)),
        ("decided".to_string(), Json::Int(rows.len() as i64 - unrated_ids.len() as i64)),
        ("unrated".to_string(), Json::Int(unrated_ids.len() as i64)),
        ("undecided_token".to_string(), Json::Str(tok)),
        ("allow_unrated".to_string(), Json::Bool(allow)),
    ]);
    RatingScan { issues, stats }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn vocabulary_falls_back_to_default_when_declaration_missing() {
        let tmp = crate::testutil::fixture("rating-vocab");
        assert_eq!(vocabulary(&tmp), DEFAULT_VOCAB.to_vec());
        let _ = std::fs::remove_dir_all(&tmp);
    }

    #[test]
    fn vocabulary_follows_the_declaration_not_a_hardcoded_list() {
        let tmp = crate::testutil::fixture("rating-vocab2");
        std::fs::create_dir_all(tmp.join("library")).unwrap();
        std::fs::write(
            tmp.join(INTAKE_REL),
            r#"{"rating": {"vocabulary": ["alpha", "beta"]}}"#.as_bytes(),
        )
        .unwrap();
        assert_eq!(vocabulary(&tmp), vec!["alpha".to_string(), "beta".to_string()]);
        let _ = std::fs::remove_dir_all(&tmp);
    }
    /// ===== 分支级差分判据（期望值由 `tools/gen_rating_branches.py` 从真源生成）=====
    ///
    /// 三个场景：声明齐（rating.vocabulary 成文）/ 声明在但缺 rating.vocabulary / 声明件缺失。
    /// 每场景都踩：缺 `rating` 字段 / rating 越词表 / rating 合法（计数）。
    const RATING_ENTRIES: [(&str, &str); 3] = [
        ("NF-1.md", "---\nid: NF-1\ntype: t\ntitle: A\n---\n正文\n"),
        ("NF-2.md", "---\nid: NF-2\ntype: t\ntitle: B\nrating: bogus\n---\n正文\n"),
        ("NF-3.md", "---\nid: NF-3\ntype: t\ntitle: C\nrating: teen\n---\n正文\n"),
    ];

    fn build_rating_fixture(scenario: &str, decl: Option<&str>) -> std::path::PathBuf {
        let root = crate::testutil::fixture(&format!("rating-branches-{}", scenario));
        std::fs::create_dir_all(root.join("library")).unwrap();
        if let Some(d) = decl {
            std::fs::write(root.join("library/intake.json"), d).unwrap();
        }
        for (name, body) in RATING_ENTRIES {
            std::fs::write(root.join("library").join(name), body).unwrap();
        }
        root
    }

    #[test]
    fn scan_matches_truth_source_in_all_three_declaration_states() {
        for (scenario, decl, want_issues, want_vocab, want_counts) in [
            (
                "withvocab",
                Some(r#"{"rating": {"vocabulary": ["general", "teen", "unrated"]}}"#),
                &["NF-1 缺 frontmatter `rating`（修复指引：取值为 general/teen/unrated；未定级写 unrated 而非留空——分级是消费方选择的前提）", "NF-2 的 rating 越词表：bogus（允许：general/teen/unrated；词表真源 = library/intake.json）"] as &[&str],
                &["general", "teen", "unrated"] as &[&str],
                &[("teen", 1i64)] as &[(&str, i64)],
            ),
            (
                "novocab",
                Some(r#"{"rating": {}}"#),
                &["NF-1 缺 frontmatter `rating`（修复指引：取值为 general/teen/mature/unrated；未定级写 unrated 而非留空——分级是消费方选择的前提）", "NF-2 的 rating 越词表：bogus（允许：general/teen/mature/unrated；词表真源 = library/intake.json）", "library/intake.json 缺 rating.vocabulary 声明（修复指引：分级词表须成文，门禁按声明判而不写死）"] as &[&str],
                &["general", "teen", "mature", "unrated"] as &[&str],
                &[("teen", 1i64)] as &[(&str, i64)],
            ),
            ("nodecl", None, &["NF-1 缺 frontmatter `rating`（修复指引：取值为 general/teen/mature/unrated；未定级写 unrated 而非留空——分级是消费方选择的前提）", "NF-2 的 rating 越词表：bogus（允许：general/teen/mature/unrated；词表真源 = library/intake.json）", "缺 library/intake.json（修复指引：投稿闸门声明件须在场）"] as &[&str], &["general", "teen", "mature", "unrated"] as &[&str], &[("teen", 1i64)] as &[(&str, i64)]),
        ] {
            let root = build_rating_fixture(scenario, decl);
            let got = scan(&root);
            assert_eq!(got.issues, want_issues, "场景 {} 的 issues", scenario);
            let want = crate::pyjson::Json::Object(vec![
                (
                    "entries".to_string(),
                    crate::pyjson::Json::Int(3),
                ),
                (
                    "vocabulary".to_string(),
                    crate::pyjson::Json::Array(
                        want_vocab.iter().map(|s| crate::pyjson::Json::Str((*s).to_string())).collect(),
                    ),
                ),
                (
                    "counts".to_string(),
                    crate::pyjson::Json::Object(
                        want_counts
                            .iter()
                            .map(|(k, v)| ((*k).to_string(), crate::pyjson::Json::Int(*v)))
                            .collect(),
                    ),
                ),
                // Z3 追加口径（真源 scan 的 stats 同形）：3 件里 0 件只声明 unrated ⇒ decided=3。
                ("decided".to_string(), crate::pyjson::Json::Int(3)),
                ("unrated".to_string(), crate::pyjson::Json::Int(0)),
                (
                    "undecided_token".to_string(),
                    crate::pyjson::Json::Str("unrated".to_string()),
                ),
                (
                    "issues".to_string(),
                    crate::pyjson::Json::Int(want_issues.len() as i64),
                ),
            ]);
            assert!(
                crate::jsonread::json_eq(&got.stats, &want),
                "场景 {} 的 stats：实得 {:?}",
                scenario,
                got.stats
            );
        }
    }


    /// 真源 `decided` 的策略分支（台账 Z3：声明在场 ≠ 真被定级）。
    ///
    /// 覆盖 `allow_unrated` 缺省（fail-closed）/ 显式放行 / 自定义 undecided 记号 / 缺字段不计数。
    fn decided_fixture(decl: Option<&str>, entries: &[(&str, Option<&str>)]) -> std::path::PathBuf {
        let root = crate::testutil::fixture("rating-decided-rt");
        std::fs::create_dir_all(root.join("library")).unwrap();
        if let Some(d) = decl {
            std::fs::write(root.join("library/intake.json"), d).unwrap();
        }
        for (id, rating) in entries {
            let mut s = format!("---\nid: {}\ntype: t\ntitle: {}\n", id, id);
            if let Some(r) = rating {
                s.push_str(&format!("rating: {}\n", r));
            }
            s.push_str("---\n正文\n");
            std::fs::write(root.join("library").join(format!("NF-{}.md", id)), s).unwrap();
        }
        root
    }

    #[test]
    fn decided_policy_branches() {
        // ① fail-closed：两件 unrated、未声明 allow ⇒ 必报 1 条
        let r = decided_fixture(None, &[("1", Some("general")), ("2", Some("unrated")), ("3", Some("unrated"))]);
        let got = decided(&r);
        assert_eq!(got.issues.len(), 1, "缺省 fail-closed 应报一条：{:?}", got.issues);
        assert!(got.issues[0].contains("只声明「未定级」"), "文案：{}", got.issues[0]);
        // `dumps_default` 是 CPython 默认分隔符（", " / ": "，带空格）
        assert!(
            got.stats.dumps_default().contains("\"unrated\": 2"),
            "{}",
            got.stats.dumps_default()
        );
        let _ = std::fs::remove_dir_all(&r);

        // ② 显式 allow_unrated=true ⇒ 放行
        let r = decided_fixture(Some("{\"rating\": {\"allow_unrated\": true}}"),
                                &[("1", Some("general")), ("2", Some("unrated"))]);
        assert!(decided(&r).issues.is_empty(), "显式放行时不该报");
        let _ = std::fs::remove_dir_all(&r);

        // ③ 自定义 undecided 记号跟随声明
        let r = decided_fixture(Some("{\"rating\": {\"undecided\": \"pending\"}}"),
                                &[("1", Some("pending")), ("2", Some("general"))]);
        let got = decided(&r);
        assert_eq!(got.issues.len(), 1, "自定义记号应被判为未定级：{:?}", got.issues);
        assert!(got.issues[0].contains("pending"), "{}", got.issues[0]);
        let _ = std::fs::remove_dir_all(&r);

        // ④ 缺 rating 字段不归 decided 管（两层判据必须可分）
        let r = decided_fixture(Some("{\"rating\": {}}"), &[("1", None)]);
        assert!(decided(&r).issues.is_empty(), "缺字段不归 decided 管");
        assert!(scan(&r).issues.iter().any(|i| i.contains("缺 frontmatter")), "scan 应报缺字段");
        let _ = std::fs::remove_dir_all(&r);
    }
}
