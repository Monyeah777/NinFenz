"""platform_rules 规则包与 fail-closed 评估的单元测试（纯标准库）。"""

import unittest

from core.labeling import platform_rules as pr


def _sections(statuses=None):
    """构造一份五段报告；statuses 里没写的分段默认 PASS。"""
    statuses = statuses or {}
    out = {}
    for key in pr.SECTIONS:
        out[key] = {
            "id": key,
            "title": pr.SECTION_TITLES[key],
            "status": statuses.get(key, "PASS"),
            "items": [],
        }
    return {"sections": out, "verdict": "PASS"}


def _by_id(result):
    return {row["id"]: row for row in result["checks"]}


class PlatformRulePackTest(unittest.TestCase):
    def test_platforms_contract(self):
        self.assertEqual(pr.platforms(), [
            "douyin", "wechat_channels", "xiaohongshu",
            "apple_app_store", "eu_ai_act",
        ])
        self.assertEqual(set(pr.platforms()), set(pr.PLATFORMS))
        self.assertEqual(len(pr.platforms()), 5)

    def test_rulepack_fields_and_maps_to(self):
        required_platform = {"name", "summary", "checks", "sources"}
        required_check = {"id", "requirement", "maps_to", "source",
                          "verified", "checked_at"}
        for pid, pack in pr.PLATFORMS.items():
            self.assertEqual(set(pack), required_platform, pid)
            self.assertTrue(pack["name"] and pack["summary"], pid)
            self.assertIsInstance(pack["sources"], list)
            for url in pack["sources"]:
                self.assertTrue(url.startswith(("http://", "https://")), url)
            self.assertTrue(pack["checks"], pid)
            ids = set()
            for check in pack["checks"]:
                self.assertEqual(set(check), required_check, check)
                self.assertIn(check["maps_to"], pr.VALID_MAPS)
                self.assertNotIn(check["id"], ids)
                ids.add(check["id"])
                self.assertIsInstance(check["verified"], bool)
                self.assertTrue(check["checked_at"])

    def test_selfcheck_reports_structure_and_source_counts(self):
        rows = pr.selfcheck()
        self.assertIsInstance(rows, list)
        self.assertTrue(all(isinstance(row, tuple) and len(row) == 3
                            for row in rows))
        self.assertTrue(all(row[1] for row in rows),
                        [row for row in rows if not row[1]])
        total = sum(len(pack["checks"]) for pack in pr.PLATFORMS.values())
        with_source = sum(
            1 for pack in pr.PLATFORMS.values() for check in pack["checks"]
            if str(check["source"]).strip()
        )
        coverage = next(row for row in rows if row[0] == "source-coverage")
        self.assertIn("%d/%d" % (with_source, total), coverage[2])
        for pid, pack in pr.PLATFORMS.items():
            row = next(row for row in rows if row[0] == "platform:%s" % pid)
            self.assertIn("规则 %d 条" % len(pack["checks"]), row[2])


class EvaluateTest(unittest.TestCase):
    def test_pass_report_overall_pass(self):
        result = pr.evaluate(_sections(), "apple_app_store")
        self.assertEqual(result["schema"], "nf-label-platform-eval/1")
        self.assertEqual(result["overall"], "PASS")
        self.assertEqual(result["summary"], {"PASS": 3, "WARN": 0,
                                             "FAIL": 0, "UNKNOWN": 0})
        for row in result["checks"]:
            self.assertEqual(row["verdict"], "PASS")

    def test_fail_report_overall_fail(self):
        result = pr.evaluate(_sections({"C": "FAIL"}), "apple_app_store")
        self.assertEqual(result["overall"], "FAIL")
        rows = _by_id(result)
        self.assertEqual(rows["apple_app_store.ugc_safety"]["verdict"], "FAIL")
        self.assertEqual(rows["apple_app_store.third_party_ai"]["verdict"], "FAIL")
        self.assertEqual(rows["apple_app_store.accurate_metadata"]["verdict"], "PASS")

    def test_warn_report_overall_warn(self):
        result = pr.evaluate(_sections({"E": "WARN"}), "apple_app_store")
        self.assertEqual(result["overall"], "WARN")
        rows = _by_id(result)
        self.assertEqual(rows["apple_app_store.accurate_metadata"]["verdict"], "WARN")

    def test_unverified_rules_never_pass(self):
        result = pr.evaluate(_sections(), "xiaohongshu")
        self.assertEqual(result["overall"], "UNKNOWN")
        self.assertEqual(result["summary"]["PASS"], 0)
        self.assertTrue(result["checks"])
        for row in result["checks"]:
            self.assertFalse(row["verified"])
            self.assertEqual(row["verdict"], "UNKNOWN")
            self.assertIn("待核实", row["requirement"])
            self.assertTrue(any("未核实" in n for n in result["notes"]))

    def test_unverified_rule_is_unknown_even_when_section_passes(self):
        pack = pr.PLATFORMS["xiaohongshu"]
        check = pack["checks"][0]
        self.assertFalse(check["verified"])
        self.assertEqual(check["source"], "")
        result = pr.evaluate(_sections({"A": "PASS"}), "xiaohongshu")
        row = _by_id(result)["xiaohongshu.active_label"]
        self.assertEqual(row["verdict"], "UNKNOWN")
        self.assertIn("verified=False", row["reason"])

    def test_missing_section_is_unknown(self):
        report = _sections()
        del report["sections"]["C"]
        result = pr.evaluate(report, "apple_app_store")
        self.assertEqual(result["overall"], "UNKNOWN")
        rows = _by_id(result)
        self.assertEqual(rows["apple_app_store.ugc_safety"]["verdict"], "UNKNOWN")
        self.assertEqual(result["report_sections"]["C"], "MISSING")

    def test_na_section_is_unknown_not_pass(self):
        result = pr.evaluate(_sections({"C": "NA"}), "apple_app_store")
        self.assertEqual(result["overall"], "UNKNOWN")
        rows = _by_id(result)
        self.assertEqual(rows["apple_app_store.ugc_safety"]["verdict"], "UNKNOWN")

    def test_all_mapping_is_fail_closed(self):
        rows = _by_id(pr.evaluate(_sections(), "eu_ai_act"))
        self.assertEqual(rows["eu_ai_act.clear_and_timely"]["verdict"], "PASS")
        rows = _by_id(pr.evaluate(_sections({"D": "FAIL"}), "eu_ai_act"))
        self.assertEqual(rows["eu_ai_act.clear_and_timely"]["verdict"], "FAIL")
        rows = _by_id(pr.evaluate(_sections({"B": "NA"}), "eu_ai_act"))
        self.assertEqual(rows["eu_ai_act.clear_and_timely"]["verdict"], "UNKNOWN")
        report = _sections({"D": "FAIL"})
        del report["sections"]["B"]
        rows = _by_id(pr.evaluate(report, "eu_ai_act"))
        self.assertEqual(rows["eu_ai_act.clear_and_timely"]["verdict"], "FAIL")

    def test_unknown_platform_raises_with_fix_guidance(self):
        with self.assertRaises(ValueError) as ctx:
            pr.evaluate(_sections(), "no-such-platform")
        message = str(ctx.exception)
        self.assertIn("未知平台", message)
        self.assertIn("platforms()", message)
        self.assertIn("修复指引", message)
        self.assertIn("示例", message)


if __name__ == "__main__":
    unittest.main()
