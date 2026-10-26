"""英文术语层（T12.2）单测：数据形状 / 唯一性 / 真实锚点 / 必含清单 / 渲染确定性 / 负例。

覆盖：
1. 真仓库 `protocol/glossary.json`：schema、entries ≥30、7 分类、必含术语 33 条齐全、
   锚点全部真实（`nf glossary check` 零 issue）；
2. 渲染确定性：两次 render 逐字节一致；与生成件 `docs/protocol/glossary.en.md` 同源；
3. 负例（注入变异）：重复 zh / 重复 en、假文件、假章节、假关键词、假行号、缺必含术语、
   未知 category、schema 错；
4. 与既有行话表 `terms` 并存：`core.cognition.verify_glossary` 仍绿（不破坏旧面）；
5. CLI：`nf glossary check [--json]`、`nf glossary render --out`。

运行：cd desktop && python -m unittest tests.test_glossary -v
"""
from __future__ import annotations

import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import glossary as glg          # noqa: E402
from core import cognition as cog         # noqa: E402

DOC_PATH = ROOT / glg.GLOSSARY_REL
EN_DOC = ROOT / "docs" / "protocol" / "glossary.en.md"
NF = ROOT / "scripts" / "nf.py"


def _doc() -> dict:
    return json.loads(DOC_PATH.read_text(encoding="utf-8"))


class RealRepoGlossaryTest(unittest.TestCase):
    def test_check_clean(self):
        report = glg.check(str(ROOT))
        self.assertTrue(report["ok"], report["issues"][:5])
        self.assertEqual(0, len(report["issues"]))

    def test_entries_and_categories(self):
        doc = _doc()
        self.assertEqual(glg.SCHEMA, doc["schema"])
        entries = doc["entries"]
        self.assertGreaterEqual(len(entries), 30, "英文术语层应 ≥30 条")
        self.assertEqual(list(glg.DEFAULT_CATEGORIES), doc["categories"])
        cats = {e["category"] for e in entries}
        self.assertEqual(set(glg.DEFAULT_CATEGORIES), cats)

    def test_required_terms_all_present(self):
        zh = {e["zh"] for e in _doc()["entries"]}
        missing = [t for t in glg.REQUIRED_TERMS if t not in zh]
        self.assertEqual([], missing, "必含术语缺项：%s" % missing)
        self.assertEqual(33, len(glg.REQUIRED_TERMS))

    def test_every_source_has_real_locator(self):
        for e in _doc()["entries"]:
            src = e["source"]
            self.assertIn("file", src)
            self.assertTrue(src.get("section") or src.get("keyword"),
                            "条目 %s 缺 section/keyword 锚点" % e["zh"])
            # 刻意不用行号锚点：避免「行号随文件改动漂移」的假锚点风险
            self.assertNotIn("line", src, "条目 %s 用了行号锚点（本项目禁假行号）" % e["zh"])

    def test_render_deterministic_and_same_source(self):
        doc = _doc()
        a = glg.render_markdown(doc, str(ROOT))
        b = glg.render_markdown(copy.deepcopy(doc), str(ROOT))
        self.assertEqual(a, b, "同输入渲染必须逐字节一致")
        self.assertTrue(EN_DOC.is_file(), "缺人读生成件 docs/protocol/glossary.en.md")
        self.assertEqual(a, EN_DOC.read_text(encoding="utf-8"),
                         "生成件与数据不同源（跑 nf glossary render 重生成）")
        for e in doc["entries"]:
            self.assertIn(e["zh"], a)
            self.assertIn(e["en"], a)

    def test_legacy_terms_untouched(self):
        """既有行话表（cognition 消费）与英文术语层并存，旧面保持绿。"""
        doc = _doc()
        self.assertGreaterEqual(len(doc.get("terms") or []), 8)
        self.assertEqual([], cog.verify_glossary(str(ROOT))[0])


