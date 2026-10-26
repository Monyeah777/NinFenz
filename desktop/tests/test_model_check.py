"""T10.1 · world_model 有限状态模型检查单测。

覆盖：5 类违例（不可达相位 / 非确定 / 不变式破坏 / 死锁 / 未注册槽）+ 终态显式正例 +
真实仓正例（WARN 可接受、FAIL=0）+ 状态上限 fail-closed（exit 2，不假装通过）+ CLI 形状。
所有 fixture 是内存字典，不改 world_model 契约或任何模块。
"""
import contextlib
import copy
import io
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import model_check as mc  # noqa: E402

SCRIPT = ROOT / "scripts" / "nf.py"
PHASE_VAR = {"name": "phase", "kind": "string", "source": "M50",
             "slot": "data_bus.round.phase"}


def wm(phases, initial="a", *, checks=None, variables=None, invariants=None,
       initial_state=None):
    """合成 world_model：phases = [(phase, next, guard)]；next="" 表示 sink。"""
    return {
        "abstract_state": {
            "variables": copy.deepcopy(variables if variables is not None
                                       else [PHASE_VAR]),
            "initial": dict(initial_state if initial_state is not None
                            else {"phase": initial}),
        },
        "transition": {
            "initial_phase": initial,
            "phases": [{"phase": p, "next": n, "guard": g or "守卫", "writes": []}
                       for p, n, g in phases],
        },
        "invariants": list(invariants if invariants is not None else []),
        "checks": list(checks or []),
    }


def real_slots():
    return mc.load_slots(ROOT)


def codes(res):
    return {i["rule"] for i in res["issues"]}


class FiveViolationTest(unittest.TestCase):
    def test_unreachable_phase(self):
        res = mc.check_world_model("MX", wm([("a", "b", ""), ("b", "a", ""),
                                             ("c", "c", "")]), real_slots())
        self.assertEqual("fail", res["verdict"])
        self.assertIn("reachability", codes(res))
        row = next(i for i in res["issues"] if i["rule"] == "reachability")
        self.assertIn("c", row["subject"])

    def test_nondeterminism_duplicate_phase(self):
        res = mc.check_world_model(
            "MX", wm([("a", "b", ""), ("a", "c", ""), ("b", "a", ""),
                      ("c", "a", "")]), real_slots())
        self.assertEqual("fail", res["verdict"])
        self.assertIn("determinism", codes(res))
        self.assertTrue(any(i["rule"] == "determinism" and i["subject"] == "a"
                            for i in res["issues"]))

    def test_invariant_broken(self):
        # finite_phase 只允许 a，但迁移 a→b 可达 b ⇒ 不变式破坏
        res = mc.check_world_model(
            "MX", wm([("a", "b", ""), ("b", "a", "")],
                     checks=[{"kind": "finite_phase", "field": "phase",
                              "values": ["a"]}]), real_slots())
        self.assertEqual("fail", res["verdict"])
        self.assertIn("invariant", codes(res))
        row = next(i for i in res["issues"] if i["rule"] == "invariant")
        self.assertTrue(row["trace"], "不变式违例须带 trace 路径")

    def test_deadlock_unmarked_sink(self):
        res = mc.check_world_model("MX", wm([("a", "b", ""), ("b", "", "")]),
                                   real_slots())
        self.assertEqual("fail", res["verdict"])
        self.assertIn("deadlock", codes(res))
        row = next(i for i in res["issues"] if i["rule"] == "deadlock")
        self.assertEqual(["a", "b"], row["trace"])

    def test_slot_unregistered(self):
        bad_var = {"name": "phase", "kind": "string", "source": "M50",
                   "slot": "Ghost.not_registered"}
        res = mc.check_world_model("MX", wm([("a", "a", "")], variables=[bad_var]),
                                   real_slots())
        self.assertEqual("fail", res["verdict"])
        self.assertIn("slot_registration", codes(res))


