#!/usr/bin/env python3
"""README 入口契约：canonical 人读入口必须「结构稳、事实同源、照做能跑通」。

为什么必须有：README.md 是三语入口的 canonical 面（check34 只判语言锚点 / 切换行 / H2 数对齐 /
引件在场），但「快速开始六步有没有验收标准」「FAQ 有没有回答装不装得上 / 怎么接 MCP」
「版本与命令是否真」此前无判据。实测本轮补的真缺口：快速开始六步只有命令没有期望结果、
FAQ 缺「怎么装 / 环境要求 / 怎么接 MCP」三类高频问题、版本线没有真源声明。

范围：只判 README.md 的**可执行性与同源事实**（不改文案口径）。同族判据：
test_locales（三语锚点 / 切换行 / H2 对齐）、test_version_map（公开数字）、
test_doc_reachability（全仓路径与 nf 命令）、test_nf_tui（演示帧逐字一致）。
契约：五节结构按序、语言面锚点齐、快速开始六步带验收、FAQ 三类问题在场、
版本 = npm/pyproject 真源、命令与旗标真实、stats 生成区外零运行时计数。
"""
import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "desktop" / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import locales as _locales  # noqa: E402
from core import prose_lint  # noqa: E402

README = ROOT / "README.md"
NPMPKG = ROOT / "packaging" / "npm" / "package.json"
PYPROJECT = ROOT / "pyproject.toml"
STATS = ROOT / "protocol" / "repo_stats.json"
VERIFY = ROOT / "verify.sh"
TICK = chr(96)
STATS_BEGIN = "<!-- nf:stats:begin -->"
STATS_END = "<!-- nf:stats:end -->"

#: canonical 面五节（顺序即导航顺序）
REQUIRED_SECTIONS = ("## ⚡ 如果你是 AI / Agent", "## 快速开始", "## 能力与资产",
                     "## 协议链与文档导航", "## 版本")
#: 高频入口必须回答的三类 FAQ（缺一类就有人装不上 / 接不上）
FAQ_MARKERS = ("怎么装", "环境要求", "怎么接 MCP")
#: 快速开始的执行性要素（只有命令没有验收标准 = 读者不知道什么时候算过）
QUICKSTART_MARKERS = ("退出码 0", "17/17", "--checks-only", "Git Bash", "每步验收")
REQUIRED_MARKERS = ("唯一官方仓库", "不是什么", "ninfenz.dev", "llms.txt",
                    "安装说明书", "check34")
_BACKTICK = re.compile(TICK + "([^" + TICK + "\n]+)" + TICK)
_NF_CMD = re.compile(r"\bnf(?:\.py)?\s+([a-z][a-z0-9-]*)")
_PLACEHOLDER = ("*", "\u2026", "<", ">", "...", "::", "{", "}", "XXXX")
_FILEY = (".md", ".json", ".py", ".yaml", ".yml", ".txt", ".sh", ".cmd")
LIVE_COUNT = (r"PASS=\d+", r"check1-\d+")


def load_text(path: Path = README) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"README 不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("README 为空")
    return text


def stats_region(text: str) -> str:
    match = re.search(re.escape(STATS_BEGIN) + "(.*?)" + re.escape(STATS_END), text, re.S)
    return match.group(1) if match else ""


def core_versions() -> dict:
    """版本真源双读：pyproject 与 npm 包元数据必须一致。"""
    pyproject = PYPROJECT.read_text(encoding="utf-8")
    py = re.search(r"(?m)^version\s*=\s*\"([^\"]+)\"", pyproject)
    npm = json.loads(NPMPKG.read_text(encoding="utf-8")).get("version")
    return {"pyproject": py.group(1) if py else "", "npm": str(npm or "")}


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


