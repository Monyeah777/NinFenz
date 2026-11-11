#!/usr/bin/env python3
"""coverage 契约判据：门槛口径与 release-gate 一致、fail-closed、工件可下载（2026-11-11）。

为什么必须有：覆盖率门槛在两处出现（本 workflow 的 PR 侧量化 + release-gate 的发布前门槛）。
两处口径（--fail-under / --source / --include）一旦漂移，会出现「PR 绿、发布红」或反过来的
假保证；而失败时没有可下载日志、或门槛被调低，都不会红。本件把口径与两处一致性钉成契约。

范围：只判 .github/workflows/coverage.yml（交叉引用 release-gate.yml 的覆盖率步骤）。
同族判据：test_release_gate_workflow_contract、test_ci_diagnostics（KEY_WORKFLOWS 工件面）。
"""
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "coverage.yml"
RELEASE = ROOT / ".github" / "workflows" / "release-gate.yml"
MAX_RETENTION = 7
THRESHOLD = "--fail-under=80"
CORE_SCOPE = "desktop/src/core"


def load_workflow(path: Path = WORKFLOW) -> dict:
    """读 workflow YAML（缺失 / 非法 / 非映射 → ValueError）。"""
    try:
        doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ValueError(f"coverage.yml 不可读/不可解析：{exc}") from exc
    if not isinstance(doc, dict):
        raise ValueError("coverage.yml 根节点必须是映射")
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


def _env_text(job: dict) -> str:
    """job + 各步骤的 env 声明（NF_COVERAGE 这类开关不在 run 文本里）。"""
    parts = [str(dict(job.get("env") or {}))]
    parts.extend(str(dict(s.get("env") or {})) for s in _steps(job))
    return "\n".join(parts)


def workflow_issues(doc: dict, release_text: str = "") -> list:
    """覆盖率契约问题列表（纯函数，便于变异自证）。"""
    issues = []
    if doc.get("permissions") != {"contents": "read"}:
        issues.append(f"顶层权限必须最小化（contents: read），实际 {doc.get('permissions')!r}")
    conc = doc.get("concurrency") or {}
    if conc.get("cancel-in-progress") is not True:
        issues.append("concurrency.cancel-in-progress 必须为 true")
    triggers = _on(doc)
    if (triggers.get("push") or {}).get("branches") != ["main"]:
        issues.append("push 触发必须限定 branches: [main]")
    if "pull_request" in triggers:
        issues.append("覆盖率全量 discover 太贵，不应在 pull_request 触发")
    if "workflow_dispatch" not in triggers:
        issues.append("缺 workflow_dispatch（人工重跑入口）")
    job = (doc.get("jobs") or {}).get("core-coverage")
    if not job:
        return issues + ["缺作业：core-coverage"]
    if str(job.get("name") or "").strip() != "core-coverage-ge-80":
        issues.append("作业名必须稳定（core-coverage-ge-80）")
    timeout = job.get("timeout-minutes")
    if not isinstance(timeout, int) or not 1 <= timeout <= 60:
        issues.append(f"timeout-minutes 必须 1..60：{timeout!r}")
    checkout = [s for s in _steps(job) if "actions/checkout" in str(s.get("uses") or "")]
    if not checkout:
        issues.append("缺 checkout")
    else:
        with_args = checkout[0].get("with") or {}
        if with_args.get("fetch-depth") != 0:
            issues.append("checkout 必须 fetch-depth: 0（全量 discover 依赖 tag/全历史）")
        if with_args.get("fetch-tags") is not True:
            issues.append("checkout 必须 fetch-tags: true")
        if with_args.get("persist-credentials") is not False:
            issues.append("checkout 必须 persist-credentials: false")
    runs = _runs(job)
    if "--require-hashes" not in runs or "requirements-ci.txt" not in runs:
        issues.append("依赖必须走 requirements-ci.txt + --require-hashes")
    if "libegl1" not in runs:
        issues.append("Linux 需装 EGL 系统库（Qt 无头依赖）")
    for path in (".gitee/ISSUE_TEMPLATE", "engine/dotnet/dist", "engine/rust/canonical/target"):
        if path not in runs:
            issues.append(f"冷启动前置缺目录：{path}")
    if "NF_COVERAGE" not in _env_text(job):
        issues.append("缺 NF_COVERAGE=1（verify_tests 才开 coverage run）")
    if "verify_tests.py --jobs" not in runs:
        issues.append("缺并行测试调用（verify_tests.py --jobs）")
    if "coverage combine" not in runs:
        issues.append("缺 coverage combine（分片数据要合并）")
    if THRESHOLD not in runs:
        issues.append(f"覆盖率门槛必须 {THRESHOLD}")
    if CORE_SCOPE not in runs:
        issues.append(f"覆盖率口径必须限定 {CORE_SCOPE}")
    if "set -o pipefail" not in runs:
        issues.append("缺显式 set -o pipefail（tee 会吞退出码）")
    if 'exit "$rc"' not in runs:
        issues.append("必须以 exit \"$rc\" fail-closed（不许吞失败）")
    uploads = [s for s in _steps(job) if "upload-artifact" in str(s.get("uses") or "")]
    if not uploads:
        issues.append("缺失败诊断工件")
    for step in uploads:
        if str(step.get("if") or "").strip() != "always()":
            issues.append("诊断工件必须 if: always()")
        with_args = step.get("with") or {}
        path_text = str(with_args.get("path") or "")
        if "coverage.log" not in path_text and "*.log" not in path_text:
            issues.append("工件未包含覆盖率日志")
        days = with_args.get("retention-days")
        if not isinstance(days, int) or not 1 <= days <= MAX_RETENTION:
            issues.append(f"工件 retention-days 必须 1..{MAX_RETENTION}：{days!r}")
    if release_text:
        if THRESHOLD not in release_text:
            issues.append("release-gate 的覆盖率门槛与本件不一致")
        if CORE_SCOPE not in release_text:
            issues.append("release-gate 的覆盖率口径与本件不一致")
    return issues


