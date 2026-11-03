"""标识体检价值链（pipeline.py）的单元回归。

作者：impl（DSH agent）· 2026-11-02
运行：cd desktop && PYTHONPATH=src python3 -m unittest tests.test_labeling_pipeline -v

覆盖：基础 evaluate（无 platform/history）、pipeline schema、renders 键、
save_outputs 七件套、未知平台不崩、历史 list/文件两种形态、坏历史与缺文件
的修复指引、selfcheck 形状、结果 JSON 可序列化、CLI 退出码与用法错。
可选子系统（platform_rules / xcheck / metadata_extra）未落盘时，用例按
降级语义断言（UNAVAILABLE），落盘后同一套用例自动改按真实接口断言。
"""

import csv
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core.labeling import metadata, pipeline  # noqa: E402

PY = sys.executable
SCRIPT = str(ROOT / "scripts" / "nf_label_pipeline.py")
RENDER_KEYS = {"html", "console", "svg", "csv_row", "csv_header", "csv"}
OUTPUT_FILES = {
    "html": "report.html", "json": "report.json", "summary": "summary.txt",
    "svg": "card.svg", "csv": "row.csv", "recheck": "recheck.json",
    "xcheck": "xcheck.json",
}


def make_labeled_png(path, produce_id="PIPE-TEST-1"):
    """带 AIGC JSON 文本块的 PNG（当前判据下为 WARN，exit 0）。"""
    fields = {"Label": 1, "ContentProducer": "1" * 27,
              "ProduceID": produce_id}
    metadata.make_png(path, {"AIGC": json.dumps(fields, ensure_ascii=False)})
    return path


class PipelineBase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        self.png = str(self.dir / "a.png")
        make_labeled_png(self.png)

    def tearDown(self):
        self._tmp.cleanup()


class EvaluateTest(PipelineBase):
    def test_schema_and_required_keys(self):
        result = pipeline.evaluate(self.png)
        self.assertEqual(result["schema"], "nf-label-pipeline/1")
        for key in ("report", "platform_eval", "recheck", "xcheck", "renders"):
            self.assertIn(key, result)
        self.assertEqual(result["report"]["schema"], "nf-label-report/1")
        self.assertEqual(result["verdict"], result["report"]["verdict"])
        self.assertEqual(result["exit_code"], result["report"]["exit_code"])
        self.assertIsNone(result["platform_eval"])
        self.assertIsNone(result["recheck"])
        self.assertIsInstance(result["xcheck"], dict)
        self.assertIsInstance(result["missing"], list)
        self.assertIsInstance(result["degraded"], list)

    def test_renders_have_all_keys_and_consistent_csv(self):
        result = pipeline.evaluate(self.png)
        renders = result["renders"]
        self.assertEqual(set(renders), RENDER_KEYS)
        for key in RENDER_KEYS:
            self.assertIsInstance(renders[key], str, key)
            self.assertTrue(renders[key].strip(), key)
        self.assertIn(result["verdict"], renders["html"])
        self.assertNotIn("<script", renders["html"].lower())
        self.assertTrue(renders["svg"].lstrip().startswith("<svg"))
        header = next(csv.reader(io.StringIO(renders["csv_header"])))
        row = next(csv.reader(io.StringIO(renders["csv_row"])))
        self.assertEqual(len(header), len(row))

    def test_save_outputs_writes_all_seven_files(self):
        result = pipeline.evaluate(self.png)
        out = str(self.dir / "out")
        paths = pipeline.save_outputs(result, out)
        self.assertEqual(set(paths), set(OUTPUT_FILES))
        for key, name in OUTPUT_FILES.items():
            target = Path(paths[key])
            self.assertEqual(target.name, name)
            self.assertTrue(target.is_file(), key)
        self.assertEqual(json.loads(Path(paths["json"]).read_text("utf-8")),
                         result["report"])
        json.loads(Path(paths["recheck"]).read_text("utf-8"))
        json.loads(Path(paths["xcheck"]).read_text("utf-8"))
        self.assertIn(result["verdict"],
                      Path(paths["summary"]).read_text("utf-8"))
        self.assertTrue(Path(paths["svg"]).read_text("utf-8")
                        .lstrip().startswith("<svg"))
        self.assertEqual(len(Path(paths["csv"]).read_text("utf-8")
                             .strip().splitlines()), 2)

    def test_unknown_platform_does_not_crash(self):
        result = pipeline.evaluate(self.png, platform="不存在的平台")
        pe = result["platform_eval"]
        self.assertIsInstance(pe, dict)
        tokens = " ".join(str(pe.get(key, ""))
                          for key in ("status", "verdict", "result")).upper()
        if pe.get("available", True) is False:
            self.assertIn("UNAVAILABLE", tokens)
        else:
            # platform_rules 在场时应把未知平台判成 UNKNOWN；单次求值失败为 ERROR。
            self.assertIn("UNKNOWN", tokens)
        self.assertEqual(result["report"]["verdict"],
                         pipeline.evaluate(self.png)["report"]["verdict"])

    def test_result_is_json_serializable(self):
        result = pipeline.evaluate(self.png)
        text = json.dumps(result, ensure_ascii=False)
        again = json.loads(text)
        self.assertEqual(again["schema"], result["schema"])
        self.assertEqual(again["report"]["report_id"],
                         result["report"]["report_id"])


