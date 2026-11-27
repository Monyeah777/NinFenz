//! 契约测试（非生成块）：分派面 / ST / pyval 语义 / 断言数据化 / RFC 头 / 认知族夹具。
//!
//! 自 `contracts.rs` 的 `mod tests` 平移；生成块仍留在 `contracts.rs`（生成器按该路径回写）。

use super::*;

use crate::jsonread;
use crate::pyjson::Json;
use crate::pyval::{plain_str, py_eq, py_str, py_truthy, str_list};
use std::path::Path;
use std::path::PathBuf;

fn fixture(name: &str) -> PathBuf {
    crate::testutil::fixture(name)
}

/// 原判据断言 `purity-clean` **未分派**（当时它是"显式缺席"的例子）。**2026-10-04：27/27
/// 全部移植**，该断言自然失效——但 ADR-0005 的两半都要守，故改写成两个方向：
/// ① **未知 id 必须显式缺席**（不许伪造结论）；② **在册的 27 条都必须真有分派**
/// （防止"登记了却没接线"这种反方向的缺口）。
///
/// 分派检查跑在**空夹具根**上：各判据在缺件时都快速返回，故这条判据是廉价的。
#[test]
fn unknown_contract_is_absent_and_every_registered_one_is_dispatched() {
    // ① 未知 id：显式缺席
    assert!(run("no-such-contract", Path::new(".")).is_none());
    assert!(description("no-such-contract").is_none());
    // ② 在册 27 条：有说明、且有分派
    let empty = fixture("all-ported");
    for id in PORTED {
        assert!(description(id).is_some(), "契约 {} 缺说明登记", id);
        assert!(run(id, &empty).is_some(), "契约 {} 登记了却缺分派", id);
    }
}

#[test]
fn st_quality_on_missing_file_reports_missing_declaration() {
    let tmp = fixture("st-missing");
    let _ = std::fs::create_dir_all(&tmp);
    let (ok, detail) = run("st-quality", &tmp).unwrap();
    assert!(!ok);
    assert!(detail.contains("缺 ST 制卡质量规范"), "got: {}", detail);
}

#[test]
fn py_str_mirrors_python_falsy_rule() {
    assert_eq!(py_str(None), "");
    assert_eq!(py_str(Some(&Json::Null)), "");
    assert_eq!(py_str(Some(&Json::Int(0))), "");
    assert_eq!(py_str(Some(&Json::Bool(false))), "");
    assert_eq!(py_str(Some(&Json::Bool(true))), "True");
    assert_eq!(py_str(Some(&Json::Str("x".into()))), "x");
    assert_eq!(py_str(Some(&Json::Int(7))), "7");
}

#[test]
fn str_list_treats_missing_as_empty() {
    assert!(str_list(None).is_empty());
    assert_eq!(
        str_list(Some(&Json::Array(vec![
            Json::Str("M".into()),
            Json::Str("S".into())
        ]))),
        vec!["M".to_string(), "S".to_string()]
    );
}

#[test]
fn empty_object_is_treated_as_missing_declaration() {
    let tmp = fixture("st-empty");
    let _ = std::fs::remove_dir_all(&tmp);
    std::fs::create_dir_all(tmp.join("protocol")).expect("建夹具目录");
    std::fs::write(tmp.join(ST_REL), b"{}").expect("写夹具文件");
    let (ok, detail) = run("st-quality", &tmp).unwrap();
    assert!(!ok);
    assert!(detail.contains("缺 ST 制卡质量规范"), "got: {}", detail);
    let _ = std::fs::remove_dir_all(&tmp);
}

#[test]
fn ported_contracts_are_exactly_the_declared_list() {
    for id in PORTED {
        assert!(description(id).is_some(), "{} 缺 description 登记", id);
        assert!(run(id, Path::new(".")).is_some(), "{} 缺 run 分派", id);
    }
    // 冻结数：**故意**留的摩擦——新增契约时必须回来改这一行，顺带检查登记齐全。
    assert_eq!(PORTED.len(), 27);
}

