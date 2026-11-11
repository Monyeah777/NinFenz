#!/usr/bin/env python3
"""Allstar Branch Protection 契约判据：镜像平台现状 / required 检查真存在 / 形状自洽（2026-11-11）。

为什么必须有：branch_protection.yaml 此前是 4 行 stub——只有仓库级静默无效的 optConfig 与
action，等于「分支保护政策在这个文件里并不存在」。而 Allstar 的 fail-open 解析让任何写错都不会
红：未知键静默忽略、类型写错整份文件被丢弃并回落默认 action=log（见 .allstar/allstar.yaml）。
本件把三件事钉成契约：(1) 取值必须逐字段镜像 main 分支现有保护设置（2026-11-11 平台快照）；
(2) required 检查的 context 必须真的由受跟踪 workflow 产出（作业名对账）——否则平台侧 required
check 永远等不到、branch protection 永久红；(3) 形状与自洽（仓库级 enforceBranches 是 list 不是
org 级 map、requireCodeOwnerReviews 依赖 requireApproval、approvalCount 上限 6 等）。

平台独有、Allstar 分支策略无法表达的项（required_linear_history / conversation resolution /
allow_deletions / require_last_push_approval）必须在文件里写明缺口，避免被当作已覆盖。

上游事实来源（2026-11-11）：ossf/allstar pkg/policies/branch/branch.go 的 OrgConfig / RepoConfig /
StatusCheck、org 默认值、makeSCLookupTable / checkReviewProtection / checkStatusProtection；
平台快照：GET /repos/Monyeah777/NinFenz/branches/main/protection。
范围：只判 .allstar/branch_protection.yaml。同族判据：test_allstar_config_contract（六件共用
契约）、test_ci_health_workflow_contract（required 检查漂移的看门狗面）。
"""
import copy
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / ".allstar" / "branch_protection.yaml"

#: 平台快照（2026-11-11，GET /repos/Monyeah777/NinFenz/branches/main/protection）。
LIVE = {
    "required_status_checks": {"strict": True, "contexts": ["static-checks-42", "gate"]},
    "required_approving_review_count": 0,
    "dismiss_stale_reviews": True,
    "require_code_owner_reviews": False,
    "enforce_admins": True,
    "allow_force_pushes": False,
    "required_signatures": False,
    "required_linear_history": True,
}
#: Allstar 分支策略可表达字段 → 由 LIVE 机械推出的期望值（无自由裁量）。
EXPECTED = {
    "enforceDefault": True,                     # 监视默认分支（main）
    "requireApproval": True,                    # required_pull_request_reviews 存在 = PR 必需
    "requireCodeOwnerReviews": LIVE["require_code_owner_reviews"],
    "approvalCount": LIVE["required_approving_review_count"],
    "dismissStale": LIVE["dismiss_stale_reviews"],
    "blockForce": not LIVE["allow_force_pushes"],
    "requireUpToDateBranch": LIVE["required_status_checks"]["strict"],
    "requireStatusChecks": [{"context": c} for c in LIVE["required_status_checks"]["contexts"]],
    "enforceOnAdmins": LIVE["enforce_admins"],
    "requireSignedCommits": LIVE["required_signatures"],
}
ALLOWED_KEYS = {"optConfig", "action", "enforceBranches"} | set(EXPECTED)
#: 平台独有、Allstar 分支策略表达不了的项（文件里必须写明缺口，别当作已覆盖）。
PLATFORM_ONLY = ("required_linear_history", "required_conversation_resolution",
                 "allow_deletions", "require_last_push_approval")
CAVEAT_MARKERS = ("branches/main/protection", "平台状态才是真源") + PLATFORM_ONLY
MAX_APPROVALS = 6          # GitHub required_approving_review_count 上限
SECRET_MARKERS = ("token:", "secret:", "ghp_", "PRIVATE KEY")


def load_config(path: Path = CONFIG) -> dict:
    """读分支保护配置（缺失 / 非法 YAML / 非映射 → ValueError）。"""
    try:
        import yaml
    except ModuleNotFoundError as exc:
        raise ValueError("缺 PyYAML：" + str(exc)) from exc
    try:
        doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ValueError("分支保护配置不可读/不可解析：" + str(path) + "：" + str(exc)) from exc
    if not isinstance(doc, dict):
        raise ValueError("分支保护配置根节点必须是映射：" + str(path))
    return doc


def _tracked(root: Path, pattern: str) -> list:
    try:
        proc = subprocess.run(["git", "-C", str(root), "ls-files", "-z", pattern],
                              capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=120)
    except (OSError, subprocess.SubprocessError) as exc:
        raise ValueError("git ls-files 不可用：" + str(exc)) from exc
    return [p for p in proc.stdout.split("\0") if p]


