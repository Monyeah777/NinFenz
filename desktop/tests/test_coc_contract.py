#!/usr/bin/env python3
"""行为准则契约判据：违规处置必须「通道清楚、档位可判、申诉有门」（2026-11-10）。

为什么必须有：行为准则是最容易被写成「我们倡导友善」的治理件——关键词齐全但无可执行内容。
本仓此前把行为举报指向安全通报，而 SECURITY.md 又把纯内容合规列为范围外（同一通道自我否认），
这类矛盾不会有任何测试变红。本件把「可执行的 COC」钉成契约：
通道分工、四档、时限、申诉、回避逐项可判。

范围：只判 CODE_OF_CONDUCT.md。同族判据：test_governance_docs（治理件在场与语义）、
test_support_contract（支持入口）、test_issue_form_contract（表单）。
"""
import re
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
COC = ROOT / "CODE_OF_CONDUCT.md"
MAINTAINERS = ROOT / "MAINTAINERS.md"

#: 必备段落（缺一段即处置链断一环）
REQUIRED_SECTIONS = ("承诺", "期望行为", "不接受", "举报", "处置", "申诉", "适用范围")
#: 必备要素（研究对齐：受保护属性 / 代表本项目 / 保密 / 报复 / 恶意举报 / 回避 / 第三方复核）
REQUIRED_MARKERS = (
    "受保护属性", "代表本项目", "私密通报", "保密", "报复", "恶意举报",
    "回避", "外部第三方", "受理归属", "匿名",
)
#: 四档处置（缺一档即「尺度随意」）
TIERS = ("私下纠正", "书面警告", "暂时封禁", "永久封禁")
#: 两个时限（确认 / 申诉）；只承诺「流程确认」，不承诺处理时限
TIMING = (("7 天内", "确认时限"), ("14 天内", "申诉时限"))

_BACKTICK = re.compile(chr(96) + r"([^" + chr(96) + r"\n]+)" + chr(96))
_LINK = re.compile(r"\]\(([^)\s]+)\)")
_PATH_SHAPE = re.compile(r"^[A-Za-z0-9_./\-\u4e00-\u9fff]+$")
_PLACEHOLDER = ("*", "…", "<", ">")


def load_text(path: Path = COC) -> str:
    """读行为准则（缺失 / 空件显式报错，不静默跳过）。"""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"行为准则不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("行为准则为空")
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


def markdown_targets(text: str) -> list:
    """Markdown 链接目标清单。"""
    return [match.group(1).strip() for match in _LINK.finditer(text)]


def dangling(text: str, root: Path = ROOT) -> list:
    """悬空的仓内引用：反引号路径与 Markdown 相对链接，目标必须存在。"""
    bad = [tok for tok in repo_path_tokens(text)
           if not (root / tok.rstrip("/")).exists()]
    for target in markdown_targets(text):
        if target.startswith(("http://", "https://", "#", "mailto:")):
            continue
        rel = target.split("#")[0]
        if rel and not (root / rel).exists():
            bad.append(target)
    return bad


def coc_issues(text: str, root: Path = ROOT) -> list:
    """行为准则契约问题列表（纯函数，便于变异自证）。"""
    issues = []
    secs = sections(text)
    for key in REQUIRED_SECTIONS:
        if not find_section(secs, key).strip():
            issues.append(f"缺段落：{key}")
    for marker in REQUIRED_MARKERS:
        if marker not in text:
            issues.append(f"缺要素：{marker}")
    for tier in TIERS:
        if tier not in text:
            issues.append(f"处置档位缺失：{tier}")
    for needle, label in TIMING:
        if needle not in text:
            issues.append(f"缺时限：{label}（{needle}）")
    if "SECURITY.md" not in text:
        issues.append("未声明与 SECURITY.md 的通道分工")
    if "受理归属" not in text:
        issues.append("未声明行为举报的受理归属（否则会被「不是漏洞」退回）")
    if "公开 Issue" not in text or "不要" not in text:
        issues.append("未写明「不要在公开 Issue 举报」")
    maintainers = ""
    try:
        maintainers = (root / "MAINTAINERS.md").read_text(encoding="utf-8")
    except OSError:
        issues.append("维护者名单不在场：MAINTAINERS.md")
    if maintainers and "Owner" not in maintainers:
        issues.append("MAINTAINERS.md 未点名 Owner（执行主体不具名）")
    if "Owner" not in text and "维护者" not in text:
        issues.append("未写明执行主体（谁受理/谁裁决）")
    for target in dangling(text, root):
        issues.append(f"仓内引用不存在：{target}（悬空引用）")
    return issues


class CodeOfConductContractTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_coc_matches_contract(self):
        self.assertEqual([], coc_issues(self.text), "行为准则不满足契约")

    def test_channel_separation_declared(self):
        """行为举报必须有归属方——否则安全通道会以「不是漏洞」退回（本轮修的真实矛盾）。"""
        self.assertIn("SECURITY.md", self.text, "未声明与安全通道的分工")
        self.assertIn("受理归属", self.text, "未声明受理归属")
        self.assertIn("不要", self.text, "未写明不要在公开 Issue 举报")
        self.assertIn("外部第三方", self.text, "单人维护下缺利益冲突回避的第三方复核路径")
        self.assertIn("Owner", (MAINTAINERS).read_text(encoding="utf-8"), "维护者名单未点名 Owner")

    def test_channel_links_resolve(self):
        """准则里指向的仓内文档（SECURITY / MAINTAINERS / CONTRIBUTING）必须真实可解析。"""
        relative = [t for t in markdown_targets(self.text)
                    if not t.startswith(("http://", "https://", "#", "mailto:"))]
        self.assertGreaterEqual(len(relative), 2, "准则应以相对链接指向仓内治理件")
        self.assertEqual([], dangling(self.text), "准则存在悬空的仓内引用")

    def test_contract_catches_broken_coc(self):
        """变异自证：删申诉段 / 删报复条款 / 去掉时限 / 删受理归属 / 悬空链接——都必须报。"""
        no_appeal = self.text.replace("## 7. 申诉", "## 7. 附注")
        self.assertTrue(any("申诉" in i for i in coc_issues(no_appeal)), "删掉申诉段必须报")
        no_retal = self.text.replace("报复", "回击")
        self.assertTrue(any("报复" in i for i in coc_issues(no_retal)), "删掉报复条款必须报")
        no_timing = self.text.replace("14 天内", "视情况")
        self.assertTrue(any("申诉时限" in i for i in coc_issues(no_timing)), "去掉申诉时限必须报")
        no_owner = self.text.replace("受理归属", "处理方式")
        self.assertTrue(any("受理归属" in i for i in coc_issues(no_owner)), "无受理归属必须报")
        bad_link = self.text + "\n[示例](docs/nope.md)\n"
        self.assertTrue(any("docs/nope.md" in i for i in coc_issues(bad_link)), "悬空链接必须报")
        with tempfile.TemporaryDirectory() as tmp:
            empty = Path(tmp) / "empty.md"
            empty.write_text("", encoding="utf-8")
            with self.assertRaises(ValueError):
                load_text(empty)
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_coc.md")


if __name__ == "__main__":
    unittest.main()
