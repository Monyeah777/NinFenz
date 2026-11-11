#!/usr/bin/env python3
"""全仓相对链接契约判据：markdown 链接 / 图片 / HTML href / 锚点都必须指向真件（2026-11-11）。

为什么必须有：仓库有 1192 个受跟踪 markdown 件、118 条相对链接，但只有 docs/ccos 一族的相对链接
有判据（test_ccos_docs_anchors 第 126 轮只覆盖该目录）。其余 1000+ 文档里的链接断了不会让任何测试
红，只会让读者点进 404。本轮实测命中一个真缺陷：community/西幻生存领域包 的资产档把伪代码调用写成
EXTERNAL_DATA[...](current_day) 且未用代码围栏包裹，在 GitHub 上会渲染成一个指向不存在的
current_day 的链接——正文没有反引号时，它就是坏链。

口径（防误报，逐条可自证）：
- 只判受跟踪 markdown（git ls-files 面，本地产物不参与）；
- 围栏代码块与行内代码围栏里的内容不算链接（伪代码大量出现在代码块里）；
- http(s) / mailto / 纯锚点（#xxx）不在本件范围（外链归外部链接巡检 workflow）；
- 相对目标须落在仓库内且真实存在（目录链接同样判）；
- 目标带 #anchor 时，按 GitHub slug 规则核对目标文件标题（当前仓内 0 条锚点链接，
  判据为防新增坏锚）。

同族判据：test_ccos_docs_anchors（docs/ccos 的代码锚点面）。
"""
import re
import subprocess
import tempfile
import unittest
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[2]
TICK = chr(96)
FENCE = TICK * 3
LINK_RE = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")
HREF_RE = re.compile(r"<a\s[^>]*href=\"([^\"]+)\"")
HEAD_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*$")
#: 面级 sanity：受跟踪 markdown 件数与相对链接数（低于此值说明扫描面失效）。
MIN_DOCS = 800
MIN_LINKS = 80


def strip_code(text: str) -> str:
    """去掉围栏代码块与行内代码围栏（伪代码里的 [x](y) 不是链接）。"""
    out, fenced = [], False
    for line in text.splitlines():
        head = line.lstrip()
        if head.startswith(FENCE) or head.startswith("~~~"):
            fenced = not fenced
            continue
        if fenced:
            continue
        out.append(re.sub(TICK + "[^" + TICK + "]*" + TICK, "", line))
    return "\n".join(out)


def split_target(raw: str) -> str:
    """去掉 markdown 目标里的 title 段与尖括号包装。"""
    target = raw.strip()
    if target.startswith("<") and ">" in target:
        return target[1:target.index(">")]
    parts = target.split()
    return parts[0] if parts else ""


def is_external(target: str) -> bool:
    return target.startswith(("http://", "https://", "mailto:", "tel:", "data:"))


def slugify(heading: str) -> str:
    """GitHub 标题 slug 的子集：小写 / 去标点 / 空格转连字符 / 保留 Unicode 字母数字与 -_。"""
    s = re.sub(r"<[^>]+>", "", heading).strip().lower()
    s = re.sub("[" + TICK + r"*_~\[\]()<>!]", "", s)
    out = []
    for ch in s:
        if ch.isalnum() or ch in "-_":
            out.append(ch)
        elif ch.isspace():
            out.append("-")
    return "".join(out)


def heading_slugs(rel: str, root: Path = ROOT) -> set:
    """目标文件的标题锚点集合（含重复标题的 -1/-2 后缀）。"""
    try:
        text = (root / rel).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return set()
    seen, slugs = {}, set()
    for line in strip_code(text).splitlines():
        m = HEAD_RE.match(line)
        if not m:
            continue
        base = slugify(m.group(2))
        if not base:
            continue
        if base in seen:
            seen[base] += 1
            slugs.add(base + "-" + str(seen[base]))
        else:
            seen[base] = 0
            slugs.add(base)
    return slugs


def link_issues(rel: str, text: str, root: Path = ROOT) -> list:
    """单个 markdown 件的链接问题列表（纯函数，便于变异自证）。"""
    issues = []
    body = strip_code(text)
    for raw in LINK_RE.findall(body) + HREF_RE.findall(body):
        target = split_target(raw)
        if not target or is_external(target) or target.startswith("#"):
            continue
        path, _, anchor = target.partition("#")
        path = unquote(path)
        if not path or path.startswith("/"):
            issues.append(rel + " → 链接必须是仓库内相对路径：" + target)
            continue
        resolved = (root / rel).parent / path
        try:
            resolved.resolve().relative_to(root.resolve())
        except ValueError:
            issues.append(rel + " → 链接逃出仓库：" + target)
            continue
        if not resolved.exists():
            issues.append(rel + " → 目标不存在：" + target)
            continue
        if anchor and resolved.is_file() and resolved.suffix.lower() == ".md":
            try:
                tgt = resolved.resolve().relative_to(root.resolve()).as_posix()
            except ValueError:
                continue
            if anchor.lower() not in {s.lower() for s in heading_slugs(tgt, root)}:
                issues.append(rel + " → 锚点不存在：" + target)
    return issues


