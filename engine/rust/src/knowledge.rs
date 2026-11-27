//! 双源知识层（`knowledge`）—— 与真源 `desktop/src/core/knowledge.py` 的 `scan` 对账。
//!
//! 判据：声明 schema / 三套词表逐项一致；每个源必填齐、id 唯一、词表在册、`locator` **真实存在**
//!（防纸面源）；**reference 级**须是 external-retrieval + 要求标注来源 + 时效策略取 `ttl`/`no-cache`
//!（且 `ttl` 时 `ttl_days` 为正整数）；**contract 级**须是 local-compiled + 不要求外部标注 + 时效取
//! `stale_after`；`query_order` 须与 sources 同集合且**合同级全部排在参考级之前**；晋升/审核/认知
//! 三段规则成文；`cognition.filter_module` 须指向在册模块；消化记录在场且 schema 匹配。
//!
//! **移植范围**：只做 `scan`。同模块的 `verify_transform` / `verify_usage` / `verify_reuse` /
//! `harvest_frequency` / `write_*` 是另几条判据与写面，不在 `verify_report` 的判据表里。
//!
//! **已知近似（fail-closed）**：真源 `_read_json` **不吞解析异常**——声明件坏 JSON 会让整条判据
//! 记 `error`。本线照样如实记 `error`（而不是当作空声明往下走，那会把 error 悄悄降级成一堆
//! 看起来正常的字段缺失 issue）。
//!
//! 本模块是 `nf verify-report` 的 `knowledge` 判据，**不单独开 CLI 面**。

use crate::jsonread;
use crate::pyjson::Json;
use crate::pyval::{arr_items, get, py_str, py_truthy};
use std::collections::BTreeSet;
use std::path::Path;

mod part1;
mod part2;

pub(crate) use part1::*;
pub(crate) use part2::*;

#[cfg(test)]
mod tests {
    use super::*;

    /// 真源在真语料上是**全绿**的（0 issues）⇒ 只靠契约对账**核不到错误路径**。
    /// 本判据构造一个逐条踩分支的夹具，期望值由 `tools/gen_knowledge_expected.py`
    /// 从真源生成（勿手改）——这样每条消息的措辞都真的被核过。
    /// 第 5 条是**全绿样本**：证明这套判据不是空转。
    const WANT_TRANSFORM: [&str; 14] = [
            "记录 #1 非对象",
            "记录 #2 缺必填字段：from",
            "记录 #2 缺必填字段：to",
            "记录 #2 缺必填字段：digest",
            "记录 #2 缺必填字段：reviewed_by",
            "记录 #2 缺必填字段：reviewed_at",
            "记录 #2 缺必填字段：evidence",
            "记录 #3 的 from 不是已声明的参考级源：ghost",
            "记录 #3 的产物不存在：no/such.md",
            "记录 #3 声明转正但缺证据档：machine-checkable/reproducible/externally-attestable",
            "记录 #3 的 reuse_count 非非负整数（频次判据不可复算）",
            "记录 #4 的产物摘要与记录不一致：protocol/LAYERS.json（产物已改，记录失效；修复指引：重新消化并更新 digest）",
            "记录 #4 声明转正但缺证据档：machine-checkable/reproducible/externally-attestable",
            "记录 #4 声明转正但无复核人（消化审核未双签）",
    ];
    const WANT_USAGE: [&str; 6] = [
            "频率台账 schema 不匹配（期望 nf-knowledge-usage/1）",
            "频率台账含未声明的源：ghost-source（防幽灵频次）",
            "频率计数非非负整数：ext-x",
            "频率台账 total 与 counts 求和不一致（手改痕迹）",
            "频次不可复算：ghost 的记录 reuse_count=-1，频率台账=None（修复指引：按 trace 重算，不要手写频次）",
            "频次不可复算：ext-x 的记录 reuse_count=4，频率台账=-1（修复指引：按 trace 重算，不要手写频次）",
    ];

