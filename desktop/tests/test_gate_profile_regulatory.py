"""M80 质量门 profile 单测（T4.2 合规与监管域包纵深：regulatory-strict）。

覆盖（对齐技术文档域包 `test_gate_profile.py` 的纵深打法）：
1. profile 形状：34 条 clause / 必填字段 / 判据注册（只用已注册 predicate，不改引擎）/
   资产可达 / 校验能抓出变异；
2. 每条 clause **2 正 2 反**：正例 = 清洁 fixture + 官方证据包样例（两件独立产物都要过），
   反例 = 两个互不相同的注入缺陷变体，各自必须命中该 clause；
3. fixture 逐条报告：清洁件 FAIL=0；缺陷件命中注入的 clause 集合；
4. 证据包样例：`nf assemble --check` PASS（八段骨架 + 编号允许集），profile 全 clause PASS；
5. 接线：profile → `quality_gate` 规则数 = clause 数，且不进 `default_rules()`。

运行：cd desktop && python -m unittest tests.test_gate_profile_regulatory -v
"""
from __future__ import annotations

import copy
import re
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import gate_profile as gp  # noqa: E402

PACK = ROOT / "community" / "合规与监管域包"
PROFILE = PACK / "gate_profiles" / "regulatory-strict.json"
FIXTURES = ROOT / "desktop" / "tests" / "fixtures" / "compliance"
OK_DOC = FIXTURES / "compliance_ok.md"
BAD_DOC = FIXTURES / "compliance_bad.md"
SAMPLE = PACK / "outputs" / "samples" / "AI_CONTENT_COMPLIANCE_EVIDENCE_PACK.md"
ASSEMBLE_REQ = "自定义：AI 内容合规证据包（合规与监管域包 P98 装配）"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _sub(old: str, new: str):
    """返回「把 old 全量替换为 new」的变异函数。"""
    return lambda t: t.replace(old, new)


def _pairs(*pairs):
    """返回「按给定 (old, new) 序列依次替换」的变异函数。"""
    def mutate(t: str) -> str:
        for old, new in pairs:
            t = t.replace(old, new)
        return t
    return mutate


def _drop_heading(keyword: str):
    """删掉第一条含 keyword 的章节标题行（章节判据应因此失败）。"""
    def mutate(t: str) -> str:
        return re.sub(r"(?m)^#{2,6}[^\n]*%s[^\n]*\n" % re.escape(keyword), "", t, count=1)
    return mutate


def _rename_heading(keyword: str, new: str):
    """把第一条含 keyword 的章节标题行里的 keyword 改写成 new。"""
    def mutate(t: str) -> str:
        return re.sub(r"(?m)^(#{2,6}[^\n]*?)%s" % re.escape(keyword),
                      lambda m: m.group(1) + new, t, count=1)
    return mutate


def _append(line: str):
    return lambda t: t + "\n" + line + "\n"


