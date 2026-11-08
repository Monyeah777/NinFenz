"""预注册评测判据（D-05）：协议先冻结、只计数、演练数据不得当证据。

判据盯四件事：
① 协议冻结：frozen_before_run 必须 true；缺 free 基线/缺反窄化指标 → 拒；
② 不打分：协议与 run 里出现 score/grade/rating 键 → 拒（递归查）；
③ 演练 ≠ 测量：synthetic run 不得进 compare（直接拒），fixture 报告必须写明 measurement=not-run；
④ 只给计数差：compare 输出中位数与差值，不含 p 值/排序/总分键。
"""
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import eval_harness as eh  # noqa: E402

SCRIPT = (sys.executable, str(ROOT / "scripts" / "eval_run.py"))


def _protocol() -> dict:
    return eh.load_protocol(str(ROOT))


def _run(proto: dict, source: str = "measured") -> dict:
    items = []
    for cond in proto["conditions"]:
        for task in proto["tasks"]:
            for sample in range(1, int(proto["samples_per_task"]) + 1):
                items.append({
                    "condition": cond["id"], "task": task["id"], "sample": sample,
                    "values": {dim["id"]: (5 if cond["id"] == "free" else 2)
                               for dim in proto["dimensions"]},
                })
    return eh.record_run(proto, {"source": source, "items": items})


class ProtocolTest(unittest.TestCase):
    def test_protocol_is_valid(self):
        proto = _protocol()
        self.assertEqual([], eh.validate_protocol(proto))
        self.assertTrue(proto["frozen_before_run"])

    def test_unfrozen_protocol_is_rejected(self):
        proto = json.loads(json.dumps(_protocol()))
        proto["frozen_before_run"] = False
        self.assertTrue(any("冻结" in i for i in eh.validate_protocol(proto)))

    def test_missing_free_baseline_is_rejected(self):
        proto = json.loads(json.dumps(_protocol()))
        proto["conditions"] = [c for c in proto["conditions"] if c["id"] != "free"]
        self.assertTrue(any("free" in i for i in eh.validate_protocol(proto)))

    def test_missing_narrowing_metric_is_rejected(self):
        proto = json.loads(json.dumps(_protocol()))
        proto["dimensions"] = [d for d in proto["dimensions"]
                               if d["id"] != "table_external_mechanisms"]
        self.assertTrue(any("反窄化" in i for i in eh.validate_protocol(proto)))

    def test_score_keys_in_protocol_are_rejected(self):
        proto = json.loads(json.dumps(_protocol()))
        proto["dimensions"][0]["score"] = 1
        self.assertTrue(any("打分键" in i for i in eh.validate_protocol(proto)))

    def test_bad_dimension_kind_is_rejected(self):
        proto = json.loads(json.dumps(_protocol()))
        proto["dimensions"][0]["kind"] = "vibes"
        self.assertTrue(any("kind 非法" in i for i in eh.validate_protocol(proto)))


class RunTest(unittest.TestCase):
    def test_valid_run(self):
        proto = _protocol()
        run = _run(proto)
        self.assertEqual("measured", run["source"])
        self.assertTrue(run["digest"])

    def test_unknown_condition_is_rejected(self):
        proto = _protocol()
        run = _run(proto)
        run["items"][0]["condition"] = "no-such"
        with self.assertRaises(ValueError):
            eh.record_run(proto, run)

    def test_missing_dimension_is_rejected(self):
        proto = _protocol()
        run = _run(proto)
        run["items"][0]["values"].pop("coherence")
        with self.assertRaises(ValueError) as ctx:
            eh.record_run(proto, run)
        self.assertIn("缺维度值", str(ctx.exception))

    def test_score_key_in_run_is_rejected(self):
        proto = _protocol()
        run = _run(proto)
        run["items"][0]["score"] = 0.9
        with self.assertRaises(ValueError) as ctx:
            eh.record_run(proto, run)
        self.assertIn("打分键", str(ctx.exception))

    def test_bad_source_is_rejected(self):
        proto = _protocol()
        run = _run(proto)
        run["source"] = "guess"
        with self.assertRaises(ValueError) as ctx:
            eh.record_run(proto, run)
        self.assertIn("measured", str(ctx.exception))

    def test_sample_out_of_range_is_rejected(self):
        proto = _protocol()
        run = _run(proto)
        run["items"][0]["sample"] = 99
        with self.assertRaises(ValueError):
            eh.record_run(proto, run)

    def test_checklist_covers_every_cell_without_fabricating_data(self):
        """采集检查单：格子数 = 条件×任务×样本，全部 planned、values 为空（不伪造测量）。"""
        doc = eh.eval_run_checklist(str(ROOT))
        protocol = eh.load_protocol(str(ROOT))
        expected = (len(protocol["conditions"]) * len(protocol["tasks"])
                    * int(protocol["samples_per_task"]))
        self.assertEqual(expected, len(doc["cells"]))
        self.assertEqual({"planned"}, {c["status"] for c in doc["cells"]})
        self.assertTrue(all(c["values"] == {} for c in doc["cells"]),
                        "未采集就填了值——那是伪造测量")
        self.assertTrue(all(c["review"]["reviewer"] is None for c in doc["cells"]))
        self.assertEqual("evaluation-design", doc["pack"]["id"])
        self.assertIn("planned", json.dumps(doc["negative_control"]))
        self.assertEqual("not-run", doc["measurement"]["status"])

    def test_checklist_is_deterministic(self):
        self.assertEqual(eh.eval_run_checklist(str(ROOT)),
                         eh.eval_run_checklist(str(ROOT)))


class CompareTest(unittest.TestCase):
    def test_compare_gives_diffs_and_narrowing(self):
        proto = _protocol()
        out = eh.compare(proto, [_run(proto)])
        self.assertIn("diffs_vs_free", out)
        self.assertIn("narrowing_index", out)
        self.assertEqual(-3.0, out["diffs_vs_free"]["hybrid"]["frame_change"])

    def test_synthetic_run_is_blocked(self):
        proto = _protocol()
        with self.assertRaises(ValueError) as ctx:
            eh.compare(proto, [_run(proto, source="synthetic")])
        self.assertIn("synthetic", str(ctx.exception))

    def test_output_has_no_score_keys(self):
        proto = _protocol()
        text = json.dumps(eh.compare(proto, [_run(proto)])).lower()
        for key in ('"score', '"grade', '"rating', '"p_value'):
            self.assertNotIn(key, text)

    def test_empty_runs_is_rejected(self):
        with self.assertRaises(ValueError):
            eh.compare(_protocol(), [])


class ScriptTest(unittest.TestCase):
    def test_report_is_reproducible(self):
        proc = subprocess.run([*SCRIPT, "--json"], capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=180)
        self.assertEqual(0, proc.returncode, proc.stderr[-300:])
        report = json.loads(proc.stdout)
        self.assertTrue(report["ok"], report["harness"])
        self.assertTrue(report["harness"]["synthetic_blocked"])

    def test_measurement_not_claimed(self):
        proc = subprocess.run([*SCRIPT, "--json"], capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=180)
        report = json.loads(proc.stdout)
        self.assertEqual("not-run", report["measurement"]["status"])


if __name__ == "__main__":
    unittest.main()
