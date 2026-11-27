//! 基线相对回归评分（`score`）—— 与真源 `desktop/src/core/regression_score.py` 对账。
//!
//! 真源 `evaluate` 要跑 6 个扫描器。本线已移植其中 2 个（`doc_hygiene` / `asset_density`），
//! 其余 4 个（`schema_lint` / `conformance_scan` / `purity_scan` / `quality_depth_scan`）由
//! `--signals` 以**计数**形式喂入——`None` 表示"扫描器不可用"，与真源 `_count` 的哨兵语义一致
//! （**不可用 ≠ 零问题**：真源按 0 分计并记 issue，本线同）。
//!
//! 随着更多扫描器移植，`--signals` 的输入面会逐步缩小，直至 `nf score` 可完全自主。

use crate::asset_density;
use crate::doc_hygiene;
use crate::pyfloat;
use crate::pyjson::Json;
use crate::pyval::{arr_items, get, plain_str_opt};
use std::path::Path;

mod part1;

pub(crate) use part1::*;

#[cfg(test)]
mod tests {
    use super::*;

    fn cur(vals: &[(&str, f64, f64)]) -> Current {
        Current {
            score: 100.0,
            signals: vals
                .iter()
                .map(|(n, w, v)| ((*n).to_string(), *w, *v, String::new()))
                .collect(),
            asset_keys: 0,
            asset_files: 0,
            issues: Vec::new(),
        }
    }

    #[test]
    fn penalty_floors_at_zero() {
        assert_eq!(penalty(0, 0.1), 1.0);
        assert_eq!(penalty(10, 0.1), 0.0);
        assert_eq!(penalty(25, 0.1), 0.0);
        assert!((penalty(3, 0.1) - 0.7).abs() < 1e-12);
    }

    #[test]
    fn no_baseline_signals_yields_dedicated_verdict() {
        let c = cur(&[("schema_clean", 0.2, 1.0)]);
        let out = compare(&c, &Json::Object(vec![]), 0.0, &[]);
        assert_eq!(
            plain_str_opt(get(&out, "verdict")),
            "无基线（只报当前分值，未做回归判定）"
        );
    }

    #[test]
    fn single_signal_drop_is_regression_even_if_total_score_holds() {
        // no silent worsening：总分不降掩盖不了单信号恶化
        let baseline: Json = crate::jsonread::convert(&serde_json::json!({
            "score": 100.0,
            "signals": [{"name": "schema_clean", "value": 1.0},
                        {"name": "purity_clean", "value": 0.5}]
        }))
        .unwrap();
        let c = cur(&[("schema_clean", 0.2, 1.0), ("purity_clean", 0.15, 0.4)]);
        let out = compare(&c, &baseline, 0.0, &[]);
        assert_eq!(get(&out, "ok"), Some(&Json::Bool(false)));
        assert!(plain_str_opt(get(&out, "verdict")).contains("信号回落"));
    }

    #[test]
    fn exemption_moves_item_and_releases_budget() {
        let baseline: Json = crate::jsonread::convert(&serde_json::json!({
            "score": 100.0,
            "signals": [{"name": "purity_clean", "value": 1.0}]
        }))
        .unwrap();
        let c = cur(&[("purity_clean", 0.15, 0.9)]);
        // 不豁免 → 回落
        assert_eq!(
            get(&compare(&c, &baseline, 0.0, &[]), "ok"),
            Some(&Json::Bool(false))
        );
        // 豁免 → 进 exempted 且释放额度
        let exc = vec![("purity_clean".to_string(), "已批准".to_string())];
        let out = compare(&c, &baseline, 0.0, &exc);
        assert_eq!(
            get(&out, "exempted").map(|v| matches!(v, Json::Array(a) if a.len() == 1)),
            Some(true)
        );
        assert!(plain_str_opt(get(&out, "verdict")).contains("审计例外"));
    }
}
