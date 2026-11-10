#!/usr/bin/env python3
"""codeql 契约判据：最小权限、同版本固定、路径过滤、双语言矩阵、SARIF 不互覆（2026-11-11）。

为什么必须有：codeql.yml 只在 2026-11-09 恢复，既有判据（test_ci_diagnostics）只守「触发面」；
而权限放大、init/analyze 版本错位、PR 路径过滤漏掉公网面（packaging/hf-space/server.py）、
或 analyze 丢 category（两语言 SARIF 互相覆盖）都不会红。本件把扫描工作流钉成契约。

范围：只判 .github/workflows/codeql.yml。同族判据：test_sast_workflow_contract（本地规则集）、
test_ci_supply_chain（action 固定面）。
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "codeql.yml"

#: PR 必须触发扫描的代码面（漏一面 = 新代码没人扫）
REQUIRED_PATHS = ("desktop/**", "scripts/**", "tui/**", "site/**",
                  ".github/scripts/**", "packaging/**")
#: 允许的扫描语言（与矩阵一致）
LANGUAGES = ("python", "javascript-typescript")
USES_RE = re.compile(r"^github/codeql-action/(init|analyze)@[0-9a-f]{40}$")


def load_workflow(path: Path = WORKFLOW) -> dict:
    """读 workflow YAML（缺失 / 非法 / 非映射 → ValueError）。"""
    try:
        import yaml
    except ModuleNotFoundError as exc:
        raise ValueError(f"缺 PyYAML：{exc}") from exc
    try:
        doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ValueError(f"codeql.yml 不可读/不可解析：{exc}") from exc
    if not isinstance(doc, dict):
        raise ValueError("codeql.yml 根节点必须是映射")
    return doc


def _on(doc: dict) -> dict:
    value = doc.get("on")
    if value is None:
        value = doc.get(True)
    return value if isinstance(value, dict) else {}


def _steps(job: dict) -> list:
    return [s for s in (job.get("steps") or []) if isinstance(s, dict)]


def codeql_actions() -> dict:
    """→ {"init": uses, "analyze": uses}（取 workflow 里实际的两处 action）。"""
    doc = load_workflow()
    out = {}
    for job in (doc.get("jobs") or {}).values():
        for step in _steps(job or {}):
            uses = str(step.get("uses") or "")
            m = USES_RE.match(uses)
            if m:
                out[m.group(1)] = uses
    return out


def workflow_issues(doc: dict) -> list:
    """codeql 契约问题列表（纯函数，便于变异自证）。"""
    issues = []
    if doc.get("permissions") != {"contents": "read"}:
        issues.append(f"顶层权限必须最小化（contents: read），实际 {doc.get('permissions')!r}")
    conc = doc.get("concurrency") or {}
    if conc.get("cancel-in-progress") is not True:
        issues.append("concurrency.cancel-in-progress 必须为 true")
    if not str(conc.get("group") or "").strip():
        issues.append("concurrency 缺 group")
    triggers = _on(doc)
    if "pull_request_target" in triggers:
        issues.append("不得使用 pull_request_target（会给 fork PR 写权限/密钥）")
    if (triggers.get("push") or {}).get("branches") != ["main"]:
        issues.append("push 触发必须限定 branches: [main]")
    pr = triggers.get("pull_request") or {}
    paths = [str(p) for p in (pr.get("paths") or [])]
    if not paths:
        issues.append("pull_request 缺 paths 过滤（每个依赖 PR 都烧分析）")
    for need in REQUIRED_PATHS:
        if need not in paths:
            issues.append(f"PR 路径过滤漏掉代码面：{need}")
    sched = triggers.get("schedule") or []
    if not sched or not any(str((s or {}).get("cron") or "").strip() for s in sched):
        issues.append("缺周 schedule（合并后代码无人扫）")
    if "workflow_dispatch" not in triggers:
        issues.append("缺 workflow_dispatch（人工重跑入口）")
    job = (doc.get("jobs") or {}).get("analyze")
    if not job:
        return issues + ["缺作业：analyze"]
    perm = job.get("permissions") or {}
    if perm.get("contents") != "read" or perm.get("security-events") != "write":
        issues.append("analyze 权限必须含 contents: read + security-events: write（SARIF 上传）")
    if perm.get("actions") != "read":
        issues.append("analyze 需 actions: read（CodeQL 读取 workflow 元数据）")
    strategy = job.get("strategy") or {}
    if strategy.get("fail-fast") is not False:
        issues.append("analyze 必须 fail-fast: false（一门语言红不掩盖另一门）")
    langs = [str(x) for x in ((strategy.get("matrix") or {}).get("language") or [])]
    if langs != list(LANGUAGES):
        issues.append(f"扫描语言矩阵必须恰为 {list(LANGUAGES)}，实际 {langs!r}")
    timeout = job.get("timeout-minutes")
    if not isinstance(timeout, int) or not 1 <= timeout <= 30:
        issues.append(f"analyze 的 timeout-minutes 必须 1..30：{timeout!r}")
    uses = {}
    category = ""
    for step in _steps(job):
        ref = str(step.get("uses") or "")
        m = USES_RE.match(ref)
        if m:
            uses[m.group(1)] = ref
        if "codeql-action/analyze" in ref:
            category = str((step.get("with") or {}).get("category") or "")
    if set(uses) != {"init", "analyze"}:
        issues.append("缺 codeql-action init/analyze（或未固定到 40 位 SHA）")
    elif uses["init"].split("@")[1] != uses["analyze"].split("@")[1]:
        issues.append("init 与 analyze 必须钉同一个 codeql-action SHA（版本错位）")
    if not category or "matrix.language" not in category:
        issues.append("analyze 缺 category（两语言 SARIF 会互相覆盖）")
    return issues


class CodeqlWorkflowContractTest(unittest.TestCase):
    def setUp(self):
        self.doc = load_workflow()

    def test_workflow_matches_contract(self):
        self.assertEqual([], workflow_issues(self.doc), "codeql.yml 不满足契约")

    def test_actions_are_same_pinned_version(self):
        """init/analyze 必须同一 SHA 且 40 位（版本错位 = 格式不兼容）。"""
        acts = codeql_actions()
        self.assertEqual({"init", "analyze"}, set(acts), "缺 init/analyze 固定引用")
        self.assertEqual(acts["init"].split("@")[1], acts["analyze"].split("@")[1],
                         "init/analyze 版本不一致")

    def test_pr_paths_cover_public_surfaces(self):
        """packaging/ 含公网 hf-space server.py 与 js/ts 工具链，必须在扫描触发面内。"""
        triggers = self.doc.get("on") or self.doc.get(True) or {}
        paths = (triggers.get("pull_request") or {}).get("paths")
        self.assertIn("packaging/**", paths)

    def test_contract_catches_broken_workflow(self):
        """变异自证（六类坏件都必须报）。

        覆盖：去 security-events / 版本错位 / 路径漏 packaging / 去 schedule / 丢 category /
        pull_request_target。
        """
        import copy

        no_events = copy.deepcopy(self.doc)
        no_events["jobs"]["analyze"]["permissions"].pop("security-events", None)
        self.assertTrue(any("security-events" in i for i in workflow_issues(no_events)),
                        "去 security-events 必须报")
        mismatched = copy.deepcopy(self.doc)
        for step in mismatched["jobs"]["analyze"]["steps"]:
            if "codeql-action/analyze@" in str(step.get("uses") or ""):
                step["uses"] = "github/codeql-action/analyze@" + "a" * 40
        self.assertTrue(any("同一个" in i for i in workflow_issues(mismatched)),
                        "init/analyze 版本错位必须报")
        no_pack = copy.deepcopy(self.doc)
        pr = (no_pack.get("on") or no_pack.get(True))["pull_request"]
        pr["paths"] = [p for p in pr.get("paths") or [] if p != "packaging/**"]
        self.assertTrue(any("packaging" in i for i in workflow_issues(no_pack)),
                        "路径漏 packaging 必须报")
        no_sched = copy.deepcopy(self.doc)
        (no_sched.get("on") or no_sched.get(True)).pop("schedule", None)
        self.assertTrue(any("schedule" in i for i in workflow_issues(no_sched)),
                        "去 schedule 必须报")
        no_cat = copy.deepcopy(self.doc)
        for step in no_cat["jobs"]["analyze"]["steps"]:
            if "codeql-action/analyze@" in str(step.get("uses") or ""):
                (step.get("with") or {}).pop("category", None)
        self.assertTrue(any("category" in i for i in workflow_issues(no_cat)),
                        "丢 category 必须报")
        target = copy.deepcopy(self.doc)
        (target.get("on") or target.get(True))["pull_request_target"] = {}
        self.assertTrue(any("pull_request_target" in i for i in workflow_issues(target)),
                        "pull_request_target 必须报")
        with self.assertRaises(ValueError):
            load_workflow(ROOT / ".github" / "no_such_codeql.yml")


if __name__ == "__main__":
    unittest.main()
