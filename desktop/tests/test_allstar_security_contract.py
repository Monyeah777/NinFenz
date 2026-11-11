#!/usr/bin/env python3
"""Allstar SECURITY.md 策略契约判据：唯一通过条件在场 + 内容质量不归本策略管（2026-11-11）。

为什么必须有：security.yaml 此前是 4 行 stub。该策略的检测面极窄——上游
pkg/policies/security/security.go 只问 GitHub 一个问题：repository.isSecurityPolicyEnabled
（**不检查任何内容**：不看报告通道、不看模板、不看时限）。因此「本策略已配置」绝不能当内容合格的
证据；而 stub 又没写这条边界，容易被后来者误读。本件把三件事对账：配置本身不静默（action=issue /
键集）、唯一通过条件（SECURITY.md 在受跟踪面且非空）在场、内容质量由 test_security_contract 判据
负责这条边界写进文件并被抽查。

本仓平台状态（2026-11-11 核对）：isSecurityPolicyEnabled=true，
securityPolicyUrl=https://github.com/Monyeah777/NinFenz/security/policy → 本策略恒 pass。
范围：只判 .allstar/security.yaml + SECURITY.md 的「存在/非空」与内容判据文件在场性对账。
同族判据：test_security_contract（SECURITY.md 内容契约）、test_allstar_config_contract（六件共用）。
上游事实来源（2026-11-11）：ossf/allstar pkg/policies/security/security.go 的 OrgConfig /
RepoConfig / check(isSecurityPolicyEnabled)。
"""
import copy
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / ".allstar" / "security.yaml"
SECURITY = ROOT / "SECURITY.md"
CONTENT_JUDGE = ROOT / "desktop" / "tests" / "test_security_contract.py"
ALLOWED_KEYS = {"optConfig", "action"}
#: 诚实边界锚点：唯一通过条件读法 / 内容质量归属 / 不可表达面。
CAVEAT_MARKERS = ("isSecurityPolicyEnabled", "SECURITY.md", "内容质量", "无法表达")
SECRET_MARKERS = ("token:", "secret:", "ghp_", "PRIVATE KEY")


def load_config(path: Path = CONFIG) -> dict:
    """读 SECURITY.md 策略配置（缺失 / 非法 YAML / 非映射 → ValueError）。"""
    try:
        import yaml
    except ModuleNotFoundError as exc:
        raise ValueError("缺 PyYAML：" + str(exc)) from exc
    try:
        doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ValueError("SECURITY.md 策略配置不可读/不可解析："
                         + str(path) + "：" + str(exc)) from exc
    if not isinstance(doc, dict):
        raise ValueError("SECURITY.md 策略配置根节点必须是映射：" + str(path))
    return doc


def tracked_files(root: Path = ROOT) -> list:
    try:
        proc = subprocess.run(["git", "-C", str(root), "ls-files", "-z"],
                              capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=180)
    except (OSError, subprocess.SubprocessError) as exc:
        raise ValueError("git ls-files 不可用：" + str(exc)) from exc
    return [p for p in proc.stdout.split("\0") if p]


def policy_issues(tracked: list, root: Path = ROOT) -> list:
    """策略唯一通过条件：SECURITY.md 在受跟踪面且非空（GitHub 认根目录/.github/docs）。"""
    issues = []
    candidates = ("SECURITY.md", ".github/SECURITY.md", "docs/SECURITY.md")
    present = [rel for rel in candidates if rel in tracked]
    if not present:
        return ["SECURITY.md 不在受跟踪面 → isSecurityPolicyEnabled 判 false，本策略必然 fail"]
    non_empty = [rel for rel in present if (root / rel).read_text(encoding="utf-8").strip()]
    if not non_empty:
        issues.append("SECURITY.md 存在但为空 → GitHub 不计为安全策略")
    return issues


