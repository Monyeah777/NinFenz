"""Cognition Event：manifest+journal → 可复算事件；无评分；事件库。"""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core.meta_cockpit import cognition_event as ce  # noqa: E402

MANIFEST = {
    "schema": "nf-cockpit-manifest/1",
    "prompt_digest": "a" * 64, "machine_digest": "b" * 64, "runtime_digest": "c" * 64,
    "journal_digest": "d" * 64, "handoff_digest": "e" * 64, "context_digest": "f" * 64,
    "status": "pass", "termination": "max-turns", "complete": False, "turns": 2,
    "context_units_spent": 100, "abstention_status": "evidence-required",
    "human_action_required": True,
}
JOURNAL = {"events": [
    {"seq": 1, "status": "pass", "event_digest": "1" * 64,
     "atom_trace": [{"atom_id": "k.partition"}, {"atom_id": "e.falsify"}]},
    {"seq": 2, "status": "pass", "event_digest": "2" * 64,
     "atom_trace": [{"atom_id": "s.synthesize"}]},
]}


class CognitionEventTest(unittest.TestCase):
    def test_build_verify_and_atoms(self):
        ev = ce.build(MANIFEST, JOURNAL)
        self.assertEqual([], ce.verify(ev))
        self.assertEqual(["k.partition", "e.falsify", "s.synthesize"], ev["atoms"])
        self.assertEqual(2, len(ev["rounds"]))
        self.assertTrue(ev["no_scoring"])
        self.assertEqual(ce.build(MANIFEST, JOURNAL)["digest"], ev["digest"])

    def test_tamper_detected(self):
        ev = ce.build(MANIFEST, JOURNAL)
        ev["status"] = "fail"
        self.assertIn("digest", ce.verify(ev))

    def test_store_and_load(self):
        old = os.environ.get("NF_COCKPIT_HOME")
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["NF_COCKPIT_HOME"] = tmp
            try:
                ev = ce.build(MANIFEST, JOURNAL)
                ce.write(ev)
                self.assertEqual(ev["digest"], ce.load(ev["digest"])["digest"])
            finally:
                if old is None: os.environ.pop("NF_COCKPIT_HOME", None)
                else: os.environ["NF_COCKPIT_HOME"] = old

    def test_bad_manifest_rejected(self):
        with self.assertRaises(ValueError):
            ce.build({"schema": "x"})
