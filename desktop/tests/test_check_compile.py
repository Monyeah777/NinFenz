"""策略编译器 v0（core/check_compile.py）判据：意图 → 封闭词表策略，并如实报告不可表达项。

为什么这些判据重要：编译器的风险不是「编得难看」，而是**静默丢要求**——把「表达不了」当成
「没这回事」，用户于是以为体检覆盖了全部法规要求。故 unsupported 必须逐条留痕，
且编出来的策略必须能真的被 nf-check-policy/1 判定器吃下去（跨模块对账）。
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import check_compile as cc  # noqa: E402
from core import check_policy  # noqa: E402

INTENT = {
    "schema": "nf-check-intent/1",
    "object": "docs/report.md",
    "policy_id": "AIGC-basic",
    "requirements": [
        {"rule": "explicit_notice", "text": "AI 生成", "where": "start"},
        {"rule": "forbidden_tokens", "patterns": ["TODO", "待补"]},
        {"rule": "min_bytes", "n": 200},
        {"rule": "require_metadata", "key": "AIGC", "value": "1"},
    ],
}


def _compile(intent=None):
    return cc.compile_intent(INTENT if intent is None else intent)


def _kinds(policy):
    return [rule["kind"] for rule in policy["rules"]]


class TestValidateIntent(unittest.TestCase):
    def test_bad_schema(self):
        issues = cc.validate_intent({**INTENT, "schema": "x"})
        self.assertTrue(any("schema" in i for i in issues))

    def test_missing_object(self):
        bad = {k: v for k, v in INTENT.items() if k != "object"}
        self.assertTrue(any("object" in i for i in cc.validate_intent(bad)))

    def test_empty_requirements(self):
        self.assertTrue(any("requirements" in i for i in
                            cc.validate_intent({**INTENT, "requirements": []})))

    def test_unknown_rule_is_an_error_not_unsupported(self):
        bad = {**INTENT, "requirements": [{"rule": "not_a_rule"}]}
        res = cc.compile_intent(bad)
        self.assertFalse(res["ok"])
        self.assertIn("未知", res["issues"][0])

    def test_bad_where(self):
        bad = {**INTENT, "requirements": [{"rule": "explicit_notice", "text": "x",
                                           "where": "middle"}]}
        self.assertTrue(any("where" in i for i in cc.validate_intent(bad)))

    def test_bad_regex(self):
        bad = {**INTENT, "requirements": [{"rule": "forbidden_tokens", "patterns": ["("]}]}
        self.assertTrue(any("正则" in i for i in cc.validate_intent(bad)))

    def test_bad_sha(self):
        bad = {**INTENT, "requirements": [{"rule": "digest_pinned", "sha256": "zz"}]}
        self.assertTrue(any("sha256" in i for i in cc.validate_intent(bad)))

    def test_duplicate_ids(self):
        bad = {**INTENT, "requirements": [{"rule": "utf8", "id": "a"},
                                          {"rule": "utf8", "id": "a"}]}
        self.assertTrue(any("重复" in i for i in cc.validate_intent(bad)))


class TestCompile(unittest.TestCase):
    def test_utf8_is_always_first(self):
        res = _compile()
        self.assertTrue(res["ok"])
        self.assertEqual("utf8", res["policy"]["rules"][0]["kind"])

    def test_explicit_notice_variants(self):
        for where, prefix in (("start", "^"), ("end", "$"), ("any", None)):
            intent = {**INTENT, "requirements": [
                {"rule": "explicit_notice", "text": "AI 生成", "where": where}]}
            rules = _compile(intent)["policy"]["rules"][1:]
            self.assertEqual(1, len(rules))
            pat = rules[0]["pattern"]
            if prefix == "^":
                self.assertTrue(pat.startswith("^"))
            elif prefix == "$":
                self.assertTrue(pat.endswith("$"))
            else:
                self.assertFalse(pat.startswith("^") or pat.endswith("$"))

    def test_forbidden_tokens_one_rule_each(self):
        intent = {**INTENT, "requirements": [
            {"rule": "forbidden_tokens", "patterns": ["TODO", "待补", "FIXME"]}]}
        rules = _compile(intent)["policy"]["rules"][1:]
        self.assertEqual(3, len(rules))
        self.assertTrue(all(r["kind"] == "regex_absent" for r in rules))
        self.assertEqual(["TODO", "待补", "FIXME"], [r["pattern"] for r in rules])

    def test_min_bytes(self):
        intent = {**INTENT, "requirements": [{"rule": "min_bytes", "n": 42}]}
        rule = _compile(intent)["policy"]["rules"][1]
        self.assertEqual("count_at_least", rule["kind"])
        self.assertEqual("bytes", rule["field"])
        self.assertEqual(42, rule["n"])

    def test_require_metadata_pattern_has_escaped_whitespace(self):
        intent = {**INTENT, "requirements": [
            {"rule": "require_metadata", "key": "AIGC", "value": "1"}]}
        rule = _compile(intent)["policy"]["rules"][1]
        self.assertIn(r"\s*", rule["pattern"])
        self.assertIn("AIGC", rule["pattern"])

    def test_digest_pinned_lowercased(self):
        sha = "A" * 64
        intent = {**INTENT, "requirements": [{"rule": "digest_pinned", "sha256": sha}]}
        self.assertEqual("a" * 64, _compile(intent)["policy"]["rules"][1]["sha256"])

    def test_compiled_policy_passes_policy_validation(self):
        self.assertEqual([], check_policy.validate(_compile()["policy"]))

    def test_deterministic(self):
        a = _compile()["policy"]
        b = _compile()["policy"]
        self.assertEqual(json.dumps(a, sort_keys=True), json.dumps(b, sort_keys=True))
        self.assertEqual(a["compiled_from"]["digest"], b["compiled_from"]["digest"])

    def test_coverage_counts(self):
        res = _compile()
        self.assertEqual(4, res["coverage"]["requirements"])
        self.assertTrue(res["coverage"]["complete"])


class TestUnsupported(unittest.TestCase):
    def test_unsupported_is_reported_not_dropped(self):
        intent = {**INTENT, "requirements": [
            {"rule": "explicit_notice", "text": "AI 生成"},
            {"rule": "semantic_claim"},
            {"rule": "carrier_watermark", "id": "wm"}]}
        res = _compile(intent)
        self.assertTrue(res["ok"], "不可表达不算编译失败，但要留痕")
        self.assertEqual(2, res["coverage"]["unsupported"])
        self.assertFalse(res["coverage"]["complete"])
        names = [u["rule"] for u in res["unsupported"]]
        self.assertEqual(["semantic_claim", "carrier_watermark"], names)
        for row in res["unsupported"]:
            self.assertTrue(row["why"])
            self.assertTrue(row["needs"], "必须写清缺什么能力")

    def test_rules_table_covers_both_sides(self):
        table = cc.rules_table()
        self.assertEqual(sorted(cc.SUPPORTED), sorted(r["rule"] for r in table["compilable"]))
        self.assertEqual(sorted(cc.UNSUPPORTED),
                         sorted(r["rule"] for r in table["unsupported"]))


class TestEndToEnd(unittest.TestCase):
    def test_compiled_policy_judges_a_real_object(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            good = root / "good.md"
            good.write_text("AI 生成\n\n" + "正" * 300 + "\n\nAIGC: 1\n", encoding="utf-8")
            bad = root / "bad.md"
            bad.write_text("正文 TODO\n", encoding="utf-8")
            policy = _compile()["policy"]
            ok = check_policy.check(str(good), policy)
            self.assertEqual("ok", ok["verdict"], ok["findings"])
            self.assertEqual("invalid", check_policy.check(str(bad), policy)["verdict"])


if __name__ == "__main__":
    unittest.main()
