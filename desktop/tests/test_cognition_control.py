"""元算子判据（P2）：11 算子 + 触发引擎 + 双 trace + 反仪式化。

判据盯四件事：
① **witness 必填且非空**：没有副作用证据的算子请求一律拒绝；
② **平面分离**：算子写 discourse 字段（tensions/open_questions…）= 越界，拒绝；
③ **反仪式化**：同算子同 witness 连续 3 次 → 拒绝；改读数则放行；
④ **真效果**：stop 真终止（后续 step 被拒）、allocate 真改预算、switch 真换策略；
⑤ **双 trace 可重放**：控制记录链可复算，改 effect/digest 必被抓。
"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core.cognition_workspace import control as ct  # noqa: E402
from core.cognition_workspace import operators as op  # noqa: E402
from core.cognition_workspace import session as se  # noqa: E402

NF = (sys.executable, str(ROOT / "scripts" / "nf.py"))

PAYLOADS = {
    "observe": {"observation": "已用步数", "reading": 2},
    "estimate": {"claim": "q70 可读", "value": 0.1, "basis": "上一轮探针"},
    "detect": {"anomaly": "连续三步同动作", "evidence": "moves[-3:] 相同"},
    "calibrate": {"estimate_ref": "E1", "actual": 0.49, "gap": 0.39},
    "allocate": {"resource": "steps", "from": 24, "to": 40, "reason": "需要更多步"},
    "switch": {"from": "explore", "to": "attack", "reason": "无进展"},
    "stop": {"reason": "已证伪", "terminal_state": "falsified"},
    "abstain": {"question": "拍屏是否可读", "missing": "拍屏样本",
                "searched": "results/ccos/watermark_ecc_probe.json 的 10 组配置",
                "why_not_guess": "缺样本，猜就是造假"},
    "revise": {"target": "块网格同步", "before": "可对齐", "after": "仅整数比可对齐"},
    "request_context": {"missing": "原始尺寸", "needed_for": "缩放反解"},
    "audit": {"target": "自身记录链", "finding": "两条记录缺 frame_delta 语义"},
}


class OperatorTableTest(unittest.TestCase):
    def test_eleven_operators(self):
        self.assertEqual(11, len(op.OPERATOR_IDS))

    def test_every_operator_declares_contract(self):
        for op_id in op.OPERATOR_IDS:
            info = op.describe(op_id)
            for field in ("name", "when", "witness", "effect", "failure_mode"):
                self.assertTrue(info[field], op_id + "." + field)

    def test_every_operator_accepts_its_payload(self):
        for op_id, payload in PAYLOADS.items():
            self.assertEqual([], op.validate_request(op_id, payload), op_id)

    def test_missing_witness_is_rejected(self):
        issues = op.validate_request("switch", {"from": "a", "to": "b"})
        self.assertTrue(any("witness" in i for i in issues), issues)

    def test_empty_witness_is_rejected(self):
        issues = op.validate_request("detect", {"anomaly": "", "evidence": ""})
        self.assertTrue(any("witness" in i for i in issues), issues)

    def test_plane_violation_is_rejected(self):
        issues = op.validate_request("observe", {"observation": "x", "reading": 1,
                                                 "tensions": []})
        self.assertTrue(any("越界" in i for i in issues), issues)

    def test_noop_effects_are_rejected(self):
        self.assertTrue(op.validate_request("switch", {"from": "a", "to": "a",
                                                       "reason": "x"}))
        self.assertTrue(op.validate_request("allocate", {"resource": "s", "from": 1,
                                                         "to": 1, "reason": "x"}))
        self.assertTrue(op.validate_request("revise", {"target": "t", "before": "a",
                                                       "after": "a"}))


class ApplyTest(unittest.TestCase):
    def test_each_operator_applies(self):
        for op_id, payload in PAYLOADS.items():
            state = ct.new()
            new_state, out = ct.apply(state, op_id, payload)
            self.assertEqual(1, len(new_state["records"]), op_id)
            self.assertEqual(op_id, out["record"]["op"])

    def test_ritual_observe_is_rejected_on_third(self):
        state = ct.new()
        payload = {"observation": "步数", "reading": 1}
        state, _ = ct.apply(state, "observe", payload)
        state, _ = ct.apply(state, "observe", payload)
        with self.assertRaises(ValueError) as ctx:
            ct.apply(state, "observe", payload)
        self.assertIn("仪式化", str(ctx.exception))

    def test_varied_observe_is_allowed(self):
        state = ct.new()
        state, _ = ct.apply(state, "observe", {"observation": "步数", "reading": 1})
        state, _ = ct.apply(state, "observe", {"observation": "步数", "reading": 2})
        state, _ = ct.apply(state, "observe", {"observation": "步数", "reading": 3})
        self.assertEqual(3, len(state["records"]))

    def test_stop_terminates_control(self):
        state = ct.new()
        state, _ = ct.apply(state, "stop", PAYLOADS["stop"])
        self.assertEqual("stopped", state["status"])
        with self.assertRaises(ValueError):
            ct.apply(state, "observe", {"observation": "x", "reading": 1})

    def test_stop_terminates_session_steps(self):
        bundle = se.begin("问题 A")
        bundle = se.control(bundle, "stop", PAYLOADS["stop"])
        with self.assertRaises(ValueError) as ctx:
            se.step(bundle, "decomposition",
                    {"kind": "subquestions_added", "subquestions": ["a", "b"]})
        self.assertIn("控制面已", str(ctx.exception))

    def test_allocate_changes_budget(self):
        bundle = se.begin("问题 A", steps_max=10)
        bundle = se.control(bundle, "allocate",
                            {"resource": "steps", "from": 10, "to": 20,
                             "reason": "扩大预算"})
        self.assertEqual(20, bundle["state"]["budget"]["steps_max"])


    def test_abstain_requires_search_boundary(self):
        """同构判据 #5（负空间层）：没有检索边界的「不知道」等于装懂，必须拒。

        契约侧的非包含证明要求「声明覆盖集」；认知侧的 abstain 必须给出 `searched`（检索了什么）。
        两侧同源：**没有边界的否定不是证据**。
        """
        bad = {"question": "拍屏是否可读", "missing": "拍屏样本",
               "why_not_guess": "缺样本"}
        issues = op.validate_request("abstain", bad)
        self.assertTrue(any("searched" in i for i in issues), issues)
        state = ct.new()
        with self.assertRaises(ValueError) as ctx:
            ct.apply(state, "abstain", bad)
        self.assertIn("修复指引", str(ctx.exception))
        good = dict(bad, searched="results/ccos/watermark_ecc_probe.json 全 10 组")
        state2, _ = ct.apply(ct.new(), "abstain", good)
        self.assertEqual("results/ccos/watermark_ecc_probe.json 全 10 组",
                         state2["abstained"][-1]["searched"])
    def test_abstain_marks_status(self):
        state = ct.new()
        state, _ = ct.apply(state, "abstain", PAYLOADS["abstain"])
        self.assertEqual("abstained", state["status"])
        self.assertEqual(1, len(state["abstained"]))


class TraceReplayTest(unittest.TestCase):
    def _state(self):
        state = ct.new()
        for op_id, payload in (("observe", PAYLOADS["observe"]),
                               ("estimate", PAYLOADS["estimate"]),
                               ("calibrate", PAYLOADS["calibrate"]),
                               ("switch", PAYLOADS["switch"])):
            state, _ = ct.apply(state, op_id, payload)
        return state

    def test_replay_reproduces_control(self):
        state = self._state()
        res = ct.replay(state)
        self.assertTrue(res["ok"], res["issues"])
        self.assertEqual(state["digest"], res["control"]["digest"])

    def test_tampered_effect_is_detected(self):
        state = json.loads(json.dumps(self._state()))
        state["records"][1]["effect"]["estimate"]["value"] = 999
        self.assertFalse(ct.replay(state)["ok"])

    def test_broken_chain_is_detected(self):
        state = json.loads(json.dumps(self._state()))
        state["records"][2]["prev"] = "0" * 64
        self.assertFalse(ct.replay(state)["ok"])


class TriggerTest(unittest.TestCase):
    def test_no_trigger_on_fresh_session(self):
        bundle = se.begin("问题 A")
        self.assertEqual([], se.triggers(bundle))

    def test_loop_triggers_switch(self):
        bundle = se.begin("问题 A")
        delta = {"kind": "subquestions_added", "subquestions": ["a", "b"]}
        for _ in range(3):
            bundle = se.step(bundle, "decomposition", delta)
        found = [t for t in se.triggers(bundle) if t["trigger"] == "loop"]
        self.assertTrue(found)
        self.assertEqual("switch", found[0]["op"])

    def test_budget_low_triggers_allocate(self):
        bundle = se.begin("问题 A", steps_max=4)
        for _ in range(3):
            bundle = se.step(bundle, "decomposition",
                             {"kind": "subquestions_added", "subquestions": ["a", "b"]})
        self.assertTrue(any(t["trigger"] == "budget_low" for t in se.triggers(bundle)))

    def test_unresolved_tension_triggers_detect(self):
        bundle = se.begin("问题 A")
        bundle = se.step(bundle, "dialectic",
                         {"kind": "tension_added", "between": ["鲁棒", "不可见"],
                          "statement": "不可兼得"})
        self.assertTrue(any(t["trigger"] == "unresolved_tension"
                            for t in se.triggers(bundle)))

    def test_blind_spot_triggers_audit(self):
        bundle = se.begin("问题 A")
        for _ in range(4):
            bundle = se.step(bundle, "conceptual_analysis",
                             {"kind": "concept_clarified", "concept": "鲁棒",
                              "distinctions": ["压缩", "几何"]})
        self.assertTrue(any(t["trigger"] == "blind_spot" for t in se.triggers(bundle)))

    def test_calibration_drift_triggers_calibrate(self):
        bundle = se.begin("问题 A")
        bundle = se.control(bundle, "estimate", PAYLOADS["estimate"])
        for _ in range(3):
            bundle = se.step(bundle, "conceptual_analysis",
                             {"kind": "concept_clarified", "concept": "鲁棒",
                              "distinctions": ["压缩", "几何"]})
        self.assertTrue(any(t["trigger"] == "calibration_drift"
                            for t in se.triggers(bundle)))

    def test_triggers_are_deterministic(self):
        bundle = se.begin("问题 A", steps_max=4)
        for _ in range(3):
            bundle = se.step(bundle, "decomposition",
                             {"kind": "subquestions_added", "subquestions": ["a", "b"]})
        self.assertEqual(se.triggers(bundle), se.triggers(bundle))


class CliTest(unittest.TestCase):
    def test_ops_listing(self):
        proc = subprocess.run([*NF, "cog", "ops", "--json"], capture_output=True,
                              text=True, encoding="utf-8", errors="replace", timeout=180)
        self.assertEqual(0, proc.returncode, proc.stderr[-300:])
        doc = json.loads(proc.stdout)
        self.assertEqual("cog-ops", doc["kind"])
        self.assertEqual(11, len(doc["items"]))

    def test_control_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            bundle_path = Path(tmp) / "s.json"
            subprocess.run([*NF, "cog", "begin", "--problem", "问题 P",
                            "--out", str(bundle_path)],
                           capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=180)
            payload = json.dumps(PAYLOADS["estimate"], ensure_ascii=False)
            proc = subprocess.run([*NF, "cog", "control", "--bundle", str(bundle_path),
                                   "--op", "estimate", "--payload-json", payload,
                                   "--out", str(bundle_path), "--json"],
                                  capture_output=True, text=True, encoding="utf-8",
                                  errors="replace", timeout=180)
            self.assertEqual(0, proc.returncode, proc.stderr[-300:])
            self.assertEqual(1, len(json.loads(proc.stdout)["records"]))
            trig = subprocess.run([*NF, "cog", "triggers", "--bundle", str(bundle_path),
                                   "--json"],
                                  capture_output=True, text=True, encoding="utf-8",
                                  errors="replace", timeout=180)
            self.assertEqual(0, trig.returncode, trig.stderr[-300:])


if __name__ == "__main__":
    unittest.main()
