"""内容 IR（T7.2）单测：节点图 / 规范形往返 / 稳定 id / 悬空负例 / 确定性。

覆盖：
1. 装配产物（`nf assemble --build`）parse→render 与原文规范形**逐字节一致**；
2. 馆藏样本（NF-1 / NF-TECHDOC）往返 + 非规范形声明（以 canonical 输出为准）；
3. 节点 id 稳定性：同输入同 id、CRLF/空白归一后同 id、内容变则 id 变；
4. 负例：悬空引用（`#nowhere` / §9）与悬空实体（M99 未声明）；
5. 确定性：两次 render / 两次 parse / to_json 逐字节一致；
6. `nf ir check` CLI + IR 文本规则 adapter（3 条；不改 profile 引擎）。

运行：cd desktop && python -m unittest tests.test_content_ir -v
"""
from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import content_ir as ci                 # noqa: E402
from core import assemble_build as ab             # noqa: E402
from core import assemble_plan as ap              # noqa: E402
from core import gate_profile_rules as gpr       # noqa: E402

REQ = "写一份技术文档，要术语表和修订记录"
LIB = ROOT / "library"


def _build_text() -> str:
    plan = ap.plan(REQ)
    text, _stats = ab.build(str(ROOT), REQ, plan)
    return text


def _ids(ir: ci.Document) -> dict:
    return dict(sorted((n.id, n.kind) for n in ir.nodes.values()))


class BuildRoundtripTest(unittest.TestCase):
    """验收主项：装配产物规范形往返逐字节一致。"""

    @classmethod
    def setUpClass(cls):
        cls.text = _build_text()
        cls.ir = ci.parse(cls.text, "完整版.md")

    def test_build_is_canonical(self):
        self.assertTrue(self.ir.canonical, self.ir.noncanonical_reason)
        self.assertEqual(self.ir.path and ci._normalize_source(self.text),
                         ci.canonical(self.text))

    def test_parse_render_byte_identical(self):
        self.assertEqual(ci.canonical(self.text), ci.render(self.ir))

    def test_eight_section_roles(self):
        roles = {s.role for s in self.ir.sections}
        for role in ("assembly_record", "overview", "pipeline", "registry",
                     "modules", "assets"):
            self.assertIn(role, roles, "八段结构角色缺失：%s（实得 %s）" % (role, roles))
        self.assertGreaterEqual(len(self.ir.sections), 8)

    def test_nodes_are_typed(self):
        kinds = {n.kind for n in self.ir.nodes.values()}
        self.assertTrue({"document", "section", "paragraph", "claim", "citation",
                         "entity", "slot_ref"} <= kinds, kinds)
        self.assertGreater(len(self.ir.claims), 0)
        self.assertGreater(len(self.ir.citations), 0)
        self.assertGreater(len(self.ir.entities), 0)


class LibraryRoundtripTest(unittest.TestCase):
    """馆藏样本：往返成立；非规范形如实声明（以 canonical 输出为准）。"""

    def _check(self, rel: str):
        text = (ROOT / rel).read_text(encoding="utf-8")
        ir = ci.parse(text, rel)
        canon = ci.canonical(text)
        self.assertEqual(ci.render(ir), canon, "%s 往返不一致" % rel)
        self.assertEqual(ci.canonical(canon), canon, "%s canonical 非幂等" % rel)
        if ir.canonical:
            self.assertEqual(canon, ci._normalize_source(text))
        else:
            self.assertNotEqual(canon, ci._normalize_source(text))
            self.assertTrue(ir.noncanonical_reason)
        return ir

    def test_nf1(self):
        ir = self._check("library/NF-1.md")
        self.assertGreaterEqual(len(ir.sections), 1)

    def test_nf_techdoc(self):
        ir = self._check("library/NF-TECHDOC-Monyeah777-1.md")
        self.assertEqual("技术文档装配流 P06 · 内容自包含完整版",
                         ir.title, "frontmatter title 兜底未生效")

    def test_nf_worldcampus(self):
        self._check("library/NF-WORLDCAMPUS-Monyeah777-1.md")


class StableIdTest(unittest.TestCase):
    """节点 id：同输入同 id；CRLF/空白归一后同 id；内容变则 id 变。"""

    @classmethod
    def setUpClass(cls):
        cls.text = _build_text()
        cls.ir = ci.parse(cls.text, "完整版.md")

    def test_same_input_same_ids(self):
        again = ci.parse(self.text, "完整版.md")
        self.assertEqual(_ids(self.ir), _ids(again))

    def test_crlf_and_whitespace_insensitive(self):
        messy = (self.text.replace("\n", "\r\n")
                 .replace("## 0.", "## 0.   ")
                 .replace("\n\n## 1.", "\n\n\n\n## 1.")
                 + "\n\n")
        a = ci.parse(self.text, "x.md")
        b = ci.parse(messy, "x.md")
        self.assertEqual(_ids(a), _ids(b), "CRLF/空白不应改变节点 id")
        self.assertEqual(ci.canonical(self.text), ci.canonical(messy))

    def test_content_change_changes_ids(self):
        old = ci.parse(self.text, "x.md")
        changed = self.text.replace("## 0. 装配记录", "## 0. 装配记录（改）")
        new = ci.parse(changed, "x.md")
        old_ids, new_ids = set(_ids(old)), set(_ids(new))
        self.assertNotEqual(old_ids, new_ids)
        old_sec = [s for s in old.sections if "0." in s.title][0]
        new_sec = [s for s in new.sections if "0." in s.title][0]
        self.assertNotEqual(old_sec.id, new_sec.id, "内容变则节点 id 必变")

    def test_parse_is_deterministic_json(self):
        a = ci.to_json(ci.parse(self.text, "x.md"))
        b = ci.to_json(ci.parse(self.text, "x.md"))
        self.assertEqual(a, b)
        self.assertEqual(json.loads(a)["schema"], ci.SCHEMA)


