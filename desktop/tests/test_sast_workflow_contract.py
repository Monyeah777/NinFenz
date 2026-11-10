#!/usr/bin/env python3
"""sast 工作流契约判据：最小权限、固定工具、fail-closed 棘轮、面与脚本同源（2026-11-11）。

为什么必须有：sast.yml 是安全面唯一门禁，但此前没有工作流级判据——把权限放大、把棘轮命令接上
`|| true`（失败吞掉）、或让 SECURITY.md 声称的 tui/packaging 扫描面与脚本 SCAN_TARGETS 漂移，
都不会红。本件把「工作流 ⇄ 脚本 ⇄ 基线 ⇄ 安全文档」四处钉成一条契约。

范围：只判 .github/workflows/sast.yml 与其真源（scripts/sast_check.py /
protocol/sast_baseline.json / SECURITY.md 的对应行）。同族判据：test_ci_verify_contract。
"""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "sast.yml"
SCRIPT = ROOT / "scripts" / "sast_check.py"
BASELINE = ROOT / "protocol" / "sast_baseline.json"
SECURITY = ROOT / "SECURITY.md"
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
        raise ValueError(f"sast.yml 不可读/不可解析：{exc}") from exc
    if not isinstance(doc, dict):
        raise ValueError("sast.yml 根节点必须是映射")
    return doc


def _on(doc: dict) -> dict:
    value = doc.get("on")
    if value is None:
        value = doc.get(True)
    return value if isinstance(value, dict) else {}


def _steps(job: dict) -> list:
    return [s for s in (job.get("steps") or []) if isinstance(s, dict)]


def _runs_job(job: dict) -> str:
    return "\n".join(str(s.get("run") or "") for s in _steps(job))


def ratchet_line(run_text: str) -> str:
    """取「实际判定用」的 sast_check 命令行（排除只打印计数的 --json 行）。"""
    for line in run_text.splitlines():
        line = line.strip()
        if "sast_check.py" in line and "--json" not in line:
            return line
    return ""


def workflow_issues(doc: dict) -> list:
    """sast 工作流契约问题列表（纯函数，便于变异自证）。"""
    issues = []
    if doc.get("permissions") != {"contents": "read"}:
        issues.append(f"顶层权限必须最小化（contents: read），实际 {doc.get('permissions')!r}")
    conc = doc.get("concurrency") or {}
    if conc.get("cancel-in-progress") is not True:
        issues.append("concurrency.cancel-in-progress 必须为 true")
    if not str(conc.get("group") or "").strip():
        issues.append("concurrency 缺 group")
    triggers = _on(doc)
    if (triggers.get("push") or {}).get("branches") != ["main"]:
        issues.append("push 触发必须限定 branches: [main]")
    if (triggers.get("pull_request") or {}).get("branches") != ["main"]:
        issues.append("pull_request 触发必须限定目标 branches: [main]")
    if "workflow_dispatch" not in triggers:
        issues.append("缺 workflow_dispatch（人工重跑入口）")
    job = (doc.get("jobs") or {}).get("sast-baseline")
    if not job:
        return issues + ["缺作业：sast-baseline"]
    timeout = job.get("timeout-minutes")
    if not isinstance(timeout, int) or not 1 <= timeout <= 60:
        issues.append(f"sast-baseline 的 timeout-minutes 必须 1..60：{timeout!r}")
    name = str(job.get("name") or "")
    for needle in ("bandit", "ruff"):
        if needle not in name:
            issues.append(f"sast-baseline 作业名应标明工具：缺 {needle}")
    runs = _runs_job(job)
    for needle in ("pip install --require-hashes -r .github/requirements-sast.txt",
                   "pip install --require-hashes -r .github/requirements-lint.txt"):
        if needle not in runs:
            issues.append(f"工具安装未固定（缺 {needle}）")
    line = ratchet_line(runs)
    if not line:
        issues.append("缺实际棘轮命令（python scripts/sast_check.py 且非 --json 行）")
    elif "|| true" in line:
        issues.append(f"棘轮命令接 `|| true`（失败被吞，fail-open）：{line}")
    for step in _steps(job):
        if "upload-artifact" not in str(step.get("uses") or ""):
            continue
        if str(step.get("if") or "").strip() != "always()":
            issues.append("诊断工件上传必须 if: always()（失败也要留证据）")
        with_args = step.get("with") or {}
        path_text = str(with_args.get("path") or "")
        if "sast-counts.json" not in path_text:
            issues.append("诊断工件未包含 sast-counts.json（棘轮结论不可下载）")
        days = with_args.get("retention-days")
        if not isinstance(days, int) or not 1 <= days <= MAX_RETENTION:
            issues.append(f"工件 retention-days 必须在 1..{MAX_RETENTION}：{days!r}")
    return issues


