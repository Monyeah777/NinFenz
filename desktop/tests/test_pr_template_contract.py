#!/usr/bin/env python3
"""PR 模板契约判据：模板必须让评审**独立复跑**（2026-11-10）。

为什么必须有：.github/PULL_REQUEST_TEMPLATE.md 是合并前唯一的自述面。它掉了段
不会让任何测试红，但会让每个 PR 少掉「改了哪一面 / 怎么验 / 哪个判据守住 / 怎么归档」
——评审只能靠追问补全，或者凭信任放行。本件把「可核 PR 模板该有哪几类要素」钉成契约：
缺一类即红，引用了不存在的仓内路径也红。

范围：只判 PR 模板。Issue 表单另见 test_issue_form_contract，投稿面一致性另见
test_intake_surface。三家同构：能现算的都从声明件现算（代码面清单真源 =
library/intake.json 的 submission.code_surfaces），不在模板里手抄第二份。
"""
import json
import re
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TEMPLATE = ROOT / ".github" / "PULL_REQUEST_TEMPLATE.md"
INTAKE = ROOT / "library" / "intake.json"
BT = chr(96)  # 反引号：源码里不写裸反引号，避免与文档记号互相干扰

#: 必备段落：分别对应「只做一件事 / 改了哪一面 / 为什么改 / 怎么验 / 过没过门 / 怎么归档」
REQUIRED_SECTIONS = ("只做一件事", "改动域", "变更说明", "可核验收", "门禁自检", "关联")
#: 变更说明三段（问题 → 做法 → 影响面）：缺一段评审就只能靠猜
REQUIRED_CHANGE_KEYS = ("问题", "做法", "影响面")
#: 改动域四类（协议层 / 代码层 / 社区领域包 / 工程治理）：缺一类就看不见那一面
REQUIRED_DOMAINS = ("协议层", "代码层", "community/", "工程治理")
#: 门禁自检四项（verify / CHANGELOG / 文档状态行 / 生成物重算）
REQUIRED_GATES = ("verify.sh", "CHANGELOG", "状态行", "freshness")
#: 关联写法两种（关单 / 引用）
REQUIRED_REFS = ("Closes #", "Refs #")
#: 验收段必须给出「命令 + 期望输出」，不是「我跑过了」
REQUIRED_VERIFY = ("bash verify.sh", "precheck.py", "期望")

_BACKTICK = re.compile(BT + r"([^" + BT + r"\n]+)" + BT)
_PATH_SHAPE = re.compile(r"^[A-Za-z0-9_./\-\u4e00-\u9fff]+$")
_PLACEHOLDER = ("*", "…", "<", ">")
_BOX = "- [ ]"


def load_template(path: Path = TEMPLATE) -> str:
    """读模板 → 文本（缺失 / 空文件显式报错，不静默跳过）。"""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"PR 模板不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("PR 模板为空")
    return text


def sections(text: str) -> dict:
    """二级标题 → 该段正文（标题带关键词即可命中，段落按二级标题起止切）。"""
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
    """按标题关键词取段正文（缺段 → 空串，交由调用方报「缺段落」）。"""
    for title, body in secs.items():
        if keyword in title:
            return body
    return ""


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


def _boxes(body: str) -> list:
    return [line for line in body.splitlines() if line.lstrip().startswith(_BOX)]


def template_issues(text: str, root: Path = ROOT) -> list:
    """PR 模板契约问题列表（纯函数，便于变异自证）。"""
    issues = []
    secs = sections(text)
    for key in REQUIRED_SECTIONS:
        if not find_section(secs, key).strip():
            issues.append(f"缺段落：{key}")
    change = find_section(secs, "变更说明")
    for key in REQUIRED_CHANGE_KEYS:
        if key not in change:
            issues.append(f"变更说明缺一段：{key}")
    domain = find_section(secs, "改动域")
    if len(_boxes(domain)) < len(REQUIRED_DOMAINS):
        issues.append(f"改动域勾选少于 {len(REQUIRED_DOMAINS)} 项（{len(_boxes(domain))}）")
    for dom in REQUIRED_DOMAINS:
        if dom not in domain:
            issues.append(f"改动域缺分类：{dom}")
    gate = find_section(secs, "门禁自检")
    if len(_boxes(gate)) < len(REQUIRED_GATES):
        issues.append(f"门禁自检少于 {len(REQUIRED_GATES)} 项（{len(_boxes(gate))}）")
    for item in REQUIRED_GATES:
        if item not in gate:
            issues.append(f"门禁自检缺项：{item}")
    verify = find_section(secs, "可核验收")
    for item in REQUIRED_VERIFY:
        if item not in verify:
            issues.append(f"可核验收缺项：{item}")
    refs = find_section(secs, "关联")
    for item in REQUIRED_REFS:
        if item not in refs:
            issues.append(f"关联写法缺项：{item}")
    for tok in dangling_paths(text, root):
        issues.append(f"反引号内仓内路径不存在：{tok}（悬空引用）")
    return issues


def without_section(text: str, keyword: str) -> str:
    """删掉标题含关键词的整段（变异夹具用）。"""
    out = []
    skipping = False
    for line in text.splitlines():
        if line.startswith("## "):
            skipping = keyword in line
        if not skipping:
            out.append(line)
    return "\n".join(out)


class PrTemplateContractTest(unittest.TestCase):
    def setUp(self):
        self.text = load_template()

    def test_template_matches_contract(self):
        self.assertEqual([], template_issues(self.text), "PR 模板不满足契约")

    def test_backtick_paths_resolve(self):
        """模板里反引号内的仓内路径必须逐个可解析（悬空引用 = 评审点不开）。"""
        tokens = repo_path_tokens(self.text)
        self.assertGreaterEqual(len(tokens), 3, "模板里没有足够的仓内路径引用")
        self.assertEqual([], dangling_paths(self.text), "模板引用了不存在的路径")

    def test_code_surface_line_matches_intake_declaration(self):
        """代码面清单不得手写副本——必须与 library/intake.json 逐字一致。"""
        self.assertIn(code_surface_line(), self.text, "代码面清单与声明件不一致")

    def test_contract_catches_broken_templates(self):
        """变异自证：删验收段 / 悬空路径 / 删域勾选——三种坏模板都必须报。"""
        bad_verify = without_section(self.text, "可核验收")
        self.assertTrue(any("可核验收" in i for i in template_issues(bad_verify)),
                        "删掉验收命令段必须报")
        bad_path = self.text + "\n参考 " + BT + "docs/nope.md" + BT + "。\n"
        self.assertTrue(any("docs/nope.md" in i for i in template_issues(bad_path)),
                        "悬空路径必须报")
        bad_domain = without_section(self.text, "改动域")
        self.assertTrue(any("改动域" in i for i in template_issues(bad_domain)),
                        "删掉域勾选必须报")
        with tempfile.TemporaryDirectory() as tmp:
            empty = Path(tmp) / "empty.md"
            empty.write_text("", encoding="utf-8")
            with self.assertRaises(ValueError):
                load_template(empty)
        with self.assertRaises(ValueError):
            load_template(ROOT / ".github" / "no_such_pr_template.md")


if __name__ == "__main__":
    unittest.main()
