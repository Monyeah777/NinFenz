#!/usr/bin/env python3
"""gitee-poll 契约判据：共享写锁、无令牌不假红、凭据保留显式、工件有限留存（2026-11-11）。

为什么必须有：本 workflow 每 10 分钟跑一次、带 contents: write 与 Gitee 子令牌，是仓库里
**运行频率最高 + 唯一跨端推送**的面。三处都真实发生过或极易踩：①轮询与 GitHub 端入库必须
共用同一把写锁（否则两端同时分配编号会撞号）；②没配 GITEE_TOKEN 时若直接跑，每天 144 次
假红会把真失败淹掉（2026-11-07 实测）；③origin 端推送依赖 checkout 注入凭据，照抄别处
「关闭凭据」会让推送 401。本件把这三条钉成契约。

范围：只判 .github/workflows/gitee-poll.yml 与其脚本 .github/scripts/gitee_ingest.py。
同族判据：test_library_ingest_workflow_contract（GitHub 端同构）、test_intake_surface。
"""
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "gitee-poll.yml"
LIBRARY = ROOT / ".github" / "workflows" / "library-ingest.yml"
SCRIPT = ROOT / ".github" / "scripts" / "gitee_ingest.py"
MAX_RETENTION = 7


def load_workflow(path: Path = WORKFLOW) -> dict:
    """读 workflow YAML（缺失 / 非法 / 非映射 → ValueError）。"""
    try:
        doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ValueError(f"gitee-poll.yml 不可读/不可解析：{exc}") from exc
    if not isinstance(doc, dict):
        raise ValueError("gitee-poll.yml 根节点必须是映射")
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


def workflow_issues(doc: dict, text: str = "", library_group: str = "") -> list:
    """gitee 轮询契约问题列表（纯函数，便于变异自证）。"""
    issues = []
    if doc.get("permissions") != {"contents": "read"}:
        issues.append(f"顶层权限必须最小化（contents: read），实际 {doc.get('permissions')!r}")
    triggers = _on(doc)
    sched = triggers.get("schedule") or []
    if not sched or not any(str((s or {}).get("cron") or "").strip() for s in sched):
        issues.append("缺 schedule cron（轮询面）")
    if "workflow_dispatch" not in triggers:
        issues.append("缺 workflow_dispatch（人工重跑入口）")
    if "pull_request_target" in triggers:
        issues.append("不得使用 pull_request_target")
    conc = doc.get("concurrency") or {}
    group = str(conc.get("group") or "").strip()
    if group != "library-write":
        issues.append(f"跨端入库必须共用写锁 library-write，实际 {group!r}")
    if library_group and group != library_group:
        issues.append(f"与 library-ingest 的写锁不一致：{group!r} ≠ {library_group!r}")
    if conc.get("cancel-in-progress") is not False:
        issues.append("入库轮询不得被取消（cancel-in-progress 必须 false）")
    job = (doc.get("jobs") or {}).get("poll")
    if not job:
        return issues + ["缺作业：poll"]
    perm = job.get("permissions") or {}
    if sorted(perm.items()) != [("contents", "write")]:
        issues.append(f"poll 权限必须恰为 contents: write，实际 {perm!r}")
    timeout = job.get("timeout-minutes")
    if not isinstance(timeout, int) or not 1 <= timeout <= 20:
        issues.append(f"poll 的 timeout-minutes 必须 1..20：{timeout!r}")
    body = text if text else ""
    if "GITEE_TOKEN" not in body:
        issues.append("缺 GITEE_TOKEN 注入（子令牌）")
    guard = [s for s in _steps(job) if str(s.get("id") or "") == "guard"]
    if not guard:
        issues.append("缺凭据守卫步骤（无 token 时必须显式 skip，不许每天 144 次假红）")
    gated = [s for s in _steps(job) if "gitee_ingest.py" in str(s.get("run") or "")]
    if not gated:
        issues.append("缺轮询脚本调用：.github/scripts/gitee_ingest.py")
    elif "steps.guard.outputs.skip" not in str(gated[0].get("if") or ""):
        issues.append("轮询步骤必须由凭据守卫 output 门控（skip 时不跑）")
    if "persist-credentials: false" in body:
        issues.append("checkout 不得关闭凭据注入（origin 推送依赖它）")
    if "凭据" not in body:
        issues.append("checkout 的凭据保留必须显式说明")
    runs = _runs(job)
    for needle in ("fetch-depth: 0",):
        if needle not in body:
            issues.append("checkout 必须 fetch-depth: 0（两端推送/历史对账）")
    for step in _steps(job):
        if "upload-artifact" not in str(step.get("uses") or ""):
            continue
        if str(step.get("if") or "").strip() != "always()":
            issues.append("诊断工件必须 if: always()")
        days = (step.get("with") or {}).get("retention-days")
        if not isinstance(days, int) or not 1 <= days <= MAX_RETENTION:
            issues.append(f"工件 retention-days 必须 1..{MAX_RETENTION}：{days!r}")
    if "python3 .github/scripts/gitee_ingest.py" not in runs:
        issues.append("轮询调用必须走 python3 脚本")
    return issues


