#!/usr/bin/env python3
"""net-probes 契约判据：仅手动、失败不产假红、金标 fail-fast、双 RID 真交付（2026-11-11）。

为什么必须有：本 workflow 曾被 schedule 每周产一次假红（v2.11.0 历史重写后不存在，实测），
最终收口为**仅手动 + 允许失败（诊断信号）**。这三条最容易回潮：①有人重新加回 schedule/push
（再次每周假红）；②有人把 continue-on-error 去掉（金标未前移时把维护窗口变成门禁红）；③金标
快照 ref 不可用时不再 fail-fast 而是静默继续（跑批结果无意义却绿）。本件把收口决策钉成契约。

范围：只判 .github/workflows/net-probes.yml 与其输入（engine/dotnet/probes/probe_manifest.json）。
同族判据：test_ci_health_workflow_contract（看门狗会把这些红算进来）、test_dotnet_build_workflow_contract。
"""
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "net-probes.yml"
MANIFEST = ROOT / "engine" / "dotnet" / "probes" / "probe_manifest.json"
OSES = ("ubuntu-latest", "windows-latest")
MAX_RETENTION = 7


def load_workflow(path: Path = WORKFLOW) -> dict:
    """读 workflow YAML（缺失 / 非法 / 非映射 → ValueError）。"""
    try:
        doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ValueError(f"net-probes.yml 不可读/不可解析：{exc}") from exc
    if not isinstance(doc, dict):
        raise ValueError("net-probes.yml 根节点必须是映射")
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


def workflow_issues(doc: dict, text: str = "") -> list:
    """探针跑批契约问题列表（纯函数，便于变异自证）。"""
    issues = []
    body = text if text else ""
    if doc.get("permissions") != {"contents": "read"}:
        issues.append(f"顶层权限必须最小化（contents: read），实际 {doc.get('permissions')!r}")
    conc = doc.get("concurrency") or {}
    if conc.get("cancel-in-progress") is not True:
        issues.append("concurrency.cancel-in-progress 必须为 true")
    triggers = _on(doc)
    for bad in ("schedule", "push", "pull_request"):
        if bad in triggers:
            msg = f"收口决策：仅手动触发；不得恢复 {bad}（金标未前移时只会每周假红）"
            issues.append(msg)
    if "workflow_dispatch" not in triggers:
        issues.append("缺 workflow_dispatch（这也是它唯一的触发面）")
    inputs = (triggers.get("workflow_dispatch") or {}).get("inputs") or {}
    tier = inputs.get("tier") or {}
    if [str(x) for x in (tier.get("options") or [])] != ["core", "all"]:
        issues.append("workflow_dispatch 必须有 tier 输入（core/all）")
    if "snap_ref" not in inputs:
        issues.append("workflow_dispatch 必须有 snap_ref 输入（金标快照参数化）")
    job = (doc.get("jobs") or {}).get("probes")
    if not job:
        return issues + ["缺作业：probes"]
    if "matrix.os" not in str(job.get("name") or ""):
        issues.append("作业名必须含 matrix.os（两平台可区分）")
    strategy = job.get("strategy") or {}
    if strategy.get("fail-fast") is not False:
        issues.append("必须 fail-fast: false（一台红不掩盖另一台）")
    oses = [str(x) for x in ((strategy.get("matrix") or {}).get("os") or [])]
    if oses != list(OSES):
        issues.append(f"矩阵必须是两平台 {list(OSES)}，实际 {oses!r}")
    if job.get("continue-on-error") is not True:
        issues.append("金标未前移期间必须 continue-on-error: true（失败只作诊断信号，不产门禁红）")
    if "裁决" not in body and "诊断信号" not in body:
        issues.append("continue-on-error 必须写明理由（金标裁决未定 ⇒ 诊断信号）")
    timeout = job.get("timeout-minutes")
    if not isinstance(timeout, int) or not 1 <= timeout <= 90:
        issues.append(f"timeout-minutes 必须 1..90：{timeout!r}")
    checkout = [s for s in _steps(job) if "actions/checkout" in str(s.get("uses") or "")]
    if not checkout:
        issues.append("缺 checkout")
    else:
        with_args = checkout[0].get("with") or {}
        if with_args.get("fetch-depth") != 0:
            issues.append("checkout 必须 fetch-depth: 0（金标快照要 git archive 祖先提交）")
        if with_args.get("persist-credentials") is not False:
            issues.append("checkout 必须 persist-credentials: false")
    runs = _runs(job)
    for cmd in ("dotnet --list-sdks", "pwsh", "bash --version"):
        if cmd not in runs:
            issues.append(f"工具链自述缺：{cmd}")
    if "缺 .NET 8 SDK" not in runs:
        issues.append(".NET 8 主版本守卫必须显式报错")
    if "git archive" not in runs or "NF_SNAP_REF" not in runs:
        issues.append("金标快照必须 git archive $NF_SNAP_REF")
    if "tarfile" not in runs:
        issues.append("快照解包必须用 Python tarfile（bsdtar 解 CJK 路径会丢文件）")
    if "快照 ref 不在历史里" not in runs:
        issues.append("快照 ref 不可用必须 fail-fast 并给可执行提示")
    if "RUNNER_TEMP" not in runs:
        issues.append("树外构建铁律：必须用 RUNNER_TEMP")
    for rid in ("win-x64", "linux-x64"):
        if rid not in runs:
            issues.append(f"必须 publish 两个 RID 交付形态：{rid}")
    for placeholder in ("-Cli", "-Parity", "-Snap", "-Other", "-Python", "-Bash", "-Tier"):
        if placeholder not in runs:
            issues.append(f"跑批参数缺占位符解析：{placeholder}")
    for marker in ("git commit", "git push", "git add "):
        if marker in runs:
            issues.append(f"只读作业不得出现写仓库动作：{marker}")
    if not MANIFEST.is_file():
        issues.append("缺探针清单 engine/dotnet/probes/probe_manifest.json（口径唯一出处）")
    uploads = [s for s in _steps(job) if "upload-artifact" in str(s.get("uses") or "")]
    if not uploads:
        issues.append("缺失败证据工件")
    for step in uploads:
        if str(step.get("if") or "").strip() != "failure()":
            issues.append("探针证据工件应只在 failure() 上传（成功时不产噪声）")
        with_args = step.get("with") or {}
        if "matrix.os" not in str(with_args.get("name") or ""):
            issues.append("工件名必须含 matrix.os")
        days = with_args.get("retention-days")
        if not isinstance(days, int) or not 1 <= days <= MAX_RETENTION:
            issues.append(f"工件 retention-days 必须 1..{MAX_RETENTION}：{days!r}")
    return issues


