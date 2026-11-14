#!/usr/bin/env python3
"""README.en 镜像契约：English 入口必须与 canonical 面「同结构、同事实、同可执行性」。

为什么必须有：README.en.md 是 check34 语言面的一员（锚点 / 切换行 / H2 数 / 引件对齐），
但「正文内容有没有跟上 canonical 的升级」此前无判据。实测本轮抓到 6 处滞后：快速开始仍只有
命令没有验收标准、FAQ 缺「怎么装 / 环境要求 / 怎么接 MCP」、入口链缺 ROUTES、版本线无真源
声明、最后更新时间停在 2026-09-20、以及一句 canonical 已删掉的「随附单文件可执行」旧宣言。

范围：只判 README.en.md 的**镜像完整性与可执行性**（不改语言面口径）。同族判据：
test_readme_contract（canonical 面）/ test_locales（三语锚点 / 切换行 / H2 对齐）/
test_version_map（公开数字）/ test_doc_reachability（全仓路径与 nf 命令）。
契约：五节英文标题按序、FAQ 三类在场、快速开始带验收、版本与 npm 真源一致、
统计区外零运行时计数、引件零悬空。
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

README_EN = ROOT / "README.en.md"
NPMPKG = ROOT / "packaging" / "npm" / "package.json"
VERIFY = ROOT / "verify.sh"
TICK = chr(96)
STATS_BEGIN = "<!-- nf:stats:begin -->"
STATS_END = "<!-- nf:stats:end -->"

#: English 面的五节（与 canonical 面逐节对应）
REQUIRED_SECTIONS = ("## ⚡ If you are an AI / Agent", "## Quick start",
                     "## Capabilities and assets", "## Protocol chain and documentation map",
                     "## Versions")
FAQ_MARKERS = ("How do I install it?", "environment requirements", "connect MCP")
QUICKSTART_MARKERS = ("Per-step acceptance", "exit 0", "17/17", "--checks-only", "Git Bash")
REQUIRED_MARKERS = ("Canonical repository", "What it is not", "ninfenz.dev", "llms.txt",
                    "Last updated:", "authoritative", "repository root")
_BACKTICK = re.compile(TICK + "([^" + TICK + "\n]+)" + TICK)
_NF_CMD = re.compile(r"\bnf(?:\.py)?\s+([a-z][a-z0-9-]*)")
_PLACEHOLDER = ("*", "\u2026", "<", ">", "...", "::", "{", "}", "XXXX")
_FILEY = (".md", ".json", ".py", ".yaml", ".yml", ".txt", ".sh", ".cmd")
LIVE_COUNT = (r"PASS=\d+", r"check1-\d+")


def load_text(path: Path = README_EN) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"README.en 不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("README.en 为空")
    return text


def stats_region(text: str) -> str:
    match = re.search(re.escape(STATS_BEGIN) + "(.*?)" + re.escape(STATS_END), text, re.S)
    return match.group(1) if match else ""


def npm_version() -> str:
    return str(json.loads(NPMPKG.read_text(encoding="utf-8")).get("version") or "")


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


def readme_en_issues(text: str) -> list:
    issues = []
    positions = [text.find(section) for section in REQUIRED_SECTIONS]
    for section, pos in zip(REQUIRED_SECTIONS, positions, strict=True):
        if pos < 0:
            issues.append(f"缺小节：{section}")
    if all(pos >= 0 for pos in positions) and positions != sorted(positions):
        issues.append("五节顺序不对")
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
    elif "Do not edit by hand" not in stats_region(text):
        issues.append("stats 生成区缺「Do not edit by hand」口径")
    for anchor in _locales.anchors():
        if anchor not in text:
            issues.append(f"缺语言面机读锚点：{anchor}")
    version = npm_version()
    if version and f"{TICK}ninfenz{TICK} {version}" not in text:
        issues.append(f"版本声明未对上是真源 ninfenz {version}")
    for target in dangling(text):
        issues.append(f"引用的仓内路径不存在：{target}（悬空引用）")
    valid = prose_lint.cli_commands(str(ROOT))
    if len(valid) < 40:
        issues.append(f"CLI 命令面解析失败（{len(valid)} 条），判据可能已失效")
    for cmd in _NF_CMD.findall(text):
        if cmd not in valid:
            issues.append(f"引用了不存在的 nf 子命令：nf {cmd}")
    if "--checks-only" in text and "--checks-only" not in VERIFY.read_text(encoding="utf-8"):
        issues.append("README.en 写了 bash verify.sh --checks-only，但 verify.sh 不支持该旗标")
    outside = text.replace(stats_region(text), "")
    for pattern in LIVE_COUNT:
        for hit in re.findall(pattern, outside):
            issues.append(f"stats 生成区外钉了运行时计数：{hit}")
    return issues


class ReadmeEnContractTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_readme_en_matches_contract(self):
        self.assertEqual([], readme_en_issues(self.text), "README.en 不满足镜像契约")

    def test_sections_and_stats_region(self):
        positions = [self.text.find(s) for s in REQUIRED_SECTIONS]
        self.assertTrue(all(p >= 0 for p in positions), "五节不全")
        self.assertEqual(sorted(positions), positions, "五节顺序不对")
        self.assertIn("Do not edit by hand", stats_region(self.text))

    def test_versions_match_npm(self):
        version = npm_version()
        self.assertTrue(version)
        self.assertIn(f"{TICK}ninfenz{TICK} {version}", self.text)

    def test_readme_en_catches_mutations(self):
        """变异自证：删节 / 删 FAQ / 版本漂移 / 悬空路径 / 假命令 / 区外计数都必须报。"""
        no_section = self.text.replace("## Quick start", "## Getting started")
        self.assertTrue(any("缺小节" in i for i in readme_en_issues(no_section)))
        no_faq = self.text.replace("connect MCP", "connect a client")
        self.assertTrue(any("FAQ 缺问题类" in i for i in readme_en_issues(no_faq)))
        version = npm_version()
        claim = f"{TICK}ninfenz{TICK} {version}"
        wrong = self.text.replace(claim, f"{TICK}ninfenz{TICK} 9.9.9")
        self.assertTrue(any("版本声明" in i for i in readme_en_issues(wrong)))
        bad_path = self.text + "\nSee " + TICK + "docs/nope.md" + TICK + ".\n"
        self.assertTrue(any("docs/nope.md" in i for i in readme_en_issues(bad_path)))
        bad_cmd = self.text + "\nRun " + TICK + "nf doctorr" + TICK + ".\n"
        self.assertTrue(any("doctorr" in i for i in readme_en_issues(bad_cmd)))
        pinned = self.text + "\nCurrent PASS=999.\n"
        self.assertTrue(any("runtime count" in i or "运行时计数" in i
                            for i in readme_en_issues(pinned)))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_readme_en.md")


if __name__ == "__main__":
    unittest.main()
