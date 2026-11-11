#!/usr/bin/env python3
"""external-links 契约判据：非门禁定位、离线面永远绿、联网面有硬预算、报告只走工件（2026-11-11）。

为什么必须有：这是仓库里唯一「主动联网」的常驻面，最容易退化：①被塞进 push/PR（把网络抖动
变成每次提交的门禁红，破坏"门禁须静态可复现"红线）；②联网面接上 || true（失效链接被吞）；
③没有时间预算（慢站点把 job 拖到 15 min 超时，红的原因不可见）；④把受跟踪 results/ 原件当工件
上传（失败时上传的是上一次提交的旧结论，N1 同类）。本件把定位、预算、证据钉成契约。

范围：只判 .github/workflows/external-links.yml 与其脚本 scripts/check_external_links.py。
同族判据：test_ci_supply_chain、test_ci_diagnostics（ArtifactPolicyTest）。
"""
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "external-links.yml"
SCRIPT = ROOT / "scripts" / "check_external_links.py"
MAX_BUDGET = 600
MAX_RETENTION = 7


def load_workflow(path: Path = WORKFLOW) -> dict:
    """读 workflow YAML（缺失 / 非法 / 非映射 → ValueError）。"""
    try:
        doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ValueError(f"external-links.yml 不可读/不可解析：{exc}") from exc
    if not isinstance(doc, dict):
        raise ValueError("external-links.yml 根节点必须是映射")
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
    """外网巡检契约问题列表（纯函数，便于变异自证）。"""
    issues = []
    body = text if text else ""
    if doc.get("permissions") != {"contents": "read"}:
        issues.append(f"顶层权限必须最小化（contents: read），实际 {doc.get('permissions')!r}")
    triggers = _on(doc)
    if "push" in triggers:
        issues.append("不得在 push 触发（网络抖动会污染每次提交的门禁）")
    if "pull_request" in triggers:
        issues.append("不得在 pull_request 触发（同上）")
    if "workflow_dispatch" not in triggers:
        issues.append("缺 workflow_dispatch（人工重跑入口）")
    sched = triggers.get("schedule") or []
    if not sched or not any(str((s or {}).get("cron") or "").strip() for s in sched):
        issues.append("缺周 schedule")
    conc = doc.get("concurrency") or {}
    if str(conc.get("group") or "").strip() != "external-links":
        issues.append("concurrency.group 应为 external-links（独立于门禁）")
    job = (doc.get("jobs") or {}).get("check-links")
    if not job:
        return issues + ["缺作业：check-links"]
    timeout = job.get("timeout-minutes")
    if not isinstance(timeout, int) or not 1 <= timeout <= 20:
        issues.append(f"timeout-minutes 必须 1..20：{timeout!r}")
    runs = _runs(job)
    if "|| true" in runs:
        issues.append("联网面不得接兜底假绿写法（失效链接被吞）")
    if "set -o pipefail" not in runs:
        issues.append("缺显式 set -o pipefail（tee 会吞退出码）")
    if "--max-seconds" not in runs:
        issues.append(f"联网面必须给硬预算 --max-seconds（≤{MAX_BUDGET}；否则慢站点拖到 job 超时）")
    else:
        import re
        m = re.search(r"--max-seconds\s+(\d+)", runs)
        if not m or int(m.group(1)) > MAX_BUDGET:
            issues.append(f"--max-seconds 必须 ≤ {MAX_BUDGET}")
    if "check_external_links.py" not in runs:
        issues.append("缺巡检脚本调用")
    offline = [s for s in _steps(job) if "check_external_links.py" in str(s.get("run") or "")
               and "--fetch" not in str(s.get("run") or "")]
    if not offline:
        issues.append("缺离线扫描步（不联网、永远绿，先证明解析面健康）")
    fetch = [s for s in _steps(job) if "--fetch" in str(s.get("run") or "")]
    if not fetch:
        issues.append("缺联网探测步（--fetch）")
    else:
        fr = str(fetch[0].get("run") or "")
        if "--write" not in fr:
            issues.append("联网步必须落盘报告（--write）")
        if "tee" not in fr:
            issues.append("联网步日志必须 tee 落盘（失败无证据）")
    uploads = [s for s in _steps(job) if "upload-artifact" in str(s.get("uses") or "")]
    if not uploads:
        issues.append("缺报告工件")
    for step in uploads:
        if str(step.get("if") or "").strip() != "always()":
            issues.append("报告工件必须 if: always()（失败也要留证据）")
        path_text = str((step.get("with") or {}).get("path") or "")
        for line in path_text.splitlines():
            item = line.strip()
            if not item:
                continue
            if not item.startswith(".artifacts/"):
                issues.append(f"工件只能传 .artifacts/ 副本（不许传受跟踪路径）：{item}")
        days = (step.get("with") or {}).get("retention-days")
        if not isinstance(days, int) or not 1 <= days <= MAX_RETENTION:
            issues.append(f"工件 retention-days 必须 1..{MAX_RETENTION}：{days!r}")
    if "bash verify.sh" in body:
        issues.append("外链巡检不进 verify 基线（不得调用 verify.sh）")
    return issues