def job_names(root: Path = ROOT) -> set:
    """受跟踪 workflow 里会产出 check run 的名字：作业 name（无模板变量）+ 作业 id。"""
    try:
        import yaml
    except ModuleNotFoundError as exc:
        raise ValueError("缺 PyYAML：" + str(exc)) from exc
    names = set()
    for rel in _tracked(root, ".github/workflows"):
        if not rel.endswith((".yml", ".yaml")):
            continue
        doc = yaml.safe_load((root / rel).read_text(encoding="utf-8", errors="replace"))
        jobs = (doc or {}).get("jobs") if isinstance(doc, dict) else None
        for job_id, job in (jobs or {}).items():
            names.add(str(job_id))
            if isinstance(job, dict):
                name = job.get("name")
                if isinstance(name, str) and "$" not in name:
                    names.add(name)
    return names


def _status_issues(entries) -> list:
    """requireStatusChecks 形状：非空 list，每项是 {context[, appID]}。"""
    issues = []
    if not isinstance(entries, list) or not entries:
        return ["requireStatusChecks 必须是非空 list（每项含 context）"]
    seen = set()
    for i, entry in enumerate(entries):
        if not isinstance(entry, dict):
            issues.append("requireStatusChecks[" + str(i) + "] 必须是映射")
            continue
        extra = sorted(set(entry) - {"context", "appID"})
        if extra:
            issues.append("requireStatusChecks[" + str(i) + "] 未知键（静默忽略）：" + str(extra))
        ctx = entry.get("context")
        if not isinstance(ctx, str) or not ctx.strip():
            issues.append("requireStatusChecks[" + str(i) + "] context 必须是非空字符串")
        elif ctx in seen:
            issues.append("requireStatusChecks 重复 context：" + ctx)
        else:
            seen.add(ctx)
        if "appID" in entry:
            app_id = entry["appID"]
            if isinstance(app_id, bool) or not isinstance(app_id, int) or app_id <= 0:
                issues.append("requireStatusChecks[" + str(i) + "] appID 必须是正整数")
    return issues


def branch_issues(doc: dict, jobs: set = None, text: str = "") -> list:
    """分支保护配置契约问题列表（纯函数，便于变异自证）。"""
    issues = []
    jobs = job_names() if jobs is None else jobs
    for key in sorted(set(doc) - ALLOWED_KEYS):
        issues.append("未知键（Allstar 静默忽略）：" + key)
    if doc.get("action") != "issue":
        issues.append("action 必须显式写 issue（默认 log 无任何可见结果）")
    opt = doc.get("optConfig")
    if not isinstance(opt, dict):
        issues.append("optConfig 必须是映射（与组织级模板逐字对齐）")
    elif opt.get("optOutStrategy") is not True:
        issues.append("optConfig.optOutStrategy 必须是布尔 true（组织级模板一致性）")
    # 1) 镜像：可表达字段必须逐字段等于平台快照推出的期望值。
    for key, want in EXPECTED.items():
        got = doc.get(key)
        if key == "requireStatusChecks":
            issues.extend(_status_issues(got))
            ctxs = [e.get("context") for e in got or [] if isinstance(e, dict)]
            if sorted(str(c) for c in ctxs) != sorted(e["context"] for e in want):
                issues.append("requireStatusChecks 与平台快照不一致：" + repr(got))
            continue
        if isinstance(want, bool):
            bad = got is not want
        else:
            bad = isinstance(got, bool) or not isinstance(got, int) or got != want
        if bad:
            issues.append(key + " 与平台快照不一致：期望 " + repr(want) + "，实际 " + repr(got))
    # 2) 交叉对账：required 检查必须真由受跟踪 workflow 产出，否则平台侧永远等不到。
    for entry in doc.get("requireStatusChecks") or []:
        ctx = entry.get("context") if isinstance(entry, dict) else None
        if isinstance(ctx, str) and ctx.strip() and ctx not in jobs:
            issues.append("required 检查不在受跟踪 workflow 作业名里（平台侧永久红）：" + ctx)
    # 3) 自洽：字段间依赖与取值范围。
    approval = doc.get("approvalCount")
    if (isinstance(approval, int) and not isinstance(approval, bool)
            and not 0 <= approval <= MAX_APPROVALS):
        issues.append("approvalCount 必须在 0.." + str(MAX_APPROVALS) + "，实际 " + repr(approval))
    if doc.get("requireCodeOwnerReviews") is True and doc.get("requireApproval") is not True:
        issues.append("requireCodeOwnerReviews=true 要求 requireApproval=true（上游约束）")
    if doc.get("requireApproval") is False and approval not in (None, 0):
        issues.append("requireApproval=false 时 Allstar 会把 approvalCount 强制置 0，写了也无效")
    checks = doc.get("requireStatusChecks")
    if (not checks) and doc.get("requireUpToDateBranch") not in (None, False):
        issues.append("requireUpToDateBranch 仅在 requireStatusChecks 非空时生效")
    branches = doc.get("enforceBranches")
    if branches is not None:
        if isinstance(branches, dict):
            issues.append("仓库级 enforceBranches 必须是 list（org 级才是 map），写成 map 会整份"
                          "文件被丢弃")
        elif not isinstance(branches, list) or not all(isinstance(b, str) for b in branches):
            issues.append("enforceBranches 必须是字符串 list")
    # 4) 平台独有缺口必须写明（否则会被当作已由 Allstar 覆盖）。
    for marker in CAVEAT_MARKERS:
        if text and marker not in text:
            issues.append("缺少平台独有缺口的说明：" + marker)
    # 5) 凭据面。
    if text:
        for marker in SECRET_MARKERS:
            if marker.lower() in text.lower():
                issues.append("不得包含凭据类字样：" + marker)
    return issues


