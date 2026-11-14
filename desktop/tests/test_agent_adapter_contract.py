#!/usr/bin/env python3
"""WP-20 Agent Adapter 判据（有界任务/输出契约/2 adapter parity）。

判据：
1. 2 个 adapter（mock/local-template）都能跑同一 `nf-task/1`，输出过 `nf-adapter-output/1`；
2. 编造引用（不在 context_refs）→ 红；超 budget → 红；kind 不符 → 红；坏 task/未知 adapter → 错误码；
3. parity：两 adapter citations 集一致、kind 一致，报告 committed == 实时重算（确定性）；
4. 本地子进程桩（local-template）不依赖网络/外部服务；真实外部 adapter 继续挂 OPEN；
5. CLI `nf agent list` / `nf agent run --adapter ...` 可用。
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
from core import context_packer as cp  # noqa: E402
from core import spec_compiler as sc  # noqa: E402

SCRIPT = ROOT / "scripts" / "nf.py"
INTENT = "spec/intents/sample-document.json"


def _task():
    intent = json.loads((ROOT / INTENT).read_text(encoding="utf-8"))
    return sc.compile_intent(intent, str(ROOT), INTENT)["tasks"][0]


class AgentAdapterContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.task = _task()
        cls.pack = cp.pack_task(cls.task, str(ROOT), budget_chars=2000, role="author")

    def test_two_adapters_listed(self):
        rows = aa.list_adapters()
        ids = {row["id"] for row in rows}
        self.assertGreaterEqual(len(rows), 2)
        self.assertEqual({"mock", "local-template"}, ids)
        for row in rows:
            for field in ("kind", "determinism", "cost", "desc"):
                self.assertTrue(row.get(field))

    def test_both_adapters_valid(self):
        for aid in ("mock", "local-template"):
            out = aa.run(aid, self.task, self.pack, str(ROOT))
            self.assertEqual([], aa.validate_output(out, self.task, self.pack))
            allowed = {c["id"] for c in self.task["context_refs"]}
            self.assertTrue(set(out["citations"]) <= allowed or
                            set(out["citations"]) == {e["id"] for e in self.pack["entries"]})
            self.assertLessEqual(len(out["output"]["content"]),
                                 self.task["budget"]["max_tokens"] * 4)

    def test_parity_report_and_committed(self):
        rep = aa.parity_report(self.task, self.pack, str(ROOT))
        self.assertTrue(rep["parity"])
        self.assertEqual([], rep["issues"])
        committed = (ROOT / aa.REPORT_REL).read_text(encoding="utf-8")
        self.assertEqual(aa.render(rep), committed, "committed adapter-report 必须 == 实时重算")

    def test_fabricated_citation_rejected(self):
        out = aa.run("mock", self.task, self.pack, str(ROOT))
        bad = copy.deepcopy(out)
        bad["citations"] = bad["citations"] + ["wiki:fake:page"]
        self.assertTrue(aa.validate_output(bad, self.task, self.pack), "编造引用必须红")

    def test_over_budget_rejected(self):
        out = aa.run("mock", self.task, self.pack, str(ROOT))
        bad = copy.deepcopy(out)
        bad["output"]["content"] = "x" * (self.task["budget"]["max_tokens"] * 4 + 10)
        self.assertTrue(aa.validate_output(bad, self.task, self.pack), "超预算必须红")

    def test_kind_mismatch_rejected(self):
        out = aa.run("mock", self.task, self.pack, str(ROOT))
        bad = copy.deepcopy(out)
        bad["output"]["kind"] = "json"
        self.assertTrue(aa.validate_output(bad, self.task, self.pack), "kind 不符必须红")

    def test_bad_task_and_unknown_adapter(self):
        with self.assertRaises(aa.AdapterError) as ctx:
            aa.run("mock", {"schema": "nf-task/1"}, None, str(ROOT))
        self.assertEqual("TASK-INVALID", ctx.exception.code)
        with self.assertRaises(aa.AdapterError) as ctx:
            aa.run("nope", self.task, self.pack, str(ROOT))
        self.assertEqual("ADAPTER-UNKNOWN", ctx.exception.code)
        self.assertIn("修复指引", ctx.exception.message)

    def test_cli(self):
        proc = subprocess.run([sys.executable, str(SCRIPT), "agent", "run",
                               "--adapter", "mock", "--intent", INTENT, "--json"],
                              cwd=str(ROOT), capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=120)
        self.assertEqual(0, proc.returncode, proc.stderr[-300:])
        payload = json.loads(proc.stdout)
        self.assertEqual("nf-adapter-output/1", payload["output"]["schema"])
        self.assertTrue(payload["report"]["parity"])


if __name__ == "__main__":
    unittest.main()
