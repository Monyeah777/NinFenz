"""结论可复用性查询判据：current / stale / unknown 三态都要判得出来。

依据（第 101 轮）：自省层让「工具改了没重跑」在仓库里变红；但只要手里有一份结论文件，
还需要一个直接答案：这份结论还能不能引用。本件只测查询逻辑（不跑全量）。
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "desktop" / "src"))
import verifier_status as vs  # noqa: E402


class VerifierStatusTest(unittest.TestCase):
    def test_repo_state_is_current(self):
        doc = vs.build()
        self.assertEqual("nf-verifier-status/1", doc["schema"])
        self.assertEqual("current", doc["status"], doc)
        self.assertEqual(doc["recorded"], doc["current"])

    def test_unknown_digest_is_stale(self):
        doc = vs.build(digest="0" * 64)
        self.assertEqual("stale", doc["status"], doc)

    def test_conclusion_file_roundtrip(self):
        """把当前摘要写成一份「结论文件」，查询必须判 current。"""
        current = vs._current_digest()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "conclusion.json"
            path.write_text(json.dumps({"schema": "nf-release-conclusion/1",
                                        "verifier_digest": current}), encoding="utf-8")
            doc = vs.build(conclusion=str(path))
        self.assertEqual("current", doc["status"], doc)
        self.assertIn("conclusion.json", doc["source"])

    def test_no_source_is_unknown(self):
        """既没给文件也没给摘要、仓库记录缺失时，必须如实说 unknown（不是 current）。"""
        original = vs.SELF_AUDIT_REL
        try:
            vs.SELF_AUDIT_REL = "results/ccos/does_not_exist_xyz.json"
            doc = vs.build()
        finally:
            vs.SELF_AUDIT_REL = original
        self.assertEqual("unknown", doc["status"], doc)


if __name__ == "__main__":
    unittest.main()
