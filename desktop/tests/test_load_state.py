import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from core import load_state as L  # noqa: E402


class Test(unittest.TestCase):
    def test_only_stale_blocks(self):
        r = L.evaluate([{"id": "a", "expected_digest": "x", "actual_digest": "y"},
                        {"id": "b", "expected_digest": "x"},
                        {"id": "c", "expected_digest": "x", "actual_digest": "x"}])
        self.assertEqual(["a"], [x["id"] for x in r["blocking"]])
        self.assertEqual(["b"], [x["id"] for x in r["warn"]])
        self.assertEqual(["c"], [x["id"] for x in r["ok"]])