class NetProbesWorkflowContractTest(unittest.TestCase):
    def setUp(self):
        self.text = WORKFLOW.read_text(encoding="utf-8")
        self.doc = load_workflow()

    def test_workflow_matches_contract(self):
        self.assertEqual([], workflow_issues(self.doc, self.text), "net-probes.yml 不满足契约")

    def test_manual_only_and_non_blocking(self):
        triggers = _on(self.doc)
        self.assertEqual(["workflow_dispatch"], [k for k in triggers if k == "workflow_dispatch"])
        for bad in ("schedule", "push", "pull_request"):
            self.assertNotIn(bad, triggers)
        self.assertIs(True, self.doc["jobs"]["probes"].get("continue-on-error"))

    def test_snapshot_and_dual_rid(self):
        runs = _runs(self.doc["jobs"]["probes"])
        self.assertIn("git archive", runs)
        self.assertIn("tarfile", runs)
        for rid in ("win-x64", "linux-x64"):
            self.assertIn(rid, runs)

    def test_contract_catches_broken_workflow(self):
        """变异自证（五类坏件都必须报）。

        覆盖：恢复 schedule / 去掉 continue-on-error / 金标不 fail-fast / 缺 RID / 无保留期。
        """
        import copy

        resched = copy.deepcopy(self.doc)
        _on(resched)["schedule"] = [{"cron": "0 0 * * 1"}]
        self.assertTrue(any("仅手动" in i for i in workflow_issues(resched, self.text)),
                        "恢复 schedule 必须报")
        blocking = copy.deepcopy(self.doc)
        blocking["jobs"]["probes"].pop("continue-on-error", None)
        self.assertTrue(any("continue-on-error" in i for i in workflow_issues(blocking, self.text)),
                        "去掉 continue-on-error 必须报")
        no_fail = copy.deepcopy(self.doc)
        for step in no_fail["jobs"]["probes"]["steps"]:
            run = str(step.get("run") or "")
            if "快照 ref 不在历史里" in run:
                step["run"] = "Write-Host 'skip'"
        self.assertTrue(any("fail-fast" in i for i in workflow_issues(no_fail, self.text)),
                        "金标不 fail-fast 必须报")
        one_rid = copy.deepcopy(self.doc)
        for step in one_rid["jobs"]["probes"]["steps"]:
            run = str(step.get("run") or "")
            if "linux-x64" in run:
                step["run"] = run.replace("linux-x64", "win-x64")
        self.assertTrue(any("RID" in i for i in workflow_issues(one_rid, self.text)),
                        "缺 RID 必须报")
        no_days = copy.deepcopy(self.doc)
        for step in no_days["jobs"]["probes"]["steps"]:
            if "upload-artifact" in str(step.get("uses") or ""):
                (step.get("with") or {}).pop("retention-days", None)
        self.assertTrue(any("retention" in i for i in workflow_issues(no_days, self.text)),
                        "无保留期必须报")
        with self.assertRaises(ValueError):
            load_workflow(ROOT / ".github" / "no_such_probes.yml")


if __name__ == "__main__":
    unittest.main()
