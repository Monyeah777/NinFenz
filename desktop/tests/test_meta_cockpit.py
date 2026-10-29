"""Meta-cognitive cockpit integration contracts."""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core.meta_cockpit import (  # noqa: E402
    calibration_ledger,
    cockpit_ab,
    cockpit_ab_bundle,
    cockpit_ab_store,
    cockpit_service,
    cognitive_cockpit,
    constrained_choice,
    constrained_loop,
    epistemic_agenda,
    json_asset,
    meta_atom_runtime,
    meta_runtime_manifest,
    runtime_executor,
    schema_compat,
    secret_guard,
    session_journal,
)

cal_ledger = calibration_ledger
cockpit = cognitive_cockpit
atoms = meta_atom_runtime
runtime = runtime_executor

PACKAGE = ROOT / "desktop" / "src" / "core" / "meta_cockpit"


def _feature_catalog() -> list[dict]:
    return [
        {
            "id": node_id,
            "meta_level": node.get("meta_level"),
            "meta_function": node.get("meta_function"),
            "atoms": node.get("atoms", []),
        }
        for node_id, node in sorted(runtime.NODES.items())
    ]


def _contains_key(value, key: str) -> bool:
    if isinstance(value, dict):
        return key in value or any(_contains_key(item, key) for item in value.values())
    if isinstance(value, list):
        return any(_contains_key(item, key) for item in value)
    return False


def _ab_trial(pair: int, arm: str) -> dict:
    output = f"neutral paired output {pair:02d}"
    return {
        "trial_id": f"p{pair:02d}-{arm}",
        "prompt_id": f"task-{pair:02d}",
        "prompt": f"Complete task {pair:02d}.",
        "model_id": "model-x",
        "seed": 100 + pair,
        "arm": arm,
        "generation": {
            "temperature": 0.2,
            "top_p": 0.9,
            "max_output_tokens": 4096,
        },
        "resource_budget": {
            "max_total_tokens": 48000,
            "max_seconds": 300,
        },
        "status": "completed",
        "truncated": False,
        "output": output,
        "output_digest": hashlib.sha256(output.encode("utf-8")).hexdigest(),
    }


def _ab_experiment(pairs: int = 8, guided_wins: int = 8) -> tuple[dict, list[dict]]:
    trials = []
    for pair in range(pairs):
        trials.append(_ab_trial(pair, "baseline"))
        trials.append(_ab_trial(pair, "guided"))
    document = cockpit_ab.preregister(
        {
            "schema": "nf-cockpit-ab/1",
            "experiment_id": "integration-exp",
            "blind_salt": "integration-salt-001",
            "trials": trials,
        }
    )
    mapping = cockpit_ab._mapping(document)
    ballots = []
    for index, pair_id in enumerate(sorted(mapping)):
        winner_arm = "guided" if index < guided_wins else "baseline"
        winner = next(label for label in ("A", "B") if mapping[pair_id][label] == winner_arm)
        for judge in range(3):
            ballots.append(
                {
                    "pair_id": pair_id,
                    "judge_id": f"judge-{judge}",
                    "winner": winner,
                }
            )
    return document, ballots


