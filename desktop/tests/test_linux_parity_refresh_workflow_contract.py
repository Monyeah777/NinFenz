#!/usr/bin/env python3
"""linux-parity-refresh 契约判据：跨平台漂移刷新器必须「只读、证据可下载、漂移判红」（2026-11-11）。

为什么必须有：这是唯一"在 Linux 上重算生成物"的作业，最容易被误改成回写机器人——一旦加
contents: write 或 git push，就变成"机器人自己刷基线"（漂移被自动掩盖）。另外它此前零判据：
工件无保留期、漂移判定被改成总数比较、或证据件缺失都不会红。

范围：只判 .github/workflows/linux-parity-refresh.yml。
同族判据：test_ci_diagnostics（ParityKeyCompareTest 从文本侧守键级比对）、test_ci_verify_contract。
"""
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "linux-parity-refresh.yml"
MAX_RETENTION = 7
#: 只读契约：出现这些即说明它变成了回写机器人
WRITE_MARKERS = ("contents: write", "git push", "git commit", "git add ")


def load_workflow(path: Path = WORKFLOW) -> dict:
    """读 workflow YAML（缺失 / 非法 / 非映射 → ValueError）。"""
    try:
        doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ValueError(f"linux-parity-refresh.yml 不可读/不可解析：{exc}") from exc
    if not isinstance(doc, dict):
        raise ValueError("linux-parity-refresh.yml 根节点必须是映射")
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
    """只读刷新器契约问题列表（纯函数，便于变异自证）。"""
    issues = []
    if doc.get("permissions") != {"contents": "read"}:
        issues.append(f"顶层权限必须最小化（contents: read），实际 {doc.get('permissions')!r}")
    body = text if text else ""
    for marker in WRITE_MARKERS:
        if marker in body:
            issues.append(f"只读刷新器不得出现回写动作：{marker}")
    conc = doc.get("concurrency") or {}
    if conc.get("cancel-in-progress") is not True:
        issues.append("concurrency.cancel-in-progress 必须为 true（只读作业可取消）")
    triggers = _on(doc)
    if "workflow_dispatch" not in triggers:
        issues.append("缺 workflow_dispatch（人工重跑入口）")
    sched = triggers.get("schedule") or []
    if not sched or not any(str((s or {}).get("cron") or "").strip() for s in sched):
        issues.append("缺周 schedule（跨平台漂移要定期告警）")
    if "pull_request" in triggers:
        issues.append("刷新器不应在 pull_request 触发（生成物重算与 PR 无关）")
    job = (doc.get("jobs") or {}).get("refresh")
    if not job:
        return issues + ["缺作业：refresh"]
    if str(job.get("name") or "").strip() != "linux-parity-refresh":
        issues.append("refresh 作业名必须稳定（linux-parity-refresh）")
    timeout = job.get("timeout-minutes")
    if not isinstance(timeout, int) or not 1 <= timeout <= 30:
        issues.append(f"refresh 的 timeout-minutes 必须 1..30：{timeout!r}")
    runs = _runs(job)
    if "--require-hashes" not in runs:
        issues.append("工具安装未固定（缺 --require-hashes）")
    for name in ("requirements-ci.txt", "requirements-lint.txt", "requirements-sast.txt"):
        if name not in runs:
            issues.append(f"工具安装缺固定集：{name}")
    for needle, why in (("--platform posix", "posix SAST 计数必须显式指定平台"),
                        ("sast-posix.json", "posix 计数必须留证据件"),
                        ("evidence_vectors.py --write", "证据向量必须 Linux 重算"),
                        ("vectors.diff", "向量漂移必须落 diff"),
                        ("projections.diff", "投影漂移必须落 diff"),
                        ("protocol/sast_baseline.json", "必须与基线真源比对")):
        if needle not in runs:
            issues.append(f"缺漂移检测要素：{why}")
    if '[ -s "$f" ]' not in runs and "-s \"$f\"" not in runs:
        issues.append("漂移判定缺非空检查（[ -s $f ]）")
    if "for f in vectors.diff projections.diff" not in runs:
        issues.append("漂移判定未同时覆盖两份 diff")
    for needle in ("extra", "missing", "changed"):
        if needle not in runs:
            issues.append(f"SAST 漂移必须键级比对（缺 {needle}）")
    for step in _steps(job):
        if "upload-artifact" not in str(step.get("uses") or ""):
            continue
        if str(step.get("if") or "").strip() != "always()":
            issues.append("漂移证据工件必须 if: always()")
        with_args = step.get("with") or {}
        path_text = str(with_args.get("path") or "")
        for name in ("sast-posix.json", "vectors.diff", "projections.diff"):
            if name not in path_text:
                issues.append(f"证据工件缺 {name}")
        days = with_args.get("retention-days")
        if not isinstance(days, int) or not 1 <= days <= MAX_RETENTION:
            issues.append(f"工件 retention-days 必须 1..{MAX_RETENTION}：{days!r}")
    return issues


