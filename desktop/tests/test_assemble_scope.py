"""T5.2 · assemble 允许集域作用域（scoped 默认 + `--loose` 逃生阀）单测。

判据面：
1. techdoc brief 的允许集从全库 248 收窄到 ≤30（实测 15 = 官方核心 13 + P06 default/allowed 2）；
2. 跨域模块提及被拒（校园 plan + 西幻编号 → 越界），同域编号仍放行；
3. 自定义/未命中预设：scoped = 官方核心 13；`--loose` 恢复全库（≥248）；
4. P02/P03/P06/P98 官方样本 `check()` 仍 PASS；`--loose` CLI 口径可见。
"""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import assemble_plan as ap  # noqa: E402

SCRIPT = ROOT / "scripts" / "nf.py"
TECHDOC_REQ = "写一份技术文档，要术语表和修订记录"
CAMPUS_REQ = "帮我组装一个校园情感世界的完整版"
CUSTOM_REQ = "帮我做一个悬疑都市的完整版"
SAMPLES = {
    "P02": (CAMPUS_REQ, "library/NF-1.md"),
    "P03": ("西幻生存+生存+单世界", "docs/完整版样本_西幻生存流P03.md"),
    "P06": (TECHDOC_REQ, "docs/examples/state-front/techdoc_front.md"),
    "P98": ("自定义：AI 内容合规证据包（合规与监管域包 P98 装配）",
            "community/合规与监管域包/outputs/samples/AI_CONTENT_COMPLIANCE_EVIDENCE_PACK.md"),
}


def _core_ids():
    reg = json.loads((ROOT / "desktop" / "src" / "core" / "registry.json")
                     .read_text(encoding="utf-8"))
    return [str(m["id"]) for m in reg.get("modules", [])]


class ScopedPlanTest(unittest.TestCase):
    def test_techdoc_allowed_shrinks_under_30(self):
        plan = ap.plan(TECHDOC_REQ)
        self.assertTrue(plan["matched"])
        self.assertEqual("preset-pipeline", plan["allowed_scope"])
        n = len(plan["allowed_module_ids"])
        self.assertLessEqual(n, 30, "techdoc 允许集应 ≤30，实为 %d" % n)
        self.assertEqual(15, n, "官方核心 13 + P06 default/allowed 2 应为 15")
        self.assertIn("M97", plan["allowed_module_ids"])
        self.assertIn("M98", plan["allowed_module_ids"])
        self.assertNotIn("情感:M22", plan["allowed_module_ids"])
        self.assertNotIn("生存:M10", plan["allowed_module_ids"])

    def test_preset_allowed_is_core_plus_pipeline_layers(self):
        plan = ap.plan("西幻生存+生存+单世界")
        allowed = set(plan["allowed_module_ids"])
        self.assertTrue(set(_core_ids()).issubset(allowed), "官方核心 13 件必须在允许集内")
        self.assertIn("M01", allowed)          # P03 P20 default
        self.assertIn("M03", allowed)          # P03 P20 allowed
        self.assertIn("生存:M10", allowed)      # P03 P60 default
        self.assertNotIn("情感:M40", allowed)   # 校园题材件不得进西幻作用域
        self.assertEqual("preset-pipeline", plan["allowed_scope"])

    def test_cross_domain_mention_rejected(self):
        plan = ap.plan(CAMPUS_REQ)
        text = "\n".join("## %d. 段" % i for i in range(8)) + \
            "\n\n## 3. 注册表投影\n\n本世界装配西幻战斗模块 M04 与生产模块 M17。\n"
        issues, stats = ap.check(text, plan)
        self.assertTrue(any("越界编号" in i and "M04" in i for i in issues),
                        "跨域 M04 应被拒，实得：%s" % issues)
        self.assertTrue(any("越界编号" in i and "M17" in i for i in issues))

    def test_same_domain_mention_accepted(self):
        plan = ap.plan(CAMPUS_REQ)
        text = "\n".join("## %d. 段" % i for i in range(8)) + \
            "\n\n## 3. 注册表投影\n\n本世界装配关系深度模块 M40 与情敌系统 M43。\n"
        issues, _ = ap.check(text, plan)
        self.assertEqual([], issues, "同域编号不得判越界：%s" % issues)

    def test_custom_scoped_is_core_only(self):
        plan = ap.plan(CUSTOM_REQ)
        self.assertFalse(plan["matched"])
        self.assertEqual("core-only", plan["allowed_scope"])
        self.assertEqual(sorted(_core_ids()), sorted(plan["allowed_module_ids"]))
        self.assertEqual(13, len(plan["allowed_module_ids"]))

    def test_loose_restores_old_full_library(self):
        scoped = ap.plan(CAMPUS_REQ)
        loose = ap.plan(CAMPUS_REQ, loose=True)
        self.assertTrue(loose["loose"])
        self.assertEqual("loose-all", loose["allowed_scope"])
        self.assertGreater(len(loose["allowed_module_ids"]), len(scoped["allowed_module_ids"]))
        self.assertGreaterEqual(len(loose["allowed_module_ids"]), 200)
        self.assertIn("生存:M10", loose["allowed_module_ids"])     # 域外件仅 --loose 可见
        self.assertIn("M91", loose["allowed_module_ids"])
        # 自定义档同样能从 13 恢复到全库
        self.assertEqual(13, len(ap.plan(CUSTOM_REQ)["allowed_module_ids"]))
        self.assertGreater(len(ap.plan(CUSTOM_REQ, loose=True)["allowed_module_ids"]), 200)

    def test_loose_check_accepts_cross_domain_mention(self):
        text = "\n".join("## %d. 段" % i for i in range(8)) + \
            "\n\n## 3. 注册表投影\n\n本世界装配西幻战斗模块 M04。\n"
        issues, _ = ap.check(text, ap.plan(CAMPUS_REQ, loose=True))
        self.assertFalse(any("越界编号" in i for i in issues),
                         "--loose 下域外编号应放行：%s" % issues)


