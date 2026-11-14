#!/usr/bin/env python3
"""可访问性 + 本地化契约（NF-Final WP-0E，P1 盲区 BL-08/BL-09）。

真源 = `protocol/accessibility.json`（`nf-a11y/1`）+ `protocol/i18n.json`（`nf-i18n/1`）；
语言面真源 = `protocol/locales.json`（文件即真源 + source_sha256）。
判据：
1. 可访问性：8 条 WCAG 适用项（enforced 必须有测试/门禁证据、not-applicable 必须有理由、
   planned 必须有 gate）、6 条 PAIR/HAX 人因、可用性测试模板诚实（template-only）、违规预算=0；
2. CLI/TUI 事实：NO_COLOR 一票否决、键盘操作、宽度/限长、self_check 在场；
3. 语言面：locale ≥3、入口 ≥3、docs 译件 ≥6 组且 en/ja 镜像、source_sha256 合法；
4. 时区：UTC ISO-8601 样例可解析；显示转换不进证据；
5. RTL/Unicode：当前无 RTL locale；bidi/零宽扫描零命中；新增 RTL 必须先过扫描；
6. 不越级：不声称 WCAG 合规/认证、不声称完整 i18n/RTL；
7. 变异自证：enforced 缺测试证据、n-a 缺理由、违规预算非 0、locale 与真源不一致、
   译件组下限被调高、坏 evidence、bidi 注入、声明 RTL locale —— 判据都必须红。
"""
import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import accessibility as acc  # noqa: E402
from core import i18n_checks as i18n  # noqa: E402
from core import iso8601  # noqa: E402

A11Y = ROOT / "protocol" / "accessibility.json"
I18N = ROOT / "protocol" / "i18n.json"
LOCALES = ROOT / "protocol" / "locales.json"
DOCS = {
    "A11Y": ROOT / "A11Y.md",
    "A11Y_QA": ROOT / "docs" / "a11y" / "A11Y_QA.md",
    "I18N": ROOT / "I18N.md",
    "I18N_QA": ROOT / "docs" / "i18n" / "I18N_QA.md",
}
NEGATION = ("不", "非", "无", "未")


