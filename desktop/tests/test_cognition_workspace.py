"""认知工作台 L0 判据：话语状态 + 15 元动作 + 只追加记录 + 重放 + 依赖方向。

判据重点（对应方案 P1）：
① 动作必须有 frame_delta，且是**语义有效**的（只换词不换问题 → 红）；
② 记录只追加、可重放，篡改任何一处都要被抓（记录链 + 状态 digest 双保险）；
③ 认知核不 import 契约核（AST 判据）——否则「独立可跑」是假的；
④ 步数/关闭/未知动作全部 fail-closed 并给修复指引。
"""
import ast
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core.cognition_workspace import discourse as dc  # noqa: E402
from core.cognition_workspace import moves as mv  # noqa: E402
from core.cognition_workspace import session as se  # noqa: E402

NF = (sys.executable, str(ROOT / "scripts" / "nf.py"))
PKG = ROOT / "desktop" / "src" / "core" / "cognition_workspace"

GOOD_DELTAS = {
    "reframe": {"kind": "question_restated", "before_digest": "aa", "after_digest": "bb",
                "changed_terms": ["可验证"], "statement": "改述后的问题"},
    "bracket": {"kind": "assumption_suspended", "assumption_id": "A1", "reason": "未验证"},
    "conceptual_analysis": {"kind": "concept_clarified", "concept": "鲁棒",
                            "distinctions": ["抗压缩", "抗几何"]},
    "dialectic": {"kind": "tension_added", "between": ["鲁棒", "不可见"],
                  "statement": "两者不可同时最大化"},
    "thought_experiment": {"kind": "hypothesis_proposed", "hypothesis": "换域可扛 q70",
                           "expected_observation": "BER<0.1"},
    "counterexample": {"kind": "counterexample_found", "claim": "块网格能同步",
                       "case": "0.9x 后同步分 81/128", "breaks": True,
                       "witness": {"file": "results/ccos/watermark_ecc_probe.json",
                                   "case": "screenshot_blur_0.3"}},
    "analogy": {"kind": "mapping_added", "source": "纠错码", "target": "水印",
                "preserved": ["冗余换可靠"], "broken": ["噪声模型不同"]},
    "perspective_shift": {"kind": "stakeholder_added", "perspective": "验证方",
                          "obligations": ["能离线验"]},
    "value_conflict": {"kind": "tension_added", "between": ["容量", "不可见性"],
                       "statement": "载荷越大越可见"},
    "genealogy": {"kind": "provenance_added", "origin": "C2PA",
                  "lineage": ["C2PA 1.x", "CCOS label IR"]},
    "reductio": {"kind": "hypothesis_proposed", "hypothesis": "同步可省",
                 "expected_observation": "缩放后仍 BER=0"},
    "boundary_case": {"kind": "boundary_added", "case": "0.99× 缩放", "near_miss": True},
    "steelman": {"kind": "objection_strengthened", "objection": "LSB 已够用",
                 "reasons": ["实现简单", "无可见性损失"]},
    "meta_question": {"kind": "question_restated", "before_digest": "aa",
                      "after_digest": "cc", "changed_terms": ["问法"],
                      "statement": "为什么问「能不能读回」而不是「怎么证明读过」"},
    "decomposition": {"kind": "subquestions_added",
                      "subquestions": ["缩放怎么估", "payload 怎么解码"]},
}