class CoverageWorkflowContractTest(unittest.TestCase):
    def setUp(self):
        self.doc = load_workflow()
        self.release = RELEASE.read_text(encoding="utf-8")

    def test_workflow_matches_contract(self):
        self.assertEqual([], workflow_issues(self.doc, self.release),
                         "coverage.yml 不满足契约")

    def test_threshold_matches_release_gate(self):
        """两处覆盖率门槛必须同口径（否则出现 PR 绿/发布红）。"""
        self.assertIn(THRESHOLD, self.release)
        self.assertIn(CORE_SCOPE, self.release)
        self.assertIn(THRESHOLD, _runs(self.doc["jobs"]["core-coverage"]))

    def test_fail_closed(self):
        runs = _runs(self.doc["jobs"]["core-coverage"])
        self.assertIn('exit "$rc"', runs)
        self.assertIn("set -o pipefail", runs)

    def test_contract_catches_broken_workflow(self):
        """变异自证（五类坏件都必须报）。

        覆盖：调低门槛 / 去 pipefail / 去 exit rc / 无保留期 / 加 PR 触发。
        """
        import copy

        lowered = copy.deepcopy(self.doc)
        for step in lowered["jobs"]["core-coverage"]["steps"]:
            run = str(step.get("run") or "")
            if THRESHOLD in run:
                step["run"] = run.replace(THRESHOLD, "--fail-under=79")
        self.assertTrue(any("门槛" in i for i in workflow_issues(lowered, self.release)),
                        "调低门槛必须报")
        no_pipe = copy.deepcopy(self.doc)
        for step in no_pipe["jobs"]["core-coverage"]["steps"]:
            run = str(step.get("run") or "")
            if "set -o pipefail" in run:
                step["run"] = run.replace("set -o pipefail", "true")
        self.assertTrue(any("pipefail" in i for i in workflow_issues(no_pipe, self.release)),
                        "去 pipefail 必须报")
        no_exit = copy.deepcopy(self.doc)
        for step in no_exit["jobs"]["core-coverage"]["steps"]:
            run = str(step.get("run") or "")
            if 'exit "$rc"' in run:
                step["run"] = run.replace('exit "$rc"', "true")
        self.assertTrue(any("fail-closed" in i for i in workflow_issues(no_exit, self.release)),
                        "去 exit rc 必须报")
        no_days = copy.deepcopy(self.doc)
        for step in no_days["jobs"]["core-coverage"]["steps"]:
            if "upload-artifact" in str(step.get("uses") or ""):
                (step.get("with") or {}).pop("retention-days", None)
        self.assertTrue(any("retention" in i for i in workflow_issues(no_days, self.release)),
                        "无保留期必须报")
        pr = copy.deepcopy(self.doc)
        _on(pr)["pull_request"] = {}
        self.assertTrue(any("pull_request" in i for i in workflow_issues(pr, self.release)),
                        "加 PR 触发必须报")
        with self.assertRaises(ValueError):
            load_workflow(ROOT / ".github" / "no_such_coverage.yml")


if __name__ == "__main__":
    unittest.main()
