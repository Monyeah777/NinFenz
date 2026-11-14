#!/usr/bin/env python3
"""llms.txt 契约判据：机器入口清单的链接、检查引用与运行时计数都必须真（2026-11-11）。

为什么必须有：llms.txt 是 agent/抓取器的第一跳机器入口（38 条 raw 直链 + 检查号 + 命令面声明），
但 check34 只抽查 5 个锚点（# NinFenz、library/INDEX.md、01_核心协议.md 等），其余条目无判据。
本轮实测命中 2 处真缺陷：① 验证卡册仍写「由 build_verification_cards.ps1 生成」——该脚本不在仓库
（生成器脚本自己的注释就写着「此前自称、实际零命中」），实际是 scripts/build_verification_cards.py；
② 「conformance（16 契约报告 …）」——conformance_report.json 当前是 27 条契约，活文档钉了会漂的
运行时计数。

判据（逐条可自证）：
1. 全部 raw / tree 直链的仓库路径必须存在（占位符 {路径} 跳过；面 ≥ 30 条防失效）；
2. 反引号里的仓库路径必须存在；裸文件名要么能在受跟踪面按 basename 命中，要么在「非路径术语」
   白名单里（llms.txt v2 规格术语 page.md 不是仓库件）；
3. 引用的检查号必须真存在（verify.sh 的 checkN 函数），且该函数体必须真的管那件事
   （check34→locales、check38→接入面、check39→quickstart）；
4. nf:stats 生成区之外的活文本不得钉运行时计数（PASS= / check1- / N 契约报告）；
5. 形态与生成新鲜度：H1 / 摘要引用块 / 官方仓库行 / 关键小节在场；nf stats --check 通过。

范围：只判 llms.txt（llms-full.txt 与站点投影的判据在 sync_llms 侧）。同族判据：
test_doc_links_contract（全仓链接）、test_live_doc_counts（活文档计数）、test_ccos_docs_anchors。
"""
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LLMS = ROOT / "llms.txt"
VERIFY = ROOT / "verify.sh"
TICK = chr(96)
BS = chr(92)  # 反斜杠（避免源码里出现 \\d 这类转义歧义）
STATS_BEGIN = "<!-- nf:stats:begin -->"
STATS_END = "<!-- nf:stats:end -->"
#: 裸文件名中的非仓库路径术语（llms.txt v2 规格用语）。
NON_PATH_TOKENS = {"page.md"}
#: 检查号 → 该检查必须真的管的「面」关键词（防止引用错号）。
CHECK_CLAIMS = (("check34", "locales"), ("check38", "接入面"), ("check39", "quickstart"))
PATH_RE = re.compile(r"^[A-Za-z0-9_.\-/]+\.(?:md|json|txt|py|yml|yaml|sh|mjs|toml|cff|ps1)$")
#: 活文本里不许出现的运行时计数形态。
LIVE_COUNT_PATTERNS = (r"PASS=\d+", r"check1-\d+", r"\d+\s*契约报告", r"\d+\s*条单测")


def load_text(path: Path = LLMS) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError("llms.txt 不可读：" + str(exc)) from exc
    if not text.strip():
        raise ValueError("llms.txt 为空")
    return text


def tracked(root: Path = ROOT) -> list:
    try:
        proc = subprocess.run(["git", "-C", str(root), "ls-files", "-z"],
                              capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=180)
    except (OSError, subprocess.SubprocessError) as exc:
        raise ValueError("git ls-files 不可用：" + str(exc)) from exc
    return [p for p in proc.stdout.split("\x00") if p]


def url_issues(text: str, root: Path = ROOT) -> list:
    """raw / tree 直链的仓库路径必须存在。"""
    issues, count = [], 0
    for pattern in (r"https://raw\.githubusercontent\.com/Monyeah777/NinFenz/main/([^\s)#]+)",
                    r"https://github\.com/Monyeah777/NinFenz/tree/main/([^\s)#]+)"):
        for m in re.finditer(pattern, text):
            rel = m.group(1).strip(TICK + ".,;:)")
            if "{" in rel:
                continue
            count += 1
            if not (root / rel).exists():
                issues.append("直链指向不存在的路径：" + rel)
    return issues


def url_count(text: str) -> int:
    """直链条数（面级 sanity：太少说明判据失效）。"""
    host = "(?:raw" + BS + ".githubusercontent" + BS + ".com|github" + BS + ".com)"
    tail = "[^" + BS + "s)#]+"
    return len(re.findall("https://" + host + "/Monyeah777/NinFenz/"
                     "(?:main|tree/main)/" + tail, text))