def readme_issues(text: str) -> list:
    issues = []
    positions = [text.find(section) for section in REQUIRED_SECTIONS]
    for section, pos in zip(REQUIRED_SECTIONS, positions, strict=True):
        if pos < 0:
            issues.append(f"缺小节：{section}")
    if all(pos >= 0 for pos in positions) and positions != sorted(positions):
        issues.append("五节顺序不对（导航顺序即读者路径）")
    for marker in REQUIRED_MARKERS:
        if marker not in text:
            issues.append(f"缺要素：{marker}")
    for marker in FAQ_MARKERS:
        if marker not in text:
            issues.append(f"FAQ 缺问题类：{marker}")
    for marker in QUICKSTART_MARKERS:
        if marker not in text:
            issues.append(f"快速开始缺执行性要素：{marker}")
    if STATS_BEGIN not in text or STATS_END not in text:
        issues.append("缺 nf:stats 生成区标记")
    elif "禁止手改" not in stats_region(text):
        issues.append("stats 生成区缺「禁止手改」口径")
    for anchor in _locales.anchors():
        if anchor not in text:
            issues.append(f"缺语言面机读锚点：{anchor}")
    versions = core_versions()
    if versions["pyproject"] != versions["npm"]:
        issues.append(f"pyproject 版本 {versions['pyproject']} ≠ npm 版本 {versions['npm']}")
    if versions["pyproject"] and f"{TICK}ninfenz{TICK} {versions['pyproject']}" not in text:
        issues.append(f"版本声明未对上是真源 ninfenz {versions['pyproject']}")
    for target in dangling(text):
        issues.append(f"引用的仓内路径不存在：{target}（悬空引用）")
    valid = prose_lint.cli_commands(str(ROOT))
    if len(valid) < 40:
        issues.append(f"CLI 命令面解析失败（{len(valid)} 条），判据可能已失效")
    for cmd in _NF_CMD.findall(text):
        if cmd not in valid:
            issues.append(f"引用了不存在的 nf 子命令：nf {cmd}")
    if "--checks-only" in text and "--checks-only" not in VERIFY.read_text(encoding="utf-8"):
        issues.append("README 写了 bash verify.sh --checks-only，但 verify.sh 不支持该旗标")
    outside = text.replace(stats_region(text), "")
    for pattern in LIVE_COUNT:
        for hit in re.findall(pattern, outside):
            issues.append(f"stats 生成区外钉了运行时计数：{hit}")
    return issues


class ReadmeContractTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_readme_matches_contract(self):
        self.assertEqual([], readme_issues(self.text), "README 不满足入口契约")

    def test_sections_in_order_and_stats_region(self):
        positions = [self.text.find(s) for s in REQUIRED_SECTIONS]
        self.assertTrue(all(p >= 0 for p in positions), "五节不全")
        self.assertEqual(sorted(positions), positions, "五节顺序不对")
        self.assertIn("禁止手改", stats_region(self.text))

    def test_versions_match_npm_and_pyproject(self):
        versions = core_versions()
        self.assertEqual(versions["pyproject"], versions["npm"], "版本真源两处不一致")
        self.assertIn(f"{TICK}ninfenz{TICK} {versions['npm']}", self.text)

    def test_readme_catches_mutations(self):
        """变异自证：删节 / 删 FAQ / 版本漂移 / 悬空路径 / 假命令 / 区外计数都必须报。"""
        no_section = self.text.replace("## 快速开始", "## 开始")
        self.assertTrue(any("缺小节" in i for i in readme_issues(no_section)))
        no_faq = self.text.replace("怎么接 MCP", "如何连接")
        self.assertTrue(any("FAQ 缺问题类" in i for i in readme_issues(no_faq)))
        version = core_versions()["npm"]
        claim = f"{TICK}ninfenz{TICK} {version}"
        wrong_version = self.text.replace(claim, f"{TICK}ninfenz{TICK} 9.9.9")
        self.assertTrue(any("版本声明" in i for i in readme_issues(wrong_version)))
        bad_path = self.text + "\n参考 " + TICK
        bad_path += "docs/nope.md" + TICK + "。\n"
        self.assertTrue(any("docs/nope.md" in i for i in readme_issues(bad_path)))
        bad_cmd = self.text + "\n跑 " + TICK + "nf doctorr" + TICK + "。\n"
        self.assertTrue(any("doctorr" in i for i in readme_issues(bad_cmd)))
        pinned = self.text + "\n当前 PASS=999。\n"
        self.assertTrue(any("运行时计数" in i for i in readme_issues(pinned)))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_readme.md")


if __name__ == "__main__":
    unittest.main()
