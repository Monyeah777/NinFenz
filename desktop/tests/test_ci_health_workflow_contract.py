#!/usr/bin/env python3
"""ci-health 契约判据：静默红看门狗须「只读、最新一次口径、自引用排除、快照不判红」（2026-11-11）。

为什么必须有：本 workflow 是唯一能发现「定时面天天红但没人看见」的面（net-probes / gitee-poll
都真实发生过）。它一旦退化就会自己制造假绿/假红：① 去掉自引用排除 → 一次失败后永远在报上一次的
自己（死循环）；② 把 cancelled/skipped 当失败 → 瞬时假红；③ 快照步骤不再 continue-on-error → 权限
不足直接判红；④ 只取一页 → 长期不跑的 workflow 滑出窗口而假绿。本件把这几条钉成契约。

范围：只判 .github/workflows/ci-health.yml。同族判据：test_ci_verify_contract、
test_ci_diagnostics（KEY_WORKFLOWS 工件面）。
"""
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "ci-health.yml"
OWN_PATH = ".github/workflows/ci-health.yml"
#: 看门狗只读：不得 checkout / 写仓库 / 开 issue
READONLY_MARKERS = ("actions/checkout", "git commit", "git push", "git add ")
ENDPOINTS = ("code-scanning", "secret-scanning", "dependabot")


def load_workflow(path: Path = WORKFLOW) -> dict:
    """读 workflow YAML（缺失 / 非法 / 非映射 → ValueError）。"""
    try:
        doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ValueError(f"ci-health.yml 不可读/不可解析：{exc}") from exc
    if not isinstance(doc, dict):
        raise ValueError("ci-health.yml 根节点必须是映射")
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


def _has_enough_schedule_slots(crons: list) -> bool:
    """cron 可以是 4 条，也可以是 1 条带 4 个钟点的（如 0 5,11,17,23 * * *）。"""
    if len([c for c in crons if c.strip()]) >= 4:
        return True
    hours = set()
    for c in crons:
        parts = c.split()
        if len(parts) < 2 or "*" in parts[1]:
            continue
        for h in parts[1].split(","):
            if h.strip().isdigit():
                hours.add(h.strip())
    return len(hours) >= 4


def workflow_issues(doc: dict, text: str = "") -> list:
    """看门狗契约问题列表（纯函数，便于变异自证）。"""
    issues = []
    body = text if text else ""
    perm = doc.get("permissions")
    if not isinstance(perm, dict) or sorted(perm.items()) != sorted(
            {"actions": "read", "contents": "read", "security-events": "read"}.items()):
        issues.append(f"权限必须恰为 actions/contents/security-events 三个 read，实际 {perm!r}")
    for marker in READONLY_MARKERS:
        if marker in body:
            issues.append(f"看门狗必须只读：出现 {marker}")
    triggers = _on(doc)
    if (triggers.get("push") or {}).get("branches") != ["main"]:
        issues.append("push 触发必须限定 branches: [main]（合并即体检，不依赖 cron 投递）")
    sched = triggers.get("schedule") or []
    crons = [str((s or {}).get("cron") or "") for s in sched]
    if not _has_enough_schedule_slots(crons):
        issues.append(f"schedule 每天至少 4 次（平台节流下多给投递机会），实际 {crons!r}")
    if "workflow_dispatch" not in triggers:
        issues.append("缺 workflow_dispatch（人工即时体检入口）")
    job = (doc.get("jobs") or {}).get("scheduled-red-audit")
    if not job:
        return issues + ["缺作业：scheduled-red-audit"]
    if str(job.get("name") or "").strip() != "scheduled-red-audit":
        issues.append("作业名必须稳定（scheduled-red-audit）")
    timeout = job.get("timeout-minutes")
    if not isinstance(timeout, int) or not 1 <= timeout <= 10:
        issues.append(f"timeout-minutes 必须 1..10：{timeout!r}")
    runs = _runs(job)
    if "event=schedule" not in runs:
        issues.append("缺 schedule 面审计（event=schedule）")
    if "page=%d" not in runs:
        issues.append("缺分页（长期不跑的 workflow 会滑出窗口而假绿）")
    if "== own" not in runs:
        issues.append(f"缺自引用排除（{OWN_PATH}）；否则一次失败后永远在报上一次的自己")
    if "timed_out" not in runs:
        issues.append("失败口径必须含 timed_out")
    if "SystemExit(1)" not in runs:
        issues.append("发现失败必须显式 exit 1（不许只打印）")
    if "::error::" not in runs:
        issues.append("失败必须在 Actions 面上显式可见（::error::）")
    if "branch=main" not in runs:
        issues.append("缺 main 分支全 workflow 审计（抓非 required 的静默红）")
    if '"cancelled"' in runs or "'cancelled'" in runs:
        issues.append("不得把 cancelled/skipped 计入失败结论（否则瞬时假红）")
    if "cancelled" not in body:
        issues.append("口径必须写明 cancelled/skipped 不算失败（否则瞬时假红）")
    steps = _steps(job)
    snapshot = [s for s in steps if "continue-on-error" in s]
    if not snapshot or snapshot[0].get("continue-on-error") is not True:
        issues.append("安全面快照必须 continue-on-error: true（信息性，不判红）")
    snap_runs = "\n".join(str(s.get("run") or "") for s in snapshot)
    for ep in ENDPOINTS:
        if ep not in snap_runs:
            issues.append(f"安全面快照缺端点：{ep}")
    if "NA" not in snap_runs:
        issues.append("快照必须对权限不足打印 NA 而不是判红")
    return issues


