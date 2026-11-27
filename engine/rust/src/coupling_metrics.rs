//! 模块级耦合度量与**只许收敛**的债务闸门（`coupling_metrics`）—— 与真源
//! `desktop/src/core/coupling_metrics.py` 对账。
//!
//! 外部标准只作机制借鉴（Martin 包度量 + 稳定依赖原则 SDP）：**Ca** = 有多少同包模块依赖我；
//! **Ce** = 我依赖多少同包模块；**I = Ce/(Ca+Ce)**（0 = 最稳）。SDP：依赖应指向更稳的一侧。
//!
//! 真源为什么是「登记债 + 棘轮」而非一律判死（实测口径）：首日实测 core 122 个模块 →
//! 3 个模块级环 + 5 处 SDP 违例，都是存量设计债；一次性判死会立刻红门禁且要求重构正被
//! 并发会话改写的文件。故**登记在册的债放行**，判据只拦**新增**环/新增 SDP 违例；
//! 债务被消掉时记 WARN（债务表不得虚挂）。
//!
//! **移植口径（重要）**：真源用 `ast` 抽 import；本线用**词法抽取**（先剥注释与字符串，
//! 再解析 `import` / `from … import …` 语句，含相对导入与括号多行）。这是**近似**——
//! 但它不是"悄悄近似"：任何分歧都会改变环/SDP 集合，而环/SDP 是与基线**逐条**比对的，
//! 故分歧必然以「新增环/新增 SDP 违例」的形式在对账面上暴露出来。
//!
//! 本模块是 `nf verify-report` 的 `coupling` 判据，**不单独开 CLI 面**。

use crate::jsonread;
use crate::pyfloat;
use crate::pyjson::Json;
use crate::pysrc;
use crate::pyval::{arr_items, get, plain_str, py_str};
use std::collections::{BTreeMap, BTreeSet};
use std::path::Path;

mod part1;

