#!/usr/bin/env python3
"""CONTRIBUTING 入口面契约判据：文档不得与「结构化表单 + 声明件」分叉（2026-11-10）。

为什么必须有：入口文档（CONTRIBUTING §5）是贡献者的第一跳，但它此前只写「用哪份模板」——
空白 Issue 已关、安全走 SECURITY 私密通道、一次一件事这些纪律都没落进文档。文档与模板/声明件
分叉不会让任何测试红，评审只能靠人记。本件把「入口面文档该写清什么」钉成契约。

范围：只判 CONTRIBUTING.md 的入口面（§5）。同族判据：test_issue_form_contract（表单与入口配置）、
test_pr_template_contract（PR 模板）、test_intake_surface（投稿面 ⇄ 声明件）。
三家同构：能现算的都从真源现算（空白 Issue 口径 ⇄ config.yml；代码面清单 ⇄ library/intake.json）。
"""
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOC = ROOT / "CONTRIBUTING.md"
CONFIG = ROOT / ".github" / "ISSUE_TEMPLATE" / "config.yml"
INTAKE = ROOT / "library" / "intake.json"
BT = chr(96)  # 反引号：源码里不写裸反引号
BLOB = "https://github.com/Monyeah777/NinFenz/blob/main/"

#: 入口面必备要素：入口关闭 / 四条分流 / 三个模板 / 一次一件事 / 关联写法 / 判据指针
REQUIRED_MARKERS = (
    "空白 Issue", "blank_issues_enabled", "SECURITY.md", "私密通道", "SUPPORT.md",
    "一条 Issue 只报一个缺陷", "一个 PR 只做一件事", "Closes #", "Refs #", "判据",
)
#: 入口模板三件（缺一即评审拿不到对应字段）
TEMPLATES = (
    ".github/ISSUE_TEMPLATE/bug_report.yml",
    ".github/ISSUE_TEMPLATE/feature_request.yml",
    ".github/PULL_REQUEST_TEMPLATE.md",
)

_BACKTICK = re.compile(BT + r"([^" + BT + r"\n]+)" + BT)
_PATH_SHAPE = re.compile(r"^[A-Za-z0-9_./\-\u4e00-\u9fff]+$")
_PLACEHOLDER = ("*", "…", "<", ">")


def load_text(path: Path = DOC) -> str:
    """读入口文档（缺失 / 空件显式报错，不静默跳过）。"""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"入口文档不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("入口文档为空")
    return text


def load_config(path: Path = CONFIG) -> dict:
    """读议题入口配置（缺 PyYAML / 不可解析 → ValueError，fail-closed）。"""
    try:
        import yaml
    except ModuleNotFoundError as exc:
        raise ValueError(f"缺 PyYAML，无法校验入口配置：{exc}") from exc
    try:
        doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ValueError(f"入口配置不可读/不可解析：{exc}") from exc
    if not isinstance(doc, dict):
        raise ValueError("入口配置根节点必须是映射")
    return doc


def config_linked_docs(cfg: dict) -> list:
    """选择页里指向仓内文档的 contact_link → 相对路径清单。"""
    out = []
    for link in cfg.get("contact_links") or []:
        url = str((link or {}).get("url") or "")
        if url.startswith(BLOB):
            out.append(url[len(BLOB):].split("#")[0])
    return out


def code_surface_line() -> str:
    """由声明件算出「代码层（a · b · c）」的逐字期望值（单一真源，不手抄）。"""
    sub = json.loads(INTAKE.read_text(encoding="utf-8")).get("submission") or {}
    prefix = str(sub.get("code_surface_prefix") or "")
    surfaces = [str(x) for x in (sub.get("code_surfaces") or [])]
    if not (prefix and surfaces):
        raise ValueError("intake.json 缺 code_surface_prefix / code_surfaces")
    return f"{prefix}（{' · '.join(surfaces)}）"


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


