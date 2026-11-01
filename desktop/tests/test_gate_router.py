# -*- coding: utf-8 -*-
"""core.gate_router 回归：策略 S 路由 + 三条硬纪律 + 变异自证。"""
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "desktop" / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import gate_faces as gf  # noqa: E402
from core import gate_router as gr  # noqa: E402


def _fixture(tmp):
    (Path(tmp) / "protocol").mkdir(parents=True, exist_ok=True)
    (Path(tmp) / "unsafe.py").write_text("import socket\n", encoding="utf-8")
    (Path(tmp) / "safe.py").write_text("X = 1\n", encoding="utf-8")
    (Path(tmp) / "cond.py").write_text("import os\nos.path.exists('x')\n", encoding="utf-8")
    (Path(tmp) / "protocol" / "gate_experts.json").write_text(
        '{"schema": "nf-gate-experts/1", "experts": ['
        '{"id": "e_unsafe", "reads": ["a.md"], "skip_safety": "SAFE", "module": "unsafe.py"},'
        '{"id": "e_safe", "reads": ["docs"], "skip_safety": "SAFE", "module": "safe.py"},'
        '{"id": "e_cond", "reads": ["b.md"], "skip_safety": "CONDITIONAL", "module": "cond.py"}]}',
        encoding="utf-8")


class RouteTest(unittest.TestCase):
    def test_unsafe_is_dense_and_declared_cannot_downgrade(self):
        with tempfile.TemporaryDirectory() as tmp:
            _fixture(tmp)
            issues, plan, stats = gr.route(tmp, ["docs/x.md"])
            self.assertEqual([], issues)
            self.assertIn("e_unsafe", plan["dense"])
            routed = {r["id"] for r in plan["routed"]}
            self.assertIn("e_unsafe", routed)
            self.assertIn("e_safe", routed)
            dormant = {d["id"]: d["reason"] for d in plan["dormant"]}
            self.assertIn("e_cond", dormant)
            self.assertTrue(dormant["e_cond"])

    def test_no_change_runs_only_dense(self):
        with tempfile.TemporaryDirectory() as tmp:
            _fixture(tmp)
            _i, plan, _s = gr.route(tmp, [])
            routed = {r["id"] for r in plan["routed"]}
            self.assertEqual({"e_unsafe"}, routed)
            self.assertEqual(2, len(plan["dormant"]))

    def test_audit_clean(self):
        with tempfile.TemporaryDirectory() as tmp:
            _fixture(tmp)
            issues, stats = gr.audit(tmp, ["docs/x.md"])
            self.assertEqual([], issues)
            self.assertEqual(3, stats["experts"])


class UnverifiedFaceTest(unittest.TestCase):
    """M2：读面未验证（face_verified=false）的专家不得被裁，须进 dense。"""

    def test_unverified_is_dense(self):
        with tempfile.TemporaryDirectory() as tmp:
            _fixture(tmp)
            doc = gf.load_manifest(tmp) if False else None  # noqa: F841
            experts = {"e_a": {"id": "e_a", "reads": [], "skip_safety": "SAFE",
                               "module": "safe.py", "face_verified": False}}
            _i, plan, _s = gr.route(tmp, ["docs/x.md"], experts=experts)
            self.assertIn("e_a", plan["dense"])
            self.assertEqual("dense(读面未验证)", plan["routed"][0]["via"])

    def test_audit_catches_culling_unverified(self):
        with tempfile.TemporaryDirectory() as tmp:
            experts = {"e_a": {"id": "e_a", "reads": [], "skip_safety": "SAFE",
                               "module": "safe.py", "face_verified": False}}
            _i, plan, _s = gr.route(tmp, [], experts=experts)
            plan["dense"] = []
            plan["routed"] = []
            issues = gr.audit_route(tmp, plan, experts)
            self.assertTrue(any("读面未验证" in i for i in issues), issues)


class MutationTest(unittest.TestCase):
    """变异自证：剪掉 UNSAFE、去掉休眠理由、漏一个专家，都必须被抓。"""

    def _plan(self, tmp):
        _i, plan, _s = gr.route(tmp, ["docs/x.md"])
        return plan

    def test_culling_unsafe_is_caught(self):
        with tempfile.TemporaryDirectory() as tmp:
            _fixture(tmp)
            plan = self._plan(tmp)
            plan["dense"] = []
            plan["routed"] = [r for r in plan["routed"] if r["id"] != "e_unsafe"]
            issues = gr.audit_route(tmp, plan)
            self.assertTrue(any("UNSAFE 专家被裁" in i for i in issues), issues)

    def test_dormant_without_reason_is_caught(self):
        with tempfile.TemporaryDirectory() as tmp:
            _fixture(tmp)
            plan = self._plan(tmp)
            plan["dormant"][0]["reason"] = "  "
            issues = gr.audit_route(tmp, plan)
            self.assertTrue(any("休眠缺理由" in i for i in issues), issues)

    def test_missing_expert_is_caught(self):
        with tempfile.TemporaryDirectory() as tmp:
            _fixture(tmp)
            plan = self._plan(tmp)
            plan["routed"] = [r for r in plan["routed"] if r["id"] != "e_safe"]
            plan["dormant"] = [d for d in plan["dormant"] if d["id"] != "e_safe"]
            issues = gr.audit_route(tmp, plan)
            self.assertTrue(any("既未路由也不休眠" in i for i in issues), issues)


if __name__ == "__main__":
    unittest.main()
