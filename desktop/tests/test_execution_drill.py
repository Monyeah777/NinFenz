#!/usr/bin/env python3
"""42 M1 + 44 扩展 —— 执行失范捕获器单测（多管线演练集 P01-P06/P90 + 变异自检/捕获率验收）。"""
import json
import re
import sys
import unittest
from pathlib import Path

if str(Path(__file__).resolve().parent.parent / "src") not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from core import execution_drill as drill  # noqa: E402

FIX_DIR = Path(__file__).resolve().parent / "fixtures" / "execution"
FIXTURES = [FIX_DIR / n
            for n in ("p01_drill_cases.json", "p02_drill_cases.json",
                      "p03_drill_cases.json", "p04_drill_cases.json",
                      "p05_drill_cases.json", "p06_drill_cases.json",
                      "p90_drill_cases.json")]


class ExecutionDrillTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sets = [json.loads(p.read_text(encoding="utf-8")) for p in FIXTURES]

    def _all_cases(self):
        for data in self.sets:
            for case in data["cases"]:
                yield data, case

    def _hits(self, data, case):
        return drill.run_case(case, data["real_ids"],
                              data.get("semantics") or {},
                              data.get("source_text", ""),
                              data.get("other_ids") or [],
                              data.get("asset_keys") or [])

    def test_deviation_capture_all(self):
        """失范样本须全部被硬断言捕获（无漏报）。"""
        for data, case in self._all_cases():
            expected = set(case.get("expect_captured") or [])
            if not expected:
                continue
            hits = set(self._hits(data, case))
            self.assertTrue(expected <= hits,
                            "{}/{} 期望捕获 {} 实得 {}".format(data["pipeline"], case["id"],
                             sorted(expected), sorted(hits)))

    def test_guard_samples_no_false_positive(self):
        """变异对照（guard）样本不得误捕获（特异性）。"""
        for data, case in self._all_cases():
            if not case.get("guard"):
                continue
            hits = set(self._hits(data, case))
            self.assertEqual(hits, set(),
                             "{}/{} 应无捕获，实得 {}".format(
                                 data["pipeline"], case["id"], sorted(hits)))

    def test_capture_rate_at_least_two_thirds(self):
        """M1 验收：注入 ≥3 失范样本捕获率 ≥2/3（逐管线）。"""
        for data in self.sets:
            dev = [c for c in data["cases"]
                   if c.get("expect_captured") and not c.get("guard")]
            captured = sum(1 for c in dev
                           if set(c["expect_captured"]) <= set(self._hits(data, c)))
            self.assertGreaterEqual(captured, len(dev))
            self.assertGreaterEqual(captured / max(1, len(dev)), 2 / 3,
                                    data["pipeline"])

    def test_state_header_acceptance_rule_law_mapping(self):
        """带状态头执行口径：硬断言须一一映射到判级器必须/禁止铁律（无越级）。"""
        from core import round_header as rh
        for rule, law_id in drill.RULE_LAW.items():
            law = rh.LAW_INDEX[law_id]
            self.assertIn(law["level"], ("必须", "禁止"),
                          f"{rule} 不得映射到软级/自由级")
        self.assertEqual(len(drill.RULE_LAW), 6)


class RealCorpusRegressionTest(unittest.TestCase):
    """2026-10-20 真实语料实测暴露的两条误报（唯一真实战例 P03）的定点回归。"""

    def test_id_suffix_normalized_against_category_prefixed_real_ids(self):
        """真实集写 `生存:M10`/`通用:M10`，正文写裸 `M10` ⇒ 同一模块，不得判编造。"""
        for ids in (["生存:M10"], ["通用:M10"], ["M00", "生存:M10"]):
            self.assertEqual([], drill.run_case({"output": "裸 M10 由本模块结算。"}, ids),
                             f"real_ids={ids} 时裸 M10 被判编造（后缀归一缺失）")
        self.assertEqual(["fabricated_id"],
                         drill.run_case({"output": "由 M99 完成本条推进。"}, ["M00", "生存:M10"]),
                         "真编造必须still捕获")

    def test_cross_pipeline_by_tail(self):
        """其它管线真实编号按尾段识别 ⇒ 判跨管线串号（不是「编造」）。"""
        self.assertEqual(["cross_pipeline_id"],
                         drill.run_case({"output": "由 M65 完成。"}, ["M00"],
                                        {}, "", ["情感:M65"]))
        self.assertEqual(["fabricated_id"],
                         drill.run_case({"output": "由 M65 完成。"}, ["M00"]),
                         "未给 other_ids 时无从判跨管线，仍应落回编造")

    def test_path_token_is_not_a_bare_id(self):
        """文件名/路径里的编号前缀不是裸编号断言（P03:109 `modules/M10_死亡重生.md`）。"""
        for out in ("- 出处：community/西幻生存领域包/modules/M99_不存在.md",
                    "见 modules/M99.md。",
                    "文件 M99_死亡重生.md 已归档。"):
            self.assertEqual([], drill.run_case({"output": out}, ["M00"]),
                             f"路径/文件名 token 被当裸编号：{out!r}")
        self.assertEqual(["fabricated_id"],
                         drill.run_case({"output": "由 M99 推进。"}, ["M00"]),
                         "裸编号断言不得因路径排除而漏报")

    def test_path_token_keeps_no_citation_guard(self):
        """路径排除只作用于编号断言：路径里的真实编号仍算「有编号提及」
        （避免新增 no_citation 误报）。"""
        out = "应用与亚种。出处：modules/M02_种族天赋.md。"
        self.assertEqual([], drill.run_case({"output": out}, ["M00", "M02"]),
                         "路径 token 一并从「有编号提及」里排除 ⇒ 反而新增 no_citation 误报")


