#!/usr/bin/env python3
"""WP-42 策略适配判据（外置规则集 + 默认拒绝 + 优先级 + 可复算判定）。"""

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import governance_adapters as ga  # noqa: E402
from core import policy_engine as pe  # noqa: E402

REG = ROOT / pe.REL


class PolicyEngineContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.reg = json.loads(REG.read_text(encoding="utf-8"))

    def test_registry_selfcheck(self):
        self.assertEqual([], pe.check_registry(str(ROOT)))
        self.assertEqual("deny", self.reg["default_effect"])

    def test_t1_allowed(self):
        d = pe.evaluate({"required_level": "T1", "contract_status": "active",
                         "has_evidence": True, "attachment_mode": "none"}, str(ROOT))
        self.assertTrue(d["allowed"])
        self.assertEqual("allow", d["effect"])
        self.assertIn("P-005", d["matched"])

    def test_t4_denied(self):
        d = pe.evaluate({"required_level": "T4", "contract_status": "active",
                         "has_evidence": True}, str(ROOT))
        self.assertFalse(d["allowed"])
        self.assertIn("P-004", d["matched"])
        plan = ga.verify_plan("T4", str(ROOT))
        self.assertFalse(plan["ok"], "策略 deny 必须与适配器不可达一致")

    def test_require_without_evidence_denied(self):
        d = pe.evaluate({"required_level": "T1", "contract_status": "active",
                         "has_evidence": False, "attachment_mode": "require"}, str(ROOT))
        self.assertFalse(d["allowed"])
        self.assertIn("P-002", d["matched"])

    def test_retired_contract_denied_by_priority(self):
        d = pe.evaluate({"required_level": "T1", "contract_status": "retired",
                         "has_evidence": True, "attachment_mode": "none"}, str(ROOT))
        self.assertFalse(d["allowed"])
        self.assertIn("P-001", d["matched"], "retired deny 优先级最高")

    def test_default_deny(self):
        d = pe.evaluate({"required_level": "T1"}, str(ROOT))
        self.assertFalse(d["allowed"])
        self.assertEqual("deny", d["effect"])
        self.assertEqual([], d["matched"])
        self.assertIn("默认拒绝", d["reason"])

    def test_missing_facts_rejected(self):
        with self.assertRaises(pe.PolicyError) as ctx:
            pe.evaluate({}, str(ROOT))
        self.assertEqual("FACTS-MISSING", ctx.exception.code)
        self.assertIn("修复指引", ctx.exception.message)

    def test_deterministic(self):
        facts = {"required_level": "T2", "contract_status": "active", "has_evidence": True}
        self.assertEqual(json.dumps(pe.evaluate(facts, str(ROOT)), sort_keys=True),
                         json.dumps(pe.evaluate(facts, str(ROOT)), sort_keys=True))

    def test_registry_mutations_red(self):
        def check_doc(mutate):
            doc = copy.deepcopy(self.reg)
            mutate(doc)
            original = REG.read_text(encoding="utf-8")
            try:
                REG.write_text(json.dumps(doc, ensure_ascii=False, indent=2),
                               encoding="utf-8", newline="\n")
                return pe.check_registry(str(ROOT))
            finally:
                REG.write_text(original, encoding="utf-8", newline="\n")

        def allow_default(doc):
            doc["default_effect"] = "allow"

        self.assertTrue(check_doc(allow_default), "默认放行必须红")

        def bad_effect(doc):
            doc["rules"][0]["effect"] = "maybe"

        self.assertTrue(check_doc(bad_effect), "非法 effect 必须红")

        def unknown_fact(doc):
            doc["rules"][0]["when"] = {"surprise": True}

        self.assertTrue(check_doc(unknown_fact), "未知事实必须红")

    def test_claims_boundary(self):
        boundary = " ".join(self.reg.get("claims_boundary") or [])
        self.assertIn("不声称", boundary)


if __name__ == "__main__":
    unittest.main()
