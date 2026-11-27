//! 抽象阶梯体检 —— **与 Python 真源 `desktop/src/core/layer_model.py` 逐字节对账**。
//!
//! 覆盖真源的 `load` + `scan`/`_scan_impl`/`_rule_issues`（L1–L10）与 `render_markdown`，
//! 以及 CLI 面 `nf layers --verify --json` 的输出字节。
//!
//! **只读**：`write_region`（刷新 `docs/layers.md` 生成区）**不实现**——真源仍在 Python 侧。
//!
//! **已知近似**：L6 需要 `ast` 判定「core 有没有反向 import 入口面」。本线用
//! [`crate::pysrc`] 做词法级提取（剥注释/字符串后按语句行取 import），**不宣称等价于 `ast`**；
//! 该近似只影响 L6 的 issue 文本与行号，且当前语料上 L6 零命中（详见 `pysrc` 模块文档）。

use crate::glob;
use crate::jsonread;
use crate::pyjson::Json;
use crate::pysrc;
use crate::pyval::{arr_items, get, plain_str, plain_str_opt, py_str, str_list};
use std::collections::{BTreeSet, HashMap, HashSet};
use std::path::Path;

mod part1;
mod part2;

pub(crate) use part1::*;
pub(crate) use part2::*;

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn region_of_extracts_between_markers() {
        let t = format!("head\n{}\nBODY\n{}\ntail", MARK_BEGIN, MARK_END);
        assert_eq!(region_of(&t).unwrap().trim(), "BODY");
        assert!(region_of("no markers").is_none());
        assert!(region_of(MARK_BEGIN).is_none());
    }

    #[test]
    fn table_matches_truth_source_shape() {
        let rows = vec![vec!["a".to_string(), "b".to_string()]];
        let got = table(&rows, &["x", "y"]);
        assert_eq!(got[0], "| x | y |");
        assert_eq!(got[1], "|---|---|");
        assert_eq!(got[2], "| a | b |");
    }

    #[test]
    fn missing_declaration_reports_and_zeroes_stats() {
        let tmp = crate::testutil::fixture("layers-missing");
        let (issues, stats) = scan(&tmp);
        assert_eq!(issues.len(), 1);
        assert!(issues[0].contains("缺阶梯真源"), "got: {}", issues[0]);
        // 真源此处 stats 只有三个键
        let Json::Object(p) = &stats else { panic!() };
        assert_eq!(p.len(), 3);
        let _ = std::fs::remove_dir_all(&tmp);
    }

    #[test]
    fn entry_import_detection_ignores_prose_and_strings() {
        // 真源本体就长这样：文档字符串里写「不许 import nf」，AST 不判、裸行扫描会假红
        let src = "\"\"\"core 不许出现 import nf / from scripts …\"\"\"\n# from scripts import x\nimport os\n";
        assert!(
            pysrc::entry_imports(src).is_empty(),
            "散文/注释不得被当成 import"
        );
        let real = "import os\nimport nf\n";
        assert_eq!(pysrc::entry_imports(real), vec![(2usize, "nf".to_string())]);
        let rel = "from scripts.nf import y\n";
        assert_eq!(
            pysrc::entry_imports(rel),
            vec![(1usize, "scripts".to_string())]
        );
    }

    #[test]
    fn raw_prefix_and_triple_quotes_are_stripped() {
        let src = "x = r\"import nf\"\ny = '''\nimport scripts\n'''\nz = 1\n";
        let stripped = pysrc::strip_comments_and_strings(src);
        assert!(!stripped.contains("import nf"));
        assert!(!stripped.contains("import scripts"));
        assert!(stripped.contains("z = 1"));
        // 行结构（含换行）必须保留，否则 L6 行号会漂
        assert_eq!(stripped.lines().count(), src.lines().count());
    }

    #[test]
    fn raw_string_escaped_quote_does_not_swallow_following_import() {
        let src = r#"x = r"\""
from core import atomic_write
"#;
        let stripped = pysrc::strip_comments_and_strings(src);
        assert!(
            stripped.contains("from core import atomic_write"),
            "raw string 内的 \\\" 不得提前闭合词法状态：{stripped:?}"
        );
    }
}