def _json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _text(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


class A11yI18nContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.a11y = _json(A11Y)
        cls.i18n = _json(I18N)
        cls.texts = {k: _text(p) for k, p in DOCS.items()}

    def test_registries_valid(self):
        self.assertEqual([], acc.validate(self.a11y, str(ROOT)))
        self.assertEqual([], i18n.validate(self.i18n, str(ROOT)))

    def test_docs_present_and_cross_consistent(self):
        for key, path in DOCS.items():
            self.assertTrue(path.is_file(), "缺文档：%s" % path)
            self.assertTrue(self.texts[key].strip(), "文档为空：%s" % path)
        for row in self.a11y["wcag"]:
            self.assertIn(row["id"], self.texts["A11Y"])
        for row in self.a11y["human_factors"]:
            self.assertIn(row["id"], self.texts["A11Y"])
        for test in self.a11y["usability_tests"]:
            self.assertIn(test["id"], self.texts["A11Y"])
        for loc in self.i18n["locales"]:
            self.assertIn(loc["id"], self.texts["I18N"])
        for word in ("UTC", "RTL", "bidi", "NFC"):
            self.assertIn(word, self.texts["I18N"])
        self.assertIn("test_a11y_i18n_contract.py", self.texts["A11Y_QA"])
        self.assertIn("test_a11y_i18n_contract.py", self.texts["I18N_QA"])

    def test_terminal_facts(self):
        facts = acc.terminal_facts(str(ROOT))
        self.assertTrue(facts["no_color"], "terminal.py 必须支持 NO_COLOR")
        self.assertTrue(facts["self_check"], "terminal.self_check 必须在场")
        self.assertTrue(facts["width_limit"], "必须有限长/宽度控制")
        self.assertIn("nf.py", facts["tui_files"])
        text = _text(ROOT / "desktop" / "src" / "core" / "terminal.py")
        self.assertIn("非 TTY", text, "非 TTY 逐字节确定是硬契约")

    def test_claims_boundary(self):
        self.assertIn("不声称", " ".join(self.a11y["claims_boundary"]))
        claims = self.i18n["review"]["claims_boundary"]
        self.assertTrue(any("不声称" in x for x in claims))
        for key, text in self.texts.items():
            for line in text.splitlines():
                for word in ("不可抵赖", "认证"):
                    if word in line:
                        self.assertTrue(any(m in line for m in NEGATION),
                                        "%s 禁用词未在否定语境：%s" % (key, line.strip()))

    def test_i18n_coverage(self):
        snap = i18n.locale_snapshot(str(ROOT))
        self.assertEqual(["zh", "en", "ja"], snap["locales"])
        self.assertEqual(3, len(snap["entries"]))
        self.assertGreaterEqual(snap["doc_pairs"], self.i18n["coverage_metrics"]["doc_pairs_min"])
        self.assertEqual(snap["en"], snap["ja"], "docs/en 与 docs/ja 必须镜像")
        reg = _json(LOCALES)
        self.assertEqual("zh", reg["canonical"])
        for item in reg["docs"]:
            self.assertTrue((ROOT / item["path"]).is_file())
            for lang, tr in (item.get("translations") or {}).items():
                self.assertTrue((ROOT / tr["path"]).is_file(), "%s/%s" % (item["path"], lang))
                self.assertRegex(tr["source_sha256"], r"^[0-9a-f]{64}$")

    def test_i18n_timezone(self):
        self.assertTrue(iso8601.is_iso_instant("2026-11-14T00:00:00Z"))
        tz = self.i18n["timezone"]
        self.assertIn("UTC", tz["safety_timestamps"])
        self.assertTrue((ROOT / tz["evidence"]).is_file())
        self.assertIn("不捆绑", tz["tzdb"])

    def test_i18n_bidi_clean(self):
        scan = i18n.scan_surfaces(str(ROOT), self.i18n["unicode"]["scan_surfaces"])
        self.assertEqual([], scan["findings"], "语言面出现 bidi/零宽控制字符：%s"
                         % scan["findings"][:3])
        self.assertEqual([], scan["skipped"])
        self.assertEqual(["U+202E"], i18n.bidi_controls("abc\u202edef"))
        self.assertEqual(["U+200B"], i18n.bidi_controls("a\u200bb"))

    def test_i18n_rtl_policy(self):
        rtl = self.i18n["rtl"]
        self.assertEqual([], rtl["current_rtl_locales"], "当前不得声称 RTL 支持")
        self.assertIn("新增 RTL", rtl["policy"])
        self.assertTrue(rtl["banned_codepoints"])

    def test_mutations_red(self):
        weak = copy.deepcopy(self.a11y)
        next(r for r in weak["wcag"] if r["status"] == "enforced")["evidence"] = [
            "docs/terminal.md"]
        self.assertTrue(acc.validate(weak, str(ROOT)), "enforced 缺测试证据必须红")

        no_reason = copy.deepcopy(self.a11y)
        next(r for r in no_reason["wcag"] if r["status"] == "not-applicable").pop("reason", None)
        self.assertTrue(acc.validate(no_reason, str(ROOT)), "not-applicable 缺理由必须红")

        planned = copy.deepcopy(self.a11y)
        next(r for r in planned["wcag"] if r["status"] == "enforced")["status"] = "planned"
        self.assertTrue(acc.validate(planned, str(ROOT)), "planned 缺 gate 必须红")

        budget = copy.deepcopy(self.a11y)
        budget["violation_budget"] = 3
        self.assertTrue(acc.validate(budget, str(ROOT)), "违规预算非 0 必须红")

        locale_drift = copy.deepcopy(self.i18n)
        locale_drift["locales"] = [x for x in locale_drift["locales"] if x["id"] != "ja"]
        self.assertTrue(i18n.validate(locale_drift, str(ROOT)), "locale 与真源不一致必须红")

        too_strict = copy.deepcopy(self.i18n)
        too_strict["coverage_metrics"]["doc_pairs_min"] = 99
        self.assertTrue(i18n.validate(too_strict, str(ROOT)), "译件组下限被调高必须红")

        bad_tz = copy.deepcopy(self.i18n)
        bad_tz["timezone"]["evidence"] = "desktop/src/core/nonexistent_zzz.py"
        self.assertTrue(i18n.validate(bad_tz, str(ROOT)), "时区证据不在场必须红")

        rtl = copy.deepcopy(self.i18n)
        rtl["rtl"]["current_rtl_locales"] = ["ar"]
        self.assertTrue(i18n.validate(rtl, str(ROOT)), "声明 RTL locale 必须红")

    def test_bidi_scan_detects_injected_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "docs" / "en"
            dest.mkdir(parents=True)
            (dest / "poison.md").write_text("safe\u202eevil\n", encoding="utf-8")
            scan = i18n.scan_surfaces(tmp, ["docs/en/"])
            self.assertTrue(scan["findings"], "注入 bidi 控制字符必须被扫出")


if __name__ == "__main__":
    unittest.main()
