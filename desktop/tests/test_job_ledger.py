"""作业账本判据（K1+K4）与启动自检判据（K8）。

① 六态状态机：created→queued→running→终态；非法迁移与终态后追加一律拒绝；
② 只追加事件链：seq 连续、prev 相连、digest 可复算，改一处即断；
③ 可重放：replay 从事件链重建状态，篡改/断链/非法迁移必被抓；
④ 证据按 job 归集：回执挂到 job 上，job_digest 可进 commitment；
⑤ 安全模式：关键件缺失/坏 JSON/坏 schema → safe，且写面被拒（fail-closed）；
⑥ panic 转储：结构化、带 digest、不泄漏堆栈源码。
"""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import boot_check as bc  # noqa: E402
from core import job_ledger as jl  # noqa: E402
from core import mcp_manifest as mf  # noqa: E402

RECEIPT = mf.receipt("check_file", {"path": "a.png"}, {"verdict": "pass"})


def _running() -> dict:
    led = jl.new_ledger()
    led = jl.create(led, "job-1", "check", contract_digest="c" * 64)
    led = jl.transition(led, "job-1", "queued")
    return jl.transition(led, "job-1", "running")


class StateMachineTest(unittest.TestCase):
    def test_legal_path_to_success(self):
        led = _running()
        led = jl.attach_receipt(led, "job-1", RECEIPT)
        led = jl.transition(led, "job-1", "succeeded")
        self.assertEqual("succeeded", led["jobs"]["job-1"]["state"])
        self.assertEqual(1, len(led["jobs"]["job-1"]["receipts"]))

    def test_illegal_transition_is_rejected(self):
        led = jl.new_ledger()
        led = jl.create(led, "job-1", "check")
        with self.assertRaises(ValueError) as ctx:
            jl.transition(led, "job-1", "succeeded")
        self.assertIn("非法迁移", str(ctx.exception))

    def test_terminal_blocks_further_transitions(self):
        led = jl.transition(_running(), "job-1", "succeeded")
        with self.assertRaises(ValueError) as ctx:
            jl.transition(led, "job-1", "queued")
        self.assertIn("已终止", str(ctx.exception))

    def test_terminal_blocks_receipts(self):
        led = jl.transition(_running(), "job-1", "failed")
        with self.assertRaises(ValueError) as ctx:
            jl.attach_receipt(led, "job-1", RECEIPT)
        self.assertIn("已终止", str(ctx.exception))

    def test_duplicate_job_is_rejected(self):
        led = jl.create(jl.new_ledger(), "job-1", "check")
        with self.assertRaises(ValueError):
            jl.create(led, "job-1", "check")

    def test_unknown_job_is_rejected_with_guide(self):
        with self.assertRaises(ValueError) as ctx:
            jl.transition(jl.new_ledger(), "nope", "queued")
        self.assertIn("修复指引", str(ctx.exception))

    def test_empty_kind_is_rejected(self):
        with self.assertRaises(ValueError):
            jl.create(jl.new_ledger(), "job-1", "  ")


class ChainTest(unittest.TestCase):
    def test_events_are_chained(self):
        led = _running()
        chain = led["chain"]
        self.assertEqual("", chain[0]["prev"])
        self.assertEqual(chain[0]["digest"], chain[1]["prev"])
        self.assertEqual([1, 2, 3], [e["seq"] for e in chain])

    def test_job_digest_changes_with_state(self):
        led = _running()
        before = jl.job_digest(led, "job-1")
        after = jl.transition(led, "job-1", "succeeded")
        self.assertNotEqual(before, jl.job_digest(after, "job-1"))

    def test_replay_reproduces_ledger(self):
        led = jl.transition(_running(), "job-1", "succeeded")
        res = jl.replay(led)
        self.assertTrue(res["ok"], res["issues"])
        self.assertEqual(led["digest"], res["ledger"]["digest"])

    def test_tampered_event_is_caught(self):
        led = json.loads(json.dumps(_running()))
        led["chain"][0]["body"]["kind"] = "label"
        self.assertFalse(jl.replay(led)["ok"])

    def test_broken_prev_is_caught(self):
        led = json.loads(json.dumps(_running()))
        led["chain"][1]["prev"] = "0" * 64
        self.assertFalse(jl.replay(led)["ok"])

    def test_illegal_transition_in_chain_is_caught(self):
        led = json.loads(json.dumps(_running()))
        led["chain"][1]["body"]["to"] = "succeeded"
        led["chain"][1]["digest"] = jl.digest_of(
            {k: v for k, v in led["chain"][1].items() if k != "digest"})
        self.assertFalse(jl.replay(led)["ok"])


class BootCheckTest(unittest.TestCase):
    def test_repo_boots_normal(self):
        res = bc.check(str(ROOT))
        self.assertEqual("normal", res["mode"], res["issues"])
        self.assertEqual([], bc.safe_mode_write_gate(res))

    def test_missing_critical_file_is_safe(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            res = bc.check(tmp)
            self.assertEqual("safe", res["mode"])
            self.assertTrue(res["issues"])

    def test_bad_json_is_safe(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            for rel in bc.CRITICAL:
                path = Path(tmp) / rel
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('{"schema": "nf-x/1"}', encoding="utf-8")
            bad = Path(tmp) / bc.CRITICAL[0]
            bad.write_text("{not json", encoding="utf-8")
            res = bc.check(tmp)
            self.assertEqual("safe", res["mode"])
            self.assertTrue(any(i["code"] == "bad-json" for i in res["issues"]))

    def test_safe_mode_blocks_writes(self):
        res = {"mode": "safe", "issues": [{"file": "x", "detail": "坏了"}]}
        blocked = bc.safe_mode_write_gate(res)
        self.assertTrue(blocked)
        self.assertIn("safe mode", blocked[0])

    def test_panic_dump_is_structured_and_digested(self):
        dump = bc.panic_dump(ValueError("坏配置"), {"cmd": "nf cog job"}, version="2.30")
        self.assertEqual("ValueError", dump["exc_type"])
        self.assertEqual("坏配置", dump["message"])
        self.assertTrue(dump["digest"])
        self.assertNotIn("Traceback", json.dumps(dump))


if __name__ == "__main__":
    unittest.main()
