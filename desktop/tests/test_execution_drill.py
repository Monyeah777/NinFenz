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
                            "%s/%s 期望捕获 %s 实得 %s" %
                            (data["pipeline"], case["id"],
                             sorted(expected), sorted(hits)))

    def test_guard_samples_no_false_positive(self):
        """变异对照（guard）样本不得误捕获（特异性）。"""
        for data, case in self._all_cases():
            if not case.get("guard"):
                continue
            hits = set(self._hits(data, case))
            self.assertEqual(hits, set(),
                             "%s/%s 应无捕获，实得 %s" %
                             (data["pipeline"], case["id"], sorted(hits)))

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
                          "%s 不得映射到软级/自由级" % rule)
        self.assertEqual(len(drill.RULE_LAW), 6)


class RealCorpusRegressionTest(unittest.TestCase):
    """2026-10-20 真实语料实测暴露的两条误报（唯一真实战例 P03）的定点回归。"""

    def test_id_suffix_normalized_against_category_prefixed_real_ids(self):
        """真实集写 `生存:M10`/`通用:M10`，正文写裸 `M10` ⇒ 同一模块，不得判编造。"""
        for ids in (["生存:M10"], ["通用:M10"], ["M00", "生存:M10"]):
            self.assertEqual([], drill.run_case({"output": "裸 M10 由本模块结算。"}, ids),
                             "real_ids=%s 时裸 M10 被判编造（后缀归一缺失）" % ids)
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
                             "路径/文件名 token 被当裸编号：%r" % out)
        self.assertEqual(["fabricated_id"],
                         drill.run_case({"output": "由 M99 推进。"}, ["M00"]),
                         "裸编号断言不得因路径排除而漏报")

    def test_path_token_keeps_no_citation_guard(self):
        """路径排除只作用于编号断言：路径里的真实编号仍算「有编号提及」（避免新增 no_citation 误报）。"""
        out = "应用与亚种。出处：modules/M02_种族天赋.md。"
        self.assertEqual([], drill.run_case({"output": out}, ["M00", "M02"]),
                         "路径 token 一并从「有编号提及」里排除 ⇒ 反而新增 no_citation 误报")


class ReverseCheckTest(unittest.TestCase):
    """反向：真实语料上 `M10` 的文件名误报必须消失（用整个 P03 文档逐行回放）。"""

    def test_p03_real_corpus_has_no_path_false_positive(self):
        root = Path(__file__).resolve().parents[2]
        doc = root / "docs" / "完整版样本_西幻生存流P03.md"
        text = doc.read_text(encoding="utf-8")
        real_ids = []
        for line in text.splitlines():
            m = re.match(r"^\|\s*((?:[\u4e00-\u9fff]+:)?M\d{2,3})\s*\|", line)
            if m and m.group(1) not in real_ids:
                real_ids.append(m.group(1))
        self.assertEqual(26, len(real_ids), "P03 注册表投影应 26 在册")
        reported = []
        for line_no, line in enumerate(text.splitlines(), 1):
            if not line.strip():
                continue
            for rule in drill.run_case({"output": line}, real_ids):
                reported.append((line_no, rule))
        self.assertNotIn((109, "fabricated_id"), reported,
                         "P03:109 的 `M10_死亡重生.md` 文件名误报仍在（路径 token 未排除）")
        # 剩余命中已逐条人工裁定（工件 = rounds/selfrun-*.json 的 real_corpus.adjudications）


if __name__ == "__main__":
    unittest.main()
