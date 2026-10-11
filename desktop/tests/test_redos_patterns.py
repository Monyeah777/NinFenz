#!/usr/bin/env python3
"""正则失控回溯（ReDoS）回归 —— 2026-10-10 全仓审计 Y3。

四层判据：
1. **形态自证**：(a+)+ 命中、(?:[.-]数字+)* 不命中（后者每次迭代有强制分隔符，是线性的）——
   比 json_schema 里的粗粒度启发式更严，避免把正常正则误判成 ReDoS。
2. **动态自证**：已知坏形态在长输入上必须被判超线性（探针真的抓得住）；加边界后必须线性。
3. **全仓面**：core.redos_scan.scan(ROOT) 零 issue（谁再写出 O(n²) 正则就会红）。
4. **同源夹具**：round_drill._CITE 与 assemble_plan._CITATION 逐字相同——同一语义两处实现时，
   夹具钉住它们不许分叉（本波只改一处就会红）。
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "desktop" / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import redos_scan as rs  # noqa: E402
from core import round_drill, assemble_plan  # noqa: E402

#: 探针规模与预算：坏形态在 32 KB 上约 0.7 s（远超 600 ms），好形态毫秒级（余量 >100×）。
N = 32768
BUDGET_MS = 600.0


class ShapeTest(unittest.TestCase):
    def test_refined_nesting_heuristic(self):
        self.assertTrue(rs.suspicious_nesting(r"(a+)+$"), "量词套量词应命中")
        self.assertTrue(rs.suspicious_nesting(r"(\w*)*"), "量词套量词应命中")
        self.assertEqual("", rs.suspicious_nesting(r"(?:[.-]\d+)*"),
                         "每轮有强制分隔符的组不是指数形态（不得误报）")
        self.assertEqual("", rs.suspicious_nesting(r"(?:_[A-Z0-9]+)+"))
        self.assertEqual("", rs.suspicious_nesting(r"v\d+(?:\.\d+){1,2}"))


class ProbeTest(unittest.TestCase):
    def test_probe_catches_quadratic(self):
        ms, _desc = rs.probe(r"[a-z]+:", n=N, budget_ms=BUDGET_MS)
        self.assertGreater(ms, BUDGET_MS, "已知 O(n²) 形态必须被探针判超线性（探针失效=假绿）")

    def test_probe_passes_linear(self):
        ms, _desc = rs.probe(r"\b[a-z]+:", n=N, budget_ms=BUDGET_MS)
        self.assertLessEqual(ms, BUDGET_MS, "加词首边界后应线性")


class RepoTest(unittest.TestCase):
    def test_repo_regexes_are_linear(self):
        issues, stats = rs.scan(str(ROOT), n=N, budget_ms=BUDGET_MS)
        self.assertGreaterEqual(stats["patterns"], 100, "扫描面过窄（regex 库存异常）：%s" % stats)
        self.assertEqual([], issues, "仓库正则出现超线性回溯：\n%s" % "\n".join(issues[:5]))

    def test_citation_patterns_are_single_source(self):
        self.assertEqual(round_drill._CITE.pattern, assemble_plan._CITATION.pattern,
                         "两处引文正则已分叉（同一语义两处实现，须同步）")


if __name__ == "__main__":
    unittest.main()