class NegativeCaseTest(unittest.TestCase):
    """悬空引用 / 悬空实体负例。"""

    def test_dangling_citation(self):
        doc = ("# 样例\n\n> 文档类型：guide\n\n## 1. 说明\n\n"
               "见 [术语表](#nowhere) 与 §9。\n")
        ir = ci.parse(doc, "")
        report = ci.check_file  # 仅取函数名做存在性断言（避免写盘）
        self.assertTrue(callable(report))
        _unattributed, dangling = ci._check_citations(ir)
        targets = {c.target for c in dangling}
        self.assertIn("nowhere", targets, "锚点悬空未被识别")
        self.assertIn("9", targets, "§9 悬空未被识别")

    def test_dangling_entity(self):
        doc = ("# 样例\n\n> 文档类型：guide\n\n## 1. 注册表投影\n\n"
               "| 模块ID | 名称 |\n|---|---|\n| M00 | 数据槽 |\n\n"
               "## 2. 说明\n\n本装置引用 M99 但未在注册表声明。\n")
        ir = ci.parse(doc, "")
        dangling = ci._check_entities(ir)
        values = {e.text for e in dangling}
        self.assertIn("M99", values)
        self.assertNotIn("M00", values)

    def test_check_file_negative_report(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "bad.md"
            p.write_text("# 样例\n\n见 [x](#nowhere)，引用 M99。\n", encoding="utf-8")
            rep = ci.check_file(str(p), root=str(ROOT))
        self.assertFalse(rep["ok"])
        self.assertTrue(rep["dangling_citations"])
        self.assertTrue(rep["dangling_entities"])


class DeterminismTest(unittest.TestCase):
    def test_render_twice_identical(self):
        text = _build_text()
        ir = ci.parse(text, "")
        self.assertEqual(ci.render(ir), ci.render(ir))

    def test_ids_keep_under_whitespace_edit(self):
        """纯空白（行尾空格/空行数）改动不影响任何 id。"""
        text = "## 1. 说明\n\n- 条目一  \n- 条目二\n"
        noisy = "## 1. 说明\n\n\n\n- 条目一\n- 条目二   \n\n"
        self.assertEqual(_ids(ci.parse(text, "")), _ids(ci.parse(noisy, "")))


class IRTextRuleAdapterTest(unittest.TestCase):
    """3 条 techdoc-strict 文本规则 → IR 节点执行（复用判据实现，不改引擎）。"""

    def test_adapter_rules_are_three_known_rules(self):
        self.assertEqual(3, len(ci.IR_TEXT_RULES))
        self.assertEqual({"heading_sentence", "heading_end_punct", "single_space"},
                         {r for _c, r in ci.IR_TEXT_RULES})
        for _clause, rule in ci.IR_TEXT_RULES:
            self.assertIn(rule, gpr.TEXT_RULES)
        self.assertEqual(5, len(gpr.TEXT_RULES), "profile 引擎仍是 5 条（未被改动）")

    def test_adapter_findings_are_node_level(self):
        doc = ("# 样例\n\n> 文档类型：guide\n\n## 注意：\n\n本  设备说明。\n")
        ir = ci.parse(doc, "")
        findings = ci.ir_text_rule_findings(ir)
        self.assertTrue(findings)
        for f in findings:
            self.assertIn(f["rule"], {r for _c, r in ci.IR_TEXT_RULES})
            self.assertTrue(f["node_id"])
            self.assertIn(f["node_kind"], ("section", "paragraph", "list", "para",
                                           "quote", "table"))
        clause_ids = {f["clause_id"] for f in findings}
        self.assertIn("MS-STYLE-HEADING-PUNCT", clause_ids)
        self.assertIn("MS-STYLE-SPACE-01", clause_ids)


class CliTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = None

    def _run(self, *argv):
        return subprocess.run([sys.executable, str(ROOT / "scripts" / "nf.py"), *argv],
                              cwd=str(ROOT), capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=180)

    def test_ir_check_on_build_artifact(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "artifact.md"
            out.write_text(_build_text(), encoding="utf-8")
            p = self._run("ir", "check", str(out))
            self.assertEqual(0, p.returncode, p.stdout + p.stderr)
            self.assertIn("往返：逐字节一致", p.stdout)
            self.assertIn("无归属引用：0", p.stdout)
            pj = self._run("ir", "check", str(out), "--json")
            self.assertEqual(0, pj.returncode, pj.stderr)
            rep = json.loads(pj.stdout)
            self.assertEqual(ci.REPORT_SCHEMA, rep["schema"])
            self.assertTrue(rep["roundtrip_ok"])
            self.assertGreaterEqual(rep["counts"]["sections"], 8)

    def test_ir_check_missing_file_is_clean_error(self):
        p = self._run("ir", "check", "no/such/file.md")
        self.assertNotEqual(0, p.returncode)
        self.assertIn("目标不存在", p.stderr)
        self.assertNotIn("内部错误", p.stderr)


if __name__ == "__main__":
    unittest.main()
