#!/usr/bin/env python3
"""DEEP_DIVE 理解层契约：心智模型必须「自足、可核、能自检」。

为什么必须有：DEEP_DIVE 是 AI 入口链的理解层，但此前零判据——它 §7 自检十问里的第 3 问
「什么是三正交」在全文没有定义（三正交的权威定义在 01 §5 I1），照文自检的人只能猜；五维
纵深 / 内部法官链 / 零编造等口径与 STRATEGY、01 的对应关系也没有任何对账。理解层一旦漂移，
读者会带着错的模型去操作，而所有静态判据都不会红。

范围：只判本文件的**自足性与跨源一致**（不改协议口径）。同族判据：
test_agent_start_contract / test_ai_routing_contract / test_routes_contract（操作层）/
test_doc_reachability（全仓路径与命令）/ test_agents_contract（开发纪律第一跳）。
契约：七节结构、三正交与五条不变式与 01 §5 同源、十问逐问可映射回小节、引用零悬空。
"""
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "desktop" / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import prose_lint  # noqa: E402

DEEP = ROOT / "docs" / "meta" / "DEEP_DIVE.md"
PROTOCOL = ROOT / "01_核心协议.md"
TICK = chr(96)

REQUIRED_SECTIONS = ("## §1 本质", "## §2 质量观", "## §3 结构地图", "## §4 运行心智",
                     "## §5 纪律红线", "## §6 深读路径", "## §7 自检十问")
REQUIRED_MARKERS = ("三正交", "I1", "I2", "I3", "I4", "I5", "五维纵深", "内部法官链",
                    "零编造", "计划不外发", "引用不等于背书", "门禁绿 ≠ 顶尖",
                    "读 → 判 → 配 → 装 → 执 → 验", "P02", "P03",
                    "protocol/LAYERS.json", "protocol/driver.json")
REQUIRED_LINKS = ("STRATEGY.md", "docs/agent/AGENT_START.md", "docs/agent/AI_ROUTING.md",
                  "docs/agent/agent_组装指令包_v0.2.md", "docs/verification-cards.md",
                  "docs/mcp.md", "protocol/LAYERS.json", "protocol/driver.json",
                  "protocol/WORLD_MODEL.md", "01_核心协议.md", "02_联动注册表.md",
                  "06_Agent执行协议.md", "07_官方核心出厂与社区预设导航.md",
                  "desktop/src/core", "scripts/nf.py")
#: 01 §5 五条不变式（理解层必须与协议真源同源，名称逐条对账）
INVARIANTS = {"I1": "三正交分离", "I2": "核心固定", "I3": "通信契约",
              "I4": "数据隔离", "I5": "真相唯一"}

_BACKTICK = re.compile(TICK + "([^" + TICK + "\n]+)" + TICK)
_LINK = re.compile(r"\]\(([^)\s]+)\)")
_NF_CMD = re.compile(r"\bnf(?:\.py)?\s+([a-z][a-z0-9-]*)")
_PLACEHOLDER = ("*", "\u2026", "<", ">", "...", "::", "{", "}")
_FILEY = (".md", ".json", ".py", ".yaml", ".yml", ".txt", ".sh", ".cmd")


def load_text(path: Path = DEEP) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"DEEP_DIVE 不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("DEEP_DIVE 为空")
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
    for match in _LINK.finditer(text):
        target = match.group(1).strip()
        if target.startswith(("http://", "https://", "#", "mailto:")):
            continue
        rel = target.split("#")[0]
        if rel and not (ROOT / rel).exists():
            bad.append(target)
    return bad


def protocol_invariants(text: str) -> dict:
    """从 01 §5 抽 I1-I5 名称（真源；缺一行即理解层失去对照物）。"""
    rows = re.findall(r"^\|\s*(I[1-5])\s*\|\s*([^|]+?)\s*\|", text, re.M)
    return {key: name.strip() for key, name in rows}


def question_count(text: str) -> int:
    """§7 自检十问的条目数 + 是否每问都映射回小节。"""
    if "## §7 自检十问" not in text:
        return 0
    body = text.split("## §7 自检十问", 1)[1]
    return sum(1 for ln in body.splitlines()
               if "." in ln.strip() and ln.strip().split(".", 1)[0].isdigit())


