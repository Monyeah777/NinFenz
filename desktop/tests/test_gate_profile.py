"""M80 质量门 profile 引擎单测（T4.1 技术文档域包纵深）。

覆盖：
1. `techdoc-strict` profile 形状校验：≥20 clause / 必填字段（clause_id/level/
   predicate/evidence/source/data_source）/ 判据注册 / 资产可达；
2. 5 条确定性文本规则各 **2 正 2 反**（注入缺陷）；
3. fixture 产物逐条 clause 报告：干净件 FAIL=0、缺陷件命中注入的 clause；
4. profile → `quality_gate` 接线：未装 profile 的默认行为不变（仍是 6 条结构规则），
   装 profile 后逐条 clause 成为可解释 Issue（消息带 clause_id）。

运行：cd desktop && python -m unittest tests.test_gate_profile -v
"""
from __future__ import annotations

import copy
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import gate_profile as gp          # noqa: E402
from core.ir import IRDocument, IRLayer, IRModule  # noqa: E402
from core.quality_gate import default_rules, run_gate  # noqa: E402

PROFILE = ROOT / "community" / "技术文档域包" / "gate_profiles" / "techdoc-strict.json"
GLOSSARY = ROOT / "community" / "技术文档域包" / "assets" / "TECH_GLOSSARY.md"
FIXTURES = ROOT / "desktop" / "tests" / "fixtures" / "techdoc"
OK_DOC = FIXTURES / "techdoc_ok.md"
BAD_DOC = FIXTURES / "techdoc_bad.md"

TEXT_CLAUSES = {
    "MS-STYLE-HEADING-SENTENCE": "heading_sentence",
    "MS-STYLE-HEADING-PUNCT": "heading_end_punct",
    "MS-STYLE-SPACE-01": "single_space",
    "MS-STYLE-ABBR-01": "acronym_first_use",
    "MS-STYLE-WEAK-01": "weak_expression",
}


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _rule_findings(rule: str, text: str, options: dict | None = None):
    pred = {"kind": "text_rule", "rule": rule}
    if options:
        pred["options"] = options
    return gp._TEXT_IMPL[rule](pred, gp.build_context(text))


class ProfileShapeTest(unittest.TestCase):
    """profile 是**数据**：形状/判据/资产三项可机检。"""

    @classmethod
    def setUpClass(cls):
        cls.profile = gp.load(str(PROFILE))

    def test_profile_has_at_least_20_clauses(self):
        clauses = self.profile.get("clauses") or []
        self.assertGreaterEqual(len(clauses), 20,
                                "技术文档严格 profile 应 ≥20 条 clause（≥22 外部标准映射）")
        self.assertEqual([], gp.validate(self.profile))

    def test_each_clause_has_required_fields_and_registered_predicate(self):
        seen = set()
        for clause in self.profile["clauses"]:
            for key in ("clause_id", "level", "predicate", "evidence",
                        "source", "data_source"):
                self.assertIn(key, clause, "clause 缺必填字段 %s：%r" % (key, clause))
            cid = clause["clause_id"]
            self.assertNotIn(cid, seen, "clause_id 重复：%s" % cid)
            seen.add(cid)
            self.assertIn(clause["level"], gp.LEVELS)
            pred = clause["predicate"]
            self.assertIn(pred["kind"], gp.PREDICATE_KINDS)
            if pred["kind"] == "text_rule":
                self.assertIn(pred["rule"], gp.TEXT_RULES)
            self.assertTrue(str(clause["evidence"]).strip())
            self.assertTrue(str(clause["data_source"]).strip())

    def test_profile_assets_resolve(self):
        refs = (self.profile.get("assets") or {})
        self.assertIn("glossary", refs)
        self.assertTrue(GLOSSARY.is_file(), "术语表资产缺失：%s" % GLOSSARY)
        self.assertEqual([], gp.validate(self.profile))
        self.assertTrue((PROFILE.parent / refs["glossary"]).resolve().is_file())

    def test_validate_catches_mutations(self):
        bad = copy.deepcopy(self.profile)
        bad["clauses"][0]["predicate"] = {"kind": "no_such_predicate"}
        self.assertTrue(any("predicate.kind 未注册" in i for i in gp.validate(bad)), "未抓到未知判据")
        bad2 = copy.deepcopy(self.profile)
        del bad2["clauses"][1]["evidence"]
        self.assertTrue(any("evidence" in i for i in gp.validate(bad2)), "未抓到缺 evidence")
        bad3 = copy.deepcopy(self.profile)
        bad3["clauses"][2]["clause_id"] = bad3["clauses"][0]["clause_id"]
        self.assertTrue(any("重复" in i for i in gp.validate(bad3)), "未抓到重复 clause_id")


