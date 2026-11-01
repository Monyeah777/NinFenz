import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from core import claim_labels as C  # noqa: E402


class Test(unittest.TestCase):
    def test_core_contract_needs_evidence(self):
        self.assertTrue(C.validate([{"id": "X", "label": "core-contract"}]))

    def test_label_vocab(self):
        self.assertTrue(any("词表" in i for i in C.validate([{"id": "X", "label": "wish"}])))

    def test_hypothesis_ok(self):
        self.assertEqual([], C.validate([{"id": "X", "label": "product-hypothesis"}]))
