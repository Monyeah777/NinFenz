#!/usr/bin/env python3
"""e2e-desktop 契约判据：无 GUI 依赖、PR 全量、失败即红、证据可下载（2026-11-11）。

为什么必须有：这是桌面链路唯一的端到端实跑面。它最容易悄悄变味成三种样子：①被塞进 PySide6/QT
之类的 GUI 依赖（那么"无需 GUI 也能跑"的承诺就破了，且 runner 上会 flaky）；②PR 触发被加 paths
过滤（桌面回归要等合并后才发现）；③e2e 命令接上兜底假绿写法或去掉 tee（失败没有证据）。
本件把这些钉成契约，并与 release-gate 的 e2e 步骤交叉对账（同一脚本）。

范围：只判 .github/workflows/e2e-desktop.yml（交叉引用 release-gate.yml 与脚本文件）。
同族判据：test_release_gate_workflow_contract、test_ci_diagnostics（KEY_WORKFLOWS 工件面）。
"""
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "e2e-desktop.yml"
RELEASE = ROOT / ".github" / "workflows" / "release-gate.yml"
SCRIPT = ROOT / "scripts" / "e2e_desktop_headless.py"
MAX_RETENTION = 7
SWALLOW = "|| true"
#: 无 GUI 不变量：出现这些即说明它开始依赖显示栈
GUI_MARKERS = ("PySide6", "QT_QPA_PLATFORM", "pyside6", "xvfb")


def load_workflow(path: Path = WORKFLOW) -> dict:
    """读 workflow YAML（缺失 / 非法 / 非映射 → ValueError）。"""
    try:
        doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ValueError(f"e2e-desktop.yml 不可读/不可解析：{exc}") from exc
    if not isinstance(doc, dict):
        raise ValueError("e2e-desktop.yml 根节点必须是映射")
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


def workflow_issues(doc: dict, text: str = "", release_text: str = "") -> list:
    """桌面 e2e 契约问题列表（纯函数，便于变异自证）。"""
    issues = []
    body = text if text else ""
    if doc.get("permissions") != {"contents": "read"}:
        issues.append(f"顶层权限必须最小化（contents: read），实际 {doc.get('permissions')!r}")
    conc = doc.get("concurrency") or {}
    if conc.get("cancel-in-progress") is not True:
        issues.append("concurrency.cancel-in-progress 必须为 true")
    triggers = _on(doc)
    pr = triggers.get("pull_request")
    if "pull_request" not in triggers:
        issues.append("缺 pull_request 触发（桌面回归要能在评审时暴露）")
    elif isinstance(pr, dict) and pr.get("paths"):
        issues.append("PR 触发不应按 paths 限制（job 仅约 10 s，全量跑得起）")
    if (triggers.get("push") or {}).get("branches") != ["main"]:
        issues.append("push 触发必须限定 branches: [main]")
    if "workflow_dispatch" not in triggers:
        issues.append("缺 workflow_dispatch（人工重跑入口）")
    for marker in GUI_MARKERS:
        if marker in body:
            issues.append(f"桌面 e2e 必须无 GUI 依赖：出现 {marker}")
    job = (doc.get("jobs") or {}).get("e2e-headless")
    if not job:
        return issues + ["缺作业：e2e-headless"]
    if str(job.get("name") or "").strip() != "desktop-headless-e2e":
        issues.append("作业名必须稳定（desktop-headless-e2e）")
    timeout = job.get("timeout-minutes")
    if not isinstance(timeout, int) or not 1 <= timeout <= 30:
        issues.append(f"timeout-minutes 必须 1..30：{timeout!r}")
    runs = _runs(job)
    if "e2e_desktop_headless.py" not in runs:
        issues.append("缺端到端脚本调用：scripts/e2e_desktop_headless.py")
    if "python3 " not in runs:
        issues.append("调用必须用 python3（与脚本 shebang/CI 口径一致）")
    if "set -o pipefail" not in runs:
        issues.append("缺显式 set -o pipefail（tee 会吞退出码）")
    if "tee e2e-desktop.log" not in runs:
        issues.append("e2e 输出未落盘（失败无诊断物）")
    if SWALLOW in runs:
        issues.append(f"e2e 命令不得接兜底假绿写法（{SWALLOW}）")
    uploads = [s for s in _steps(job) if "upload-artifact" in str(s.get("uses") or "")]
    if not uploads:
        issues.append("缺失败诊断工件")
    for step in uploads:
        if str(step.get("if") or "").strip() != "always()":
            issues.append("诊断工件必须 if: always()")
        with_args = step.get("with") or {}
        if "*.log" not in str(with_args.get("path") or ""):
            issues.append("工件未包含 e2e 日志")
        days = with_args.get("retention-days")
        if not isinstance(days, int) or not 1 <= days <= MAX_RETENTION:
            issues.append(f"工件 retention-days 必须 1..{MAX_RETENTION}：{days!r}")
    if release_text and "e2e_desktop_headless.py" not in release_text:
        issues.append("release-gate 未跑同一 e2e 脚本（两处口径不一致）")
    return issues


