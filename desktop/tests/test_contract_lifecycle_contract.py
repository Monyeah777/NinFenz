#!/usr/bin/env python3
"""WP-30 契约生命周期/义务判据（nf-contract/1 状态义务 + 引用策略）。"""

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import contract_lifecycle as cl  # noqa: E402

REG = ROOT / cl.REGISTRY_REL


def _contract(status="active", evidence=None, acceptance=None, constraints=None):
    doc = {"schema": "nf-contract/1", "id": "nf:test:doc", "version": 1,
           "artifact": {"kind": "doc", "digest": "a" * 64, "path": "out/doc.md"},
           "constraints": constraints if constraints is not None else [
               {"id": "C-001", "rule": "输出必须引用上下文", "severity": "MUST"}],
           "acceptance": acceptance if acceptance is not None else [{"id": "A-001"}],
           "status": status}
    if evidence is not None:
        doc["evidence"] = evidence
    elif status != "draft":
        doc["evidence"] = [{"id": "evidence:1"}]
    return doc


class ContractLifecycleContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.reg = json.loads(REG.read_text(encoding="utf-8"))

    def test_registry_selfcheck(self):
        self.assertEqual([], cl.check_registry(str(ROOT)))
        self.assertEqual({"draft", "active", "deprecated", "retired"},
                         set(cl.states(str(ROOT))))

    def test_active_contract_passes(self):
        self.assertEqual([], cl.check_contract(_contract("active"), str(ROOT)))

    def test_evidence_required(self):
        bad = _contract("active", evidence=[])
        self.assertTrue(any("evidence" in i for i in cl.check_contract(bad, str(ROOT))))

    def test_acceptance_required(self):
        bad = _contract("active", acceptance=[])
        self.assertTrue(any("acceptance" in i for i in cl.check_contract(bad, str(ROOT))))

    def test_constraint_rule_required(self):
        bad = _contract("active", constraints=[{"id": "C-001", "rule": "", "severity": "MUST"}])
        self.assertTrue(any("rule" in i for i in cl.check_contract(bad, str(ROOT))))

    def test_reference_policy(self):
        self.assertFalse(cl.can_reference("draft", True, str(ROOT)))
        self.assertTrue(cl.can_reference("active", True, str(ROOT)))
        self.assertFalse(cl.can_reference("deprecated", True, str(ROOT)), "deprecated 不得新增引用")
        self.assertTrue(cl.can_reference("deprecated", False, str(ROOT)), "deprecated 既有引用可读")
        self.assertFalse(cl.can_reference("retired", True, str(ROOT)))

    def test_unknown_status_rejected(self):
        with self.assertRaises(cl.LifecycleError) as ctx:
            cl.can_reference("unknown", True, str(ROOT))
        self.assertEqual("STATUS-UNKNOWN", ctx.exception.code)
        self.assertIn("修复指引", ctx.exception.message)
        self.assertTrue(any("不在状态词表" in i for i in
                            cl.check_contract(_contract("unknown"), str(ROOT))))

    def test_schema_invalid_contract(self):
        bad = _contract("active")
        bad["id"] = "not-a-contract-id"
        self.assertTrue(cl.check_contract(bad, str(ROOT)))

    def test_registry_mutations_red(self):
        reg = copy.deepcopy(self.reg)
        reg["states"] = [s for s in reg["states"] if s["id"] != "retired"]
        original = REG.read_text(encoding="utf-8")
        try:
            REG.write_text(json.dumps(reg, ensure_ascii=False), encoding="utf-8", newline="\n")
            issues = cl.check_registry(str(ROOT))
        finally:
            REG.write_text(original, encoding="utf-8", newline="\n")
        self.assertTrue(issues, "缺状态义务必须红")


if __name__ == "__main__":
    unittest.main()
