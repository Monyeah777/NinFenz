"""标识体检报告（report.py）的单元回归。

作者：impl（DSH agent）· 2026-11-02
运行：cd <repo> && python3 -m unittest desktop.tests.test_labeling_report -v

只测报告层：预检（含加密 PDF 提示）、报告结构、HTML 自包含性、落盘、
批量、矩阵与 CLI 退出码；判定逻辑本身由 test_labeling_core 覆盖。
"""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core.labeling import metadata, report  # noqa: E402

PY = sys.executable
LAUNCHER = str(ROOT / "scripts" / "nf_label_report.py")


def make_meta_png(path):
    """造一个带 AIGC JSON 文本块的 PNG（无签名，结论多为 WARN/FAIL）。"""
    fields = {"Label": 1, "ContentProducer": "1" * 27,
              "ProduceID": "REPORT-TEST-1"}
    metadata.make_png(path, {"AIGC": json.dumps(fields, ensure_ascii=False)})


class PreflightTest(unittest.TestCase):
    def test_png_preflight_ok(self):
        with tempfile.TemporaryDirectory() as td:
            png = str(Path(td) / "a.png")
            metadata.make_png(png)
            pre = report.preflight(png)
        self.assertEqual(pre["container"], "png")
        self.assertTrue(pre["readable"])
        self.assertEqual(pre["warnings"], [])
        self.assertEqual(len(pre["sha256"]), 64)

    def test_pdf_encrypt_warns(self):
        with tempfile.TemporaryDirectory() as td:
            pdf = str(Path(td) / "a.pdf")
            Path(pdf).write_bytes(
                b"%PDF-1.7\n1 0 obj\n<< /Encrypt << /Filter /Standard >> >>"
                b"\nendobj\ntrailer\n<< /Root 1 0 R >>\n%%EOF\n")
            pre = report.preflight(pdf)
        self.assertEqual(pre["container"], "pdf")
        self.assertTrue(any("/Encrypt" in w for w in pre["warnings"]))

    def test_missing_file_unreadable(self):
        pre = report.preflight("/nonexistent/x.png")
        self.assertFalse(pre["readable"])
        self.assertTrue(pre["warnings"])


class BuildReportTest(unittest.TestCase):
    def _report(self, td):
        png = str(Path(td) / "a.png")
        make_meta_png(png)
        return report.build_report(png, generated_at="2026-11-02T00:00:00+0800")

    def test_structure(self):
        with tempfile.TemporaryDirectory() as td:
            rep = self._report(td)
        self.assertEqual(rep["schema"], "nf-label-report/1")
        self.assertEqual(len(rep["report_id"]), 16)
        self.assertEqual(set(rep["summary"]), {"A", "B", "C", "D", "E"})
        self.assertIn(rep["verdict"], ("PASS", "WARN", "FAIL"))
        self.assertIsInstance(rep["actions"], list)
        self.assertEqual(rep["generated_at"], "2026-11-02T00:00:00+0800")
        self.assertEqual(rep["file"]["name"], "a.png")

    def test_report_id_is_content_addressed(self):
        with tempfile.TemporaryDirectory() as td:
            png = str(Path(td) / "a.png")
            make_meta_png(png)
            one = report.build_report(png, generated_at="t")
            two = report.build_report(png, generated_at="t")
        self.assertEqual(one["report_id"], two["report_id"])
        self.assertEqual(one["file"]["sha256"], two["file"]["sha256"])

    def test_render_html_self_contained(self):
        with tempfile.TemporaryDirectory() as td:
            rep = self._report(td)
        page = report.render_html(rep)
        self.assertIn("<!doctype html>", page)
        self.assertIn("标识体检报告", page)
        self.assertNotIn("<script", page)
        self.assertNotIn('src="http', page)
        self.assertNotIn('href="http', page)
        self.assertIn("免责声明", page)
        self.assertIn(rep["report_id"], page)

    def test_render_markdown(self):
        with tempfile.TemporaryDirectory() as td:
            rep = self._report(td)
        md = report.render_markdown(rep)
        self.assertIn("# GB 45438 标识体检报告", md)
        self.assertIn("复算命令", md)

    def test_write_report_three_files(self):
        with tempfile.TemporaryDirectory() as td:
            rep = self._report(td)
            out = str(Path(td) / "out")
            paths = report.write_report(rep, out)
            for key in ("html", "json", "md"):
                self.assertTrue(Path(paths[key]).is_file(), key)
            doc = json.loads(Path(paths["json"]).read_text(encoding="utf-8"))
            self.assertEqual(doc["report_id"], rep["report_id"])


class BatchTest(unittest.TestCase):
    def test_batch_index_and_summary(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "src"
            root.mkdir()
            metadata.make_png(str(root / "a.png"))
            make_meta_png(str(root / "b.png"))
            (root / "note.xyz").write_bytes(b"\x00\x01\x02")
            out = str(Path(td) / "out")
            items, index, summary = report.run_batch(
                str(root), out, generated_at="2026-11-02T00:00:00+0800")
            self.assertTrue(Path(index).is_file())
            doc = json.loads(Path(summary).read_text(encoding="utf-8"))
            self.assertEqual(len(items), 2)  # 二进制 .xyz 被默认排除
            self.assertEqual(doc["total"], 2)
            self.assertEqual(doc["schema"], "nf-label-report/1#batch")
            self.assertTrue(Path(out, "reports").is_dir())


class CliTest(unittest.TestCase):
    def _run(self, *args):
        return subprocess.run([PY, LAUNCHER, *args], cwd=str(ROOT),
                              capture_output=True, text=True, timeout=120)

    def test_matrix(self):
        r = self._run("matrix")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("容器", r.stdout)
        self.assertIn("pdf", r.stdout)

    def test_selfcheck(self):
        r = self._run("selfcheck")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("PASS", r.stdout)

    def test_report_missing_rc2(self):
        r = self._run("report", "/nonexistent/x.png")
        self.assertEqual(r.returncode, 2)

    def test_report_writes_dir(self):
        with tempfile.TemporaryDirectory() as td:
            png = str(Path(td) / "a.png")
            make_meta_png(png)
            out = str(Path(td) / "out")
            r = self._run("report", png, "--out", out,
                          "--generated-at", "2026-11-02T00:00:00+0800")
            self.assertIn(r.returncode, (0, 1), r.stderr)
            self.assertTrue(any(Path(out).glob("*.html")))


if __name__ == "__main__":
    unittest.main()
