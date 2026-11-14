#!/usr/bin/env python3
"""WP-43 AIGC/标注证据判据（机器可读标识 + 绑定 + 引用闭合）。"""

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import aigc_labeling as al  # noqa: E402

REG = ROOT / al.REL
LABEL = ROOT / "results/ai/aigc-label.json"


class AIGCLabelingContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.reg = json.loads(REG.read_text(encoding="utf-8"))
        cls.label = json.loads(LABEL.read_text(encoding="utf-8"))
        cls.card = json.loads((ROOT / al.CARD_REL).read_text(encoding="utf-8"))

    def test_registry_and_check_green(self):
        self.assertEqual("nf-aigc-labeling/1", self.reg["schema"])
        self.assertEqual([], al.check(str(ROOT)))

    def test_committed_equals_live(self):
        live = al.build_sample(str(ROOT))
        live.pop("label_rel")
        self.assertEqual(json.dumps(live, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                         LABEL.read_text(encoding="utf-8"))

    def test_label_bindings(self):
        self.assertEqual(self.card["model_digest"], self.label["generator"]["model_digest"])
        import hashlib
        subject = (ROOT / al.SUBJECT).read_bytes()
        self.assertEqual(hashlib.sha256(subject).hexdigest(), self.label["subject_digest"])
        self.assertIn(self.label["label"], self.reg["label_vocabulary"])

    def test_missing_label(self):
        import shutil
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "protocol").mkdir()
            shutil.copy(ROOT / al.REL, Path(tmp) / "protocol" / "aigc_labeling.json")
            with self.assertRaises(al.LabelError) as ctx:
                al.load_sample(tmp)
        self.assertEqual("LABEL-MISSING", ctx.exception.code)
        self.assertIn("修复指引", ctx.exception.message)

    def test_unlabeled_not_default_human(self):
        issues = al.check_label({}, str(ROOT))
        self.assertTrue(issues)
        self.assertTrue(any("label" in i for i in issues))

    def test_tampered_subject_red(self):
        bad = copy.deepcopy(self.label)
        bad["subject_digest"] = "0" * 64
        self.assertTrue(any("subject_digest" in i for i in al.check_label(bad, str(ROOT))))

    def test_wrong_model_red(self):
        bad = copy.deepcopy(self.label)
        bad["generator"]["model_digest"] = "f" * 64
        self.assertTrue(any("model_digest" in i for i in al.check_label(bad, str(ROOT))))

    def test_ref_out_of_bounds_red(self):
        bad = copy.deepcopy(self.label)
        bad["provenance_refs"] = ["README.md"]
        issues = al.check_label(bad, str(ROOT))
        self.assertTrue(any("越界" in i for i in issues), issues)
        bad2 = copy.deepcopy(self.label)
        bad2["provenance_refs"] = ["results/ai/nonexistent.json"]
        self.assertTrue(any("不在场" in i for i in al.check_label(bad2, str(ROOT))))

    def test_human_label_needs_approve(self):
        bad = copy.deepcopy(self.label)
        bad["label"] = "human"
        review_path = ROOT / al.REVIEW_REL
        original = review_path.read_text(encoding="utf-8")
        try:
            review = json.loads(original)
            review["decision"] = "reject"
            review_path.write_text(json.dumps(review, ensure_ascii=False), encoding="utf-8",
                                   newline="\n")
            issues = al.check_label(bad, str(ROOT))
        finally:
            review_path.write_text(original, encoding="utf-8", newline="\n")
        self.assertTrue(any("human" in i for i in issues), issues)

    def test_deterministic(self):
        a = al.build_sample(str(ROOT))
        b = al.build_sample(str(ROOT))
        a.pop("label_rel"); b.pop("label_rel")
        self.assertEqual(json.dumps(a, sort_keys=True), json.dumps(b, sort_keys=True))


if __name__ == "__main__":
    unittest.main()
