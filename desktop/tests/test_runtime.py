# -*- coding: utf-8 -*-
"""T7.3 参考运行时回归（确定性 harness + record/replay）——五组判据钉住「可复现」这个词。

1. **确定性**：同计划同状态两次跑，trace 逐字节一致、产物 digest 一致；时长只是占位 0。
2. **record → replay**：录像回放产出与录制跑逐字节相同的 trace / artifact digest。
3. **fail-closed**：fixture 缺失 / 篡改 / 与当前计划或状态不符，一律 FAIL + 修复指引
   （不许猜、不许用默认值补齐）。
4. **状态敏感**：不同 state → 不同产物 digest（且 plan_digest 不变，证明变化来自状态）。
5. **替换点**：`execute(..., client=...)` 注入自定义 ModelClient 就能换模型实现
   （未来接真实 client 的接口面就这一处）。

跑法：python -m pytest desktop/tests/test_runtime.py -q
"""
from __future__ import annotations

import contextlib
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import assemble_plan as ap  # noqa: E402
from core import pipeline_loader  # noqa: E402
from core import runtime as rt  # noqa: E402

NF = ROOT / "scripts" / "nf.py"
PRESET_REQ = "技术文档"           # 命中 P06 preset 管线（真实 assemble_plan 产出）
OFFICIAL_PIPE = "03_管线库/P90_结构装配管线.md"


def _preset_plan() -> dict:
    return ap.plan(PRESET_REQ)


def _official_plan() -> dict:
    return {"requirement": "synthetic", "matched": False, "package": None,
            "pipeline": None, "pipeline_files": [OFFICIAL_PIPE],
            "fetch_modules": ["M00"], "allowed_module_ids": ["M00"],
            "status": "custom"}


def _write(tmp: Path, name: str, doc) -> Path:
    path = tmp / name
    path.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    return path


def _run_cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(NF), "runtime", *args],
                          cwd=str(ROOT), capture_output=True, text=True,
                          encoding="utf-8", timeout=300)


def _cli_run_stderr(**kwargs) -> tuple:
    """进程内跑 cli_run 并收集 stderr（比 spawn 快，判据同一份）。"""
    buf = io.StringIO()
    with contextlib.redirect_stderr(buf):
        code = rt.cli_run(**kwargs)
    return code, buf.getvalue()


class DeterminismTest(unittest.TestCase):
    def test_two_runs_are_byte_identical(self):
        plan, state = _preset_plan(), {"slot": "A"}
        a = rt.execute(plan, state)
        b = rt.execute(plan, state)
        self.assertEqual(rt.canonical(a), rt.canonical(b))
        self.assertEqual(a["artifact_digest"], b["artifact_digest"])

    def test_trace_shape_and_duration_placeholder(self):
        trace = rt.execute(_official_plan(), {})
        self.assertEqual(rt.TRACE_SCHEMA, trace["schema"])
        self.assertGreater(len(trace["steps"]), 0)
        self.assertEqual(len(trace["steps"]), len(trace["artifacts"]))
        for event in trace["steps"]:
            for key in ("step", "step_id", "layer", "module", "contract_digest",
                        "inputs", "outputs", "duration_ms"):
                self.assertIn(key, event)
            self.assertEqual(0, event["duration_ms"], "时长必须是占位 0（不确定面不进判据）")
            self.assertTrue(event["outputs"]["response_digest"].startswith("sha256:"))
        self.assertTrue(trace["artifact_digest"].startswith("sha256:"))

    def test_steps_follow_pipeline_layer_order(self):
        plan = _preset_plan()
        pipe = pipeline_loader.load_pipeline_file(ROOT / plan["pipeline_files"][0])
        want = []
        for layer in pipe.layers:
            for module in list(layer.default_modules) + list(layer.allowed_modules):
                pair = (layer.name, module)
                if pair not in want:      # 与 runtime 的 dedupe 口径一致
                    want.append(pair)
        got = [(e["layer"], e["module"]) for e in rt.execute(plan, {})["steps"]]
        self.assertEqual(want, got, "步骤顺序应与管线层序一致")

    def test_different_state_changes_artifact_digest(self):
        plan = _preset_plan()
        a = rt.execute(plan, {"slot": "A"})
        b = rt.execute(plan, {"slot": "B"})
        self.assertEqual(a["plan_digest"], b["plan_digest"], "计划未变")
        self.assertNotEqual(a["state_digest"], b["state_digest"])
        self.assertNotEqual(a["artifact_digest"], b["artifact_digest"],
                            "状态不同却产出同一 digest = 状态没进判据")
        self.assertNotEqual(rt.canonical(a), rt.canonical(b))


