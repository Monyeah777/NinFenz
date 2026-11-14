#!/usr/bin/env python3
"""AGENTS.md 契约判据：开工前必读链第一跳必须「路径可解析、事实与仓库一致」（2026-11-11）。

为什么必须有：AGENTS.md 是任一 AI agent 的开工第一跳，但它此前零判据——路径写错、命令不存在、
或者把已退役的端壳写成现状（实测：文中声称「桌面端会显示环境缺失横幅」，而桌面 GUI 端壳
2026-09-09 已永久退役，见 docs/L3_FROZEN.md），每个新会话都会照着错的做。

范围：只判 AGENTS.md 的**可核性**（本节不改任何纪律口径）。同族判据：test_doc_reachability /
test_license_chain。契约：硬性闸门段落齐全、破坏性命令清单在场、引用可解析、
事实与仓库一致（validate_path / 单测 / STRATEGY / 端壳退役）。
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AGENTS = ROOT / "AGENTS.md"
STRATEGY = ROOT / "STRATEGY.md"
PATHS = ROOT / "desktop" / "src" / "core" / "paths.py"
L3 = ROOT / "docs" / "L3_FROZEN.md"

#: 必备段落（缺一段即开工纪律断链）
REQUIRED_SECTIONS = ("高危命令纪律", "Agent 安全保护", "通用执行纪律",
                     "Python 项目环境", "Project-Specific Rules", "NF 方向与发布纪律")
#: 硬性闸门必须写清的条目
REQUIRED_MARKERS = (
    "未确认一律禁止", "「看看」≠「动手」", "敏感文件禁止", "恶意行为拒绝",
    "系统消息信任边界", "沙箱意识", "输出保护", "求证优先", "单问约束",
    "做了什么 / 遗留什么 / 设计偏差",
)
#: 止损清单（2026-11 加）：四条高发误判必须逐条在场（只增不减）
LESSONS = ("下不全是普通文档", "一致性报告重算后必须重新批准",
           "带译件的文档要同步三处", "没跑完的门禁不许写成全绿")
LESSON_SECTION = "本仓高发误判"

#: 破坏性命令清单（少一条即有人照着做）
DESTRUCTIVE = ("git stash", "git reset --hard", "git checkout --", "git restore",
               "git clean", "git push -f", "git branch -D", "rm -rf")

_BACKTICK = re.compile(chr(96) + r"([^" + chr(96) + r"\n]+)" + chr(96))
_LINK = re.compile(r"\]\(([^)\s]+)\)")
_PATH_SHAPE = re.compile(r"^[A-Za-z0-9_./\-\u4e00-\u9fff]+$")
_PLACEHOLDER = ("*", "…", "<", ">")


def load_text(path: Path = AGENTS) -> str:
    """读 AGENTS.md（缺失 / 空件显式报错）。"""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"AGENTS.md 不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("AGENTS.md 为空")
    return text


def lesson_issues(text: str) -> list:
    """止损清单：段落在场、四条逐条在场、且不许把「部分通过」写成「全绿」。"""
    issues = []
    if LESSON_SECTION not in text:
        issues.append("缺「本仓高发误判」止损清单段")
        return issues
    for item in LESSONS:
        if item not in text:
            issues.append(f"止损清单缺条目：{item}")
    if "台账造假" not in text:
        issues.append("缺「不许写成全绿 = 台账造假」口径")
    return issues


def dangling(text: str, root: Path = ROOT) -> list:
    """悬空的仓内引用：反引号路径 + Markdown 相对链接（`..` 逃逸示例不判）。"""
    bad = []
    for match in _BACKTICK.finditer(text):
        tok = match.group(1).strip()
        if "/" not in tok or not _PATH_SHAPE.match(tok) or ".." in tok:
            continue
        if any(ch in tok for ch in _PLACEHOLDER) or tok.startswith("http"):
            continue
        if not (root / tok.rstrip("/")).exists():
            bad.append(tok)
    for match in _LINK.finditer(text):
        target = match.group(1).strip()
        if target.startswith(("http://", "https://", "#", "mailto:")):
            continue
        rel = target.split("#")[0]
        if rel and not (root / rel).exists():
            bad.append(target)
    return bad


def agents_issues(text: str, root: Path = ROOT) -> list:
    """AGENTS.md 可核性问题列表（纯函数，便于变异自证）。"""
    issues = []
    for section in REQUIRED_SECTIONS:
        if section not in text:
            issues.append(f"缺段落：{section}")
    for marker in REQUIRED_MARKERS:
        if marker not in text:
            issues.append(f"缺要素：{marker}")
    for token in DESTRUCTIVE:
        if token not in text:
            issues.append(f"破坏性命令清单缺：{token}")
    if not (root / "STRATEGY.md").is_file():
        issues.append("开工前必读链指向的 STRATEGY.md 不存在")
    paths_py = root / "desktop" / "src" / "core" / "paths.py"
    if not paths_py.is_file() or "def validate_path" not in paths_py.read_text(encoding="utf-8"):
        issues.append("AGENTS.md 点名的 validate_path 不在 desktop/src/core/paths.py")
    for rel in ("desktop/tests/test_paths.py", "desktop/tests/test_output_path_escape.py"):
        if not (root / rel).is_file():
            issues.append(f"AGENTS.md 点名的单测不在场：{rel}")
    if "paths.py::validate_path" not in text:
        issues.append("沙箱条款未把包含性判据指向 paths.py::validate_path")
    # 事实对账：桌面 GUI 端壳已于 2026-09-09 永久退役（docs/L3_FROZEN.md）
    if "桌面端" in text:
        issues.append("仍把已退役的桌面端壳写成现状（见 docs/L3_FROZEN.md）")
    l3 = root / "docs" / "L3_FROZEN.md"
    if not l3.is_file() or "永久退役" not in l3.read_text(encoding="utf-8"):
        issues.append("缺端壳退役记录 docs/L3_FROZEN.md")
    for target in dangling(text, root):
        issues.append(f"引用的仓内路径不存在：{target}（悬空引用）")
    issues += lesson_issues(text)
    return issues


class AgentsContractTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_agents_matches_contract(self):
        self.assertEqual([], agents_issues(self.text), "AGENTS.md 不满足可核性契约")

    def test_lessons_section_present(self):
        """止损清单（2026-11 加）：四条高发误判逐条在场，且明令「不许写成全绿」。"""
        self.assertEqual([], lesson_issues(self.text), "AGENTS.md 止损清单不完整")

    def test_references_resolve(self):
        """文中反引号路径与 Markdown 相对链接必须逐个可解析。"""
        self.assertEqual([], dangling(self.text), "AGENTS.md 有悬空引用")

    def test_facts_match_repo(self):
        """点名的事实必须在仓库里成立（validate_path / 单测 / 退役记录）。"""
        self.assertIn("def validate_path", PATHS.read_text(encoding="utf-8"))
        self.assertTrue((ROOT / "desktop" / "tests" / "test_paths.py").is_file())
        self.assertTrue((ROOT / "desktop" / "tests" / "test_output_path_escape.py").is_file())
        self.assertTrue(STRATEGY.is_file(), "开工前必读链缺 STRATEGY.md")
        self.assertIn("永久退役", L3.read_text(encoding="utf-8"))

    def test_contract_catches_broken_agents(self):
        """变异自证：删闸门段 / 悬空路径 / 写回退役端壳 / 改判据名——都必须报。"""
        no_safety = self.text.replace("## Agent 安全保护（硬性闸门）", "## 其他")
        self.assertTrue(any("Agent 安全保护" in i for i in agents_issues(no_safety)),
                        "删掉安全闸门段必须报")
        bad_path = self.text + "\n参考 " + chr(96) + "docs/nope.md" + chr(96) + "。\n"
        self.assertTrue(any("docs/nope.md" in i for i in agents_issues(bad_path)),
                        "悬空路径必须报")
        stale = self.text + "\n桌面端也会显示横幅。\n"
        self.assertTrue(any("退役" in i for i in agents_issues(stale)),
                        "写回已退役端壳必须报")
        renamed = self.text.replace("paths.py::validate_path", "paths.py::validatePath")
        self.assertTrue(any("validate_path" in i for i in agents_issues(renamed)),
                        "改掉判据名必须报")
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_agents.md")


if __name__ == "__main__":
    unittest.main()