class TextRulePositiveNegativeTest(unittest.TestCase):
    """5 条确定性文本规则：每条 2 正 2 反（反例均为注入缺陷）。"""

    def test_heading_sentence(self):
        self.assertEqual([], _rule_findings("heading_sentence", "## Install the device\n"))
        self.assertEqual([], _rule_findings("heading_sentence", "## 安装设备\n"))
        self.assertTrue(_rule_findings("heading_sentence", "## install the device\n"))
        self.assertTrue(_rule_findings("heading_sentence", "## INSTALL THE DEVICE\n"))

    def test_heading_end_punct(self):
        self.assertEqual([], _rule_findings("heading_end_punct", "## 安装设备\n"))
        self.assertEqual([], _rule_findings("heading_end_punct", "## 1. 术语表\n"))
        self.assertTrue(_rule_findings("heading_end_punct", "## 安装设备：\n"))
        self.assertTrue(_rule_findings("heading_end_punct", "## 注意！\n"))

    def test_single_space(self):
        self.assertEqual([], _rule_findings("single_space", "正文 单空格，正常。\n"))
        self.assertEqual([], _rule_findings("single_space", "| 表格 | 对齐 |\n|---|---|\n"))
        self.assertTrue(_rule_findings("single_space", "本  设备\n"))
        self.assertTrue(_rule_findings("single_space", "标点前有空 ，此处\n"))

    def test_acronym_first_use(self):
        opts = {"allowed_acronyms": ["API"]}
        self.assertEqual([], _rule_findings("acronym_first_use", "使用 API 调用\n", opts))
        self.assertEqual([], _rule_findings(
            "acronym_first_use", "使用应用程序接口（API）调用\n", {}))
        self.assertTrue(_rule_findings("acronym_first_use", "使用 XYZ 调用\n", {}))
        self.assertTrue(_rule_findings("acronym_first_use", "使用 SLA 调用\n", opts))

    def test_weak_expression(self):
        self.assertEqual([], _rule_findings("weak_expression", "读数稳定后继续。\n"))
        self.assertEqual([], _rule_findings("weak_expression", "关闭电源并检查接地。\n"))
        self.assertTrue(_rule_findings("weak_expression", "读数大概稳定。\n"))
        self.assertTrue(_rule_findings("weak_expression", "可能会触发告警。\n"))


class FixtureClauseReportTest(unittest.TestCase):
    """profile 对 fixture 产物**逐条**出 clause 报告。"""

    @classmethod
    def setUpClass(cls):
        cls.profile = gp.load(str(PROFILE))
        cls.ok = gp.report(_text(OK_DOC), cls.profile)
        cls.bad = gp.report(_text(BAD_DOC), cls.profile)

    def test_report_is_per_clause(self):
        self.assertEqual(len(self.profile["clauses"]), len(self.ok["clauses"]))
        for row in self.ok["clauses"]:
            self.assertIn("clause_id", row)
            self.assertIn("findings", row)
            self.assertIn("data_source", row)
            self.assertIn(row["level"], gp.LEVELS)

    def test_clean_fixture_passes_all_fail_clauses(self):
        self.assertTrue(self.ok["ok"], "干净 fixture 不应有 fail 级违例：%s"
                        % [r["clause_id"] for r in self.ok["clauses"] if not r["ok"]])
        self.assertEqual(0, self.ok["summary"]["fail"])
        passing = {r["clause_id"] for r in self.ok["clauses"] if r["ok"]}
        for cid in TEXT_CLAUSES:
            self.assertIn(cid, passing, "文本规则 %s 在干净 fixture 上未通过" % cid)

    def test_bad_fixture_reports_injected_defects(self):
        failing = {r["clause_id"] for r in self.bad["clauses"] if not r["ok"]}
        self.assertFalse(self.bad["ok"])
        expected = {
            "DITA-1.3-TITLE-01",        # 两个 H1
            "DITA-1.3-DOCTYPE-01",      # handbook 不在白名单
            "DITA-1.3-CONREF-01",       # #nowhere 不可寻址
            "DITA-1.3-TASK-STEPS-01",   # 操作章节无有序步骤
            "GB-19678-STRUCT-01",       # 缺安全章节
            "GB-19678-GLOSSARY-01",     # 术语表无表格
            "GB-19678-TERM-01",         # 术语首用未定义
            "GB-19678-TERM-02",         # 固件/firmware 混用
            "GB-19678-REVISION-01",     # 版本未递增 + 日期非 ISO
            "MS-STYLE-HEADING-PUNCT",   # 标题末尾冒号
            "MS-STYLE-SPACE-01",        # 连续空格
            "MS-STYLE-ABBR-01",         # XYZ 未定义
            "MS-STYLE-PLACEHOLDER-01",  # TODO
            "MS-STYLE-FENCE-01",        # 围栏未配平
            "MS-STYLE-TABLE-01",        # 表格列数不一致
        }
        self.assertTrue(expected <= failing,
                        "以下注入缺陷未被 clause 报告命中：%s" % sorted(expected - failing))

    def test_report_text_is_human_readable(self):
        text = gp.report_text(self.bad)
        self.assertIn("gate profile 报告", text)
        self.assertIn("FAIL", text)
        self.assertIn("MS-STYLE-PLACEHOLDER-01", text)


