"""导入器（T9.2）：DOCX/DITA → 内容 IR 单测。

覆盖：
1. DOCX：标题层级→section、段落/表格/列表→对应 IR form、规范形（canonical）往返；
2. DITA：title/shortdesc/p/steps/table、元素覆盖表（覆盖/未覆盖）、ditamap 行为；
3. 损坏文件 fail-closed（zip/XML/根元素/缺件）→ 干净错误 + 修复指引，不冒内部错误；
4. 未覆盖元素报 warn 且文字不静默丢；
5. CLI `nf import docx|dita [--json/--out]`；旧面 `nf import <file>` 不回退；
6. 确定性：同一输入两次导入逐字节一致；导入产物 parse→render 幂等。

运行：cd desktop && python -m unittest tests.test_import_docx_dita -v
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import content_ir as ci                 # noqa: E402
from core import import_dita                      # noqa: E402
from core import import_docx                      # noqa: E402

FIX = ROOT / "desktop" / "tests" / "fixtures" / "import"
DOCX = FIX / "minimal.docx"
DITA = FIX / "minimal.dita"
DITAMAP = FIX / "minimal.ditamap"
CORRUPT_DOCX = FIX / "corrupt.docx"
CORRUPT_DITA = FIX / "corrupt.dita"
SKILL = ROOT / "desktop" / "tests" / "fixtures" / "external" / "anthropic-official" / "docx.SKILL.md"
NF = ROOT / "scripts" / "nf.py"


def _run(*argv):
    return subprocess.run([sys.executable, str(NF), *argv], cwd=str(ROOT),
                          capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=180)


class DocxImportTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.res = import_docx.import_file(str(DOCX), base_dir=str(ROOT))

    def test_headings_become_sections(self):
        levels = [s.level for s in self.res.ir.sections]
        self.assertEqual([1, 2, 2, 3], levels)
        self.assertEqual(["示例产品使用说明书", "安装", "规格", "附录"],
                         [s.title for s in self.res.ir.sections])
        self.assertEqual("示例产品使用说明书", self.res.ir.title)

    def test_paragraph_table_list_forms(self):
        self.assertGreaterEqual(self.res.stats["paragraphs"], 1)
        self.assertEqual(1, self.res.stats["tables"])
        self.assertEqual(2, self.res.stats["lists"])
        forms = {n.form for n in self.res.ir.nodes.values() if n.kind == "paragraph"}
        self.assertTrue({"para", "table", "list"} <= forms, forms)

    def test_ordered_and_bullet_lists_separated(self):
        # numbering.xml：numId 1 = bullet、2 = decimal → 两种列表块各自成形
        self.assertIn("- 电源线一根", self.res.markdown)
        self.assertIn("1. 连接保护接地。", self.res.markdown)
        self.assertIn("2. 连接电源线。", self.res.markdown)

    def test_canonical_and_deterministic(self):
        self.assertTrue(self.res.ir.canonical, self.res.ir.noncanonical_reason)
        self.assertEqual(ci.canonical(self.res.markdown), self.res.markdown)
        again = import_docx.import_file(str(DOCX), base_dir=str(ROOT))
        self.assertEqual(self.res.markdown, again.markdown)

    def test_roundtrip_section_count(self):
        ir2 = ci.parse(ci.render(self.res.ir))
        self.assertEqual(len(self.res.ir.sections), len(ir2.sections))

    def test_uncovered_element_warns_but_keeps_text(self):
        joined = "\n".join(self.res.warnings)
        self.assertIn("drawing", joined)
        self.assertIn("图片", self.res.markdown)      # 图片前后文字未丢
        self.assertIn("参考链接", self.res.markdown)   # 超链接文字保留


class DitaImportTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.res = import_dita.import_file(str(DITA), base_dir=str(ROOT))

    def test_topic_structure(self):
        self.assertEqual("示例产品安装指南", self.res.ir.title)
        self.assertEqual(2, self.res.stats["sections"])       # H1 + section 安装
        self.assertEqual(1, self.res.stats["tables"])
        self.assertEqual(2, self.res.stats["lists"])          # ul + steps
        self.assertEqual(1, self.res.stats["quotes"])         # shortdesc
        self.assertIn("> 本指南说明示例产品的安装", self.res.markdown)

    def test_steps_ordered(self):
        self.assertIn("1. 连接保护接地。接地电阻不大于 4 Ω。", self.res.markdown)
        self.assertIn("3. 上电并检查指示灯。", self.res.markdown)

    def test_canonical_and_roundtrip(self):
        self.assertTrue(self.res.ir.canonical)
        self.assertEqual(ci.canonical(self.res.markdown), self.res.markdown)
        ir2 = ci.parse(ci.render(self.res.ir))
        self.assertEqual(len(self.res.ir.sections), len(ir2.sections))
        again = import_dita.import_file(str(DITA), base_dir=str(ROOT))
        self.assertEqual(self.res.markdown, again.markdown)

    def test_coverage_table(self):
        cov = import_dita.coverage_report()
        self.assertIn("table", cov["covered"])
        self.assertIn("steps", cov["covered"])
        self.assertIn("image", cov["uncovered"])
        self.assertTrue(cov["unknown_policy"])

    def test_uncovered_warns_text_preserved(self):
        joined = "\n".join(self.res.warnings)
        self.assertIn("<fig>", joined)
        self.assertIn("<pre>", joined)
        self.assertIn("未覆盖块元素示例文本", self.res.markdown)  # 未知元素文字没丢
        self.assertIn("接线示意图", self.res.markdown)            # image alt 文字保留


class DitamapImportTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.res = import_dita.import_file(str(DITAMAP), base_dir=str(ROOT))

    def test_map_projection(self):
        self.assertEqual("示例产品文档集", self.res.ir.title)
        self.assertEqual(3, self.res.stats["sections"])   # H1 + 两个 topicref
        self.assertIn("## 示例产品安装指南", self.res.markdown)
        self.assertIn("## 示例产品规格", self.res.markdown)   # topicmeta/navtitle 生效
        self.assertTrue(any("不展开" in w for w in self.res.warnings))


class CorruptFailClosedTest(unittest.TestCase):
    def test_bad_zip(self):
        with self.assertRaises(import_docx.DocxImportError) as cm:
            import_docx.import_file(str(CORRUPT_DOCX), base_dir=str(ROOT))
        self.assertIn("修复指引", str(cm.exception))
        self.assertIn("docx", str(cm.exception).lower())

    def test_bad_xml(self):
        with self.assertRaises(import_dita.DitaImportError) as cm:
            import_dita.import_file(str(CORRUPT_DITA), base_dir=str(ROOT))
        self.assertIn("修复指引", str(cm.exception))

    def test_wrong_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "x.dita"
            p.write_text('<?xml version="1.0"?><doc><title>t</title></doc>',
                         encoding="utf-8")
            with self.assertRaises(import_dita.DitaImportError) as cm:
                import_dita.import_file(str(p))
        self.assertIn("根元素", str(cm.exception))

    def test_cli_clean_error(self):
        p = _run("import", "docx", str(CORRUPT_DOCX))
        self.assertEqual(2, p.returncode)
        self.assertIn("导入失败", p.stderr)
        self.assertNotIn("内部错误", p.stderr)
        pj = _run("import", "dita", str(CORRUPT_DITA), "--json")
        self.assertEqual(2, pj.returncode)
        data = json.loads(pj.stdout)
        self.assertFalse(data["ok"])
        self.assertIn("schema", data)


class CliImportTest(unittest.TestCase):
    def test_docx_json_and_out(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "imported.md"
            p = _run("import", "docx", str(DOCX), "--json", "--out", str(out))
            self.assertEqual(0, p.returncode, p.stdout + p.stderr)
            data = json.loads(p.stdout)
            self.assertEqual("nf-import-docx/1", data["schema"])
            self.assertTrue(data["ok"])
            self.assertEqual(4, data["stats"]["sections"])
            self.assertEqual(data["canonical"], True)
            text = out.read_text(encoding="utf-8")
            res = import_docx.import_file(str(DOCX), base_dir=str(ROOT))
            self.assertEqual(res.markdown, text, "--out 应写规范形 Markdown")

    def test_dita_human_face(self):
        p = _run("import", "dita", str(DITA))
        self.assertEqual(0, p.returncode, p.stdout + p.stderr)
        self.assertIn("→ 内容 IR", p.stdout)
        self.assertIn("section 2", p.stdout)
        self.assertIn("[WARN]", p.stdout)
        self.assertIn("fig", p.stdout)

    def test_legacy_import_still_works(self):
        p = _run("import", str(SKILL))
        self.assertEqual(0, p.returncode, p.stdout + p.stderr)
        self.assertIn("nf import docx.SKILL.md", p.stdout)
        self.assertIn("解析: ok", p.stdout)


if __name__ == "__main__":
    unittest.main()
