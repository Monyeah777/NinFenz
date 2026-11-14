#!/usr/bin/env python3
"""check48 判据自身判据：真仓全绿 + 变异必红（交付件/claim 口径/自审计/PASS 基线）。"""
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core.trust import gate_dod  # noqa: E402

FILES = {
    "results/trust/BASELINE.md": "results/trust/BASELINE.md",
    "results/trust/CLAIM_MATRIX.md": "results/trust/CLAIM_MATRIX.md",
    "results/trust/SELF_AUDIT.json": "results/trust/SELF_AUDIT.json",
    "results/trust/DOD.md": "results/trust/DOD.md",
    "docs/trust/SELF_AUDIT.md": "docs/trust/SELF_AUDIT.md",
    "docs/trust/THREAT_MODEL.md": "docs/trust/THREAT_MODEL.md",
    "docs/trust/WITNESS_SPEC.md": "docs/trust/WITNESS_SPEC.md",
    "verify.sh": "verify.sh",
}


def _repo(tmp: Path) -> Path:
    for rel, source in FILES.items():
        target = tmp / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / source, target)
    return tmp


class RealRepoTest(unittest.TestCase):
    def test_clean_and_deterministic(self):
        first = gate_dod.scan(str(ROOT))
        self.assertEqual([], first[0], first[0])
        stats = first[1]
        self.assertEqual(7, stats["files"])
        self.assertGreaterEqual(stats["claims"], 30)
        self.assertEqual(0, stats["todo"])
        self.assertEqual(0, stats["unsupported"])
        self.assertEqual(0, stats["p0"])
        self.assertEqual(first, gate_dod.scan(str(ROOT)))


class MutationRedTest(unittest.TestCase):
    def _scan(self, tmp):
        return gate_dod.scan(str(tmp))[0]

    def test_missing_artifact_is_red(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = _repo(Path(tmp))
            (base / "results/trust/DOD.md").unlink()
            issues = self._scan(base)
        self.assertTrue(any("交付件" in i for i in issues), issues)

    def test_todo_or_unsupported_claim_is_red(self):
        for marker in ("TODO", "UNSUPPORTED"):
            with tempfile.TemporaryDirectory() as tmp:
                base = _repo(Path(tmp))
                matrix = base / "results/trust/CLAIM_MATRIX.md"
                text = matrix.read_text(encoding="utf-8")
                rows = [ln for ln in text.splitlines()
                        if ln.startswith("|") and ln.strip("|").split("|")[0].strip().isdigit()]
                target = rows[0]
                mutated = target.rsplit("|", 2)[0] + "| " + marker + " |"
                matrix.write_text(text.replace(target, mutated), encoding="utf-8")
                issues = self._scan(base)
            self.assertTrue(any(marker in i for i in issues), issues)

    def test_partial_without_env_is_red(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = _repo(Path(tmp))
            matrix = base / "results/trust/CLAIM_MATRIX.md"
            text = matrix.read_text(encoding="utf-8")
            rows = [ln for ln in text.splitlines()
                    if ln.startswith("|") and ln.strip("|").split("|")[0].strip().isdigit()]
            target = rows[0]
            mutated = target.rsplit("|", 2)[0] + "| PARTIAL（缺环境标注） |"
            matrix.write_text(text.replace(target, mutated), encoding="utf-8")
            issues = self._scan(base)
        self.assertTrue(any("PARTIAL" in i and "ENV" in i for i in issues), issues)

    def test_self_audit_p0_red(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = _repo(Path(tmp))
            path = base / "results/trust/SELF_AUDIT.json"
            doc = json.loads(path.read_text(encoding="utf-8"))
            doc["stop"]["p0"] = 1
            path.write_text(json.dumps(doc), encoding="utf-8")
            issues = self._scan(base)
        self.assertTrue(any("P0" in i for i in issues), issues)

    def test_pass_baseline_mismatch_red(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = _repo(Path(tmp))
            path = base / "results/trust/SELF_AUDIT.json"
            doc = json.loads(path.read_text(encoding="utf-8"))
            doc["gate"]["verify"] = "PASS=1 WARN=0 FAIL=0"
            path.write_text(json.dumps(doc), encoding="utf-8")
            issues = self._scan(base)
        self.assertTrue(any("PASS" in i or "门禁" in i for i in issues), issues)

    def test_verify_chain_missing_is_red(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = _repo(Path(tmp))
            verify = base / "verify.sh"
            verify.write_text(verify.read_text(encoding="utf-8").replace("check45", "checkX"),
                              encoding="utf-8")
            issues = self._scan(base)
        self.assertTrue(any("check45" in i or "接线" in i for i in issues), issues)

    def test_dod_missing_env_is_red(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = _repo(Path(tmp))
            dod = base / "results/trust/DOD.md"
            dod.write_text(dod.read_text(encoding="utf-8").replace("ENV-01", "环境"),
                           encoding="utf-8")
            issues = self._scan(base)
        self.assertTrue(any("DOD" in i for i in issues), issues)


if __name__ == "__main__":
    unittest.main()
