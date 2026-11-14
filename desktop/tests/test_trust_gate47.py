#!/usr/bin/env python3
"""check47 判据自身判据：真仓全绿 + 变异必红（T3 组合 / T4 不声称 / parity 独立）。"""
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core.trust import gate_g4  # noqa: E402


class RealRepoTest(unittest.TestCase):
    def test_clean_and_deterministic(self):
        first = gate_g4.scan(str(ROOT))
        self.assertEqual([], first[0], first[0])
        stats = first[1]
        self.assertEqual("T3", stats["t3"])
        self.assertEqual(0, stats["t3_exit"])
        self.assertEqual(7, stats["parity_families"])
        self.assertEqual(first, gate_g4.scan(str(ROOT)))


class MutationRedTest(unittest.TestCase):
    def test_t3_not_reached_is_caught(self):
        real = gate_g4.tv.verify

        def fake(bundle, policy, root=".", **kwargs):
            result = real(bundle, policy, root, **kwargs)
            result["report"]["level"]["achieved"] = "T2"
            result["exit_code"] = 2
            return result

        with mock.patch.object(gate_g4.tv, "verify", fake):
            issues, _stats = gate_g4.scan(str(ROOT))
        self.assertTrue(any("T3" in i for i in issues), issues)

    def test_t4_claimed_is_caught(self):
        real = gate_g4.tv.verify

        def fake(bundle, policy, root=".", **kwargs):
            result = real(bundle, policy, root, **kwargs)
            if policy.get("required_level") == "T4":
                result["report"]["level"]["achieved"] = "T4"
                result["exit_code"] = 0
                result["report"]["issues"] = []
            return result

        with mock.patch.object(gate_g4.tv, "verify", fake):
            issues, _stats = gate_g4.scan(str(ROOT))
        self.assertTrue(any("T4" in i for i in issues), issues)

    def test_threshold_weakening_is_caught(self):
        real = gate_g4.tv.verify

        def fake(bundle, policy, root=".", **kwargs):
            result = real(bundle, policy, root, **kwargs)
            if (policy.get("anchors") or {}).get("witness_threshold") == 2:
                result["exit_code"] = 0
                result["report"]["level"]["achieved"] = "T3"
            return result

        with mock.patch.object(gate_g4.tv, "verify", fake):
            issues, _stats = gate_g4.scan(str(ROOT))
        self.assertTrue(any("阈值" in i for i in issues), issues)

    def test_parity_script_missing_is_red(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / "results" / "trust").mkdir(parents=True)
            shutil.copy2(ROOT / "results" / "trust" / "trust_vectors.json",
                         base / "results/trust/trust_vectors.json")
            (base / "desktop" / "tests").mkdir(parents=True)
            issues, _stats = gate_g4.scan(str(base))
        self.assertTrue(any("独立 parity 实现" in i for i in issues), issues)

    def test_parity_impure_implementation_is_red(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / "scripts/trust_parity").mkdir(parents=True)
            (base / "results/trust").mkdir(parents=True)
            shutil.copy2(ROOT / "results" / "trust" / "trust_vectors.json",
                         base / "results/trust/trust_vectors.json")
            (base / "desktop/tests").mkdir(parents=True)
            (base / "scripts/trust_parity/verify.mjs").write_text(
                "// uses desktop/src/core.trust + python\n", encoding="utf-8")
            issues, _stats = gate_g4.scan(str(base))
        self.assertTrue(any("不独立" in i for i in issues), issues)


if __name__ == "__main__":
    unittest.main()