class HistoryTest(PipelineBase):
    def test_list_history_baseline_then_recheck(self):
        history = []
        first = pipeline.evaluate(self.png, history=history)
        self.assertEqual(first["recheck"]["status"], "FIRST")
        self.assertTrue(first["recheck"]["history_appended"])
        self.assertEqual(len(history), 1)
        self.assertIsNotNone(history[0].get("report"))
        self.assertTrue(history[0].get("recheck_id"))

        second = pipeline.evaluate(self.png, history=history)
        self.assertEqual(len(history), 2)
        self.assertTrue(second["recheck"]["history_appended"])
        self.assertEqual(second["recheck"]["previous"]["report_id"],
                         first["report"]["report_id"])
        self.assertIn(second["history"]["source"], ("memory", "file"))
        self.assertEqual(second["history"]["entries"], 2)

    def test_file_history_roundtrip_and_saved(self):
        path = str(self.dir / "history.json")
        pipeline.evaluate(self.png, history=path)
        second = pipeline.evaluate(self.png, history=path)
        self.assertTrue(Path(path).is_file())
        self.assertIsInstance(json.loads(Path(path).read_text("utf-8")), list)
        entries = pipeline.load_history(path)
        self.assertEqual(len(entries), 2)
        self.assertTrue(second["history"]["saved"])
        self.assertEqual(second["history"]["source"], "file")
        self.assertTrue(all("recheck_id" in item for item in entries))

    def test_bad_history_and_missing_input_have_repair_hints(self):
        bad = self.dir / "bad.json"
        bad.write_text("{", encoding="utf-8")
        with self.assertRaises(ValueError) as ctx:
            pipeline.evaluate(self.png, history=str(bad))
        self.assertIn("修复指引", str(ctx.exception))
        with self.assertRaises(TypeError) as ctx:
            pipeline.evaluate(self.png, history=42)
        self.assertIn("修复指引", str(ctx.exception))
        with self.assertRaises(FileNotFoundError) as ctx:
            pipeline.evaluate(str(self.dir / "missing.png"))
        self.assertIn("修复指引", str(ctx.exception))


class SelfcheckAndCliTest(PipelineBase):
    def test_selfcheck_reports_each_subsystem(self):
        report = pipeline.selfcheck()
        self.assertEqual(report["schema"], "nf-label-selfcheck/1")
        self.assertIsInstance(report["ok"], bool)
        self.assertEqual(report["status"], "PASS" if report["ok"] else "FAIL")
        names = {item["name"] for item in report["checks"]}
        self.assertEqual(names, set(pipeline.SUBSYSTEMS))
        for item in report["checks"]:
            self.assertIsInstance(item["ok"], bool)
            self.assertIsInstance(item["missing"], list)
            self.assertIsInstance(item["hint"], str)
        self.assertTrue(next(i for i in report["checks"]
                             if i["name"] == "report")["ok"])
        self.assertEqual(set(report["missing"]),
                         {i["name"] for i in report["checks"] if not i["ok"]})

    def test_cli_json_exit_code_and_out_dir(self):
        out = str(self.dir / "cli-out")
        proc = subprocess.run(
            [PY, SCRIPT, "evaluate", self.png, "--json", "--out", out],
            cwd=str(ROOT), capture_output=True, text=True, timeout=120)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        data = json.loads(proc.stdout)
        self.assertEqual(data["schema"], "nf-label-pipeline/1")
        self.assertEqual(proc.returncode, data["report"]["exit_code"])
        for name in OUTPUT_FILES.values():
            self.assertTrue((Path(out) / name).is_file(), name)

        bare = str(self.dir / "bare.png")
        metadata.make_png(bare)
        fail = subprocess.run(
            [PY, SCRIPT, "evaluate", bare, "--json"],
            cwd=str(ROOT), capture_output=True, text=True, timeout=120)
        self.assertEqual(fail.returncode, 1, fail.stderr)
        self.assertEqual(json.loads(fail.stdout)["report"]["verdict"], "FAIL")

    def test_cli_usage_and_missing_file_exit_2(self):
        usage = subprocess.run([PY, SCRIPT], cwd=str(ROOT),
                               capture_output=True, text=True, timeout=120)
        self.assertEqual(usage.returncode, 2)
        missing = subprocess.run(
            [PY, SCRIPT, "evaluate", str(self.dir / "nope.png")],
            cwd=str(ROOT), capture_output=True, text=True, timeout=120)
        self.assertEqual(missing.returncode, 2)
        self.assertIn("修复指引", missing.stderr)


if __name__ == "__main__":
    unittest.main()