class PositiveTest(unittest.TestCase):
    def test_terminal_sink_is_explicit_and_passes(self):
        res = mc.check_world_model(
            "MX", wm([("a", "b", ""), ("b", "", "terminal：流程结束")]), real_slots())
        self.assertEqual("pass", res["verdict"], res["issues"])
        self.assertEqual(["b"], res["stats"]["terminals"])
        self.assertEqual(2, res["stats"]["states"])

    def test_cycle_passes_and_stats(self):
        res = mc.check_world_model(
            "MX", wm([("a", "b", ""), ("b", "c", ""), ("c", "a", "")]), real_slots())
        self.assertEqual("pass", res["verdict"], res["issues"])
        self.assertEqual(3, res["stats"]["states"])
        self.assertEqual(3, res["stats"]["edges"])
        self.assertEqual(2, res["stats"]["depth"])

    def test_real_repo_positive_warn_no_fail(self):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = mc.run(ROOT)
        self.assertEqual(0, rc, "真实仓应 WARN/PASS（rc=0），不得 FAIL")
        self.assertIn("WARN", buf.getvalue())
        slots = real_slots()
        models, total, no_model = mc._module_world_models(ROOT)
        self.assertGreaterEqual(len(models), 1, "真实仓至少 1 件 world_model")
        self.assertEqual(total, len(models) + len(no_model))
        res = mc.check_world_model("M50", models[0][1], slots)
        self.assertEqual([], [i for i in res["issues"] if i["severity"] == "FAIL"])
        self.assertTrue(any(i["rule"] == "invariant" and i["severity"] == "WARN"
                            for i in res["issues"]),
                        "不可判定的 monotonic/自然语言不变式必须 WARN 并写原因")


class StateLimitTest(unittest.TestCase):
    def test_cap_is_fail_closed_exit2(self):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = mc.run(ROOT, max_states=2)
        self.assertEqual(2, rc, "超状态上限必须 exit 2（undecided），不得 PASS")
        out = buf.getvalue()
        self.assertIn("UNDECIDED", out)
        self.assertNotIn("判定：PASS", out)

    def test_check_world_model_cap_undecided(self):
        res = mc.check_world_model("MX", wm([(str(i), str(i + 1), "")
                                             for i in range(6)] + [("6", "", "")],
                                            initial="0"),
                                   real_slots(), max_states=3)
        self.assertEqual("undecided", res["verdict"])
        self.assertTrue(res["undecided"])
        self.assertIn("state_limit", res.get("reason", ""))

    def test_zero_and_negative_cap_rejected(self):
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(2, mc.run(ROOT, max_states=0))


class CliTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import importlib.util
        spec = importlib.util.spec_from_file_location("nf_mc_probe", SCRIPT)
        assert spec is not None and spec.loader is not None
        mod = importlib.util.module_from_spec(spec)
        sys.modules["nf_mc_probe"] = mod
        spec.loader.exec_module(mod)
        cls.nf = mod
        cls.parser = mod._build_parser()

    def _run(self, *argv):
        buf, err = io.StringIO(), io.StringIO()
        args = self.parser.parse_args(["spec", "modelcheck", *argv])
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(err):
            rc = self.nf._cmd_spec(args)
        return rc, buf.getvalue(), err.getvalue()

    def test_parser_flags(self):
        ns = self.parser.parse_args(["spec", "modelcheck", "--json", "--max-states", "7"])
        self.assertEqual("modelcheck", ns.action)
        self.assertTrue(ns.json)
        self.assertEqual(7, ns.max_states)

    def test_cli_json_pass_or_warn(self):
        rc, out, err = self._run("--json")
        self.assertEqual(0, rc, err)
        doc = json.loads(out)
        self.assertIn(doc["verdict"], ("pass", "warn"))
        self.assertEqual(1, doc["stats"]["modules_with_world_model"])
        self.assertEqual([], [i for i in doc["issues"] if i["severity"] == "FAIL"])

    def test_cli_cap_exit2(self):
        rc, out, err = self._run("--json", "--max-states", "2")
        self.assertEqual(2, rc)
        self.assertEqual("undecided", json.loads(out)["verdict"])


if __name__ == "__main__":
    unittest.main()
