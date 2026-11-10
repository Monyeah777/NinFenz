#!/usr/bin/env python3
"""release-gate 契约判据：发布闸门须最小权限、永不取消、fail-closed、有覆盖门槛（2026-11-11）。

为什么必须有：发布是不可逆动作，release-gate 是 tag 推送时的唯一强制体检；但它此前零判据——
把 cancel-in-progress 改回 true（发布体检被取消 = 这次发布「没跑过」）、把权限提成 write、
把 e2e/覆盖率步骤接上 || true、或删掉覆盖门槛，都不会红。本件把发布闸门钉成 fail-closed 契约。

范围：只判 .github/workflows/release-gate.yml 与其真源（scripts/nf.py release / e2e 脚本 /
requirements-ci.txt）。同族判据：test_ci_verify_contract、test_lint_workflow_contract。
"""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "release-gate.yml"
NF_CLI = ROOT / "scripts" / "nf.py"
E2E = ROOT / "scripts" / "e2e_desktop_headless.py"
REQ_CI = ROOT / ".github" / "requirements-ci.txt"
#: 发布证据保留期上限（发布证据可比普通排障工件更久，但仍须有上限）
MAX_RETENTION = 30


def load_workflow(path: Path = WORKFLOW) -> dict:
    """读 workflow YAML（缺失 / 非法 / 非映射 → ValueError）。"""
    try:
        import yaml
    except ModuleNotFoundError as exc:
        raise ValueError(f"缺 PyYAML：{exc}") from exc
    try:
        doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ValueError(f"release-gate.yml 不可读/不可解析：{exc}") from exc
    if not isinstance(doc, dict):
        raise ValueError("release-gate.yml 根节点必须是映射")
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


def workflow_issues(doc: dict) -> list:
    """发布闸门契约问题列表（纯函数，便于变异自证）。"""
    issues = []
    if doc.get("permissions") != {"contents": "read"}:
        issues.append(f"顶层权限必须最小化（contents: read），实际 {doc.get('permissions')!r}")
    conc = doc.get("concurrency") or {}
    if not str(conc.get("group") or "").strip():
        issues.append("concurrency 缺 group")
    if conc.get("cancel-in-progress") is not False:
        issues.append("发布体检必须 cancel-in-progress: false（取消 = 这次发布没跑过）")
    triggers = _on(doc)
    push = triggers.get("push") or {}
    if push.get("tags") != ["v*"]:
        issues.append(f"push 触发必须是 tags: [v*]，实际 {push.get('tags')!r}")
    if "pull_request" in triggers:
        issues.append("发布闸门不应在 pull_request 触发（tag 推送才有意义）")
    job = (doc.get("jobs") or {}).get("gate")
    if not job:
        return issues + ["缺作业：gate"]
    if str(job.get("name") or "").strip() != "release-preflight":
        issues.append("gate 作业名必须是 release-preflight")
    timeout = job.get("timeout-minutes")
    if not isinstance(timeout, int) or not 30 <= timeout <= 90:
        issues.append(f"release-preflight 的 timeout-minutes 必须 30..90：{timeout!r}")
    runs = _runs(job)
    if "pip install --require-hashes -r .github/requirements-ci.txt" not in runs:
        issues.append("依赖未固定（缺 --require-hashes -r .github/requirements-ci.txt）")
    if "scripts/nf.py release" not in runs:
        issues.append("缺发布前总体检：python3 scripts/nf.py release")
    if "set -o pipefail" not in runs:
        issues.append("缺 pipefail（管道会吞掉退出码）")
    if "e2e_desktop_headless.py" not in runs:
        issues.append("缺端到端显式步（e2e_desktop_headless.py）")
    if "2>&1 | tee e2e.log" not in runs:
        issues.append("e2e 步骤未落盘日志（失败无诊断）")
    if "--fail-under=80" not in runs:
        issues.append("缺覆盖率门槛（coverage report --fail-under=80）")
    if "--source=desktop/src/core" not in runs:
        issues.append("覆盖率口径未限定 desktop/src/core")
    checkout = [s for s in _steps(job) if "actions/checkout" in str(s.get("uses") or "")]
    if not checkout:
        issues.append("缺 checkout 步骤")
    else:
        with_args = checkout[0].get("with") or {}
        if with_args.get("fetch-depth") != 0:
            issues.append("checkout 必须 fetch-depth: 0（p6 依赖 tag/全历史）")
        if with_args.get("fetch-tags") is not True:
            issues.append("checkout 必须 fetch-tags: true")
    for step in _steps(job):
        if "upload-artifact" not in str(step.get("uses") or ""):
            continue
        if str(step.get("if") or "").strip() != "always()":
            issues.append("发布诊断工件必须 if: always()（失败也要留证据）")
        with_args = step.get("with") or {}
        if ".log" not in str(with_args.get("path") or ""):
            issues.append("发布证据工件未包含日志")
        days = with_args.get("retention-days")
        if not isinstance(days, int) or not 1 <= days <= MAX_RETENTION:
            issues.append(f"发布证据 retention-days 必须在 1..{MAX_RETENTION}：{days!r}")
    return issues


