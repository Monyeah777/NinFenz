"""M80 结构门 S4/S5 单测（T4.1：术语一致 / 无越层直写）。

判据（M80 §2.1，`desktop/src/core/quality_gate.py`）：
- S4 `_r_term_consistency`：消费 M97 `term_synced` + DocState.terms——未同步 /
  已使用无定义 / 规范术语与别名混用 → fail；**无术语域数据时不启用**（通用装配零影响）。
- S5 `_r_no_layer_bypass`：消费 M23 可见性裁剪结果——隐藏域直述 → fail；
  **无可见性数据时不启用**。
- 两条规则须进入 `default_rules()`（结构门 = 硬门），但仅条件评估。

运行：cd desktop && python -m unittest tests.test_quality_gate_techdoc -v
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from core.ir import IRDocument, IRLayer, IRModule  # noqa: E402
from core.quality_gate import (  # noqa: E402
    _r_no_layer_bypass, _r_term_consistency, default_rules, run_gate)


def _ir(content: str = "正文", meta: dict | None = None) -> IRDocument:
    return IRDocument(
        title="测试文档", pipeline_id="P06", pipeline_name="技术文档题材装配流",
        layers=[
            IRLayer(id="P00", name="数据基座", modules=[
                IRModule(full_id="M00", name="数据结构", layer="P00", content="正文")]),
            IRLayer(id="P80", name="输出呈现", modules=[
                IRModule(full_id="M80", name="输出质检门", layer="P80",
                         content=content)]),
        ], extra_modules=[], meta=meta or {})


def _run(rule, ir):
    return list(rule(ir))


class TermConsistencyRuleTest(unittest.TestCase):
    """S4 术语一致：2 正 2 反。"""

    def test_positive_without_term_state(self):
        # 正例①：无术语域数据（通用装配）→ 不启用
        self.assertEqual([], _run(_r_term_consistency, _ir("任意正文")))

    def test_positive_synced_terms(self):
        # 正例②：term_synced 通过 + 已定义术语被使用
        meta = {"term_synced": {"ok": True, "status": "ok", "count": 1},
                "doc_state": {"terms": {"API": {"definition": "应用程序接口",
                                                "first_use_chapter": "1"}}}}
        self.assertEqual([], _run(_r_term_consistency, _ir("调用 API 即可", meta)))

    def test_negative_unsynced(self):
        # 反例①：term_synced 未通过（M97 冲突未消解）
        meta = {"term_synced": {"ok": False, "status": "conflict",
                                "conflicts": ["API"]}}
        issues = _run(_r_term_consistency, _ir("调用 API", meta))
        self.assertEqual(1, len(issues))
        self.assertEqual("fail", issues[0].level)
        self.assertIn("术语表未同步", issues[0].message)
        self.assertTrue(issues[0].suggestion)

    def test_negative_undefined_or_alias_mixed(self):
        # 反例②：已使用但无定义（M97 首用未定义）
        meta = {"doc_state": {"terms": {"API": {"definition": ""}}}}
        issues = _run(_r_term_consistency, _ir("调用 API", meta))
        self.assertTrue(any("无定义" in i.message for i in issues), issues)
        # 反例②b：规范术语与别名混用
        meta2 = {"doc_state": {"terms": {"固件": {"definition": "内置程序",
                                                  "aliases": ["firmware"]}}}}
        issues2 = _run(_r_term_consistency, _ir("固件与 firmware 混用", meta2))
        self.assertTrue(any("混用" in i.message for i in issues2), issues2)


class NoLayerBypassRuleTest(unittest.TestCase):
    """S5 无越层直写：2 正 2 反。"""

    def test_positive_without_visibility_state(self):
        self.assertEqual([], _run(_r_no_layer_bypass, _ir("公开可见的正文")))

    def test_positive_hidden_declared_but_absent(self):
        meta = {"visibility": {"hidden": ["内部报价"]}}
        self.assertEqual([], _run(_r_no_layer_bypass, _ir("公开可见的正文", meta)))

    def test_negative_hidden_direct_statement(self):
        meta = {"visibility": {"hidden": ["内部报价 100 元"]}}
        issues = _run(_r_no_layer_bypass, _ir("本机内部报价 100 元，对外不可见", meta))
        self.assertEqual(1, len(issues))
        self.assertEqual("fail", issues[0].level)
        self.assertIn("隐藏域直述", issues[0].message)
        self.assertIn("M23", issues[0].suggestion)

    def test_negative_hidden_slot_path(self):
        meta = {"hidden_slots": ["WorldState.internal.secret"]}
        issues = _run(_r_no_layer_bypass,
                      _ir("直写 WorldState.internal.secret 字段", meta))
        self.assertTrue(any("隐藏域直述" in i.message for i in issues), issues)


class DefaultRulesIntegrationTest(unittest.TestCase):
    def test_new_structural_rules_in_default_rules(self):
        names = {r.__name__ for r in default_rules()}
        self.assertEqual(6, len(default_rules()))
        self.assertIn("_r_term_consistency", names)
        self.assertIn("_r_no_layer_bypass", names)

    def test_narrative_gate_count_unchanged_without_techdoc_data(self):
        res = run_gate(_ir("任意正文"))
        self.assertTrue(res.ok())
        self.assertEqual(len(default_rules()), res.n_pass)

    def test_fail_blocks_ok(self):
        meta = {"visibility": {"hidden": ["内部报价"]}}
        res = run_gate(_ir("内部报价泄漏", meta))
        self.assertFalse(res.ok())
        self.assertGreaterEqual(res.n_fail, 1)
        report = res.report_text()
        self.assertIn("隐藏域直述", report)


if __name__ == "__main__":
    unittest.main()
