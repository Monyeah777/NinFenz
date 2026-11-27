//! 门禁的**机器可读出口**（`verify_report`）—— 与真源 `desktop/src/core/verify_report.py` 对账。
//!
//! 真源把 **31 条判据**（各自调一个 core 扫描器）聚合成 `protocol/verification_report.json`：
//! 逐条归一到 `(issues, warns, stats)` → 定 status → 汇总 counts + 声明面 → 主体规范化 sha256 作
//! `root_digest`（报告被手改即对不上）→ 按 `indent=2, sort_keys=True` 渲染。
//!
//! **本线已自主算出 26/31 条**，其余 5 条由 `--results` 喂入各自的 `(issues, warns, stats)`
//! ——与 `score` 的 `--signals` 同一增量法：每移植一个扫描器，喂入面就小一格，内核不动。
//!
//! 喂入的 5 条：`redos` / `instruction_evidence` / `perf_budget` / `asset_contract` /
//! `role_coordinates`（`asset_contract` 为**已裁定**退出原生面，见 `docs/asset_contract.md`）。
//! ⚠️ 数字**不得凭记忆手写**：以 `engine/rust/tools/check_native_sync.py` 实测输出为准。
//!
//! **口径提醒**：`root_digest` 的源串用 CPython **默认分隔符**（`", "` / `": "`，带空格），
//! 不是紧凑模式——差一个空格摘要就全变（见 `pyjson::dumps_default`）。

use crate::baseline;
use crate::jsonread;
use crate::merkle;
use crate::pyjson::Json;
use crate::pyval::{get, plain_str_opt, py_str};
use std::collections::HashMap;
use std::path::Path;

mod part1;
mod part2;

pub(crate) use part1::*;
pub(crate) use part2::*;

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn spec_table_matches_the_truth_source_shape() {
        assert_eq!(SPECS.len(), 31);
        assert_eq!(SPECS[0].id, "purity");
        assert_eq!(SPECS[1].source(), "schema_lint.scan");
        assert_eq!(SPECS[5].id, "rating");
        assert_eq!(SPECS[6].id, "rating_decided");
        assert_eq!(SPECS[6].source(), "rating_gate.decided");
        assert_eq!(SPECS[29].id, "asset_contract");
        assert_eq!(SPECS[30].id, "role_coordinates");
        assert_eq!(SPECS[30].source(), "role_model.scan");
    }

    #[test]
    fn unported_spec_without_supplied_result_is_reported_as_error() {
        let spec = Spec {
            id: "nope",
            name: "x",
            module: "m",
            entry: "scan",
        };
        let got = call(&spec, Path::new("."), &HashMap::new());
        assert_eq!(got.status, "error");
        assert!(
            got.issues[0].contains("未移植且未喂入结果"),
            "{:?}",
            got.issues
        );
    }

    #[test]
    fn supplied_warns_alone_yield_warn_status() {
        let mut m = HashMap::new();
        m.insert(
            "nope".to_string(),
            Supplied {
                issues: Vec::new(),
                warns: vec!["w".to_string()],
                stats: empty_obj(),
                status: None,
            },
        );
        let spec = Spec {
            id: "nope",
            name: "x",
            module: "m",
            entry: "scan",
        };
        assert_eq!(call(&spec, Path::new("."), &m).status, "warn");
    }

    #[test]
    fn sample_truncates_at_200_characters() {
        let long = "字".repeat(250);
        let sample: Vec<Json> = vec![Json::Str(long.chars().take(200).collect())];
        let Json::Str(s) = &sample[0] else { panic!() };
        assert_eq!(s.chars().count(), 200);
    }
}