class MetaAtomRuntimeTest(unittest.TestCase):
    def test_registry_and_meta_pipeline_are_complete(self):
        self.assertEqual(33, len(atoms.SPECS))
        self.assertEqual(set(atoms.SPECS), set(atoms.EXECUTORS))
        self.assertEqual(14, len(runtime.NODES))
        self.assertEqual(10, len(runtime.PIPELINE["nodes"]))
        self.assertEqual(5, len(runtime.META_PIPELINE["nodes"]))

        content_ids = [node["id"] for node in runtime.PIPELINE["nodes"] if node["kind"] == "method"]
        result = runtime.run_meta_pipeline({node_id: (True, []) for node_id in content_ids})
        self.assertEqual("pass", result["status"])
        self.assertEqual(5, len(result["nodes"]))
        self.assertEqual(17, len(result["traces"]))
        self.assertTrue(all(item["status"] == "pass" for item in result["traces"]))

    def test_meta_runtime_fails_closed(self):
        catalog = _feature_catalog()
        saved = atoms.EXECUTORS.pop("c.select")
        try:
            missing = atoms.execute_node(
                runtime.NODES["认知:M31"],
                {
                    "requirement": "content-production",
                    "options": catalog,
                    "goal": {"levels": ["M0"], "functions": ["knowledge"]},
                    "budget": {"envelope": 16},
                    "fallback": {},
                },
            )
        finally:
            atoms.EXECUTORS["c.select"] = saved
        self.assertEqual("fail", missing["status"])

        bad_route = atoms.execute_node(
            runtime.NODES["认知:M32"],
            {
                "target": {"order": ["认知:X99"], "allocation": {}, "fallback": {}},
                "reference": catalog,
                "node_verdicts": [{"id": "x", "ok": True, "fails": []}],
            },
        )
        self.assertEqual("fail", bad_route["status"])

        good = runtime.run_meta_pipeline(
            {
                node["id"]: (True, [])
                for node in runtime.PIPELINE["nodes"]
                if node["kind"] == "method"
            }
        )
        plan = good["nodes"]["认知:M31"]["output"]["plan"]
        overflow = atoms.execute_node(
            runtime.NODES["认知:M41"],
            {
                "plan": plan,
                "budget_state": {"remaining": -1},
            },
        )
        self.assertEqual("{stop}", "{{{}}}".format(overflow["output"]["decision"]["action"]))

        missing_criteria = atoms.execute_node(
            runtime.NODES["认知:M51"],
            {
                "target": {"rows": []},
                "reference": [{"id": "x", "ok": True}],
                "frame": {"rows": []},
            },
        )
        self.assertEqual("fail", missing_criteria["status"])

        unknown_task = atoms.execute_node(
            runtime.NODES["认知:M52"],
            {
                "options": [{"id": "HR-001", "task_type": "content-production"}],
                "goal": {"task_type": "unknown"},
                "library": [{"id": "HR-001", "task_type": "content-production"}],
                "task_type": "unknown",
            },
        )
        self.assertEqual("fail", unknown_task["status"])

        original = atoms.EXECUTORS["c.select"]
        atoms.EXECUTORS["c.select"] = lambda payload: {"selected": "not-a-list"}
        try:
            mismatch = atoms.execute_atom("c.select", {"options": [{"id": "x"}], "goal": {}})
        finally:
            atoms.EXECUTORS["c.select"] = original
        self.assertEqual("fail", mismatch["status"])
        self.assertIn("type mismatch", mismatch["error"])