def tracked_markdown(root: Path = ROOT) -> list:
    try:
        proc = subprocess.run(["git", "-C", str(root), "ls-files", "-z", "*.md"],
                              capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=180)
    except (OSError, subprocess.SubprocessError) as exc:
        raise ValueError("git ls-files 不可用：" + str(exc)) from exc
    return [p for p in proc.stdout.split("\0") if p.endswith(".md")]


def scan_all(root: Path = ROOT) -> tuple:
    """→ (issues, 受跟踪 md 件数, 相对链接数)。"""
    docs = tracked_markdown(root)
    issues, links = [], 0
    for rel in docs:
        try:
            text = (root / rel).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        body = strip_code(text)
        for raw in LINK_RE.findall(body) + HREF_RE.findall(body):
            target = split_target(raw)
            if target and not is_external(target) and not target.startswith("#"):
                links += 1
        issues.extend(link_issues(rel, text, root))
    return issues, len(docs), links


class DocLinksContractTest(unittest.TestCase):
    def setUp(self):
        self.issues, self.docs, self.links = scan_all()

    def test_relative_links_resolve(self):
        self.assertGreaterEqual(self.docs, MIN_DOCS, "受跟踪 markdown 面过小（判据可能失效）")
        self.assertGreaterEqual(self.links, MIN_LINKS, "相对链接过少（判据可能失效）")
        self.assertEqual([], self.issues[:10], "相对链接指向不存在的目标")

    def test_html_hrefs_are_covered(self):
        """README 等入口用 <a href> 做语言切换，必须与 markdown 链接同判。"""
        text = '<p><a href="README.en.md">English</a> <a href="missing.md">x</a></p>'
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "README.en.md").write_text("# x\n", encoding="utf-8")
            issues = link_issues("README.md", text, Path(tmp))
            self.assertEqual(1, len(issues), issues)
            self.assertIn("missing.md", issues[0])

    def test_anchor_slugs_follow_github_rules(self):
        """锚点判据的自证：GitHub slug 对中文 / 编号 / 代码 / 重复标题的规则。"""
        self.assertEqual("hello-world", slugify("Hello World"))
        self.assertEqual("中文-标题", slugify("中文 标题"))
        self.assertEqual("1-step-one", slugify("1. Step One"))
        self.assertEqual("code-name", slugify(TICK + "code" + TICK + " name"))
        doc = "# A\n## A\n## A\n"
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "t.md"
            target.write_text(doc, encoding="utf-8")
            self.assertEqual({"a", "a-1", "a-2"}, heading_slugs("t.md", Path(tmp)))

    def test_code_spans_are_not_links(self):
        """负向对照：代码围栏 / 行内代码里的 [x](y) 不是链接（伪代码大量出现）。"""
        text = (FENCE + "\n[not](a-link.md)\n" + FENCE + "\n"
                "行内 " + TICK + "[not](b-link.md)" + TICK + " 也不算。\n")
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual([], link_issues("x.md", text, Path(tmp)))

    def test_contract_catches_broken_links(self):
        """变异自证：缺文件 / 逃出仓库 / 坏锚点 / 绝对路径都必报；有效件不误报。"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "docs").mkdir()
            (root / "docs" / "ok.md").write_text("# Good Title\n", encoding="utf-8")
            (root / "README.md").write_text("[ok](docs/ok.md)\n", encoding="utf-8")
            good = (root / "README.md").read_text(encoding="utf-8")
            self.assertEqual([], link_issues("README.md", good, root))
            self.assertTrue(any("目标不存在" in i for i in link_issues(
                "README.md", "[x](docs/none.md)", root)))
            self.assertTrue(any("逃出仓库" in i for i in link_issues(
                "README.md", "[x](../outside.md)", root)))
            self.assertTrue(any("锚点不存在" in i for i in link_issues(
                "README.md", "[x](docs/ok.md#no-such-heading)", root)))
            self.assertEqual([], link_issues("README.md", "[x](docs/ok.md#good-title)", root))
            self.assertTrue(any("相对路径" in i for i in link_issues(
                "README.md", "[x](/etc/passwd)", root)))


if __name__ == "__main__":
    unittest.main()
