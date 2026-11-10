"""Issue 表单契约判据：缺陷模板必须覆盖「能复跑」的最小字段集（2026-11-10）。

为什么必须有：模板是**唯一**的外部录入面。字段掉了不会让任何测试红，
但会让 Issue 缺环境/缺复现/缺等级——评审只能来回追问。本件把「顶尖模板该有哪几项」
钉成契约：缺一项即红，字段类型写错也红。

范围：只判 `.github/ISSUE_TEMPLATE/bug_report.yml`（Gitee 面另有投稿面判据）。
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FORM = ROOT / ".github" / "ISSUE_TEMPLATE" / "bug_report.yml"

#: 缺一即红的核心字段（按「评审能不能一次复跑」排序）
REQUIRED_IDS = (
    "what-happened", "severity", "reproduce-stability", "regression",
    "steps", "expected", "actual", "form", "reproducibility-impact",
    "install", "os", "python-version", "version", "checklist",
)
#: 自检清单必须四项全勾（挡重复 / 挡安全外泄 / 挡未脱敏 / 挡多缺陷混报）
MIN_CHECKLIST = 4
ID_RE = re.compile(r"^[A-Za-z0-9_-]+$")
TYPES = {"markdown", "textarea", "input", "dropdown", "checkboxes", "upload"}


def load_form(path: Path = FORM) -> dict:
    try:
        import yaml
    except ModuleNotFoundError as exc:  # 缺依赖 → 显式失败，不静默跳过
        raise ValueError(f"缺 PyYAML，无法校验表单契约：{exc}") from exc
    try:
        doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ValueError(f"表单不可读/不可解析：{exc}") from exc
    if not isinstance(doc, dict):
        raise ValueError("表单根节点必须是映射")
    return doc


def form_issues(doc: dict, required_ids: tuple = REQUIRED_IDS,
                min_checklist: int = MIN_CHECKLIST) -> list:
    """表单契约问题列表（纯函数，便于变异自证）。"""
    issues = []
    for key in ("name", "description", "body"):
        if not doc.get(key):
            issues.append(f"缺顶层键 {key}")
    body = doc.get("body") or []
    if not isinstance(body, list) or not body:
        return issues + ["body 必须是非空列表"]
    desc = str(doc.get("description") or "")
    if len(desc) > 200:
        issues.append(f"顶层 description 过长（{len(desc)} > 200）")
    seen = set()
    ids = []
    for item in body:
        if not isinstance(item, dict):
            issues.append("body 元素必须是映射")
            continue
        kind = item.get("type")
        if kind not in TYPES:
            issues.append(f"未知元素类型：{kind!r}")
            continue
        if kind == "markdown":
            if not str((item.get("attributes") or {}).get("value") or "").strip():
                issues.append("markdown 元素缺 value")
            continue
        eid = str(item.get("id") or "")
        if not eid:
            issues.append(f"{kind} 元素缺 id")
            continue
        if not ID_RE.match(eid):
            issues.append(f"id 不符合 [A-Za-z0-9_-]+：{eid}")
        if eid in seen:
            issues.append(f"id 重复：{eid}")
        seen.add(eid)
        ids.append(eid)
        attrs = item.get("attributes") or {}
        if not str(attrs.get("label") or "").strip():
            issues.append(f"{eid} 缺 label")
        if kind == "dropdown":
            opts = attrs.get("options") or []
            if len(opts) < 2:
                issues.append(f"{eid} 下拉至少要有 2 个选项")
        if kind == "checkboxes":
            opts = attrs.get("options") or []
            if len(opts) < min_checklist:
                issues.append(f"{eid} 自检清单少于 {min_checklist} 项（{len(opts)}）")
            for opt in opts:
                if not isinstance(opt, dict) or not str(opt.get("label") or "").strip():
                    issues.append(f"{eid} 清单项缺 label")
    missing = [f for f in required_ids if f not in ids]
    if missing:
        issues.append("缺核心字段：" + ", ".join(missing))
    return issues


class BugReportFormTest(unittest.TestCase):
    def setUp(self):
        self.doc = load_form()

    def test_form_matches_contract(self):
        self.assertEqual([], form_issues(self.doc), "缺陷模板不满足契约")

    def test_security_redirect_present(self):
        text = FORM.read_text(encoding="utf-8")
        self.assertIn("SECURITY.md", text, "缺安全私密通道指引")
        self.assertIn("CHANGELOG.md", text, "缺「先查变更日志」指引")

    def test_contract_catches_broken_forms(self):
        """变异自证：删字段 / 未知类型 / 缺 label 三种坏表单都必须报。"""
        import copy

        bad = copy.deepcopy(self.doc)
        bad["body"] = [b for b in bad["body"] if b.get("id") != "steps"]
        self.assertTrue(form_issues(bad), "删掉复现步骤必须报")
        bad2 = copy.deepcopy(self.doc)
        bad2["body"].append({"type": "matrix", "id": "x"})
        self.assertTrue(form_issues(bad2), "未知元素类型必须报")
        bad3 = copy.deepcopy(self.doc)
        bad3["body"][0] = {"type": "input", "id": "no-label"}
        self.assertTrue(form_issues(bad3), "缺 label 必须报")
        with self.assertRaises(ValueError):
            load_form(ROOT / "no_such_form.yml")

#: 功能请求表单：B1 五问（谁消费 / 怎么验证 / 非目标 / 协议关系 / 失败定义）缺一即红
FEAT_FORM = ROOT / ".github" / "ISSUE_TEMPLATE" / "feature_request.yml"
FEAT_REQUIRED_IDS = (
    "background", "capability", "usage", "consumers", "verification",
    "non-goals", "impact", "protocol-layer", "compat", "acceptance",
    "failure", "alternatives", "contribution", "checklist",
)
INTAKE = ROOT / "library" / "intake.json"


def code_surface_line() -> str:
    """由投稿面声明件算出「代码层（a · b · c）」这一行的逐字期望值（单一真源）。"""
    import json

    sub = json.loads(INTAKE.read_text(encoding="utf-8")).get("submission") or {}
    prefix = str(sub.get("code_surface_prefix") or "")
    surfaces = [str(x) for x in (sub.get("code_surfaces") or [])]
    if not (prefix and surfaces):
        raise ValueError("intake.json 缺 code_surface_prefix / code_surfaces")
    return f"{prefix}（{' · '.join(surfaces)}）"


class FeatureRequestFormTest(unittest.TestCase):
    def setUp(self):
        self.doc = load_form(FEAT_FORM)

    def test_form_matches_contract(self):
        self.assertEqual([], form_issues(self.doc, FEAT_REQUIRED_IDS, min_checklist=3),
                         "功能请求模板不满足契约")

    def test_b1_five_questions_are_collectable(self):
        """B1 五问必须在表单里各有一栏（否则评审只能靠追问补全）。"""
        ids = {b.get("id") for b in self.doc["body"] if b.get("id")}
        for need in ("consumers", "verification", "non-goals", "protocol-layer", "failure"):
            self.assertIn(need, ids, "B1 缺栏位：" + need)

    def test_code_surface_line_matches_intake_declaration(self):
        """代码面清单不得手写副本——必须与 library/intake.json 逐字一致。"""
        text = FEAT_FORM.read_text(encoding="utf-8")
        self.assertIn(code_surface_line(), text, "代码面清单与声明件不一致")

    def test_contract_catches_broken_feature_forms(self):
        import copy

        bad = copy.deepcopy(self.doc)
        bad["body"] = [b for b in bad["body"] if b.get("id") != "consumers"]
        self.assertTrue(form_issues(bad), "删掉「谁消费」必须报")
        bad2 = copy.deepcopy(self.doc)
        for item in bad2["body"]:
            if item.get("id") == "checklist":
                item["attributes"]["options"] = item["attributes"]["options"][:1]
        self.assertTrue(form_issues(bad2), "自检清单不足必须报")


if __name__ == "__main__":
    unittest.main()
