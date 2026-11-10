#!/usr/bin/env python3
"""lint 契约判据：required check 名稳定、棘轮 fail-closed、规则集与 ruff.toml 同源（2026-11-11）。

为什么必须有：lint.yml 的两个 job 名是**分支保护的 required check 名**（`ruff-check-e9-f63-f7-f82` /
`ruff-style-ratchet`），改名会让保护失效；而风格棘轮一旦被接上 `|| true`、或 ruff.toml 的 select
被改而 job 名/检查面没跟上，都不会红。本件把「工作流 ⇄ ruff.toml ⇄ style_check.py ⇄ 基线」钉成契约。

范围：只判 .github/workflows/lint.yml 与其真源（ruff.toml / scripts/style_check.py /
protocol/style_baseline.json）。同族判据：test_sast_workflow_contract。
"""
import json
import re
import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "lint.yml"
RUFF_TOML = ROOT / "ruff.toml"
STYLE_SCRIPT = ROOT / "scripts" / "style_check.py"
BASELINE = ROOT / "protocol" / "style_baseline.json"
#: 分支保护依赖的 required check 名（改名 = 保护静默失效）
REQUIRED_NAMES = {"ruff-syntax": "ruff-check-e9-f63-f7-f82", "style-ratchet": "ruff-style-ratchet"}
MAX_RETENTION = 14


def load_workflow(path: Path = WORKFLOW) -> dict:
    """读 workflow YAML（缺失 / 非法 / 非映射 → ValueError）。"""
    try:
        import yaml
    except ModuleNotFoundError as exc:
        raise ValueError(f"缺 PyYAML：{exc}") from exc
    try:
        doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ValueError(f"lint.yml 不可读/不可解析：{exc}") from exc
    if not isinstance(doc, dict):
        raise ValueError("lint.yml 根节点必须是映射")
    return doc


def _on(doc: dict) -> dict:
    value = doc.get("on")
    if value is None:
        value = doc.get(True)
    return value if isinstance(value, dict) else {}


def _steps(job: dict) -> list:
    return [s for s in (job.get("steps") or []) if isinstance(s, dict)]


def _runs(job: dict) -> str:
    return "\n".join(str(s.get("run") or "") for s in _steps(job))


def ratchet_command(run_text: str) -> str:
    """取实际棘轮命令（排除只输出 JSON 的快照行）。"""
    for line in run_text.splitlines():
        line = line.strip()
        if "scripts/style_check.py" in line and "--json" not in line:
            return line
    return ""


def workflow_issues(doc: dict, ruff_select: list = None) -> list:
    """lint 契约问题列表（纯函数，便于变异自证）。"""
    issues = []
    if doc.get("permissions") != {"contents": "read"}:
        issues.append(f"顶层权限必须最小化（contents: read），实际 {doc.get('permissions')!r}")
    conc = doc.get("concurrency") or {}
    if conc.get("cancel-in-progress") is not True:
        issues.append("concurrency.cancel-in-progress 必须为 true")
    triggers = _on(doc)
    if (triggers.get("push") or {}).get("branches") != ["main"]:
        issues.append("push 触发必须限定 branches: [main]")
    if (triggers.get("pull_request") or {}).get("branches") != ["main"]:
        issues.append("pull_request 触发必须限定目标 branches: [main]")
    if "workflow_dispatch" not in triggers:
        issues.append("缺 workflow_dispatch（人工重跑入口）")
    jobs = doc.get("jobs") or {}
    for job_id, want_name in REQUIRED_NAMES.items():
        job = jobs.get(job_id)
        if not job:
            issues.append(f"缺作业：{job_id}")
            continue
        if str(job.get("name") or "").strip() != want_name:
            issues.append(f"{job_id} 的 name 必须是 required check 名 {want_name!r}")
        timeout = job.get("timeout-minutes")
        if not isinstance(timeout, int) or not 1 <= timeout <= 60:
            issues.append(f"{job_id} 的 timeout-minutes 必须 1..60：{timeout!r}")
        runs = _runs(job)
        if "pip install --require-hashes -r .github/requirements-lint.txt" not in runs:
            issues.append(f"{job_id} 的 ruff 安装未固定（缺 --require-hashes）")
    syntax = jobs.get("ruff-syntax") or {}
    syntax_runs = _runs(syntax)
    if "ruff check" not in syntax_runs:
        issues.append("ruff-syntax 未执行 ruff check")
    if "--output-format=github" not in syntax_runs:
        issues.append("ruff-syntax 缺 --output-format=github（失败无行内注释）")
    for scope in ("desktop/src", "scripts"):
        if scope not in syntax_runs:
            issues.append(f"ruff-syntax 检查面缺：{scope}")
    style = jobs.get("style-ratchet") or {}
    line = ratchet_command(_runs(style))
    if not line:
        issues.append("style-ratchet 缺实际棘轮命令")
    elif "|| true" in line:
        issues.append(f"棘轮命令接 `|| true`（失败被吞，fail-open）：{line}")
    for step in _steps(style):
        if "upload-artifact" not in str(step.get("uses") or ""):
            continue
        if str(step.get("if") or "").strip() != "always()":
            issues.append("诊断工件必须 if: always()")
        with_args = step.get("with") or {}
        if "style-counts.json" not in str(with_args.get("path") or ""):
            issues.append("诊断工件未包含 style-counts.json")
        days = with_args.get("retention-days")
        if not isinstance(days, int) or not 1 <= days <= MAX_RETENTION:
            issues.append(f"工件 retention-days 必须在 1..{MAX_RETENTION}：{days!r}")
    select = ruff_select if ruff_select is not None else _ruff_select()
    want_name = "ruff-check-" + "-".join(s.lower() for s in select)
    if str(REQUIRED_NAMES["ruff-syntax"]).lower() != want_name.lower():
        got = REQUIRED_NAMES["ruff-syntax"]
        issues.append(f"required check 名与 ruff.toml select 漂移：{got!r} ≠ {want_name!r}")
    return issues


