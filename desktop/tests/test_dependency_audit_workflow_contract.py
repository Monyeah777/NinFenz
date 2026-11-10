#!/usr/bin/env python3
"""dependency-audit 契约判据：四份固定集必须全审、fail-closed、审计日志可下载（2026-11-11）。

为什么必须有：本仓 CI 工具链的依赖面只靠这一个工作流做 CVE 审计。四份固定集里少扣一份、
审计命令被接上兜底假绿写法、或失败时没有可下载的审计日志——都不会红，漏洞就被静默放过。
本件把「审计范围 = 四份固定集」「有漏洞即红」「审计输出进工件」钉成契约。

范围：只判 .github/workflows/dependency-audit.yml 与其输入（.github/requirements-*.txt）。
同族判据：test_ci_supply_chain（固定/ASCII）、test_dependabot_contract（跟进面）。
"""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "dependency-audit.yml"
REQ_DIR = ROOT / ".github"
#: 必须被审计的四份固定集
REQUIREMENTS = ("requirements-ci.txt", "requirements-lint.txt",
                "requirements-sast.txt", "requirements-audit.txt")
MAX_RETENTION = 7
SWALLOW = "|| true"


def load_workflow(path: Path = WORKFLOW) -> dict:
    """读 workflow YAML（缺失 / 非法 / 非映射 → ValueError）。"""
    try:
        import yaml
    except ModuleNotFoundError as exc:
        raise ValueError(f"缺 PyYAML：{exc}") from exc
    try:
        doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ValueError(f"dependency-audit.yml 不可读/不可解析：{exc}") from exc
    if not isinstance(doc, dict):
        raise ValueError("dependency-audit.yml 根节点必须是映射")
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
    """依赖审计契约问题列表（纯函数，便于变异自证）。"""
    issues = []
    if doc.get("permissions") != {"contents": "read"}:
        issues.append(f"顶层权限必须最小化（contents: read），实际 {doc.get('permissions')!r}")
    conc = doc.get("concurrency") or {}
    if conc.get("cancel-in-progress") is not True:
        issues.append("concurrency.cancel-in-progress 必须为 true")
    triggers = _on(doc)
    if (triggers.get("push") or {}).get("branches") != ["main"]:
        issues.append("push 触发必须限定 branches: [main]")
    pr = triggers.get("pull_request") or {}
    paths = [str(p) for p in (pr.get("paths") or [])]
    if not paths:
        issues.append("PR 触发缺 paths（requirements 改动要能在 PR 上审）")
    if not any("requirements" in p for p in paths):
        issues.append("PR paths 未覆盖 requirements 面")
    sched = triggers.get("schedule") or []
    if not sched or not any(str((s or {}).get("cron") or "").strip() for s in sched):
        issues.append("缺周 schedule（漏洞披露后要能定期重扫）")
    if "workflow_dispatch" not in triggers:
        issues.append("缺 workflow_dispatch（人工重跑入口）")
    job = (doc.get("jobs") or {}).get("audit")
    if not job:
        return issues + ["缺作业：audit"]
    if str(job.get("name") or "").strip() != "pip-audit-pinned-ci-toolchain":
        issues.append("audit 作业名必须稳定（pip-audit-pinned-ci-toolchain）")
    timeout = job.get("timeout-minutes")
    if not isinstance(timeout, int) or not 1 <= timeout <= 30:
        issues.append(f"audit 的 timeout-minutes 必须 1..30：{timeout!r}")
    runs = _runs(job)
    if "pip install --require-hashes -r .github/requirements-audit.txt" not in runs:
        issues.append("审计器安装未固定（缺 --require-hashes）")
    if "set -euo pipefail" not in runs:
        issues.append("缺 set -euo pipefail（管道会吞退出码）")
    if "pip_audit" not in runs:
        issues.append("缺 pip_audit 调用")
    for name in REQUIREMENTS:
        if name not in runs:
            issues.append(f"审计范围漏掉固定集：{name}")
    audit_steps = [str(s.get("run") or "") for s in _steps(job)
                   if "pip_audit" in str(s.get("run") or "")]
    if not audit_steps:
        issues.append("缺审计命令行")
    if "tee dependency-audit.log" not in runs:
        issues.append("审计输出未落盘（失败时无诊断物）")
    if any(SWALLOW in step for step in audit_steps):
        issues.append(f"审计步骤接兜底假绿写法（{SWALLOW}）：漏洞被吞")
    for step in _steps(job):
        if "upload-artifact" not in str(step.get("uses") or ""):
            continue
        if str(step.get("if") or "").strip() != "always()":
            issues.append("诊断工件必须 if: always()")
        with_args = step.get("with") or {}
        if "dependency-audit.log" not in str(with_args.get("path") or ""):
            issues.append("工件未包含 dependency-audit.log")
        days = with_args.get("retention-days")
        if not isinstance(days, int) or not 1 <= days <= MAX_RETENTION:
            issues.append(f"工件 retention-days 必须 1..{MAX_RETENTION}：{days!r}")
    return issues


