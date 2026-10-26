"""T7.1 · 契约语义核心（五概念 + W1/W2/W3 + 规范形）单测。

覆盖：当前仓正例（无 FAIL、不可判定项必须 WARN 且带原因）、≥6 个注入负例（孤儿事件 /
跨域模块 / 未登记层序倒挂 / 槽未供 / 重复模块声明 / 门缺失 / 门非全）、canonical 幂等与
稳定性性质测试、CLI 形状与退出码（0/1/2，fail-closed）。
"""
import contextlib
import copy
import io
import json
import random
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import contract_semantics as cs  # noqa: E402

SCRIPT = ROOT / "scripts" / "nf.py"
_MODEL = None


def model():
    global _MODEL
    if _MODEL is None:
        _MODEL = cs.load_model(ROOT)
    return _MODEL


def fresh():
    return copy.deepcopy(model())


def codes(report):
    return {i["code"] for i in report["issues"]}


class PositiveTest(unittest.TestCase):
    def test_current_repo_is_well_formed(self):
        report = cs.check_model(fresh())
        self.assertEqual([], report["fails"],
                         "当前仓不应有 FAIL：%s" % [(i["code"], i["subject"])
                                                    for i in report["fails"]])
        self.assertIn(report["verdict"], ("pass", "warn"))

    def test_issues_are_structured(self):
        report = cs.check_model(fresh())
        self.assertTrue(report["issues"])
        for i in report["issues"]:
            for key in ("rule", "code", "severity", "subject", "message", "evidence", "fix"):
                self.assertIn(key, i)
            self.assertIn(i["severity"], ("FAIL", "WARN"))
            self.assertIsInstance(i["evidence"], list)

    def test_unverifiable_items_are_warn_not_pass(self):
        report = cs.check_model(fresh())
        by_code = {i["code"]: i for i in report["issues"]}
        self.assertIn("asset_domain_unverifiable", by_code,
                      "资产域缺字段必须 WARN，不得静默当通过")
        self.assertEqual("WARN", by_code["asset_domain_unverifiable"]["severity"])
        self.assertIn("不可判定", by_code["asset_domain_unverifiable"]["message"])
        self.assertIn("gate_unbound", by_code, "P04/P05 未绑定 M80 必须 WARN")
        self.assertEqual("WARN", by_code["gate_unbound"]["severity"])

    def test_w1_registered_inversion_is_warn_with_evidence(self):
        report = cs.check_model(fresh())
        rows = [i for i in report["issues"]
                if i["code"] == "layer_inversion_registered"]
        self.assertTrue(rows, "已登记倒挂应以 WARN 出现")
        self.assertIn("M06←M20", {i["subject"] for i in rows})
        self.assertTrue(any(i["evidence"] for i in rows))

    def test_gate_policy_is_type_level_total(self):
        self.assertEqual({"pass", "warn", "fail"}, set(cs.GATE_POLICY.verdicts))
        self.assertEqual("fail", cs.GATE_POLICY.on_undefined)

    def test_model_has_five_concepts(self):
        m = model()
        for key in ("modules", "slots", "pipelines", "publishers", "subscribers"):
            self.assertIn(key, m)
        self.assertTrue(m["slots"] and m["pipelines"] and m["core_contracts"])


class InjectedNegativeTest(unittest.TestCase):
    """≥6 个注入负例：每条都能把对应规则从正例打成 FAIL。"""

    def test_orphan_event(self):
        m = fresh()
        m["subscribers"]["ghost_event_t71"] = ["M00"]
        report = cs.check_model(m)
        self.assertIn("orphan_event", codes(report))
        self.assertTrue(report["fails"])

    def test_cross_domain_module(self):
        m = fresh()
        pkg = m["packages"]["校园情感领域包"]
        pkg["module_ids"].append("生存:M10")
        m["module_claims"].setdefault("生存:M10", []).append("校园情感领域包")
        report = cs.check_model(m)
        self.assertIn("cross_domain_module", codes(report))

    def test_unregistered_layer_inversion(self):
        m = fresh()
        m["layer_exceptions"].pop("M13←M20")
        report = cs.check_model(m)
        self.assertIn("layer_inversion", codes(report))
        row = next(i for i in report["fails"] if i["code"] == "layer_inversion")
        self.assertIn("M13←M20", row["subject"])

    def test_slot_unbound(self):
        m = fresh()
        wm = m["core_contracts"]["M50"]["world_model"]
        wm["abstract_state"]["variables"].append(
            {"name": "ghost", "kind": "string", "source": "M50",
             "slot": "WorldState.time.ghost"})
        report = cs.check_model(m)
        self.assertIn("slot_unbound", codes(report))

    def test_duplicate_module_claim(self):
        m = fresh()
        m["module_claims"]["M01"] = list(m["module_claims"].get("M01") or []) + \
            ["校园情感领域包"]
        report = cs.check_model(m)
        self.assertIn("duplicate_module_claim", codes(report))

    def test_gate_missing(self):
        m = fresh()
        m["pipelines"]["P01"]["layers"] = [l for l in m["pipelines"]["P01"]["layers"]
                                           if l["id"] != "P80"]
        m["pipelines"]["P01"]["p80"] = None
        report = cs.check_model(m)
        self.assertIn("gate_missing", codes(report))

    def test_gate_not_total(self):
        m = fresh()
        m["gate_policy"]["on_undefined"] = "pass"
        report = cs.check_model(m)
        self.assertIn("gate_not_total", codes(report))
        self.assertTrue(any(i["severity"] == "FAIL" for i in report["fails"]))


