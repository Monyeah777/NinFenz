#!/usr/bin/env python3
"""安全策略契约判据：报告通道必须「分类清楚、模板可给、时限与披露可判」（2026-11-10）。

为什么必须有：安全策略最容易被写成「请走私密通道」一句话——没有报告模板（来回答）、没有分类分工
（行为举报被当漏洞退回）、没有确认与披露口径（无限期拖）。这些缺失不会让任何测试红，
而 SECURITY.md 是 OpenSSF Scorecard 的 Security-Policy 信号面，也是用户第一跳。

范围：只判 SECURITY.md。同族判据：test_coc_contract（行为通道）、test_support_contract（支持入口）、
test_issue_form_contract（入口配置）。通道分工用「SECURITY ⇄ COC 双向引用」断言。
"""
import re
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SECURITY = ROOT / "SECURITY.md"
COC = ROOT / "CODE_OF_CONDUCT.md"
CONFIG = ROOT / ".github" / "ISSUE_TEMPLATE" / "config.yml"

#: 必备段落（缺一段即报告链断一环）
REQUIRED_SECTIONS = ("私密报告", "范围内", "范围外", "处理口径", "安全机制", "信任边界")
#: 必备要素（分类分工 / 模板 / 时限 / 披露 / 致谢 / 赏金边界）
REQUIRED_MARKERS = (
    "Security Advisories", "不要", "公开 Issue", "CODE_OF_CONDUCT.md", "SUPPORT.md",
    "7 天内", "90 天", "协调披露", "CVE", "致谢", "无赏金", "报告模板",
)
#: 报告模板六项（缺项评审就得来回追问）
TEMPLATE_KEYS = ("影响面", "复现", "期望", "可利用性", "已尝试修复", "署名")

_BACKTICK = re.compile(chr(96) + r"([^" + chr(96) + r"\n]+)" + chr(96))
_LINK = re.compile(r"\]\(([^)\s]+)\)")
_PATH_SHAPE = re.compile(r"^[A-Za-z0-9_./\-\u4e00-\u9fff]+$")
_PLACEHOLDER = ("*", "…", "<", ">")


def load_text(path: Path = SECURITY) -> str:
    """读安全策略（缺失 / 空件显式报错）。"""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"安全策略不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("安全策略为空")
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


def repo_path_tokens(text: str) -> list:
    """反引号内的仓内路径记号（过滤 URL / 占位符 / 含空格或通配者）。"""
    out = []
    for match in _BACKTICK.finditer(text):
        tok = match.group(1).strip()
        if "/" not in tok or not _PATH_SHAPE.match(tok):
            continue
        if any(ch in tok for ch in _PLACEHOLDER) or tok.startswith("http"):
            continue
        out.append(tok)
    return out


def dangling(text: str, root: Path = ROOT) -> list:
    """悬空的仓内引用：反引号路径与 Markdown 相对链接。"""
    bad = [tok for tok in repo_path_tokens(text)
           if not (root / tok.rstrip("/")).exists()]
    for match in _LINK.finditer(text):
        target = match.group(1).strip()
        if target.startswith(("http://", "https://", "#", "mailto:")):
            continue
        rel = target.split("#")[0]
        if rel and not (root / rel).exists():
            bad.append(target)
    return bad


def security_issues(text: str, root: Path = ROOT) -> list:
    """安全策略契约问题列表（纯函数，便于变异自证）。"""
    issues = []
    secs = sections(text)
    for key in REQUIRED_SECTIONS:
        if not find_section(secs, key).strip():
            issues.append(f"缺段落：{key}")
    for marker in REQUIRED_MARKERS:
        if marker not in text:
            issues.append(f"缺要素：{marker}")
    report = find_section(secs, "私密报告")
    for key in TEMPLATE_KEYS:
        if key not in report:
            issues.append(f"报告模板缺项：{key}")
    coc = ""
    try:
        coc = (root / "CODE_OF_CONDUCT.md").read_text(encoding="utf-8")
    except OSError:
        issues.append("行为准则不在场：CODE_OF_CONDUCT.md")
    if coc and "SECURITY.md" not in coc:
        issues.append("CODE_OF_CONDUCT.md 未指向本通道（通道分工单向）")
    config = ""
    try:
        config = (root / ".github" / "ISSUE_TEMPLATE" / "config.yml").read_text(encoding="utf-8")
    except OSError:
        issues.append("入口配置不在场：config.yml")
    if config and "/security/advisories/new" not in config:
        issues.append("入口配置缺私密安全直达链接")
    for target in dangling(text, root):
        issues.append(f"仓内引用不存在：{target}（悬空引用）")
    return issues


class SecurityPolicyContractTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_security_matches_contract(self):
        self.assertEqual([], security_issues(self.text), "安全策略不满足契约")

    def test_channels_are_mutually_declared(self):
        """三条通道互不代收：本件指向 COC/SUPPORT，COC 反向指向本件。"""
        self.assertIn("CODE_OF_CONDUCT.md", self.text, "本件未把行为举报指回 COC")
        self.assertIn("SUPPORT.md", self.text, "本件未把使用问题指回 SUPPORT")
        coc = (ROOT / "CODE_OF_CONDUCT.md").read_text(encoding="utf-8")
        self.assertIn("SECURITY.md", coc, "COC 未声明与安全通道的分工")
        self.assertIn("/security/advisories/new", self.text, "缺私密直达地址")

    def test_links_resolve(self):
        """策略里指向的仓内文档（COC / SUPPORT / CONTRIBUTING / 机制载体）必须可解析。"""
        self.assertEqual([], dangling(self.text), "安全策略存在悬空的仓内引用")

    def test_contract_catches_broken_policy(self):
        """变异自证：删范围外 / 去掉 90 天 / 删模板 / 悬空链接——都必须报。"""
        no_scope = self.text.replace("## 三、范围外（OUT OF SCOPE）", "## 三、附注")
        self.assertTrue(any("范围外" in i for i in security_issues(no_scope)),
                        "删掉范围外必须报")
        no_deadline = self.text.replace("90 天", "视情况")
        self.assertTrue(any("90 天" in i for i in security_issues(no_deadline)),
                        "去掉协调披露时限必须报")
        no_template = self.text.replace("报告模板", "报告说明")
        self.assertTrue(any("报告模板" in i for i in security_issues(no_template)),
                        "删掉报告模板必须报")
        bad_link = self.text + "\n[示例](docs/nope.md)\n"
        self.assertTrue(any("docs/nope.md" in i for i in security_issues(bad_link)),
                        "悬空链接必须报")
        with tempfile.TemporaryDirectory() as tmp:
            empty = Path(tmp) / "empty.md"
            empty.write_text("", encoding="utf-8")
            with self.assertRaises(ValueError):
                load_text(empty)
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_security.md")


if __name__ == "__main__":
    unittest.main()