    static LOG_HEAD: std::sync::OnceLock<serde_json::Value> = std::sync::OnceLock::new();
    fn log_head() -> &'static serde_json::Value {
        LOG_HEAD.get_or_init(|| serde_json::from_str(r#"{"schema": "nf-transform-log/1", "entries": ["不是对象", {}, {"from": "ghost", "to": "no/such.md", "digest": "x", "reviewed_by": "a", "reviewed_at": "2026-13-99", "evidence": [], "reuse_count": -1, "promoted": true}, {"from": "ext-x", "to": "protocol/LAYERS.json", "digest": "deadbeef", "reviewed_by": "  ", "reviewed_at": "2026-01-01", "evidence": [], "promoted": true}]}"#).unwrap())
    }

    fn build_fixture() -> std::path::PathBuf {
        let root = crate::testutil::fixture("knowledge-branches");
        std::fs::create_dir_all(root.join("protocol")).unwrap();
        std::fs::write(root.join("protocol/LAYERS.json"), "{}").unwrap();
        let real = crate::merkle::hex(&crate::merkle::sha256(b"{}"));
        std::fs::write(root.join("protocol/knowledge_sources.json"), r#"{"schema": "nf-knowledge-sources/1", "authority_vocabulary": ["contract", "reference"], "kind_vocabulary": ["local-compiled", "external-retrieval"], "visibility_vocabulary": ["public", "internal", "restricted"], "sources": [{"id": "nf-protocol", "authority": "contract", "kind": "local-compiled", "locator": "protocol/LAYERS.json", "requires_source_label": false, "visibility": "public", "freshness": {"policy": "stale_after"}}, {"id": "ext-x", "authority": "reference", "kind": "external-retrieval", "locator": "protocol/LAYERS.json", "requires_source_label": true, "visibility": "public", "freshness": {"policy": "ttl", "ttl_days": 7}}], "query_order": ["nf-protocol", "ext-x"], "promotion": {"evidence_tiers": ["machine-checkable", "reproducible", "externally-attestable"], "triggers": ["reuse-frequency", "author-mark", "machine-check-pass"], "rule": "r", "on_missing_evidence": "stay-reference"}, "review": {"machine_gates": ["g"], "rule": "r"}, "cognition": {"filter_module": "M23"}}"#).unwrap();
        let mut log = log_head().clone();
        if let Some(serde_json::Value::Array(a)) = log.get_mut("entries") {
            a.push(serde_json::json!({
                "from": "ext-x", "to": "protocol/LAYERS.json", "digest": real,
                "reviewed_by": "张三", "reviewed_at": "2026-01-01",
                "evidence": ["machine-checkable", "reproducible", "externally-attestable"],
                "promoted": true, "reuse_count": 4
            }));
        }
        std::fs::write(root.join("protocol/transform_log.json"), log.to_string()).unwrap();
        std::fs::write(root.join("protocol/knowledge_usage.json"), r#"{"schema": "wrong/1", "counts": {"ghost-source": 3, "ext-x": -1, "nf-protocol": 4}, "total": 999}"#).unwrap();
        root
    }

    #[test]
    fn verify_transform_matches_truth_source_branch_by_branch() {
        let root = build_fixture();
        let got = verify_transform(&root);
        assert_eq!(got.issues, WANT_TRANSFORM, "逐条消息须与真源一致");
        // 比 JSON 语义（对象键序无关）——`Json::Object` 的 `assert_eq!` 比的是内部向量序，
        // 而出口 `pyjson` 本就会排序，用它比会得到**假失败**。
        assert!(crate::jsonread::json_eq(
            &got.stats,
            &crate::jsonread::convert(&serde_json::json!({"entries": 5, "promoted": 3})).unwrap()
        ));
    }

    #[test]
    fn verify_usage_matches_truth_source_branch_by_branch() {
        let root = build_fixture();
        let got = verify_usage(&root);
        assert_eq!(got.issues, WANT_USAGE, "逐条消息须与真源一致");
        assert!(crate::jsonread::json_eq(
            &got.stats,
            &crate::jsonread::convert(&serde_json::json!({"events": 6, "sources_with_usage": 3}))
                .unwrap()
        ));
    }
}
