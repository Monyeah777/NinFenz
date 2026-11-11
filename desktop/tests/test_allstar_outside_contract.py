#!/usr/bin/env python3
"""Allstar Outside 契约判据：权限开关须显式收紧、豁免表仓库级写不了（2026-11-11）。

为什么必须有：outside.yaml 此前是 4 行 stub。该策略的两个开关都是「允许」语义，且默认朝宽松一侧
（上游 pkg/policies/outside/outside.go：PushAllowed 组织级默认 true、AdminAllowed 默认 false）——
stub 只写 action: issue 等于吃默认 true，对 push 面是**静默 no-op**：外部协作者有 push 也不会报，
这正是「写了等于没写」的典型。仓库级只读 action / pushAllowed / adminAllowed；exemptions 只在
组织级定义（上游注释：必须让组织安全管理员一眼看到），仓库级写它会被静默忽略 = 自以为豁免了。

本仓平台现状（2026-11-11 核对）：owner 是个人账号（users/Monyeah777 type=User），协作者只有
Monyeah777（direct，admin），affiliation=outside 为空 → 外部协作者 0。个人账号仓库没有组织成员可
对照，GitHub 对 affiliation=outside 恒返回空，因此该策略在本仓恒 pass——本文件是配置就绪声明与
迁移模板，不是实时防线，所以开关值必须由判据钉死。

范围：只判 .allstar/outside.yaml + 治理面单点（MAINTAINERS.md / CODEOWNERS 的执行主体）交叉对账。
同族判据：test_allstar_config_contract（六件共用契约）、test_codeowners_contract（owner 真源）。
上游事实来源（2026-11-11）：ossf/allstar pkg/policies/outside/outside.go 的 OrgConfig /
RepoConfig / OutsideExemption / getUsers(affiliation) / isExempt 与 org 默认值。
"""
import copy
import re
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / ".allstar" / "outside.yaml"
MAINTAINERS = ROOT / "MAINTAINERS.md"
CODEOWNERS = ROOT / ".github" / "CODEOWNERS"
ALLOWED_KEYS = {"optConfig", "action", "pushAllowed", "adminAllowed"}
#: 两个开关都必须显式为 false（push 默认 true 会让策略静默失效；admin 显式写 = 与组织默认解耦）。
REQUIRED_FALSE = ("pushAllowed", "adminAllowed")
#: 组织级独有键：仓库级写了会被静默忽略（= 误以为已豁免）。
ORG_ONLY_KEYS = ("exemptions", "ignoreFiles", "optInRepos", "optOutRepos")
#: 诚实边界锚点：检测面读法 / 个人账号现实 / 组织级独有 / 不可表达面。
CAVEAT_MARKERS = ("affiliation=outside", "个人账号", "exemptions", "无法表达")
#: 本仓声明的唯一执行主体（新增维护者必须同步裁决 outside 权限声明后再改判据）。
SINGLE_MAINTAINER = frozenset({"Monyeah777"})
SECRET_MARKERS = ("token:", "secret:", "ghp_", "PRIVATE KEY")


def load_config(path: Path = CONFIG) -> dict:
    """读外部协作者配置（缺失 / 非法 YAML / 非映射 → ValueError）。"""
    try:
        import yaml
    except ModuleNotFoundError as exc:
        raise ValueError("缺 PyYAML：" + str(exc)) from exc
    try:
        doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ValueError("外部协作者配置不可读/不可解析：" + str(path) + "：" + str(exc)) from exc
    if not isinstance(doc, dict):
        raise ValueError("外部协作者配置根节点必须是映射：" + str(path))
    return doc


def handle_set(text: str) -> set:
    """文本里点名的 GitHub 账号（@handle → 去 @）。"""
    return set(re.findall(r"@([A-Za-z0-9][A-Za-z0-9-]*)", text))


def maintainer_set(root: Path = ROOT) -> set:
    return handle_set((root / "MAINTAINERS.md").read_text(encoding="utf-8"))


def codeowner_set(root: Path = ROOT) -> set:
    return handle_set((root / ".github" / "CODEOWNERS").read_text(encoding="utf-8"))


