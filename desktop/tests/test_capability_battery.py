# -*- coding: utf-8 -*-
"""吸收项契约电池回归：契约真源 ↔ 磁盘模块 ↔ 真实调用 三方一致。"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "desktop" / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import capability_battery as cb  # noqa: E402


class CapabilityBatteryTest(unittest.TestCase):
    def test_contracts_shape(self):
        doc = cb.contracts(str(ROOT))
        self.assertEqual("nf-capability-contracts/1", doc.get("schema"))
        caps = doc.get("capabilities") or []
        self.assertGreaterEqual(len(caps), 10)
        ids = [c["id"] for c in caps]
        self.assertEqual(len(ids), len(set(ids)), "契约 id 必须唯一")
        for c in caps:
            for k in ("id", "module", "entry", "family", "source", "cases"):
                self.assertTrue(str(c.get(k) or "").strip(),
                                "契约缺 %s：%s" % (k, c.get("id")))
            self.assertTrue(c["cases"], "契约无用例：%s" % c["id"])

    def test_every_contract_module_and_entry_exists(self):
        for c in cb.contracts(str(ROOT)).get("capabilities") or []:
            mod = cb.MODULES.get(c["module"])
            self.assertIsNotNone(mod, "电池未装载：%s" % c["module"])
            self.assertTrue(callable(getattr(mod, c["entry"], None)),
                            "入口不存在：%s.%s" % (c["module"], c["entry"]))

    def test_all_capabilities_pass(self):
        doc = cb.run(str(ROOT))
        bad = [r for r in doc["rows"] if not r["ok"]]
        self.assertEqual([], bad, "契约未通过：%s" % bad[:3])

    def test_missing_root_is_fail_closed(self):
        doc = cb.run(str(ROOT / "no-such-root"))
        self.assertEqual(0, doc["total"])


if __name__ == "__main__":
    unittest.main()
