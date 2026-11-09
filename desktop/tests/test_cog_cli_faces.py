"""cog 机器面真跑覆盖（每张 --json 面都点名，防「跳过=没人管」）。

CLI 面清单里 cog 的 17 张面大多需要参数（--bundle/--ledger/--claim-file…），
不能进 CANON 的无参只读面；本件逐张真跑一遍，断言：rc 属预期、成功面输出带面判别键
（kind/schema）。这样 SKIP 里写「覆盖见本件」就是**可核事实**，不是记忆。
"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
NF = (sys.executable, str(ROOT / "scripts" / "nf.py"))
CLAIM = {"schema": "nf-cog-claim/1", "claim": "c", "digest": "a" * 64}
CC_OK = {"verdict": "ok", "head": "b" * 64, "root": "c" * 64, "count": 1, "issues": []}
CC_FAIL = {"verdict": "invalid", "head": "d" * 64, "root": "e" * 64, "issues": ["坏"]}


def run(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run([*NF, *args], capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=300)


def payload(proc: subprocess.CompletedProcess) -> dict:
    data = json.loads(proc.stdout)
    assert isinstance(data, dict), "机器面成功时必须回对象"
    return data


class CogFacesTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.bundle = self.tmp / "b.json"
        self.ledger = self.tmp / "led.json"
        self.claim_file = self.tmp / "claim.json"
        self.cc_ok = self.tmp / "cc_ok.json"
        self.cc_fail = self.tmp / "cc_fail.json"
        self.claim_file.write_text(json.dumps(CLAIM), encoding="utf-8")
        self.cc_ok.write_text(json.dumps(CC_OK), encoding="utf-8")
        self.cc_fail.write_text(json.dumps(CC_FAIL), encoding="utf-8")
        self.assertEqual(0, run(["cog", "begin", "--problem", "面覆盖",
                                 "--out", str(self.bundle)]).returncode)

    def tearDown(self):
        self._tmp.cleanup()

    def test_begin_face(self):
        data = payload(run(["cog", "begin", "--problem", "另一问",
                            "--out", str(self.tmp / "b2.json"), "--json"]))
        self.assertIn("schema", data)

    def test_step_face(self):
        delta = json.dumps({"kind": "subquestions_added", "subquestions": ["a", "b"]})
        proc = run(["cog", "step", "--bundle", str(self.bundle), "--move", "decomposition",
                    "--delta-json", delta, "--out", str(self.bundle), "--json"])
        self.assertEqual(0, proc.returncode, proc.stderr[-200:])
        self.assertIn("schema", payload(proc))

    def test_replay_face(self):
        data = payload(run(["cog", "replay", "--bundle", str(self.bundle), "--json"]))
        self.assertIn("kind", data)

    def test_status_face(self):
        self.assertIn("schema", payload(run(["cog", "status", "--bundle", str(self.bundle),
                                             "--json"])))

    def test_diff_face(self):
        data = payload(run(["cog", "diff", "--a", str(self.bundle), "--b", str(self.bundle),
                            "--json"]))
        self.assertIn("schema", data)

    def test_moves_ops_criteria_faces(self):
        for face in ("moves", "ops", "criteria"):
            data = payload(run(["cog", face, "--json"]))
            self.assertIn("kind", data, face)

    def test_control_face(self):
        proc = run(["cog", "control", "--bundle", str(self.bundle), "--op", "estimate",
                    "--payload-json", json.dumps({"claim": "x", "value": 1, "basis": "b"}),
                    "--out", str(self.bundle), "--json"])
        self.assertEqual(0, proc.returncode, proc.stderr[-200:])
        self.assertIn("schema", payload(proc))

    def test_triggers_face(self):
        self.assertIn("kind", payload(run(["cog", "triggers", "--bundle", str(self.bundle),
                                           "--json"])))

    def test_claim_and_claim_check_faces(self):
        proc = run(["cog", "claim", "--claim", "关系嵌入扛缩放", "--kind", "robustness",
                    "--pack", "watermarking", "--out", str(self.claim_file), "--json"])
        self.assertEqual(0, proc.returncode, proc.stderr[-200:])
        claim = payload(proc)
        self.assertIn("schema", claim)
        ev = {need: {"status": "ok"} for block in claim["obligations"]
              for std in block["standards"] for need in std["required"]}
        ev_file = self.tmp / "ev.json"
        ev_file.write_text(json.dumps(ev), encoding="utf-8")
        check = run(["cog", "claim-check", "--claim-file", str(self.claim_file),
                     "--evidence", str(ev_file), "--json"])
        self.assertEqual(0, check.returncode, check.stderr[-200:])
        self.assertIn("schema", payload(check))

    def _commit(self, cc: Path) -> Path:
        out = self.tmp / ("commit-" + cc.stem + ".json")
        proc = run(["cog", "bridge-commit", "--bundle", str(self.bundle),
                    "--claim-file", str(self.claim_file), "--cc-result", str(cc),
                    "--out", str(out), "--json"])
        self.assertEqual(0, proc.returncode, proc.stderr[-200:])
        self.assertIn("schema", payload(proc))
        return out

    def test_bridge_commit_face(self):
        self.assertTrue(self._commit(self.cc_ok).is_file())

    def test_bridge_obligation_face(self):
        commit = self._commit(self.cc_fail)
        proc = run(["cog", "bridge-obligation", "--commitment", str(commit),
                    "--cc-result", str(self.cc_fail), "--failed", "BER", "--json"])
        self.assertEqual(0, proc.returncode, proc.stderr[-200:])
        self.assertIn("schema", payload(proc))

    def test_bridge_apply_face(self):
        commit = self._commit(self.cc_fail)
        ob = self.tmp / "ob.json"
        run(["cog", "bridge-obligation", "--commitment", str(commit),
             "--cc-result", str(self.cc_fail), "--out", str(ob)])
        proc = run(["cog", "bridge-apply", "--bundle", str(self.bundle),
                    "--obligation", str(ob), "--commitment", str(commit),
                    "--out", str(self.bundle), "--json"])
        self.assertEqual(0, proc.returncode, proc.stderr[-200:])
        self.assertIn("schema", payload(proc))

    def test_bridge_verify_face(self):
        commit = self._commit(self.cc_ok)
        proc = run(["cog", "bridge-verify", "--bundle", str(self.bundle),
                    "--claim-file", str(self.claim_file), "--cc-result", str(self.cc_ok),
                    "--commitment", str(commit), "--json"])
        self.assertEqual(0, proc.returncode, proc.stderr[-200:])
        self.assertIn("kind", payload(proc))


    def test_calibrate_face(self):
        pairs = self.tmp / "pairs.json"
        pairs.write_text(json.dumps({"pairs": [{"confidence": 0.9, "correct": 1},
                                              {"confidence": 0.1, "correct": 0}]}),
                         encoding="utf-8")
        data = payload(run(["cog", "calibrate", "--pairs", str(pairs), "--json"]))
        self.assertEqual("nf-calibration/1", data["schema"])
        self.assertIn("ece", data)
        # --threshold 分支（第 120 轮补）：trigger 块必须随 --json 输出，且计数自洽
        trig = payload(run(["cog", "calibrate", "--pairs", str(pairs),
                            "--threshold", "0.6", "--json"]))
        self.assertEqual("nf-calibration/1", trig["schema"])
        block = trig.get("trigger")
        self.assertIsInstance(block, dict, "给了 --threshold 却没带 trigger 块")
        self.assertEqual("nf-calibration-trigger/1", block["schema"])
        counts = block["counts"]
        self.assertEqual(counts["trigger"] + counts["skip"], 2, "样本只有 2 条")
        self.assertEqual(len(block["triggered"]) + len(block["skipped"]), 2)

    def test_job_faces(self):
        self.assertEqual(0, run(["cog", "job", "create", "--ledger", str(self.ledger),
                                 "--id", "j1", "--kind", "check",
                                 "--out", str(self.ledger)]).returncode)
        self.assertEqual(0, run(["cog", "job", "transition", "--ledger", str(self.ledger),
                                 "--id", "j1", "--to", "queued",
                                 "--out", str(self.ledger)]).returncode)
        receipt = self.tmp / "r.json"
        receipt.write_text(json.dumps({"schema": "nf-call-receipt/1", "digest": "f" * 64}),
                           encoding="utf-8")
        self.assertEqual(0, run(["cog", "job", "receipt", "--ledger", str(self.ledger),
                                 "--id", "j1", "--receipt", str(receipt),
                                 "--out", str(self.ledger)]).returncode)
        show = payload(run(["cog", "job", "show", "--ledger", str(self.ledger), "--json"]))
        self.assertIn("kind", show)
        verify = run(["cog", "job", "verify", "--ledger", str(self.ledger), "--json"])
        self.assertEqual(0, verify.returncode, verify.stderr[-200:])
        self.assertIn("kind", payload(verify))


if __name__ == "__main__":
    unittest.main()
