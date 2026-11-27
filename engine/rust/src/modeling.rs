//! 内容建模三件门禁（`modeling`）—— 与真源 `desktop/src/core/modeling.py` 对账。
//!
//! 三件：**词表登记册**（每个 scheme 的 probe 必须回指真源且逐项一致）/ **规范与说明件之分**
//! （两份名单交集为空；规范件须被回执锚定或显式 `covered_by`；说明件不得进回执覆盖面）/
//! **数据契约登记**（artifact 在场、quality_rule 解析到真实 checkN 或 assertion:<id>）。
//!
//! `python_attr` 探针走 [`crate::pyconsts`]（转录的真源常量；未登记即报"真源取不到"）。

use crate::jsonread;
use crate::pyconsts;
use crate::pyjson::Json;
use crate::pyval::{arr_items, get, plain_str, plain_str_opt, py_str};
use std::collections::BTreeSet;
use std::path::Path;

mod part1;
mod part2;

pub(crate) use part1::*;
pub(crate) use part2::*;

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn missing_declarations_are_reported_in_scan_order() {
        let tmp = crate::testutil::fixture("modeling-missing");
        let got = scan(&tmp);
        assert_eq!(got.issues.len(), 3, "三件各报一条：{:?}", got.issues);
        assert!(got.issues[0].contains("缺词表登记册"));
        assert!(got.issues[1].contains("缺规范/说明件名单"));
        assert!(got.issues[2].contains("缺数据契约登记"));
        let _ = std::fs::remove_dir_all(&tmp);
    }

    #[test]
    fn informative_double_star_is_appended_not_replaced() {
        // 真源 `g + "/*"`：`docs/**` → `docs/**/*`（递归）。抄成 `docs/*` 会只数直接子级，
        // 而 ok/not-ok 不会变——只错一个计数（实测：2352 → 75）。
        let tmp = crate::testutil::fixture("modeling-informative");
        std::fs::create_dir_all(tmp.join("protocol")).unwrap();
        std::fs::create_dir_all(tmp.join("docs/sub")).unwrap();
        std::fs::write(tmp.join("docs/a.md"), "x").unwrap();
        std::fs::write(tmp.join("docs/sub/b.md"), "x").unwrap();
        std::fs::write(
            tmp.join(NORM_REL),
            r#"{"schema": "nf-normative/1", "normative": [], "informative": ["docs/**"]}"#
                .as_bytes(),
        )
        .unwrap();
        let got = scan(&tmp);
        assert_eq!(
            got.informative_files, 2,
            "`docs/**` 必须递归命中子目录（a.md + sub/b.md）"
        );
        let _ = std::fs::remove_dir_all(&tmp);
    }

    #[test]
    fn python_attr_probe_uses_the_transcribed_registry() {
        let pr: Json = jsonread::convert(&serde_json::json!({
            "kind": "python_attr", "module": "core.doc_hygiene", "attr": "KINDS"
        }))
        .unwrap();
        let (vals, note) = probe(Path::new("."), &pr);
        assert_eq!(note, "python_attr");
        assert_eq!(vals, vec!["tutorial", "how-to", "reference", "explanation"]);
        // 未登记的常量必须报"取不到"，不得冒充一致
        let pr2: Json = jsonread::convert(&serde_json::json!({
            "kind": "python_attr", "module": "core.nope", "attr": "X"
        }))
        .unwrap();
        let (v2, n2) = probe(Path::new("."), &pr2);
        assert!(v2.is_empty());
        assert!(n2.contains("未登记"), "got: {}", n2);
    }

    #[test]
    fn as_values_mirrors_truth_source() {
        let obj = jsonread::convert(&serde_json::json!({"b": 1, "a": 2})).unwrap();
        let mut got = as_values(&obj);
        got.sort();
        assert_eq!(got, vec!["a", "b"]);
        let arr = jsonread::convert(&serde_json::json!(["x", "y"])).unwrap();
        assert_eq!(as_values(&arr), vec!["x", "y"]);
    }
    /// ===== 分支级差分判据（期望值由 `tools/gen_modeling_branches.py` 从真源生成）=====
    ///
    /// 真语料上 `modeling` 三件全绿 ⇒ 只靠契约对账核不到错误分支。本夹具逐分支踩：
    /// 词表（schema / status 词表 / id 重复 / 值不足 / 值重复 / alias 撞车 / probe.kind 不在册 /
    /// json_path 断链 / 真源漂移 / python_attr 已登记与未登记）、规范件（缺 path / 不存在 /
    /// 无锚定 / covered_by 指向不存在 check / 合法 / 与说明件重叠 / 说明面未命中）、
    /// 数据契约（schema / rule_prefixes / id 重复 / artifact 缺 / status 越词表 / 缺 owner /
    /// 缺 freshness / 规则指向不存在 check / 指向不存在断言 / 无法解析 / 合法）。
    const WANT_MD_ISSUES: [&str; 27] = [
        "词表登记册 schema 不匹配（期望 nf-vocabularies/1）",
        "status 词表与判据不一致（期望 active/deprecated）",
        "词表 id 重复：v-literal",
        "词表 v-literal 少于两个值（不成词表）",
        "词表 v-status status 越词表：bogus",
        "词表 v-dup 值重复",
        "词表 v-dup 的 alias 与值撞车：a",
        "词表 v-kind 的 probe.kind 不在册：nope",
        "词表 v-broken 的真源取不到（json_path 断链：nope.deep）",
        "词表 v-drift 与真源漂移：册=x/y 真源=x/z",
        "词表 v-attr status 越词表：deprecated",
        "规范件名单 schema 不匹配（期望 nf-normative/1）",
        "规范件条目缺 path",
        "规范件不存在：docs/missing.md",
        "规范件既未被回执锚定也无 covered_by：docs/norm-a.md（修复指引：跑 nf receipts --write，或显式声明 covered_by）",
        "规范件 docs/norm-a.md 的 covered_by 指向不存在的 check：check99",
        "规范件既未被回执锚定也无 covered_by：docs/ex/one.md（修复指引：跑 nf receipts --write，或显式声明 covered_by）",
        "同一件既列规范又列说明：docs/ex/one.md",
        "数据契约登记 schema 不匹配（期望 nf-data-contracts/1）",
        "rule_prefixes 与判据不一致（期望 check / assertion:）",
        "契约 id 重复：c1",
        "契约 c1 的 artifact 不存在：no/such",
        "契约 c1 status 越词表：bogus",
        "契约 c1 缺 owner（无人认领的契约不许登记）",
        "契约 c1 缺 freshness（重建动作必须写明）",
        "契约 c1 的 quality_rule 指向不存在的断言：assertion:nope",
        "契约 c3 的 quality_rule 无法解析（须 checkN 或 assertion:<id>）：不能解析",
    ];

    fn build_modeling_fixture() -> std::path::PathBuf {
        let root = crate::testutil::fixture("modeling-branches");
        for rel in ["protocol", "protocol/schema", "docs", "docs/ex", "library"] {
            std::fs::create_dir_all(root.join(rel)).unwrap();
        }
        for (rel, body) in [
            (
                "docs/ex/one.md",
                r#"# one
"#,
            ),
            (
                "docs/ex/two.md",
                r#"# two
"#,
            ),
            (
                "docs/norm-a.md",
                r#"# a
"#,
            ),
            (
                "docs/norm-b.md",
                r#"# b
"#,
            ),
            (
                "protocol/RECEIPTS.json",
                r#"{"schema": "nf-receipts/1", "entries": [{"id": "docs/norm-b.md"}]}"#,
            ),
            (
                "protocol/assertions.json",
                r#"{"assertions": [{"id": "a1"}]}"#,
            ),
            (
                "protocol/data_contracts.json",
                r#"{"schema": "wrong/1", "status_vocabulary": ["active"], "rule_prefixes": ["check"], "contracts": [{"id": "c1", "artifact": "docs/norm-a.md", "status": "active", "owner": "o", "freshness": "f", "quality_rule": "check1"}, {"id": "c1", "artifact": "no/such", "status": "bogus", "owner": "", "freshness": "", "quality_rule": "assertion:nope"}, {"id": "c3", "artifact": "docs/norm-a.md", "status": "active", "owner": "o", "freshness": "f", "quality_rule": "不能解析"}, {"id": "c4", "artifact": "docs/norm-b.md", "status": "active", "owner": "o", "freshness": "f", "quality_rule": "assertion:a1"}]}"#,
            ),
            (
                "protocol/normative.json",
                r#"{"schema": "wrong/1", "normative": [{"path": ""}, "docs/missing.md", {"path": "docs/norm-a.md"}, {"path": "docs/norm-a.md", "covered_by": ["check99"]}, {"path": "docs/norm-b.md", "covered_by": ["check1"]}, {"path": "docs/ex/one.md"}], "informative": ["docs/ex/**", "docs/none/**"]}"#,
            ),
            ("protocol/other.json", r#"{"words": ["x", "z"]}"#),
            (
                "protocol/vocabularies.json",
                r#"{"schema": "wrong/1", "status_vocabulary": ["active"], "probe_kinds": ["literal", "json_path", "python_attr"], "schemes": [{"id": "v-literal", "status": "active", "values": ["a", "b"], "probe": {"kind": "literal"}}, {"id": "v-literal", "status": "active", "values": ["a"], "probe": {"kind": "literal"}}, {"id": "v-status", "status": "bogus", "values": ["a", "b"], "probe": {"kind": "literal"}}, {"id": "v-dup", "status": "active", "values": ["a", "a"], "aliases": ["a"], "probe": {"kind": "literal"}}, {"id": "v-kind", "status": "active", "values": ["a", "b"], "probe": {"kind": "nope"}}, {"id": "v-broken", "status": "active", "values": ["a", "b"], "probe": {"kind": "json_path", "file": "protocol/other.json", "path": "nope.deep"}}, {"id": "v-drift", "status": "active", "values": ["x", "y"], "probe": {"kind": "json_path", "file": "protocol/other.json", "path": "words"}}, {"id": "v-attr", "status": "deprecated", "values": ["tutorial", "how-to", "reference", "explanation"], "probe": {"kind": "python_attr", "module": "core.doc_hygiene", "attr": "KINDS"}}]}"#,
            ),
            (
                "verify.sh",
                r#"#!/bin/bash
check1(){
  true
}
check2(){
  true
}
"#,
            ),
        ] {
            std::fs::write(root.join(rel), body).unwrap();
        }
        root
    }

    #[test]
    fn scan_matches_truth_source_branch_by_branch() {
        let root = build_modeling_fixture();
        let got = scan(&root);
        assert_eq!(got.issues, WANT_MD_ISSUES, "逐条消息与次序都须与真源一致");
        assert_eq!(got.schemes, 7);
        assert_eq!(got.normative, 6);
        assert_eq!(got.informative_files, 2);
        assert_eq!(got.contracts, 3);
    }
}