class ExternalLinksWorkflowContractTest(unittest.TestCase):
    def setUp(self):
        self.text = WORKFLOW.read_text(encoding="utf-8")
        self.doc = load_workflow()

    def test_workflow_matches_contract(self):
        self.assertEqual([], workflow_issues(self.doc, self.text), "external-links.yml 不满足契约")

    def test_non_gate_positioning(self):
        """非门禁定位：不 push/PR 触发、不调 verify.sh、独立并发组。"""
        triggers = _on(self.doc)
        self.assertNotIn("push", triggers)
        self.assertNotIn("pull_request", triggers)
        self.assertNotIn("bash verify.sh", self.text)

    def test_network_face_has_budget_and_fails_closed(self):
        runs = _runs(self.doc["jobs"]["check-links"])
        self.assertIn("--max-seconds", runs)
        self.assertNotIn("|| true", runs)
        self.assertIn("set -o pipefail", runs)

    def test_contract_catches_broken_workflow(self):
        """变异自证（五类坏件都必须报）。

        覆盖：加 push 触发 / 接兜底写法 / 去预算 / 上传受跟踪路径 / 无保留期。
        """
        import copy

        on_push = copy.deepcopy(self.doc)
        _on(on_push)["push"] = {"branches": ["main"]}
        self.assertTrue(any("push" in i for i in workflow_issues(on_push, self.text)),
                        "加 push 触发必须报")
        swallow = copy.deepcopy(self.doc)
        for step in swallow["jobs"]["check-links"]["steps"]:
            if "--fetch" in str(step.get("run") or ""):
                step["run"] = str(step.get("run")) + " || true"
        self.assertTrue(any("兜底" in i for i in workflow_issues(swallow, self.text)),
                        "接兜底写法必须报")
        no_budget = copy.deepcopy(self.doc)
        for step in no_budget["jobs"]["check-links"]["steps"]:
            run = str(step.get("run") or "")
            if "--max-seconds" in run:
                step["run"] = run.replace("--max-seconds 600", "")
        self.assertTrue(any("预算" in i for i in workflow_issues(no_budget, self.text)),
                        "去预算必须报")
        tracked_upload = copy.deepcopy(self.doc)
        for step in tracked_upload["jobs"]["check-links"]["steps"]:
            if "upload-artifact" in str(step.get("uses") or ""):
                (step.get("with") or {})["path"] = "results/external-links-report.json"
        self.assertTrue(any("受跟踪" in i
                            for i in workflow_issues(tracked_upload, self.text)),
                        "上传受跟踪路径必须报")
        no_days = copy.deepcopy(self.doc)
        for step in no_days["jobs"]["check-links"]["steps"]:
            if "upload-artifact" in str(step.get("uses") or ""):
                (step.get("with") or {}).pop("retention-days", None)
        self.assertTrue(any("retention" in i for i in workflow_issues(no_days, self.text)),
                        "无保留期必须报")
        self.assertTrue(SCRIPT.is_file())
        with self.assertRaises(ValueError):
            load_workflow(ROOT / ".github" / "no_such_links.yml")


if __name__ == "__main__":
    unittest.main()
