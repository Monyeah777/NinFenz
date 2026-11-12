#!/usr/bin/env python3
"""docs/agent/ROUTES.md 契约判据：路由后缀必须指向真件，死指针与死命令零容忍（2026-11-11）。

为什么必须有：ROUTES 是「AI 接待员」的导购中枢——它说「按 README B2 协议卡创作」，接待员就会去找；
而 README 的 B2 段与 📚 图书馆段早已按 2026-09-07 作者裁决移出主文档（docs/paste_card.md 自己写着
「历史真相源：README B2 段（v0.3，2026-09-07 免除时移出主文档）」）。死指针不会让任何测试红，只会
让接待员当场编造或空转。本轮实测命中 3 处：README 上不存在的 📚 图书馆段、README B2 协议卡 ×2。

判据（逐条可自证）：
1. 反引号里的仓库路径（带文件扩展名，或首段是真实顶层目录）必须存在；裸文件名按本文件的资源别名
   表解析（INDEX.md / ALIAS.md → library/ 下的真件）；
2. 第二节 URL 示例表的 raw / blob / tree 形态里 {路径} 必须指向受跟踪真件（占位符跳过），且两种
   镜像前缀与四种路由形态成对出现（换镜像 = 只换前缀的纪律可核）；
3. 机器面声明必须真存在：nf library search 子命令、MCP library_search / library_read 工具、
   nf://repo/library/{id} 资源模板、.github/ISSUE_TEMPLATE/NF投稿.md；
4. 跨文档指针必须指向仍承载该内容的文件：B2 协议卡 → docs/paste_card.md（不得指 README），
   📚 图书馆段 → library/INDEX.md（不得指 README）；
5. Gitee 刻意空置声明可核（.gitee/ISSUE_TEMPLATE 除 .gitkeep 外为空）。

范围：只判 docs/agent/ROUTES.md。同族判据：test_doc_links_contract（全仓链接）、
test_library_ingest_script_contract（投稿面）、test_mcp_runtime（机器面）。
"""
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ROUTES = ROOT / "docs" / "agent" / "ROUTES.md"
README = ROOT / "README.md"
PASTE_CARD = ROOT / "docs" / "paste_card.md"
MCP_SOURCE = ROOT / "desktop" / "src" / "core" / "mcp_runtime.py"
TICK = chr(96)
#: 本文件对裸文件名的资源别名（ROUTES 里的 INDEX.md 指馆藏目录，不是同名其它 INDEX）。
BARE_ALIASES = {"INDEX.md": "library/INDEX.md", "ALIAS.md": "library/ALIAS.md"}
#: 可核的镜像前缀 × 路由形态成对（GitHub raw 走 raw.githubusercontent.com，不是 github.com/raw）。
FORMS = (
    "github.com/Monyeah777/NinFenz/blob/main/",
    "github.com/Monyeah777/NinFenz/tree/main/",
    "raw.githubusercontent.com/Monyeah777/NinFenz/main/",
    "gitee.com/monyeah777/ninfenz/blob/main/",
    "gitee.com/monyeah777/ninfenz/raw/main/",
    "gitee.com/monyeah777/ninfenz/tree/main/",
)
PATH_RE = re.compile(r"^[A-Za-z0-9_.\-/]+\.(?:md|json|txt|py|yml|yaml|sh|mjs|toml|cff)$")

URL_RE = re.compile(r"https://(?:github\.com|gitee\.com)/[^\s)|\]" + TICK + r"]+")


def load_text(path: Path = ROUTES) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError("ROUTES 不可读：" + str(exc)) from exc
    if not text.strip():
        raise ValueError("ROUTES 为空")
    return text


def tracked(root: Path = ROOT) -> list:
    try:
        proc = subprocess.run(["git", "-C", str(root), "ls-files", "-z"],
                              capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=180)
    except (OSError, subprocess.SubprocessError) as exc:
        raise ValueError("git ls-files 不可用：" + str(exc)) from exc
    return [p for p in proc.stdout.split("\x00") if p]


def top_dirs(root: Path = ROOT) -> set:
    return {p.split("/", 1)[0] for p in tracked(root) if "/" in p}


