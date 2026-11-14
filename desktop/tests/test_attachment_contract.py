#!/usr/bin/env python3
"""WP-32 治理附件模式判据（none/observe/require + 生产独立性）。"""

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import attachment as at  # noqa: E402
from core import assembly_runtime as ar  # noqa: E402

INTENT = "spec/intents/sample-document.json"
REG = ROOT / at.REL


class AttachmentContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.reg = json.loads(REG.read_text(encoding="utf-8"))
        cls.record = ar.run(INTENT, "mock", str(ROOT))

    def test_registry_selfcheck(self):
        self.assertEqual([], at.check_registry(str(ROOT)))
        self.assertEqual({"none", "observe", "require"}, set(at.modes(str(ROOT))))

    def test_none_passes_without_evidence(self):
        report = at.evaluate("none", {}, str(ROOT))
        self.assertTrue(report["passed"])
        self.assertEqual(0, report["exit_code"])
        self.assertEqual([], report["observations"])

    def test_observe_never_blocks(self):
        report = at.evaluate("observe", {"bundle_present": False}, str(ROOT))
        self.assertTrue(report["passed"], "observe 缺证据不得阻塞")
        self.assertTrue(report["observations"])
        self.assertIn("WARN", report["observations"][0])
        self.assertTrue(report["evidence"]["bundle_present"] is False)

    def test_require_rejects_missing(self):
        with self.assertRaises(at.AttachmentError) as ctx:
            at.evaluate("require", {"bundle_present": False}, str(ROOT))
        self.assertEqual("ATTACHMENT-MISSING", ctx.exception.code)
        self.assertEqual(2, ctx.exception.code and 2)
        self.assertIn("修复指引", ctx.exception.message)

    def test_require_rejects_unverified(self):
        ev = {"bundle_present": True, "verification": {"ok": False, "level": "T1"}}
        with self.assertRaises(at.AttachmentError) as ctx:
            at.evaluate("require", ev, str(ROOT))
        self.assertEqual("ATTACHMENT-NOT-VERIFIED", ctx.exception.code)

    def test_require_rejects_low_level(self):
        ev = {"bundle_present": True, "verification": {"ok": True, "level": "T0"}}
        with self.assertRaises(at.AttachmentError) as ctx:
            at.evaluate("require", ev, str(ROOT))
        self.assertEqual("ATTACHMENT-LEVEL-LOW", ctx.exception.code)

    def test_require_passes_with_t1(self):
        ev = {"bundle_present": True, "verification": {"ok": True, "level": "T1"}}
        report = at.evaluate("require", ev, str(ROOT))
        self.assertTrue(report["passed"])
        self.assertEqual(0, report["exit_code"])

    def test_independence_of_production(self):
        """三模式评估不得改变生产记录（纯函数）；摘要逐字节一致。"""
        digest_before = at.independence_digest(self.record)
        for mode in ("none", "observe", "require"):
            try:
                at.evaluate(mode, {"bundle_present": True,
                                   "verification": {"ok": True, "level": "T1"}}, str(ROOT))
            except at.AttachmentError:
                pass
            after = ar.run(INTENT, "mock", str(ROOT))
            self.assertEqual(at.independence_digest(after), digest_before,
                             "%s 评估改变了生产产物" % mode)
            self.assertEqual(ar.render(self.record), ar.render(after))

    def test_unknown_mode_rejected(self):
        with self.assertRaises(at.AttachmentError) as ctx:
            at.evaluate("bogus", {}, str(ROOT))
        self.assertEqual("MODE-UNKNOWN", ctx.exception.code)
        self.assertIn("修复指引", ctx.exception.message)

    def test_registry_mutations_red(self):
        def check_doc(mutate):
            doc = copy.deepcopy(self.reg)
            mutate(doc)
            original = REG.read_text(encoding="utf-8")
            try:
                REG.write_text(json.dumps(doc, ensure_ascii=False, indent=2),
                               encoding="utf-8", newline="\n")
                return at.check_registry(str(ROOT))
            finally:
                REG.write_text(original, encoding="utf-8", newline="\n")

        def no_blocking(doc):
            next(m for m in doc["modes"] if m["id"] == "require")["blocking"] = False

        self.assertTrue(check_doc(no_blocking), "require 不阻塞必须红")

        def no_min_level(doc):
            next(m for m in doc["modes"] if m["id"] == "require")["min_level"] = ""

        self.assertTrue(check_doc(no_min_level), "require 缺 min_level 必须红")


if __name__ == "__main__":
    unittest.main()
