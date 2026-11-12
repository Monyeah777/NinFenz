#!/usr/bin/env python3
"""docs/41_波C_C7 实测记录 契约：快照 + 工具面现状对照 + 复现口径 + E3 口径。

为什么必须有：这份记录写于 2026-09-08——当时 MCP 工具面是 **4 个只读工具**、起服务要带快照；
现行已是 **12 个只读工具**（新增 library_read / module_read / pipeline_read / asset_* /
pattern_* / knowledge_order_read），且入口默认实时仓库面（无需快照）。记录不标快照状态，
读者会把 4 工具/需快照当现状。本轮补「历史快照」横幅、「现状对照（当时→现行）」表、
「复现与引用口径」段（含 E3 外部客户端仍待回填的口径）。

范围：只判本文与引用事实/现行 MCP 面自洽（不改历史数值）。同族判据：
test_mcp_runtime.py（工具/prompt/未知方法回归）/ test_c1c2_record_contract.py（同类快照口径）/
test_doc_reachability.py（可达性）/ docs/mcp.md（E3 状态句真源）。
契约：标题 + 快照横幅、六段按序、历史数值保留、工具面「当时 4 → 现行 12」与 TOOL_DEFS 实况一致、
prompt 一条 assemble_guide、入口默认无需快照、E3 待回填口径引用 docs/mcp.md、复现命令在 CLI。
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "desktop" / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import mcp_runtime as mcp  # noqa: E402

DOC = ROOT / "docs" / "41_波C_C7_实测记录.md"
MCP_DOC = ROOT / "docs" / "mcp.md"
SECTIONS = ("## 交付", "## 实测", "## 验收口径", "## 回归",
            "## 现状对照", "## 复现与引用口径")
HISTORICAL = ("4 个只读检索工具", "406 OK", "PASS=39", "tools/list", "prompts/get")
CURRENT = ("12 个只读工具", "library_read", "module_read", "pipeline_read",
           "asset_list", "pattern_list", "无需快照", "tools/list")


def load_text(path: Path = DOC) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"实测记录不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("实测记录为空")
    return text


def record_issues(text: str) -> list:
    issues = []
    if not text.startswith("# 41 波C C7 实测记录"):
        issues.append("缺标题「# 41 波C C7 实测记录」")
    if "状态：历史实测快照" not in text:
        issues.append("缺「历史实测快照」状态横幅（读者会误当现状）")
    if "不随仓库演进而改写" not in text:
        issues.append("缺「不随演进改写」声明")
    positions = [text.find(s) for s in SECTIONS]
    for section, pos in zip(SECTIONS, positions, strict=True):
        if pos < 0:
            issues.append(f"缺段：{section}")
    if all(p >= 0 for p in positions) and positions != sorted(positions):
        issues.append("六段顺序不对")
    for marker in HISTORICAL:
        if marker not in text:
            issues.append(f"历史数值/口径被改写：{marker}")
    for marker in CURRENT:
        if marker not in text:
            issues.append(f"现状对照缺要素：{marker}")
    if not (ROOT / "desktop" / "src" / "core" / "mcp_runtime.py").is_file():
        issues.append("缺实现件：desktop/src/core/mcp_runtime.py")
    if not (ROOT / "desktop" / "tests" / "test_mcp_runtime.py").is_file():
        issues.append("缺判据件：desktop/tests/test_mcp_runtime.py")
    tools = {t["name"] for t in mcp.TOOL_DEFS}
    if len(tools) != 12:
        issues.append(f"TOOL_DEFS 工具数已变（{len(tools)}）：现状对照需复核")
    for want in ("library_read", "module_read", "pipeline_read"):
        if want not in tools:
            issues.append(f"TOOL_DEFS 缺工具：{want}")
    if str(len(tools)) + " 个只读工具" not in text:
        issues.append(f"现状对照未写当前工具数（{len(tools)}）")
    prompts = {p["name"] for p in mcp.PROMPT_DEFS}
    if prompts != {"assemble_guide"}:
        issues.append(f"prompt 面已变（{sorted(prompts)}）：现状对照需复核")
    if "assemble_guide" not in text:
        issues.append("缺 prompt 口径：assemble_guide")
    if "无需快照" not in text:
        issues.append("缺「现行入口默认无需快照」口径")
    if "nf serve" not in text:
        issues.append("缺现行入口命令：nf serve")
    mcp_doc = MCP_DOC.read_text(encoding="utf-8")
    if "回填" not in mcp_doc:
        issues.append("docs/mcp.md 缺 E3 回填状态句（真源漂移）")
    if "docs/mcp.md" not in text:
        issues.append("E3 待办口径未指向 docs/mcp.md")
    if "-32602" not in text or "-32601" not in text:
        issues.append("缺未知工具/方法错误码口径")
    if "TODO" in text or "待补" in text:
        issues.append("含 TODO/待补 占位")
    return issues


class C7RecordContractTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_record_matches_contract(self):
        self.assertEqual([], record_issues(self.text), "实测记录不满足契约")

    def test_tool_face_is_live(self):
        names = {t["name"] for t in mcp.TOOL_DEFS}
        self.assertEqual(12, len(names))
        self.assertIn("12 个只读工具", self.text)
        self.assertEqual({"assemble_guide"}, {p["name"] for p in mcp.PROMPT_DEFS})

    def test_e3_status_source_agrees(self):
        self.assertIn("回填", MCP_DOC.read_text(encoding="utf-8"))
        self.assertIn("docs/mcp.md", self.text)

    def test_contract_catches_mutations(self):
        """变异自证：去快照横幅 / 改历史数值 / 工具数漂移 / 去无需快照 / 去 E3 口径。"""
        no_banner = self.text.replace("> **状态：历史实测快照**", "> **状态：现行**", 1)
        self.assertTrue(any("历史实测快照" in i for i in record_issues(no_banner)))
        rewritten = self.text.replace("406 OK", "999 OK")
        self.assertTrue(any("406 OK" in i for i in record_issues(rewritten)))
        wrong_count = self.text.replace("12 个只读工具", "4 个只读工具")
        self.assertTrue(any("工具数" in i or "12 个只读工具" in i
                            for i in record_issues(wrong_count)))
        no_snap = self.text.replace("无需快照", "需快照")
        self.assertTrue(any("无需快照" in i for i in record_issues(no_snap)))
        no_e3 = self.text.replace("docs/mcp.md", "mcp 文档")
        self.assertTrue(any("docs/mcp.md" in i for i in record_issues(no_e3)))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_c7.md")


if __name__ == "__main__":
    unittest.main()