def contributing_issues(text: str, config: dict = None, root: Path = ROOT) -> list:
    """入口面契约问题列表（纯函数，便于变异自证）。"""
    issues = []
    for marker in REQUIRED_MARKERS:
        if marker not in text:
            issues.append(f"入口面缺要素：{marker}")
    cfg = load_config() if config is None else config
    if cfg.get("blank_issues_enabled") is not False:
        issues.append("config.yml 的 blank_issues_enabled 不是 false："
                      "入口面契约前提已变，须重写文档与判据")
    else:
        if "空白 Issue 已关" not in text:
            issues.append("config 已关空白 Issue，但文档未声明「已关」")
        if "blank_issues_enabled: false" not in text:
            issues.append("文档未给出机读口径 blank_issues_enabled: false")
    for rel in config_linked_docs(cfg):
        if rel != "CONTRIBUTING.md" and rel not in text:
            issues.append(f"选择页指向的文档未在入口面出现：{rel}")
    for rel in TEMPLATES:
        if not (root / rel).is_file():
            issues.append(f"入口模板不在场：{rel}")
    if code_surface_line() not in text:
        issues.append("改动域的代码面清单与 library/intake.json 声明不一致")
    for tok in dangling_paths(text, root):
        issues.append(f"反引号内仓内路径不存在：{tok}（悬空引用）")
    return issues


class ContributingContractTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()
        self.cfg = load_config()

    def test_doc_matches_contract(self):
        self.assertEqual([], contributing_issues(self.text, self.cfg), "入口面文档不满足契约")

    def test_backtick_paths_resolve(self):
        """文档里反引号内的仓内路径必须逐个可解析（悬空引用 = 贡献者点不开）。"""
        tokens = repo_path_tokens(self.text)
        self.assertGreaterEqual(len(tokens), 10, "入口面文档的仓内路径引用过少")
        self.assertEqual([], dangling_paths(self.text), "入口面文档引用了不存在的路径")

    def test_entry_split_matches_config(self):
        """空白 Issue 关闭与四条分流必须是声明驱动的（config.yml ⇄ 文档），不是各写一份。"""
        self.assertIs(self.cfg.get("blank_issues_enabled"), False, "空白 Issue 必须保持关闭")
        links = self.cfg.get("contact_links") or []
        self.assertGreaterEqual(len(links), 4, "选择页分流入口不足 4 条")
        self.assertTrue(any("/security/advisories/new" in str(x.get("url")) for x in links),
                        "缺私密安全直达入口")
        for rel in config_linked_docs(self.cfg):
            if rel != "CONTRIBUTING.md":
                self.assertIn(rel, self.text, "选择页指向的文档未在入口面出现：" + rel)

    def test_code_surface_line_matches_intake_declaration(self):
        """改动域代码面清单不得手写副本——必须与 library/intake.json 逐字一致。"""
        self.assertIn(code_surface_line(), self.text, "代码面清单与声明件不一致")

    def test_contract_catches_broken_docs(self):
        """变异自证：放开空白 Issue / 悬空路径 / 删一次一件事 / 改配置——都必须报。"""
        bad_blank = self.text.replace("空白 Issue 已关", "空白 Issue 开放")
        self.assertTrue(any("空白" in i for i in contributing_issues(bad_blank, self.cfg)),
                        "把「空白 Issue 已关」改成「开放」必须报")
        bad_path = self.text + "\n参考 " + BT + "docs/nope.md" + BT + "。\n"
        self.assertTrue(any("docs/nope.md" in i for i in contributing_issues(bad_path, self.cfg)),
                        "悬空路径必须报")
        bad_rule = self.text.replace("**一个 PR 只做一件事**", "**一个 PR 可以做很多事**")
        self.assertTrue(any("一个 PR 只做一件事" in i
                            for i in contributing_issues(bad_rule, self.cfg)),
                        "删掉「一个 PR 只做一件事」必须报")
        flipped = dict(self.cfg)
        flipped["blank_issues_enabled"] = True
        self.assertTrue(any("blank_issues_enabled" in i
                            for i in contributing_issues(self.text, flipped)),
                        "配置放开空白 Issue 时必须报（契约前提已变）")
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_contributing.md")


if __name__ == "__main__":
    unittest.main()
