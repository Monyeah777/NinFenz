#!/usr/bin/env python3
"""Allstar 策略配置契约判据：六件可被真实加载、不静默、且不冒充平台启用（2026-11-11）。

为什么必须有：.allstar/ 是 Allstar（ossf/allstar）的配置声明面，而 Allstar 的解析是 fail-open
的——非严格解析（无 DisallowUnknownFields）：未知/拼错的键被静默忽略；某个已知键类型写错会让
**整份文件被丢弃**、回落到默认值（所有策略默认 action 是 log，只进操作者日志，不产生任何可见
结果）。于是下列写法都不会让任何测试红，却等于「配置写了等于没写」：文件名拼错（Allstar 按
固定文件名加载，拼错的文件根本不被读）、漏 action: issue、把组织级字段（optOutStrategy /
issueFooter）当仓库级开关（仓库级 RepoConfig 不读，静默忽略）。本件把「六件齐备 + 有效键集 +
issue 动作 + 组织级字段的诚实边界」钉成契约。

上游事实来源（2026-11-11 逐文件核对，commit 399d86e）：ossf/allstar pkg/config/config.go 的
OrgConfig / RepoConfig / OrgOptConfig / RepoOptConfig；pkg/policies/<pkg>/<pkg>.go 的
configFile 常量与各自 RepoConfig；pkg/enforce/enforce.go 的 action 分发（未知 action 只 warn）；
pkg/issue/issue.go 的 label 解析与 footer 拼接（不自动建 label）；README（hosted app 已退役）。
范围：只判 .allstar/*.yaml。同族判据：test_workflow_policy（ExternalSecurityEvidenceTest
已断言五策略的 optOutStrategy / action 与无凭据），本件不复述它的检查。
"""
import copy
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ALLSTAR = ROOT / ".allstar"
APP_FILE = "allstar.yaml"

#: 上游注册的 10 个策略配置文件名（pkg/policies/policies.go + 各包 configFile 常量）。
UPSTREAM_POLICY_FILES = {
    "actions.yaml", "admin.yaml", "binary_artifacts.yaml", "branch_protection.yaml",
    "codeowners.yaml", "dangerous_workflow.yaml", "outside.yaml", "scorecard.yaml",
    "secret_scanning.yaml", "security.yaml",
}
#: 本仓维护的 5 个策略 → 上游 configFile 常量所在源文件（拼错即静默失效，故逐字对齐）。
POLICIES = {
    "binary_artifacts.yaml": "pkg/policies/binary/binary.go",
    "branch_protection.yaml": "pkg/policies/branch/branch.go",
    "dangerous_workflow.yaml": "pkg/policies/workflow/workflow.go",
    "outside.yaml": "pkg/policies/outside/outside.go",
    "security.yaml": "pkg/policies/security/security.go",
}
#: 仓库级 RepoConfig 的允许键（issueFooter 属组织级模板，保留理由见根配置注释）。
APP_KEYS = {"optConfig", "issueLabel", "issueFooter", "schedule"}
#: RepoOptConfig 允许键（optIn / optOut）；optOutStrategy 属组织级 OrgOptConfig。
OPT_KEYS = {"optIn", "optOut", "optOutStrategy"}
#: 各策略 RepoConfig 的额外键（上游 pkg/policies/*/RepoConfig 逐字段核对；组级独有键不算）。
POLICY_KEYS = {
    "binary_artifacts.yaml": {"ignorePaths"},
    "branch_protection.yaml": {
        "enforceDefault", "enforceBranches", "requireApproval", "requireCodeOwnerReviews",
        "approvalCount", "dismissStale", "blockForce", "requireUpToDateBranch",
        "requireStatusChecks", "enforceOnAdmins", "requireSignedCommits",
    },
    "dangerous_workflow.yaml": {"branchList"},
    "outside.yaml": {"pushAllowed", "adminAllowed"},
    "security.yaml": set(),
}
#: 诚实边界必须保留的锚点：读法（readiness / not proof）+ 上游类型名 + label 前置条件。
CAVEAT_MARKERS = ("not proof", "readiness", "OrgOptConfig", "RepoOptConfig", "SECURITY.md",
                  "预先存在")
SECRET_MARKERS = ("token:", "secret:", "ghp_", "PRIVATE KEY")


def load_yaml(path: Path) -> dict:
    """读 Allstar 配置（缺失 / 非法 YAML / 非映射 → ValueError）。"""
    try:
        import yaml
    except ModuleNotFoundError as exc:
        raise ValueError("缺 PyYAML：" + str(exc)) from exc
    try:
        doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ValueError("Allstar 配置不可读/不可解析：" + str(path) + "：" + str(exc)) from exc
    if not isinstance(doc, dict):
        raise ValueError("Allstar 配置根节点必须是映射：" + str(path))
    return doc


