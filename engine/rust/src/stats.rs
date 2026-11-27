//! `nf stats` 只读面 —— **与 Python 真源 `desktop/src/core/repo_stats.py` 逐字节对账**。
//!
//! 覆盖真源的 `compute` + `check`（两者皆只读）：口径表见 `repo_stats.py` 模块头。
//! 输出字节与 `nf stats --json` 同形（`json.dumps(ensure_ascii=False, indent=2, sort_keys=True)` + `\n`）；
//! **退出码同真源**：`check` 有 issue ⇔ 退出码 1。
//!
//! 写面（`write`：重写 README/README.en/llms.txt 生成区 + `protocol/repo_stats.json`）**不实现**
//! ——真源仍是 Python 侧，本线只读。

use crate::jsonread;
use crate::pyjson::Json;
use std::path::Path;

mod part1;
mod part2;

pub(crate) use part1::*;
pub(crate) use part2::*;

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn check_counter_matches_python_regex() {
        let t = "check1() {\n}\ncheck22() {\n}\n# check3()\ncheck()\ncheckX()\n";
        // 真源 `^check[0-9]+\(\)`：只数行首且紧跟数字与 ()
        assert_eq!(count_checks(t), 2);
    }

    #[test]
    fn version_parser_takes_first_match() {
        assert_eq!(parse_version("# 版本 : v2.30  配套 : x\n"), "2.30");
        assert_eq!(parse_version("no version here\n"), "");
        assert_eq!(parse_version("# 版本: v1.0\n# 版本 : v9.9\n"), "1.0");
    }

    #[test]
    fn py_int_const_reads_module_level_only() {
        let src = "EXPECTED_CHECKS = 40\nEXPECTED_PASS = 70\nOTHER = 1\n";
        assert_eq!(py_int_const(src, "EXPECTED_CHECKS"), Some(40));
        assert_eq!(py_int_const(src, "EXPECTED_PASS"), Some(70));
        assert_eq!(py_int_const(src, "EXPECTED_MISSING"), None);
    }

    #[test]
    fn py_int_const_not_fooled_by_longer_name() {
        assert_eq!(
            py_int_const("EXPECTED_CHECKS_EXTRA = 9\n", "EXPECTED_CHECKS"),
            None
        );
    }

    #[test]
    fn replace_block_swaps_inner_region() {
        let text = format!("head\n{}\nOLD\n{}\ntail\n", BEGIN, END);
        let got = replace_block(&text, &format!("{}\nNEW\n{}", BEGIN, END)).unwrap();
        assert_eq!(got, format!("head\n{}\nNEW\n{}\ntail\n", BEGIN, END));
        assert!(replace_block("no markers", "x").is_none());
    }

    #[test]
    fn render_has_three_blocks_in_source_order() {
        let r = render(&Stats::default());
        assert_eq!(r.len(), 3);
        assert_eq!(r[0].0, "README.md");
        assert_eq!(r[2].0, "llms.txt");
        assert!(r[0].1.starts_with(BEGIN));
    }
}
