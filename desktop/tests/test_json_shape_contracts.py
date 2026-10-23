#!/usr/bin/env python3
"""JSON 顶层形状契约（审计 N11：132 个 json.load/loads 站点无类型校验）。

三层：
1. json_doc 助手本身（形状/坏件/缺件/BOM → 带指引的 ValueError）；
2. 契约/真源读取点必须走 json_doc（点名清单，防「改回去」）；
3. **棘轮**：全仓未校验的 json.load/loads 站点数只许下降（基线写死在 MAX_UNGUARDED）。
"""
import ast
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import json_doc  # noqa: E402

#: 棘轮基线（2026-10-10 N11 收口时实测）：未校验站点数只许下降。
#: 修一个契约读取点就把它调小一次；调大必须说明为何新引入未校验读点。
#: 余 1 处是 tui/nf.py:1545——该模块按设计**零 core 依赖**（只读 nf shell --surface --json 的
#: 自有输出），故刻意不走 json_doc；这是唯一在册例外。
MAX_UNGUARDED = 1
SCAN_DIRS = ("desktop/src", "scripts", "tui")

#: 契约/真源读取点：这些文件必须至少有一处走 json_doc（顶层形状判据的落点）。
CONTRACT_READERS = (
    "desktop/src/core/assertions.py",
    "desktop/src/core/receipts.py",
    "desktop/src/core/registry_cross.py",
    "desktop/src/core/judgement_coverage.py",
    "desktop/src/core/decisions.py",
    "desktop/src/core/driver.py",
    "desktop/src/core/rfc.py",
    "desktop/src/core/conformance_report.py",
    "desktop/src/core/conformance_scan.py",
    "desktop/src/core/schema_lint.py",
    "desktop/src/core/payload_registry.py",
    "desktop/src/core/locales.py",
    "desktop/src/core/knowledge.py",
    "desktop/src/core/verify_report.py",
    "desktop/src/core/machine_contract.py",
    "desktop/src/core/transparency_log.py",
    "desktop/src/core/interop_export.py",
    "desktop/src/core/coupling_metrics.py",
    "desktop/src/core/module_signature.py",
    "desktop/src/core/conformance_decl.py",
    "desktop/src/core/mcp_package.py",
    "desktop/src/core/repo_stats.py",
    "desktop/src/core/approval.py",
    "desktop/src/core/gap_review.py",
    "desktop/src/core/payload_harvest.py",
    "desktop/src/core/payload_typing.py",
    "desktop/src/core/assemble_build.py",
    "desktop/src/core/assemble_plan.py",
    "desktop/src/core/storage.py",
    "desktop/src/core/decision_layer.py",
    "desktop/src/core/postmortem.py",
    "desktop/src/core/mcp_runtime.py",
    "desktop/src/core/nfal_cli.py",
    "desktop/src/core/layer_model.py",
    "desktop/src/core/shell_ledger.py",
    "desktop/src/core/rating_gate.py",
    "desktop/src/core/state_front.py",
    "desktop/src/core/world_slots.py",
    "desktop/src/core/nfal.py",
    "desktop/src/core/orchestration.py",
    "desktop/src/core/pipelinerun.py",
    "desktop/src/core/cognition.py",
    "desktop/src/core/endpoint.py",
    "desktop/src/core/doc_family.py",
    "desktop/src/core/nf_language.py",
    "desktop/src/core/workloop.py",
    "desktop/src/core/regression_score.py",
    "desktop/src/core/instruction_evidence.py",
    "desktop/src/core/disk_cache.py",
    "desktop/src/core/drill_fidelity.py",
    "desktop/src/core/integrations.py",
    "desktop/src/core/output_forms.py",
    "desktop/src/core/domain_pack.py",
    "desktop/src/core/asset_contract.py",
    "desktop/src/core/asset_ledger_projection.py",
    "desktop/src/core/asset_line_baseline.py",
    "desktop/src/core/domain_metrics.py",
    "desktop/src/core/st_quality.py",
    "desktop/src/core/pack_combo.py",
    "desktop/src/core/bench.py",
    "desktop/src/core/execution_drill.py",
    "desktop/src/core/terminal.py",
    "scripts/check_interop_schemas.py",
    "scripts/nf.py",
    "scripts/geo_export.py",
    "scripts/pull_decision_model.py",
    "scripts/serve_decision_model.py",
    # 注：scripts/nf_verify.py 是**独立验证器**（零 core 依赖，供仓库外验证回执），
    # 其顶层形状校验在本地就地 isinstance——故不在本清单内（见 test_reader_verify 的零依赖判据）。
    "scripts/orchestrate.py",
    "scripts/fde_sample_run.py",
    "scripts/interop_thirdparty_kit.py",
    ".github/scripts/library_ingest.py",
    ".github/scripts/gitee_ingest.py",
)


