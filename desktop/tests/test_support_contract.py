#!/usr/bin/env python3
"""SUPPORT 契约判据：支持入口不得与表单 / 入口配置 / 声明件分叉（2026-11-10）。

为什么必须有：SUPPORT.md 是「使用问题」的第一跳（config.yml 的第二条 contact_link 就指向它），
但它此前缺「提 Issue 前自检」、没有说明空白 Issue 已关、也没把「一条只报一个缺陷 / 脱敏 /
安全走私密通道」写清——这些纪律只存在于表单里，于是文档与表单各说一套，且不会有任何测试变红。

范围：只判 SUPPORT.md。同族判据：test_contributing_contract（贡献入口）、
test_issue_form_contract（表单与入口配置）、test_intake_surface（投稿面 ⇄ 声明件）。
契约同构：自检四项 ⇄ bug_report.yml 的 checklist 逐项对齐；空白 Issue 口径 ⇄ config.yml。
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SUPPORT = ROOT / "SUPPORT.md"
CONFIG = ROOT / ".github" / "ISSUE_TEMPLATE" / "config.yml"
BUG = ROOT / ".github" / "ISSUE_TEMPLATE" / "bug_report.yml"
BT = chr(96)  # 反引号：源码里不写裸反引号

#: 必备段落：先自查 → 去哪问 → 提 Issue 前自检 → 之后会发生什么 → 支持边界
REQUIRED_SECTIONS = ("先自查", "去哪问", "提 Issue 前自检", "之后会发生什么", "支持边界")
#: 入口面必备要素（缺一说不上「支持入口」）
REQUIRED_MARKERS = (
    "空白 Issue 已关", "SECURITY.md", "私密通道", "结构化表单",
    "脱敏", "不静默丢弃", "不承诺响应时限", "MAINTAINERS.md", "外部第三方",
)
#: 自检四项的纪律关键词（与缺陷表单 checklist 的四条一一对应）
CHECK_TOPICS = ("重复", "安全", "脱敏", "缺陷")
#: 两个结构化表单（入口面必须指到，否则无法解释空白 Issue 已关）
FORMS = (
    ".github/ISSUE_TEMPLATE/bug_report.yml",
    ".github/ISSUE_TEMPLATE/feature_request.yml",
)

_BACKTICK = re.compile(BT + r"([^" + BT + r"\n]+)" + BT)
_PATH_SHAPE = re.compile(r"^[A-Za-z0-9_./\-\u4e00-\u9fff]+$")
_PLACEHOLDER = ("*", "…", "<", ">")
_BOX = "- [ ]"
_LINK = re.compile(r"\]\(([^)\s]+)\)")  # Markdown 链接目标 [文本](目标)


def load_text(path: Path = SUPPORT) -> str:
    """读支持文档（缺失 / 空件显式报错，不静默跳过）。"""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"支持文档不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("支持文档为空")
    return text


def load_yaml(path: Path) -> dict:
    """读 YAML（缺 PyYAML / 不可解析 → ValueError，fail-closed）。"""
    try:
        import yaml
    except ModuleNotFoundError as exc:
        raise ValueError(f"缺 PyYAML，无法校验入口面：{exc}") from exc
    try:
        doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ValueError(f"入口面 YAML 不可读/不可解析：{exc}") from exc
    if not isinstance(doc, dict):
        raise ValueError(f"{path.name} 根节点必须是映射")
    return doc


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


def dangling_paths(text: str, root: Path = ROOT) -> list:
    """仓内路径记号的悬空清单（不存在的才算悬空）。"""
    return [tok for tok in repo_path_tokens(text)
            if not (root / tok.rstrip("/")).exists()]


def markdown_link_targets(text: str) -> list:
    """Markdown 链接目标清单（含外链，供「至少引用了几个仓内文档」这类断言用）。"""
    return [match.group(1).strip() for match in _LINK.finditer(text)]


def dangling_links(text: str, root: Path = ROOT) -> list:
    """Markdown 相对链接目标中不存在的仓内路径（外链 / 锚点不判）。"""
    out = []
    for match in _LINK.finditer(text):
        target = match.group(1).strip()
        if target.startswith(("http://", "https://", "#", "mailto:")):
            continue
        rel = target.split("#")[0]
        if rel and not (root / rel).exists():
            out.append(target)
    return out


def checkbox_topics(body: str) -> tuple:
    """自检段 → (勾选框清单, 命中的纪律关键词)。"""
    boxes = [line for line in body.splitlines() if line.lstrip().startswith(_BOX)]
    joined = "\n".join(boxes)
    hits = tuple(topic for topic in CHECK_TOPICS if topic in joined)
    return boxes, hits


def support_issues(text: str, config: dict = None, root: Path = ROOT) -> list:
    """支持入口契约问题列表（纯函数，便于变异自证）。"""
    issues = []
    secs = sections(text)
    for key in REQUIRED_SECTIONS:
        if not find_section(secs, key).strip():
            issues.append(f"缺段落：{key}")
    for marker in REQUIRED_MARKERS:
        if marker not in text:
            issues.append(f"缺要素：{marker}")
    check = find_section(secs, "提 Issue 前自检")
    boxes, hits = checkbox_topics(check)
    if len(boxes) < len(CHECK_TOPICS):
        issues.append(f"提 Issue 前自检少于 {len(CHECK_TOPICS)} 项（{len(boxes)}）")
    for topic in CHECK_TOPICS:
        if topic not in hits:
            issues.append(f"提 Issue 前自检缺纪律：{topic}")
    for rel in FORMS:
        if not (root / rel).is_file():
            issues.append(f"结构化表单不在场：{rel}")
    cfg = load_yaml(CONFIG) if config is None else config
    if cfg.get("blank_issues_enabled") is not False:
        issues.append("config.yml 的 blank_issues_enabled 不是 false：入口面前提已变")
    for tok in dangling_paths(text, root):
        issues.append(f"反引号内仓内路径不存在：{tok}（悬空引用）")
    for target in dangling_links(text, root):
        issues.append(f"Markdown 相邻链接目标不存在：{target}（悬空链接）")
    return issues


def bug_checklist_labels() -> list:
    """缺陷表单的 checklist 选项 label 清单（自检四项的真源）。"""
    doc = load_yaml(BUG)
    for item in doc.get("body") or []:
        if isinstance(item, dict) and item.get("id") == "checklist":
            opts = (item.get("attributes") or {}).get("options") or []
            return [str((opt or {}).get("label") or "") for opt in opts]
    raise ValueError("bug_report.yml 缺 checklist（自检四项真源）")


class SupportContractTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_support_matches_contract(self):
        self.assertEqual([], support_issues(self.text), "支持入口不满足契约")

    def test_backtick_paths_resolve(self):
        """文档里反引号内的仓内路径必须逐个可解析（悬空引用 = 求助者点不开）。"""
        tokens = repo_path_tokens(self.text)
        self.assertGreaterEqual(len(tokens), 8, "支持入口的仓内路径引用过少")
        self.assertEqual([], dangling_paths(self.text), "支持入口引用了不存在的路径")

    def test_private_channel_is_direct(self):
        """安全私密通道必须给直达地址——只写「见 SECURITY.md」等于让求助者自己找。"""
        self.assertIn("/security/advisories/new", self.text, "缺私密安全直达地址")

    def test_markdown_links_resolve(self):
        """Markdown 相对链接目标必须存在（[SECURITY.md](SECURITY.md) 这类今天没人校验）。"""
        relative = [t for t in markdown_link_targets(self.text)
                    if not t.startswith(("http://", "https://", "#", "mailto:"))]
        self.assertGreaterEqual(len(relative), 2, "支持入口应以相对链接指向仓内文档")
        self.assertEqual([], dangling_links(self.text), "支持入口有悬空的 Markdown 链接")

    def test_appeal_reviewer_matches_maintainers(self):
        """申诉的复核主体必须与维护者表同源——单人仓不存在「另一位维护者」。"""
        self.assertIn("MAINTAINERS.md", self.text, "申诉段未指向维护者表")
        self.assertIn("外部第三方", self.text, "涉己复核缺第三方路径")
        maintainers = (ROOT / "MAINTAINERS.md").read_text(encoding="utf-8")
        self.assertIn("外部第三方", maintainers, "维护者表未定义外部第三方复核路径")

    def test_self_check_matches_bug_form(self):
        """自检四项必须与缺陷表单的 checklist 同源（表单改了、文档不改 → 红）。"""
        labels = bug_checklist_labels()
        self.assertGreaterEqual(len(labels), 4, "缺陷表单 checklist 少于 4 项")
        joined = "\n".join(labels)
        for topic in CHECK_TOPICS:
            self.assertIn(topic, joined, "缺陷表单 checklist 缺纪律关键词：" + topic)
        boxes, hits = checkbox_topics(find_section(sections(self.text), "提 Issue 前自检"))
        self.assertEqual(len(boxes), len(labels), "自检项数与表单 checklist 不一致")
        self.assertEqual(CHECK_TOPICS, hits, "自检项与表单纪律不一致")

    def test_contract_catches_broken_support(self):
        """变异自证：删自检段 / 悬空路径 / 删空白口径 / 放开配置——都必须报。"""
        no_section = self.text.replace("## 提 Issue 前自检", "## 随便写写")
        self.assertTrue(any("提 Issue 前自检" in i for i in support_issues(no_section)),
                        "删掉自检段必须报")
        bad_path = self.text + "\n参考 " + BT + "docs/nope.md" + BT + "。\n"
        self.assertTrue(any("docs/nope.md" in i for i in support_issues(bad_path)),
                        "悬空路径必须报")
        no_closed = self.text.replace("空白 Issue 已关", "空白 Issue 开放")
        self.assertTrue(any("空白 Issue" in i for i in support_issues(no_closed)),
                        "删掉空白 Issue 已关必须报")
        bad_link = self.text + "\n[示例](docs/nope.md)\n"
        self.assertTrue(any("Markdown" in i for i in support_issues(bad_link)),
                        "悬空 Markdown 链接必须报")
        no_reviewer = self.text.replace("外部第三方", "另行通知")
        self.assertTrue(any("外部第三方" in i for i in support_issues(no_reviewer)),
                        "删掉涉己复核路径必须报")
        cfg = load_yaml(CONFIG)
        cfg["blank_issues_enabled"] = True
        self.assertTrue(any("blank_issues_enabled" in i for i in support_issues(self.text, cfg)),
                        "配置放开空白 Issue 时必须报")
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_support.md")


if __name__ == "__main__":
    unittest.main()