class ReverseCheckTest(unittest.TestCase):
    """反向：真实语料（唯一真实战例 P03）逐行回放必须**零误报**。"""

    def _real_ids(self, text):
        real_ids = []
        for line in text.splitlines():
            m = re.match(r"^\|\s*((?:[\u4e00-\u9fff]+:)?M\d{2,3})\s*\|", line)
            if m and m.group(1) not in real_ids:
                real_ids.append(m.group(1))
        self.assertEqual(26, len(real_ids), "P03 注册表投影应 26 在册")
        return real_ids

    def test_p03_real_corpus_has_no_false_positive(self):
        root = Path(__file__).resolve().parents[2]
        text = (root / "docs" / "完整版样本_西幻生存流P03.md").read_text(encoding="utf-8")
        real_ids = self._real_ids(text)
        reported = []
        for line_no, line in enumerate(text.splitlines(), 1):
            if not line.strip():
                continue
            for rule in drill.run_case({"output": line}, real_ids):
                reported.append((line_no, rule))
        self.assertEqual([], reported, f"P03 真实语料仍有命中（应全为已裁定误报）：{reported}")

    def test_p03_known_false_positive_lines_are_gone(self):
        """上轮逐条裁定的 4 条误报（构词粘连 / 否定语境 / 历史语境）定点消失。"""
        real_ids = ["M00", "M23", "M04", "M02", "通用:M10", "生存:M10", "M01", "M08"]
        cases = (
            ("元素反应", "- 核心逻辑：战斗结算——元素反应 → 士气体型修正。"),
            ("对应件", "### 官方核心配合 11 件（契约摘要；全文路径 = 04_模块库对应件）"),
            ("否定语境", "（步 5 M23、步 14 M65 幽灵沉淀不命中）"),
            ("历史语境", "| 数据接口 | EXTERNAL | 源编号残留 M21，职能归 M00 |"),
        )
        for name, out in cases:
            self.assertEqual([], drill.run_case({"output": out}, real_ids),
                             f"{name} 误报仍在：{out!r}")


class ContextBoundaryTest(unittest.TestCase):
    """两条新判据的**边界守卫**：只收紧不放宽（真阳性必须仍捕获）。"""

    IDS = ["M00"]

    def _hits(self, out):
        return drill.run_case({"output": out}, self.IDS)

    def test_decision_word_glue_is_not_decision(self):
        for out in ("技能应用说明。", "混沌事件响应链。", "种族适应与亚种。",
                    "材料供应清单。", "地形效应修正。"):
            self.assertEqual([], self._hits(out), f"构词粘连被当决策词：{out!r}")

    def test_real_decision_words_still_caught(self):
        for out in ("应当输出结算结果。", "必须先写回状态。", "下一步进入结算。",
                    "结论：按此推进。", "禁止跳过质检门。"):
            self.assertEqual(["no_citation"], self._hits(out), f"真决策句漏报：{out!r}")

    def test_negation_context_only_for_explicit_predicates(self):
        """否定**谓词**才豁免；句内光有「不」不算（否则真失范会被误豁免）。"""
        for out in ("步 14 M65 幽灵沉淀不命中。", "M99 未使用。", "M99 不参与本回合。",
                    "不得使用 M98 作为编号。"):
            self.assertEqual([], self._hits(out), f"否定语境误报：{out!r}")
        for out in ("M99 输出不完整。", "M99 未完待续。", "由 M99 完成本条推进。"):
            self.assertEqual(["fabricated_id"], self._hits(out),
                             f"否定语境豁免过宽，真失范漏报：{out!r}")

    def test_history_context(self):
        for out in ("源编号残留 M21，职能归 M00。", "旧版 M98 已下线。",
                    "此前曾由 M97 承担。"):
            self.assertEqual([], self._hits(out), f"历史语境误报：{out!r}")
        self.assertEqual(["fabricated_id"], self._hits("由 M21 结算经济。"),
                         "当前断言里的编造编号被历史语境规则吃掉")

    def test_context_window_does_not_cross_clause(self):
        """语境窗不跨句：前一句的否定不得豁免后一句的当前断言。"""
        self.assertEqual(["fabricated_id"], self._hits("该模块未启用。由 M99 完成推进。"),
                         "跨句豁免（否定词在上一句）")


if __name__ == "__main__":
    unittest.main()
