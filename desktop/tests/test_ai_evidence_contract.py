#!/usr/bin/env python3
"""WP-40 AI 证据链判据（模型卡/血缘/人类复核绑定 + 拒收状态）。"""

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import ai_evidence as ae  # noqa: E402
from core.trust import model_card as tmc  # noqa: E402

REG = ROOT / ae.REL


class AIEvidenceContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.reg = json.loads(REG.read_text(encoding="utf-8"))
        cls.sample = ae.load_sample(str(ROOT))

    def test_registry_and_check_green(self):
        self.assertEqual("nf-ai-evidence/1", self.reg["schema"])
        self.assertEqual([], ae.check(str(ROOT)))

    def test_committed_equals_live(self):
        live = ae.build_sample(str(ROOT))
        for key, rel in (("card", "results/ai/model-card.json"),
                         ("lineage", "results/ai/lineage.json"),
                         ("review", "results/ai/human-review.json")):
            self.assertEqual(json.dumps(live[key], ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                             (ROOT / rel).read_text(encoding="utf-8"), rel)

    def test_approved_state(self):
        self.assertEqual("APPROVED", ae.state(self.sample["card"], self.sample["lineage"],
                                              self.sample["review"], str(ROOT)))

    def test_missing_review_pending(self):
        self.assertEqual("PENDING", ae.state(self.sample["card"], self.sample["lineage"],
                                             None, str(ROOT)))

    def test_reject_and_escalate_states(self):
        for decision, want in (("reject", "REJECTED"), ("escalate", "ESCALATED")):
            review = copy.deepcopy(self.sample["review"])
            review["decision"] = decision
            self.assertEqual(want, ae.state(self.sample["card"], self.sample["lineage"],
                                            review, str(ROOT)))
            self.assertTrue(ae.check_ai_evidence(self.sample["card"], self.sample["lineage"],
                                                 review, str(ROOT)),
                            "%s 必须产生 issues（未 approve 不得交付）" % decision)

    def test_tampered_lineage_invalid(self):
        lineage = copy.deepcopy(self.sample["lineage"])
        lineage["segments"][0]["digest"] = "0" * 64
        issues = ae.check_ai_evidence(self.sample["card"], lineage, self.sample["review"],
                                      str(ROOT))
        self.assertTrue(issues)
        self.assertEqual("INVALID", ae.state(self.sample["card"], lineage,
                                             self.sample["review"], str(ROOT)))

    def test_eval_digest_mismatch(self):
        card = copy.deepcopy(self.sample["card"])
        card["eval_protocol"]["protocol_digest"] = "f" * 64
        issues = ae.check_ai_evidence(card, self.sample["lineage"], self.sample["review"],
                                      str(ROOT))
        self.assertTrue(any("eval_protocol" in i for i in issues), issues)

    def test_review_binding_mismatch(self):
        review = copy.deepcopy(self.sample["review"])
        review["subject_digest"] = "a" * 64
        issues = ae.check_ai_evidence(self.sample["card"], self.sample["lineage"], review,
                                      str(ROOT))
        self.assertTrue(any("subject_digest" in i for i in issues), issues)

    def test_lineage_binds_identity(self):
        """血缘必须绑模型身份摘要（model_digest+eval_protocol），不是整卡摘要。"""
        self.assertEqual(tmc.identity_digest(self.sample["card"]),
                         self.sample["lineage"]["model_card_digest"])

    def test_claims_boundary(self):
        boundary = " ".join(self.reg.get("claims_boundary") or [])
        self.assertIn("不作保证", boundary)
        self.assertIn("不声称", boundary)


if __name__ == "__main__":
    unittest.main()