def script_issues(text: str) -> list:
    """扫描面真源：SCAN_TARGETS 必须含 tui/packaging，且基线按平台分段。"""
    issues = []
    targets = ""
    for line in text.splitlines():
        if "SCAN_TARGETS" in line:
            targets = line
            break
    for needle in ("tui", "packaging"):
        if needle not in targets:
            issues.append(f"SCAN_TARGETS 缺扫描面：{needle}")
    for needle in ("PLATFORM", "platforms"):
        if needle not in text:
            issues.append(f"缺平台分段棘轮口径：{needle}")
    return issues


def baseline_issues(doc: dict) -> list:
    """基线必须两平台分段（缺段即 FAIL）。"""
    issues = []
    platforms = doc.get("platforms") or {}
    for key in ("nt", "posix"):
        if key not in platforms:
            issues.append(f"SAST 基线缺平台段：{key}")
    if not str(doc.get("schema") or "").strip():
        issues.append("SAST 基线缺 schema")
    return issues


def security_claim_issues(text: str) -> list:
    """SECURITY.md 的 SAST 行不得再声称「非阻塞 / sast-extra」（与脚本现实不符）。"""
    issues = []
    if "sast_check.py" not in text:
        issues.append("SECURITY.md 未指向 sast_check.py")
    if "SCAN_TARGETS" not in text:
        issues.append("SECURITY.md 未声明扫描面真源 SCAN_TARGETS")
    if "非阻塞" in text:
        issues.append("SECURITY.md 仍声称 SAST 扩展面为非阻塞（实际已并入棘轮）")
    if "sast-extra" in text:
        issues.append("SECURITY.md 仍引用不存在的 sast-extra 工件")
    return issues


class SastWorkflowContractTest(unittest.TestCase):
    def setUp(self):
        self.doc = load_workflow()

    def test_workflow_matches_contract(self):
        self.assertEqual([], workflow_issues(self.doc), "sast.yml 不满足契约")

    def test_scan_face_matches_script(self):
        """SECURITY.md 声称的 tui/packaging 面必须真的在脚本 SCAN_TARGETS 里。"""
        text = SCRIPT.read_text(encoding="utf-8")
        self.assertEqual([], script_issues(text), "sast_check.py 扫描面不满足契约")

    def test_baseline_has_both_platforms(self):
        doc = json.loads(BASELINE.read_text(encoding="utf-8"))
        self.assertEqual([], baseline_issues(doc), "SAST 基线缺平台段")

    def test_security_claim_is_current(self):
        self.assertEqual([], security_claim_issues(SECURITY.read_text(encoding="utf-8")),
                         "SECURITY.md 的 SAST 口径已过期")

    def test_contract_catches_broken_workflow(self):
        """变异自证：写权限 / PR 不设限 / 棘轮接 || true / 工件无保留期 / 缺 tui 都必须报。"""
        import copy

        write_perm = copy.deepcopy(self.doc)
        write_perm["permissions"] = {"contents": "write"}
        self.assertTrue(any("权限" in i for i in workflow_issues(write_perm)), "写权限必须报")
        open_pr = copy.deepcopy(self.doc)
        _on(open_pr)["pull_request"] = {}
        self.assertTrue(any("pull_request" in i for i in workflow_issues(open_pr)),
                        "PR 不设分支限必须报")
        fail_open = copy.deepcopy(self.doc)
        for step in fail_open["jobs"]["sast-baseline"]["steps"]:
            if "sast_check.py" in str(step.get("run") or ""):
                old = "python scripts/sast_check.py 2>&1 | tee sast.log"
                step["run"] = str(step.get("run")).replace(old, old + " || true")
        self.assertTrue(any("fail-open" in i for i in workflow_issues(fail_open)),
                        "棘轮接 || true 必须报")
        no_retention = copy.deepcopy(self.doc)
        for step in no_retention["jobs"]["sast-baseline"]["steps"]:
            if "upload-artifact" in str(step.get("uses") or ""):
                (step.get("with") or {}).pop("retention-days", None)
        self.assertTrue(any("retention" in i for i in workflow_issues(no_retention)),
                        "工件无保留期必须报")
        script_text = SCRIPT.read_text(encoding="utf-8").replace('"tui", "packaging"',
                                                                  '"tui"')
        self.assertTrue(script_issues(script_text), "扫描面缺 tui/packaging 必须报")
        baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
        broken_baseline = {"schema": baseline.get("schema"), "platforms": {"nt": {}}}
        self.assertTrue(baseline_issues(broken_baseline), "缺 posix 段必须报")
        with self.assertRaises(ValueError):
            load_workflow(ROOT / ".github" / "no_such_sast.yml")


if __name__ == "__main__":
    unittest.main()
