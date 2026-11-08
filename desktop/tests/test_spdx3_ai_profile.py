"""SPDX 3.0.1 AI Profile builder and fail-closed negative cases."""
import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from core import spdx3

DEPS = [
    {"name": "yaml", "version": "6.0.3", "purl": "pkg:pypi/pyyaml@6.0.3",
     "optional": False, "reason": "hard"},
    {"name": "psutil", "version": "", "purl": "pkg:pypi/psutil",
     "optional": True, "reason": "optional"},
]


class SPDX3AIProfileTest(unittest.TestCase):
    def test_builds_closed_ai_profile_graph(self):
        doc = spdx3.build("v1.2.3", "2026-11-08", DEPS)
        self.assertEqual([], spdx3.validate(doc))
        graph = doc["@graph"]
        root = next(e for e in graph if e["@type"] == "ai_AIPackage")
        doc_node = next(e for e in graph if e["@type"] == "software_Sbom")
        self.assertEqual(doc_node["rootElement"], [root["@id"]])
        self.assertEqual(doc_node["profileConformance"],
                         ["core", "software", "simpleLicensing", "ai"])
        self.assertEqual(root["software_primaryPurpose"], "application")
        self.assertEqual(root["ai_autonomyType"], "no")
        self.assertIn("No model training", root["ai_informationAboutTraining"])
        self.assertIn("does not bundle model weights", root["ai_limitation"])
        self.assertNotIn("ai_energyConsumption", root,
                         "无实测能量数据时不得填充估计值")
        rels = [e for e in graph
                if e["@type"] == "LifecycleScopedRelationship"]
        self.assertEqual({"dependsOn", "hasOptionalDependency"},
                         {e["relationshipType"] for e in rels})

    def test_ai_claim_without_training_boundary_is_rejected(self):
        doc = spdx3.build("v1.2.3", "2026-11-08", DEPS)
        root = next(e for e in doc["@graph"] if e["@type"] == "ai_AIPackage")
        root["ai_informationAboutTraining"] = "Model was trained on private data."
        issues = spdx3.validate(doc)
        self.assertTrue(any("未训练模型" in issue for issue in issues), issues)

    def test_dangling_relationship_is_rejected(self):
        doc = spdx3.build("v1.2.3", "2026-11-08", DEPS)
        relation = next(e for e in doc["@graph"]
                        if e["@type"] == "LifecycleScopedRelationship")
        relation["to"] = ["https://invalid.example/nope"]
        issues = spdx3.validate(doc)
        self.assertTrue(any("未知 @id" in issue for issue in issues), issues)

    def test_duplicate_ids_are_rejected(self):
        doc = spdx3.build("v1.2.3", "2026-11-08", DEPS)
        dup = copy.deepcopy(doc["@graph"][0])
        doc["@graph"].append(dup)
        issues = spdx3.validate(doc)
        self.assertTrue(any("@id 重复" in issue for issue in issues), issues)

    def test_missing_root_license_relationship_is_rejected(self):
        doc = spdx3.build("v1.2.3", "2026-11-08", DEPS)
        root = next(e for e in doc["@graph"] if e["@type"] == "ai_AIPackage")
        doc["@graph"] = [
            e for e in doc["@graph"]
            if not (e.get("from") == root["@id"]
                    and e.get("relationshipType") == "hasDeclaredLicense")
        ]
        issues = spdx3.validate(doc)
        self.assertTrue(any("declared/concluded license" in issue for issue in issues), issues)


if __name__ == "__main__":
    unittest.main()
