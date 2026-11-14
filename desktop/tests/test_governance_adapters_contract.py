#!/usr/bin/env python3
"""WP-31 治理 verify 适配判据（in-toto/DSSE、Sigstore、RFC3161、透明日志）。"""

import copy
import json
import shutil
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import governance_adapters as ga  # noqa: E402

REG = ROOT / ga.REL


class GovernanceAdaptersContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.reg = json.loads(REG.read_text(encoding="utf-8"))

    def test_registry_selfcheck(self):
        self.assertEqual([], ga.check(str(ROOT)))

    def test_detect_is_honest(self):
        live = ga.detect(str(ROOT))
        self.assertEqual("available", live["A-01"]["live"], "DSSE 本地实现应 available")
        if shutil.which("cosign"):
            self.assertEqual("available", live["A-02"]["live"])
        else:
            self.assertEqual("blocked", live["A-02"]["live"], "缺 cosign 必须 blocked")
        self.assertIn(live["A-03"]["live"], ("external-open", "blocked"),
                      "外部 TSA 不得冒充 available")

    def test_plan_t1_ok(self):
        plan = ga.verify_plan("T1", str(ROOT))
        self.assertTrue(plan["ok"])
        self.assertEqual(0, plan["exit_code"])
        self.assertIn("T1", plan["achievable"])

    def test_plan_t2_degraded(self):
        plan = ga.verify_plan("T2", str(ROOT))
        self.assertFalse(plan["ok"])
        self.assertTrue(plan["degraded"])
        self.assertEqual(2, plan["exit_code"], "缺适配器必须 exit 2（不可判定）")
        self.assertIn("A-03", plan["missing"])

    def test_plan_t4_never_faked(self):
        plan = ga.verify_plan("T4", str(ROOT))
        self.assertFalse(plan["ok"])
        self.assertLess(plan["achievable"], "T4", "缺工具/缺锚不得声称 T4")
        self.assertTrue(plan["missing"])

    def test_unknown_level_rejected(self):
        with self.assertRaises(ga.AdapterError) as ctx:
            ga.verify_plan("T9", str(ROOT))
        self.assertEqual("LEVEL-UNKNOWN", ctx.exception.code)
        self.assertIn("修复指引", ctx.exception.message)

    def test_registry_mutations_red(self):
        def check_doc(mutate):
            doc = copy.deepcopy(self.reg)
            mutate(doc)
            original = REG.read_text(encoding="utf-8")
            try:
                REG.write_text(json.dumps(doc, ensure_ascii=False, indent=2),
                               encoding="utf-8", newline="\n")
                return ga.check(str(ROOT))
            finally:
                REG.write_text(original, encoding="utf-8", newline="\n")

        def drop_reason(doc):
            next(a for a in doc["adapters"] if a["availability"] == "blocked").pop(
                "blocked_reason", None)

        self.assertTrue(check_doc(drop_reason), "blocked 缺理由必须红")

        def bad_level_ref(doc):
            doc["level_requirements"]["T4"].append("A-99")

        self.assertTrue(check_doc(bad_level_ref), "等级映射引用未登记适配器必须红")

        def missing_impl(doc):
            doc["adapters"][0]["local_impl"] = "desktop/src/core/nonexistent_zzz.py"

        self.assertTrue(check_doc(missing_impl), "本地实现不在场必须红")


if __name__ == "__main__":
    unittest.main()