#: clause_id → 两个**互不相同**的缺陷注入变体（各自必须使该 clause 失败）。
MUTATIONS = {
    "EU-AIA-50-TRANSPARENCY-SECTION": [
        _drop_heading("AI 披露"), _rename_heading("AI 披露", "AI 说明")],
    "EU-AIA-50-GEN-STATEMENT": [
        _pairs(("人工智能生成", "自动生成"), ("AI 生成", "自动生成")),
        _pairs(("人工智能生成", "系统产出"), ("AI 生成", "系统回复"))],
    "EU-AIA-50-DISCLOSURE-TABLE": [
        _sub("| 披露对象 | 披露方式 | 披露文本 |", "| 受众 | 披露方式 | 披露文本 |"),
        _sub("| 披露对象 | 披露方式 | 披露文本 |", "| 披露对象 | 方式 | 披露文本 |")],
    "EU-AIA-50-DEEPFAKE": [
        _sub("深度合成内容", "合成内容"), _sub("深度合成", "人工合成")],
    "EU-AIA-50-EFFECTIVE-DATE": [
        _sub("2026-08-02", "2026-08"), _sub("2026-08-02", "2026 年 8 月")],
    "EU-AIA-COP-2026-06": [
        _sub("行为准则", "实践指引"), _sub("行为准则", "操作指引文件")],
    "GB-45438-EXPLICIT": [
        _sub("显式标识", "前端标注"), _sub("显式标识", "显式水印")],
    "GB-45438-IMPLICIT": [
        _sub("隐式标识", "后台水印"), _sub("隐式标识", "隐式属性标记")],
    "GB-45438-LABEL-TABLE": [
        _sub("| 标识类型 | 标识位置 | 标识内容 |", "| 类别 | 标识位置 | 标识内容 |"),
        _pairs(("| 显式标识 | 分享卡片 | 同文案 + 生成服务提供者名称 |\n", ""),
               ("| 隐式标识 | 文件元数据 | 生成合成属性 + 服务提供者编码 + trace_id |\n", ""))],
    "ISO-42001-STATEMENT": [
        _pairs(("## 1. 合规声明\n", ""), ("内容合规声明", "内容合规证明")),
        _pairs(("## 1. 合规声明", "## 1. 合规承诺"), ("内容合规声明", "内容合规证明"))],
    "ISO-42001-DOC-REGISTER": [
        _sub("| 文件名称 | 版本 | 责任人 | 保留期 |", "| 文件名 | 版本 | 责任人 | 保留期 |"),
        _pairs(("| 审计日志 schema | 1.0.0 | 平台负责人 | 保留期 3 年 |\n", ""))],
    "DATA-SOURCE-SECTION": [
        _drop_heading("数据来源"), _rename_heading("数据来源", "数据出处")],
    "DATA-SOURCE-TABLE": [
        _sub("| 数据来源 | 授权方式 | 用途 |", "| 数据来源 | 来源类型 | 用途 |"),
        _sub("| 数据来源 | 授权方式 | 用途 |", "| 来源 | 授权方式 | 用途 |")],
    "DATA-LICENSE": [
        _pairs(("授权", "来源说明"), ("许可", "来源说明")),
        _pairs(("授权", "归属"), ("许可", "使用范围"))],
    "NIST-AIRMF-RISK-SECTION": [
        _drop_heading("风险分级"), _rename_heading("风险分级", "风险等级")],
    "NIST-AIRMF-RISK-LEVELS": [
        _pairs(("不可接受风险", "禁止情形"), ("高风险", "严重情形"),
               ("有限风险", "一般情形"), ("最小风险", "轻微情形")),
        _pairs(("不可接受风险", "阻断情形"), ("高风险", "重大情形"),
               ("有限风险", "普通情形"), ("最小风险", "极小情形"))],
    "NIST-AIRMF-RISK-TABLE": [
        _sub("| 风险等级 | 风险描述 | 处置措施 |", "| 等级 | 风险描述 | 处置措施 |"),
        _pairs(("| 有限风险 | 营销文案可能夸大产品能力 | 显式标识 + 人工复核后发布 |\n", ""))],
    "OVERSIGHT-SECTION": [
        _drop_heading("人类监督"), _rename_heading("人类监督", "监督责任")],
    "OVERSIGHT-ACTION": [
        _pairs(("人工复核", "关注"), ("人工确认", "关注"), ("审批", "关注")),
        _pairs(("人工复核", "检查"), ("人工确认", "检查"), ("审批", "检查"))],
    "OVERSIGHT-TABLE": [
        _sub("| 监督角色 | 监督动作 | 触发条件 |", "| 角色 | 监督动作 | 触发条件 |"),
        _sub("| 监督角色 | 监督动作 | 触发条件 |", "| 监督角色 | 动作 | 触发条件 |")],
    "AUDIT-SECTION": [
        _drop_heading("审计日志"), _rename_heading("审计日志", "日志")],
    "AUDIT-FIELD-TABLE": [
        _sub("| 字段 | 类型 | 必填 | 说明 |", "| 名称 | 类型 | 必填 | 说明 |"),
        _pairs(("| content_ref | string | 是 | 内容编号或摘要 |\n", ""),
               ("| decision | enum | 是 | pass/block/escalate |\n", ""))],
    "AUDIT-TRACE-ID": [
        _sub("trace_id", "event_no"), _sub("trace_id", "event_id")],
    "RETENTION-SECTION": [
        _drop_heading("保留期"), _rename_heading("保留期", "保存期限")],
    "RETENTION-DURATION": [
        _pairs(("保留期 3 年", "保留期 长期"), ("保留期 2 年", "保留期 长期")),
        _sub("保留期", "保存安排")],
    "RETENTION-CONTACT": [
        _pairs(("联系人", "相关团队"), ("数据保护官", "相关团队")),
        _pairs(("联系人", "对口团队"), ("数据保护官", "对口团队"))],
    "PRIVACY-SECTION": [
        _drop_heading("敏感信息"), _rename_heading("敏感信息", "个人信息保护")],
    "PRIVACY-MINIMIZATION": [
        _pairs(("去标识化", "脱敏"), ("匿名化", "脱敏")),
        _pairs(("去标识化", "遮蔽"), ("匿名化", "遮蔽"))],
    "PRIVACY-NO-PLAINTEXT": [
        _append("- 连接串示例：password: EXAMPLE123"),
        _append("- 示例凭据：sk-ABCDEFGH1234")],
    "VERSION-TRACE": [
        _sub("| 1.1.0 | 2026-10-26 | 补审计日志字段", "| 1.0.0 | 2026-10-26 | 补审计日志字段"),
        _sub("| 1.1.0 | 2026-10-26 |", "| 1.1.0 | 2026/10/26 |")],
    "VERSION-CHANGE-TABLE": [
        _sub("| 版本 | 日期 | 变更 |", "| 版本 | 日期 | 说明 |"),
        _pairs(("| 1.0.0 | 2026-10-20 | 初版：披露、标识、来源、风险四类证据 |\n", ""))],
    "STRUCT-DOCTYPE": [
        _sub("> 文档类型：compliance_statement", "> 文档类型：handbook"),
        _sub("> 文档类型：compliance_statement\n", "")],
    "STRUCT-H1": [
        _append("# 附录：第二份证据包"),
        _sub("# AI 内容合规证据包（样例：内容合规声明）", "AI 内容合规证据包（样例：内容合规声明）")],
    "STRUCT-TABLE-COLS": [
        _sub("| 终端读者 | 内容首屏可见声明 | 本内容由人工智能生成，经人工复核后发布。 |",
             "| 终端读者 | 内容首屏可见声明 |"),
        _sub("| pass/block/escalate |", "| pass/block/escalate | extra |")],
}


