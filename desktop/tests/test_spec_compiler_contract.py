#!/usr/bin/env python3
"""WP-11 Spec Compiler 判据（intent → nf-spec/1 → nf-task/1）。

判据：
1. 样本 intent 合法；编译产物经 `nf-spec/1`/`nf-task/1` schema 校验（含 digest/budget/acceptance）；
2. 确定性：同 intent + 同 Wiki 页 → 逐字节一致；改约束 → digest 变；
3. 拒绝未知：未知 kind/wiki id/未知字段 → SpecError（CLI exit 2 + 修复指引）；
4. 任务图无环（relations 图拓扑检查）+ context_refs digest 与 Wiki 页一致；
5. CLI `nf spec compile --intent ... --json` 可跑、坏 intent exit 2。
"""
import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import json_schema  # noqa: E402
from core import spec_compiler as sc  # noqa: E402

INTENT_REL = "spec/intents/sample-document.json"
SCRIPT = ROOT / "scripts" / "nf.py"


def _intent():
    return json.loads((ROOT / INTENT_REL).read_text(encoding="utf-8"))


class SpecCompilerContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.intent = _intent()
        cls.bundle = sc.compile_intent(cls.intent, str(ROOT), INTENT_REL)

    def test_sample_intent_valid(self):
        self.assertEqual([], sc.parse_intent(self.intent))
        self.assertEqual("nf-intent/1", self.intent["schema"])

    def test_bundle_schema_valid(self):
        self.assertEqual([], sc.validate_bundle(self.bundle, str(ROOT)))
        spec_schema = json.loads((ROOT / sc.SPEC_SCHEMA_REL).read_text(encoding="utf-8"))
        task_schema = json.loads((ROOT / sc.TASK_SCHEMA_REL).read_text(encoding="utf-8"))
        self.assertEqual([], json_schema.json_schema_check(self.bundle["spec"], spec_schema))
        for task in self.bundle["tasks"]:
            self.assertEqual([], json_schema.json_schema_check(task, task_schema))
            self.assertGreaterEqual(task["budget"]["max_tokens"], 1)
            self.assertTrue(task["acceptance"])
        self.assertGreaterEqual(len(self.bundle["tasks"]), 1)

    def test_deterministic(self):
        again = sc.compile_intent(_intent(), str(ROOT), INTENT_REL)
        self.assertEqual(sc.render(self.bundle), sc.render(again))
        changed = copy.deepcopy(self.intent)
        changed["constraints"] = changed["constraints"] + ["新增一条硬约束"]
        other = sc.compile_intent(changed, str(ROOT), INTENT_REL)
        self.assertNotEqual(self.bundle["spec"]["digest"], other["spec"]["digest"])

    def test_unknown_kind_rejected(self):
        bad = copy.deepcopy(self.intent)
        bad["kind"] = "bogus"
        with self.assertRaises(sc.SpecError) as ctx:
            sc.compile_intent(bad, str(ROOT))
        self.assertIn(ctx.exception.code, ("INTENT-INVALID", "SPEC-KIND-UNKNOWN"))
        self.assertTrue(ctx.exception.fix)

    def test_unknown_wiki_id_rejected(self):
        bad = copy.deepcopy(self.intent)
        bad["wiki_ids"] = ["wiki:module:NOT-EXIST"]
        with self.assertRaises(sc.SpecError) as ctx:
            sc.compile_intent(bad, str(ROOT))
        self.assertEqual("WIKI-ID-UNKNOWN", ctx.exception.code)

    def test_unknown_field_rejected(self):
        bad = copy.deepcopy(self.intent)
        bad["surprise"] = 1
        with self.assertRaises(sc.SpecError):
            sc.compile_intent(bad, str(ROOT))

    def test_task_graph_acyclic(self):
        pages = {"wiki:a": {"relations": [{"kind": "references", "target": "wiki:b"}]},
                 "wiki:b": {"relations": [{"kind": "references", "target": "wiki:a"}]}}
        self.assertTrue(sc.task_graph_issues(pages, ["wiki:a", "wiki:b"]), "环必须被检出")
        pages_ok = {"wiki:a": {"relations": [{"kind": "references", "target": "wiki:b"}]},
                    "wiki:b": {"relations": []}}
        self.assertEqual([], sc.task_graph_issues(pages_ok, ["wiki:a", "wiki:b"]))

    def test_context_refs_match_wiki(self):
        pages = sc._pages(str(ROOT))
        for task in self.bundle["tasks"]:
            for ctx in task["context_refs"]:
                pid = ctx["id"]
                self.assertEqual(pages[pid]["provenance"]["digest"], ctx["digest"])

    def test_cli_compile_and_reject(self):
        proc = subprocess.run([sys.executable, str(SCRIPT), "spec", "compile",
                               "--intent", INTENT_REL, "--json"],
                              cwd=str(ROOT), capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=120)
        self.assertEqual(0, proc.returncode, proc.stderr[-300:])
        payload = json.loads(proc.stdout)
        self.assertEqual("nf-spec-bundle/1", payload["schema"])
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "bad.json"
            bad.write_text(json.dumps({"schema": "nf-intent/1", "kind": "bogus",
                                       "goal": "x", "wiki_ids": ["wiki:module:M06"],
                                       "constraints": ["x"], "budget": {"max_tokens": 10}}),
                           encoding="utf-8")
            proc = subprocess.run([sys.executable, str(SCRIPT), "spec", "compile",
                                   "--intent", str(bad)],
                                  cwd=str(ROOT), capture_output=True, text=True,
                                  encoding="utf-8", errors="replace", timeout=120)
            self.assertEqual(2, proc.returncode)
            self.assertIn("✗", proc.stderr)
            self.assertIn("修复指引", proc.stderr)


if __name__ == "__main__":
    unittest.main()
