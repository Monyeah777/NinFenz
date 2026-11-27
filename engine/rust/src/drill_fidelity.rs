//! 演练保真度**量化**（`drill_fidelity`）—— 与真源逐字对账。
//!
//! 真源三个件（本模块一并移植，均在模块头注明）：
//! - `desktop/src/core/drill_fidelity.py` —— `measure` / `scan`（外层判据）
//! - `desktop/src/core/execution_drill.py` —— `run_case`（句子级硬断言 R1–R4）
//! - `desktop/src/core/round_drill.py` —— `scan`（回合级断言 R-R1–R-R4）
//!
//! 判据：逐个执行演练集跑 `run_case`，要求「捕获无漏报（`expect_captured ⊆ hits`）+
//! guard 无误报（无期望命中时不得有命中）」；逐个回合样本回放，要求实测 verdict 复现样本声明
//! （`good → conformant` / `bad → non-conformant`）；**找不到用例/样本 = FAIL**（标准不得无载体）。
//! 保真度 = 通过例数 / 总例数，`round(x, 4)`（CPython 半偶舍入，走 `pyfloat::round_to`）。
//!
//! 移植面：只做 `scan`。真源的 `write` 是**写面**（落 `protocol/drill_fidelity.json`），本线不碰；
//! `main()` 是 CLI 入口，无判据消费者。故 `measure` 只按 `scan` 要用的字段取材。
//!
//! ## 已知偏差（无法逐字比对，单列说明）
//!
//! 1. **坏 JSON 的异常文本**：真源 `except ValueError as exc` 把 CPython 的
//!    `JSONDecodeError` 原文（如 `Expecting value: line 1 column 1 (char 0)`）拼进 issue；
//!    本线措辞自拟（`…不是合法 JSON：（本线不复刻 CPython 解析器原文，见模块头）`）。
//!    **两侧都判 FAIL**，只是文本不同。真语料上所有夹具件均可解析；分支夹具里的坏 JSON 因此
//!    只断言 issue 前缀（`bad_json_*_needs_a_self_authored_prefix`），不伪造真源文本。
//! 2. **JSON 合法但非对象**（如顶层是 `[]`）：真源 `data.get(...)` 抛 `AttributeError` ⇒ 整条判据
//!    记 **ERROR**；本线把该件当作「无 cases / 无样本」继续 ⇒ 记 **FAIL**。两侧都是红的，
//!    但状态不同。这与 `modeling` 的未登记 `python_attr` 是同一类偏差。
//! 3. **`cases`/`allowed` 显式为 `null`**：真源 `for case in None` 抛 `TypeError` ⇒ ERROR；
//!    本线按空集处理 ⇒ FAIL。
//! 4. **Unicode 数字的回合号**：Python `int("٣")` 得 3；本线 `parse::<i64>()` 只吃 ASCII 数字，
//!    解析失败按 0 计。真语料为 ASCII。
//! 5. **真实语料命中裁定（2026-10-20 加，真源 `real_corpus`）**：真源把唯一真实战例
//!    `docs/完整版样本_西幻生存流P03.md` 逐非空行回放 `execution_drill`，并要求逐条 TP/FP 裁定
//!    （`real_corpus.adjudications`）；本线**只移植 `scan`**（写面/度量面不移植，见本模块头），
//!    故 `real_corpus` 的命中裁定门与 `metrics` 只在真源侧执行。两侧在真语料上的 `scan`
//!    （issues/stats）仍逐字一致；语料裁定漂移时只有真源报 FAIL——这是**有意的不对称**，
//!    不是静默：真源 `scan` 的 issues 里会多出「真实语料裁定：…」条目。
//! 6. **待裁定样本**（`verdict`/`label_status` = `pending`，2026-10-20 加）：两侧同口径——
//!    不参与「声明 vs 实测」分子分母，但必须解析出回合标记（`turns > 0`），否则 FAIL。
//! 7. **正例对照（2026-10-20 加，真源 `positive_controls`）**：真源对真实语料注入已知违规生成变体
//!    （注入→必红 / 原版→必绿）并把结果记进 `protocol/drill_fidelity.json`；本线在测试侧**同夹具
//!    同期望**复跑（`positive_controls_catch_injected_violations`），但不把它接进 `scan` issues
//!    （同偏差 5：度量面不移植）。两侧都失败时真源 `scan` 多出「正例对照失效：…」条目——有意不对称。

use crate::jsonread;
use crate::pyjson::Json;
use crate::pyval::{arr_items, get, plain_str_opt, py_str};
use std::collections::BTreeSet;
use std::path::Path;

mod part1;
mod part2;
mod part3;

pub(crate) use part1::*;
pub(crate) use part2::*;
pub(crate) use part3::*;

#[cfg(test)]
mod handwritten_tests {
    use super::*;