def _report(text: str) -> dict:
    return gp.report(text, gp.load(str(PROFILE)))


def _failing(doc: dict) -> set:
    return {row["clause_id"] for row in doc["clauses"] if not row["ok"]}


class ProfileShapeTest(unittest.TestCase):
    """profile 是**数据**：条数/字段/判据/资产四项可机检。"""

    @classmethod
    def setUpClass(cls):
        cls.profile = gp.load(str(PROFILE))
        cls.ids = [c["clause_id"] for c in cls.profile["clauses"]]

    def test_profile_has_at_least_20_clauses(self):
        self.assertGreaterEqual(len(self.ids), 20,
                                "合规严格 profile 应 ≥20 条 clause（实际 %d）" % len(self.ids))
        self.assertEqual([], gp.validate(self.profile))

    def test_required_fields_and_registered_predicates(self):
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
            self.assertIn(pred["kind"], gp.PREDICATE_KINDS,
                          "判据未注册（引擎不支持）：%s" % pred["kind"])
            self.assertTrue(str(clause["evidence"]).strip())
            self.assertTrue(str(clause["data_source"]).strip())
            src = clause["source"]
            self.assertTrue((isinstance(src, dict) and src.get("standard"))
                            or (isinstance(src, str) and src.strip()))

    def test_profile_assets_resolve(self):
        refs = self.profile.get("assets") or {}
        self.assertGreaterEqual(len(refs), 5, "profile 应挂合规资产（证据来源可追）")
        for key, rel in refs.items():
            self.assertTrue((PROFILE.parent / rel).resolve().is_file(),
                            "asset %s 不可达：%s" % (key, rel))

    def test_validate_catches_mutations(self):
        bad = copy.deepcopy(self.profile)
        bad["clauses"][0]["predicate"] = {"kind": "no_such_predicate"}
        self.assertTrue(any("predicate.kind 未注册" in i for i in gp.validate(bad)))
        bad = copy.deepcopy(self.profile)
        del bad["clauses"][1]["evidence"]
        self.assertTrue(any("evidence" in i for i in gp.validate(bad)))
        bad = copy.deepcopy(self.profile)
        bad["clauses"][2]["clause_id"] = bad["clauses"][0]["clause_id"]
        self.assertTrue(any("重复" in i for i in gp.validate(bad)))
        bad = copy.deepcopy(self.profile)
        bad["clauses"][3]["level"] = "error"
        self.assertTrue(any("level 非法" in i for i in gp.validate(bad)))
        bad = copy.deepcopy(self.profile)
        bad["clauses"][4]["source"] = {}
        self.assertTrue(any("source" in i for i in gp.validate(bad)))
        bad = copy.deepcopy(self.profile)
        bad["assets"] = {"ghost": "../assets/NO_SUCH_ASSET.md"}
        self.assertTrue(any("assets.ghost" in i for i in gp.validate(bad)))
        bad = copy.deepcopy(self.profile)
        bad["schema"] = "nf-gate-profile/9"
        self.assertTrue(any("schema" in i for i in gp.validate(bad)))


