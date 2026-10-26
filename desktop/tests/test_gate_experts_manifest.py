# -*- coding: utf-8 -*-
"""真声明面（protocol/gate_experts.json）判据：形状合法、读面已验证、路由覆盖全、对账零缺口。"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "desktop" / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import gate_faces as gf   # noqa: E402
from core import gate_router as gr  # noqa: E402


class RealManifestTest(unittest.TestCase):
    def test_manifest_is_valid_and_verified(self):
        doc = gf.load_manifest_doc(str(ROOT))
        self.assertEqual([], gf.validate_manifest(doc), "真声明面形状不合契约")
        experts = gf.load_manifest(str(ROOT))
        self.assertGreaterEqual(len(experts), 4, "真声明面专家数不足")
        for eid, e in experts.items():
            self.assertTrue(e.get("face_verified"), "%s 未标 face_verified" % eid)
            self.assertTrue(e.get("reads"), "%s 读面为空" % eid)
            self.assertIn(e.get("skip_safety"), gf.SKIP_SAFETY, eid)

    def test_route_covers_every_expert(self):
        experts = gf.load_manifest(str(ROOT))
        _i, plan, _s = gr.route(str(ROOT), ["docs/README.md"], experts=experts)
        seen = {r["id"] for r in plan["routed"]} | {d["id"] for d in plan["dormant"]}
        self.assertEqual(set(experts), seen, "路由表未覆盖全部专家")

    def test_repo_audit_reports_no_gap(self):
        issues, stats = gf.audit(str(ROOT))
        self.assertEqual([], issues, "真仓读面对账有缺口：%s" % issues[:3])
        self.assertGreaterEqual(stats["experts"], 4)


if __name__ == "__main__":
    unittest.main()