class ContractTest(unittest.TestCase):
    def test_fifteen_moves(self):
        self.assertEqual(15, len(mv.MOVE_IDS))

    def test_every_move_accepts_its_canonical_delta(self):
        for move_id, delta in GOOD_DELTAS.items():
            self.assertEqual([], mv.validate_delta(move_id, delta), move_id)

    def test_every_move_declares_contract_fields(self):
        for move_id in mv.MOVE_IDS:
            info = mv.describe(move_id)
            for field in ("name", "when", "delta_kinds", "failure_mode", "note"):
                self.assertTrue(info[field], move_id + "." + field)

    def test_ritual_reframe_is_rejected(self):
        bad = {"kind": "question_restated", "before_digest": "aa", "after_digest": "aa",
               "changed_terms": []}
        issues = mv.validate_delta("reframe", bad)
        self.assertTrue(any("只换词" in i for i in issues), issues)

    def test_counterexample_must_break(self):
        bad = {"kind": "counterexample_found", "claim": "x", "case": "y", "breaks": False,
               "witness": {"file": "f.json", "case": "c"}}
        self.assertTrue(any("breaks" in i for i in mv.validate_delta("counterexample", bad)))

    def test_counterexample_needs_replayable_witness(self):
        """对抗层（第 93 轮）：反例必须带可复算证人（文件 + 用例 id），否则只是叙述。"""
        base = {"kind": "counterexample_found", "claim": "x", "case": "y", "breaks": True}
        self.assertTrue(any("witness" in i for i in mv.validate_delta("counterexample", base)))
        no_case = dict(base, witness={"file": "f.json"})
        self.assertTrue(any("case" in i for i in mv.validate_delta("counterexample", no_case)))
        ok = dict(base, witness={"file": "results/ccos/x.json", "case": "c-01"})
        self.assertEqual([], mv.validate_delta("counterexample", ok))

    def test_counterexample_witness_file_must_exist(self):
        """对抗层补严（第 94 轮）：给 root 时必须核对证人文件真的在场。

        「格式对」不等于「证人真存在」——这条补的正是后者；不给 root 时保持纯函数（不做 IO）。
        """
        root = str(ROOT)
        base = {"kind": "counterexample_found", "claim": "x", "case": "y", "breaks": True}
        real = dict(base, witness={"file": "results/ccos/watermark_ecc_probe.json",
                                   "case": "screenshot_blur_0.3"})
        self.assertEqual([], mv.validate_delta("counterexample", real, root))
        ghost = dict(base, witness={"file": "results/ccos/does_not_exist_xyz.json",
                                    "case": "c-01"})
        issues = mv.validate_delta("counterexample", ghost, root)
        self.assertTrue(any("不存在" in i for i in issues), issues)

    def test_boundary_must_be_near_miss(self):
        bad = {"kind": "boundary_added", "case": "x", "near_miss": False}
        self.assertTrue(any("near_miss" in i
                            for i in mv.validate_delta("boundary_case", bad)))

    def test_decomposition_needs_two_subquestions(self):
        bad = {"kind": "subquestions_added", "subquestions": ["only one"]}
        self.assertTrue(any("至少两条" in i for i in mv.validate_delta("decomposition", bad)))

    def test_analogy_needs_broken_mapping(self):
        bad = {"kind": "mapping_added", "source": "a", "target": "b",
               "preserved": ["x"], "broken": []}
        self.assertTrue(any("断点" in i for i in mv.validate_delta("analogy", bad)))

    def test_unknown_move_is_rejected_with_guide(self):
        issues = mv.validate_delta("no_such_move", {})
        self.assertIn("未知元动作", issues[0])


class StateTest(unittest.TestCase):
    def test_begin_requires_problem(self):
        with self.assertRaises(ValueError) as ctx:
            se.begin("   ")
        self.assertIn("修复指引", str(ctx.exception))

    def test_new_state_validates_and_digest_stable(self):
        a = se.begin("问题 A")
        b = se.begin("问题 A")
        self.assertEqual(a["state"]["session_id"], b["state"]["session_id"])
        self.assertEqual(a["state"]["digest"], b["state"]["digest"])
        self.assertEqual([], dc.validate(a["state"]))

    def test_step_changes_digest_and_counts(self):
        bundle = se.begin("问题 A")
        after = se.step(bundle, "decomposition", GOOD_DELTAS["decomposition"])
        self.assertNotEqual(bundle["state"]["digest"], after["state"]["digest"])
        self.assertEqual(1, after["state"]["budget"]["steps_used"])
        self.assertEqual(1, len(after["state"]["moves"]))

    def test_closed_session_rejects_step(self):
        bundle = se.begin("问题 A")
        bundle = se.close(bundle, verdict="收口")
        with self.assertRaises(ValueError) as ctx:
            se.step(bundle, "decomposition", GOOD_DELTAS["decomposition"])
        self.assertIn("已关闭", str(ctx.exception))

    def test_budget_is_enforced(self):
        bundle = se.begin("问题 A", steps_max=1)
        bundle = se.step(bundle, "decomposition", GOOD_DELTAS["decomposition"])
        with self.assertRaises(ValueError) as ctx:
            se.step(bundle, "boundary_case", GOOD_DELTAS["boundary_case"])
        self.assertIn("上限", str(ctx.exception))

    def test_bad_move_does_not_write_record(self):
        bundle = se.begin("问题 A")
        with self.assertRaises(ValueError):
            se.step(bundle, "reframe", {"kind": "question_restated",
                                        "before_digest": "x", "after_digest": "x",
                                        "changed_terms": []})
        self.assertEqual(0, len(bundle["records"]["records"]))


