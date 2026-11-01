"""P5-01/P5-02/P5-03 装载期判据：插件清单必须**拒绝**该拒绝的一切。

重点不在「好清单能过」（那是正向覆盖），而在**拒绝面**：deny by default 若没有硬拒绝，
就只是一句口号。每条篡改对应一条真实越权/自相矛盾形态。
"""
import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "desktop" / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import plugin_manifest as pm  # noqa: E402

MANIFEST = ROOT / "engine" / "wasm" / "manifests" / "sha256.json"
WIT = ROOT / "engine" / "wasm" / "ninfenz-plugin.wit"


def _doc():
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def _tamper(fn):
    doc = copy.deepcopy(_doc())
    fn(doc)
    return pm.validate(doc)


class ShippedManifestTest(unittest.TestCase):
    def test_shipped_manifest_passes_validation(self):
        self.assertEqual([], pm.validate(_doc()))

    def test_shipped_manifest_matches_wit_contract(self):
        self.assertEqual([], pm.validate_against_wit(_doc(), WIT.read_text(encoding="utf-8")))

    def test_wit_declares_exactly_the_shipped_method(self):
        self.assertEqual(["sha256"], pm.wit_exports(WIT.read_text(encoding="utf-8")))

    def test_granted_capabilities_are_empty_even_though_declared(self):
        granted = pm.granted_capabilities(_doc())
        self.assertEqual([], granted["fs"])
        self.assertEqual([], granted["net"])
        self.assertEqual([], granted["env"])
        self.assertEqual("deny", granted["clocks"])
        self.assertEqual("deny", granted["random"])


class CapabilityDenyTest(unittest.TestCase):
    """deny by default（§18.3）：fs / net / env 的非空请求一律拒绝装载。"""

    def test_fs_request_is_refused(self):
        issues = _tamper(lambda d: d["methods"][0]["capabilities"].update(fs=["/data"]))
        self.assertTrue(any("fs" in i for i in issues), issues)

    def test_net_request_is_refused(self):
        issues = _tamper(lambda d: d["methods"][0]["capabilities"].update(net=["example.com"]))
        self.assertTrue(any("net" in i for i in issues), issues)

    def test_env_request_is_refused(self):
        issues = _tamper(lambda d: d["methods"][0]["capabilities"].update(env=["PATH"]))
        self.assertTrue(any("env" in i for i in issues), issues)

    def test_unknown_capability_key_is_refused(self):
        issues = _tamper(lambda d: d["methods"][0]["capabilities"].update(gpu=True))
        self.assertTrue(any("未知键" in i for i in issues), issues)

    def test_missing_capabilities_block_is_refused(self):
        issues = _tamper(lambda d: d["methods"][0].pop("capabilities"))
        self.assertTrue(any("capabilities" in i for i in issues), issues)


class DeterminismContractTest(unittest.TestCase):
    """确定性声明与非确定来源不能同时成立。"""

    def test_deterministic_with_clocks_is_refused(self):
        issues = _tamper(lambda d: d["methods"][0]["capabilities"].update(clocks="allow"))
        self.assertTrue(any("clocks" in i for i in issues), issues)

    def test_deterministic_with_random_is_refused(self):
        issues = _tamper(lambda d: d["methods"][0]["capabilities"].update(random="allow"))
        self.assertTrue(any("random" in i for i in issues), issues)

    def test_nondeterministic_may_declare_clocks(self):
        def patch(d):
            d["methods"][0]["determinism"] = "nondeterministic"
            d["methods"][0]["capabilities"]["clocks"] = "allow"
        self.assertEqual([], _tamper(patch))

    def test_bogus_determinism_level_is_refused(self):
        issues = _tamper(lambda d: d["methods"][0].update(determinism="maybe"))
        self.assertTrue(any("determinism" in i for i in issues), issues)


class FuelAndCostTest(unittest.TestCase):
    """实测教训：线性成本若只给固定预算，那个数字就是**隐式的输入长度上限**。"""

    def test_linear_cost_without_per_kib_is_refused(self):
        issues = _tamper(lambda d: d["methods"][0].update(fuel={"base": 1000}))
        self.assertTrue(any("per_kib" in i for i in issues), issues)

    def test_constant_cost_without_per_kib_is_fine(self):
        def patch(d):
            d["methods"][0]["cost"] = {"kind": "constant", "unit": "call"}
            d["methods"][0]["fuel"] = {"base": 1000}
        self.assertEqual([], _tamper(patch))

    def test_non_positive_fuel_base_is_refused(self):
        issues = _tamper(lambda d: d["methods"][0]["fuel"].update(base=0))
        self.assertTrue(any("base" in i for i in issues), issues)

    def test_bad_cost_model_is_refused(self):
        issues = _tamper(
            lambda d: d["methods"][0].update(cost={"kind": "quadratic", "unit": "byte"}))
        self.assertTrue(any("cost" in i for i in issues), issues)


class InterfaceAndShapeTest(unittest.TestCase):
    def test_method_not_in_wit_is_refused(self):
        doc = _doc()
        extra = copy.deepcopy(doc["methods"][0])
        extra["name"] = "md5"
        doc["methods"].append(extra)
        self.assertIn("清单方法 md5 不在 WIT 契约里",
                      pm.validate_against_wit(doc, WIT.read_text(encoding="utf-8")))

    def test_wit_method_without_manifest_entry_is_refused(self):
        doc = _doc()
        doc["methods"] = []
        issues = pm.validate_against_wit(doc, WIT.read_text(encoding="utf-8"))
        self.assertIn("WIT 方法 sha256 没有清单条目", issues)

    def test_missing_required_field_is_refused(self):
        issues = _tamper(lambda d: d.pop("abi"))
        self.assertTrue(any("abi" in i for i in issues), issues)

    def test_unknown_abi_is_refused(self):
        issues = _tamper(lambda d: d.update(abi="native-so"))
        self.assertTrue(any("ABI" in i for i in issues), issues)

    def test_artifact_path_escape_is_refused(self):
        issues = _tamper(lambda d: d["artifact"].update(path="../../etc/passwd"))
        self.assertTrue(any("逃逸" in i for i in issues), issues)

    def test_artifact_path_absolute_windows_is_refused(self):
        issues = _tamper(lambda d: d["artifact"].update(path="C:/Windows/system32/x.wasm"))
        self.assertTrue(any("逃逸" in i for i in issues), issues)

    def test_duplicate_method_name_is_refused(self):
        def patch(d):
            d["methods"].append(copy.deepcopy(d["methods"][0]))
        issues = _tamper(patch)
        self.assertTrue(any("重复" in i for i in issues), issues)

    def test_artifact_path_resolves_inside_root(self):
        got = pm.artifact_path(_doc(), str(ROOT))
        self.assertIsNotNone(got)
        self.assertTrue(str(got).startswith(str(ROOT)))
        self.assertEqual(None, pm.artifact_path({"artifact": {"path": "../x"}}, str(ROOT)))


if __name__ == "__main__":
    unittest.main()
