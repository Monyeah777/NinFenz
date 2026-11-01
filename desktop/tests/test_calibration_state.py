import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from core import calibration_state as C  # noqa: E402


class Test(unittest.TestCase):
    def test_states(self):
        self.assertEqual(C.UNJUDGED, C.state(0, 5))
        self.assertEqual(C.CALIBRATION, C.state(3, 5))
        self.assertEqual(C.GATED, C.state(5, 5))

    def test_calibration_downgrades_fail(self):
        self.assertEqual(C.CALIBRATION, C.gate(C.CALIBRATION, "fail"))
        self.assertEqual("fail", C.gate(C.GATED, "fail"))
