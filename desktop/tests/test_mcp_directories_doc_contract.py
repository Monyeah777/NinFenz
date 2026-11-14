#!/usr/bin/env python3
"""packaging/mcp/DIRECTORIES.md 契约：仓库侧证件可核 / 平台侧状态不冒充判据。

为什么必须有：这是 MCP 第三方目录的逐站投稿说明，混着两类信息——**仓库侧可核**（server.json
的 name/version/packages、npm 包 mcpName、图标真实像素、submissions 逐渠道件、llms-install.md）
与**平台侧状态**（官方注册表最后记录、各站是否收录、当时测到的 302/403/000）。
前者能机检、后者只能联网/浏览器核；不分开就会被读成「已全部上架」或「本仓没准备好」。
本轮补「§现状对照」「§复现与引用口径」并加本判据。

范围：只判本文与 packaging/mcp 资产事实自洽（不发网络请求、不改投稿流程）。
同族判据：test_mcp_packaging.py / test_mcp_manifest.py / test_mcp_doc_contract.py。
契约：复核位、server.json name/version/packages 一致、npm version 与之一致且带 mcpName、
图标 400/512 真实像素、submissions 10 件、llms-install.md 在场、平台侧「未验」标注、复现三命令。
"""
import json
import struct
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOC = ROOT / "packaging" / "mcp" / "DIRECTORIES.md"
BASE = ROOT / "packaging" / "mcp"
SERVER = BASE / "server.json"
NPM = ROOT / "packaging" / "npm" / "package.json"
PLATFORM = ("平台侧未验", "当时快照", "需联网", "需浏览器复核")


def load_text(path: Path = DOC) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"MCP 目录文档不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("MCP 目录文档为空")
    return text


def png_size(path: Path) -> tuple:
    data = path.read_bytes()
    return struct.unpack(">II", data[16:24])


def directories_issues(text: str) -> list:
    issues = []
    if not text.startswith("# 第三方 MCP 目录提交包"):
        issues.append("缺标题「# 第三方 MCP 目录提交包」")
    if "复核（2026-11-14）" not in text:
        issues.append("缺复核位")
    for section in ("## 0 渠道总表", "## 1 通用材料包", "## 现状对照",
                    "## 复现与引用口径"):
        if section not in text:
            issues.append(f"缺段落：{section}")
    server = json.loads(SERVER.read_text(encoding="utf-8"))
    npm = json.loads(NPM.read_text(encoding="utf-8"))
    if server.get("name") != "io.github.Monyeah777/ninfenz":
        issues.append(f"server.json name 已变：{server.get('name')}")
    if server.get("version") != npm.get("version"):
        issues.append("server.json 与 npm 包版本不一致")
    if [p.get("version") for p in server.get("packages") or []] != [server.get("version")]:
        issues.append("server.json packages[].version 与顶层 version 不一致")
    if npm.get("mcpName") != server.get("name"):
        issues.append("npm 包 mcpName 缺失或与 server.json name 不一致")
    if str(server.get("version")) not in text:
        issues.append("正文未写当前版本")
    if "`mcpName`" not in text:
        issues.append("正文未写 npm 包 mcpName 前置")
    if png_size(BASE / "assets" / "icon-400.png") != (400, 400):
        issues.append("icon-400.png 实际像素不是 400x400")
    if png_size(BASE / "assets" / "icon-512.png") != (512, 512):
        issues.append("icon-512.png 实际像素不是 512x512")
    if "**400×400**" not in text or "**512×512**" not in text:
        issues.append("正文未写图标真实像素")
    subs = sorted((BASE / "submissions").glob("*.md"))
    if len(subs) != 10:
        issues.append(f"submissions 件数已变（{len(subs)}）")
    if "**10**" not in text:
        issues.append("正文未写 submissions 10 件")
    if not (ROOT / "llms-install.md").is_file():
        issues.append("仓库根 llms-install.md 不在场")
    for token in PLATFORM:
        if token not in text:
            issues.append(f"缺平台侧标注：{token}")
    if "不进本仓判据" not in text:
        issues.append("缺「平台侧状态不进本仓判据」口径")
    if "TODO" in text:
        issues.append("含 TODO 占位")
    return issues


class McpDirectoriesTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_directories_matches_contract(self):
        self.assertEqual([], directories_issues(self.text), "MCP 目录文档不满足契约")

    def test_assets_live(self):
        server = json.loads(SERVER.read_text(encoding="utf-8"))
        npm = json.loads(NPM.read_text(encoding="utf-8"))
        self.assertEqual(server["version"], npm["version"])
        self.assertEqual(10, len(list((BASE / "submissions").glob("*.md"))))

    def test_contract_catches_mutations(self):
        """变异自证：版本不一致 / 图标像素改错 / 缺平台标注 / 缺判据口径。"""
        bad = self.text.replace("1.0.5", "9.9.9")
        self.assertTrue(any("版本" in i for i in directories_issues(bad)))
        no_px = self.text.replace("**400×400**", "**400×300**")
        self.assertTrue(any("像素" in i for i in directories_issues(no_px)))
        no_platform = self.text.replace("平台侧未验", "平台侧已验")
        self.assertTrue(any("平台侧" in i for i in directories_issues(no_platform)))
        no_rule = self.text.replace("不进本仓判据", "可作本仓判据")
        self.assertTrue(any("判据" in i for i in directories_issues(no_rule)))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_directories.md")


if __name__ == "__main__":
    unittest.main()