class AllstarBranchProtectionContractTest(unittest.TestCase):
    def setUp(self):
        self.doc = load_config()
        self.text = CONFIG.read_text(encoding="utf-8")
        self.jobs = job_names()

    def test_config_mirrors_live_protection(self):
        self.assertEqual([], branch_issues(self.doc, self.jobs, self.text),
                         "分支保护配置不满足契约")

    def test_required_checks_are_produced_by_tracked_workflows(self):
        """required 检查的 context 必须真的是受跟踪 workflow 的作业名（否则永久红）。"""
        ctxs = [e.get("context") for e in self.doc.get("requireStatusChecks") or []
                if isinstance(e, dict)]
        self.assertEqual(sorted(e["context"] for e in EXPECTED["requireStatusChecks"]),
                         sorted(ctxs), "required 检查集合与平台快照不一致")
        for ctx in ctxs:
            self.assertIn(ctx, self.jobs, "required 检查不在受跟踪 workflow 作业名里：" + str(ctx))

    def test_shape_and_coherence(self):
        """形状：status 检查项结构 / appID 类型 / enforceBranches 仓库级 list / 字段依赖。"""
        self.assertEqual([], _status_issues(self.doc.get("requireStatusChecks")))
        self.assertNotIn("enforceBranches", self.doc, "main 由 enforceDefault 覆盖，不需额外分支")
        self.assertEqual([], [i for i in branch_issues(self.doc, self.jobs, "")
                              if "enforceBranches" in i or "approvalCount" in i
                              or "requireCodeOwnerReviews" in i])

    def test_platform_only_gap_is_documented(self):
        """平台独有项与「平台状态才是真源」必须在文件里写明，避免被当作已覆盖。"""
        for marker in CAVEAT_MARKERS:
            self.assertIn(marker, self.text, "缺少缺口/真源说明：" + marker)
        self.assertEqual(set(), ALLOWED_KEYS & set(PLATFORM_ONLY),
                         "平台独有项不应出现在 Allstar 允许键里")

    def test_contract_catches_broken_config(self):
        """变异自证：镜像漂移 / 检查名拼错 / appID 类型错 / 依赖违反 / 形状错 / 删缺口说明 /
        坏 YAML——都必须报。"""
        base = {"jobs": self.jobs, "text": self.text}
        escaped = copy.deepcopy(self.doc)
        escaped["blockForce"] = False
        self.assertTrue(any("blockForce" in i
                            for i in branch_issues(escaped, **base)))
        renamed = copy.deepcopy(self.doc)
        renamed["requireStatusChecks"][0]["context"] = "static-check-42"
        self.assertTrue(any("永久红" in i for i in branch_issues(renamed, **base)))
        str_app = copy.deepcopy(self.doc)
        str_app["requireStatusChecks"][0]["appID"] = "15368"
        self.assertTrue(any("appID" in i for i in branch_issues(str_app, **base)))
        no_ctx = copy.deepcopy(self.doc)
        no_ctx["requireStatusChecks"].append({"appID": 15368})
        self.assertTrue(any("context" in i for i in branch_issues(no_ctx, **base)))
        dep = copy.deepcopy(self.doc)
        dep["requireCodeOwnerReviews"] = True
        dep["requireApproval"] = False
        self.assertTrue(any("requireCodeOwnerReviews" in i
                            for i in branch_issues(dep, **base)))
        many = copy.deepcopy(self.doc)
        many["approvalCount"] = 9
        self.assertTrue(any("approvalCount" in i for i in branch_issues(many, **base)))
        org_shape = copy.deepcopy(self.doc)
        org_shape["enforceBranches"] = {"release": ["main"]}
        self.assertTrue(any("enforceBranches" in i for i in branch_issues(org_shape, **base)))
        typo = copy.deepcopy(self.doc)
        typo["blockForc"] = True
        self.assertTrue(any("未知键" in i for i in branch_issues(typo, **base)))
        no_caveat = "\n".join(line for line in self.text.splitlines()
                               if "required_linear_history" not in line)
        self.assertTrue(any("缺口" in i
                            for i in branch_issues(self.doc, **dict(base, text=no_caveat))))
        with self.assertRaises(ValueError):
            load_config(ROOT / ".allstar" / "no_such_branch_protection.yaml")
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "bad.yaml"
            bad.write_text("requireStatusChecks: [unclosed\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                load_config(bad)


if __name__ == "__main__":
    unittest.main()