def load_allstar(base: Path = ALLSTAR) -> tuple:
    """→ (根配置, {策略文件名: 配置}, {策略文件名: 文本})；缺件即 ValueError。"""
    app = load_yaml(base / APP_FILE)
    docs, texts = {}, {}
    for name in POLICIES:
        docs[name] = load_yaml(base / name)
        texts[name] = (base / name).read_text(encoding="utf-8")
    return app, docs, texts


def tracked_names(root: Path = ROOT) -> list:
    """git 追踪面里 .allstar/*.yaml 的文件名（避免本地产物污染）。"""
    try:
        proc = subprocess.run(["git", "-C", str(root), "ls-files", "-z", ".allstar"],
                              capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=120)
    except (OSError, subprocess.SubprocessError) as exc:
        raise ValueError("git ls-files 不可用：" + str(exc)) from exc
    return sorted(p.rsplit("/", 1)[-1] for p in proc.stdout.split("\0")
                  if p.endswith(".yaml"))


def bool_issues(where: str, value) -> list:
    """optOutStrategy 必须是真 bool：类型写错会让 Allstar 丢弃整份文件并回落默认 log。"""
    if value is not True:
        return [where + ".optConfig.optOutStrategy 必须是布尔 true（类型错会令整份文件被丢弃、"
                "action 回落 log），实际 " + repr(value)]
    return []


def config_issues(app_doc: dict, docs: dict, app_text: str = "", texts: dict = None,
                  tracked: list = None) -> list:
    """Allstar 配置契约问题列表（纯函数，便于变异自证）。"""
    issues = []
    texts = texts or {}
    # 1) 件集：Allstar 按固定文件名加载——拼错即静默失效，缺件即该策略走默认 log。
    want = set(POLICIES) | {APP_FILE}
    got = set(tracked_names() if tracked is None else tracked)
    for name in sorted(want - got):
        issues.append("缺件（Allstar 场景下会静默回退默认 log）：" + name)
    for name in sorted(got - want):
        if name in UPSTREAM_POLICY_FILES:
            issues.append("多出的策略件（上游合法但未纳入本仓维护集，会与根配置模板口径漂移）："
                          + name)
        else:
            issues.append("未知文件名（不是上游 configFile，Allstar 不会读）：" + name)
    # 2) 根配置：键集 + 仓库级真正生效的 issueLabel + 组织级模板字段的值。
    for key in sorted(set(app_doc) - APP_KEYS):
        issues.append("根配置未知键（Allstar 静默忽略）：" + key)
    opt = app_doc.get("optConfig")
    if not isinstance(opt, dict):
        issues.append("根配置 optConfig 必须是映射")
        opt = {}
    for key in sorted(set(opt) - OPT_KEYS):
        issues.append("根配置 optConfig 未知键（静默忽略）：" + key)
    if "optOutStrategy" not in opt:
        issues.append("根配置缺组织级模板开关 optConfig.optOutStrategy: true")
    else:
        issues.extend(bool_issues("根配置", opt.get("optOutStrategy")))
    label = app_doc.get("issueLabel")
    if not isinstance(label, str) or not label.strip():
        issues.append("根配置 issueLabel 必须是非空字符串（仓库级真正生效的字段）")
    elif label != "allstar":
        issues.append("根配置 issueLabel 必须是上游默认标签 allstar，实际 " + repr(label))
    if "issueFooter" in app_doc and "SECURITY" not in str(app_doc.get("issueFooter") or ""):
        issues.append("组织级模板 issueFooter 必须指向 SECURITY.md")
    # 3) 五件策略：键集、可见动作、与根配置模板逐字一致。
    for name in sorted(POLICIES):
        doc = docs.get(name) or {}
        allowed = {"optConfig", "action"} | POLICY_KEYS[name]
        for key in sorted(set(doc) - allowed):
            issues.append(name + " 未知键（Allstar 静默忽略）：" + key)
        if doc.get("action") != "issue":
            issues.append(name + " action 必须显式写 issue（默认 log 无任何可见结果），实际 "
                          + repr(doc.get("action")))
        p_opt = doc.get("optConfig")
        if not isinstance(p_opt, dict):
            issues.append(name + " optConfig 必须是映射（与组织级模板逐字对齐）")
            continue
        for key in sorted(set(p_opt) - OPT_KEYS):
            issues.append(name + " optConfig 未知键（静默忽略）：" + key)
        issues.extend(bool_issues(name, p_opt.get("optOutStrategy")))
        if p_opt.get("optOutStrategy") != opt.get("optOutStrategy"):
            issues.append(name + " optOutStrategy 与根配置漂移（组织级模板须逐字一致）")
    # 4) 凭据面：策略配置只读，不需任何凭据。
    for name, text in sorted({APP_FILE: app_text, **texts}.items()):
        if not text:
            continue
        for marker in SECRET_MARKERS:
            if marker.lower() in text.lower():
                issues.append(name + " 不得包含凭据类字样：" + marker)
    # 5) 诚实边界：仓库级不读组织级字段、label 须预先存在——这些事实必须写在文件里。
    for marker in CAVEAT_MARKERS:
        if marker not in app_text:
            issues.append("根配置缺少诚实边界锚点：" + marker)
    return issues