class CiHealthWorkflowContractTest(unittest.TestCase):
    def setUp(self):
        self.text = WORKFLOW.read_text(encoding="utf-8")
        self.doc = load_workflow()

    def test_workflow_matches_contract(self):
        self.assertEqual([], workflow_issues(self.doc, self.text), "ci-health.yml 不满足契约")

    def test_read_only_watchdog(self):
        for marker in READONLY_MARKERS:
            self.assertNotIn(marker, self.text)

    def test_latest_run_semantics(self):
        """口径：只取最新一次、排除自身、cancelled/skipped 不算失败。"""
        runs = _runs(self.doc["jobs"]["scheduled-red-audit"])
        self.assertIn("== own", runs)
        self.assertIn("timed_out", runs)
        self.assertNotIn('"cancelled"', runs)

    def test_contract_catches_broken_workflow(self):
        """变异自证（五类坏件都必须报）。

        覆盖：去自引用排除 / 把 cancelled 当失败 / 去 continue-on-error / 去分页 / 去 push 触发。
        """
        import copy

        no_self = copy.deepcopy(self.doc)
        for step in no_self["jobs"]["scheduled-red-audit"]["steps"]:
            run = str(step.get("run") or "")
            if "== own" in run:
                step["run"] = run.replace("== own", "== 'never'")
        self.assertTrue(any("自引用" in i
                            for i in workflow_issues(no_self, yaml.safe_dump(no_self))),
                        "去自引用排除必须报")
        cancelled = copy.deepcopy(self.doc)
        for step in cancelled["jobs"]["scheduled-red-audit"]["steps"]:
            run = str(step.get("run") or "")
            if '"failure", "timed_out"' in run:
                step["run"] = run.replace('"failure", "timed_out"',
                                          '"failure", "timed_out", "cancelled"')
        self.assertTrue(any("cancelled" in i
                            for i in workflow_issues(cancelled, yaml.safe_dump(cancelled))),
                        "把 cancelled 当失败必须报")
        no_ce = copy.deepcopy(self.doc)
        for step in no_ce["jobs"]["scheduled-red-audit"]["steps"]:
            step.pop("continue-on-error", None)
        self.assertTrue(any("continue-on-error" in i
                            for i in workflow_issues(no_ce, yaml.safe_dump(no_ce))),
                        "去 continue-on-error 必须报")
        no_page = copy.deepcopy(self.doc)
        for step in no_page["jobs"]["scheduled-red-audit"]["steps"]:
            run = str(step.get("run") or "")
            if "page=%d" in run:
                step["run"] = "url = 'https://api.github.com/x\\n'"
        self.assertTrue(any("分页" in i
                            for i in workflow_issues(no_page, yaml.safe_dump(no_page))),
                        "去分页必须报")
        no_push = copy.deepcopy(self.doc)
        _on(no_push).pop("push", None)
        self.assertTrue(any("push" in i
                            for i in workflow_issues(no_push, yaml.safe_dump(no_push))),
                        "去 push 触发必须报")
        with self.assertRaises(ValueError):
            load_workflow(ROOT / ".github" / "no_such_health.yml")


if __name__ == "__main__":
    unittest.main()