def path_issues(text: str, root: Path = ROOT) -> list:
    """反引号里的仓库路径必须存在；裸文件名按 basename 命中或白名单。"""
    files = tracked(root)
    basenames = {p.rsplit("/", 1)[-1] for p in files}
    dirs = {p.split("/", 1)[0] for p in files if "/" in p}
    issues = []
    for token in re.findall(TICK + "([^" + TICK + "\n]+)" + TICK, text):
        tok = token.strip()
        if not tok or " " in tok or tok.startswith(("http", "nf://", "bash ", "python ")):
            continue
        if "{" in tok or "}" in tok:
            continue
        if "/" in tok:
            first = tok.rstrip("/").split("/", 1)[0]
            if (PATH_RE.match(tok) or first in dirs) and not (root / tok.rstrip("/")).exists():
                issues.append("路径不存在：" + tok)
        elif PATH_RE.match(tok) and tok not in NON_PATH_TOKENS and tok not in basenames:
            issues.append("裸文件名在受跟踪面不存在：" + tok)
    return issues


def check_body(verify_text: str, name: str) -> str:
    """提取 verify.sh 里 checkN() 的函数体（缺失返回空串）。"""
    m = re.search(r"^" + name + r"\(\)\{(.*?)^\}", verify_text, re.S | re.M)
    return m.group(1) if m else ""


def citation_issues(text: str, verify_text: str = None) -> list:
    """引用的检查号必须存在，且该检查的函数体必须真的管所声称的面。"""
    if verify_text is None:
        verify_text = VERIFY.read_text(encoding="utf-8", errors="replace")
    issues = []
    for num in sorted(set(re.findall(r"check(\d+)", text))):
        if not check_body(verify_text, "check" + num):
            issues.append("引用了不存在的检查：check" + num)
    for name, keyword in CHECK_CLAIMS:
        if name not in text:
            issues.append("关键引用缺失（判据可能漂移）：" + name)
            continue
        body = check_body(verify_text, name)
        if body and keyword not in body:
            issues.append(name + " 的函数体不含关键词 " + keyword + "（引用错号）")
    return issues


def stats_region(text: str) -> str:
    """返回 nf:stats 生成区内容（缺失返回空串）。"""
    m = re.search(re.escape(STATS_BEGIN) + "(.*?)" + re.escape(STATS_END), text, re.S)
    return m.group(1) if m else ""


def live_count_issues(text: str) -> list:
    """nf:stats 生成区之外的活文本不得钉运行时计数（钉了必漂）。"""
    issues = []
    outside = text.replace(stats_region(text), "")
    for pattern in LIVE_COUNT_PATTERNS:
        for hit in re.findall(pattern, outside):
            issues.append("活文本钉了运行时计数（应指向真源）：" + hit)
    return issues


def shape_issues(text: str) -> list:
    """llms.txt v2 形态与必备入口。"""
    issues = []
    if not text.startswith("# NinFenz"):
        issues.append("首行必须是 H1： # NinFenz")
    if "> NinFenz" not in text:
        issues.append("缺摘要引用块（> NinFenz …）")
    for needle in ("https://github.com/Monyeah777/NinFenz",
                   "https://raw.githubusercontent.com/Monyeah777/NinFenz/main/",
                   "## 先读", "## 协议", "## 馆藏", "## 工具", "## Optional"):
        if needle not in text:
            issues.append("缺必备入口 / 小节：" + needle)
    if STATS_BEGIN not in text or STATS_END not in text:
        issues.append("缺 nf:stats 生成区标记")
    return issues


def stats_check_ok(root: Path = ROOT) -> bool:
    try:
        proc = subprocess.run([sys.executable, str(root / "scripts" / "nf.py"), "stats",
                               "--check"], capture_output=True, timeout=180, check=False)
    except (OSError, subprocess.SubprocessError):
        return False
    return proc.returncode == 0


#: agent 第一跳面清单（都必须在本文件里有入口；缺一件 = 机器入口不完整）
REQUIRED_ENTRIES = (
    "docs/quickstart.md", "docs/agent/AGENT_START.md", "docs/agent/AI_ROUTING.md",
    "docs/agent/ROUTES.md", "docs/ai-menu.md", "docs/meta/DEEP_DIVE.md",
    "docs/agent/agent_组装指令包_v0.2.md", "docs/mcp.md", "docs/nfal.md",
    "docs/domain-packs.md", "docs/verification-cards.md", "docs/terminal.md",
    "docs/asset_contract.md", "docs/locales.md", "docs/release.md",
    "01_核心协议.md", "02_联动注册表.md", "06_Agent执行协议.md",
    "07_官方核心出厂与社区预设导航.md", "STRATEGY.md",
    "protocol/WORLD_MODEL.md", "protocol/LAYERS.json", "protocol/driver.json",
    "protocol/CONFORMANCE.md", "library/INDEX.md", "library/ALIAS.md",
    "community/README.md", "README.md", "README.en.md", "README.ja.md",
    "LICENSE", "CITATION.cff", "SECURITY.md", "CONTRIBUTING.md",
)
#: 「按任务选入口」表必须覆盖的任务类（少一类 = 有人找不到第一跳）
ROUTING_GOALS = ("装配", "选线", "取件", "菜单", "理解", "扩展", "查模块")