def config_issues(doc: dict, tracked: list = None, text: str = "") -> list:
    """SECURITY.md 策略配置契约问题列表（纯函数，便于变异自证）。"""
    issues = []
    tracked = tracked_files() if tracked is None else tracked
    for key in sorted(set(doc) - ALLOWED_KEYS):
        issues.append("未知键（Allstar 静默忽略）：" + key)
    if doc.get("action") != "issue":
        issues.append("action 必须显式写 issue（默认 log 无任何可见结果）")
    opt = doc.get("optConfig")
    if not isinstance(opt, dict):
        issues.append("optConfig 必须是映射（与组织级模板逐字对齐）")
    elif opt.get("optOutStrategy") is not True:
        issues.append("optConfig.optOutStrategy 必须是布尔 true（组织级模板一致性）")
    issues.extend(policy_issues(tracked))
    for marker in CAVEAT_MARKERS:
        if text and marker not in text:
            issues.append("缺少检测面/边界说明：" + marker)
    if text:
        for marker in SECRET_MARKERS:
            if marker.lower() in text.lower():
                issues.append("不得包含凭据类字样：" + marker)
    return issues


class AllstarSecurityContractTest(unittest.TestCase):
    def setUp(self):
        self.doc = load_config()
        self.text = CONFIG.read_text(encoding="utf-8")
        self.tracked = tracked_files()

    def test_config_matches_contract(self):
        self.assertEqual([], config_issues(self.doc, self.tracked, self.text),
                         "SECURITY.md 策略配置不满足契约")

    def test_pass_condition_is_present(self):
        """策略唯一通过条件：SECURITY.md 在受跟踪面且非空（根目录即 GitHub 认可位置）。"""
        self.assertIn("SECURITY.md", self.tracked, "根目录 SECURITY.md 必须在受跟踪面")
        self.assertTrue(SECURITY.read_text(encoding="utf-8").strip(), "SECURITY.md 不得为空")
        empty = copy.deepcopy(self.tracked)
        empty.remove("SECURITY.md")
        self.assertTrue(any("SECURITY.md" in i for i in config_issues(self.doc, empty)))
        with tempfile.TemporaryDirectory() as tmp:
            blank = Path(tmp) / "SECURITY.md"
            blank.write_text("   \n", encoding="utf-8")
            issues = policy_issues(["SECURITY.md"], root=Path(tmp))
            self.assertTrue(any("为空" in i for i in issues))

    def test_content_quality_is_out_of_scope(self):
        """内容质量不归本策略管：文件必须写明，且内容判据文件必须在场（否则边界是空话）。"""
        self.assertIn("test_security_contract.py", self.text, "必须指明内容质量判据的归属")
        self.assertTrue(CONTENT_JUDGE.is_file(), "内容判据文件不存在，边界声明失效")
        body = CONTENT_JUDGE.read_text(encoding="utf-8")
        self.assertIn("def test_", body, "内容判据文件疑似空壳")

    def test_contract_catches_broken_config(self):
        """变异自证：action=log / 键名拼错 / 键集越界 / 删说明 / 缺 SECURITY.md / 坏 YAML。"""
        silent = copy.deepcopy(self.doc)
        silent["action"] = "log"
        self.assertTrue(any("action" in i for i in config_issues(
            silent, self.tracked, self.text)))
        typo = copy.deepcopy(self.doc)
        typo["Actions"] = "issue"
        self.assertTrue(any("未知键" in i for i in config_issues(
            typo, self.tracked, self.text)))
        extra = copy.deepcopy(self.doc)
        extra["pushAllowed"] = False
        self.assertTrue(any("未知键" in i for i in config_issues(
            extra, self.tracked, self.text)))
        no_caveat = "\n".join(line for line in self.text.splitlines()
                               if "isSecurityPolicyEnabled" not in line)
        self.assertTrue(any("缺少检测面" in i for i in config_issues(
            self.doc, self.tracked, no_caveat)))
        missing = [rel for rel in self.tracked if rel != "SECURITY.md"]
        self.assertTrue(any("SECURITY.md" in i for i in config_issues(self.doc, missing)))
        with self.assertRaises(ValueError):
            load_config(ROOT / ".allstar" / "no_such_security.yaml")
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "bad.yaml"
            bad.write_text("action: [unclosed\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                load_config(bad)


if __name__ == "__main__":
    unittest.main()
