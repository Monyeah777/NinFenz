//! 决策记录门禁（`decisions`）—— 与真源 `desktop/src/core/decisions.py` 对账。
//!
//! 判据：编号合法且与文件名一致 / 编号唯一 / 必填齐 / status 在词表 / date 格式 / 三段齐 /
//! evidence 可解析（真实件或 `checkN` 或 `ADR-N`）/ **accepted 须被协议回执锚定** /
//! supersede 链可解析且无环；另加**投影一致**（`decisions/INDEX.md` == 实时重算）。

use crate::jsonread;
use crate::mdblocks;
use crate::pyjson::Json;
use crate::pyval::{arr_items, get, plain_str, plain_str_opt, py_str, py_truthy};
use std::collections::BTreeSet;
use std::path::Path;

mod part1;

pub(crate) use part1::*;

#[cfg(test)]
mod handwritten_tests {
    use super::*;

    #[test]
    fn missing_adrs_reports_and_zeroes_stats() {
        let tmp = crate::testutil::fixture("dec-none");
        let (issues, d, a, c) = scan(&tmp);
        assert_eq!(issues.len(), 1);
        assert!(issues[0].contains("未发现任何 ADR"));
        assert_eq!((d, a, c), (0, 0, 0));
        let _ = std::fs::remove_dir_all(&tmp);
    }

    #[test]
    fn id_must_match_file_name() {
        let tmp = crate::testutil::fixture("dec-idmismatch");
        std::fs::create_dir_all(tmp.join("decisions")).unwrap();
        std::fs::write(
            tmp.join("decisions/ADR-0007-x.md"),
            "---\nid: ADR-0009\ntitle: t\nstatus: accepted\ndate: 2026-01-01\nevidence: [protocol/LAYERS.json]\n---\n## 背景\n## 决策\n## 后果\n"
                .as_bytes(),
        )
        .unwrap();
        let (issues, _, _, _) = scan(&tmp);
        assert!(
            issues.iter().any(|i| i.contains("id 与文件名不一致")),
            "编号与文件名不一致必须判红：{:?}",
            issues
        );
        let _ = std::fs::remove_dir_all(&tmp);
    }

    #[test]
    fn supersede_cycle_is_detected() {
        let tmp = crate::testutil::fixture("dec-cycle");
        std::fs::create_dir_all(tmp.join("decisions")).unwrap();
        for (n, sb) in [("0001", "ADR-0002"), ("0002", "ADR-0001")] {
            std::fs::write(
                tmp.join(format!("decisions/ADR-{}-x.md", n)),
                format!(
                    "---\nid: ADR-{}\ntitle: t\nstatus: superseded\ndate: 2026-01-01\nevidence: [protocol/LAYERS.json]\nsuperseded_by: {}\n---\n## 背景\n## 决策\n## 后果\n",
                    n, sb
                )
                .as_bytes(),
            )
            .unwrap();
        }
        let (issues, _, _, chains) = scan(&tmp);
        assert_eq!(chains, 2);
        assert!(
            issues.iter().any(|i| i.contains("取代链成环")),
            "环必须判红：{:?}",
            issues
        );
        let _ = std::fs::remove_dir_all(&tmp);
    }
}

#[cfg(test)]
#[path = "generated/decisions_gen.rs"]
mod decisions_gen;
