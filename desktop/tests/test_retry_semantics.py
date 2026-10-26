import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from core import retry_semantics as R  # noqa: E402


class Test(unittest.TestCase):
    def test_known_and_unknown(self):
        self.assertEqual(R.SAFE, R.semantics("NETWORK"))
        self.assertEqual(R.INSPECT, R.semantics("SOMETHING_NEW"))

    def test_exit_tiers(self):
        self.assertEqual(0, R.exit_tier("ok"))
        self.assertEqual(1, R.exit_tier("findings"))
        self.assertEqual(2, R.exit_tier("could-not-check"))
