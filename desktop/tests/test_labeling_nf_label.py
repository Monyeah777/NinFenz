"""统一入口 scripts/nf_label.py 的回归（新子命令 + 旧命令透传）。"""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core.labeling import metadata  # noqa: E402

PY = sys.executable
ENTRY = str(ROOT / "scripts" / "nf_label.py")


def run(*args, timeout=180):
    return subprocess.run([PY, ENTRY, *args], cwd=str(ROOT),
                          capture_output=True, text=True, timeout=timeout)


class NfLabelCliTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        self.png = str(self.dir / "a.png")
        metadata.make_png(self.png, {"AIGC": json.dumps(
            {"Label": 1, "ContentProducer": "1" * 27,
             "ProduceID": "CLI-1"}, ensure_ascii=False)})

    def tearDown(self):
        self._tmp.cleanup()

    def test_matrix(self):
        r = run("matrix")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("容器", r.stdout)

    def test_legacy_selfcheck_passthrough(self):
        r = run("selfcheck")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("自检结果：PASS", r.stdout)

    def test_report_writes_html(self):
        out = str(self.dir / "rep")
        r = run("report", self.png, "--out", out,
                "--generated-at", "2026-11-02T00:00:00+0800")
        self.assertIn(r.returncode, (0, 1), r.stderr)
        self.assertTrue(any(Path(out).glob("*.html")))

    def test_pipeline_writes_seven_outputs(self):
        out = str(self.dir / "pipe")
        r = run("pipeline", self.png, "--out", out)
        self.assertIn(r.returncode, (0, 1), r.stderr)
        names = {p.name for p in Path(out).iterdir()}
        self.assertTrue({"report.html", "report.json", "summary.txt",
                         "card.svg", "row.csv", "recheck.json",
                         "xcheck.json"} <= names, names)

    def test_platform_json(self):
        r = run("platform", self.png, "douyin", "--json")
        self.assertIn(r.returncode, (0, 1), r.stderr)
        doc = json.loads(r.stdout)
        self.assertEqual(doc["platform"], "douyin")
        self.assertIn(doc["overall"], ("PASS", "WARN", "FAIL", "UNKNOWN"))

    def test_xcheck(self):
        r = run("xcheck", self.png)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("交叉认证", r.stdout)

    def test_recheck_two_reports(self):
        r1 = run("report", self.png, "--json")
        self.assertIn(r1.returncode, (0, 1), r1.stderr)
        before = str(self.dir / "before.json")
        Path(before).write_text(r1.stdout, encoding="utf-8")
        after = str(self.dir / "after.json")
        Path(after).write_text(r1.stdout, encoding="utf-8")
        r = run("recheck", before, after)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("复测", r.stdout)


if __name__ == "__main__":
    unittest.main()