class RecordReplayTest(unittest.TestCase):
    def test_record_then_replay_reproduces_same_trace(self):
        plan = _preset_plan()
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            fixture = d / "fixture.json"
            t1, t2 = d / "t1.json", d / "t2.json"
            code, err = _cli_run_stderr(plan=str(_write(d, "plan.json", plan)),
                                        trace=str(t1), record=str(fixture))
            self.assertEqual(0, code, err)
            code, err = _cli_run_stderr(plan=str(_write(d, "plan.json", plan)),
                                        trace=str(t2), replay=str(fixture))
            self.assertEqual(0, code, err)
            self.assertEqual(t1.read_bytes(), t2.read_bytes(),
                             "回放 trace 与录制跑不一致")
            doc = json.loads(fixture.read_text(encoding="utf-8"))
            self.assertEqual(rt.FIXTURE_SCHEMA, doc["schema"])
            self.assertEqual(json.loads(t1.read_text(encoding="utf-8"))["artifact_digest"],
                             doc["artifact_digest"])

    def test_tampered_response_fails(self):
        plan = _preset_plan()
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            plan_path = _write(d, "plan.json", plan)
            fixture = d / "fixture.json"
            _cli_run_stderr(plan=str(plan_path), trace=str(d / "t1.json"),
                            record=str(fixture))
            doc = json.loads(fixture.read_text(encoding="utf-8"))
            doc["calls"][0]["response"] = "tampered"
            fixture.write_text(json.dumps(doc), encoding="utf-8")
            code, err = _cli_run_stderr(plan=str(plan_path), trace=str(d / "t2.json"),
                                        replay=str(fixture))
            self.assertEqual(1, code)
            self.assertIn("篡改", err)
            self.assertIn("修复指引", err)

    def test_tampered_trace_digest_fails(self):
        plan = _preset_plan()
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            plan_path = _write(d, "plan.json", plan)
            fixture = d / "fixture.json"
            _cli_run_stderr(plan=str(plan_path), trace=str(d / "t1.json"),
                            record=str(fixture))
            doc = json.loads(fixture.read_text(encoding="utf-8"))
            doc["trace_digest"] = "sha256:" + "0" * 64
            fixture.write_text(json.dumps(doc), encoding="utf-8")
            code, err = _cli_run_stderr(plan=str(plan_path), trace=str(d / "t2.json"),
                                        replay=str(fixture))
            self.assertEqual(1, code)
            self.assertIn("修复指引", err)

    def test_missing_fixture_fails(self):
        plan = _preset_plan()
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            code, err = _cli_run_stderr(plan=str(_write(d, "plan.json", plan)),
                                        trace=str(d / "t.json"),
                                        replay=str(d / "nope.json"))
            self.assertEqual(1, code)
            self.assertIn("fixture 缺失", err)
            self.assertIn("修复指引", err)

    def test_fixture_for_other_state_fails(self):
        plan = _preset_plan()
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            plan_path = _write(d, "plan.json", plan)
            state_a = _write(d, "state_a.json", {"slot": "A"})
            state_b = _write(d, "state_b.json", {"slot": "B"})
            _cli_run_stderr(plan=str(plan_path), state=str(state_a),
                            trace=str(d / "t1.json"), record=str(d / "fx.json"))
            code, err = _cli_run_stderr(plan=str(plan_path), state=str(state_b),
                                        trace=str(d / "t2.json"), replay=str(d / "fx.json"))
            self.assertEqual(1, code)
            self.assertIn("状态不符", err)
            self.assertIn("修复指引", err)

    def test_fixture_for_other_plan_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            plan_a = _write(d, "plan_a.json", _preset_plan())
            plan_b = _write(d, "plan_b.json", _official_plan())
            _cli_run_stderr(plan=str(plan_a), trace=str(d / "t1.json"),
                            record=str(d / "fx.json"))
            code, err = _cli_run_stderr(plan=str(plan_b), trace=str(d / "t2.json"),
                                        replay=str(d / "fx.json"))
            self.assertEqual(1, code)
            self.assertIn("计划不符", err)

    def test_record_and_replay_are_mutually_exclusive(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            plan = _write(d, "plan.json", _preset_plan())
            code, err = _cli_run_stderr(plan=str(plan), trace=str(d / "t.json"),
                                        record=str(d / "a.json"), replay=str(d / "a.json"))
            self.assertEqual(1, code)
            self.assertIn("互斥", err)


class FailClosedTest(unittest.TestCase):
    def test_missing_plan_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            code, err = _cli_run_stderr(plan=str(d / "nope.json"), trace=str(d / "t.json"))
            self.assertEqual(1, code)
            self.assertIn("装配计划缺失", err)
            self.assertIn("修复指引", err)

    def test_plan_without_steps_fails(self):
        with self.assertRaises(rt.RuntimeFailure) as ctx:
            rt.plan_steps({"pipeline_files": [], "fetch_modules": [],
                           "allowed_module_ids": []})
        self.assertIn("修复指引", str(ctx.exception))

    def test_missing_state_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            code, err = _cli_run_stderr(plan=str(_write(d, "p.json", _preset_plan())),
                                        trace=str(d / "t.json"),
                                        state=str(d / "nope_state.json"))
            self.assertEqual(1, code)
            self.assertIn("状态件缺失", err)
            self.assertIn("修复指引", err)


class ModelClientTest(unittest.TestCase):
    def test_mock_is_pure_function_of_contract_and_step(self):
        model = rt.MockModel()
        a = model.respond("sha256:" + "1" * 64, "01|层|M00")
        b = model.respond("sha256:" + "1" * 64, "01|层|M00")
        c = model.respond("sha256:" + "1" * 64, "02|层|M00")
        self.assertEqual(a, b)
        self.assertNotEqual(a, c)

    def test_custom_client_is_the_replacement_point(self):
        class ConstantClient(rt.ModelClient):
            def respond(self, contract_digest: str, step_id: str) -> str:
                return "real-client-stub:" + step_id

        trace = rt.execute(_official_plan(), {}, ConstantClient())
        for event, artifact in zip(trace["steps"], trace["artifacts"]):
            self.assertTrue(artifact["response"].startswith("real-client-stub:"))
            self.assertEqual("real-client-stub:" + event["step_id"], artifact["response"])


class CliTest(unittest.TestCase):
    def test_run_json_face(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            plan = _write(d, "plan.json", _preset_plan())
            trace = d / "trace.json"
            proc = _run_cli("run", "--plan", str(plan), "--trace", str(trace), "--json")
            self.assertEqual(0, proc.returncode, proc.stderr[-500:])
            doc = json.loads(proc.stdout)
            self.assertEqual(rt.JSON_SCHEMA, doc["schema"])
            self.assertTrue(doc["ok"])
            self.assertTrue(trace.is_file())
            self.assertTrue(doc["artifact_digest"].startswith("sha256:"))

    def test_runtime_without_subcommand_gives_guidance(self):
        proc = _run_cli()
        self.assertNotEqual(0, proc.returncode)
        self.assertTrue(("修复指引" in proc.stderr) or ("usage:" in proc.stderr),
                        proc.stderr[-400:])

    def test_path_escape_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            plan = _write(d, "plan.json", _preset_plan())
            proc = _run_cli("run", "--plan", str(plan), "--trace", "../escape_trace.json")
            self.assertEqual(1, proc.returncode)
            self.assertIn("修复指引", proc.stderr)
            self.assertFalse((ROOT.parent / "escape_trace.json").exists())


if __name__ == "__main__":
    unittest.main()
