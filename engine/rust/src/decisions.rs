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

/// evidence 面：checkN / ADR-N / 真实件路径 三选一。
pub(crate) fn entry_evidence_issues(
    tag: &str,
    fm: &Json,
    root: &Path,
    checks: &BTreeSet<String>,
    issues: &mut Vec<String>,
) {
    for ev in arr_items(get(fm, "evidence")) {
        let s = plain_str(ev).trim().to_string();
        if s.is_empty() {
            issues.push(format!("{} 的 evidence 有空项", tag));
            continue;
        }
        if let Some(c) = re_check().captures(&s) {
            if !checks.contains(&c[1]) {
                issues.push(format!("{} 的 evidence 指向不存在的 check：{}", tag, s));
            }
            continue;
        }
        if re_adr().is_match(&s) {
            continue;
        }
        if !root.join(s.replace('\\', "/")).exists() {
            issues.push(format!(
                "{} 的 evidence 无法解析：{}（修复指引：改为真实件路径，或 checkN，或 ADR-N）",
                tag, s
            ));
        }
    }
}

/// accepted 必须被协议回执锚定。
pub(crate) fn entry_acceptance_issues(
    tag: &str,
    st: &str,
    has_receipts: bool,
    path: &str,
    receipts: &BTreeSet<String>,
    issues: &mut Vec<String>,
) {
    if st == "accepted" && has_receipts && !receipts.contains(path) {
        issues.push(format!(
            "{} 已 accepted 但未被协议回执锚定（修复指引：nf receipts --write）——未锚定的 accepted 等于可被偷改",
            tag
        ));
    }
}

/// superseded 必须带 superseded_by；有值则记录取代边（同 did 后者覆盖）。
pub(crate) fn entry_supersede_issues(
    tag: &str,
    st: &str,
    did: &str,
    fm: &Json,
    supby: &mut Vec<(String, String)>,
    issues: &mut Vec<String>,
) {
    let sb = py_str(get(fm, "superseded_by")).trim().to_string();
    if st == "superseded" && DASHES.contains(&sb.as_str()) {
        issues.push(format!("{} 标 superseded 但缺 superseded_by", tag));
    }
    if !DASHES.contains(&sb.as_str()) {
        if let Some(slot) = supby.iter_mut().find(|(i, _)| *i == did) {
            slot.1 = sb;
        } else {
            supby.push((did.to_string(), sb));
        }
    }
}