    /// ===== 真实语料误报收口（2026-10-20，非生成段：与真源 `test_execution_drill` 同用例集）=====
    ///
    /// 判据只收紧不放宽：构词粘连（反应/对应/应用…）不算决策词；否定/历史**显式谓词**
    /// 语境里的编号提及不算断言；而句内光有「不」、或跨句的谓词都不得豁免真失范。
    #[test]
    fn context_boundary_matches_the_truth_source() {
        let ids = vec!["M00".to_string()];
        let run = |out: &str| {
            run_case(
                &crate::jsonread::convert(&serde_json::json!(
            {"output": out}))
                .unwrap(),
                &ids,
                None,
                "",
                &[],
                &[],
                None,
            )
        };
        // 构词粘连：不算决策词 ⇒ 无失范
        for out in [
            "技能应用说明。",
            "混沌事件响应链。",
            "种族适应与亚种。",
            "材料供应清单。",
            "地形效应修正。",
        ] {
            assert!(run(out).is_empty(), "构词粘连被当决策词：{}", out);
        }
        // 真决策句仍捕获
        for out in [
            "应当输出结算结果。",
            "必须先写回状态。",
            "下一步进入结算。",
            "结论：按此推进。",
            "禁止跳过质检门。",
        ] {
            assert_eq!(
                run(out),
                vec!["no_citation".to_string()],
                "真决策句漏报：{}",
                out
            );
        }
        // 否定语境：只认显式谓词
        for out in [
            "步 14 M65 幽灵沉淀不命中。",
            "M99 未使用。",
            "M99 不参与本回合。",
            "不得使用 M98 作为编号。",
        ] {
            assert!(run(out).is_empty(), "否定语境误报：{}", out);
        }
        for out in [
            "M99 输出不完整。",
            "M99 未完待续。",
            "由 M99 完成本条推进。",
        ] {
            assert_eq!(
                run(out),
                vec!["fabricated_id".to_string()],
                "否定语境豁免过宽，真失范漏报：{}",
                out
            );
        }
        // 历史语境 + 守卫
        for out in [
            "源编号残留 M21，职能归 M00。",
            "旧版 M98 已下线。",
            "此前曾由 M97 承担。",
        ] {
            assert!(run(out).is_empty(), "历史语境误报：{}", out);
        }
        assert_eq!(
            run("由 M21 结算经济。"),
            vec!["fabricated_id".to_string()],
            "当前断言里的编造编号被历史语境规则吃掉"
        );
        // 语境窗不跨句
        assert_eq!(
            run("该模块未启用。由 M99 完成推进。"),
            vec!["fabricated_id".to_string()],
            "跨句豁免（否定词在上一句）"
        );
    }

    /// ===== 正例对照（2026-10-20，非生成段：与真源 `drill_fidelity.positive_controls` 同夹具）=====
    ///
    /// 动机：真实语料 hits 从 5 降到 0 有两种解释——(a) 语料确实干净；(b) 判据被改弱到
    /// 什么都不报。用**注入已知违规**的 P03 变体区分：注入行必须命中期望规则、其它行零附带命中，
    /// 且原版 P03 仍 0 命中；变体还必须逐字节等于「语料+注入」（语料一改就要重生成夹具）。
    #[test]
    fn positive_controls_catch_injected_violations() {
        let root = crate::testutil::repo_root();
        let rel = "desktop/tests/fixtures/execution/positive_controls/p03_injections.json";
        let manifest = jsonread::read_file(&root, rel).expect("正例对照清单缺件");
        let source_rel = plain_str_opt(get(&manifest, "source"));
        let real_ids: Vec<String> = arr_items(get(&manifest, "real_ids"))
            .iter()
            .map(|v| py_str(Some(v)))
            .collect();
        let source = std::fs::read_to_string(root.join(&source_rel)).expect("源语料不可读");
        assert!(
            probe_line_hits(&source, &real_ids).is_empty(),
            "原版真实语料必须 0 命中：{:?}",
            probe_line_hits(&source, &real_ids)
        );
        let base = if source.ends_with('\n') {
            source.clone()
        } else {
            format!("{}\n", source)
        };
        let source_lines = source.lines().count();
        let mut count = 0;
        for item in arr_items(get(&manifest, "controls")) {
            let id = plain_str_opt(get(item, "id"));
            let injection = plain_str_opt(get(item, "injection"));
            let variant = plain_str_opt(get(item, "variant"));
            let expect: Vec<String> = arr_items(get(item, "expect"))
                .iter()
                .map(|v| py_str(Some(v)))
                .collect();
            let vpath = root
                .join("desktop/tests/fixtures/execution/positive_controls")
                .join(&variant);
            let text = std::fs::read_to_string(&vpath).expect("变体件不可读");
            assert_eq!(
                text,
                format!("{}{}\n", base, injection),
                "变体须等于「语料+注入」：{}",
                id
            );
            let line_no = source_lines + 1;
            let hits = probe_line_hits(&text, &real_ids);
            let at_line: Vec<String> = hits
                .iter()
                .filter(|(n, _)| *n == line_no)
                .map(|(_, r)| r.clone())
                .collect();
            let extra: Vec<(usize, String)> =
                hits.into_iter().filter(|(n, _)| *n != line_no).collect();
            assert!(extra.is_empty(), "{} 出现附带命中：{:?}", id, extra);
            for rule in &expect {
                assert!(
                    at_line.iter().any(|r| r == rule),
                    "{} 注入行未命中 {}（实得 {:?}）",
                    id,
                    rule,
                    at_line
                );
            }
            count += 1;
        }
        assert_eq!(count, 3, "注入清单必须恰好三组");
    }

    /// 逐非空行回放 `run_case` → `[(行号, 规则名)]`（正例对照用）。
    fn probe_line_hits(text: &str, real_ids: &[String]) -> Vec<(usize, String)> {
        let mut out: Vec<(usize, String)> = Vec::new();
        for (i, line) in text.split('\n').enumerate() {
            if line.trim().is_empty() {
                continue;
            }
            let case: Json =
                crate::jsonread::convert(&serde_json::json!({"output": line})).expect("case 构造");
            for rule in run_case(&case, real_ids, None, "", &[], &[], None) {
                out.push((i + 1, rule));
            }
        }
        out
    }
}

#[cfg(test)]
#[path = "generated/drill_fidelity_gen.rs"]
mod drill_fidelity_gen;