def unguarded_sites(root: Path) -> list:
    """AST 扫 json.load/loads：±6 行内无 isinstance 的记一条（纯函数，可变异自证）。"""
    out = []
    for d in SCAN_DIRS:
        for p in sorted((root / d).rglob("*.py")):
            if p.name == "json_doc.py":
                continue  # 助手自身：包一层解析是它的职责
            try:
                src = p.read_text(encoding="utf-8")
                tree = ast.parse(src)
            except (OSError, SyntaxError):
                continue
            lines = src.split(chr(10))
            for node in ast.walk(tree):
                if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
                    continue
                if node.func.attr not in ("load", "loads"):
                    continue
                if not (isinstance(node.func.value, ast.Name) and node.func.value.id == "json"):
                    continue
                ctx = chr(10).join(lines[max(0, node.lineno - 7):node.lineno + 6])
                if "isinstance(" not in ctx:
                    out.append("%s:%d" % (p.relative_to(root).as_posix(), node.lineno))
    return out


class JsonDocHelperTest(unittest.TestCase):
    def test_check_accepts_expected_shapes(self):
        self.assertEqual({"a": 1}, json_doc.check({"a": 1}, dict, "x"))
        self.assertEqual([1], json_doc.check([1], list, "x"))
        self.assertEqual(1, json_doc.check(1, (int, float), "x"))

    def test_check_rejects_wrong_shape_with_guide(self):
        for bad in ([1, 2], "hello", 42, None):
            with self.assertRaises(ValueError) as ctx:
                json_doc.check(bad, dict, "协议件 X")
            self.assertIn("顶层形状不对", str(ctx.exception))
            self.assertIn("修复指引", str(ctx.exception))

    def test_loads_tolerates_bom_and_rejects_bad_json(self):
        self.assertEqual({"a": 1}, json_doc.loads("\ufeff" + '{"a": 1}', dict, what="t"))
        with self.assertRaises(ValueError) as ctx:
            json_doc.loads("{oops", dict, what="t")
        self.assertIn("不是合法 JSON", str(ctx.exception))
        self.assertIn("修复指引", str(ctx.exception))

    def test_excessive_nesting_fails_before_recursive_parse(self):
        too_deep = "[" * (json_doc.MAX_JSON_DEPTH + 1) + "]" * (json_doc.MAX_JSON_DEPTH + 1)
        with self.assertRaisesRegex(ValueError, "嵌套过深"):
            json_doc.loads(too_deep, list, what="deep")
        ok = "[" * json_doc.MAX_JSON_DEPTH + "]" * json_doc.MAX_JSON_DEPTH
        self.assertIsInstance(json_doc.loads(ok, list, what="ok"), list)

    def test_load_reports_missing_file_and_shape(self):
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "nope.json"
            with self.assertRaises(ValueError) as ctx:
                json_doc.load(missing, dict, what="缺件")
            self.assertIn("缺件", str(ctx.exception))
            good = Path(tmp) / "list.json"
            good.write_text("[1, 2]", encoding="utf-8")
            with self.assertRaises(ValueError) as ctx:
                json_doc.load(good, dict, what="数组件")
            self.assertIn("顶层形状不对", str(ctx.exception))


class ContractReadersTest(unittest.TestCase):
    def test_contract_readers_go_through_json_doc(self):
        missing = []
        for rel in CONTRACT_READERS:
            text = (ROOT / rel).read_text(encoding="utf-8")
            if "json_doc." not in text and "json_doc import" not in text:
                missing.append(rel)
        self.assertEqual([], missing, "契约读取点未走 json_doc（N11）：%s" % missing)


class UnguardedRatchetTest(unittest.TestCase):
    def test_unguarded_sites_do_not_grow(self):
        bad = unguarded_sites(ROOT)
        self.assertLessEqual(
            len(bad), MAX_UNGUARDED,
            "未校验的 json.load/loads 站点增至 %d（基线 %d）。新读点请走 core.json_doc.load/loads："
                "\n%s"
            % (len(bad), MAX_UNGUARDED, chr(10).join(bad[:10])))

    def test_scanner_catches_a_mutation(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            (d / "scripts").mkdir()
            (d / "scripts" / "m.py").write_text(
                "import json\nx = json.load(open('a.json'))\n", encoding="utf-8")
            self.assertEqual(1, len(unguarded_sites(d)))


if __name__ == "__main__":
    unittest.main()
