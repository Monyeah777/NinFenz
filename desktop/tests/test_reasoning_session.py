"""ReasoningSession 门面测试：只读、确定性、mode 行为、fail-closed、记录。"""

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core.meta_cockpit.reasoning import bridge as nf  # noqa: E402
from core.meta_cockpit.reasoning import memory as rmemory  # noqa: E402
from core.meta_cockpit.reasoning import session as rsession  # noqa: E402

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


class SessionReadOnlyTests(unittest.TestCase):
    def setUp(self):
        self.state = nf.initial_state(PROMPT)
        self.candidates = nf.candidate_actions(self.state)
        self.ledger = nf.initial_ledger()

    def test_begin_turn_does_not_mutate_inputs(self):
        state_before = copy.deepcopy(self.state)
        candidates_before = copy.deepcopy(self.candidates)
        ledger_before = copy.deepcopy(self.ledger)
        for mode in ("off", "auto", "search"):
            session = rsession.ReasoningSession(mode=mode, search_nodes=40, beta=0.5)
            session.begin_turn(self.state, self.candidates, self.ledger)
            self.assertEqual(canonical(self.state), canonical(state_before), mode)
            self.assertEqual(canonical(self.candidates), canonical(candidates_before), mode)
            self.assertEqual(canonical(self.ledger), canonical(ledger_before), mode)

    def test_mode_off_does_not_search_or_reorder(self):
        session = rsession.ReasoningSession(mode="off", search_nodes=40, beta=0.0)
        step = session.begin_turn(self.state, self.candidates, self.ledger)
        trace = step["trace"]
        self.assertEqual(trace["schema"], rsession.TURN_SCHEMA)
        self.assertEqual(trace["mode"], "off")
        self.assertEqual(trace["search_nodes"], 0)
        self.assertIsNone(trace["plan_head"])
        self.assertIs(trace["degraded"], False)
        self.assertEqual(
            [item["cluster"] for item in step["candidates"]],
            [item["cluster"] for item in self.candidates],
        )

    def test_mode_search_puts_plan_head_first(self):
        for mode in ("auto", "search"):
            session = rsession.ReasoningSession(mode=mode, search_nodes=40, beta=0.0)
            step = session.begin_turn(self.state, self.candidates, self.ledger)
            trace = step["trace"]
            self.assertEqual(trace["mode"], mode)
            self.assertGreater(trace["search_nodes"], 0)
            self.assertIsNotNone(trace["plan_head"])
            self.assertEqual(
                step["candidates"][0]["cluster"], trace["plan_head"], mode
            )

    def test_beta_reorders_and_is_audited(self):
        session = rsession.ReasoningSession(mode="off", search_nodes=40, beta=0.5)
        step = session.begin_turn(self.state, self.candidates, self.ledger)
        trace = step["trace"]
        self.assertEqual(trace["beta_applied"], 0.5)
        self.assertIsNotNone(trace["audit_digest"])
        self.assertEqual(len(trace["audit_digest"]), 64)
        self.assertEqual(
            sorted(tuple(item["cluster"]) for item in step["candidates"]),
            sorted(tuple(item["cluster"]) for item in self.candidates),
        )
        self.assertIs(trace["no_scoring"], True)

    def test_session_deterministic(self):
        def run():
            session = rsession.ReasoningSession(mode="search", search_nodes=40, beta=0.5)
            session.begin_turn(self.state, self.candidates, self.ledger)
            return session.summary()

        first, second = run(), run()
        self.assertEqual(canonical(first), canonical(second))
        self.assertEqual(first["schema"], rsession.SESSION_SCHEMA)
        self.assertEqual(first["orders_digest"], second["orders_digest"])
        self.assertEqual(first["audits_digest"], second["audits_digest"])
        self.assertEqual(set(walk_keys(first)) & FORBIDDEN_KEYS, set())

    def test_memory_hit_is_read_only_feature(self):
        plan = [item["cluster"] for item in self.candidates[:2]]
        mem = rmemory.PlanMemory(threshold=0.75)
        for _ in range(7):
            mem.record(self.state, plan, True, source_digest="a" * 64)
        session = rsession.ReasoningSession(
            mode="off", search_nodes=40, beta=0.0, memory=mem
        )
        step = session.begin_turn(self.state, self.candidates, self.ledger)
        self.assertEqual(step["trace"]["memory_hit"], 1)
        self.assertEqual(mem.stats()["misses"], 0)  # peek 不推进统计

        empty = rmemory.PlanMemory(threshold=0.75)
        session = rsession.ReasoningSession(
            mode="off", search_nodes=40, beta=0.0, memory=empty
        )
        step = session.begin_turn(self.state, self.candidates, self.ledger)
        self.assertEqual(step["trace"]["memory_hit"], 0)


class SessionRecordTests(unittest.TestCase):
    def setUp(self):
        self.state = nf.initial_state(PROMPT)
        self.candidates = nf.candidate_actions(self.state)
        self.ledger = nf.initial_ledger()

    def test_record_turn_deducts_search_nodes(self):
        session = rsession.ReasoningSession(mode="search", search_nodes=40, beta=0.0)
        session.begin_turn(self.state, self.candidates, self.ledger)
        cluster = self.candidates[0]["cluster"]
        executed = nf.shadow_execute(self.state, cluster)
        record = session.record_turn(
            turn=1,
            before_state=self.state,
            cluster=cluster,
            after_state=executed["state"],
            result=executed,
        )
        self.assertEqual(record["schema"], rsession.RECORD_SCHEMA)
        self.assertEqual(record["verdict"], "pass")
        self.assertGreater(record["nodes_deducted"], 0)
        self.assertLessEqual(record["nodes_remaining"], 40 - record["nodes_deducted"])
        summary = session.summary()
        self.assertEqual(summary["turns"], 1)
        self.assertGreaterEqual(summary["search_nodes"], record["nodes_deducted"])
        self.assertEqual(set(walk_keys(record)) & FORBIDDEN_KEYS, set())

    def test_invalid_inputs_fail_closed(self):
        with self.assertRaises(ValueError):
            rsession.ReasoningSession(mode="bogus")
        with self.assertRaises(ValueError):
            rsession.ReasoningSession(search_nodes=0)
        with self.assertRaises(ValueError):
            rsession.ReasoningSession(beta=0.6)
        with self.assertRaises(ValueError):
            rsession.ReasoningSession(memory=object())
        session = rsession.ReasoningSession(mode="off", search_nodes=40)
        with self.assertRaises(ValueError):
            session.begin_turn(None, self.candidates, self.ledger)
        with self.assertRaises(ValueError):
            session.begin_turn(self.state, [], self.ledger)
        with self.assertRaises(ValueError):
            session.begin_turn(self.state, [{"cluster": ["not.an.atom"]}], self.ledger)
        with self.assertRaises(ValueError):
            session.begin_turn(self.state, self.candidates, None)
        with self.assertRaises(ValueError):
            session.record_turn(
                turn=0,
                before_state=self.state,
                cluster=self.candidates[0]["cluster"],
                after_state=self.state,
                result={"status": "pass"},
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