class FixtureReportTest(unittest.TestCase):
    """fixture 逐条报告：清洁件全过、缺陷件命中注入缺陷。"""

    @classmethod
    def setUpClass(cls):
        cls.ok = _report(_text(OK_DOC))
        cls.bad = _report(_text(BAD_DOC))
        cls.sample = _report(_text(SAMPLE))

    def test_clean_fixture_passes_all_clauses(self):
        self.assertEqual(0, self.ok["summary"]["fail"],
                         "清洁 fixture 不应有 fail：%s" % sorted(
                             r["clause_id"] for r in self.ok["clauses"] if not r["ok"]))
        self.assertTrue(self.ok["ok"])

    def test_sample_evidence_pack_passes_all_clauses(self):
        self.assertEqual(0, self.sample["summary"]["fail"],
                         "证据包样例不应有 fail：%s" % sorted(_failing(self.sample)))
        self.assertTrue(self.sample["ok"])

    def test_bad_fixture_reports_injected_defects(self):
        failing = _failing(self.bad)
        self.assertFalse(self.bad["ok"])
        expected = {
            "EU-AIA-50-GEN-STATEMENT",     # 只写「智能生成」
            "EU-AIA-50-DISCLOSURE-TABLE",  # 披露表列名不符
            "GB-45438-EXPLICIT",           # 无显式标识口径
            "GB-45438-IMPLICIT",           # 无隐式标识口径
            "GB-45438-LABEL-TABLE",        # 标识表缺「标识类型」列
            "ISO-42001-DOC-REGISTER",      # 无文档台账表
            "NIST-AIRMF-RISK-LEVELS",      # 自造「中高」档
            "NIST-AIRMF-RISK-TABLE",       # 风险表仅 1 行
            "OVERSIGHT-ACTION",            # 只写「关注」
            "OVERSIGHT-TABLE",             # 监督表列名不符
            "AUDIT-FIELD-TABLE",           # 日志表缺「说明」列
            "AUDIT-TRACE-ID",              # 无 trace_id
            "PRIVACY-MINIMIZATION",        # 无去标识化
            "PRIVACY-NO-PLAINTEXT",        # 含凭据/证件号明文
            "RETENTION-DURATION",          # 无量化保留期
            "VERSION-TRACE",               # 版本未递增 + 日期非 ISO
            "VERSION-CHANGE-TABLE",        # 变更表缺「变更」列
            "STRUCT-DOCTYPE",              # handbook 不在白名单
        }
        self.assertTrue(expected <= failing,
                        "以下注入缺陷未被命中：%s" % sorted(expected - failing))

    def test_report_rows_carry_data_source_and_findings(self):
        for row in self.ok["clauses"]:
            self.assertIn("clause_id", row)
            self.assertIn("findings", row)
            self.assertIn("data_source", row)
            self.assertIn("evidence", row)
        bad_rows = [r for r in self.bad["clauses"] if not r["ok"]]
        self.assertTrue(bad_rows)
        self.assertTrue(any(f.get("message") for r in bad_rows for f in r["findings"]))