def tick_tokens(text: str) -> list:
    return [t.strip() for t in re.findall(TICK + "([^" + TICK + "\n]+)" + TICK, text)]


def path_issues(text: str, root: Path = ROOT) -> list:
    """反引号里的仓库路径 / 资源别名必须存在。"""
    issues = []
    dirs = top_dirs(root)
    for token in tick_tokens(text):
        if not token or " " in token or token.startswith(("http", "nf://", "issues/")):
            continue
        if "{" in token or "}" in token:
            continue
        if token in BARE_ALIASES:
            if not (root / BARE_ALIASES[token]).exists():
                issues.append("裸名别名指向不存在：" + token + " -> " + BARE_ALIASES[token])
            continue
        first = token.rstrip("/").split("/", 1)[0]
        if ((PATH_RE.match(token) or first in dirs)
                and not (root / token.rstrip("/")).exists()):
            issues.append("路由指向不存在的路径：" + token)
    return issues


def url_issues(text: str, root: Path = ROOT) -> list:
    """第二节 URL 示例的 {路径} 必须真存在；镜像前缀与形态必须成对。"""
    issues = []
    for raw in URL_RE.findall(text):
        url = raw.rstrip(TICK + ".,;:)")
        m = re.search(r"/(blob|raw|tree)/main/(.+)$", url)
        if not m:
            continue
        rel = m.group(2)
        if "{" in rel or "}" in rel:
            continue
        if not (root / rel.rstrip("/")).exists():
            issues.append("路由示例指向不存在的路径：" + url)
    for form in FORMS:
        if form not in text:
            issues.append("镜像 / 形态成对缺失：" + form)
    return issues


def surface_issues(text: str, root: Path = ROOT, mcp_text: str = None,
                   cli_ok: bool = None) -> list:
    """机器面声明（CLI / MCP / 资源模板 / 投稿模板 / Gitee 空置）必须真存在。"""
    issues = []
    if mcp_text is None:
        mcp_text = (root / "desktop" / "src" / "core" / "mcp_runtime.py").read_text(
            encoding="utf-8")
    if cli_ok is None:
        try:
            proc = subprocess.run([sys.executable, str(root / "scripts" / "nf.py"),
                                   "library", "search", "--help"],
                                  capture_output=True, timeout=120, check=False)
            cli_ok = proc.returncode == 0
        except (OSError, subprocess.SubprocessError):
            cli_ok = False
    if "nf library search" in text and not cli_ok:
        issues.append("声明了 nf library search，但该子命令不可用")
    for tool in ("library_search", "library_read"):
        needle = '"name": "' + tool + '"'
        if tool in text and needle not in mcp_text:
            issues.append("声明了 MCP 工具，但运行时不存在：" + tool)
    if "nf://repo/library/" in text and "nf://repo/library/{id}" not in mcp_text:
        issues.append("声明了 nf://repo/library/{id} 资源模板，但 MCP 运行时没有该模板")
    template = root / ".github" / "ISSUE_TEMPLATE" / "NF投稿.md"
    if "NF投稿.md" in text and not template.is_file():
        issues.append("投稿模板路径不存在：.github/ISSUE_TEMPLATE/NF投稿.md")
    if "刻意空置" in text:
        gitee = root / ".gitee" / "ISSUE_TEMPLATE"
        extra = ([p.name for p in gitee.glob("*") if p.name != ".gitkeep"]
                 if gitee.is_dir() else ["<缺目录>"])
        if extra:
            issues.append("Gitee 投稿模板声明「刻意空置」，实际有件：" + repr(extra))
    return issues


