#!/usr/bin/env python3
"""judge 校准单测：整体/分类别 kappa、样本量门、位置/长度偏差、fail-closed。"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

if str(Path(__file__).resolve().parent.parent / "src") not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from core import judge_calibration as jc

ROOT = Path(__file__).resolve().parents[2]


def rows(category: str, human: str, judge: str, n: int, output: str = "x"):
    return [{"category": category, "human": human, "judge": judge,
             "output": output} for _ in range(n)]


class JudgeCalibrationTest(unittest.TestCase):
    def test_perfect_category_is_reliable(self):
        out = jc.calibrate(rows("math", "pass", "pass", 6)
                           + rows("math", "fail", "fail", 2))
        self.assertEqual(out["schema"], "nf-judge-calibration/1")
        self.assertAlmostEqual(out["kappa"], 1.0)
        self.assertIn("math", out["reliable"])


    def test_constant_labels_are_perfect(self):
        out = jc.calibrate(rows("math", "pass", "pass", 8))
        self.assertAlmostEqual(out["kappa"], 1.0)
        self.assertIn("math", out["reliable"])

    def test_small_category_never_reliable(self):
        out = jc.calibrate(rows("tiny", "pass", "pass", 3), min_category_n=8)
        self.assertIn("tiny", out["not_reliable"])

    def test_anti_correlated_category_not_reliable(self):
        data = (rows("refusals", "pass", "fail", 4)
                + rows("refusals", "fail", "pass", 4))
        out = jc.calibrate(data, min_category_n=8)
        self.assertIn("refusals", out["not_reliable"])
        self.assertLess(out["kappa"], 0.6)

    def test_position_probe(self):
        data = rows("math", "pass", "pass", 2)
        data[0].update({"pick_original": "a", "pick_swapped": "b"})
        data[1].update({"pick_original": "b", "pick_swapped": "b"})
        out = jc.calibrate(data, min_category_n=1)
        self.assertEqual(out["position"]["n"], 2)
        self.assertEqual(out["position"]["flips"], 1)
        self.assertEqual(out["position"]["first_position_wins"], 1)

    def test_verbosity_signal(self):
        data = ([{"category": "c", "human": "pass", "judge": "pass", "output": "long output"}
                 for _ in range(4)]
                + [{"category": "c", "human": "pass", "judge": "fail", "output": "x"}
                   for _ in range(4)])
        out = jc.calibrate(data, min_category_n=1)
        self.assertGreater(out["verbosity"]["correlation"], 0.0)


    def test_cli_json_and_gate(self):
        data = (rows("math", "pass", "pass", 6) + rows("math", "fail", "fail", 2)
                + rows("refusals", "pass", "fail", 4)
                + rows("refusals", "fail", "pass", 4))
        with tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False,
                                         encoding="utf-8") as fh:
            for row in data:
                fh.write(json.dumps(row) + "\n")
            path = fh.name
        try:
            proc = subprocess.run(
                [sys.executable, "scripts/judge_calibrate.py", "--labeled", path, "--json"],
                cwd=ROOT, capture_output=True, text=True, check=False)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            out = json.loads(proc.stdout)
            self.assertEqual(out["schema"], "nf-judge-calibration/1")
            self.assertIn("refusals", out["not_reliable"])
            gate = subprocess.run(
                [sys.executable, "scripts/judge_calibrate.py", "--labeled", path, "--gate"],
                cwd=ROOT, capture_output=True, text=True, check=False)
            self.assertEqual(gate.returncode, 1, gate.stderr)
        finally:
            Path(path).unlink(missing_ok=True)

    def test_cli_fail_closed(self):
        with tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False,
                                         encoding="utf-8") as fh:
            fh.write("{not json}\n")
            path = fh.name
        try:
            proc = subprocess.run(
                [sys.executable, "scripts/judge_calibrate.py", "--labeled", path],
                cwd=ROOT, capture_output=True, text=True, check=False)
            self.assertEqual(proc.returncode, 2)
            self.assertIn("不是 JSON", proc.stderr)
        finally:
            Path(path).unlink(missing_ok=True)

    def test_fail_closed(self):
        with self.assertRaises(ValueError):
            jc.calibrate([])
        with self.assertRaises(ValueError):
            jc.calibrate([{"category": "c", "human": "pass"}])
        with self.assertRaises(ValueError):
            jc.calibrate(rows("c", "pass", "pass", 1), kappa_threshold=2.0)
        with self.assertRaises(ValueError):
            jc.calibrate(rows("c", "pass", "pass", 1), min_category_n=0)


if __name__ == "__main__":
    unittest.main()