class ClauseTwoPositiveTwoNegativeTest(unittest.TestCase):
    """每条 clause：2 正（清洁 fixture + 官方证据包样例）2 反（两个不同注入变体）。"""

    @classmethod
    def setUpClass(cls):
        cls.profile = gp.load(str(PROFILE))
        cls.ok_text = _text(OK_DOC)
        cls.sample_text = _text(SAMPLE)
        cls.ok = _failing(gp.report(cls.ok_text, cls.profile))
        cls.sample = _failing(gp.report(cls.sample_text, cls.profile))
        cls.bad = _failing(gp.report(_text(BAD_DOC), cls.profile))

    def test_mutations_cover_every_clause(self):
        ids = {c["clause_id"] for c in self.profile["clauses"]}
        self.assertEqual(ids, set(MUTATIONS),
                         "MUTATIONS 未覆盖：%s" % sorted(ids - set(MUTATIONS)))
        for cid, fns in MUTATIONS.items():
            self.assertEqual(2, len(fns), "%s 需 2 个反例变体" % cid)

    def test_each_clause_two_positive(self):
        for cid in MUTATIONS:
            with self.subTest(clause=cid, fixture="clean"):
                self.assertNotIn(cid, self.ok, "清洁 fixture 应通过 %s" % cid)
            with self.subTest(clause=cid, fixture="sample"):
                self.assertNotIn(cid, self.sample, "证据包样例应通过 %s" % cid)

    def test_each_clause_two_negative(self):
        for cid, fns in MUTATIONS.items():
            for n, fn in enumerate(fns, 1):
                with self.subTest(clause=cid, variant=n):
                    mutated = fn(self.ok_text)
                    self.assertNotEqual(self.ok_text, mutated,
                                        "%s 变体 %d 未改动文本" % (cid, n))
                    failing = _failing(gp.report(mutated, self.profile))
                    self.assertIn(cid, failing,
                                  "%s 变体 %d 未被命中（实际失败：%s）"
                                  % (cid, n, sorted(failing)))

    def test_failing_evidence_points_at_line(self):
        mutated = MUTATIONS["PRIVACY-NO-PLAINTEXT"][0](self.ok_text)
        doc = gp.report(mutated, self.profile)
        row = next(r for r in doc["clauses"] if r["clause_id"] == "PRIVACY-NO-PLAINTEXT")
        self.assertFalse(row["ok"])
        self.assertTrue(row["findings"][0]["line"] >= 1)


class EvidencePackIntegrationTest(unittest.TestCase):
    """证据包样例：`nf assemble --check` PASS + profile 全过 + CLI 入口。"""

    SCRIPT = ROOT / "scripts" / "nf.py"

    def test_sample_declares_eight_segments(self):
        text = _text(SAMPLE)
        segs = {int(m.group(1)) for m in re.finditer(r"(?m)^##\s*([0-7])\s*\.", text)}
        self.assertEqual(set(range(8)), segs, "证据包样例须含八段骨架 ##0—##7")
        self.assertIn("P98", text)

    def test_nf_assemble_check_passes_on_sample(self):
        proc = subprocess.run(
            [sys.executable, str(self.SCRIPT), "assemble", ASSEMBLE_REQ,
             "--check", str(SAMPLE)],
            capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=300, cwd=str(ROOT))
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        self.assertIn("通过自组装机器验收", proc.stdout)

    def test_profile_cli_ok_and_bad(self):
        script = ROOT / "desktop" / "src" / "core" / "gate_profile.py"

        def run(doc: Path):
            return subprocess.run(
                [sys.executable, str(script), "--profile", str(PROFILE),
                 "--text", str(doc)],
                capture_output=True, text=True, encoding="utf-8",
                errors="replace", timeout=120)

        good = run(SAMPLE)
        self.assertEqual(0, good.returncode, good.stdout + good.stderr)
        self.assertIn("PASS 34", good.stdout)
        bad = run(BAD_DOC)
        self.assertEqual(1, bad.returncode, bad.stdout + bad.stderr)


class IrRulesWiringTest(unittest.TestCase):
    """profile → quality_gate 接线：规则数 = clause 数，且不进 default_rules()。"""

    @classmethod
    def setUpClass(cls):
        cls.profile = gp.load(str(PROFILE))

    def test_rules_count_and_names(self):
        rules = gp.ir_rules(self.profile)
        self.assertEqual(len(self.profile["clauses"]), len(rules))
        names = [r.__name__ for r in rules]
        self.assertEqual(len(names), len(set(names)), "profile 规则名须唯一")

    def test_profile_rules_stay_out_of_default(self):
        from core.quality_gate import default_rules

        default_ids = {r.__name__ for r in default_rules()}
        for r in gp.ir_rules(self.profile):
            self.assertNotIn(r.__name__, default_ids)


if __name__ == "__main__":
    unittest.main()
