#!/usr/bin/env python3
"""WP-51 稳定性/长稳证据判据（进程内重复 + 并发确定性，非 soak）。"""

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import stability as st  # noqa: E402

REG = ROOT / st.REL
REPORT = ROOT / st.REPORT_REL


class StabilityContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.reg = json.loads(REG.read_text(encoding="utf-8"))
        cls.report = json.loads(REPORT.read_text(encoding="utf-8"))

    def test_registry(self):
        self.assertEqual("nf-stability/1", self.reg["schema"])
        ids = [c["id"] for c in self.reg["checks"]]
        self.assertEqual(7, len(ids), "7 条纯管线必须全覆盖")
        self.assertEqual(0, self.reg["tolerance"]["mismatches"])

    def test_check_green(self):
        self.assertEqual([], st.check(str(ROOT)))

    def test_committed_equals_live(self):
        self.assertEqual(st.render(st.build(str(ROOT))), REPORT.read_text(encoding="utf-8"))

    def test_all_identical(self):
        for item in self.report["checks"]:
            self.assertTrue(item["identical"], item["id"])
            self.assertEqual(0, item["mismatches"], item["id"])
            # 每个 check 跑「串行 runs 次 + 并发 runs 次」，concurrency 是并发度不是次数
            self.assertEqual(self.report["runs"] * 2, item["runs"])
        self.assertEqual(0, self.report["summary"]["mismatches"])
        self.assertEqual(7, self.report["summary"]["checks"])

    def test_scope_honest(self):
        scope = self.report["scope"]
        self.assertTrue(scope["in_process_repeat"])
        self.assertTrue(scope["concurrent"])
        self.assertFalse(scope["soak_hours"], "不得冒充长稳 soak")
        self.assertIn("OPEN", scope["note"])
        boundary = " ".join(self.report["claims_boundary"])
        self.assertIn("不是长稳 soak", boundary)

    def test_build_deterministic(self):
        a = st.build(str(ROOT))
        b = st.build(str(ROOT))
        self.assertEqual(st.render(a), st.render(b))

    def test_mutations_red(self):
        original = REPORT.read_text(encoding="utf-8")
        try:
            bad = copy.deepcopy(self.report)
            bad["checks"][0]["identical"] = False
            bad["checks"][0]["mismatches"] = 2
            REPORT.write_text(st.render(bad), encoding="utf-8", newline="\n")
            self.assertTrue(st.check(str(ROOT)), "mismatch 必须红")

            soak = copy.deepcopy(self.report)
            soak["scope"]["soak_hours"] = True
            REPORT.write_text(st.render(soak), encoding="utf-8", newline="\n")
            self.assertTrue(st.check(str(ROOT)), "冒充 soak 必须红")
        finally:
            REPORT.write_text(original, encoding="utf-8", newline="\n")

    def test_unknown_check_rejected(self):
        with self.assertRaises(st.StabilityError) as ctx:
            st._digest_check("S-99", str(ROOT))
        self.assertEqual("CHECK-UNKNOWN", ctx.exception.code)
        self.assertIn("修复指引", ctx.exception.message)


if __name__ == "__main__":
    unittest.main()