class LinuxParityRefreshWorkflowContractTest(unittest.TestCase):
    def setUp(self):
        self.text = WORKFLOW.read_text(encoding="utf-8")
        self.doc = load_workflow()

    def test_workflow_matches_contract(self):
        self.assertEqual([], workflow_issues(self.doc, self.text),
                         "linux-parity-refresh.yml 不满足契约")

    def test_never_writes_to_repository(self):
        """只读不变量：一旦加写权限或 push，漂移会被机器人自动掩盖。"""
        self.assertNotIn("contents: write", self.text)
        for marker in ("git push", "git commit", "git add "):
            self.assertNotIn(marker, self.text, f"刷新器出现回写动作：{marker}")

    def test_drift_evidence_is_downloadable(self):
        upload = [s for s in _steps(self.doc["jobs"]["refresh"])
                  if "upload-artifact" in str(s.get("uses") or "")]
        self.assertTrue(upload)
        upload_text = str(upload[0].get("with") or {})
        for name in ("sast-posix.json", "vectors.diff", "projections.diff"):
            self.assertIn(name, upload_text)

    def test_contract_catches_broken_workflow(self):
        """变异自证（五类坏件都必须报）。

        覆盖：加写权限 / 加 git push / 去 retention / 去键级比对 / 去 schedule。
        """
        import copy

        writer = copy.deepcopy(self.doc)
        writer["permissions"] = {"contents": "write"}
        self.assertTrue(any("回写" in i or "权限" in i
                            for i in workflow_issues(writer, self.text)),
                        "写权限必须报")
        pusher = self.text + "\n#   run: git push origin HEAD:main\n"
        self.assertTrue(any("git push" in i for i in workflow_issues(self.doc, pusher)),
                        "git push 必须报")
        no_retention = copy.deepcopy(self.doc)
        for step in no_retention["jobs"]["refresh"]["steps"]:
            if "upload-artifact" in str(step.get("uses") or ""):
                (step.get("with") or {}).pop("retention-days", None)
        self.assertTrue(any("retention" in i for i in workflow_issues(no_retention, self.text)),
                        "无保留期必须报")
        total_only = copy.deepcopy(self.doc)
        for step in total_only["jobs"]["refresh"]["steps"]:
            if "键级漂移" in str(step.get("run") or ""):
                step["run"] = "python -c 'got != want'"
        self.assertTrue(any("键级" in i for i in workflow_issues(total_only, self.text)),
                        "退化成总数比较必须报")
        no_sched = copy.deepcopy(self.doc)
        _on(no_sched).pop("schedule", None)
        self.assertTrue(any("schedule" in i for i in workflow_issues(no_sched, self.text)),
                        "去 schedule 必须报")
        with self.assertRaises(ValueError):
            load_workflow(ROOT / ".github" / "no_such_parity.yml")


if __name__ == "__main__":
    unittest.main()
