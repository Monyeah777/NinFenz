#!/usr/bin/env python3
"""WP-23 Delivery 判据（包完整/路径安全/可重复/sidecar 不阻塞）。

判据：
1. delivered + 校验通过的产物 → 打包成功；manifest `nf-delivery/1` 文件 digest/size 与在盘一致；
2. committed `results/delivery/delivery-report.json` == 实时 verify 重算（可复算）；
3. 篡改包内文件 → verify 红；manifest 路径穿越 → 红；symlink → 红；
4. sidecar 可选：带/不带都能 verify 通过；声明与实物不一致 → 红；
5. 未 delivered / 校验未过 → 拒收（DeliveryError）；manifest 确定性（两次同字节）；
6. CLI `nf agent run --assembly --deliver [--sidecar]` 可用。
"""
import copy
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import agent_adapter as aa  # noqa: E402
from core import assembly_runtime as ar  # noqa: E402
from core import context_packer as cp  # noqa: E402
from core import delivery as dv  # noqa: E402
from core import output_validation as ov  # noqa: E402
from core import spec_compiler as sc  # noqa: E402

SCRIPT = ROOT / "scripts" / "nf.py"
INTENT = "spec/intents/sample-document.json"
PACK_DIR = "results/delivery/wiki-module-M06"
REPORT = "results/delivery/delivery-report.json"


def _ctx():
    intent = json.loads((ROOT / INTENT).read_text(encoding="utf-8"))
    task = sc.compile_intent(intent, str(ROOT), INTENT)["tasks"][0]
    pack = cp.pack_task(task, str(ROOT), budget_chars=2000, role="author")
    out = aa.run("mock", task, pack, str(ROOT))
    report = ov.validate(out, task, pack, str(ROOT))
    record = ar.run(INTENT, "mock", str(ROOT))
    return record, out, report


class DeliveryContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.record, cls.out, cls.report_doc = _ctx()
        cls.pack = dv.build(cls.record, cls.out, cls.report_doc, sidecar=True)

    def test_pack_manifest_and_verify(self):
        self.assertEqual("nf-delivery/1", self.pack["manifest"]["schema"])
        self.assertTrue(all(f["digest"] for f in self.pack["manifest"]["files"]))
        issues, report = dv.verify(PACK_DIR, str(ROOT))
        self.assertEqual([], issues)
        self.assertTrue(report["ok"])
        self.assertTrue(report["sidecar"])

    def test_committed_report_equals_live(self):
        _, live = dv.verify(PACK_DIR, str(ROOT))
        self.assertEqual(dv.render_report(live), (ROOT / REPORT).read_text(encoding="utf-8"),
                         "committed delivery-report 必须 == 实时 verify")

    def test_tamper_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            dst = Path(tmp) / "pack"
            shutil.copytree(ROOT / PACK_DIR, dst)
            (dst / "artifact.md").write_text("tampered", encoding="utf-8")
            issues, report = dv.verify(str(dst), str(ROOT))
            self.assertTrue(issues, "篡改必须被检出")
            self.assertIn("digest", " ".join(issues))

    def test_path_traversal_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            dst = Path(tmp) / "pack"
            shutil.copytree(ROOT / PACK_DIR, dst)
            manifest = json.loads((dst / "manifest.json").read_text(encoding="utf-8"))
            manifest["files"].append({"path": "../evil.md", "role": "artifact",
                                      "digest": "a" * 64, "size": 1})
            (dst / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            issues, _ = dv.verify(str(dst), str(ROOT))
            self.assertTrue(any("路径不安全" in i for i in issues), issues)

    def test_symlink_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            dst = Path(tmp) / "pack"
            shutil.copytree(ROOT / PACK_DIR, dst)
            target = dst / "artifact.md"
            target.unlink()
            target.symlink_to(ROOT / "README.md")
            issues, _ = dv.verify(str(dst), str(ROOT))
            self.assertTrue(any("symlink" in i for i in issues), issues)

    def test_sidecar_optional(self):
        no_side = dv.build(self.record, self.out, self.report_doc, sidecar=False)
        self.assertFalse(no_side["manifest"]["sidecar"])
        self.assertNotIn(dv.SIDECAR, no_side["files"])
        self.assertIn(dv.ARTIFACT, no_side["files"])

    def test_not_delivered_rejected(self):
        blocked = copy.deepcopy(self.record)
        blocked["run"]["status"] = "blocked"
        with self.assertRaises(dv.DeliveryError) as ctx:
            dv.build(blocked, self.out, self.report_doc)
        self.assertEqual("NOT-DELIVERED", ctx.exception.code)
        bad_report = copy.deepcopy(self.report_doc)
        bad_report["ok"] = False
        with self.assertRaises(dv.DeliveryError) as ctx:
            dv.build(self.record, self.out, bad_report)
        self.assertEqual("OUTPUT-NOT-VALIDATED", ctx.exception.code)

    def test_manifest_deterministic(self):
        a = dv.build(self.record, self.out, self.report_doc, sidecar=True)
        b = dv.build(self.record, self.out, self.report_doc, sidecar=True)
        self.assertEqual(a["files"][dv.MANIFEST], b["files"][dv.MANIFEST])

    def test_cli_deliver(self):
        proc = subprocess.run([sys.executable, str(SCRIPT), "agent", "run",
                               "--adapter", "mock", "--intent", INTENT,
                               "--assembly", "--deliver", "--sidecar"],
                              cwd=str(ROOT), capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=180)
        self.assertEqual(0, proc.returncode, proc.stderr[-300:])
        self.assertIn("交付包", proc.stdout)


if __name__ == "__main__":
    unittest.main()
