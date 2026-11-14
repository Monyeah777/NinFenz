#!/usr/bin/env python3
"""AI_ROUTING 路由契约：入口第二跳必须「档位可自测、通道有落点、override 同源、失败即停」。

为什么必须有：AI_ROUTING 是 AI 入口链的选线层，但此前零判据——三档只有一行「能力边界」没有
判定证据（A 线是否真能执行、B1 是否真读到 raw 全靠自述），B2 冻结卡只提了文件名没写「已免除」
的来源，DRIVER OVERRIDE 与 protocol/driver.json 的 fallback / 工具 / fail-closed 关键词也没有
任何对账。照着走会出现：拿不准档位硬选高挡、MCP 不可用时反复重试、把已免除通道当主路径。

范围：只判本文件的**可执行性与同源事实**（不改协议口径）。同族判据：
test_agent_start_contract（入口第一跳）/ test_doc_reachability（全仓路径与命令）/
test_prose_lint（命令面）。契约：九段结构、三档判定证据、落点与验收列、driver.json 同源、悬空零。
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

ROUTING = ROOT / "docs" / "agent" / "AI_ROUTING.md"
DRIVER = ROOT / "protocol" / "driver.json"

#: 九段结构（缺一段即某一类读者走到断点）
REQUIRED_SECTIONS = ("## 一、先自测", "## 二、档位", "## 三、B1 完整装配",
                     "## 四、产出验收", "## 五、停止条件", "## 六、云端图书馆导购",
                     "## 七、模型与通道参考", "## 八、取件基底", "## 九、下一步")
#: 三档判定 + override 纪律 + fail-closed 的必备要素
REQUIRED_MARKERS = ("DRIVER OVERRIDE", "spec_list", "registry_search", "不得回退",
                    "停止", "B1", "B2", "已免除", "paste_card.md", "不编造", "档位")
#: 入口链与落点必须指到的件（读不到 = 选线断链）
REQUIRED_LINKS = ("docs/agent/AGENT_START.md", "docs/agent/agent_组装指令包_v0.2.md",
                  "docs/paste_card.md", "docs/mcp.md", "docs/agent/ROUTES.md",
                  "library/ALIAS.md", "docs/meta/DEEP_DIVE.md")

_BACKTICK = re.compile(r"`([^`\n]+)`")
_LINK = re.compile(r"\]\(([^)\s]+)\)")
_NF_CMD = re.compile(r"\bnf(?:\.py)?\s+([a-z][a-z0-9-]*)")
_PATH_SHAPE = re.compile(r"^[A-Za-z0-9_./\-\u4e00-\u9fff]+$")
_PLACEHOLDER = ("*", "\u2026", "<", ">", "...", "::")
_FILEY = (".md", ".json", ".py", ".yaml", ".yml", ".txt", ".sh", ".cmd")


def load_text(path: Path = ROUTING) -> str:
    """读路由件（缺失 / 空件显式报错，不静默跳过）。"""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"AI_ROUTING 不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("AI_ROUTING 为空")
    return text


def load_driver(path: Path = DRIVER) -> dict:
    """读机读真源（缺件即抛错，不静默降级）。"""
    return json.loads(path.read_text(encoding="utf-8"))


def looks_like_path(tok: str) -> bool:
    """仓库相对路径形状（与 test_doc_reachability 同一辨别口径）。"""
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


def driver_issues(text: str, driver: dict) -> list:
    """DRIVER OVERRIDE 与 protocol/driver.json 的双向同源问题（纯函数，便于变异）。"""
    issues = []
    workflow = (driver.get("workflows") or {}).get("routing") or {}
    if not workflow:
        issues.append("driver.json 缺 workflows.routing 映射（OVERRIDE 无真源）")
    fallback = str(workflow.get("fallback") or "")
    if fallback != "docs/agent/AI_ROUTING.md":
        issues.append(f"driver.json routing.fallback 未指向本文件：{fallback!r}")
    tools = list(workflow.get("mcp_tools") or [])
    if not tools:
        issues.append("driver.json routing.mcp_tools 为空（MCP 通道无工具面）")
    for tool in tools:
        if tool not in text:
            issues.append(f"DRIVER OVERRIDE 未点名 driver 声明的工具：{tool}")
    docs = list(driver.get("documents") or [])
    mapped = [d for d in docs if str(d.get("path") or "") == "docs/agent/AI_ROUTING.md"]
    if not mapped:
        issues.append("driver.json documents 未登记本文件")
    elif str(mapped[0].get("workflow") or "") != "routing":
        issues.append(f"driver.json 登记的工作流不是 routing：{mapped[0].get('workflow')!r}")
    keywords = list((driver.get("fail_closed") or {}).get("marker_keywords") or [])
    if not keywords:
        issues.append("driver.json fail_closed.marker_keywords 为空（fail-closed 无判据词）")
    for keyword in keywords:
        if keyword not in text:
            issues.append(f"OVERRIDE 段未写 driver 约定的 fail-closed 词：{keyword}")
    return issues


def routing_issues(text: str, driver: dict) -> list:
    """路由契约问题列表（纯函数，便于变异自证）。"""
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
    issues.extend(driver_issues(text, driver))
    return issues


class AiRoutingContractTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()
        self.driver = load_driver()

    def test_routing_matches_contract(self):
        self.assertEqual([], routing_issues(self.text, self.driver), "AI_ROUTING 不满足路由契约")

    def test_references_resolve(self):
        self.assertEqual([], dangling(self.text), "AI_ROUTING 有悬空引用")

    def test_required_links_are_reachable(self):
        for target in REQUIRED_LINKS:
            self.assertTrue((ROOT / target).is_file(), f"入口链落点不在场：{target}")

    def test_driver_face_is_same_source(self):
        """routing 工作流、工具面、fallback 与 fail-closed 词必须与 driver.json 对得上。"""
        workflow = self.driver["workflows"]["routing"]
        self.assertEqual("docs/agent/AI_ROUTING.md", workflow["fallback"])
        self.assertIn("spec_list", workflow["mcp_tools"])
        self.assertIn("registry_search", workflow["mcp_tools"])

    def test_contract_catches_broken_routing(self):
        """变异自证：删 override / 删 B2 免除 / 悬空路径 / 假命令 / 真源漂移都必须报。"""
        no_override = self.text.replace("DRIVER OVERRIDE", "普通说明")
        self.assertTrue(any("DRIVER OVERRIDE" in i
                            for i in routing_issues(no_override, self.driver)),
                        "删掉 DRIVER OVERRIDE 必须报")
        no_b2 = self.text.replace("已免除", "可用")
        self.assertTrue(any("已免除" in i for i in routing_issues(no_b2, self.driver)),
                        "删掉 B2 已免除必须报")
        bad_path = self.text + "\n参考 " + chr(96) + "docs/nope.md" + chr(96) + "。\n"
        self.assertTrue(any("docs/nope.md" in i
                            for i in routing_issues(bad_path, self.driver)),
                        "悬空路径必须报")
        bad_cmd = self.text + "\n跑 " + chr(96) + "nf doctorr" + chr(96) + "。\n"
        self.assertTrue(any("doctorr" in i for i in routing_issues(bad_cmd, self.driver)),
                        "不存在的子命令必须报")
        drifted = json.loads(json.dumps(self.driver))
        drifted["workflows"]["routing"]["fallback"] = "docs/agent/别的文件.md"
        self.assertTrue(any("fallback" in i for i in routing_issues(self.text, drifted)),
                        "driver fallback 漂移必须报")
        no_keyword = json.loads(json.dumps(self.driver))
        no_keyword["fail_closed"]["marker_keywords"] = []
        self.assertTrue(any("marker_keywords" in i
                            for i in routing_issues(self.text, no_keyword)),
                        "fail-closed 判据词被清空必须报")
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_ai_routing.md")


if __name__ == "__main__":
    unittest.main()