class IrRulesWiringTest(unittest.TestCase):
    """profile → run_gate 接线；未装 profile 默认行为不变。"""

    @classmethod
    def setUpClass(cls):
        cls.profile = gp.load(str(PROFILE))

    @staticmethod
    def _ir(content: str, meta: dict | None = None) -> IRDocument:
        return IRDocument(
            title="", pipeline_id="P06", pipeline_name="技术文档题材装配流",
            layers=[
                IRLayer(id="P00", name="数据基座", modules=[
                    IRModule(full_id="M00", name="数据结构", layer="P00", content="正文")]),
                IRLayer(id="P80", name="输出呈现", modules=[
                    IRModule(full_id="M80", name="输出质检门", layer="P80",
                             content=content)]),
            ], extra_modules=[], meta=meta or {})

    def test_default_rules_unchanged_without_profile(self):
        self.assertEqual(6, len(default_rules()),
                         "结构门应为 6 条（4 既有 + S4 术语一致 + S5 无越层直写）")
        res = run_gate(self._ir("普通正文"))
        self.assertTrue(res.ok())
        self.assertEqual(len(default_rules()), res.n_pass)

    def test_profile_rules_stay_out_of_default(self):
        """profile 规则**不进 default_rules**：默认门对通用装配零影响。"""
        self.assertEqual(6, len(default_rules()), "默认结构门不应被 profile 规则撑大")
        narrative = self._ir("普通正文")
        base = run_gate(narrative)
        self.assertEqual(0, base.n_fail)
        # profile 规则数 = clause 数，且默认规则表里不含它们
        profile_rules = gp.ir_rules(self.profile)
        self.assertEqual(len(self.profile["clauses"]), len(profile_rules))
        default_ids = {r.__name__ for r in default_rules()}
        for r in profile_rules:
            self.assertNotIn(r.__name__, default_ids)
        # 同一份通用正文装 profile 后，profile 判据如实报违例（默认门不受影响）
        with_profile = run_gate(narrative, default_rules() + profile_rules)
        self.assertGreaterEqual(with_profile.n_fail, base.n_fail)

    def test_profile_rules_report_clause_id(self):
        bad = self._ir(_text(BAD_DOC))
        res = run_gate(bad, default_rules() + gp.ir_rules(self.profile))
        self.assertFalse(res.ok())
        messages = "\n".join(i.message for i in res.issues)
        self.assertIn("[MS-STYLE-SPACE-01]", messages)
        self.assertIn("[GB-19678-STRUCT-01]", messages)


class CliReportTest(unittest.TestCase):
    """验收入口：`python desktop/src/core/gate_profile.py --profile … --text …`。"""

    SCRIPT = ROOT / "desktop" / "src" / "core" / "gate_profile.py"

    def _run(self, doc: Path):
        return subprocess.run([sys.executable, str(self.SCRIPT),
                               "--profile", str(PROFILE), "--text", str(doc)],
                              capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=120)

    def test_cli_ok_and_bad(self):
        good = self._run(OK_DOC)
        self.assertEqual(0, good.returncode, good.stdout + good.stderr)
        self.assertIn("gate profile 报告", good.stdout)
        bad = self._run(BAD_DOC)
        self.assertEqual(1, bad.returncode)
        self.assertIn("MS-STYLE-PLACEHOLDER-01", bad.stdout)


if __name__ == "__main__":
    unittest.main()
