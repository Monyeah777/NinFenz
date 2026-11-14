#!/usr/bin/env python3
"""AGENT_START 入口契约：装配师第一跳须「分流可执行、路径可达、工具面同源、失败即停」。

为什么必须有：AGENT_START 是任一 AI 拿到仓库后的操作第一跳，但此前零判据——它少了
「按能力选档后的执行动作」，B2 档仍写着向使用者要原文（而 B2 已于 2026-09-07 免除、
改为自取 `docs/paste_card.md`），也没有与 `protocol/driver.json` 的 DRIVER OVERRIDE 对齐。
照着旧文走会：在 MCP 可用时不走工具面、在纯粘贴档走已免除的通道、读完仍不知道第一步跑什么。

范围：只判本文件的**可执行性与同源事实**（不改任何协议口径）。同族判据：
test_agents_contract（开发者第一跳）/ test_doc_reachability（全仓路径与命令）/
test_prose_lint（命令面）。
契约：七段齐全、三档能力边界在场、硬断言与停止条件在场、引用路径可解析、`nf <子命令>` 真实、
提到的 MCP 工具/提示词均在 `protocol/driver.json` 声明。
"""
import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "desktop" / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import prose_lint  # noqa: E402

ENTRY = ROOT / "docs" / "agent" / "AGENT_START.md"
DRIVER = ROOT / "protocol" / "driver.json"

#: 七段结构（缺一段即某一类读者走到断点）
REQUIRED_SECTIONS = ("## 一、先分流", "## 二、按能力选档", "## 三、开工三步",
                     "## 四、硬断言", "## 五、出口自检", "## 六、停止条件",
                     "## 七、入口文件地图")
#: 三档能力边界 + 硬断言 + fail-closed 的必备要素
REQUIRED_MARKERS = ("B1", "B2", "已免除", "DRIVER OVERRIDE", "不得回退",
                    "不得假装读过仓库", "先读后写", "不得声称「已入库」",
                    "##7. 自检清单", "--check")
#: 入口链必须指到的落点（读不到 = 分流断链）
REQUIRED_LINKS = ("docs/agent/AI_ROUTING.md", "docs/agent/agent_组装指令包_v0.2.md",
                  "docs/meta/DEEP_DIVE.md", "docs/agent/ROUTES.md",
                  "docs/paste_card.md", "docs/mcp.md")

_BACKTICK = re.compile(r"`([^`\n]+)`")
_LINK = re.compile(r"\]\(([^)\s]+)\)")
_NF_CMD = re.compile(r"\bnf(?:\.py)?\s+([a-z][a-z0-9-]*)")
_PATH_SHAPE = re.compile(r"^[A-Za-z0-9_./\-\u4e00-\u9fff]+$")
_PLACEHOLDER = ("*", "\u2026", "<", ">", "...", "::")
_FILEY = (".md", ".json", ".py", ".yaml", ".yml", ".txt", ".sh", ".cmd")
#: 反引号里这些形状的标识符当作 MCP 工具/提示词（必须能在 driver.json 里找到）
_TOOL_SUFFIX = ("_read", "_list", "_search", "_guide")


def load_text(path: Path = ENTRY) -> str:
    """读入口件（缺失 / 空件显式报错，不静默跳过）。"""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"AGENT_START 不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("AGENT_START 为空")
    return text


def driver_face(path: Path = DRIVER) -> dict:
    """→ {'tools': [...], 'prompts': [...]}（机读真源；缺件即抛错）。"""
    doc = json.loads(path.read_text(encoding="utf-8"))
    bindings = doc.get("bindings") or {}
    return {"tools": list(bindings.get("mcp.tools") or []),
            "prompts": list(bindings.get("mcp.prompts") or [])}


def looks_like_path(tok: str) -> bool:
    """仓库相对路径形状（与 test_doc_reachability 同一辨别口径，避免把普通词当路径）。"""
    s = tok.strip()
    if not s or " " in s or "://" in s or s.startswith(("-", "/", "~")):
        return False
    if any(mark in s for mark in _PLACEHOLDER):
        return False
    if not (s.endswith(_FILEY) or "/" in s):
        return False
    return s.split("/", 1)[0] in {p.name for p in ROOT.iterdir()}


