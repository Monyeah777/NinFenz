#!/usr/bin/env python3
"""ci-verify 契约判据：主门禁工作流的权限/固定/超时/并发/矩阵/失败汇总口径（2026-11-11）。

为什么必须有：ci-verify.yml 是每次提交都过的主门禁，但 workflow 面只被「action 必须固定 SHA」
这一条判据覆盖（test_ci_supply_chain）。它的其余承重口径——最小权限、每作业超时、并发取消、
32 片矩阵完整性、gate 对 needs 的显式判红（fail-closed）、工件保留期——任何一处被改都不会红。

范围：只判 .github/workflows/ci-verify.yml。同族判据：test_ci_supply_chain（action 固定面 /
dependabot 在场）、test_dependabot_contract（跟进面覆盖）。
"""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "ci-verify.yml"

#: 矩阵片数（与 verify.sh --tests-only --shard i/N 的 N 一致）
SHARDS = 32
#: 每作业超时上限（挂死上限，不许吃满 runner 6h 默认）
MAX_TIMEOUT = 60
#: 工件保留期上限（排障工件，不许无限期占存储）
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
        raise ValueError(f"ci-verify.yml 不可读/不可解析：{exc}") from exc
    if not isinstance(doc, dict):
        raise ValueError("ci-verify.yml 根节点必须是映射")
    return doc


def _on(doc: dict) -> dict:
    """YAML 1.1 会把 `on:` 解析成布尔 True；两种键都收。"""
    value = doc.get("on")
    if value is None:
        value = doc.get(True)
    return value if isinstance(value, dict) else {}


def _steps(job: dict) -> list:
    return [s for s in (job.get("steps") or []) if isinstance(s, dict)]


def _runs(job: dict) -> str:
    return "\n".join(str(s.get("run") or "") for s in _steps(job))


def workflow_issues(doc: dict) -> list:
    """ci-verify 契约问题列表（纯函数，便于变异自证）。"""
    issues = []
    if doc.get("permissions") != {"contents": "read"}:
        issues.append(f"顶层权限必须最小化（contents: read），实际 {doc.get('permissions')!r}")
    concurrency = doc.get("concurrency") or {}
    if concurrency.get("cancel-in-progress") is not True:
        issues.append("concurrency.cancel-in-progress 必须为 true（陈旧 run 不占 runner）")
    if not str(concurrency.get("group") or "").strip():
        issues.append("concurrency 缺 group")
    triggers = _on(doc)
    push = triggers.get("push") or {}
    if push.get("branches") != ["main"]:
        issues.append("push 触发必须限定 branches: [main]")
    pr = triggers.get("pull_request") or {}
    if pr.get("branches") != ["main"]:
        issues.append("pull_request 触发必须限定目标 branches: [main]")
    if "workflow_dispatch" not in triggers:
        issues.append("缺 workflow_dispatch（人工重跑入口）")
    jobs = doc.get("jobs") or {}
    for name in ("static-checks", "unit-tests", "gate"):
        if name not in jobs:
            issues.append(f"缺作业：{name}")
    if issues:
        return issues
    for name, job in jobs.items():
        job = job or {}
        timeout = job.get("timeout-minutes")
        if not isinstance(timeout, int) or not 1 <= timeout <= MAX_TIMEOUT:
            issues.append(f"{name} 的 timeout-minutes 必须在 1..{MAX_TIMEOUT}：{timeout!r}")
        if (job.get("permissions") or {}).get("contents") == "write":
            issues.append(f"{name} 不应申请 contents: write")
    static = jobs["static-checks"]
    static_runs = _runs(static)
    for needle in ("verify.sh --checks-only --no-cache", "sync-numbers.mjs",
                   "site-check.mjs --offline"):
        if needle not in static_runs:
            issues.append(f"static-checks 缺步骤：{needle}")
    unit = jobs["unit-tests"]
    matrix = (unit.get("strategy") or {}).get("matrix") or {}
    shards = matrix.get("shard") or []
    if list(shards) != list(range(SHARDS)):
        issues.append(f"unit-tests 矩阵必须是 0..{SHARDS - 1} 连续片，实际 {shards!r}")
    if (unit.get("strategy") or {}).get("fail-fast") is not False:
        issues.append("unit-tests 必须 fail-fast: false（单片红不掩盖其余诊断）")
    unit_runs = _runs(unit)
    for needle in ("--tests-only --shard", "set +e", 'rc=${PIPESTATUS[0]}', 'exit "$rc"'):
        if needle not in unit_runs:
            issues.append(f"unit-tests 缺失败诊断口径：{needle}")
    if f"-of-{SHARDS}" not in str(unit.get("name") or ""):
        issues.append(f"unit-tests 作业名必须含 -of-{SHARDS}（required check 名可读）")
    gate = jobs["gate"]
    if str(gate.get("if") or "").strip() != "always()":
        issues.append("gate 必须 if: always()（skipped 会被 GitHub 当通过）")
    needs = gate.get("needs") or []
    if sorted(needs) != ["static-checks", "unit-tests"]:
        issues.append(f"gate.needs 必须同时依赖 static-checks 与 unit-tests，实际 {needs!r}")
    gate_runs = _runs(gate)
    for needle in ("NEEDS_STATIC", "NEEDS_UNIT", "exit 1"):
        if needle not in gate_runs:
            issues.append(f"gate 缺显式判红：{needle}")
    for name, job in (("static-checks", static), ("unit-tests", unit), ("gate", gate)):
        for step in _steps(job):
            if "upload-artifact" not in str(step.get("uses") or ""):
                continue
            if str(step.get("if") or "").strip() != "always()":
                issues.append(f"{name} 的工件上传必须 if: always()（失败也要留证据）")
            days = (step.get("with") or {}).get("retention-days")
            if not isinstance(days, int) or not 1 <= days <= MAX_RETENTION:
                issues.append(f"{name} 工件 retention-days 必须在 1..{MAX_RETENTION}：{days!r}")
    return issues


