"""论文台账判据（第 2026-11-10 批）：处置完整、落点可核、计数自洽。

为什么必须有：论文筛选的价值不在于「列了多少篇」，而在于**每篇的处置可追溯**——
是移植进了仓（有落点与判据面）、还是判定不适用/暂缓（有理由）。没有这条判据，
台账会退化成「看起来读了很多」的清单。
"""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import paper_ledger as pl  # noqa: E402


class PaperLedgerTest(unittest.TestCase):
    def setUp(self):
        self.doc = pl.load()

    def test_ledger_is_self_consistent(self):
        """结构 + 引用面 + 计数三面一起核（check 已含全部规则）。"""
        self.assertEqual([], pl.check(self.doc), "台账不自洽")

    def test_every_entry_has_disposition_and_reason(self):
        """每篇都必须有处置与理由——这是「系统化」的最低门槛。"""
        for e in self.doc["entries"]:
            self.assertIn(e["disposition"], pl.DISPOSITIONS, e["id"])
            self.assertTrue(str(e.get("reason") or "").strip(), e["id"] + " 缺理由")

    def test_adopted_entries_cite_existing_surfaces(self):
        """adopted 必须有仓内落点 + 证据面，且文件真实存在（引用面判据）。"""
        adopted = [e for e in self.doc["entries"] if e["disposition"] == "adopted"]
        self.assertGreaterEqual(len(adopted), 15, "移植篇数过少，判据可能已失效")
        for e in adopted:
            self.assertTrue(e["targets"], e["id"] + " 无落点")
            self.assertTrue(e["evidence"], e["id"] + " 无证据面")
            for rel in e["targets"] + e["evidence"]:
                self.assertTrue((ROOT / rel).exists(), f"{e['id']} 引用不存在：{rel}")

    def test_disposition_counts_match_declared(self):
        self.assertEqual(pl.counts(self.doc["entries"]), self.doc["counts"])
        self.assertEqual(len(self.doc["entries"]), self.doc["count"])

    def test_check_rejects_malformed_ledger(self):
        """变异自证：缺理由 / 悬空落点 / 计数漂移 三种坏件都必须报。"""
        bad = json.loads(json.dumps(self.doc))
        bad["entries"][0]["reason"] = ""
        self.assertTrue(pl.check(bad), "缺理由必须报")
        bad2 = json.loads(json.dumps(self.doc))
        bad2["entries"][0]["disposition"] = "adopted"
        bad2["entries"][0]["targets"] = ["scripts/definitely_missing_file.py"]
        self.assertTrue(pl.check(bad2), "悬空落点必须报")
        bad3 = json.loads(json.dumps(self.doc))
        bad3["count"] = 999
        self.assertTrue(pl.check(bad3), "计数漂移必须报")


if __name__ == "__main__":
    unittest.main()