def script_issues(script_text: str) -> list:
    """脚本口径：子令牌只从 env 取、日志脱敏、双端推送、Gitee API 走 v5。"""
    issues = []
    for needle, why in (("GITEE_TOKEN", "令牌必须只从 env 取"),
                        ("redact", "日志必须脱敏（CWE-532）"),
                        ("push", "必须保留双端推送"),
                        ("gitee.com/api/v5", "Gitee API 必须走 v5")):
        if needle not in script_text:
            issues.append(f"脚本缺口径：{why}")
    return issues


class GiteePollWorkflowContractTest(unittest.TestCase):
    def setUp(self):
        self.text = WORKFLOW.read_text(encoding="utf-8")
        self.doc = load_workflow()
        self.library_group = str((load_workflow(LIBRARY).get("concurrency") or {})
                                 .get("group") or "")

    def test_workflow_matches_contract(self):
        self.assertEqual([], workflow_issues(self.doc, self.text, self.library_group),
                         "gitee-poll.yml 不满足契约")

    def test_shared_write_lock_with_library_ingest(self):
        """两端入库必须同一把锁：否则同时分配 NF 编号会撞号。"""
        self.assertEqual("library-write", self.library_group)
        self.assertEqual(self.library_group,
                         (self.doc.get("concurrency") or {}).get("group"))

    def test_missing_token_skips_instead_of_failing(self):
        """无凭据显式 skip：每 10 分钟一轮，假红会把真失败淹掉（2026-11-07 实测）。"""
        steps = _steps(self.doc["jobs"]["poll"])
        guard = [s for s in steps if str(s.get("id") or "") == "guard"]
        self.assertTrue(guard, "缺 guard 步骤")
        self.assertIn("skip=1", str(guard[0].get("run") or ""))
        gated = [s for s in steps if "gitee_ingest.py" in str(s.get("run") or "")]
        self.assertIn("steps.guard.outputs.skip", str(gated[0].get("if") or ""))

    def test_script_keeps_token_and_redaction_discipline(self):
        self.assertEqual([], script_issues(SCRIPT.read_text(encoding="utf-8")),
                         "gitee_ingest.py 口径缺失")

    def test_contract_catches_broken_workflow(self):
        """变异自证（五类坏件都必须报）。

        覆盖：去 guard / 去掉门控 / 关闭凭据 / 改锁名 / 无保留期。
        """
        import copy

        no_guard = copy.deepcopy(self.doc)
        no_guard["jobs"]["poll"]["steps"] = [s for s in no_guard["jobs"]["poll"]["steps"]
                                             if str(s.get("id") or "") != "guard"]
        self.assertTrue(any("守卫" in i for i in workflow_issues(no_guard, self.text)),
                        "去 guard 必须报")
        ungated = copy.deepcopy(self.doc)
        for step in ungated["jobs"]["poll"]["steps"]:
            if "gitee_ingest.py" in str(step.get("run") or ""):
                step.pop("if", None)
        self.assertTrue(any("门控" in i for i in workflow_issues(ungated, self.text)),
                        "去掉门控必须报")
        creds = self.text + "\n# persist-credentials: false\n"
        self.assertTrue(any("不得关闭凭据" in i for i in workflow_issues(self.doc, creds)),
                        "关闭凭据必须报")
        wrong_lock = copy.deepcopy(self.doc)
        wrong_lock["concurrency"]["group"] = "gitee-write"
        self.assertTrue(any("写锁" in i or "不一致" in i
                            for i in workflow_issues(wrong_lock, self.text)),
                        "改锁名必须报")
        no_days = copy.deepcopy(self.doc)
        for step in no_days["jobs"]["poll"]["steps"]:
            if "upload-artifact" in str(step.get("uses") or ""):
                (step.get("with") or {}).pop("retention-days", None)
        self.assertTrue(any("retention" in i for i in workflow_issues(no_days, self.text)),
                        "无保留期必须报")
        self.assertTrue(script_issues("nothing"), "脚本缺口径必须报")
        with self.assertRaises(ValueError):
            load_workflow(ROOT / ".github" / "no_such_gitee.yml")


if __name__ == "__main__":
    unittest.main()
