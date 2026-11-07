"""双核桥判据（P5）：唯一共享对象 + 双向闭环 + fail-closed。

这套判据盯的正是方案里最容易糊弄的地方：
① commitment 只由三个 digest 组成，两侧不读对方内部状态；
② **双向**：cc 判 fail → 回灌 → 认知侧控制面真的增加一条 detect（不是单向审计）；
③ discourse 不被桥改动（三层分离，移动必须走 meta move）；
④ fail-closed：cc 结果缺 verdict / 被篡改 → 抛错且状态不变；
⑤ commitment 链可重放（prev + digest），改一处即断。
"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core.cognition_workspace import bridge as br  # noqa: E402
from core.cognition_workspace import session as se  # noqa: E402

NF = (sys.executable, str(ROOT / "scripts" / "nf.py"))
CLAIM = {"schema": "nf-cog-claim/1", "claim": "关系嵌入扛缩放", "digest": "a" * 64}
CC_PASS = {"verdict": "pass", "subject": "results/ccos/watermark_geometry_probe.json"}
CC_FAIL = {"verdict": "fail", "subject": "evidence.zip", "detail": "receipts 叶不符"}


def _bundle():
    bundle = se.begin("水印 v1 能否交付")
    return se.step(bundle, "decomposition",
                   {"kind": "subquestions_added", "subquestions": ["BER 够不够", "可见性够不够"]})


class CommitmentTest(unittest.TestCase):
    def test_commitment_binds_three_digests(self):
        bundle = _bundle()
        commitment = br.commit(bundle, CLAIM, CC_PASS)
        self.assertEqual(bundle["state"]["digest"], commitment["cog_digest"])
        self.assertEqual(CLAIM["digest"], commitment["claim_digest"])
        self.assertTrue(commitment["cc_digest"])
        self.assertEqual("pass", commitment["cc_verdict"])

    def test_commitment_is_deterministic(self):
        bundle = _bundle()
        self.assertEqual(br.commit(bundle, CLAIM, CC_PASS)["digest"],
                         br.commit(bundle, CLAIM, CC_PASS)["digest"])

    def test_missing_verdict_fails_closed(self):
        bundle = _bundle()
        with self.assertRaises(ValueError) as ctx:
            br.commit(bundle, CLAIM, {"subject": "x"})
        self.assertIn("修复指引", str(ctx.exception))

    def test_unknown_verdict_fails_closed(self):
        with self.assertRaises(ValueError):
            br.commit(_bundle(), CLAIM, {"verdict": "maybe"})

    def test_claim_without_digest_rejected(self):
        with self.assertRaises(ValueError):
            br.commit(_bundle(), {"schema": "nf-cog-claim/1"}, CC_PASS)

    def test_verify_detects_state_change(self):
        bundle = _bundle()
        commitment = br.commit(bundle, CLAIM, CC_PASS)
        moved = se.step(bundle, "conceptual_analysis",
                        {"kind": "concept_clarified", "concept": "鲁棒",
                         "distinctions": ["压缩", "几何"]})
        res = br.verify_commitment(commitment, moved, CLAIM, CC_PASS)
        self.assertFalse(res["ok"])
        self.assertTrue(any("认知侧" in i for i in res["issues"]))

    def test_verify_detects_cc_change(self):
        bundle = _bundle()
        commitment = br.commit(bundle, CLAIM, CC_PASS)
        self.assertFalse(br.verify_commitment(commitment, bundle, CLAIM, CC_FAIL)["ok"])

    def test_verify_detects_tampered_commitment(self):
        bundle = _bundle()
        commitment = json.loads(json.dumps(br.commit(bundle, CLAIM, CC_PASS)))
        commitment["roles"] = ["local-trusted", "external-blind"]
        self.assertFalse(br.verify_commitment(commitment, bundle, CLAIM, CC_PASS)["ok"])


class ObligationTest(unittest.TestCase):
    def test_obligation_lists_failures_and_next_actions(self):
        commitment = br.commit(_bundle(), CLAIM, CC_FAIL)
        ob = br.obligation(commitment, CC_FAIL, failed=["BER 曲线"], unknown=["可见性"])
        self.assertEqual(["BER 曲线"], ob["failed"])
        self.assertEqual(["可见性"], ob["unknown"])
        ops = [a["op"] for a in ob["next_actions"]]
        self.assertIn("detect", ops)
        self.assertIn("request_context", ops)

    def test_obligation_without_failed_items_uses_verdict(self):
        commitment = br.commit(_bundle(), CLAIM, CC_FAIL)
        ob = br.obligation(commitment, CC_FAIL)
        self.assertTrue(ob["failed"])

    def test_apply_obligation_touches_control_only(self):
        bundle = _bundle()
        commitment = br.commit(bundle, CLAIM, CC_FAIL)
        ob = br.obligation(commitment, CC_FAIL, failed=["BER 曲线"])
        after = br.apply_obligation(bundle, ob)
        self.assertEqual(1, len(after["control"]["records"]))
        self.assertEqual("detect", after["control"]["records"][0]["op"])
        self.assertEqual(bundle["state"]["digest"], after["state"]["digest"],
                         "桥不得改 discourse（三层分离）")

    def test_apply_obligation_rejects_tampered_doc(self):
        bundle = _bundle()
        ob = br.obligation(br.commit(bundle, CLAIM, CC_FAIL), CC_FAIL, failed=["x"])
        bad = json.loads(json.dumps(ob))
        bad["failed"] = ["y"]
        with self.assertRaises(ValueError):
            br.apply_obligation(bundle, bad)


class ChainTest(unittest.TestCase):
    def test_append_and_replay_chain(self):
        bundle = _bundle()
        c1 = br.commit(bundle, CLAIM, CC_FAIL)
        bundle = br.append_commitment(bundle, c1)
        c2 = br.commit(bundle, CLAIM, CC_PASS)
        bundle = br.append_commitment(bundle, c2)
        self.assertEqual(c1["digest"], c2["prev"])
        self.assertTrue(br.replay_commitments(bundle["commitments"])["ok"])

    def test_chain_detects_tamper(self):
        bundle = _bundle()
        bundle = br.append_commitment(bundle, br.commit(bundle, CLAIM, CC_PASS))
        chain = json.loads(json.dumps(bundle["commitments"]))
        chain[0]["roles"] = ["external-blind"]
        self.assertFalse(br.replay_commitments(chain)["ok"])

    def test_append_rejects_broken_prev(self):
        bundle = br.append_commitment(_bundle(), br.commit(_bundle(), CLAIM, CC_PASS))
        other = br.commit(_bundle(), CLAIM, CC_PASS)
        with self.assertRaises(ValueError):
            br.append_commitment(bundle, other)


class ClosedLoopTest(unittest.TestCase):
    def test_fail_then_revise_then_pass(self):
        """闭环：fail → 回灌 → 控制面 detect → 改 claim → 再 commit → pass。"""
        bundle = _bundle()
        c1 = br.commit(bundle, CLAIM, CC_FAIL)
        ob = br.obligation(c1, CC_FAIL, failed=["BER 曲线"])
        bundle = br.append_commitment(br.apply_obligation(bundle, ob), c1)
        self.assertEqual(1, len(bundle["control"]["records"]))
        revised = dict(CLAIM, digest="b" * 64, revised_from=CLAIM["digest"])
        c2 = br.commit(bundle, revised, CC_PASS)
        bundle = br.append_commitment(bundle, c2)
        self.assertEqual("pass", c2["cc_verdict"])
        self.assertEqual(2, len(bundle["commitments"]))
        self.assertTrue(br.replay_commitments(bundle["commitments"])["ok"])


class CliTest(unittest.TestCase):
    def test_bridge_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            bundle_path = tmp / "b.json"
            subprocess.run([*NF, "cog", "begin", "--problem", "水印 v1 能否交付",
                            "--out", str(bundle_path)],
                           capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=180)
            claim_path = tmp / "claim.json"
            claim_path.write_text(json.dumps(CLAIM, ensure_ascii=False), encoding="utf-8")
            fail_path = tmp / "cc_fail.json"
            fail_path.write_text(json.dumps(CC_FAIL, ensure_ascii=False), encoding="utf-8")
            pass_path = tmp / "cc_pass.json"
            pass_path.write_text(json.dumps(CC_PASS, ensure_ascii=False), encoding="utf-8")
            commit_path = tmp / "c1.json"
            proc = subprocess.run([*NF, "cog", "bridge-commit", "--bundle", str(bundle_path),
                                   "--claim-file", str(claim_path),
                                   "--cc-result", str(fail_path),
                                   "--out", str(commit_path), "--json"],
                                  capture_output=True, text=True, encoding="utf-8",
                                  errors="replace", timeout=180)
            self.assertEqual(0, proc.returncode, proc.stderr[-300:])
            self.assertEqual("fail", json.loads(proc.stdout)["cc_verdict"])
            ob_path = tmp / "ob.json"
            ob = subprocess.run([*NF, "cog", "bridge-obligation",
                                 "--commitment", str(commit_path),
                                 "--cc-result", str(fail_path),
                                 "--failed", "BER 曲线", "--out", str(ob_path), "--json"],
                                capture_output=True, text=True, encoding="utf-8",
                                errors="replace", timeout=180)
            self.assertEqual(0, ob.returncode, ob.stderr[-300:])
            applied = subprocess.run([*NF, "cog", "bridge-apply", "--bundle", str(bundle_path),
                                      "--obligation", str(ob_path),
                                      "--commitment", str(commit_path),
                                      "--out", str(bundle_path), "--json"],
                                     capture_output=True, text=True, encoding="utf-8",
                                     errors="replace", timeout=180)
            self.assertEqual(0, applied.returncode, applied.stderr[-300:])
            verify = subprocess.run([*NF, "cog", "bridge-verify",
                                     "--bundle", str(bundle_path),
                                     "--claim-file", str(claim_path),
                                     "--cc-result", str(fail_path),
                                     "--commitment", str(commit_path), "--json"],
                                    capture_output=True, text=True, encoding="utf-8",
                                    errors="replace", timeout=180)
            self.assertEqual(0, verify.returncode, verify.stderr[-300:])
            self.assertTrue(json.loads(verify.stdout)["ok"])


if __name__ == "__main__":
    unittest.main()