class ReleaseGateWorkflowContractTest(unittest.TestCase):
    def setUp(self):
        self.doc = load_workflow()

    def test_workflow_matches_contract(self):
        self.assertEqual([], workflow_issues(self.doc), "release-gate.yml 不满足契约")

    def test_never_cancelled(self):
        """发布体检永不取消：同 tag 强制重推时取消在跑体检 = 把发布验证变成没跑过。"""
        self.assertIs(False, (self.doc.get("concurrency") or {}).get("cancel-in-progress"))

    def test_sources_exist(self):
        """闸门点名的真源必须在场：nf release 子命令、e2e 脚本、CI 固定集。"""
        self.assertTrue(NF_CLI.is_file())
        self.assertIn('add_parser("release"', NF_CLI.read_text(encoding="utf-8"))
        self.assertTrue(E2E.is_file(), "缺 scripts/e2e_desktop_headless.py")
        self.assertTrue(REQ_CI.is_file(), "缺 .github/requirements-ci.txt")

    def test_contract_catches_broken_workflow(self):
        """变异自证（五类坏件都必须报）。

        覆盖：写权限 / 允许取消 / 去掉 tag 触发 / 去掉覆盖门槛 / 工件无保留期 / 去掉 pipefail。
        """
        import copy

        write_perm = copy.deepcopy(self.doc)
        write_perm["permissions"] = {"contents": "write"}
        self.assertTrue(any("权限" in i for i in workflow_issues(write_perm)), "写权限必须报")
        cancellable = copy.deepcopy(self.doc)
        cancellable["concurrency"]["cancel-in-progress"] = True
        self.assertTrue(any("取消" in i for i in workflow_issues(cancellable)),
                        "允许取消必须报")
        no_tag = copy.deepcopy(self.doc)
        _on(no_tag)["push"] = {"branches": ["main"]}
        self.assertTrue(any("tags" in i for i in workflow_issues(no_tag)),
                        "去掉 tag 触发必须报")
        no_cover = copy.deepcopy(self.doc)
        for step in no_cover["jobs"]["gate"]["steps"]:
            if "--fail-under=80" in str(step.get("run") or ""):
                step["run"] = str(step["run"]).replace("--fail-under=80", "--fail-under=0")
        self.assertTrue(any("fail-under" in i for i in workflow_issues(no_cover)),
                        "去掉覆盖门槛必须报")
        no_retention = copy.deepcopy(self.doc)
        for step in no_retention["jobs"]["gate"]["steps"]:
            if "upload-artifact" in str(step.get("uses") or ""):
                (step.get("with") or {}).pop("retention-days", None)
        self.assertTrue(any("retention" in i for i in workflow_issues(no_retention)),
                        "工件无保留期必须报")
        no_pipefail = copy.deepcopy(self.doc)
        for step in no_pipefail["jobs"]["gate"]["steps"]:
            if "set -o pipefail" in str(step.get("run") or ""):
                step["run"] = str(step["run"]).replace("set -o pipefail", "true")
        self.assertTrue(any("pipefail" in i for i in workflow_issues(no_pipefail)),
                        "去掉 pipefail 必须报")
        with self.assertRaises(ValueError):
            load_workflow(ROOT / ".github" / "no_such_release.yml")


if __name__ == "__main__":
    unittest.main()
