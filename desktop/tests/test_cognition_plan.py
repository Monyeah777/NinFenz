"""认知核 · 研究层判据：切片/检索词/方法论路径必须**成体系且可证伪**，不是随便列几个词。

判据盯四件事：
① 结构齐（每片有问题/中英检索词/方法/证据/证伪条件）；
② 方法论真（引用的方法必须在库里；库条目自己要有 steps/output/falsifier）；
③ 深度可调（1→3、2→5、3→7 片，且确定性输出）；
④ 不编造（纯 CJK 主题的英文检索词标 en_needs_human，不假装有译名）。
"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import cognition_plan as cp  # noqa: E402

NF = (sys.executable, str(ROOT / "scripts" / "nf.py"))


class MethodsLibraryTest(unittest.TestCase):
    def test_library_loads_and_validates(self):
        lib = cp.load_methods(str(ROOT))
        self.assertEqual("nf-research-methods/1", lib["schema"])
        self.assertGreaterEqual(len(lib["methods"]), 6)

    def test_every_method_has_steps_output_and_falsifier(self):
        lib = cp.load_methods(str(ROOT))
        for m in lib["methods"]:
            self.assertGreaterEqual(len(m["steps"]), 2, m["id"])
            self.assertTrue(m["output"].strip(), m["id"])
            self.assertTrue(m["falsifier"].strip(), m["id"])

    def test_duplicate_id_is_rejected(self):
        bad = {"schema": "nf-research-methods/1",
               "methods": [{"id": "M1", "title": "t", "when": "w", "steps": ["a", "b"],
                            "output": "o", "falsifier": "f"}] * 2}
        self.assertTrue(any("重复" in i for i in cp.validate_methods(bad)))

    def test_missing_falsifier_is_rejected(self):
        bad = {"schema": "nf-research-methods/1",
               "methods": [{"id": "M1", "title": "t", "when": "w", "steps": ["a", "b"],
                            "output": "o"}]}
        self.assertTrue(any("falsifier" in i for i in cp.validate_methods(bad)))


class PlanTest(unittest.TestCase):
    def test_depth_controls_slice_count(self):
        for depth, want in ((1, 3), (2, 5), (3, 7)):
            doc = cp.plan("水印抗转码", depth=depth, root=str(ROOT))
            self.assertEqual(want, len(doc["slices"]), depth)

    def test_every_slice_is_complete(self):
        doc = cp.plan("水印抗转码", depth=3, root=str(ROOT))
        lib_ids = {m["id"] for m in cp.load_methods(str(ROOT))["methods"]}
        for sl in doc["slices"]:
            self.assertTrue(sl["question"].strip(), sl["id"])
            self.assertGreaterEqual(len(sl["terms"]["zh"]), 2, sl["id"])
            self.assertGreaterEqual(len(sl["terms"]["en"]), 1, sl["id"])
            self.assertTrue(sl["terms"]["ops"], sl["id"])
            self.assertTrue(sl["evidence_owed"], sl["id"])
            self.assertTrue(sl["falsifier"].strip(), sl["id"])
            self.assertTrue(set(sl["methods"]) <= lib_ids, sl["id"])

    def test_paths_cover_used_methods(self):
        doc = cp.plan("水印抗转码", depth=3, root=str(ROOT))
        used = {m for sl in doc["slices"] for m in sl["methods"]}
        got = {p["method"] for p in doc["paths"]}
        self.assertEqual(used, got)
        self.assertEqual(list(range(1, len(doc["paths"]) + 1)),
                         [p["order"] for p in doc["paths"]])

    def test_plan_is_deterministic(self):
        a = cp.plan("水印抗转码", 2, root=str(ROOT))
        b = cp.plan("水印抗转码", 2, root=str(ROOT))
        self.assertEqual(json.dumps(a, sort_keys=True), json.dumps(b, sort_keys=True))

    def test_methods_filter_narrows_surface(self):
        doc = cp.plan("水印抗转码", 3, methods=["M3", "M4"], root=str(ROOT))
        for sl in doc["slices"]:
            self.assertTrue(set(sl["methods"]) <= {"M3", "M4"}, sl["id"])

    def test_unknown_method_is_rejected_with_guide(self):
        with self.assertRaises(ValueError) as ctx:
            cp.plan("x", 2, methods=["M99"], root=str(ROOT))
        self.assertIn("修复指引", str(ctx.exception))

    def test_empty_topic_is_rejected_with_guide(self):
        with self.assertRaises(ValueError) as ctx:
            cp.plan("   ", 2, root=str(ROOT))
        self.assertIn("修复指引", str(ctx.exception))

    def test_cjk_topic_marks_english_terms_for_human(self):
        doc = cp.plan("水印抗转码", 1, root=str(ROOT))
        self.assertTrue(doc["slices"][0]["terms"]["en_needs_human"])

    def test_ascii_topic_derives_english_terms(self):
        doc = cp.plan("watermark transcoding", 1, root=str(ROOT))
        self.assertFalse(doc["slices"][0]["terms"]["en_needs_human"])
        self.assertIn("watermark", doc["slices"][0]["terms"]["en"][0])

    def test_ledger_rule_forbids_unproven_claims(self):
        doc = cp.plan("水印抗转码", 1, root=str(ROOT))
        self.assertIn("未证", doc["ledger"]["rule"])
        self.assertIn("未证", doc["ledger"]["strength_scale"])


class CliTest(unittest.TestCase):
    def test_plan_json_and_out_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "plan.json"
            proc = subprocess.run([*NF, "cognition", "--plan", "水印抗转码", "--depth", "2",
                                   "--out", str(out), "--json"],
                                  capture_output=True, text=True, encoding="utf-8",
                                  errors="replace", timeout=180)
            self.assertEqual(0, proc.returncode, proc.stderr[-300:])
            doc = json.loads(proc.stdout)
            self.assertEqual("nf-research-plan/1", doc["schema"])
            self.assertEqual(5, len(doc["slices"]))
            self.assertEqual(doc, json.loads(out.read_text(encoding="utf-8")))

    def test_list_methods(self):
        proc = subprocess.run([*NF, "cognition", "--list-methods"],
                              capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=180)
        self.assertEqual(0, proc.returncode)
        self.assertIn("第一性原理", proc.stdout)
        self.assertIn("对抗审阅", proc.stdout)


if __name__ == "__main__":
    unittest.main()