def dangling(text: str) -> list:
    """反引号路径 + Markdown 相对链接中不存在的仓内引用。"""
    bad = []
    for match in _BACKTICK.finditer(text):
        tok = match.group(1).strip()
        if not looks_like_path(tok):
            continue
        cand = tok.split("::", 1)[0]
        if not (ROOT / cand).exists():
            bad.append(cand)
    for match in _LINK.finditer(text):
        target = match.group(1).strip()
        if target.startswith(("http://", "https://", "#", "mailto:")):
            continue
        rel = target.split("#")[0]
        if rel and not (ROOT / rel).exists():
            bad.append(target)
    return bad


def mentioned_tools(text: str) -> list:
    """反引号里形如 MCP 工具/提示词的标识符。"""
    out = []
    for match in _BACKTICK.finditer(text):
        tok = match.group(1).strip()
        if re.fullmatch(r"[a-z][a-z0-9_]+", tok) and tok.endswith(_TOOL_SUFFIX):
            out.append(tok)
    return out


def agent_start_issues(text: str) -> list:
    """入口契约问题列表（纯函数，便于变异自证）。"""
    issues = []
    for section in REQUIRED_SECTIONS:
        if section not in text:
            issues.append(f"缺段落：{section}")
    for marker in REQUIRED_MARKERS:
        if marker not in text:
            issues.append(f"缺要素：{marker}")
    for target in REQUIRED_LINKS:
        if target not in text:
            issues.append(f"入口链缺落点：{target}")
    for target in dangling(text):
        issues.append(f"引用的仓内路径不存在：{target}（悬空引用）")
    valid = prose_lint.cli_commands(str(ROOT))
    if len(valid) < 40:
        issues.append(f"CLI 命令面解析失败（{len(valid)} 条），判据可能已失效")
    for cmd in _NF_CMD.findall(text):
        if cmd not in valid:
            issues.append(f"引用了不存在的 nf 子命令：nf {cmd}")
    face = driver_face()
    declared = set(face["tools"]) | set(face["prompts"])
    if len(declared) < 5:
        issues.append(f"driver.json 工具/提示词面塌缩（{len(declared)} 条），判据可能已失效")
    tools = mentioned_tools(text)
    if not tools:
        issues.append("未点名任何 MCP 工具/提示词（DRIVER OVERRIDE 不可执行）")
    for tool in tools:
        if tool not in declared:
            issues.append(f"MCP 工具/提示词未在 protocol/driver.json 声明：{tool}")
    return issues


class AgentStartContractTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_entry_matches_contract(self):
        self.assertEqual([], agent_start_issues(self.text), "AGENT_START 不满足入口契约")

    def test_references_resolve(self):
        self.assertEqual([], dangling(self.text), "AGENT_START 有悬空引用")

    def test_required_links_are_reachable(self):
        for target in REQUIRED_LINKS:
            self.assertTrue((ROOT / target).is_file(), f"入口链落点不在场：{target}")

    def test_driver_override_is_same_source(self):
        """DRIVER OVERRIDE 点名的工具/提示词必须在 driver.json 里，双向同源。"""
        face = driver_face()
        self.assertIn("assemble_guide", face["prompts"])
        for tool in ("module_read", "pipeline_read", "asset_read"):
            self.assertIn(tool, face["tools"])
        for tool in ("spec_list", "registry_search"):
            self.assertIn(tool, face["tools"])

    def test_contract_catches_broken_entry(self):
        """变异自证：删段 / 删 B2 免除 / 悬空路径 / 假命令 / 假工具都必须报。"""
        no_stop = self.text.replace("## 六、停止条件", "## 其他")
        self.assertTrue(any("六、停止条件" in i for i in agent_start_issues(no_stop)),
                        "删掉停止条件必须报")
        no_b2 = self.text.replace("已免除", "可用")
        self.assertTrue(any("已免除" in i for i in agent_start_issues(no_b2)),
                        "删掉 B2 已免除必须报")
        bad_path = self.text + "\n参考 " + chr(96) + "docs/nope.md" + chr(96) + "。\n"
        self.assertTrue(any("docs/nope.md" in i for i in agent_start_issues(bad_path)),
                        "悬空路径必须报")
        bad_cmd = self.text + "\n跑 " + chr(96) + "nf doctorr" + chr(96) + "。\n"
        self.assertTrue(any("doctorr" in i for i in agent_start_issues(bad_cmd)),
                        "不存在的子命令必须报")
        bad_tool = self.text + "\n另用 " + chr(96) + "no_such_tool_read" + chr(96) + "。\n"
        self.assertTrue(any("no_such_tool_read" in i for i in agent_start_issues(bad_tool)),
                        "driver.json 未声明的工具必须报")
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_agent_start.md")


if __name__ == "__main__":
    unittest.main()