def crossref_issues(text: str, root: Path = ROOT) -> list:
    """跨文档指针必须指向仍承载该内容的文件（README 已移出 B2 段与图书馆段）。"""
    issues = []
    if "README.md" + TICK + "（⚡ AI 入口段 + 📚" in text:
        issues.append("README 已无 📚 图书馆段，仍把该段归到 README")
    if "README B2 协议卡" in text or "README.md" + TICK + " B2" in text:
        issues.append("B2 段已移出 README，仍指向 README")
    if "B2 协议卡" in text and "docs/paste_card.md" not in text:
        issues.append("B2 协议卡现存件是 docs/paste_card.md，指针缺失")
    if "📚 图书馆段" in text and "library/INDEX.md" not in text:
        issues.append("📚 图书馆段现存件是 library/INDEX.md，指针缺失")
    readme = (root / "README.md").read_text(encoding="utf-8")
    if "⚡ AI 入口段" in text and not re.search(r"^## ⚡.*AI", readme, re.M):
        issues.append("README 已无 ⚡ AI 入口段，指针漂移")
    return issues


def route_issues(text: str, root: Path = ROOT, mcp_text: str = None,
                 cli_ok: bool = None) -> list:
    return (path_issues(text, root) + url_issues(text, root)
            + surface_issues(text, root, mcp_text, cli_ok) + crossref_issues(text, root))

#: 九段结构（缺一段即某一类接待动作断链）
REQUIRED_SECTIONS = ("## 〇、什么时候用本文件", "## 一、镜像前缀", "## 二、功能后缀路由表",
                     "## 三、机器面优先", "## 四、接待菜单", "## 五、接待决策流",
                     "## 六、出库前自检", "## 七、停止条件", "## 八、行动铁律")
#: 导购红线与实测边界（少一条就有人踩）
REQUIRED_MARKERS = ("馆线", "换镜像 = 只换前缀", "405/401", "严禁编造",
                    "不得声称「已入库」", "library_submission.md", "NF投稿.md",
                    "B2", "机器面优先", "出库前自检", "停止条件")
#: 接待决策流 A-H（少一行就是一类需求没人接）
DECISION_ROWS = tuple("| " + ch + ". " for ch in "ABCDEFGH")
#: raw 基底（喂 AI 的两种镜像形态，host / 大小写 / 分支须一致）
RAW_BASES = ("https://raw.githubusercontent.com/Monyeah777/NinFenz/main/",
             "https://gitee.com/monyeah777/ninfenz/raw/main/")


def iron_rule_count(text: str) -> int:
    """「行动铁律」段里的编号条目数。"""
    if "## 八、行动铁律" not in text:
        return 0
    body = text.split("## 八、行动铁律", 1)[1]
    return sum(1 for ln in body.splitlines()
               if "." in ln.strip() and ln.strip().split(".", 1)[0].isdigit())


def structure_issues(text: str) -> list:
    """九段结构 / 红线要素 / 决策流逐行 / 五条菜单 / 十二条铁律（纯函数，便于变异）。"""
    issues = []
    for section in REQUIRED_SECTIONS:
        if section not in text:
            issues.append("缺段落：" + section)
    for marker in REQUIRED_MARKERS:
        if marker not in text:
            issues.append("缺要素：" + marker)
    for row in DECISION_ROWS:
        if row not in text:
            issues.append("接待决策流缺行：" + row.strip())
    for mark in ("①", "②", "③", "④", "⑤"):
        if mark not in text:
            issues.append("接待菜单缺项：" + mark)
    if iron_rule_count(text) < 12:
        issues.append("行动铁律不足 12 条")
    return issues


def prefix_issues(text: str) -> list:
    """raw 基底 / 分支 / 仓库名大小写一致性（纯函数，便于变异）。"""
    issues = []
    for base in RAW_BASES:
        if base not in text:
            issues.append("缺 raw 基底：" + base)
    if "master/" in text:
        issues.append("镜像前缀用了 master/（本仓默认分支应为 main/）")
    if "gitee.com/Monyeah777/NinFenz" in text or "gitee.com/Monyeah777/ninfenz" in text:
        issues.append("Gitee 仓库名大小写混用（应为 monyeah777/ninfenz）")
    if "github.com/monyeah777/ninfenz" in text:
        issues.append("GitHub 仓库名小写（应为 Monyeah777/NinFenz）")
    return issues


class RoutesContractTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_paths_and_url_examples_exist(self):
        self.assertEqual([], path_issues(self.text), "路由路径指向不存在目标")
        self.assertEqual([], url_issues(self.text), "URL 示例 / 镜像形态不成对")

    def test_machine_surfaces_exist(self):
        issues = surface_issues(self.text)
        self.assertEqual([], [i for i in issues
                              if "nf library search" in i or "MCP" in i or "资源模板" in i])
        self.assertEqual([], [i for i in issues if "投稿" in i or "空置" in i])
        self.assertTrue(PASTE_CARD.is_file(), "B2 协议卡现存件 docs/paste_card.md 缺失")

    def test_cross_document_pointers_are_live(self):
        self.assertEqual([], crossref_issues(self.text), "跨文档指针已死")
        self.assertIn("B2", PASTE_CARD.read_text(encoding="utf-8"), "paste_card 应承载 B2 模板")

    def test_route_issues_finds_nothing(self):
        self.assertEqual([], route_issues(self.text), "ROUTES 不满足契约")

    def test_contract_catches_broken_routes(self):
        """变异自证：死路径 / 死 URL / 假 MCP 工具 / 死指针必须报；占位符与正指针不误报。"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "library").mkdir()
            (root / "library" / "INDEX.md").write_text("# i\n", encoding="utf-8")
            broken = "读 " + TICK + "library/GONE.md" + TICK
            self.assertTrue(any("不存在" in i for i in path_issues(broken, root)))
            self.assertEqual([], path_issues(
                "读 " + TICK + "library/" + "{编号}" + ".md" + TICK, root))
            self.assertEqual([], path_issues(TICK + "INDEX.md" + TICK, root))
            ok_url = "https://gitee.com/monyeah777/ninfenz/raw/main/library/INDEX.md"
            bad_url = "https://gitee.com/monyeah777/ninfenz/raw/main/library/GONE.md"
            self.assertTrue(any("不存在的路径" in i for i in url_issues(bad_url, root)))
            self.assertTrue(any("成对缺失" in i for i in url_issues(ok_url, root)))
        self.assertTrue(any("MCP 工具" in i for i in surface_issues(
            "用 library_search", mcp_text="", cli_ok=True)))
        self.assertTrue(any("资源模板" in i for i in surface_issues(
            "取 nf://repo/library/{id}", mcp_text="", cli_ok=True)))
        self.assertTrue(any("B2 段" in i for i in crossref_issues(
            "按 README B2 协议卡创作")))
        self.assertTrue(any("📚 图书馆段" in i for i in crossref_issues(
            "见 README.md" + TICK + "（⚡ AI 入口段 + 📚 图书馆段）")))
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "README.md").write_text("## ⚡ 如果你是 AI / Agent\n", encoding="utf-8")
            good = ("按 " + TICK + "docs/paste_card.md" + TICK + " 的 B2 协议卡创作；"
                    "见 " + TICK + "library/INDEX.md" + TICK + "（📚 图书馆段）")
            self.assertEqual([], crossref_issues(good, root))

    def test_structure_and_decision_flow(self):
        self.assertEqual([], structure_issues(self.text), "ROUTES 结构 / 决策流不完整")

    def test_prefix_branch_and_case(self):
        self.assertEqual([], prefix_issues(self.text), "镜像前缀分支 / 大小写不一致")

    def test_structure_predicate_catches_mutations(self):
        """变异自证：分支漂移 / 大小写混搭 / 删红线 / 决策流缺行必须报。"""
        tick = chr(96)
        self.assertTrue(any("master" in i
                            for i in prefix_issues(self.text.replace("/main/", "/master/"))))
        mixed = self.text + "\n镜像：" + tick
        mixed += "https://gitee.com/Monyeah777/NinFenz/raw/main/README.md" + tick + "\n"
        self.assertTrue(any("大小写" in i for i in prefix_issues(mixed)))
        no_redline = self.text.replace("严禁编造", "尽量准确")
        self.assertTrue(any("严禁编造" in i for i in structure_issues(no_redline)))
        no_row = self.text.replace("| H. ", "| H  ")
        self.assertTrue(any("接待决策流缺行" in i for i in structure_issues(no_row)))


if __name__ == "__main__":
    unittest.main()
