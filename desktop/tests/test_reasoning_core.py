"""推理面包内核心契约测试：导入 / policy / 无标量判定 / 先验 / 预算 / 搜索。

仓库风格：unittest + 顶部 sys.path 插入（见 test_cognition_event.py）。
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core.meta_cockpit import reasoning  # noqa: E402
from core.meta_cockpit.reasoning import bridge as nf  # noqa: E402
from core.meta_cockpit.reasoning import budget as rbudget  # noqa: E402
from core.meta_cockpit.reasoning import search as rsearch  # noqa: E402
from core.meta_cockpit.reasoning import session as rsession  # noqa: E402
from core.meta_cockpit.reasoning import steering as rsteering  # noqa: E402
from core.meta_cockpit.reasoning import value as rvalue  # noqa: E402
import core.meta_cockpit.method_memory as method_memory  # noqa: E402

PROMPT = "设计一个游戏的失败回滚与死亡重生机制"
FORBIDDEN_KEYS = {"reward", "q", "value", "score", "weights"}


def walk_keys(value):
    if isinstance(value, dict):
        for key, child in value.items():
            yield key
            yield from walk_keys(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk_keys(child)


def canonical(report):
    return json.dumps(report, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


class PackageImportTests(unittest.TestCase):
    def test_package_exports(self):
        for name in (
            "budget",
            "value",
            "steering",
            "search",
            "session",
            "portfolio",
            "anytime",
            "memory",
            "counterfactual",
            "certificate",
            "parallel",
            "trace",
        ):
            self.assertTrue(hasattr(reasoning, name), name)
        self.assertTrue(callable(reasoning.ReasoningSession))
        self.assertEqual(reasoning.session.SESSION_SCHEMA, "nf-reasoning-session/1")

    def test_default_policy_valid(self):
        policy = rsession.load_policy()
        self.assertEqual(policy["schema"], rsession.POLICY_SCHEMA)
        self.assertEqual(policy["beta_cap"], 0.5)
        self.assertIn(policy["mode"], rsession.MODES)
        self.assertIn(policy["search"]["backend"], rsession.SEARCH_BACKENDS)

    def test_policy_fail_closed(self):
        base = rsession.load_policy()
        cases = []
        case = json.loads(json.dumps(base))
        case["mode"] = "bogus"
        cases.append(case)
        case = json.loads(json.dumps(base))
        case["beta"] = 0.9
        cases.append(case)
        case = json.loads(json.dumps(base))
        case["search"]["max_nodes"] = 0
        cases.append(case)
        case = json.loads(json.dumps(base))
        case["schema"] = "nf-reasoning-policy/9"
        cases.append(case)
        for document in cases:
            with tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / "policy.json"
                path.write_text(json.dumps(document), encoding="utf-8")
                with self.assertRaises(ValueError):
                    rsession.load_policy(path)
        with self.assertRaises(ValueError):
            rsession.ReasoningSession(mode="bogus")
        with self.assertRaises(ValueError):
            rsession.ReasoningSession(search_nodes=0)
        with self.assertRaises(ValueError):
            rsession.ReasoningSession(beta=0.6)
        with self.assertRaises(ValueError):
            rsession.ReasoningSession(beta=-0.1)


class ValueContractTests(unittest.TestCase):
    def _pair(self):
        state = nf.initial_state(PROMPT)
        action = nf.candidate_actions(state)[0]
        result = nf.shadow_execute(state, action["cluster"])
        return state, result["state"], action["cluster"]

    def test_verdict_schema_has_no_scalar_score(self):
        self.assertEqual(rvalue.SCHEMA, "nf-step-verdict/1")
        before, after, cluster = self._pair()
        verdict = rvalue.step_verify(before, after, cluster, turn=0, step=1)
        self.assertEqual(verdict["schema"], "nf-step-verdict/1")
        self.assertTrue(verdict["no_score"])
        self.assertEqual(
            set(verdict),
            {
                "schema",
                "turn",
                "step",
                "cluster",
                "checks",
                "mandatory",
                "verdict",
                "gains",
                "violations",
                "advisory",
                "no_score",
                "digest",
            },
        )
        self.assertEqual(set(walk_keys(verdict)) & FORBIDDEN_KEYS, set())
        for check in verdict["checks"]:
            self.assertIn(check["ok"], (True, False, "unknown"))
            self.assertEqual(len(check["witness"]), 64)
        for value in verdict["gains"].values():
            self.assertIsInstance(value, int)
        self.assertEqual(len(verdict["digest"]), 64)

    def test_step_verify_idempotent(self):
        before, after, cluster = self._pair()
        verifier = rvalue.StepVerifier()
        first = verifier.step_verify(before, after, cluster, turn=2, step=3)
        second = verifier.step_verify(before, after, cluster, turn=2, step=3)
        self.assertEqual(canonical(first), canonical(second))
        self.assertNotIn("cache", canonical(first))
        self.assertNotIn("hit", set(walk_keys(first)))
        other = verifier.step_verify(before, after, cluster, turn=3, step=3)
        self.assertNotEqual(first["digest"], other["digest"])

    def test_external_advisory_is_digest_only(self):
        before, after, cluster = self._pair()
        verifier = rvalue.StepVerifier(
            external_providers={"audit-model": lambda *_: {"value": 0.99, "evidence": ["x"]}}
        )
        verdict = verifier.step_verify(before, after, cluster, turn=1, step=1)
        self.assertEqual(len(verdict["advisory"]), 1)
        self.assertEqual(set(verdict["advisory"][0]), {"source", "role", "digest"})
        self.assertEqual(verdict["advisory"][0]["role"], "external-advisory")
        self.assertEqual(set(walk_keys(verdict)) & (FORBIDDEN_KEYS | {"escalated"}), set())

    def test_invalid_state_fail_closed(self):
        verdict = rvalue.step_verify({}, {}, ["k.represent"])
        self.assertEqual(verdict["verdict"], "fail")
        self.assertIn("invalid-state", verdict["violations"])


class SteeringTests(unittest.TestCase):
    def _candidates(self):
        state = nf.initial_state(PROMPT)
        actions = nf.candidate_actions(state)[:4]
        return state, actions

    def test_beta_capped_at_half(self):
        state, candidates = self._candidates()
        audit = rsteering.steer(state, candidates, beta=100.0)
        self.assertEqual(rsteering.MAX_BETA, 0.5)
        self.assertEqual(audit["beta_applied"], 0.5)
        self.assertEqual(audit["beta_cap"], 0.5)
        self.assertIs(audit["clamped"], True)
        self.assertIn("beta-clamped", audit["warnings"])
        self.assertEqual(audit["prior_source"], "uniform")
        self.assertEqual(audit["normalization"], "none")
        self.assertAlmostEqual(sum(audit["posterior"]), 1.0, places=9)
        self.assertEqual(set(walk_keys(audit)) & FORBIDDEN_KEYS, set())
        for entry in audit["candidates"]:
            self.assertIn("prior_terms", entry)
            self.assertIn("bias", entry)
            self.assertNotIn("score", entry)

    def test_steering_deterministic(self):
        state, candidates = self._candidates()
        first = rsteering.steer(state, candidates, beta=0.5)
        second = rsteering.steer(state, candidates, beta=0.5)
        self.assertEqual(first["digest"], second["digest"])
        self.assertEqual(first["posterior"], second["posterior"])

    def test_steering_invalid_inputs(self):
        state, candidates = self._candidates()
        with self.assertRaises(ValueError):
            rsteering.steer(state, [])
        with self.assertRaises(ValueError):
            rsteering.steer(None, candidates)
        with self.assertRaises(ValueError):
            rsteering.steer(state, [{"cluster": ["not.an.atom"], "cost": 1}])


class BudgetTests(unittest.TestCase):
    def test_allocate_for_and_shares_conserve(self):
        budget = rbudget.allocate_for(9)
        self.assertGreater(budget.max_nodes, 0)
        self.assertGreater(budget.unit_budget, 0)
        self.assertIsNone(budget.max_seconds)
        self.assertEqual(len(budget.as_dict()["digest"]), 64)
        shares = rbudget.allocate_shares(60, [0, 3, 9])
        self.assertEqual(sum(shares), 60)
        self.assertTrue(all(share >= 1 for share in shares))
        self.assertLessEqual(shares[0], shares[1])

    def test_budget_validation_and_stop_priority(self):
        for kwargs in (
            {"max_nodes": 0},
            {"max_depth": 0},
            {"max_seconds": -1.0},
            {"unit_budget": 0},
        ):
            with self.assertRaises(ValueError):
                rbudget.Budget(**kwargs)
        budget = rbudget.Budget(max_nodes=10, max_depth=4)
        self.assertEqual(
            rbudget.should_stop(budget=budget, complete=True)["reason"], "complete"
        )
        self.assertEqual(
            rbudget.should_stop(budget=budget, nodes=10)["reason"], "max-nodes"
        )
        self.assertEqual(
            rbudget.should_stop(budget=budget, depth=4)["reason"], "max-depth"
        )


class SearchTests(unittest.TestCase):
    def setUp(self):
        self.state = nf.initial_state(PROMPT)
        self.budget = rbudget.Budget(max_nodes=60, max_depth=6)

    def test_best_first_deterministic_and_complete(self):
        first = rsearch.search(state=self.state, budget=self.budget)
        second = rsearch.search(state=self.state, budget=self.budget)
        self.assertTrue(first["complete"])
        self.assertEqual(first["schema"], rsearch.SCHEMA)
        self.assertEqual(first["search_stats"]["backend"], "best_first")
        self.assertEqual(canonical(first), canonical(second))
        self.assertEqual(first["trace_digest"], second["trace_digest"])

    def test_puct_transposition(self):
        first = rsearch.search(state=self.state, budget=self.budget, mode="puct")
        second = rsearch.search(state=self.state, budget=self.budget, mode="puct")
        self.assertEqual(canonical(first), canonical(second))
        self.assertGreater(first["stats"]["transpositions"], 0)

    def test_budget_exhaustion_degrades_not_fails(self):
        tiny = rbudget.Budget(max_nodes=3, max_depth=3)
        report = rsearch.search(state=self.state, budget=tiny)
        self.assertEqual(report["status"], "pass")
        self.assertEqual(report["termination"], "search-degraded")
        self.assertIs(report["search_stats"]["degraded"], True)
        self.assertGreaterEqual(report["best_path"]["depth"], 1)
        self.assertEqual(report["best_path"]["source"], "greedy-fallback")

    def test_public_report_has_no_scoring_keys(self):
        cases = [
            rsearch.search(state=self.state, budget=self.budget),
            rsearch.search(state=self.state, budget=self.budget, mode="puct"),
            rsearch.search(state=self.state, budget=rbudget.Budget(max_nodes=3, max_depth=3)),
            rsearch.greedy(state=self.state, budget=self.budget),
        ]
        for report in cases:
            keys = set(walk_keys(report))
            self.assertEqual(keys & FORBIDDEN_KEYS, set())
            self.assertNotIn("components", keys)

    def test_state_digest_matches_cockpit_core_signature(self):
        self.assertEqual(
            nf.state_digest(self.state), method_memory.core_signature(self.state)
        )

    def test_shadow_execute_is_read_only(self):
        action = nf.candidate_actions(self.state)[0]
        before_digest = nf.state_digest(self.state)
        result = nf.shadow_execute(self.state, action["cluster"])
        self.assertEqual(result["status"], "pass")
        self.assertEqual(nf.state_digest(self.state), before_digest)
        self.assertEqual(
            result["changed_keys"],
            sorted(nf.available_keys(result["state"]) - nf.available_keys(self.state)),
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
