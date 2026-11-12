#!/usr/bin/env python3
"""docs/41_波C_C8 transport 契约：原结论保留 + 现行能力面复评 + 远程/本地口径分离。

为什么必须有：本文是 transport 评估的一次性快照，结论是「暂不做、回冻结」——但后续仓库已落地
**本地 HTTP 面**（nf serve --http，只绑回环 + 纯读端点 + ingress 策略）。若不复评，读者会把
「暂不做」误读成「完全没有 HTTP」，或反过来把回环面误读成「远程 transport 已开放」。本轮补
「评估快照 + 结论复评」双状态、「当时→现行」现状口径、复现命令，并把「远程未实现 / 本地已落地 /
E3 仍待回填」立成机检断言。

范围：只判本文与现行 MCP/HTTP 面事实自洽（不改原评估结论）。同族判据：
test_c7_record_contract.py（C7 工具面）/ test_mcp_runtime.py / test_mcp_ingress.py（闸门）/
test_doc_reachability.py / docs/mcp.md（E3 真源）。
契约：双状态横幅、五段按序、原结论与回冻结条件保留、现行口径（nf serve --http 回环 + 纯读 +
ingress nf-ingress-policy/1）、工具/提示数与 TOOL_DEFS/PROMPT_DEFS 一致、远程通道未实现、
E3 待回填指向 docs/mcp.md、33_ 基线已归档事实。
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "desktop" / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import mcp_runtime as mcp  # noqa: E402

DOC = ROOT / "docs" / "41_波C_C8_transport评估.md"
MCP_DOC = ROOT / "docs" / "mcp.md"
SECTIONS = ("## 一、现状与基线", "## 二、扩展差距评估", "## 三、试点结论",
            "## 结论复评", "## 复现与引用口径")
KEEP = ("暂不做（回冻结）", "回冻结条件", "streamable HTTP", "SSE")
CURRENT = ("nf serve --http", "127.0.0.1", "/api/health", "/api/verify", "/api/check",
           "nf-ingress-policy/1", "mcp_ingress.py", "12 只读 tools", "1 prompt")
REMOTE_NOT_DONE = ("公网/远程 streamable HTTP 与 SSE 仍未实现", "远程客户端装载")


def load_text(path: Path = DOC) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"transport 评估不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("transport 评估为空")
    return text


def c8_issues(text: str) -> list:
    issues = []
    if not text.startswith("# 41 波C C8"):
        issues.append("缺标题「# 41 波C C8 · MCP transport 扩展评估」")
    for marker in ("评估快照", "结论复评"):
        if marker not in text:
            issues.append(f"缺状态口径：{marker}")
    positions = [text.find(s) for s in SECTIONS]
    for section, pos in zip(SECTIONS, positions, strict=True):
        if pos < 0:
            issues.append(f"缺段：{section}")
    if all(p >= 0 for p in positions) and positions != sorted(positions):
        issues.append("五段顺序不对")
    for marker in KEEP:
        if marker not in text:
            issues.append(f"原评估口径丢失：{marker}")
    for marker in CURRENT:
        if marker not in text:
            issues.append(f"现行口径缺要素：{marker}")
    for marker in REMOTE_NOT_DONE:
        if marker not in text:
            issues.append(f"远程/本地口径未分离：{marker}")
    nf = (ROOT / "scripts" / "nf.py").read_text(encoding="utf-8")
    for flag in ("--http", "--port", "--ingress-policy"):
        if '"' + flag + '"' not in nf:
            issues.append(f"CLI 缺 serve 参数：{flag}")
    if not (ROOT / "desktop" / "src" / "core" / "mcp_ingress.py").is_file():
        issues.append("缺闸门实现：mcp_ingress.py")
    if not (ROOT / "desktop" / "tests" / "test_mcp_ingress.py").is_file():
        issues.append("缺闸门判据：test_mcp_ingress.py")
    if len(mcp.TOOL_DEFS) != 12:
        issues.append(f"TOOL_DEFS 工具数已变（{len(mcp.TOOL_DEFS)}）：现行口径需复核")
    if "12 只读 tools" not in text:
        issues.append("未写当前只读工具数（12）")
    if "1 prompt" not in text:
        issues.append("未写 prompt 数（1）")
    mcp_doc = MCP_DOC.read_text(encoding="utf-8")
    if "回填" not in mcp_doc:
        issues.append("docs/mcp.md 缺 E3 回填状态句")
    if "docs/mcp.md" not in text:
        issues.append("E3 口径未指向 docs/mcp.md")
    if (ROOT / "33_v2.2.0_A5-MCP规范差距核查报告.md").exists():
        issues.append("33_ 基线仍在公开仓，与「本地归档」叙述矛盾")
    if "本地归档" not in text:
        issues.append("缺「33_ 基线已本地归档」标注")
    if "TODO" in text or "待补" in text:
        issues.append("含 TODO/待补 占位")
    return issues


class C8TransportContractTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_transport_record_matches_contract(self):
        self.assertEqual([], c8_issues(self.text), "transport 评估不满足契约")

    def test_local_http_face_exists(self):
        nf = (ROOT / "scripts" / "nf.py").read_text(encoding="utf-8")
        self.assertIn('"--http"', nf)
        self.assertTrue((ROOT / "desktop" / "src" / "core" / "mcp_ingress.py").is_file())
        self.assertIn("nf-ingress-policy/1", self.text)

    def test_remote_transport_still_not_done(self):
        self.assertIn("公网/远程 streamable HTTP 与 SSE 仍未实现", self.text)
        self.assertIn("暂不做（回冻结）", self.text)

    def test_contract_catches_mutations(self):
        """变异自证：去复评 / 去原结论 / 误称远程已实现 / 去回环口径 / 工具数漂移 / 缺 E3。"""
        no_review = self.text.replace("## 结论复评（2026-11-13）", "## 备注")
        self.assertTrue(any("结论复评" in i for i in c8_issues(no_review)))
        no_decision = self.text.replace("暂不做（回冻结）", "待定")
        self.assertTrue(any("暂不做" in i for i in c8_issues(no_decision)))
        wrong_remote = self.text.replace("公网/远程 streamable HTTP 与 SSE 仍未实现",
                                         "公网/远程 streamable HTTP 与 SSE 已实现")
        self.assertTrue(any("仍未实现" in i for i in c8_issues(wrong_remote)))
        no_loop = self.text.replace("nf serve --http", "nf serve")
        self.assertTrue(any("--http" in i for i in c8_issues(no_loop)))
        wrong_tools = self.text.replace("12 只读 tools", "4 只读 tools")
        self.assertTrue(any("12 只读 tools" in i or "工具数" in i
                            for i in c8_issues(wrong_tools)))
        no_e3 = self.text.replace("docs/mcp.md", "mcp 文档")
        self.assertTrue(any("docs/mcp.md" in i for i in c8_issues(no_e3)))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_c8.md")


if __name__ == "__main__":
    unittest.main()
