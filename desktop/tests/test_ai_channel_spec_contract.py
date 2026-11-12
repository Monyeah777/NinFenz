#!/usr/bin/env python3
"""docs/44_M2 契约：AI 通道内容规范必须「口径不变 + 三个基数活绑定 + 默认实时面 + 复现口径」。

为什么必须有：这是 AI 通道的取用规范——它写的「44 模块 / 8 管线 / 4 内容工具」是 2026-09-09 快照，
现行已是 **248 模块 / 114 管线 / 12 只读工具**，且默认服务面是实时仓库（无需快照）。基数写错会让
读者按旧面判断「取不到/可寻址范围」，或误以为必须先生成快照。本轮补状态横幅、三面更新、现状对照、
复现口径，并把模块数/管线数/工具数/默认面立成机检断言。

范围：只判本文与 mcp_runtime/文件系统事实自洽（不改取用纪律）。同族判据：
test_mcp_runtime.py（工具/prompt 面）/ test_doc_hygiene.py（指令档标识）/
test_doc_examples.py（命令块）/ test_m1_drill_coverage_contract.py（drill 规则现状）。
契约：⛔ 标识 + last-updated、表面与 URI + 覆盖解析 + 取用纪律 + 关系 + 现状对照 + 复现口径、
模块 248 / 管线 114 / 工具 12 / prompt 1 与实况一致、默认实时面声明、drill R1–R8 与 6 条规则、
历史值不回退（44/8/4 保留于快照列）。
"""
import glob
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "desktop" / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import execution_drill as drill  # noqa: E402
from core import mcp_runtime as mcp  # noqa: E402

DOC = ROOT / "docs" / "44_M2_AI通道内容规范.md"
SECTIONS = ("## 1. 表面与 URI 约定", "## 2. 覆盖与解析口径", "## 3. 取用纪律",
            "## 4. 与既有设施的关系", "## 现状对照", "## 复现与引用口径")
TOOLS = ("module_read", "pipeline_read", "asset_read", "asset_list",
         "library_read", "pattern_list", "pattern_read", "knowledge_order_read")


def load_text(path: Path = DOC) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"AI 通道规范不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("AI 通道规范为空")
    return text


def module_total() -> int:
    return len(glob.glob(str(ROOT / "04_模块库" / "*" / "*.md"))) + \
        len(glob.glob(str(ROOT / "community" / "*" / "modules" / "*.md")))


def pipeline_total() -> int:
    return len(glob.glob(str(ROOT / "03_管线库" / "*.md"))) + \
        len(glob.glob(str(ROOT / "community" / "*" / "pipelines" / "*.md")))


def spec_issues(text: str) -> list:
    issues = []
    if not text.startswith("# 44 · AI 通道内容规范"):
        issues.append("缺标题「# 44 · AI 通道内容规范」")
    if "⛔ 操作指令" not in text:
        issues.append("缺「⛔ 操作指令」标识")
    if "最后更新：" not in text:
        issues.append("缺「最后更新」位")
    if "规范口径沿用" not in text:
        issues.append("缺「规范口径沿用」状态声明")
    positions = [text.find(s) for s in SECTIONS]
    for section, pos in zip(SECTIONS, positions, strict=True):
        if pos < 0:
            issues.append(f"缺段：{section}")
    if all(p >= 0 for p in positions) and positions != sorted(positions):
        issues.append("节顺序不对")
    n_mod = module_total()
    n_pipe = pipeline_total()
    if n_mod != 248:
        issues.append(f"模块面已变（{n_mod}）：覆盖段需复核")
    if n_pipe != 114:
        issues.append(f"管线面已变（{n_pipe}）：覆盖段需复核")
    if str(n_mod) not in text or "248 件" not in text:
        issues.append("未写现行模块数（248 件）")
    if "114 条" not in text:
        issues.append("未写现行管线数（114 条）")
    if len(getattr(mcp, "TOOL_DEFS", [])) != 12:
        issues.append(f"内容工具数已变（{len(mcp.TOOL_DEFS)}）")
    if "12 只读工具" not in text and "12 只读工具" not in text.replace(" ", ""):
        issues.append("未写现行工具数（12 只读工具）")
    for tool in TOOLS:
        if tool not in text:
            issues.append(f"工具示例缺：{tool}")
    if len(getattr(mcp, "PROMPT_DEFS", [])) != 1:
        issues.append("prompt 面已变（应 1 条）")
    if "assemble_guide" not in text:
        issues.append("缺 prompt 名 assemble_guide")
    if "无需快照" not in text:
        issues.append("缺「默认实时面无需快照」声明")
    if len(getattr(drill, "RULE_LAW", {})) != 6:
        issues.append("drill 硬断言规则数已变（应 6 条）")
    if "R1–R8" not in text:
        issues.append("未写 drill 规则面 R1–R8")
    if "cross_pipeline_id" not in text or "fabricated_asset_key" not in text:
        issues.append("缺新增两条硬断言规则名")
    if "PASS=72" in text:
        issues.append("残留无关历史门禁值 PASS=72（本文件不涉门禁计数）")
    for cmd in ("python scripts/nf.py serve --help", "python scripts/nf.py module ls",
                "python scripts/nf.py market --list"):
        if cmd not in text:
            issues.append(f"复现口径缺命令：{cmd}")
    if "TODO" in text or "待补" in text:
        issues.append("含 TODO/待补 占位")
    return issues


class AIChannelSpecContractTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_spec_matches_contract(self):
        self.assertEqual([], spec_issues(self.text), "AI 通道规范不满足契约")

    def test_surfaces_live(self):
        self.assertEqual(248, module_total())
        self.assertEqual(114, pipeline_total())
        self.assertEqual(12, len(mcp.TOOL_DEFS))
        self.assertEqual(1, len(mcp.PROMPT_DEFS))
        self.assertEqual(6, len(drill.RULE_LAW))

    def test_contract_catches_mutations(self):
        """变异自证：去标识 / 基数回退 / 工具缺失 / 实时面 / 规则回退 / 缺复现命令。"""
        no_marker = self.text.replace("⛔ 操作指令", "操作指令")
        self.assertTrue(any("⛔" in i for i in spec_issues(no_marker)))
        old = self.text.replace("248 件", "44 件")
        self.assertTrue(any("248" in i for i in spec_issues(old)))
        no_tool = self.text.replace("knowledge_order_read", "某工具")
        self.assertTrue(any("knowledge_order_read" in i for i in spec_issues(no_tool)))
        no_live = self.text.replace("无需快照", "需快照")
        self.assertTrue(any("无需快照" in i for i in spec_issues(no_live)))
        old_rules = self.text.replace("R1–R8", "R1–R4")
        self.assertTrue(any("R1–R8" in i for i in spec_issues(old_rules)))
        no_sec = self.text.replace("## 现状对照（2026-11-13 · 以实跑为准）", "## 表格")
        self.assertTrue(any("缺段" in i for i in spec_issues(no_sec)))
        no_cmd = self.text.replace("python scripts/nf.py serve --help", "看帮助")
        self.assertTrue(any("serve --help" in i for i in spec_issues(no_cmd)))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_spec.md")


if __name__ == "__main__":
    unittest.main()
