#!/usr/bin/env python3
"""WP-52 关键词/扩展口判据（§17 标签索引 + §18 OPEN 扩展口不得静默关闭）。"""

import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import keywords as kw  # noqa: E402

REG = ROOT / kw.REL
SCRIPT = ROOT / "scripts" / "nf.py"


class KeywordsContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.reg = json.loads(REG.read_text(encoding="utf-8"))

    def test_registry_and_check_green(self):
        self.assertEqual("nf-keywords/1", self.reg["schema"])
        self.assertEqual([], kw.check(str(ROOT)))

    def test_tags_defined_and_used_subset(self):
        defined = {t["id"] for t in self.reg["tags"]}
        used = kw.used_tags(str(ROOT))
        for tag in used:
            self.assertTrue(
                tag in defined or any(d.endswith("-*") and tag.startswith(d[:-1]) for d in defined),
                "孤儿标签：%s" % tag)

    def test_tags_have_owner_and_meaning(self):
        for tag in self.reg["tags"]:
            self.assertTrue(tag.get("meaning"), tag["id"])
            self.assertTrue(tag.get("owner"), tag["id"])
            self.assertIn(tag.get("status"), ("active", "planned", "retired"))

    def test_openings_complete_and_not_silently_closed(self):
        openings = self.reg["extension_openings"]
        self.assertGreaterEqual(len(openings), 12)
        ids = [o["id"] for o in openings]
        self.assertEqual(len(ids), len(set(ids)))
        for item in openings:
            self.assertTrue(item["id"].startswith("OPEN-"))
            self.assertIn(item["status"], ("open", "partial", "closed"))
            self.assertTrue(item.get("owner"), item["id"])
            self.assertTrue(item.get("interface"), item["id"])
            if item["status"] == "closed":
                self.assertTrue(item.get("evidence"), item["id"])
                for rel in item["evidence"]:
                    self.assertTrue((ROOT / rel).exists(), "%s 证据不在场：%s" % (item["id"], rel))

    def test_synonyms_complete(self):
        pairs = {(s["cn"], s["en"]) for s in self.reg["synonyms"]}
        for need in (("生产装配", "assembly"), ("规范", "spec"), ("契约", "contract"),
                     ("治理", "governance"), ("证据", "evidence"),
                     ("信任等级", "trust level"), ("不可抵赖", "non-repudiation")):
            self.assertIn(need, pairs)

    def test_mutations_red(self):
        readme = ROOT / "README.md"
        original = readme.read_text(encoding="utf-8")
        try:
            readme.write_text(original.replace("# NinFenz", "# NinFenz（已认证）", 1),
                              encoding="utf-8", newline="\n")
            self.assertTrue(any("禁用词" in i for i in kw.check(str(ROOT))),
                            "非否定语境的认证措辞必须红")
            reg_original = REG.read_text(encoding="utf-8")
            doc = json.loads(reg_original)
            doc["extension_openings"][0].pop("owner", None)
            REG.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8", newline="\n")
            try:
                self.assertTrue(any("缺 owner" in i for i in kw.check(str(ROOT))),
                                "OPEN 缺 owner 必须红")
            finally:
                REG.write_text(reg_original, encoding="utf-8", newline="\n")
        finally:
            readme.write_text(original, encoding="utf-8", newline="\n")

    def test_orphan_tag_red(self):
        doc = ROOT / "docs" / "keywords.md"
        original = doc.read_text(encoding="utf-8")
        try:
            doc.write_text(original + "\n[NO-SUCH-TAG]\n", encoding="utf-8", newline="\n")
            self.assertTrue(any("孤儿标签" in i for i in kw.check(str(ROOT))))
        finally:
            doc.write_text(original, encoding="utf-8", newline="\n")

    def test_cli_smoke(self):
        proc = subprocess.run([sys.executable, str(SCRIPT), "keywords", "check", "--json"],
                              cwd=str(ROOT), capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=120)
        self.assertEqual(0, proc.returncode, proc.stderr[-300:])
        payload = json.loads(proc.stdout)
        self.assertEqual("nf-keywords-check/1", payload["schema"])
        self.assertEqual([], payload["issues"])


if __name__ == "__main__":
    unittest.main()
