#!/usr/bin/env python3
"""WP-22 Output/Validation 判据（contract + output form；失败拒收）。

判据：
1. 好产物：`nf-output-report/1` ok、citations 100%、contract 过 `nf-contract/1` schema；
2. committed `results/output/output-report.json` == 实时重算（可复算）；
3. 坏产物必须**拒收**（accept 抛 OutputRejected + code + 修复指引）：
   编造引用 / 控制字符 / 占位符 / md 无标题 / json 不可解析；
4. Assembly Runtime gate 复用本模块：坏产物 → status=blocked + K-002 红、无 export；
5. form/tier 口径对齐 `protocol/output_forms.json`（不新造形态词表）。
"""
import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import agent_adapter as aa  # noqa: E402
from core import assembly_runtime as ar  # noqa: E402
from core import context_packer as cp  # noqa: E402
from core import json_schema  # noqa: E402
from core import output_validation as ov  # noqa: E402
from core import spec_compiler as sc  # noqa: E402

INTENT = "spec/intents/sample-document.json"
REPORT = "results/output/output-report.json"


def _setup():
    intent = json.loads((ROOT / INTENT).read_text(encoding="utf-8"))
    task = sc.compile_intent(intent, str(ROOT), INTENT)["tasks"][0]
    pack = cp.pack_task(task, str(ROOT), budget_chars=2000, role="author")
    out = aa.run("mock", task, pack, str(ROOT))
    return task, pack, out


class OutputValidationContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.task, cls.pack, cls.out = _setup()

    def test_good_output_accepted(self):
        report = ov.validate(self.out, self.task, self.pack, str(ROOT))
        self.assertTrue(report["ok"], report["issues"])
        self.assertEqual("nf-output-report/1", report["schema"])
        self.assertEqual(1.0, report["metrics"]["citation_rate"])
        self.assertEqual(0, report["metrics"]["violations"])
        schema = json.loads((ROOT / ov.CONTRACT_SCHEMA_REL).read_text(encoding="utf-8"))
        self.assertEqual([], json_schema.json_schema_check(report["contract"], schema))

    def test_committed_report_equals_live(self):
        live = ov.validate(self.out, self.task, self.pack, str(ROOT))
        self.assertEqual(ov.render(live), (ROOT / REPORT).read_text(encoding="utf-8"),
                         "committed output-report 必须 == 实时重算")

    def _reject(self, mutate, expect_code):
        bad = copy.deepcopy(self.out)
        mutate(bad)
        with self.assertRaises(ov.OutputRejected) as ctx:
            ov.accept(bad, self.task, self.pack, str(ROOT))
        self.assertEqual(expect_code, ctx.exception.code)
        self.assertIn("修复指引", ctx.exception.message)

    def test_fabricated_citation_rejected(self):
        self._reject(lambda b: b["citations"].append("wiki:fake:page"), "ADAPTER-CONTRACT")

    def test_control_chars_rejected(self):
        self._reject(lambda b: b["output"].__setitem__(
            "content", "## x\nbad\x07char"), "FORM-CONTROL-CHARS")

    def test_placeholder_rejected(self):
        self._reject(lambda b: b["output"].__setitem__(
            "content", "## x\nTODO"), "FORM-PLACEHOLDER")

    def test_md_without_heading_rejected(self):
        self._reject(lambda b: b["output"].__setitem__("content", "no heading here"),
                     "FORM-MD-NO-HEADING")

    def test_json_form_invalid_rejected(self):
        task = copy.deepcopy(self.task)
        task["output_schema"] = {"kind": "json", "path": "out.json"}
        bad = copy.deepcopy(self.out)
        bad["output"]["kind"] = "json"
        bad["output"]["content"] = "not json"
        with self.assertRaises(ov.OutputRejected) as ctx:
            ov.accept(bad, task, self.pack, str(ROOT))
        self.assertEqual("FORM-JSON-INVALID", ctx.exception.code)

    def test_assembly_gate_uses_validation(self):
        original = aa.run
        bad = copy.deepcopy(self.out)
        bad["output"]["content"] = "no heading"
        try:
            aa.run = lambda *a, **k: bad  # type: ignore[assignment]
            rec = ar.run(INTENT, "mock", str(ROOT))
        finally:
            aa.run = original  # type: ignore[assignment]
        self.assertEqual("blocked", rec["run"]["status"])
        self.assertEqual("OUTPUT-INVALID", rec["run"]["error"]["code"])
        self.assertTrue(any(c["id"] == "K-002" and not c["ok"] for c in rec["run"]["checks"]))
        self.assertNotIn("export", [s["id"] for s in rec["run"]["steps"]])
        self.assertTrue(any(c["id"] == "K-002" and not c["ok"] for c in rec["run"]["checks"]))

    def test_form_vocab_matches_output_forms(self):
        forms = json.loads((ROOT / "protocol/output_forms.json").read_text(encoding="utf-8"))
        tiers = forms.get("tiers") or {}
        report = ov.validate(self.out, self.task, self.pack, str(ROOT))
        self.assertIn(report["tier"], tiers, "tier 必须对齐 protocol/output_forms.json")


if __name__ == "__main__":
    unittest.main()
