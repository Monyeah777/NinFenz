#!/usr/bin/env python3
"""WP-21 Assembly Runtime 判据（P00 黄金路径 core-only E2E）。

判据：
1. 同 intent 用 mock / local-template 两 adapter 都能跑完整链 → `nf-assembly/1` 计划 + run 信封；
2. assembly 严格过 `protocol/production/assembly.schema.json`（additionalProperties=false）；
3. 失败即停：未知 adapter / 坏 intent → status=blocked + error，**不产出 export**；
4. gate：输出不合契约/超预算 → blocked（K 红项），不静默放行；
5. 记录可复算：committed `results/assembly/sample-document.assembly.json` == 实时重算；
6. CLI `nf agent run --assembly` 可用；core-only（无第三方 import）。
"""
import copy
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import agent_adapter as aa  # noqa: E402
from core import assembly_runtime as ar  # noqa: E402
from core import context_packer as cp  # noqa: E402
from core import json_schema  # noqa: E402
from core import spec_compiler as sc  # noqa: E402

SCRIPT = ROOT / "scripts" / "nf.py"
INTENT = "spec/intents/sample-document.json"
RECORD = "results/assembly/sample-document.assembly.json"


def _task():
    intent = json.loads((ROOT / INTENT).read_text(encoding="utf-8"))
    return sc.compile_intent(intent, str(ROOT), INTENT)["tasks"][0]


class AssemblyRuntimeContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bundle = json.loads((ROOT / RECORD).read_text(encoding="utf-8"))
        cls.task = _task()

    def test_two_adapters_e2e(self):
        for aid in ("mock", "local-template"):
            rec = ar.run(INTENT, aid, str(ROOT))
            self.assertEqual("delivered", rec["run"]["status"], aid)
            self.assertEqual([], ar.validate_record(rec, str(ROOT)))
            self.assertEqual("P00", rec["assembly"]["pipeline"])

    def test_assembly_schema_strict(self):
        schema = json.loads((ROOT / ar.ASSEMBLY_SCHEMA_REL).read_text(encoding="utf-8"))
        for aid in ("mock", "local-template"):
            rec = ar.run(INTENT, aid, str(ROOT))
            self.assertEqual([], json_schema.json_schema_check(rec["assembly"], schema))
            self.assertNotIn("intent", rec["assembly"], "运行元数据不得塞进 nf-assembly/1")

    def test_committed_record_equals_live(self):
        live = ar.run(INTENT, "mock", str(ROOT))
        self.assertEqual(ar.render(live), (ROOT / RECORD).read_text(encoding="utf-8"),
                         "committed assembly 记录必须 == 实时重算")

    def test_fail_fast_unknown_adapter(self):
        rec = ar.run(INTENT, "nope", str(ROOT))
        self.assertEqual("blocked", rec["run"]["status"])
        self.assertEqual("ADAPTER-UNKNOWN", rec["run"]["error"]["code"])
        self.assertNotIn("export", [s["id"] for s in rec["run"]["steps"]])
        self.assertTrue(rec["run"]["error"]["message"])

    def test_bad_intent_blocked(self):
        rec = ar.run("spec/intents/nonexistent.json", "mock", str(ROOT))
        self.assertEqual("blocked", rec["run"]["status"])
        self.assertIn("error", rec["run"])

    def test_gate_blocks_bad_output(self):
        """用篡改的 task 让输出超预算 → K 红、blocked；不得静默放行。"""
        bad_task = copy.deepcopy(self.task)
        bad_task["budget"]["max_tokens"] = 1
        bundle = {"schema": "nf-spec-bundle/1",
                  "spec": {"ref": "output:test", "digest": "a" * 64},
                  "tasks": [bad_task]}
        original = sc.compile_intent
        try:
            sc.compile_intent = lambda *a, **k: bundle  # type: ignore[assignment]
            rec = ar.run(INTENT, "mock", str(ROOT))
        finally:
            sc.compile_intent = original  # type: ignore[assignment]
        self.assertEqual("blocked", rec["run"]["status"])
        self.assertIn(rec["run"]["error"]["code"], ("OUTPUT-INVALID", "GATE-FAILED"))
        self.assertTrue(any(not c["ok"] for c in rec["run"]["checks"]),
                        "失败必须留红项（不得静默放行）")
        self.assertNotIn("export", [s["id"] for s in rec["run"]["steps"]])

    def test_core_only_imports(self):
        text = (ROOT / "desktop/src/core/assembly_runtime.py").read_text(encoding="utf-8")
        for line in text.splitlines():
            line = line.strip()
            if line.startswith("import ") or line.startswith("from "):
                self.assertNotIn("requests", line)
                self.assertNotIn("yaml", line)
                self.assertFalse(line.startswith("from core.production"), line)

    def test_cli(self):
        proc = subprocess.run([sys.executable, str(SCRIPT), "agent", "run",
                               "--adapter", "mock", "--intent", INTENT,
                               "--assembly", "--json"],
                              cwd=str(ROOT), capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=180)
        self.assertEqual(0, proc.returncode, proc.stderr[-300:])
        payload = json.loads(proc.stdout)
        self.assertEqual("nf-assembly-run/1", payload["schema"])
        self.assertEqual("delivered", payload["run"]["status"])
        self.assertEqual("nf-assembly/1", payload["assembly"]["schema"])


if __name__ == "__main__":
    unittest.main()