def requirement_issues(paths: tuple = REQUIREMENTS) -> list:
    """四份固定集必须在场、非空、ASCII-only（pip 按 locale 解析）。"""
    issues = []
    for name in paths:
        path = REQ_DIR / name
        if not path.is_file():
            issues.append(f"缺固定集：{name}")
            continue
        raw = path.read_bytes()
        if not raw.strip():
            issues.append(f"固定集为空：{name}")
            continue
        try:
            raw.decode("ascii")
        except UnicodeDecodeError:
            issues.append(f"固定集含非 ASCII（pip 会按 locale 报错）：{name}")
    return issues


class DependencyAuditWorkflowContractTest(unittest.TestCase):
    def setUp(self):
        self.doc = load_workflow()

    def test_workflow_matches_contract(self):
        self.assertEqual([], workflow_issues(self.doc), "dependency-audit.yml 不满足契约")

    def test_all_four_requirements_are_audited(self):
        runs = _runs(self.doc["jobs"]["audit"])
        for name in REQUIREMENTS:
            self.assertIn(name, runs, f"审计范围漏掉 {name}")

    def test_requirements_inputs_exist_and_are_ascii(self):
        self.assertEqual([], requirement_issues(), "固定集输入不满足契约")

    def test_contract_catches_broken_workflow(self):
        """变异自证（五类坏件都必须报）。

        覆盖：漏一份固定集 / 审计接兜底写法 / 失日志 / 无保留期 / 去 PR 触发。
        """
        import copy

        missing = copy.deepcopy(self.doc)
        for step in missing["jobs"]["audit"]["steps"]:
            if "pip_audit" in str(step.get("run") or ""):
                step["run"] = str(step["run"]).replace(
                    "-r .github/requirements-sast.txt", "")
        self.assertTrue(any("requirements-sast" in i for i in workflow_issues(missing)),
                        "漏固定集必须报")
        swallowed = copy.deepcopy(self.doc)
        for step in swallowed["jobs"]["audit"]["steps"]:
            if "pip_audit" in str(step.get("run") or ""):
                step["run"] = str(step["run"]) + " " + SWALLOW
        self.assertTrue(any(SWALLOW in i for i in workflow_issues(swallowed)),
                        "审计接兜底写法必须报")
        no_log = copy.deepcopy(self.doc)
        for step in no_log["jobs"]["audit"]["steps"]:
            if "pip_audit" in str(step.get("run") or ""):
                step["run"] = str(step["run"]).replace(" | tee dependency-audit.log", "")
        self.assertTrue(any("落盘" in i for i in workflow_issues(no_log)),
                        "审计无日志必须报")
        no_retention = copy.deepcopy(self.doc)
        for step in no_retention["jobs"]["audit"]["steps"]:
            if "upload-artifact" in str(step.get("uses") or ""):
                (step.get("with") or {}).pop("retention-days", None)
        self.assertTrue(any("retention" in i for i in workflow_issues(no_retention)),
                        "无保留期必须报")
        no_pr = copy.deepcopy(self.doc)
        _on(no_pr)["pull_request"] = {}
        self.assertTrue(any("paths" in i for i in workflow_issues(no_pr)),
                        "去 PR paths 必须报")
        with self.assertRaises(ValueError):
            load_workflow(ROOT / ".github" / "no_such_audit.yml")


if __name__ == "__main__":
    unittest.main()
