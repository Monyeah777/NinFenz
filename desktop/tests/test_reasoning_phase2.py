"""Phase 2 模块测试：portfolio / anytime / memory / counterfactual / certificate / parallel。"""

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core.meta_cockpit.reasoning import anytime  # noqa: E402
from core.meta_cockpit.reasoning import bridge as nf  # noqa: E402
from core.meta_cockpit.reasoning import budget as rbudget  # noqa: E402
from core.meta_cockpit.reasoning import certificate  # noqa: E402
from core.meta_cockpit.reasoning import counterfactual  # noqa: E402
from core.meta_cockpit.reasoning import memory as rmemory  # noqa: E402
from core.meta_cockpit.reasoning import parallel  # noqa: E402
from core.meta_cockpit.reasoning import portfolio  # noqa: E402
from core.meta_cockpit.reasoning import search as rsearch  # noqa: E402

PROMPT = "设计一个游戏的失败回滚与死亡重生机制"
FORBIDDEN_KEYS = {"reward", "q", "value", "score", "weights"}


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def walk_keys(value):
    if isinstance(value, dict):
        for key, child in value.items():
            yield key
            yield from walk_keys(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk_keys(child)


def real_state():
    return nf.initial_state(PROMPT)


def real_plan():
    state = real_state()
    report = rsearch.search(
        state=state, budget=rbudget.Budget(max_nodes=40, max_depth=6)
    )
    return state, [list(cluster) for cluster in report["best_path"]["actions"]]


class PortfolioTests(unittest.TestCase):
    def test_budget_accounting_and_rounds(self):
        state = real_state()
        report = portfolio.run(state, total_nodes=80, rounds=2)
        self.assertEqual(report["schema"], portfolio.SCHEMA)
        totals = report["totals"]
        self.assertLessEqual(totals["allocated"], 80)
        self.assertLessEqual(totals["spent"], totals["allocated"])
        self.assertEqual(totals["spent"], totals["nodes"])
        self.assertEqual(
            totals["spent"],
            sum(item["nodes"] for round_row in report["rounds"] for item in round_row["results"]),
        )
        self.assertIn(report["winner"], portfolio.BACKENDS)
        self.assertEqual(len(report["trace_digest"]), 64)
        self.assertLessEqual(len(report["rounds"]), 2)

    def test_portfolio_deterministic_and_no_scoring(self):
        state = real_state()
        first = portfolio.run(state, total_nodes=60, rounds=2)
        second = portfolio.run(state, total_nodes=60, rounds=2)
        self.assertEqual(canonical(first), canonical(second))
        self.assertEqual(first["trace_digest"], second["trace_digest"])
        self.assertEqual(set(walk_keys(first)) & FORBIDDEN_KEYS, set())

    def test_portfolio_fail_closed(self):
        state = real_state()
        with self.assertRaises(ValueError):
            portfolio.run(state, total_nodes=0)
        with self.assertRaises(ValueError):
            portfolio.run(state, backends=("bogus",))
        with self.assertRaises(ValueError):
            portfolio.run(state, rounds=0)
        with self.assertRaises(ValueError):
            portfolio.run(state, backends=("greedy", "greedy"))


class AnytimeTests(unittest.TestCase):
    def test_gap_is_monotone_and_advance_zero_is_idempotent(self):
        state = real_state()
        session = anytime.AnytimeSession(state, total_nodes=80, turns_left=4)
        initial = session.advance(0)
        self.assertEqual(initial["spent"], 0)
        self.assertEqual(initial["best_gap"], len(nf.completion_gaps(state)))
        self.assertEqual(canonical(initial), canonical(session.advance(0)))
        gaps = [initial["best_gap"]]
        for _ in range(4):
            view = session.advance(10)
            gaps.append(view["best_gap"])
        self.assertEqual(gaps, sorted(gaps, reverse=True))
        self.assertLessEqual(session.spent, 80)
        summary = session.summary()
        self.assertEqual(summary["schema"], anytime.SCHEMA)
        for row in summary["trace"]:
            self.assertLessEqual(row["nodes_used"], row["nodes"])
            self.assertIn(row["best_gap"], gaps)
        self.assertEqual(set(walk_keys(summary)) & FORBIDDEN_KEYS, set())

    def test_anytime_deterministic_and_close_turn(self):
        def run():
            session = anytime.AnytimeSession(real_state(), total_nodes=60, turns_left=3)
            session.advance(20)
            session.close_turn(False)
            session.advance(20)
            return session.summary()

        first, second = run(), run()
        self.assertEqual(canonical(first), canonical(second))
        session = anytime.AnytimeSession(real_state(), total_nodes=60, turns_left=3)
        session.close_turn(True)
        self.assertTrue(session.done)
        self.assertTrue(session.summary()["done"])

    def test_anytime_fail_closed(self):
        state = real_state()
        with self.assertRaises(ValueError):
            anytime.AnytimeSession(state, total_nodes=0)
        with self.assertRaises(ValueError):
            anytime.AnytimeSession(state, turns_left=0)
        session = anytime.AnytimeSession(state, total_nodes=40, turns_left=2)
        with self.assertRaises(ValueError):
            session.advance(-1)
        with self.assertRaises(ValueError):
            session.close_turn(1)


class MemoryTests(unittest.TestCase):
    def test_beta_lower_golden(self):
        values = [round(rmemory.beta_lower(n, n), 3) for n in (3, 5, 7, 8, 15)]
        self.assertEqual(values, [0.562, 0.681, 0.750, 0.774, 0.866])
        with self.assertRaises(ValueError):
            rmemory.beta_lower(2, 3)
        with self.assertRaises(ValueError):
            rmemory.beta_lower(-1, 0)

    def test_memory_threshold_hit_and_body(self):
        state = real_state()
        plan = real_plan()[1][:2]
        memory = rmemory.PlanMemory(threshold=0.75)
        for _ in range(3):
            memory.record(state, plan, True, source_digest="a" * 64)
        self.assertIsNone(memory.lookup(state))  # beta_lower(3,3)=0.562 < 0.75
        for _ in range(4):
            memory.record(state, plan, True, source_digest="a" * 64)
        hit = memory.lookup(state)
        self.assertIsNotNone(hit)
        self.assertEqual(set(hit), {"memory_hit", "trials", "completions", "plan"})
        self.assertEqual(hit["trials"], 7)
        self.assertEqual(hit["plan"], plan)
        self.assertEqual(set(walk_keys(hit)) & FORBIDDEN_KEYS, set())
        self.assertTrue(memory.peek(state))
        self.assertEqual(memory.steering_features(state)["memory_hit"], 1)

    def test_memory_quarantine_and_source_digest(self):
        state = real_state()
        plan = real_plan()[1][:2]
        memory = rmemory.PlanMemory(threshold=0.75)
        with self.assertRaises(ValueError):
            memory.record(state, plan, True, source_digest="not-a-digest")
        memory.record(state, plan, False, source_digest="a" * 64)
        memory.record(state, plan, False, source_digest="a" * 64)
        self.assertIsNone(memory.lookup(state))
        self.assertEqual(memory.stats()["quarantined"], 1)

    def test_memory_persistence_drift_without_content(self):
        state = real_state()
        plan = real_plan()[1][:2]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "memory.json"
            memory = rmemory.PlanMemory(path=path, threshold=0.75)
            for _ in range(7):
                memory.record(state, plan, True, source_digest="a" * 64)
            memory.save()
            text = path.read_text(encoding="utf-8")
            self.assertNotIn(PROMPT, text)
            self.assertNotIn("游戏", text)
            # 同契约 digest 重新加载：记录保留
            same = rmemory.PlanMemory(path=path, threshold=0.75)
            self.assertIsNotNone(same.lookup(state))
            self.assertFalse(same.stats()["drift"])
            # 契约漂移：全部失效 + 归档
            drifted = rmemory.PlanMemory(
                path=path,
                contracts_digest="b" * 64,
                threshold=0.75,
            )
            self.assertIsNone(drifted.lookup(state))
            self.assertTrue(drifted.stats()["drift"])
            self.assertTrue(list(Path(tmp).glob("*.drift-*.json")))
            # 损坏文件 fail-closed
            path.write_text("{corrupt", encoding="utf-8")
            with self.assertRaises(ValueError):
                rmemory.PlanMemory(path=path, threshold=0.75)


class CounterfactualTests(unittest.TestCase):
    def test_attribution_bounded_and_minimal(self):
        state, plan = real_plan()
        report = counterfactual.attribute(state, plan, budget=64)
        self.assertEqual(report["schema"], counterfactual.SCHEMA)
        self.assertLessEqual(len(report["minimal_plan"]), len(plan))
        self.assertTrue(report["bounded"])
        self.assertIsInstance(report["minimal_sufficient"], bool)
        covered = set(report["necessary"]) | set(report["removed"]) | set(report["unknown"])
        self.assertEqual(covered, set(range(len(plan))))
        self.assertEqual(len(report["replay_digest"]), 64)
        self.assertEqual(set(walk_keys(report)) & FORBIDDEN_KEYS, set())
        self.assertEqual(
            canonical(report), canonical(counterfactual.attribute(state, plan, budget=64))
        )

    def test_unknown_bounded_not_necessary(self):
        state, plan = real_plan()
        report = counterfactual.attribute(state, plan[:2], budget=1)
        self.assertTrue(report["bounded"])
        self.assertTrue(report["unknown"])
        self.assertIs(report["minimal_sufficient"], False)

    def test_invalid_plan_fail_closed(self):
        state = real_state()
        with self.assertRaises(ValueError):
            counterfactual.attribute(state, [["not.an.atom"]])
        with self.assertRaises(ValueError):
            counterfactual.attribute(state, [["k.represent"]], budget=0)


class CertificateTests(unittest.TestCase):
    def _cert(self):
        state, plan = real_plan()
        cert = certificate.build(state, plan)
        return state, cert

    def test_three_value_verify(self):
        state, cert = self._cert()
        self.assertEqual(cert["schema"], certificate.SCHEMA)
        self.assertTrue(cert["no_scoring"])
        self.assertEqual(set(walk_keys(cert)) & FORBIDDEN_KEYS, set())
        self.assertNotIn("goal", walk_keys(cert))
        l1 = certificate.verify(cert)
        self.assertEqual(l1["status"], "indeterminate")
        self.assertFalse(l1["ok"])
        l2 = certificate.verify(cert, state0=state)
        self.assertEqual(l2["status"], "pass")
        self.assertTrue(l2["ok"])
        self.assertEqual(l2["issues"], [])

    def test_six_tamper_classes_rejected(self):
        state, cert = self._cert()
        tampers = []

        extra = copy.deepcopy(cert)
        extra["unexpected"] = True
        tampers.append(extra)

        missing = copy.deepcopy(cert)
        missing.pop("checks")
        tampers.append(missing)

        schema = copy.deepcopy(cert)
        schema["schema"] = "nf-cognition-certificate/9"
        tampers.append(schema)

        actions = copy.deepcopy(cert)
        actions["actions"] = actions["actions"][:-1]
        tampers.append(actions)

        checks = copy.deepcopy(cert)
        checks["checks"]["complete"] = False
        tampers.append(checks)

        digest = copy.deepcopy(cert)
        digest["initial_digest"] = "f" * 64
        tampers.append(digest)

        for index, tampered in enumerate(tampers):
            verdict = certificate.verify(tampered, state0=state)
            self.assertEqual(verdict["status"], "fail", index)
            self.assertFalse(verdict["ok"], index)

    def test_recomputed_digest_still_caught_by_replay(self):
        state, cert = self._cert()
        payload = copy.deepcopy(cert)
        payload["checks"]["complete"] = False
        payload["digest"] = certificate._cert_digest(payload)
        # L1 摘要自洽 → indeterminate；给 state0 重算 checks → fail
        self.assertEqual(certificate.verify(payload)["status"], "indeterminate")
        verdict = certificate.verify(payload, state0=state)
        self.assertEqual(verdict["status"], "fail")
        self.assertTrue(any(issue.startswith("check-mismatch") for issue in verdict["issues"]))
        wrong_state = nf.initial_state("写一份产品说明")
        self.assertEqual(certificate.verify(cert, state0=wrong_state)["status"], "fail")


class ParallelTests(unittest.TestCase):
    def test_batched_contract_and_determinism(self):
        state = real_state()
        budget = rbudget.Budget(max_nodes=20, max_depth=6)
        first = parallel.run_batched(state, budget=budget, batch_width=4)
        second = parallel.run_batched(state, budget=budget, batch_width=4)
        self.assertEqual(first["schema"], parallel.SCHEMA)
        self.assertEqual(first.get("backend"), parallel.BACKEND)
        self.assertIn(
            first["best_path"].get("source"), {"batched", "sequential-fallback"}
        )
        self.assertGreaterEqual(first["total_nodes"], first["baseline_nodes"])
        self.assertEqual(canonical(first), canonical(second))
        self.assertEqual(first["trace_digest"], second["trace_digest"])
        self.assertEqual(set(walk_keys(first)) & FORBIDDEN_KEYS, set())

    def test_batched_fail_closed(self):
        state = real_state()
        for width in (0, -1, parallel.MAX_BATCH_WIDTH + 1):
            report = parallel.run_batched(state, batch_width=width)
            self.assertEqual(report["status"], "fail")
            self.assertEqual(report["termination"], "invalid-input")
        report = parallel.run_batched(None)
        self.assertEqual(report["status"], "fail")


if __name__ == "__main__":
    unittest.main(verbosity=2)