pub(crate) use part1::*;

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn import_extraction_covers_relative_and_parenthesised_forms() {
        let known: BTreeSet<String> = ["a", "b", "c", "d", "e"]
            .iter()
            .map(|s| s.to_string())
            .collect();
        let src = "import core.a\nfrom core import b, c\nfrom . import d\nfrom .core import e\n";
        let got = module_deps(src, "self", &known);
        assert_eq!(
            got,
            ["a", "b", "c", "d", "e"]
                .iter()
                .map(|s| s.to_string())
                .collect()
        );
    }

    #[test]
    fn parenthesised_multiline_import_is_joined() {
        let known: BTreeSet<String> = ["a", "b"].iter().map(|s| s.to_string()).collect();
        let src = "from core import (\n    a,\n    b,\n)\n";
        assert_eq!(
            module_deps(src, "self", &known),
            ["a", "b"].iter().map(|s| s.to_string()).collect()
        );
    }

    #[test]
    fn self_dependency_is_dropped() {
        let known: BTreeSet<String> = ["self", "other"].iter().map(|s| s.to_string()).collect();
        assert!(module_deps("from core import self", "self", &known).is_empty());
    }
    /// ===== 分支级差分判据（期望值由 `tools/gen_coupling_expected.py` 从真源生成）=====
    ///
    /// 真语料上 `coupling` 只有固定的那几组环/SDP，**import 抽取的各种写法一条也没被单独核过**；
    /// 而本线的抽取是**词法近似**（真源用 `ast`）——正是最该被直接核的地方。
    /// 本夹具逐形态踩：普通 / 多别名 / 点号模块 / 相对无模块 / 相对 core / 相对带模块 /
    /// 括号多行 / 别名 / 字符串与注释里的假 import / `__init__` 忽略。
    const SRC: [(&str, &str); 10] = [
        (
            "__init__",
            r#"from core.aa import x
"#,
        ),
        (
            "aa",
            r#"import core.bb
from core import cc, dd
"#,
        ),
        (
            "bb",
            r#"from core.aa import x
"#,
        ),
        (
            "cc",
            r#"from . import ee
"#,
        ),
        (
            "dd",
            r#"from .core import ff
"#,
        ),
        (
            "ee",
            r#"from ..pkg.sub import gg
"#,
        ),
        (
            "ff",
            r#"from core import (hh,
    ii)
"#,
        ),
        (
            "gg",
            r#"import core.hh as hh
"#,
        ),
        (
            "hh",
            r#"S = "from core import zzz"
# import core.yyy
"#,
        ),
        (
            "ii",
            r#"import os
import json
"#,
        ),
    ];

    fn build_fixture() -> std::path::PathBuf {
        let root = crate::testutil::fixture("coupling-branches");
        let core = root.join("desktop/src/core");
        std::fs::create_dir_all(&core).unwrap();
        for (name, body) in SRC {
            std::fs::write(core.join(format!("{}.py", name)), body).unwrap();
        }
        root
    }

    #[test]
    fn import_extraction_matches_ast_on_every_form() {
        let root = build_fixture();
        let g = graph(&root);
        let want: Vec<(String, Vec<String>)> = vec![
            (
                "aa".to_string(),
                vec!["bb".to_string(), "cc".to_string(), "dd".to_string()],
            ),
            ("bb".to_string(), vec!["aa".to_string()]),
            ("cc".to_string(), vec!["ee".to_string()]),
            ("dd".to_string(), vec!["ff".to_string()]),
            ("ee".to_string(), vec![]),
            ("ff".to_string(), vec!["hh".to_string(), "ii".to_string()]),
            ("gg".to_string(), vec!["hh".to_string()]),
            ("hh".to_string(), vec![]),
            ("ii".to_string(), vec![]),
        ];
        let got: Vec<(String, Vec<String>)> = g
            .deps
            .iter()
            .map(|(k, v)| (k.clone(), v.iter().cloned().collect()))
            .collect();
        assert_eq!(got, want, "同包依赖集合须与真源 AST 版逐条一致");
    }

    #[test]
    fn ca_ce_i_match_the_truth_source() {
        let root = build_fixture();
        let g = graph(&root);
        let want: Vec<(&str, i64, i64, f64)> = vec![
            ("aa", 1, 3, 0.75),
            ("bb", 1, 1, 0.5),
            ("cc", 1, 1, 0.5),
            ("dd", 1, 1, 0.5),
            ("ee", 1, 0, 0.0),
            ("ff", 1, 2, 0.6667),
            ("gg", 0, 1, 1.0),
            ("hh", 2, 0, 0.0),
            ("ii", 1, 0, 0.0),
        ];
        for (m, ca, ce, i) in want {
            assert_eq!(g.ca.get(m).copied().unwrap_or(-1), ca, "Ca 不符：{}", m);
            assert_eq!(g.ce.get(m).copied().unwrap_or(-1), ce, "Ce 不符：{}", m);
            assert_eq!(g.i_of.get(m).copied().unwrap_or(-1.0), i, "I 不符：{}", m);
        }
    }

    #[test]
    fn cycles_and_sdp_match_the_truth_source() {
        let root = build_fixture();
        let g = graph(&root);
        let cyc = cycles(&g.deps);
        let want: Vec<Vec<String>> = vec![vec!["aa".to_string(), "bb".to_string()]];
        assert_eq!(cyc, want, "环集合");
        let sdp = sdp_violations(&g);
        let want_sdp: Vec<(String, String)> = vec![
            ("bb".to_string(), "aa".to_string()),
            ("dd".to_string(), "ff".to_string()),
        ];
        assert_eq!(sdp, want_sdp, "SDP 违例（有方向，不排序）");
    }

    #[test]
    fn scan_reports_both_cycle_and_sdp_with_exact_wording() {
        let root = build_fixture();
        let got = scan(&root);
        assert_eq!(
            got.issues.len(),
            4,
            "1 个环 + 2 处 SDP + 缺 metrics 面：{:?}",
            got.issues
        );
        assert!(
            got.issues[0].starts_with("新增模块级环：aa → bb → aa（"),
            "{:?}",
            got.issues[0]
        );
        assert!(
            got.issues[1].starts_with("新增 SDP 违例：bb(I=0.50) 依赖了更不稳的 aa(I=0.75)（"),
            "{:?}",
            got.issues[1]
        );
        assert!(
            got.issues[2].starts_with("新增 SDP 违例：dd(I=0.50) 依赖了更不稳的 ff(I=0.67)（"),
            "{:?}",
            got.issues[2]
        );
        assert!(
            got.issues[3].starts_with("耦合基线缺 metrics 面（"),
            "{:?}",
            got.issues[3]
        );
        assert_eq!(got.warns.len(), 1);
        assert!(
            got.warns[0].starts_with("无耦合基线 protocol/coupling_baseline.json"),
            "{:?}",
            got.warns[0]
        );
        assert!(crate::jsonread::json_eq(
            &got.stats,
            &crate::jsonread::convert(&serde_json::json!({
                "cycles": 1, "modules": 9, "registered_cycles": 0,
                "registered_sdp": 0, "sdp": 2, "metrics_recorded": 0,
                "metrics_drift": 0, "metrics_missing": 9
            }))
            .unwrap()
        ));
    }
}