class AllstarConfigContractTest(unittest.TestCase):
    def setUp(self):
        self.app, self.docs, self.texts = load_allstar()
        self.app_text = (ALLSTAR / APP_FILE).read_text(encoding="utf-8")
        self.tracked = tracked_names()

    def test_files_match_contract(self):
        self.assertEqual([], config_issues(self.app, self.docs, self.app_text, self.texts,
                                           self.tracked), "Allstar 配置不满足契约")

    def test_policy_set_matches_upstream(self):
        """五个策略文件名必须与上游 configFile 常量逐字一致；动作必须是可见的 issue。"""
        names = sorted(n for n in self.tracked if n != APP_FILE)
        self.assertEqual(sorted(POLICIES), names, "策略件集与上游 configFile 常量不一致")
        self.assertTrue(set(names) <= UPSTREAM_POLICY_FILES, "件名不在上游 configFile 集合")
        for name in POLICIES:
            self.assertEqual("issue", self.docs[name].get("action"), name)

    def test_effective_fields_are_present(self):
        """仓库级真正生效的只有 issueLabel；组织级模板字段值必须为布尔 true。"""
        self.assertEqual("allstar", self.app.get("issueLabel"))
        self.assertIs(True, (self.app.get("optConfig") or {}).get("optOutStrategy"))
        for name in POLICIES:
            self.assertIs(True, (self.docs[name].get("optConfig") or {}).get("optOutStrategy"),
                          name)

    def test_honest_boundary_is_retained(self):
        """配置就绪 != 平台启用：删掉 caveat 必须让判据红。"""
        for marker in CAVEAT_MARKERS:
            self.assertIn(marker, self.app_text, "诚实边界锚点被删：" + marker)

    def test_contract_catches_broken_config(self):
        """变异自证：删 issueLabel / 字符串 true / action=log / 策略漂移 / 键名拼错 / 删 caveat /
        坏 YAML / 缺件 / 多出上游件——都必须报。"""
        base = {"app_text": self.app_text, "texts": self.texts, "tracked": self.tracked}
        no_label = copy.deepcopy(self.app)
        no_label.pop("issueLabel")
        self.assertTrue(any("issueLabel" in i
                            for i in config_issues(no_label, self.docs, **base)))
        str_true = copy.deepcopy(self.app)
        str_true["optConfig"]["optOutStrategy"] = "true"
        self.assertTrue(any("布尔" in i for i in config_issues(str_true, self.docs, **base)))
        silent = copy.deepcopy(self.docs)
        silent["security.yaml"]["action"] = "log"
        self.assertTrue(any(i.startswith("security.yaml action")
                            for i in config_issues(self.app, silent, **base)))
        drift = copy.deepcopy(self.docs)
        drift["outside.yaml"]["optConfig"]["optOutStrategy"] = False
        self.assertTrue(any("漂移" in i for i in config_issues(self.app, drift, **base)))
        typo = copy.deepcopy(self.docs)
        typo["security.yaml"]["Actions"] = "issue"
        self.assertTrue(any("未知键" in i for i in config_issues(self.app, typo, **base)))
        typo_root = copy.deepcopy(self.app)
        typo_root["issueFooters"] = "x"
        self.assertTrue(any("未知键" in i
                            for i in config_issues(typo_root, self.docs, **base)))
        missing = [n for n in self.tracked if n != "outside.yaml"]
        self.assertTrue(any("缺件" in i for i in config_issues(
            self.app, self.docs, **dict(base, tracked=missing))))
        extra = self.tracked + ["dangerous_workflows.yaml"]
        self.assertTrue(any("未知文件名" in i for i in config_issues(
            self.app, self.docs, **dict(base, tracked=extra))))
        upstream_extra = self.tracked + ["codeowners.yaml"]
        self.assertTrue(any("未纳入本仓维护集" in i for i in config_issues(
            self.app, self.docs, **dict(base, tracked=upstream_extra))))
        no_caveat = "\n".join(line for line in self.app_text.splitlines()
                               if "readiness" not in line)
        self.assertTrue(any("锚点" in i for i in config_issues(
            self.app, self.docs, **dict(base, app_text=no_caveat))))
        with self.assertRaises(ValueError):
            load_yaml(ALLSTAR / "no_such_allstar.yaml")
        with self.assertRaises(ValueError):
            load_allstar(ALLSTAR / "no_such_dir")
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "bad.yaml"
            bad.write_text("optConfig: [unclosed\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                load_yaml(bad)


if __name__ == "__main__":
    unittest.main()
