#!/usr/bin/env python3
"""ai-menu 菜单契约：一贴就发菜单的 B1 总闸门必须「菜单单源、事实同源、失败即停」。

为什么必须有：ai-menu 是免费客户端 AI 的入口闸门——菜单 8 行在「few-shot 示例」与
「复述源表」两处各写一遍，改一处不改另一处，AI 就会照旧菜单报菜名；而菜单里的事实句
（九层口径 / M22 名称与挂载 / 样本节号 / Y5 记录位 / 扩展题材范式）全是手抄，没有一份
对得上真源。实测本轮修掉 5 处：三端仓库却只列两端、九层管线写成 P00–P80（管线 id 与层位
id 混淆）、样本节号少点号、扩展题材指向已移出 README 的段、Y5 记录位缺 results/ 前缀。

范围：只判本文件的**自洽与跨源事实**（不改菜单机制）。同族判据：
test_ai_routing_contract（选线）/ test_routes_contract（导购）/ test_agent_start_contract
（装配开场）/ test_doc_reachability（全仓路径与命令）。
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

MENU = ROOT / "docs" / "ai-menu.md"
DRIVER = ROOT / "protocol" / "driver.json"
REGISTRY = ROOT / "02_联动注册表.md"
P00 = ROOT / "03_管线库" / "P00_通用文档生成管线.md"
SAMPLE = ROOT / "docs" / "完整版样本_西幻生存流P03.md"
TICK = chr(96)

REQUIRED_MARKERS = ("DRIVER OVERRIDE", "不得回退", "【执行协议", "复述菜单",
                    "回复编号 0–7", "行为纪律", "执行前自检", "停止条件",
                    "不跳步", "不编造", "P01", "P90", "九层装配流",
                    "M22", "P30", "community/模板制作指令包.md",
                    "results/docs_external-validation-v2.7.md")
REQUIRED_LINKS = ("docs/agent/AGENT_START.md", "docs/agent/ROUTES.md",
                  "docs/完整版样本_西幻生存流P03.md", "library/NF-1.md",
                  "library/INDEX.md", "library/ALIAS.md",
                  "07_官方核心出厂与社区预设导航.md", "02_联动注册表.md",
                  "01_核心协议.md", "community/模板制作指令包.md",
                  "docs/domain-packs.md", "results/docs_external-validation-v2.7.md")
#: 旧口径（出现即说明事实回退）
STALE_PHRASES = ("九层管线", "P00–P80 是装配流水线", "三端仓库", "README「扩展新领域三步」")

_BACKTICK = re.compile(TICK + "([^" + TICK + "\n]+)" + TICK)
_NF_CMD = re.compile(r"\bnf(?:\.py)?\s+([a-z][a-z0-9-]*)")
_PLACEHOLDER = ("*", "\u2026", "<", ">", "...", "::", "{", "}", "XXXX")
_FILEY = (".md", ".json", ".py", ".yaml", ".yml", ".txt", ".sh", ".cmd")
_MENU_ROW = re.compile(r"^\| \*\*([0-7])\*\* \| ([^|]+?) \| ([^|]+?) \|$", re.M)


def load_text(path: Path = MENU) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"ai-menu 不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("ai-menu 为空")
    return text


def looks_like_path(tok: str) -> bool:
    s = tok.strip()
    if not s or " " in s or "://" in s or s.startswith(("-", "/", "~")):
        return False
    if any(mark in s for mark in _PLACEHOLDER):
        return False
    if not (s.endswith(_FILEY) or "/" in s):
        return False
    return s.split("/", 1)[0] in {p.name for p in ROOT.iterdir()}


def dangling(text: str) -> list:
    bad = []
    for match in _BACKTICK.finditer(text):
        tok = match.group(1).strip()
        if not looks_like_path(tok):
            continue
        cand = tok.split("::", 1)[0]
        if not (ROOT / cand).exists():
            bad.append(cand)
    return bad


def menu_rows(text: str) -> list:
    """菜单行三连（编号, 菜名, 一句话）；同一份契约里应出现两遍（few-shot + 源表）。"""
    return [(m.group(1), m.group(2).strip(), m.group(3).strip())
            for m in _MENU_ROW.finditer(text)]


def stages_from_p00(text: str) -> list:
    """P00 声明的九层名（权威真源）。"""
    match = re.search("“([^”]*→[^”]*)”", text)
    if not match:
        return []
    return [part.strip() for part in match.group(1).split("→") if part.strip()]


def m22_name(registry_text: str) -> str:
    match = re.search(r"\|\s*事件:M22\s*\|\s*([^|]+?)\s*\|", registry_text)
    return match.group(1).strip() if match else ""


def sample_heading(sample_text: str) -> str:
    match = re.search(r"^## 6\. 装载指引.*$", sample_text, re.M)
    return match.group(0).strip() if match else ""


def menu_issues(text: str) -> list:
    issues = []
    for marker in REQUIRED_MARKERS:
        if marker not in text:
            issues.append(f"缺要素：{marker}")
    for link in REQUIRED_LINKS:
        if link not in text:
            issues.append(f"菜单缺落点：{link}")
    for phrase in STALE_PHRASES:
        if phrase in text:
            issues.append(f"仍写着旧口径：{phrase}")
    rows = menu_rows(text)
    if len(rows) != 16:
        issues.append(f"菜单行不是两遍各 8 行（实测 {len(rows)} 行）")
    else:
        if [r[0] for r in rows[:8]] != [str(i) for i in range(8)]:
            issues.append("few-shot 菜单编号不是 0–7")
        if rows[:8] != rows[8:]:
            issues.append("few-shot 菜单与复述源表不一致（改一处漏一处）")
    for target in dangling(text):
        issues.append(f"引用的仓内路径不存在：{target}（悬空引用）")
    valid = prose_lint.cli_commands(str(ROOT))
    if len(valid) < 40:
        issues.append(f"CLI 命令面解析失败（{len(valid)} 条），判据可能已失效")
    for cmd in _NF_CMD.findall(text):
        if cmd not in valid:
            issues.append(f"引用了不存在的 nf 子命令：nf {cmd}")
    driver = json.loads(DRIVER.read_text(encoding="utf-8"))
    workflow = (driver.get("workflows") or {}).get("menu") or {}
    if workflow.get("fallback") != "docs/ai-menu.md":
        issues.append(f"driver.json menu.fallback 未指向本文件：{workflow.get('fallback')!r}")
    if workflow.get("mcp_prompt") and workflow["mcp_prompt"] not in text:
        issues.append(f"OVERRIDE 未点名 driver 声明的提示词：{workflow['mcp_prompt']}")
    for tool in workflow.get("mcp_tools") or []:
        if tool not in text:
            issues.append(f"OVERRIDE 未点名 driver 声明的工具：{tool}")
    keywords = list((driver.get("fail_closed") or {}).get("marker_keywords") or [])
    if not keywords:
        issues.append("driver.json fail_closed.marker_keywords 为空")
    for keyword in keywords:
        if keyword not in text:
            issues.append(f"未写 driver 约定的 fail-closed 词：{keyword}")
    return issues


def fact_issues(text: str) -> list:
    """菜单里手抄的事实句与真源逐条对账（纯函数，便于变异）。"""
    issues = []
    stages = stages_from_p00(P00.read_text(encoding="utf-8"))
    if len(stages) < 9:
        issues.append(f"P00 九层名解析失败（{len(stages)} 层）")
    for stage in stages:
        if stage not in text:
            issues.append(f"协议速览缺九层名：{stage}")
    name = m22_name(REGISTRY.read_text(encoding="utf-8"))
    if not name:
        issues.append("02 注册表里解析不到 事件:M22 名称")
    elif f"M22 {name}" not in text:
        issues.append(f"菜单里的 M22 名称与注册表不一致：应为 M22 {name}")
    heading = sample_heading(SAMPLE.read_text(encoding="utf-8"))
    if not heading:
        issues.append("样本里解析不到 ## 6. 装载指引 标题")
    elif heading not in text:
        issues.append(f"菜单写的样本节号与样本不一致：应为 {heading}")
    if not (ROOT / "results/docs_external-validation-v2.7.md").is_file():
        issues.append("Y5 记录位不在场：results/docs_external-validation-v2.7.md")
    if not (ROOT / "community/模板制作指令包.md").is_file():
        issues.append("扩展题材范式件不在场：community/模板制作指令包.md")
    for version in ("v0.1", "v0.2", "v0.3"):
        if version not in text:
            issues.append(f"版本史缺条目：{version}")
    return issues


class AiMenuContractTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_menu_matches_contract(self):
        self.assertEqual([], menu_issues(self.text), "ai-menu 不满足菜单契约")

    def test_facts_match_sources(self):
        self.assertEqual([], fact_issues(self.text), "菜单事实句与真源不一致")

    def test_menu_rows_are_single_source(self):
        rows = menu_rows(self.text)
        self.assertEqual(16, len(rows), "菜单应两遍各 8 行")
        self.assertEqual(rows[:8], rows[8:], "few-shot 与复述源表必须逐字一致")

    def test_contract_catches_broken_menu(self):
        """变异自证：菜单错行 / M22 名称漂移 / 旧口径回潮 / 删 override / 悬空路径 / 假命令。"""
        broken_row = self.text.replace("| **7** | 复测回填 |", "| 7 | 复测回填 |", 1)
        self.assertTrue(any("两遍" in i for i in menu_issues(broken_row)))
        drifted = self.text.replace("M22 事件编排挂 P30", "M22 事件叙事挂 P30")
        self.assertTrue(any("M22" in i for i in fact_issues(drifted)))
        stale = self.text + "\n旧口径：九层管线。\n"
        self.assertTrue(any("旧口径" in i for i in menu_issues(stale)))
        no_override = self.text.replace("DRIVER OVERRIDE", "普通说明")
        self.assertTrue(any("DRIVER OVERRIDE" in i for i in menu_issues(no_override)))
        bad_path = self.text + "\n参考 " + TICK + "docs/nope.md" + TICK + "。\n"
        self.assertTrue(any("docs/nope.md" in i for i in menu_issues(bad_path)))
        bad_cmd = self.text + "\n跑 " + TICK + "nf doctorr" + TICK + "。\n"
        self.assertTrue(any("doctorr" in i for i in menu_issues(bad_cmd)))
        no_stop = self.text.replace("停止条件", "注意事项")
        self.assertTrue(any("停止条件" in i for i in menu_issues(no_stop)))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_ai_menu.md")


if __name__ == "__main__":
    unittest.main()