def config_issues(doc: dict, text: str = "", maintainers: set = None) -> list:
    """外部协作者配置契约问题列表（纯函数，便于变异自证）。"""
    issues = []
    for key in sorted(set(doc) - ALLOWED_KEYS):
        if key in ORG_ONLY_KEYS:
            issues.append("组织级独有键不得写在仓库级（会被静默忽略）：" + key)
        else:
            issues.append("未知键（Allstar 静默忽略）：" + key)
    if doc.get("action") != "issue":
        issues.append("action 必须显式写 issue（默认 log 无任何可见结果）")
    opt = doc.get("optConfig")
    if not isinstance(opt, dict):
        issues.append("optConfig 必须是映射（与组织级模板逐字对齐）")
    elif opt.get("optOutStrategy") is not True:
        issues.append("optConfig.optOutStrategy 必须是布尔 true（组织级模板一致性）")
    for key in REQUIRED_FALSE:
        if key not in doc:
            if key == "pushAllowed":
                issues.append("缺 pushAllowed: false —— 继承组织级默认 true（外部协作者可 push、"
                              "策略对该面静默 no-op）")
            else:
                issues.append("缺 adminAllowed: false —— 显式写死才能与组织级默认解耦")
            continue
        value = doc[key]
        if value is not False:
            if isinstance(value, bool):
                issues.append(key + " 必须是 false（true = 允许外部协作者该权限）")
            else:
                issues.append(key + " 必须是布尔 false（类型错会令整份文件被 Allstar 丢弃），实际 "
                              + repr(value))
    for marker in CAVEAT_MARKERS:
        if text and marker not in text:
            issues.append("缺少检测面/边界说明：" + marker)
    if text:
        for marker in SECRET_MARKERS:
            if marker.lower() in text.lower():
                issues.append("不得包含凭据类字样：" + marker)
    if maintainers is not None and set(maintainers) != SINGLE_MAINTAINER:
        issues.append("执行主体发生变化（新增/移除维护者）必须同步裁决 outside 权限声明："
                      + repr(sorted(set(maintainers))))
    return issues


class AllstarOutsideContractTest(unittest.TestCase):
    def setUp(self):
        self.doc = load_config()
        self.text = CONFIG.read_text(encoding="utf-8")
        self.maintainers = maintainer_set()

    def test_config_matches_contract(self):
        self.assertEqual([], config_issues(self.doc, self.text, self.maintainers),
                         "外部协作者配置不满足契约")

    def test_permission_switches_are_strictly_false(self):
        """两个开关必须是严格的布尔 false；缺 pushAllowed 等于吃组织默认 true。"""
        for key in REQUIRED_FALSE:
            self.assertIs(False, self.doc.get(key), key + " 必须显式 false")
        missing = copy.deepcopy(self.doc)
        missing.pop("pushAllowed")
        self.assertTrue(any("pushAllowed" in i for i in config_issues(missing, self.text,
                                                                      self.maintainers)))
        loose = copy.deepcopy(self.doc)
        loose["pushAllowed"] = True
        self.assertTrue(any("允许外部协作者" in i
                            for i in config_issues(loose, self.text, self.maintainers)))
        str_false = copy.deepcopy(self.doc)
        str_false["adminAllowed"] = "false"
        self.assertTrue(any("布尔" in i
                            for i in config_issues(str_false, self.text, self.maintainers)))

    def test_exemptions_are_org_only(self):
        """exemptions 只在组织级定义；仓库级写它会被静默忽略，必须报出来。"""
        self.assertNotIn("exemptions", self.doc, "仓库级没有豁免表字段，写了等于没写")
        with_exempt = copy.deepcopy(self.doc)
        with_exempt["exemptions"] = [{"user": "someone", "repo": "*", "push": True}]
        issues = config_issues(with_exempt, self.text, self.maintainers)
        self.assertTrue(any("组织级独有键" in i for i in issues))

    def test_governance_single_subject(self):
        """执行主体单点交叉对账：MAINTAINERS 与 CODEOWNERS 必须是同一人，且权限陈述与之相符。"""
        owners = codeowner_set()
        self.assertEqual(self.maintainers, owners, "MAINTAINERS 与 CODEOWNERS 的执行主体不一致")
        self.assertEqual(SINGLE_MAINTAINER, self.maintainers,
                         "新增维护者必须同步裁决 outside 权限声明并更新本判据")
        drifted = config_issues(self.doc, self.text, {"Monyeah777", "second-person"})
        self.assertTrue(any("执行主体" in i for i in drifted))

    def test_contract_catches_broken_config(self):
        """变异自证：开关放开 / 类型错 / 缺键 / 组织级键 / 键名拼错 / 删说明 / 坏 YAML。"""
        allow = copy.deepcopy(self.doc)
        allow["adminAllowed"] = True
        self.assertTrue(any("允许外部协作者" in i
                            for i in config_issues(allow, self.text, self.maintainers)))
        typo = copy.deepcopy(self.doc)
        typo["pushallowed"] = False
        self.assertTrue(any("未知键" in i
                            for i in config_issues(typo, self.text, self.maintainers)))
        no_caveat = "\n".join(line for line in self.text.splitlines()
                               if "affiliation=outside" not in line)
        self.assertTrue(any("缺少检测面" in i
                            for i in config_issues(self.doc, no_caveat, self.maintainers)))
        with self.assertRaises(ValueError):
            load_config(ROOT / ".allstar" / "no_such_outside.yaml")
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "bad.yaml"
            bad.write_text("pushAllowed: [unclosed\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                load_config(bad)


if __name__ == "__main__":
    unittest.main()