#[test]
fn assertion_kinds_discriminate() {
    // regex_absent：命中即不通过（判别力自证）
    let tmp = fixture("as-regex-absent");
    let _ = std::fs::remove_dir_all(&tmp);
    std::fs::create_dir_all(tmp.join("d")).unwrap();
    std::fs::write(tmp.join("d/x.md"), "C:\\tmp\\leak").unwrap();
    let params: Json = jsonread::convert(&serde_json::json!({
        "globs": ["d/*.md"], "pattern": "(?<![A-Za-z0-9])[A-Za-z]:[\\\\/]"
    }))
    .unwrap();
    let (ok, detail) = k_regex_absent(&tmp, &params);
    assert!(!ok, "命中绝对路径时必须判红");
    assert!(detail.starts_with("命中："), "got: {}", detail);

    // 该模式若用 Rust regex（不支持后顾）会编译失败——故必须走 fancy-regex。
    let clean = fixture("as-regex-clean");
    let _ = std::fs::remove_dir_all(&clean);
    std::fs::create_dir_all(clean.join("d")).unwrap();
    std::fs::write(clean.join("d/x.md"), "relative/path/only").unwrap();
    let (ok2, detail2) = k_regex_absent(&clean, &params);
    assert!(ok2, "零命中应通过；got: {}", detail2);
    assert_eq!(detail2, "零命中");

    // count_at_least：0 是假值 → min 落 0（真源 `int(x or 0)`）
    let p2: Json = jsonread::convert(&serde_json::json!({"glob": "d/*.md", "min": 0})).unwrap();
    assert!(k_count_at_least(&clean, &p2).0);
    let p3: Json = jsonread::convert(&serde_json::json!({"glob": "d/*.md", "min": 2})).unwrap();
    assert!(!k_count_at_least(&clean, &p3).0);

    // regex_present：缺锚点要指名
    std::fs::write(clean.join("t.txt"), "alpha beta").unwrap();
    let p4: Json = jsonread::convert(
        &serde_json::json!({"path": "t.txt", "patterns": ["alpha", "gamma"]}),
    )
    .unwrap();
    let (ok4, d4) = k_regex_present(&clean, &p4);
    assert!(!ok4);
    assert_eq!(d4, "缺：gamma");

    // json_value：equals / contains_keys / 未知 op
    std::fs::write(
        clean.join("j.json"),
        br#"{"a": {"b": 2}, "flags": {"f": false}}"#,
    )
    .unwrap();
    let p5: Json = jsonread::convert(
        &serde_json::json!({"path": "j.json", "key": "a.b", "op": "equals", "value": 2}),
    )
    .unwrap();
    assert!(k_json_value(&clean, &p5).0, "a.b 应等于 2");
    let p6: Json = jsonread::convert(
        &serde_json::json!({"path": "j.json", "key": "flags.f", "op": "equals", "value": false}),
    )
    .unwrap();
    assert!(k_json_value(&clean, &p6).0, "布尔 false 应相等");
    let p7: Json = jsonread::convert(
        &serde_json::json!({"path": "j.json", "key": "a", "op": "contains_keys", "value": ["b", "z"]}),
    )
    .unwrap();
    let (ok7, d7) = k_json_value(&clean, &p7);
    assert!(!ok7);
    assert_eq!(d7, "缺：z");
    let p8: Json =
        jsonread::convert(&serde_json::json!({"path": "j.json", "key": "a", "op": "nope"}))
            .unwrap();
    assert!(!k_json_value(&clean, &p8).0);

    let _ = std::fs::remove_dir_all(&tmp);
    let _ = std::fs::remove_dir_all(&clean);
}

#[test]
fn py_truthy_and_py_eq_follow_python_rules() {
    assert!(!py_truthy(&Json::Null));
    assert!(!py_truthy(&Json::Int(0)));
    assert!(!py_truthy(&Json::Str(String::new())));
    assert!(!py_truthy(&Json::Array(vec![])));
    assert!(py_truthy(&Json::Int(1)));
    assert!(py_eq(&Json::Bool(true), &Json::Int(1)), "Python True == 1");
    assert!(py_eq(&Json::Int(1), &Json::Bool(true)));
}

#[test]
fn canonical_determinism_is_key_order_independent() {
    let (ok, detail) = run("canonical-digest-determinism", Path::new(".")).unwrap();
    assert!(ok);
    assert_eq!(detail, "canonical digest 两遍一致");
}

// ------------------------------------------------------------ rfc-heads

const RFC_SAMPLE: &str = "> **RFC**: NF-0001 · **Category**: Standards Track · **Date**: 2026-09-08 ·\n  **Status**: Active · **Supersedes**: — · **Superseded by**: —\n\n> 最后更新：2026-09-08\n";

#[test]
fn rfc_head_parser_extracts_all_six_fields() {
    let h = parse_head(RFC_SAMPLE).expect("样例头应可解析");
    assert_eq!(h.rfc, "NF-0001");
    assert_eq!(h.cat, "Standards Track");
    assert_eq!(h.date, "2026-09-08");
    assert_eq!(h.status, "Active");
    assert_eq!(h.supby, "—");
    assert_eq!(h.last_updated, "2026-09-08");
}