class CanonicalTest(unittest.TestCase):
    def test_digest_is_sha256_hex(self):
        payload = cs.canonical_payload(model())
        self.assertRegex(cs.canonical_digest(payload), r"^[0-9a-f]{64}$")

    def test_idempotent_bytes(self):
        payload = cs.canonical_payload(model())
        b1 = cs.canonical_bytes(payload)
        b2 = cs.canonical_bytes(cs.canonicalize(payload))
        self.assertEqual(b1, b2, "canonicalize 必须幂等（两次逐字节一致）")
        self.assertEqual(cs.canonical_digest(payload),
                         cs.canonical_digest(cs.canonicalize(payload)))

    def test_key_order_independent(self):
        a = {"b": 1, "a": {"y": 2, "x": [3, 1, 2]}}
        b = {"a": {"x": [2, 3, 1], "y": 2}, "b": 1.0}
        self.assertEqual(cs.canonicalize(a), cs.canonicalize(b))
        self.assertEqual(cs.canonical_digest(cs.canonicalize(a)),
                         cs.canonical_digest(cs.canonicalize(b)))

    def test_numeric_and_path_normalization(self):
        self.assertEqual(cs.canonicalize({"n": 1.0}), cs.canonicalize({"n": 1}))
        self.assertEqual(cs.canonicalize({"p": "a\\b\\c.md"}),
                         cs.canonicalize({"p": "a/b/c.md"}))

    def test_property_random_subsets_stable(self):
        """性质测试：随机子集规范形稳定（同一子集两次一致、乱序输入同 digest）。"""
        rng = random.Random(20261026)
        all_ids = [str(m.get("id")) for m in
                   sorted((ROOT / "desktop" / "src" / "core" / "registry.json").read_text(
                       encoding="utf-8") and json.loads(
                           (ROOT / "desktop" / "src" / "core" / "registry.json").read_text(
                               encoding="utf-8"))["modules"],
                          key=lambda m: str(m.get("id")))]
        for _ in range(20):
            subset = rng.sample(all_ids, rng.randint(1, len(all_ids)))
            p1 = cs.canonical_payload(model(), subset)
            p2 = cs.canonical_payload(model(), subset)
            self.assertEqual(cs.canonical_bytes(p1), cs.canonical_bytes(p2),
                             "同一子集两次规范形必须逐字节一致")
            shuffled = copy.deepcopy(p1)
            for key in ("modules", "protocols"):
                rng.shuffle(shuffled[key])
            self.assertEqual(cs.canonical_bytes(p1),
                             cs.canonical_bytes(cs.canonicalize(shuffled)),
                             "输入顺序不影响规范形 digest")


class CliTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import importlib.util
        spec = importlib.util.spec_from_file_location("nf_spec_probe", SCRIPT)
        assert spec is not None and spec.loader is not None
        mod = importlib.util.module_from_spec(spec)
        sys.modules["nf_spec_probe"] = mod
        spec.loader.exec_module(mod)
        cls.nf = mod
        cls.parser = mod._build_parser()

    def _run(self, *argv, patch=None):
        buf, err = io.StringIO(), io.StringIO()
        args = self.parser.parse_args(["spec", *argv])
        ctx = mock.patch.object(cs, "load_model", side_effect=patch) if patch else \
            contextlib.nullcontext()
        with ctx, contextlib.redirect_stdout(buf), contextlib.redirect_stderr(err):
            rc = self.nf._cmd_spec(args)
        return rc, buf.getvalue(), err.getvalue()

    def test_check_json_pass(self):
        rc, out, err = self._run("check", "--core", "--json")
        self.assertEqual(0, rc, err)
        doc = json.loads(out)
        self.assertEqual([], doc["fails"])
        self.assertIn("verdict", doc)

    def test_check_requires_core(self):
        rc, _out, err = self._run("check", "--json")
        self.assertEqual(2, rc, "未加 --core 必须 rc=2（目前仅支持核心面）")
        self.assertIn("--core", err)

    def test_check_fail_rc1(self):
        m = fresh()
        m["gate_policy"]["on_undefined"] = "pass"
        rc, out, _err = self._run("check", "--core", "--json", patch=lambda _r: m)
        self.assertEqual(1, rc)
        self.assertEqual("fail", json.loads(out)["verdict"])

    def test_check_load_error_rc2(self):
        def boom(_root):
            raise ValueError("registry 不可读（探针）")
        rc, _out, err = self._run("check", "--core", patch=boom)
        self.assertEqual(2, rc, "不可判定必须 rc=2，不得假绿")
        self.assertIn("不可判定", err)

    def test_canonical_json_matches_core(self):
        rc, out, err = self._run("canonical", "--json")
        self.assertEqual(0, rc, err)
        doc = json.loads(out)
        expect = cs.canonical_digest(cs.canonical_payload(model()))
        self.assertEqual(expect, doc["digest"])
        self.assertTrue(doc["idempotent"])

    def test_ls_regression(self):
        rc, out, err = self._run("ls")
        self.assertEqual(0, rc, err)
        self.assertIn("nf spec ls", out)
        self.assertIn("registry_schema_version", out)


if __name__ == "__main__":
    unittest.main()