def section_body(text: str, heading: str) -> str:
    """取某小节正文（到下一个二级标题为止；缺标题返回空串）。"""
    if heading not in text:
        return ""
    return text.split(heading, 1)[1].split("\n## ", 1)[0]


def routing_rows(text: str) -> list:
    """「按任务选入口」表的数据行（去掉表头与分隔行）。"""
    body = section_body(text, "## 按任务选入口（最短路径）")
    rows = []
    for line in body.splitlines():
        s = line.strip()
        if s.startswith("|") and "---" not in s and "你要做什么" not in s:
            rows.append(s)
    return rows


def routing_issues(text: str) -> list:
    """机器入口完整性：第一跳面齐全 + 选入口表覆盖七类任务（纯函数，便于变异）。"""
    issues = []
    for rel in REQUIRED_ENTRIES:
        if rel not in text:
            issues.append("机器入口清单缺件：" + rel)
    rows = routing_rows(text)
    if len(rows) < 7:
        issues.append(f"按任务选入口少于 7 行（实测 {len(rows)} 行）")
    for goal in ROUTING_GOALS:
        if goal not in text:
            issues.append("选入口缺任务类：" + goal)
    return issues


def llms_issues(text: str, root: Path = ROOT, verify_text: str = None) -> list:
    return (url_issues(text, root) + path_issues(text, root)
            + citation_issues(text, verify_text) + live_count_issues(text)
            + shape_issues(text))


class LlmsContractTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_links_and_paths_resolve(self):
        self.assertGreaterEqual(url_count(self.text), 30, "直链过少（判据可能失效）")
        self.assertEqual([], url_issues(self.text), "直链指向不存在目标")
        self.assertEqual([], path_issues(self.text), "反引号路径不存在")

    def test_check_citations_are_accurate(self):
        issues = citation_issues(self.text)
        self.assertEqual([], [i for i in issues if "不存在" in i], "引用了不存在的检查")
        self.assertEqual([], [i for i in issues if "函数体" in i], "检查号与所声称的面不符")

    def test_no_pinned_runtime_counts(self):
        self.assertEqual([], live_count_issues(self.text), "活文本钉了运行时计数")

    def test_shape_and_generator_freshness(self):
        self.assertEqual([], shape_issues(self.text), "llms.txt 形态 / 必备入口缺失")
        self.assertTrue(stats_check_ok(), "nf stats --check 未通过（生成区与实算漂移）")

    def test_contract_catches_broken_llms(self):
        """变异自证：死直链 / 死路径 / 错检查号 / 硬编码计数必报；占位符与生成区计数不误报。"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "docs").mkdir()
            (root / "docs" / "ok.md").write_text("# ok\n", encoding="utf-8")
            base = "https://raw.githubusercontent.com/Monyeah777/NinFenz/main/docs/ok.md"
            self.assertEqual([], url_issues(base, root))
            dead = "https://raw.githubusercontent.com/Monyeah777/NinFenz/main/docs/gone.md"
            self.assertTrue(any("不存在" in i for i in url_issues(dead, root)))
            self.assertEqual([], path_issues(
                "取 " + TICK + "docs/" + "{路径}" + TICK, root))
        fake_verify = "\ncheck34(){\n  from core import locales\n}\n"
        self.assertTrue(any("不存在" in i for i in citation_issues(
            "见 check99", fake_verify)))
        self.assertTrue(any("函数体" in i for i in citation_issues(
            "见 check34 的 locales 扫描", "\ncheck34(){\n  echo other\n}\n")))
        self.assertTrue(any("运行时计数" in i for i in live_count_issues(
            "当前 conformance（27 契约报告 + 一致性声明）")))
        stats = (STATS_BEGIN + "\n- 质量凭证：verify v2.30 · check1-42 · PASS=76\n"
                 + STATS_END + "\n- 正常正文\n")
        self.assertEqual([], live_count_issues(stats))
        self.assertTrue(any("H1" in i for i in shape_issues("# 别的标题\n")))
        no_entry = self.text.replace("docs/nfal.md", "docs/nfal-gone.md")
        self.assertTrue(any("缺件" in i for i in routing_issues(no_entry)))
        no_table = self.text.replace("## 按任务选入口（最短路径）", "## 其他", 1)
        self.assertTrue(any("少于 7 行" in i for i in routing_issues(no_table)))

    def test_entry_coverage_complete(self):
        self.assertEqual([], routing_issues(self.text), "机器入口不完整")

    def test_task_router_table(self):
        self.assertGreaterEqual(len(routing_rows(self.text)), 7, "选入口表行数不足")
        self.assertIn("## 按任务选入口（最短路径）", self.text)



if __name__ == "__main__":
    unittest.main()