#[test]
fn rfc_head_parser_only_looks_at_first_eight_lines() {
    let mut text = String::new();
    for _ in 0..9 {
        text.push_str("填充行\n");
    }
    text.push_str(RFC_SAMPLE);
    assert!(parse_head(&text).is_none(), "第 9 行之后的头不得被采纳");
}

#[test]
fn rfc_chain_cycle_is_detected() {
    let tmp = fixture("rfc-cycle");
    let _ = std::fs::remove_dir_all(&tmp);
    std::fs::create_dir_all(tmp.join("protocol")).unwrap();
    std::fs::create_dir_all(tmp.join("d")).unwrap();
    for (n, supby) in [("0001", "NF-0002"), ("0002", "NF-0001")] {
        std::fs::write(
            tmp.join(format!("d/{}.md", n)),
            format!(
                "> **RFC**: NF-{} · **Category**: Process · **Date**: 2026-01-01 ·\n  **Status**: Active · **Supersedes**: — · **Superseded by**: {}\n",
                n, supby
            ),
        )
        .unwrap();
    }
    std::fs::write(
        tmp.join(RFC_INDEX_REL),
        br#"{"status_vocabulary": ["Active"], "docs": [
             {"path": "d/0001.md", "rfc": "NF-0001"},
             {"path": "d/0002.md", "rfc": "NF-0002"}]}"#,
    )
    .unwrap();
    let (ok, detail) = run("rfc-heads", &tmp).unwrap();
    assert!(!ok);
    assert!(detail.contains("成环"), "got: {}", detail);
    let _ = std::fs::remove_dir_all(&tmp);
}

// ------------------------------------------------------------ cognition

#[test]
fn plain_str_differs_from_py_str_on_falsy_values() {
    assert_eq!(plain_str(&Json::Null), "None");
    assert_eq!(plain_str(&Json::Bool(false)), "False");
    assert_eq!(plain_str(&Json::Int(0)), "0");
    assert_eq!(py_str(Some(&Json::Null)), "");
    assert_eq!(py_str(Some(&Json::Bool(false))), "");
    assert_eq!(py_str(Some(&Json::Int(0))), "");
}

/// cognition 契约**同时**扫术语表与执行分档；只给一半的夹具会被另一半判红。
fn write_modes_fixture(tmp: &Path) {
    std::fs::write(
        tmp.join(MODES_REL),
        br#"{"schema": "nf-execution-modes/1", "modes": []}"#,
    )
    .unwrap();
}

#[test]
fn cognition_flags_term_missing_from_its_source() {
    let tmp = fixture("cog-glossary");
    let _ = std::fs::remove_dir_all(&tmp);
    std::fs::create_dir_all(tmp.join("protocol")).unwrap();
    std::fs::write(tmp.join("src.md"), "这里没有那个术语\n").unwrap();
    std::fs::write(
        tmp.join(GLOSSARY_REL),
        br#"{"schema": "nf-glossary/1", "rules": ["r"],
             "terms": [{"term": "X", "definition": "d", "source": "src.md"}]}"#,
    )
    .unwrap();
    write_modes_fixture(&tmp);
    let (ok, detail) = run("cognition", &tmp).unwrap();
    assert!(!ok, "术语不在其 source 中逐字出现时必须判红");
    assert!(
        detail.contains("未在其 source 中逐字出现"),
        "got: {}",
        detail
    );
    let _ = std::fs::remove_dir_all(&tmp);
}

#[test]
fn cognition_empty_string_used_in_is_falsy_not_a_path() {
    // 真源 `t.get("used_in") or []`：空串按假值落空表，**不得**当成「一项空路径」
    let tmp = fixture("cog-empty-usedin");
    let _ = std::fs::remove_dir_all(&tmp);
    std::fs::create_dir_all(tmp.join("protocol")).unwrap();
    std::fs::write(tmp.join("src.md"), "X 在此\n").unwrap();
    std::fs::write(
        tmp.join(GLOSSARY_REL),
        br#"{"schema": "nf-glossary/1", "rules": ["r"],
             "terms": [{"term": "X", "definition": "d", "source": "src.md", "used_in": ""}]}"#,
    )
    .unwrap();
    write_modes_fixture(&tmp);
    let (ok, detail) = run("cognition", &tmp).unwrap();
    assert!(ok, "空串 used_in 应被当作空表；实际判红：{}", detail);
    let _ = std::fs::remove_dir_all(&tmp);
}
