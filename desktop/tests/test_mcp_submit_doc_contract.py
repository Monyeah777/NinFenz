#!/usr/bin/env python3
"""packaging/mcp/SUBMIT.md 契约：三处版本同值 / 自检期望可跑 / 平台侧不冒充判据。

为什么必须有：这份 428 行教程是「怎么把 server 提到官方 Registry」的唯一操作件，最容易漂的三件事是：
① 三处版本（npm / server.json 顶层 / packages[0]）不同值 → Registry 去查旧版本报 missing mcpName；
② 自检区写的期望（MCP 测试 / conformance 27/27）没有判据盯着；
③ 把「Registry 已收录某版本」写成仓库事实。本轮补「§现状对照」「§复现与引用口径」并加本判据。

范围：只判本文与打包资产/运行面/CLI 事实自洽（不发网络请求）。
同族判据：test_mcp_packaging.py / test_mcp_runtime.py / test_mcp_directories_doc_contract.py。
契约：复核位、三处版本同值、mcpName 相等、schema 2025-12-11、12 工具 + 1 prompt、
conformance 27/27 在文、平台侧「未验」标注、复现命令逐条可跑。
"""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "desktop" / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import mcp_runtime as mcp  # noqa: E402

DOC = ROOT / "packaging" / "mcp" / "SUBMIT.md"
NPM = ROOT / "packaging" / "npm" / "package.json"
SERVER = ROOT / "packaging" / "mcp" / "server.json"
PLATFORM = ("平台侧未验", "不进本仓判据")


def load_text(path: Path = DOC) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"MCP 投稿教程不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("MCP 投稿教程为空")
    return text


def submit_issues(text: str) -> list:
    issues = []
    if not text.startswith("# NinFenz Content Gate · 三个目录的提交教程"):
        issues.append("缺标题「# NinFenz Content Gate · 三个目录的提交教程」")
    if "复核（2026-11-14）" not in text:
        issues.append("缺复核位")
    for section in ("## 0. 先看当前状态", "## 1. GitHub 官方 MCP Registry",
                    "## 2. Awesome MCP Servers", "## 3. AgentSkillsHub",
                    "## 现状对照", "## 复现与引用口径"):
        if section not in text:
            issues.append(f"缺段落：{section}")
    npm = json.loads(NPM.read_text(encoding="utf-8"))
    server = json.loads(SERVER.read_text(encoding="utf-8"))
    versions = {npm.get("version"), server.get("version")}
    versions |= {p.get("version") for p in server.get("packages") or []}
    if len(versions) != 1:
        issues.append(f"三处版本不同值：{sorted(versions)}")
    ver = str(npm.get("version"))
    if ver not in text:
        issues.append(f"正文未写当前版本 {ver}")
    if npm.get("mcpName") != server.get("name"):
        issues.append("mcpName 与 server.json name 不一致")
    if "2025-12-11" not in text:
        issues.append("正文未写 server.json schema 版本")
    if len(mcp.TOOL_DEFS) != 12 or len(mcp.PROMPT_DEFS) != 1:
        issues.append("工具面已变（应为 12 + 1）")
    if "**12 个只读工具 + 1 个 prompt**" not in text and "12 只读工具 + 1 prompt" not in text:
        issues.append("正文未写 12 工具 + 1 prompt")
    if "27/27" not in text:
        issues.append("正文未写 conformance 27/27 期望")
    for token in PLATFORM:
        if token not in text:
            issues.append(f"缺平台侧标注：{token}")
    for cmd in ("python -m pytest desktop/tests/test_mcp_packaging.py",
                "python scripts/nf.py conformance"):
        if cmd not in text:
            issues.append(f"复现口径缺命令：{cmd}")
    if "missing 'mcpName' field" not in text:
        issues.append("缺「只改一处会报 missing mcpName」历史坑")
    if "TODO" in text:
        issues.append("含 TODO 占位")
    return issues


class McpSubmitTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_submit_matches_contract(self):
        self.assertEqual([], submit_issues(self.text), "MCP 投稿教程不满足契约")

    def test_versions_live(self):
        npm = json.loads(NPM.read_text(encoding="utf-8"))
        server = json.loads(SERVER.read_text(encoding="utf-8"))
        self.assertEqual(npm["version"], server["version"])
        self.assertEqual([server["version"]], [p["version"] for p in server["packages"]])

    def test_contract_catches_mutations(self):
        """变异自证：版本回退 / 工具面漂移 / 缺平台标注 / 缺历史坑。"""
        npm = json.loads(NPM.read_text(encoding="utf-8"))
        ver = str(npm["version"])
        bad = self.text.replace(ver, "9.9.9")
        self.assertTrue(any("版本" in i for i in submit_issues(bad)))
        no_tools = self.text.replace("12 只读工具 + 1 prompt", "10 工具")
        no_tools = no_tools.replace("**12 个只读工具 + 1 个 prompt**", "**10 工具**")
        self.assertTrue(any("12 工具" in i for i in submit_issues(no_tools)))
        no_platform = self.text.replace("平台侧未验", "平台侧已验")
        self.assertTrue(any("平台侧" in i for i in submit_issues(no_platform)))
        no_pit = self.text.replace("missing 'mcpName' field", "报错")
        self.assertTrue(any("mcpName" in i for i in submit_issues(no_pit)))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_submit.md")


if __name__ == "__main__":
    unittest.main()
