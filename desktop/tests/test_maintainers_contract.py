#!/usr/bin/env python3
"""维护者契约判据：执行主体必须「具名、有职责、涉己回避、失能有预案」（2026-11-10）。

为什么必须有：COC 与 SECURITY.md 都写「Owner 经办」，但若维护者文档只有一行名字，
「谁裁决 / 谁复核 / Owner 自己被举报怎么办 / 失能怎么办」就全是空白——两处文档会各指一个人。
本件把 MAINTAINERS.md 钉成执行主体真源：点名 Owner、职责与不可代行面、回避路径、失能预案、晋升条件。

范围：只判 MAINTAINERS.md。同族判据：test_coc_contract（行为处置）、
test_security_contract（漏洞处置）、
test_support_contract（支持入口）。执行主体一致性用「COC ⇄ 本表」双向引用断言。
"""
import re
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MAINTAINERS = ROOT / "MAINTAINERS.md"
COC = ROOT / "CODE_OF_CONDUCT.md"

#: 必备段落（缺一段即执行主体说不清）
REQUIRED_SECTIONS = ("角色与职责", "单维护者", "成为维护者", "联系与响应", "权威性")
#: 必备要素（具名 / 两道经办 / 回避 / 失能 / 时限 / 边界）
REQUIRED_MARKERS = (
    "Owner", "CODE_OF_CONDUCT.md", "SECURITY.md", "外部第三方",
    "90 天", "只读", "7 天内", "不承诺 SLA", "bus factor", "归档", "默认放行", "公示",
)
#: 点名 Owner 的行（治理件判据也要求 `| Owner` 出现在表格里）
OWNER_ROW = re.compile(r"(?m)^\|\s*Owner")

_BACKTICK = re.compile(chr(96) + r"([^" + chr(96) + r"\n]+)" + chr(96))
_LINK = re.compile(r"\]\(([^)\s]+)\)")
_PATH_SHAPE = re.compile(r"^[A-Za-z0-9_./\-\u4e00-\u9fff]+$")
_PLACEHOLDER = ("*", "…", "<", ">")


def load_text(path: Path = MAINTAINERS) -> str:
    """读维护者文档（缺失 / 空件显式报错）。"""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"维护者文档不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("维护者文档为空")
    return text


def sections(text: str) -> dict:
    """二级标题 → 该段正文。"""
    out = {}
    current = None
    for line in text.splitlines():
        if line.startswith("## "):
            current = line[3:].strip()
            out[current] = []
        elif current is not None:
            out[current].append(line)
    return {title: "\n".join(body) for title, body in out.items()}


def find_section(secs: dict, keyword: str) -> str:
    """按标题关键词取段正文（缺段 → 空串）。"""
    for title, body in secs.items():
        if keyword in title:
            return body
    return ""


def dangling(text: str, root: Path = ROOT) -> list:
    """悬空的仓内引用：反引号路径与 Markdown 相对链接。"""
    bad = []
    for match in _BACKTICK.finditer(text):
        tok = match.group(1).strip()
        if "/" not in tok or not _PATH_SHAPE.match(tok):
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


def maintainer_issues(text: str, root: Path = ROOT) -> list:
    """维护者契约问题列表（纯函数，便于变异自证）。"""
    issues = []
    secs = sections(text)
    for key in REQUIRED_SECTIONS:
        if not find_section(secs, key).strip():
            issues.append(f"缺段落：{key}")
    for marker in REQUIRED_MARKERS:
        if marker not in text:
            issues.append(f"缺要素：{marker}")
    if not OWNER_ROW.search(text):
        issues.append("未在表格里点名 Owner（执行主体不具名）")
    coc = ""
    try:
        coc = (root / "CODE_OF_CONDUCT.md").read_text(encoding="utf-8")
    except OSError:
        issues.append("行为准则不在场：CODE_OF_CONDUCT.md")
    if coc and "MAINTAINERS.md" not in coc:
        issues.append("CODE_OF_CONDUCT.md 未指向本表（经办主体不一致）")
    for target in dangling(text, root):
        issues.append(f"仓内引用不存在：{target}（悬空引用）")
    return issues


class MaintainersContractTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_maintainers_matches_contract(self):
        self.assertEqual([], maintainer_issues(self.text), "维护者文档不满足契约")

    def test_execution_subject_is_single_sourced(self):
        """COC / SECURITY 的「谁经办」必须指回本表；本表点名 Owner 与不可代行面。"""
        self.assertIsNotNone(OWNER_ROW.search(self.text), "维护者表未点名 Owner")
        self.assertIn("CODE_OF_CONDUCT.md", self.text, "本表未指向行为准则")
        self.assertIn("SECURITY.md", self.text, "本表未指向安全通道")
        coc = COC.read_text(encoding="utf-8")
        self.assertIn("MAINTAINERS.md", coc, "行为准则未指向维护者名单")
        self.assertIn("外部第三方", self.text, "单维护者缺涉己回避的第三方路径")

    def test_links_resolve(self):
        """本表指向的仓内治理件必须可解析。"""
        self.assertEqual([], dangling(self.text), "维护者文档存在悬空的仓内引用")

    def test_contract_catches_broken_maintainers(self):
        """变异自证：删 Owner 行 / 删回避 / 去掉失能天数 / 悬空链接——都必须报。"""
        no_owner = self.text.replace("| Owner / Maintainer |", "| 维护者 |")
        self.assertTrue(any("Owner" in i for i in maintainer_issues(no_owner)),
                        "删掉 Owner 行必须报")
        no_recusal = self.text.replace("外部第三方", "另行讨论")
        self.assertTrue(any("外部第三方" in i for i in maintainer_issues(no_recusal)),
                        "删掉回避路径必须报")
        no_days = self.text.replace("90 天", "一段时间")
        self.assertTrue(any("90 天" in i for i in maintainer_issues(no_days)),
                        "去掉失能天数必须报")
        no_coc = self.text.replace("CODE_OF_CONDUCT.md", "行为准则")
        self.assertTrue(any("CODE_OF_CONDUCT.md" in i for i in maintainer_issues(no_coc)),
                        "删掉行为准则指针必须报")
        bad_link = self.text + "\n[示例](docs/nope.md)\n"
        self.assertTrue(any("docs/nope.md" in i for i in maintainer_issues(bad_link)),
                        "悬空链接必须报")
        with tempfile.TemporaryDirectory() as tmp:
            empty = Path(tmp) / "empty.md"
            empty.write_text("", encoding="utf-8")
            with self.assertRaises(ValueError):
                load_text(empty)
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_maintainers.md")


if __name__ == "__main__":
    unittest.main()