class NegativeCaseTest(unittest.TestCase):
    """变异注入：每条负例都必须被 `check(doc=...)` 判红。"""

    def _bad(self, mutate):
        doc = copy.deepcopy(_doc())
        mutate(doc)
        return glg.check(str(ROOT), doc)

    def test_duplicate_zh(self):
        def mutate(doc):
            doc["entries"][1]["zh"] = doc["entries"][0]["zh"]
        report = self._bad(mutate)
        self.assertFalse(report["ok"])
        self.assertTrue(any("中文术语重复" in i for i in report["issues"]))

    def test_duplicate_en(self):
        def mutate(doc):
            doc["entries"][1]["en"] = doc["entries"][0]["en"].upper()
        report = self._bad(mutate)
        self.assertFalse(report["ok"])
        self.assertTrue(any("英文术语重复" in i for i in report["issues"]))

    def test_fake_file(self):
        def mutate(doc):
            doc["entries"][0]["source"] = {"file": "no/such/file.md", "keyword": "x"}
        report = self._bad(mutate)
        self.assertTrue(any("source.file 不存在" in i for i in report["issues"]))

    def test_fake_section(self):
        def mutate(doc):
            doc["entries"][0]["source"] = {"file": "01_核心协议.md",
                                           "section": "不存在的章节标题"}
        report = self._bad(mutate)
        self.assertTrue(any("source.section" in i for i in report["issues"]))

    def test_fake_keyword(self):
        def mutate(doc):
            doc["entries"][0]["source"] = {"file": "01_核心协议.md",
                                           "keyword": "绝不可能出现的词_zzz"}
        report = self._bad(mutate)
        self.assertTrue(any("source.keyword" in i for i in report["issues"]))

    def test_fake_line(self):
        def mutate(doc):
            doc["entries"][0]["source"] = {"file": "01_核心协议.md", "line": 999999,
                                           "keyword": "模块"}
        report = self._bad(mutate)
        self.assertTrue(any("source.line 越界" in i for i in report["issues"]))
        doc2 = copy.deepcopy(_doc())
        doc2["entries"][0]["source"] = {"file": "01_核心协议.md", "line": 1,
                                        "keyword": "模块"}
        report2 = glg.check(str(ROOT), doc2)
        self.assertTrue(any("source.line 与锚点不符" in i for i in report2["issues"]))

    def test_missing_required_term(self):
        def mutate(doc):
            doc["entries"] = [e for e in doc["entries"] if e["zh"] != "模块"]
        report = self._bad(mutate)
        self.assertTrue(any("必含术语缺项" in i for i in report["issues"]))

    def test_unknown_category(self):
        def mutate(doc):
            doc["entries"][0]["category"] = "不存在的分类"
        report = self._bad(mutate)
        self.assertTrue(any("category 不在 categories 在册" in i for i in report["issues"]))

    def test_bad_schema(self):
        def mutate(doc):
            doc["schema"] = "nf-glossary/0"
        report = self._bad(mutate)
        self.assertTrue(any("schema 非" in i for i in report["issues"]))

    def test_source_path_escape_rejected(self):
        def mutate(doc):
            doc["entries"][0]["source"] = {"file": "../outside.md", "keyword": "x"}
        report = self._bad(mutate)
        self.assertTrue(any("source.file 不可定位" in i for i in report["issues"]))


class CliTest(unittest.TestCase):
    def _run(self, *argv):
        return subprocess.run([sys.executable, str(NF), *argv], cwd=str(ROOT),
                              capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=180)

    def test_check_human_and_json(self):
        p = self._run("glossary", "check")
        self.assertEqual(0, p.returncode, p.stdout + p.stderr)
        self.assertIn("术语层通过", p.stdout)
        self.assertIn("entries 33", p.stdout)
        pj = self._run("glossary", "check", "--json")
        self.assertEqual(0, pj.returncode, pj.stderr)
        data = json.loads(pj.stdout)
        self.assertEqual(glg.CHECK_SCHEMA, data["schema"])
        self.assertTrue(data["ok"])
        self.assertEqual(33, data["stats"]["entries"])

    def test_render_to_temp_matches_module(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "glossary.en.md"
            p = self._run("glossary", "render", "--out", str(out))
            self.assertEqual(0, p.returncode, p.stdout + p.stderr)
            self.assertTrue(out.is_file())
            self.assertEqual(glg.render_markdown(_doc(), str(ROOT)),
                             out.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
