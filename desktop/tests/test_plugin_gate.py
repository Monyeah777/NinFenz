"""P5-10 晋升门判据：三条缺一不可，**不通过与通过一样是交付物**。

计划 §18.4 的三条判据在真测量下会给出不同答案（本机实测：1 MiB 输入插件快 2.8×；
32 MiB 输入插件慢 0.8×）。故门的两侧都必须可机检——只测通过路径的门等于没有门。
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "desktop" / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import plugin_gate as pg  # noqa: E402


def _evidence(**kw):
    base = {"face": "sha256", "baseline_ms": 300.0, "plugin_ms": 30.0,
            "arbitration": {"outcome": "PASS", "comparable": 2},
            "toolchain": {"available": True, "kind": "wasm32-wasip1+wasmtime",
                          "toolchain_cost": 1}}
    base.update(kw)
    return base


class PromotePathTest(unittest.TestCase):
    def test_all_three_criteria_met_promotes(self):
        rep = pg.decide(_evidence())
        self.assertTrue(rep["promoted"], rep["reasons"])
        self.assertTrue(pg.gate_ok(rep))
        self.assertEqual([], rep["reasons"])
        self.assertEqual(10.0, rep["measured"]["speedup"])


class RejectPathTest(unittest.TestCase):
    def test_slow_plugin_is_not_promoted(self):
        rep = pg.decide(_evidence(baseline_ms=100.0, plugin_ms=125.0))
        self.assertFalse(rep["promoted"])
        self.assertFalse(rep["criteria"]["speedup"]["ok"])
        self.assertTrue(any("加速" in r for r in rep["reasons"]), rep["reasons"])

    def test_spec_gap_is_never_a_pass(self):
        rep = pg.decide(_evidence(arbitration={"outcome": "SPEC-GAP", "comparable": 3}))
        self.assertFalse(rep["promoted"])
        self.assertFalse(rep["criteria"]["byte_equivalence"]["ok"])
        self.assertTrue(rep["invariants"]["spec_gap_is_not_a_pass"])

    def test_single_comparable_is_not_enough(self):
        rep = pg.decide(_evidence(arbitration={"outcome": "PASS", "comparable": 1}))
        self.assertFalse(rep["criteria"]["byte_equivalence"]["ok"])

    def test_unknown_arbitration_is_not_enough(self):
        rep = pg.decide(_evidence(arbitration={"outcome": "UNKNOWN", "comparable": 0}))
        self.assertFalse(rep["promoted"])

    def test_missing_timings_is_not_enough(self):
        rep = pg.decide(_evidence(plugin_ms=None))
        self.assertFalse(rep["criteria"]["speedup"]["ok"])
        self.assertIsNone(rep["measured"]["speedup"])

    def test_absent_toolchain_blocks_even_when_fast(self):
        rep = pg.decide(_evidence(toolchain={"available": False, "toolchain_cost": 1}))
        self.assertFalse(rep["promoted"])
        self.assertFalse(rep["criteria"]["toolchain_cost"]["ok"])

    def test_costly_toolchain_blocks(self):
        rep = pg.decide(_evidence(toolchain={"available": True, "toolchain_cost": 9}))
        self.assertFalse(rep["criteria"]["toolchain_cost"]["ok"])

    def test_thresholds_are_overridable(self):
        rep = pg.decide(_evidence(baseline_ms=30.0, plugin_ms=27.0),
                        {"min_speedup": 1.05})
        self.assertTrue(rep["promoted"], rep["reasons"])


class InvariantTest(unittest.TestCase):
    def test_reference_and_correctness_path_invariants_are_reported(self):
        inv = pg.decide(_evidence())["invariants"]
        self.assertTrue(inv["reference_always_present"])
        self.assertTrue(inv["plugin_never_on_correctness_path"])

    def test_ratchet_flags_a_vanished_promoted_face(self):
        self.assertEqual(["已晋升面消失：sha256"],
                         pg.ratchet([], ["sha256"]))
        self.assertEqual([], pg.ratchet(["sha256", "jcs"], ["sha256"]))
        self.assertEqual([], pg.ratchet([], []))


if __name__ == "__main__":
    unittest.main()