class CiVerifyContractTest(unittest.TestCase):
    def setUp(self):
        self.doc = load_workflow()

    def test_workflow_matches_contract(self):
        self.assertEqual([], workflow_issues(self.doc), "ci-verify.yml 不满足契约")

    def test_shard_matrix_is_complete(self):
        """32 片必须是 0..31 连续（分片并集 == discover 全集的前提）。"""
        shards = ((self.doc["jobs"]["unit-tests"].get("strategy") or {})
                  .get("matrix") or {}).get("shard") or []
        self.assertEqual(list(range(SHARDS)), list(shards))

    def test_gate_is_fail_closed(self):
        """gate 永远跑，并显式把 needs 的 failed/cancelled/skipped 判红。"""
        gate = self.doc["jobs"]["gate"]
        self.assertEqual("always()", str(gate.get("if")).strip())
        runs = _runs(gate)
        self.assertIn("NEEDS_STATIC", runs)
        self.assertIn("NEEDS_UNIT", runs)

    def test_contract_catches_broken_workflow(self):
        """变异自证：写入权限 / 去超时 / gate 不再 always / 矩阵缺片 / 工件无保留期——都必须报。"""
        import copy

        write_perm = copy.deepcopy(self.doc)
        write_perm["permissions"] = {"contents": "write"}
        self.assertTrue(any("权限" in i for i in workflow_issues(write_perm)),
                        "contents: write 必须报")
        no_timeout = copy.deepcopy(self.doc)
        no_timeout["jobs"]["static-checks"].pop("timeout-minutes", None)
        self.assertTrue(any("timeout" in i for i in workflow_issues(no_timeout)),
                        "缺超时必须报")
        lazy_gate = copy.deepcopy(self.doc)
        lazy_gate["jobs"]["gate"]["if"] = "success()"
        self.assertTrue(any("always" in i for i in workflow_issues(lazy_gate)),
                        "gate 不再 always 必须报")
        short_matrix = copy.deepcopy(self.doc)
        short_matrix["jobs"]["unit-tests"]["strategy"]["matrix"]["shard"] = list(range(16))
        self.assertTrue(any("矩阵" in i for i in workflow_issues(short_matrix)),
                        "矩阵缺片必须报")
        no_retention = copy.deepcopy(self.doc)
        for step in no_retention["jobs"]["static-checks"]["steps"]:
            if "upload-artifact" in str(step.get("uses") or ""):
                (step.get("with") or {}).pop("retention-days", None)
        self.assertTrue(any("retention" in i for i in workflow_issues(no_retention)),
                        "工件无保留期必须报")
        with self.assertRaises(ValueError):
            load_workflow(ROOT / ".github" / "no_such_ci_verify.yml")


if __name__ == "__main__":
    unittest.main()
