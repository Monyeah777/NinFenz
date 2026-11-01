"""围栏「在场但坏」判别（core.fence_health）单测。"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from core import fence_health as FH  # noqa: E402

BT = chr(96) * 3


class FencePresentTest(unittest.TestCase):
    def test_presence_ignores_parsability(self):
        good = BT + "yaml\nmachine_contract:\n  id: M00\n" + BT
        broken = BT + "yaml\nmachine_contract:\n  id: [unclosed\n" + BT
        self.assertTrue(FH.fence_present(good, "machine_contract"))
        self.assertTrue(FH.fence_present(broken, "machine_contract"))
        self.assertFalse(FH.fence_present("正文无围栏", "machine_contract"))


class ClassifyTest(unittest.TestCase):
    def test_ok(self):
        text = BT + "yaml\nmachine_contract:\n  id: M00\n" + BT
        self.assertEqual((FH.OK, {"id": "M00"}),
                         FH.classify(text, "machine_contract", {"machine_contract": {"id": "M00"}}))

    def test_absent(self):
        self.assertEqual((FH.ABSENT, None),
                         FH.classify("无围栏", "machine_contract", {}))

    def test_bad_when_present_but_unparsed(self):
        text = BT + "yaml\nmachine_contract:\n  id: [broken\n" + BT
        self.assertEqual((FH.BAD, None), FH.classify(text, "machine_contract", {}))

    def test_unavailable_when_parser_missing(self):
        text = BT + "yaml\nmachine_contract:\n  id: M00\n" + BT
        self.assertEqual((FH.UNAVAILABLE, None),
                         FH.classify(text, "machine_contract", {}, parser_available=False))


class BadFenceIssueTest(unittest.TestCase):
    def test_bad_gets_guidance(self):
        text = BT + "yaml\nmachine_contract:\n  id: [broken\n" + BT
        issue = FH.bad_fence_issue("04_模块库/通用类/M00_基座.md", text, {})
        self.assertIsNotNone(issue)
        self.assertIn("修复指引", issue)

    def test_ok_and_absent_get_none(self):
        text = BT + "yaml\nmachine_contract:\n  id: M00\n" + BT
        self.assertIsNone(FH.bad_fence_issue("x.md", text, {"machine_contract": {"id": "M00"}}))
        self.assertIsNone(FH.bad_fence_issue("x.md", "无围栏", {}))


if __name__ == "__main__":
    unittest.main()
