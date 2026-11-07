"""法规文本 → 意图草稿判据：抽得准、抽不到的进待补、不可表达的进 unsupported、绝不静默丢。

判据盯的是「不丢账」这件事：每一分类都有明确出口，而且草稿能真的喂进编译面。
"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import check_compile, check_text_to_intent  # noqa: E402

REG = """第一条 生成合成内容应当在内容起始位置添加「本条内容由人工智能生成」的显式标识。
第二条 服务提供者应当在文件元数据中添加生成合成信息的隐式标识。
第三条 任何组织不得删除「AI生成」标识。
第四条 生成合成内容应当添加数字水印。
第五条 提供者应当具备相应资质。
第六条 内容应当符合公序良俗。
"""


class SplitClausesTest(unittest.TestCase):
    def test_splits_by_chinese_clause_numbers(self):
        clauses = check_text_to_intent.split_clauses(REG)
        self.assertEqual(6, len(clauses))
        self.assertEqual("第一条", clauses[0]["label"])

    def test_falls_back_to_single_clause_for_plain_text(self):
        clauses = check_text_to_intent.split_clauses("没有条号的一段正文。")
        self.assertEqual(1, len(clauses))

    def test_numeric_numbering_is_recognized(self):
        clauses = check_text_to_intent.split_clauses(
            "1. 应当在起始处添加显式标识。\n2. 应当添加水印。")
        self.assertEqual(2, len(clauses))


class ExtractionTest(unittest.TestCase):
    def test_quoted_text_becomes_explicit_notice(self):
        doc = check_text_to_intent.draft(REG)
        rules = {c["rule"] for c in doc["covered"]}
        self.assertIn("explicit_notice", rules)
        item = next(r for r in doc["intent"]["requirements"]
                    if r["rule"] == "explicit_notice")
        self.assertIn("人工智能生成", item["text"])

    def test_forbidden_tokens_extracted_from_quotes(self):
        doc = check_text_to_intent.draft(REG)
        item = next(r for r in doc["intent"]["requirements"]
                    if r["rule"] == "forbidden_tokens")
        self.assertTrue(item["patterns"])

    def test_missing_params_go_to_pending_not_silently_dropped(self):
        doc = check_text_to_intent.draft(REG)
        self.assertTrue(doc["pending"], "抽不到参数的条目必须进 pending")
        self.assertTrue(all(p["missing_params"] for p in doc["pending"]))

    def test_unsupported_rules_are_listed_with_needs(self):
        doc = check_text_to_intent.draft(REG)
        rules = {u["rule"] for u in doc["unsupported"]}
        self.assertIn("carrier_watermark", rules)
        self.assertTrue(all(u["needs"] for u in doc["unsupported"]))

    def test_unmatched_clause_is_reported_as_uncovered(self):
        doc = check_text_to_intent.draft(REG)
        self.assertTrue(any(u["clause"] == "第六条" for u in doc["uncovered"]))

    def test_every_clause_lands_in_at_least_one_bucket(self):
        """一条条文可以同时要求多件事（例如「元数据 + 隐式标识」），所以按条而不是按条数对账。"""
        doc = check_text_to_intent.draft(REG)
        clauses = {split["label"] for split in check_text_to_intent.split_clauses(REG)}
        seen = {p["clause"] for p in doc["pending"]}
        seen |= {u["clause"] for u in doc["unsupported"]}
        seen |= {u["clause"] for u in doc["uncovered"]}
        seen |= {c["clause"] for c in doc["covered"]}
        self.assertEqual(clauses, seen, "每一条都必须至少落进一个分类账")

    def test_draft_is_deterministic(self):
        self.assertEqual(check_text_to_intent.canonical(check_text_to_intent.draft(REG)),
                         check_text_to_intent.canonical(check_text_to_intent.draft(REG)))

    def test_draft_compiles_into_policy(self):
        doc = check_text_to_intent.draft(REG)
        compiled = check_compile.compile_intent(doc["intent"])
        self.assertTrue(compiled["ok"], compiled["issues"])
        self.assertTrue((compiled["policy"] or {}).get("rules"), "草稿必须能编出规则")

    def test_oversized_text_is_rejected_with_guide(self):
        with self.assertRaises(ValueError) as ctx:
            check_text_to_intent.draft("x" * (check_text_to_intent.MAX_TEXT_BYTES + 1))
        self.assertIn("修复指引", str(ctx.exception))


class CliTest(unittest.TestCase):
    def test_cli_writes_draft(self):
        nf = sys.executable, str(ROOT / "scripts" / "nf.py")
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            reg = tmp / "reg.txt"
            reg.write_text(REG, encoding="utf-8")
            out = tmp / "draft.json"
            proc = subprocess.run([*nf, "check", "--intent-from-text", str(reg),
                                   "--out", str(out), "--json"],
                                  capture_output=True, text=True, encoding="utf-8",
                                  errors="replace", timeout=180)
            self.assertEqual(0, proc.returncode, proc.stderr[-400:])
            doc = json.loads(proc.stdout)
            self.assertEqual("nf-check-intent-draft/1", doc["schema"])
            self.assertTrue(out.is_file())

    def test_cli_rejects_non_utf8(self):
        nf = sys.executable, str(ROOT / "scripts" / "nf.py")
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "bad.txt"
            bad.write_bytes(b"\xff\xfe\x00bad")
            proc = subprocess.run([*nf, "check", "--intent-from-text", str(bad)],
                                  capture_output=True, text=True, encoding="utf-8",
                                  errors="replace", timeout=180)
            self.assertNotEqual(0, proc.returncode)
            self.assertIn("修复指引", proc.stderr or proc.stdout)


if __name__ == "__main__":
    unittest.main()