def question_map_issues(text: str) -> list:
    if "## §7 自检十问" not in text:
        return ["缺 §7 自检十问"]
    body = text.split("## §7 自检十问", 1)[1]
    rows = [ln.strip() for ln in body.splitlines()
            if "." in ln.strip() and ln.strip().split(".", 1)[0].isdigit()]
    return [f"自检第 {i + 1} 问没有映射回小节（应写 → §N）"
            for i, row in enumerate(rows) if "→ §" not in row]


def deep_dive_issues(text: str, protocol_text: str) -> list:
    issues = []
    for section in REQUIRED_SECTIONS:
        if section not in text:
            issues.append(f"缺段落：{section}")
    for marker in REQUIRED_MARKERS:
        if marker not in text:
            issues.append(f"缺要素：{marker}")
    for target in REQUIRED_LINKS:
        if target not in text:
            issues.append(f"理解链缺落点：{target}")
    for target in dangling(text):
        issues.append(f"引用的仓内路径不存在：{target}（悬空引用）")
    if question_count(text) != 10:
        issues.append(f"自检问答不是 10 条（实测 {question_count(text)} 条）")
    issues.extend(question_map_issues(text))
    valid = prose_lint.cli_commands(str(ROOT))
    if len(valid) < 40:
        issues.append(f"CLI 命令面解析失败（{len(valid)} 条），判据可能已失效")
    for cmd in _NF_CMD.findall(text):
        if cmd not in valid:
            issues.append(f"引用了不存在的 nf 子命令：nf {cmd}")
    truth = protocol_invariants(protocol_text)
    for key, name in INVARIANTS.items():
        if truth.get(key) != name:
            issues.append(f"01 §5 不变式真源不一致：{key} 应为 {name}"
                           f"（实测 {truth.get(key)}）")
        if key not in text or name not in text:
            issues.append(f"理解层缺不变式：{key} {name}（应引用 01 §5）")
    return issues


class DeepDiveContractTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()
        self.protocol = PROTOCOL.read_text(encoding="utf-8")

    def test_deep_dive_matches_contract(self):
        issues = deep_dive_issues(self.text, self.protocol)
        self.assertEqual([], issues, "DEEP_DIVE 不满足理解层契约")

    def test_references_resolve(self):
        self.assertEqual([], dangling(self.text), "DEEP_DIVE 有悬空引用")

    def test_invariants_match_protocol_source(self):
        truth = protocol_invariants(self.protocol)
        self.assertEqual(INVARIANTS, truth, "01 §5 五条不变式真源已漂移")
        for key, name in INVARIANTS.items():
            self.assertIn(name, self.text, f"理解层缺 {key} {name}")

    def test_ten_questions_are_mapped(self):
        self.assertEqual(10, question_count(self.text), "自检问答应为 10 条")
        self.assertEqual([], question_map_issues(self.text), "自检问未映射回小节")

    def test_contract_catches_broken_understanding(self):
        """变异自证：删三正交 / 改不变式名 / 悬空路径 / 假命令 / 十问缺映射都必须报。"""
        no_orthogonal = self.text.replace("三正交", "三要素")
        self.assertTrue(any("三正交" in i
                            for i in deep_dive_issues(no_orthogonal, self.protocol)))
        renamed = self.text.replace("I2 核心固定", "I2 核心可换")
        self.assertTrue(any("I2" in i for i in deep_dive_issues(renamed, self.protocol)))
        bad_path = self.text + "\n参考 " + TICK + "docs/nope.md" + TICK + "。\n"
        self.assertTrue(any("docs/nope.md" in i
                            for i in deep_dive_issues(bad_path, self.protocol)))
        bad_cmd = self.text + "\n跑 " + TICK + "nf doctorr" + TICK + "。\n"
        self.assertTrue(any("doctorr" in i
                            for i in deep_dive_issues(bad_cmd, self.protocol)))
        unumbered = self.text.replace("10. 外部链接 / 工具意味着什么？→ §5", "")
        self.assertTrue(any("10 条" in i
                            for i in deep_dive_issues(unumbered, self.protocol)))
        unmapped = self.text.replace("3. 什么是三正交？→ §1", "3. 什么是三正交？")
        self.assertTrue(any("没有映射回小节" in i
                            for i in deep_dive_issues(unmapped, self.protocol)))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_deep_dive.md")


if __name__ == "__main__":
    unittest.main()
