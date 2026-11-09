"""Ingress 网关判据（P6）：认证/白名单/限流/同意/记账五件，全部 fail-closed。

判据依据：合规网关宁可拒绝，不可静默降级。所以每条闸都要有「该拒就拒」的反例，
并且拒绝消息必须带修复指引（否则调用方无从修）。
"""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import mcp_ingress as mi  # noqa: E402
from core import mcp_manifest as mf  # noqa: E402
from core import mcp_runtime as mr  # noqa: E402


def _runtime(policy: dict, side_effects: dict | None = None):
    ing = mi.Ingress(policy, side_effects=side_effects or {})
    rt = mr.McpRuntime({"mcp": {"name": "t", "version": "0", "resources": []}},
                       ingress=ing)
    return rt, ing


def _call(rt, name: str, args: dict | None = None, meta: dict | None = None):
    params = {"name": name, "arguments": args or {}}
    if meta is not None:
        params["_meta"] = meta
    return rt.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": params})


class PolicyTest(unittest.TestCase):
    def test_default_policy_is_permissive(self):
        norm = mi.normalize({})
        self.assertEqual([], norm["tokens"])
        self.assertEqual(0, norm["max_calls_per_run"])

    def test_valid_policy(self):
        self.assertEqual([], mi.validate_policy({"tokens": ["t"], "allow": ["spec_list"]}))

    def test_allow_deny_overlap_is_rejected(self):
        issues = mi.validate_policy({"allow": ["a"], "deny": ["a"]})
        self.assertTrue(any("冲突" in i for i in issues))

    def test_negative_limits_are_rejected(self):
        self.assertTrue(any("不能为负" in i
                           for i in mi.validate_policy({"max_calls_per_run": -1})))


class AuthTest(unittest.TestCase):
    def test_token_required_and_accepted(self):
        rt, ing = _runtime({"tokens": ["t1"], "allow": ["spec_list"]})
        res = _call(rt, "spec_list", meta={"ingress_token": "t1"})
        self.assertIn("result", res)
        self.assertEqual(1, len(ing.receipts))

    def test_bad_token_is_denied(self):
        rt, _ing = _runtime({"tokens": ["t1"], "allow": ["spec_list"]})
        res = _call(rt, "spec_list", meta={"ingress_token": "nope"})
        self.assertIn("error", res)
        self.assertIn("修复指引", res["error"]["message"])

    def test_missing_token_is_denied(self):
        rt, _ing = _runtime({"tokens": ["t1"], "allow": ["spec_list"]})
        res = _call(rt, "spec_list")
        self.assertIn("error", res)


class AllowListTest(unittest.TestCase):
    def test_tool_not_in_allow_list_is_denied(self):
        rt, _ing = _runtime({"allow": ["spec_list"]})
        res = _call(rt, "asset_list")
        self.assertIn("error", res)
        self.assertIn("白名单", res["error"]["message"])

    def test_deny_wins_over_allow(self):
        rt, _ing = _runtime({"allow": ["spec_list"], "deny": ["spec_list"]})
        res = _call(rt, "spec_list")
        self.assertIn("error", res)
        self.assertIn("下架", res["error"]["message"])

    def test_empty_allow_means_all_tools(self):
        rt, _ing = _runtime({})
        self.assertIn("result", _call(rt, "spec_list"))


class RateLimitTest(unittest.TestCase):
    def test_limit_is_enforced(self):
        rt, _ing = _runtime({"allow": ["spec_list"], "max_calls_per_run": 2})
        self.assertIn("result", _call(rt, "spec_list"))
        self.assertIn("result", _call(rt, "spec_list"))
        res = _call(rt, "spec_list")
        self.assertIn("error", res)
        self.assertIn("上限", res["error"]["message"])


class ConsentTest(unittest.TestCase):
    def test_effectful_tool_needs_consent(self):
        rt, _ing = _runtime({"allow": ["spec_list"], "require_consent_for_effects": True},
                            side_effects={"spec_list": "local"})
        res = _call(rt, "spec_list")
        self.assertIn("error", res)
        self.assertIn("consent", res["error"]["message"])

    def test_effectful_tool_with_consent_passes(self):
        rt, _ing = _runtime({"allow": ["spec_list"], "require_consent_for_effects": True},
                            side_effects={"spec_list": "local"})
        res = _call(rt, "spec_list", meta={"consent": True})
        self.assertIn("result", res)

    def test_readonly_tool_needs_no_consent(self):
        rt, _ing = _runtime({"allow": ["spec_list"], "require_consent_for_effects": True},
                            side_effects={"spec_list": "none"})
        self.assertIn("result", _call(rt, "spec_list"))

    def test_oversized_args_are_denied(self):
        rt, _ing = _runtime({"allow": ["pattern_read"], "max_args_bytes": 10})
        res = _call(rt, "pattern_read", args={"uri": "x" * 200})
        self.assertIn("error", res)
        self.assertIn("字节", res["error"]["message"])


class ReceiptTest(unittest.TestCase):
    def test_each_allowed_call_leaves_a_receipt(self):
        rt, ing = _runtime({"allow": ["spec_list", "asset_list"]})
        _call(rt, "spec_list")
        _call(rt, "asset_list")
        self.assertEqual(2, len(ing.receipts))
        self.assertEqual(ing.receipts[0]["digest"], ing.receipts[1]["prev"])
        self.assertTrue(ing.replay()["ok"])

    def test_denied_call_leaves_no_receipt(self):
        rt, ing = _runtime({"tokens": ["t1"], "allow": ["spec_list"]})
        _call(rt, "spec_list", meta={"ingress_token": "bad"})
        self.assertEqual(0, len(ing.receipts))

    def test_receipt_same_across_two_identical_calls(self):
        rt, ing = _runtime({"allow": ["spec_list"]})
        _call(rt, "spec_list")
        _call(rt, "spec_list")
        first, second = ing.receipts
        self.assertTrue(mf.same_call_evidence(first, second))


if __name__ == "__main__":
    unittest.main()


class SelfcheckTest(unittest.TestCase):
    """启动自检判据：探针必须真的打到四道闸（否则自检形同虚设）。"""

    def setUp(self):
        self.cases = json.loads(
            (ROOT / "protocol" / "redteam" / "mcp_injection_cases.json").read_text(
                encoding="utf-8"))

    def test_bundled_policy_passes(self):
        issues = mi.selfcheck(self.cases["policy"], self.cases["side_effects"])
        self.assertEqual([], issues)

    def test_loose_policy_has_nothing_to_check(self):
        loose = {"schema": "nf-ingress-policy/1", "tokens": [], "allow": [], "deny": [],
                 "max_calls_per_run": 0, "require_consent_for_effects": False,
                 "max_args_bytes": 0}
        self.assertEqual([], mi.selfcheck(loose, {}))

    def test_selfcheck_is_not_vacuous(self):
        """把闸门换成「永远放行」，自检必须报错——证明它真的在打闸门。"""
        original = mi.Ingress.check_call
        try:
            mi.Ingress.check_call = lambda self, tool, args, params: None
            issues = mi.selfcheck(self.cases["policy"], self.cases["side_effects"])
        finally:
            mi.Ingress.check_call = original
        self.assertTrue(issues, "闸门被替换成放行后自检仍通过 = 判据空转")
        self.assertTrue(any("未被拦截" in i for i in issues))


if __name__ == "__main__":
    unittest.main()