class E2eDesktopWorkflowContractTest(unittest.TestCase):
    def setUp(self):
        self.text = WORKFLOW.read_text(encoding="utf-8")
        self.doc = load_workflow()

    def test_workflow_matches_contract(self):
        self.assertEqual([], workflow_issues(self.doc, self.text,
                                             RELEASE.read_text(encoding="utf-8")),
                         "e2e-desktop.yml 不满足契约")

    def test_headless_no_gui_dependency(self):
        """无 GUI 不变量：不装 PySide6、不设 QT 平台、不引 xvfb。"""
        for marker in GUI_MARKERS:
            self.assertNotIn(marker, self.text)

    def test_same_script_as_release_gate(self):
        self.assertTrue(SCRIPT.is_file())
        self.assertIn("e2e_desktop_headless.py", RELEASE.read_text(encoding="utf-8"))

    def test_contract_catches_broken_workflow(self):
        """变异自证（五类坏件都必须报）。

        覆盖：加 GUI 依赖 / 加 paths / 接兜底写法 / 失日志 / 无保留期。
        """
        import copy

        gui = self.text + "\n# run: pip install PySide6\n"
        self.assertTrue(any("GUI" in i for i in workflow_issues(self.doc, gui)),
                        "加 GUI 依赖必须报")
        filtered = copy.deepcopy(self.doc)
        _on(filtered)["pull_request"] = {"paths": ["desktop/**"]}
        self.assertTrue(any("paths" in i for i in workflow_issues(filtered, self.text)),
                        "加 PR paths 必须报")
        swallowed = copy.deepcopy(self.doc)
        for step in swallowed["jobs"]["e2e-headless"]["steps"]:
            if "e2e_desktop_headless.py" in str(step.get("run") or ""):
                step["run"] = str(step["run"]) + " " + SWALLOW
        self.assertTrue(any(SWALLOW in i for i in workflow_issues(swallowed, self.text)),
                        "接兜底写法必须报")
        no_log = copy.deepcopy(self.doc)
        for step in no_log["jobs"]["e2e-headless"]["steps"]:
            if "e2e_desktop_headless.py" in str(step.get("run") or ""):
                step["run"] = str(step["run"]).replace(" | tee e2e-desktop.log", "")
        self.assertTrue(any("落盘" in i for i in workflow_issues(no_log, self.text)),
                        "失日志必须报")
        no_days = copy.deepcopy(self.doc)
        for step in no_days["jobs"]["e2e-headless"]["steps"]:
            if "upload-artifact" in str(step.get("uses") or ""):
                (step.get("with") or {}).pop("retention-days", None)
        self.assertTrue(any("retention" in i for i in workflow_issues(no_days, self.text)),
                        "无保留期必须报")
        with self.assertRaises(ValueError):
            load_workflow(ROOT / ".github" / "no_such_e2e.yml")


if __name__ == "__main__":
    unittest.main()