def _ruff_select() -> list:
    doc = tomllib.loads(RUFF_TOML.read_text(encoding="utf-8"))
    select = ((doc.get("lint") or {}).get("select") or [])
    return [str(x) for x in select]


def style_scan_targets() -> tuple:
    """style_check.py 的扫描面（真源）。"""
    text = STYLE_SCRIPT.read_text(encoding="utf-8")
    m = re.search(r"SCAN_TARGETS = \(([^)]*)\)", text, re.S)
    if not m:
        raise ValueError("style_check.py 缺 SCAN_TARGETS")
    return tuple(x.strip().strip('\"') for x in m.group(1).split(",") if x.strip())


def scope_issues(scan_targets: tuple) -> list:
    """ruff-syntax 的检查面必须是 style_check 扫描面的子集（不自造第二份面）。"""
    issues = []
    for scope in ("desktop/src", "scripts"):
        if scope not in scan_targets:
            issues.append(f"ruff-syntax 检查面 {scope} 不在 style_check.SCAN_TARGETS 内")
    return issues


class LintWorkflowContractTest(unittest.TestCase):
    def setUp(self):
        self.doc = load_workflow()

    def test_workflow_matches_contract(self):
        self.assertEqual([], workflow_issues(self.doc), "lint.yml 不满足契约")

    def test_required_check_names_are_stable(self):
        """两个 job 名是分支保护依赖的 required check 名。"""
        jobs = self.doc["jobs"]
        for job_id, want in REQUIRED_NAMES.items():
            self.assertEqual(want, str(jobs[job_id].get("name")).strip(),
                             f"{job_id} 的 required check 名被改")

    def test_ruff_select_is_reconciled(self):
        """ruff.toml 的 select 必须与 job 名/检查面同源。"""
        self.assertEqual(["E9", "F63", "F7", "F82"], _ruff_select())
        self.assertIn("e9", self.doc["jobs"]["ruff-syntax"]["name"].lower())

    def test_syntax_scope_is_subset_of_style_scan(self):
        self.assertEqual([], scope_issues(style_scan_targets()), "检查面与 style_check 漂移")

    def test_contract_catches_broken_workflow(self):
        """变异自证（五类坏件都必须报）。

        覆盖：PR 不设限 / 棘轮接 || true / 工件无保留期 / required 名被改 / select 漂移。
        """
        import copy

        open_pr = copy.deepcopy(self.doc)
        _on(open_pr)["pull_request"] = {}
        self.assertTrue(any("pull_request" in i for i in workflow_issues(open_pr)),
                        "PR 不设分支限必须报")
        fail_open = copy.deepcopy(self.doc)
        for step in fail_open["jobs"]["style-ratchet"]["steps"]:
            if "scripts/style_check.py" in str(step.get("run") or ""):
                step["run"] = str(step.get("run")) + " || true"
        self.assertTrue(any("fail-open" in i for i in workflow_issues(fail_open)),
                        "棘轮接 || true 必须报")
        no_retention = copy.deepcopy(self.doc)
        for step in no_retention["jobs"]["style-ratchet"]["steps"]:
            if "upload-artifact" in str(step.get("uses") or ""):
                (step.get("with") or {}).pop("retention-days", None)
        self.assertTrue(any("retention" in i for i in workflow_issues(no_retention)),
                        "工件无保留期必须报")
        renamed = copy.deepcopy(self.doc)
        renamed["jobs"]["ruff-syntax"]["name"] = "ruff-check"
        self.assertTrue(any("required" in i for i in workflow_issues(renamed)),
                        "required check 名被改必须报")
        drifted = workflow_issues(self.doc, ruff_select=["E9", "F63", "F7"])
        self.assertTrue(any("漂移" in i for i in drifted), "select 漂移必须报")
        baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
        self.assertTrue(baseline.get("schema"), "风格基线缺 schema")
        with self.assertRaises(ValueError):
            load_workflow(ROOT / ".github" / "no_such_lint.yml")


if __name__ == "__main__":
    unittest.main()