class ReplayTest(unittest.TestCase):
    def _bundle(self):
        bundle = se.begin("水印 0.9 倍缩放还能读回吗")
        bundle = se.step(bundle, "decomposition", GOOD_DELTAS["decomposition"])
        return se.step(bundle, "counterexample", GOOD_DELTAS["counterexample"])

    def test_replay_reproduces_state(self):
        bundle = self._bundle()
        res = se.replay(bundle)
        self.assertTrue(res["ok"], res["issues"])
        self.assertEqual(bundle["state"]["digest"], res["state"]["digest"])

    def test_tampered_record_delta_is_detected(self):
        bundle = json.loads(json.dumps(self._bundle()))
        bundle["records"]["records"][0]["delta"]["subquestions"].append("塞进去的")
        self.assertFalse(se.replay(bundle)["ok"])

    def test_tampered_state_digest_is_detected(self):
        bundle = json.loads(json.dumps(self._bundle()))
        bundle["records"]["records"][1]["state_digest"] = "0" * 64
        self.assertFalse(se.replay(bundle)["ok"])

    def test_truncated_head_is_detected(self):
        bundle = json.loads(json.dumps(self._bundle()))
        bundle["records"]["records"].pop()
        res = se.replay(bundle)
        self.assertFalse(res["ok"])
        self.assertTrue(any("head" in i for i in res["issues"]), res["issues"])

    def test_chain_prev_links(self):
        bundle = self._bundle()
        items = bundle["records"]["records"]
        self.assertEqual("", items[0]["prev"])
        self.assertEqual(items[0]["digest"], items[1]["prev"])
        self.assertEqual(items[-1]["digest"], bundle["records"]["head"])

    def test_diff_reports_sequence_difference(self):
        a = self._bundle()
        b = se.step(se.begin("另一个问题"), "steelman", GOOD_DELTAS["steelman"])
        res = se.diff(a, b)
        self.assertFalse(res["same_sequence"])
        self.assertTrue(res["only_in_a"])
        self.assertTrue(res["only_in_b"])
        self.assertTrue(se.diff(a, a)["same_sequence"])


class IsolationTest(unittest.TestCase):
    """依赖方向判据：认知核不得 import 契约核（AST 扫描，不靠人工看）。"""

    FORBIDDEN = ("meta_cockpit", "backends", "core.receipts", "core.evidence",
                 "core.label", "core.check", "core.resolve", "core.verify")

    def test_no_contract_core_imports(self):
        offenders = []
        for path in sorted(PKG.glob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                names = []
                if isinstance(node, ast.Import):
                    names = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom) and node.module:
                    names = [node.module]
                    names.extend(node.module + "." + alias.name for alias in node.names)
                for name in names:
                    padded = "." + name + "."
                    if any(("." + bad + ".") in padded for bad in self.FORBIDDEN):
                        offenders.append(path.name + " → " + name)
        self.assertEqual([], offenders, "认知核 import 了契约核：" + str(offenders))


class CliTest(unittest.TestCase):
    def test_full_cli_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            bundle_path = Path(tmp) / "s.json"
            proc = subprocess.run([*NF, "cog", "begin", "--problem", "缩放后还能读回吗",
                                   "--out", str(bundle_path), "--json"],
                                  capture_output=True, text=True, encoding="utf-8",
                                  errors="replace", timeout=180)
            self.assertEqual(0, proc.returncode, proc.stderr[-300:])
            delta = json.dumps(GOOD_DELTAS["decomposition"], ensure_ascii=False)
            step = subprocess.run([*NF, "cog", "step", "--bundle", str(bundle_path),
                                   "--move", "decomposition", "--delta-json", delta,
                                   "--out", str(bundle_path), "--json"],
                                  capture_output=True, text=True, encoding="utf-8",
                                  errors="replace", timeout=180)
            self.assertEqual(0, step.returncode, step.stderr[-300:])
            replay = subprocess.run([*NF, "cog", "replay", "--bundle", str(bundle_path),
                                     "--json"],
                                    capture_output=True, text=True, encoding="utf-8",
                                    errors="replace", timeout=180)
            self.assertEqual(0, replay.returncode, replay.stderr[-300:])
            self.assertTrue(json.loads(replay.stdout)["ok"])

    def test_ritual_step_fails_with_guide(self):
        with tempfile.TemporaryDirectory() as tmp:
            bundle_path = Path(tmp) / "s.json"
            subprocess.run([*NF, "cog", "begin", "--problem", "问题 B",
                            "--out", str(bundle_path)],
                           capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=180)
            bad = json.dumps({"kind": "question_restated", "before_digest": "x",
                              "after_digest": "x", "changed_terms": []})
            proc = subprocess.run([*NF, "cog", "step", "--bundle", str(bundle_path),
                                   "--move", "reframe", "--delta-json", bad],
                                  capture_output=True, text=True, encoding="utf-8",
                                  errors="replace", timeout=180)
            self.assertNotEqual(0, proc.returncode)
            self.assertIn("只换词", proc.stderr + proc.stdout)

    def test_moves_listing(self):
        proc = subprocess.run([*NF, "cog", "moves", "--json"], capture_output=True,
                              text=True, encoding="utf-8", errors="replace", timeout=180)
        self.assertEqual(0, proc.returncode, proc.stderr[-300:])
        doc = json.loads(proc.stdout)
        self.assertEqual("cog-moves", doc["kind"])
        items = doc["items"]
        self.assertEqual(15, len(items))
        self.assertEqual("reframe", items[0]["id"])


if __name__ == "__main__":
    unittest.main()
