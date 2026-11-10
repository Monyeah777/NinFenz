#!/usr/bin/env python3
"""STRATEGY 契约判据：方向层文件必须「条款可核、内部链在场、发布边界与仓库一致」（2026-11-11）。

为什么必须有：STRATEGY.md 是方向与质量准绳的最高层文件，但它此前零判据——条款里点名的
内部验证链载体（verify.sh / audit 建档 / fixtures / 演练集）与发布边界事实（公开仓不得有方案文档）
没有任何测试断言。条款语义属作者政策面，本件只做**可核化**，不改任何口径。

范围：只判 STRATEGY.md 的可核性。同族判据：test_agents_contract（开工链第一跳）、
test_license_chain（许可链）。
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STRATEGY = ROOT / "STRATEGY.md"
AGENTS = ROOT / "AGENTS.md"
README = ROOT / "README.md"

#: 必备段落（缺一段即方向层断链）
REQUIRED_SECTIONS = ("NF 要实现什么", "验收函数", "质量法官", "仓库发布边界", "开工前置清单")
#: 政策内核必须写清楚的条目
REQUIRED_MARKERS = (
    "单变量", "五维纵深", "质量法官 = 内部验证",
    "立项理由不得引用外部", "质量论证不得引用外部背书",
    "计划内部消化", "门禁绿 ≠ 质量宣称", "开工前必读",
)
#: 五维纵深的名字（与条款一致）
DIMENSIONS = ("静态可核验", "动态可执行", "架构纯度", "资产密度", "文档可执行性")
#: STRATEGY §3.1「内部链」的四个载体（少一个即链断）
CHAIN_CARRIERS = (
    "verify.sh", "results/audit", "desktop/tests/fixtures", "docs/42_M1_P03_演练集.md",
)
#: STRATEGY §四「AGENT_START/ROUTES/assembly 指令」指向的入口件
AGENT_ENTRIES = ("AGENT_START.md", "ROUTES.md")

_BACKTICK = re.compile(chr(96) + r"([^" + chr(96) + r"\n]+)" + chr(96))
_LINK = re.compile(r"\]\(([^)\s]+)\)")
_PATH_SHAPE = re.compile(r"^[A-Za-z0-9_./\-\u4e00-\u9fff]+$")
_PLACEHOLDER = ("*", "…", "<", ">")


def load_text(path: Path = STRATEGY) -> str:
    """读 STRATEGY.md（缺失 / 空件显式报错）。"""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"STRATEGY.md 不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("STRATEGY.md 为空")
    return text


def dangling(text: str, root: Path = ROOT) -> list:
    """悬空的仓内引用：反引号路径 + Markdown 相对链接。"""
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


def public_plan_files(root: Path = ROOT) -> list:
    """公开仓根层的方案文档（STRATEGY §四：计划类文档不发布公开仓库）。"""
    return sorted(p.name for p in root.glob("*.md") if "方案" in p.name)


def strategy_issues(text: str, root: Path = ROOT, plan_files: list = None) -> list:
    """STRATEGY 可核性问题列表（纯函数，便于变异自证）。"""
    issues = []
    for section in REQUIRED_SECTIONS:
        if section not in text:
            issues.append(f"缺段落：{section}")
    for marker in REQUIRED_MARKERS:
        if marker not in text:
            issues.append(f"缺条款：{marker}")
    for dim in DIMENSIONS:
        if dim not in text:
            issues.append(f"五维纵深缺一维：{dim}")
    for rel in CHAIN_CARRIERS:
        if not (root / rel).exists():
            issues.append(f"内部验证链载体不在场：{rel}")
    if not (root / "docs" / "agent" / "AGENT_START.md").is_file():
        issues.append("发布边界点名的 AGENT_START 不在场")
    for name in AGENT_ENTRIES:
        if not (root / "docs" / "agent" / name).is_file():
            issues.append(f"发布边界点名的入口件不在场：docs/agent/{name}")
    if not list((root / "docs" / "agent").glob("*组装指令包*")):
        issues.append("发布边界点名的 assembly 指令包不在场")
    agents_path = root / "AGENTS.md"
    agents = agents_path.read_text(encoding="utf-8") if agents_path.is_file() else ""
    if "STRATEGY.md" not in agents:
        issues.append("AGENTS.md 的开工前必读链未指向 STRATEGY.md")
    readme_path = root / "README.md"
    readme = readme_path.read_text(encoding="utf-8") if readme_path.is_file() else ""
    if "STRATEGY.md" not in readme:
        issues.append("README 方向表未指向 STRATEGY.md")
    plans = plan_files if plan_files is not None else public_plan_files(root)
    if plans:
        issues.append(f"公开仓根层出现计划类文档（违反 §四）：{plans}")
    for target in dangling(text, root):
        issues.append(f"引用的仓内路径不存在：{target}（悬空引用）")
    return issues


class StrategyContractTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_strategy_matches_contract(self):
        self.assertEqual([], strategy_issues(self.text), "STRATEGY.md 不满足可核性契约")

    def test_internal_chain_carriers_exist(self):
        """§3.1 内部链的四个载体必须真实在场（verify / audit / fixtures / 演练集）。"""
        for rel in CHAIN_CARRIERS:
            self.assertTrue((ROOT / rel).exists(), f"内部链载体不在场：{rel}")

    def test_publish_boundary_matches_repo(self):
        """§四 发布边界：根层不得有方案文档；点名的 agent 入口必须在场。"""
        self.assertEqual([], public_plan_files(), "公开仓根层出现计划类文档")
        for name in AGENT_ENTRIES:
            self.assertTrue((ROOT / "docs" / "agent" / name).is_file(), f"缺 {name}")

    def test_references_resolve(self):
        self.assertEqual([], dangling(self.text), "STRATEGY 有悬空引用")

    def test_contract_catches_broken_strategy(self):
        """变异自证：删段落 / 删一维 / 注入方案文档 / 悬空引用——都必须报。"""
        no_section = self.text.replace("## 三、质量法官 = 内部验证", "## 三、附注")
        self.assertTrue(any("质量法官" in i for i in strategy_issues(no_section)),
                        "删掉质量法官段必须报")
        no_dim = self.text.replace("资产密度", "资产数量")
        self.assertTrue(any("资产密度" in i for i in strategy_issues(no_dim)),
                        "改掉五维之一必须报")
        leaked = strategy_issues(self.text, plan_files=["41_x方案.md"])
        self.assertTrue(any("计划类文档" in i for i in leaked), "根层出现方案文档必须报")
        bad_path = self.text + "\n参考 " + chr(96) + "docs/nope.md" + chr(96) + "。\n"
        self.assertTrue(any("docs/nope.md" in i for i in strategy_issues(bad_path)),
                        "悬空路径必须报")
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_strategy.md")


if __name__ == "__main__":
    unittest.main()
