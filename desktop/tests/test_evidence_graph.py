"""证据图探针判据：H 必须可算、口径写死、且对「没收口的陈述」会变红。

依据（第 48 轮设计：资产=二部图，幻觉=悬挂陈述边）：
① 每条台账陈述至少有一条证据边（H=0）——否则说明台账里有「说了但没证」的条目；
② 判据**自身不空转**：把某条 entry 的 criteria/evidence 清空后重算，H 必须 > 0；
③ 探针可复现。
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "desktop" / "src"))
import evidence_graph_probe as probe  # noqa: E402


class EvidenceGraphTest(unittest.TestCase):
    def test_ledger_has_no_dangling_claims(self):
        doc = probe.build()
        self.assertEqual("nf-evidence-graph/1", doc["schema"])
        self.assertGreaterEqual(doc["claims"], 20)
        self.assertEqual([], doc["dangling"],
                         f"这些陈述没有任何证据边（说了但没证）：{doc['dangling']}")
        self.assertEqual(0.0, doc["h_dangling_ratio"])

    def test_probe_is_not_vacuous(self):
        """清空一条 entry 的证据后 H 必须 > 0（证明判据真的在算边）。"""
        ledger = json.loads((ROOT / "protocol" / "closure" / "ledger.json")
                            .read_text(encoding="utf-8"))
        victim = ledger["entries"][0]["id"]
        ledger["entries"][0]["criteria"] = []
        ledger["entries"][0]["evidence"] = []
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "protocol" / "closure").mkdir(parents=True)
            (root / "protocol" / "closure" / "ledger.json").write_text(
                json.dumps(ledger, ensure_ascii=False), encoding="utf-8")
            doc = probe.build(root)
        self.assertEqual([victim], doc["dangling"])
        self.assertGreater(doc["h_dangling_ratio"], 0.0)

    def test_reproducible(self):
        self.assertEqual(probe.render(probe.build()), probe.render(probe.build()))


if __name__ == "__main__":
    unittest.main()
