#!/usr/bin/env python3
"""WP-41 AIBOM 导出判据（CycloneDX AI-BOM + SPDX 风格清单）。"""

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import ai_evidence as ae  # noqa: E402
from core import aibom_export as ax  # noqa: E402

REG = ROOT / ax.REL
CDX = ROOT / ax.CDX_REL
SPDX = ROOT / ax.SPDX_REL


class AIBOMContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.reg = json.loads(REG.read_text(encoding="utf-8"))
        cls.cdx = json.loads(CDX.read_text(encoding="utf-8"))
        cls.spdx = json.loads(SPDX.read_text(encoding="utf-8"))
        cls.sample = ae.load_sample(str(ROOT))

    def test_check_green(self):
        self.assertEqual([], ax.check(str(ROOT)))

    def test_committed_equals_live(self):
        live = ax.build(str(ROOT))
        self.assertEqual(ax.render(live["cdx"]), CDX.read_text(encoding="utf-8"))
        self.assertEqual(ax.render(live["spdx"]), SPDX.read_text(encoding="utf-8"))

    def test_cyclonedx_required_and_closed(self):
        for key in self.reg["exports"]["cyclonedx"]["required"]:
            self.assertIn(key, self.cdx)
        self.assertEqual("CycloneDX", self.cdx["bomFormat"])
        comp = self.cdx["metadata"]["component"]
        self.assertEqual("machine-learning-model", comp["type"])
        model_digest = self.sample["card"]["model_digest"]
        self.assertIn(model_digest, [h["content"] for h in comp["hashes"]])
        props = {p["name"]: p["value"] for p in self.cdx["properties"]}
        for name in self.reg["properties_required"]:
            self.assertIn(name, props)
        self.assertEqual(self.sample["lineage"]["head"], props["nf:lineage_head"])
        self.assertEqual(self.sample["review"]["decision"],
                         props["nf:human_review_decision"])

    def test_spdx_required_and_relationship(self):
        for key in self.reg["exports"]["spdx"]["required"]:
            self.assertIn(key, self.spdx)
        self.assertEqual("SPDX-2.3", self.spdx["spdxVersion"])
        pkg = self.spdx["packages"][0]
        self.assertIn(self.sample["card"]["model_digest"],
                      [c["checksumValue"] for c in pkg["checksums"]])
        self.assertTrue(any(r["relationshipType"] == "DESCRIBES"
                            for r in self.spdx["relationships"]))

    def test_deterministic(self):
        a = ax.build(str(ROOT))
        b = ax.build(str(ROOT))
        self.assertEqual(ax.render(a["cdx"]), ax.render(b["cdx"]))
        self.assertEqual(ax.render(a["spdx"]), ax.render(b["spdx"]))
        self.assertIn("urn:uuid:", a["cdx"]["serialNumber"])

    def test_no_secrets_detector(self):
        self.assertTrue(ax._secret_hits("-----BEGIN RSA PRIVATE KEY-----"))
        self.assertTrue(ax._secret_hits("password: hunter2"))
        self.assertFalse(ax._secret_hits(ax.render(self.cdx)))

    def test_tamper_red(self):
        original = CDX.read_text(encoding="utf-8")
        try:
            bad = copy.deepcopy(self.cdx)
            bad["metadata"]["component"]["hashes"][0]["content"] = "0" * 64
            CDX.write_text(ax.render(bad), encoding="utf-8", newline="\n")
            issues = ax.check(str(ROOT))
        finally:
            CDX.write_text(original, encoding="utf-8", newline="\n")
        self.assertTrue(issues, "hash 被篡改必须红")

    def test_missing_property_red(self):
        original = CDX.read_text(encoding="utf-8")
        try:
            bad = copy.deepcopy(self.cdx)
            bad["properties"] = [p for p in bad["properties"]
                                 if p["name"] != "nf:eval_protocol_digest"]
            CDX.write_text(ax.render(bad), encoding="utf-8", newline="\n")
            issues = ax.check(str(ROOT))
        finally:
            CDX.write_text(original, encoding="utf-8", newline="\n")
        self.assertTrue(issues, "缺必填 property 必须红")

    def test_claims_boundary(self):
        boundary = " ".join(self.reg.get("claims_boundary") or [])
        self.assertIn("不声称", boundary)


if __name__ == "__main__":
    unittest.main()
