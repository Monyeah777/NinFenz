#!/usr/bin/env python3
"""扫描面契约判据：判据不得自持「仓库根递归扫描面」（2026-11-11，L4 元判据）。

为什么必须有：本会话连续修了三处同类缺陷——test_ci_diagnostics 的 Dockerfile 面、test_version_map 的
治理 markdown 面、test_text_hygiene 的 markdown 面——都是「判据自己 rglob 仓库根 + 自持排除表」，
后果一致：本地未跟踪快照（.rivet / .worktrees）把面放大到 66547 件、拖慢 13 秒、还可能把工作树副本
当成待检内容。这类缺陷靠人记不可靠；把「扫描面必须走 core.repo_face 单点定义或 git 追踪面」写成
棘轮，新增自持根扫描即红。

判定口径（只判**仓库根递归**，不误伤锚定 glob）：
- ROOT.rglob(…) / Path(ROOT).rglob(…) —— 根递归，红；
- os.walk(ROOT …) —— 根递归，红；
- Path(ROOT).glob("**…") —— 首段通配的递归，红；
- Path(ROOT).glob("community/*/modules/*.md") 这类**锚定** pattern 不红（pathlib 只进该目录）。
字符串与注释里的历史叙述（如「原实现为 ROOT.rglob(…)」）不算代码，用 tokenize 跳过。

例外登记：ALLOWED = {文件相对路径: 理由}；当前为空——真要根递归请先走 core.repo_face。
范围：只判**判据代码**（desktop/tests/**.py 与 scripts/*.py）。core/ 是单点实现所在地，不在面内。
"""
import io
import re
import subprocess
import tempfile
import tokenize
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
#: 例外登记（当前为空）；键 = 仓库相对路径，值 = 理由。
ALLOWED = {}
#: 根递归扫描形态（命中即红）。
PATTERNS = (
    re.compile(r"\bROOT\.rglob\s*\("),
    re.compile(r"Path\(\s*ROOT\s*\)\.rglob\s*\("),
    re.compile(r"os\.walk\(\s*ROOT\b"),
    re.compile(r"Path\(\s*ROOT\s*\)\.glob\(\s*[^)]*\*\*"),
)
#: 判据代码扫描面（core/ 是单点实现所在地，不判）。
SCAN_GLOBS = ("desktop/tests/*.py", "scripts/*.py")


def tracked(globs=SCAN_GLOBS, root: Path = ROOT) -> list:
    try:
        proc = subprocess.run(["git", "-C", str(root), "ls-files", "-z", *globs],
                              capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=180)
    except (OSError, subprocess.SubprocessError) as exc:
        raise ValueError("git ls-files 不可用：" + str(exc)) from exc
    return sorted(p for p in proc.stdout.split(chr(0)) if p)


def _string_ranges(text: str) -> list:
    """→ [((起始行, 起始列), (结束行, 结束列))]：字符串 / 注释 token 的精确范围。

    只按行号跳过会把「同一个表达式里含字符串」的代码行也一起放过（实测：合成样例
    ROOT.rglob("*.md") 里的 *.md 是字符串 token，整行被跳过 → 判据自身空转）。
    """
    ranges = []
    try:
        for tok in tokenize.generate_tokens(io.StringIO(text).readline):
            if tok.type in (tokenize.STRING, tokenize.COMMENT):
                ranges.append((tok.start, tok.end))
    except (tokenize.TokenError, IndentationError):
        return []
    return ranges


def _in_ranges(pos: tuple, ranges: list) -> bool:
    line, col = pos
    for (sline, scol), (eline, ecol) in ranges:
        if sline == eline and line == sline and scol <= col < ecol:
            return True
        if sline < line < eline:
            return True
        if line == sline and line != eline and col >= scol:
            return True
        if line == eline and line != sline and col < ecol:
            return True
    return False


def risky_scans(text: str) -> list:
    """→ [(行号, 命中形态)]；跳过落在字符串 / 注释 token 内的命中。"""
    ranges = _string_ranges(text)
    hits = []
    for lineno, line in enumerate(text.splitlines(), 1):
        for pattern in PATTERNS:
            m = pattern.search(line)
            if m and not _in_ranges((lineno, m.start()), ranges):
                hits.append((lineno, m.group(0)))
    return hits



def scan_issues(root: Path = ROOT, files: list = None) -> list:
    """全仓判据代码的自持根扫描问题列表。"""
    issues = []
    files = tracked(root=root) if files is None else list(files)
    if len(files) < 100:
        issues.append("判据代码扫描面过小（" + str(len(files)) + "），判据可能已失效")
    for rel in files:
        if rel in ALLOWED:
            continue
        path = root / rel
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for lineno, hit in risky_scans(text):
            issues.append(rel + ":" + str(lineno) + " 自持根递归扫描面（应走 core.repo_face / "
                          "git 追踪面）：" + hit)
    return issues


class ScanSurfaceContractTest(unittest.TestCase):
    def test_no_judgment_scans_repo_root_recursively(self):
        self.assertEqual([], scan_issues(), "判据代码里存在自持根递归扫描面")

    def test_scan_surface_is_not_collapsed(self):
        files = tracked()
        self.assertGreaterEqual(len(files), 100, "判据代码面塌缩")

    def test_contract_catches_self_held_root_scan(self):
        """变异自证：rglob / os.walk(ROOT) / ** glob 必报；字符串叙述与锚定 glob 不误报。"""
        bad = ("import os\n"
               "for p in ROOT.rglob('*.md'):\n"
               "    pass\n")
        self.assertTrue(risky_scans(bad), "ROOT.rglob 必须被抓")
        walk = "import os\nfor d, _, fs in os.walk(ROOT):\n    pass\n"
        self.assertTrue(risky_scans(walk), "os.walk(ROOT) 必须被抓")
        star = "for p in Path(ROOT).glob('**/*.md'):\n    pass\n"
        self.assertTrue(risky_scans(star), "Path(ROOT).glob('**…') 必须被抓")
        history = '"""历史：原实现为 ROOT.rglob("*.md") + 事后过滤。"""\n'
        self.assertEqual([], risky_scans(history), "字符串里的历史叙述不该误报")
        anchored = "for p in Path(ROOT).glob('community/*/modules/*.md'):\n    pass\n"
        self.assertEqual([], risky_scans(anchored), "锚定 glob 不该误报")
        with tempfile.TemporaryDirectory() as tmp:
            empty_root = Path(tmp)
            (empty_root / "bad.py").write_text(bad, encoding="utf-8")
            issues = scan_issues(empty_root, ["bad.py"])
            self.assertTrue(any("自持根递归" in i for i in issues))


if __name__ == "__main__":
    unittest.main()