class CognitiveCockpitTest(unittest.TestCase):
    PROMPT = "设计一个西幻生存流长期玩法方案，覆盖生存、经济、战斗、死亡重生、失败成本。"

    def test_dynamic_method_sequences_react_to_context(self):
        state_a, trace_a = cockpit.think(self.PROMPT)
        state_b, trace_b = cockpit.think(self.PROMPT, injections={2: "发现经济回路缺失"})
        sequence_a = [item["need"] for item in trace_a]
        sequence_b = [item["need"] for item in trace_b]
        self.assertNotEqual(sequence_a, sequence_b)
        self.assertIn("resolve", sequence_b)
        self.assertLessEqual(len(trace_a), 8)
        self.assertLessEqual(len(trace_b), 8)
        self.assertTrue(state_a["artifact"]["verified"])
        self.assertTrue(state_b["artifact"]["verified"])
        self.assertFalse(_contains_key(trace_a, "score"))
        self.assertFalse(_contains_key(trace_b, "score"))

    def test_constrained_choice_and_thought_patch_are_closed_surfaces(self):
        state = cockpit.initial_state(self.PROMPT)
        candidates = constrained_choice.build_candidates(state, cal_ledger.initial_ledger())
        self.assertGreaterEqual(len(candidates), 1)
        self.assertLessEqual(len(candidates), 5)
        self.assertEqual(
            [],
            constrained_choice.validate(
                {"choice": 0, "reason": "补齐结构与风险", "stop": False},
                candidates,
            ),
        )
        self.assertTrue(
            constrained_choice.validate(
                {"choice": 0, "reason": "x", "stop": False, "score": 1},
                candidates,
            )
        )
        candidate = candidates[0]
        issues = epistemic_agenda.validate_thought_patch(
            candidate, {"not_produced_by_cluster": ["x"]}
        )
        self.assertTrue(issues)

    def test_production_handoff_has_no_internal_scoring(self):
        result = cockpit_service.produce("比较西幻生存流、校园情感流和技术文档流的失败成本")
        self.assertEqual("pass", result["run"]["status"])
        self.assertTrue(result["run"]["complete"])
        self.assertEqual([], result["handoff"]["gaps"])
        for key in ("score", "grade", "rating", "receipt"):
            self.assertFalse(_contains_key(result["run"], key), key)
            self.assertFalse(_contains_key(result["handoff"], key), key)
        self.assertEqual("nf-cockpit-manifest/1", result["manifest"]["schema"])

    def test_session_journal_replays_exactly(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "journal.json"
            run = constrained_loop.run(
                self.PROMPT,
                constrained_loop.first_policy,
                journal_path=path,
            )
            self.assertEqual("pass", run["status"])
            document, status = session_journal.load(path)
            self.assertEqual("ok", status)
            assert document is not None
            replay = session_journal.replay(document)
            self.assertEqual("pass", replay["status"])
            self.assertEqual([], replay["issues"])
            self.assertEqual(len(document["events"]), replay["turns"])
            self.assertEqual(run["state"], session_journal.current_state(document))
            self.assertLessEqual(len(document["events"]), 1000)
            self.assertLessEqual(path.stat().st_size, session_journal.MAX_JOURNAL_BYTES)


class CockpitABTest(unittest.TestCase):
    def test_blind_preregistration_power_and_analysis(self):
        experiment, ballots = _ab_experiment()
        self.assertEqual([], cockpit_ab.validate_experiment(experiment))
        packets = cockpit_ab.build_blind_packets(experiment)
        encoded = json.dumps(packets, ensure_ascii=False)
        self.assertNotIn("baseline", encoded)
        self.assertNotIn("guided", encoded)
        self.assertNotIn("model-x", encoded)
        power = cockpit_ab.power_analysis(effect=0.20, alpha=0.05, target_power=0.80)
        self.assertGreaterEqual(power["estimated_power"], 0.80)
        analysis = cockpit_ab.analyze(experiment, ballots)
        self.assertEqual("guided-better", analysis["decision"])
        duplicate = ballots + [copy.deepcopy(ballots[0])]
        with self.assertRaisesRegex(ValueError, "duplicate ballot"):
            cockpit_ab.analyze(experiment, duplicate)

    def test_content_addressed_store_roundtrip(self):
        experiment, ballots = _ab_experiment()
        bundle = cockpit_ab_bundle.create(experiment, ballots)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            first = cockpit_ab_store.save(root, bundle)
            second = cockpit_ab_store.save(root, bundle)
            self.assertEqual(first, second)
            self.assertEqual(bundle, cockpit_ab_store.load(first))
            self.assertEqual(1, len(cockpit_ab_store.index(root)))


class ReleaseAndSafetyTest(unittest.TestCase):
    def test_manifest_binds_runtime_and_limits(self):
        manifest = meta_runtime_manifest.build()
        self.assertEqual([], meta_runtime_manifest.verify(manifest))
        self.assertTrue(manifest["no_scoring"])
        self.assertEqual("PENDING", manifest["human_review"])
        self.assertEqual(8000, manifest["limits"]["context_units"])
        self.assertEqual(8, manifest["limits"]["method_history"])
        schema = json_asset.load(PACKAGE / "meta_runtime_manifest.schema.json")
        validator = schema_compat.Draft202012Validator(schema)
        self.assertEqual([], [item.message for item in validator.iter_errors(manifest)])

    def test_secret_guard_redacts_without_echoing_value(self):
        value = "sk-" + "a" * 24
        self.assertIn("openai-key", secret_guard.scan_text(value))
        redacted = secret_guard.redact(value)
        self.assertNotIn(value, redacted)
        self.assertIn(secret_guard.REDACTION, redacted)
        failed = constrained_loop.run("handle " + value, constrained_loop.first_policy)
        self.assertEqual("invalid-input", failed["termination"])
        self.assertNotIn(value, str(failed))


class MainCliTest(unittest.TestCase):
    def test_nf_cockpit_and_ab_are_wired(self):
        spec = importlib.util.spec_from_file_location(
            "nfcli_meta_cockpit", ROOT / "scripts" / "nf.py"
        )
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        parser = module._build_parser()
        choices = parser._subparsers._group_actions[0].choices
        self.assertIn("cockpit", choices)
        self.assertIn("cockpit-ab", choices)


if __name__ == "__main__":
    unittest.main()