class OfficialSampleCheckTest(unittest.TestCase):
    def test_four_official_samples_still_pass_scoped_check(self):
        for name, (req, rel) in SAMPLES.items():
            with self.subTest(sample=name):
                plan = ap.plan(req)
                text = (ROOT / rel).read_text(encoding="utf-8")
                issues, stats = ap.check(text, plan)
                self.assertEqual([], issues, "%s 样本在 scoped 口径下应 PASS：%s"
                                 % (name, issues))
                self.assertLessEqual(stats["allowed"], 30 if name == "P06" else 40)


class CliLooseTest(unittest.TestCase):
    """CLI 面：默认 scoped、`--loose` 恢复全库，帮助文本可发现。

    走**同进程** `_build_parser()` / `_cmd_assemble()`（不 fork subprocess）——DSH 类沙箱
    会禁 named pipe，subprocess 捕获 stdout 的环境性失败与本改动无关。
    """

    @classmethod
    def setUpClass(cls):
        import importlib.util
        spec = importlib.util.spec_from_file_location("nf_cli_scope_probe", SCRIPT)
        assert spec is not None and spec.loader is not None
        mod = importlib.util.module_from_spec(spec)
        sys.modules["nf_cli_scope_probe"] = mod
        spec.loader.exec_module(mod)
        cls.nf = mod
        cls.parser = mod._build_parser()

    def _assemble_parser(self):
        for action in self.parser._subparsers._group_actions:      # argparse 内部结构
            if "assemble" in getattr(action, "choices", {}):
                return action.choices["assemble"]
        self.fail("assemble 子命令未注册")

    def test_parser_has_loose_flag(self):
        scoped = self.parser.parse_args(["assemble", "需求"])
        loose = self.parser.parse_args(["assemble", "需求", "--loose"])
        self.assertFalse(scoped.loose, "默认必须是 scoped")
        self.assertTrue(loose.loose, "--loose 必须可解析")

    def test_help_documents_loose(self):
        self.assertIn("--loose", self._assemble_parser().format_help())

    def _run_plan(self, *extra):
        import contextlib
        import io
        buf = io.StringIO()
        args = self.parser.parse_args(["assemble", "帮我组装一个校园情感世界的完整版",
                                       *extra])
        with contextlib.redirect_stdout(buf):
            rc = self.nf._cmd_assemble(args)
        return rc, buf.getvalue()

    def test_cmd_scoped_output(self):
        rc, text = self._run_plan()
        self.assertEqual(0, rc)
        self.assertIn("官方核心 + 命中管线 default/allowed + references", text)
        self.assertNotIn("--loose 全库", text)

    def test_cmd_loose_output(self):
        rc, text = self._run_plan("--loose")
        self.assertEqual(0, rc)
        self.assertIn("--loose 全库", text)


if __name__ == "__main__":
    unittest.main()
