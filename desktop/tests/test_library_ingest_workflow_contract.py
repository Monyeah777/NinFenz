#!/usr/bin/env python3
"""library-ingest 契约判据：入库机器人是「带写权限 + 公开输入」面，口径必须显式（2026-11-11）。

为什么必须有：library-ingest 用 issues 事件 + contents/issues 写权限跑机器人，输入是任意
Issue 正文。两类事故都真实发生过：①正文走 env 触发 E2BIG（步骤起不来，超长拒收永远不生效）；
②照抄其他 workflow 的 persist-credentials: false 会让 git push 401。两者都不会被任何判据拦住，
且改错后只在「真有人投稿时」才炸。本件把工作流与脚本两条口径钉成契约。

范围：只判 .github/workflows/library-ingest.yml 与其脚本 .github/scripts/library_ingest.py。
同族判据：test_intake_bots_hardening、test_intake_surface。
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "library-ingest.yml"
SCRIPT = ROOT / ".github" / "scripts" / "library_ingest.py"
MAX_RETENTION = 7
TOKEN_SHAPE = re.compile(r"(ghp_[0-9A-Za-z]{36}|github_pat_[0-9A-Za-z_]{22,}|sk-[0-9A-Za-z]{20,})")


def load_workflow(path: Path = WORKFLOW) -> dict:
    """读 workflow YAML（缺失 / 非法 / 非映射 → ValueError）。"""
    try:
        import yaml
    except ModuleNotFoundError as exc:
        raise ValueError(f"缺 PyYAML：{exc}") from exc
    try:
        doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ValueError(f"library-ingest.yml 不可读/不可解析：{exc}") from exc
    if not isinstance(doc, dict):
        raise ValueError("library-ingest.yml 根节点必须是映射")
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
    """入库工作流契约问题列表（纯函数，便于变异自证）。"""
    issues = []
    if doc.get("permissions") != {"contents": "read"}:
        issues.append(f"顶层权限必须最小化（contents: read），实际 {doc.get('permissions')!r}")
    triggers = _on(doc)
    if "pull_request_target" in triggers:
        issues.append("不得使用 pull_request_target（会给 fork 写权限）")
    if "issue_comment" in triggers:
        issues.append("不得由 issue_comment 触发（评论即执行 = 可被滥用）")
    issues_cfg = triggers.get("issues") or {}
    types = [str(t) for t in (issues_cfg.get("types") or [])]
    if types != ["opened"]:
        issues.append(f"issues 触发必须恰为 types: [opened]，实际 {types!r}")
    conc = doc.get("concurrency") or {}
    if str(conc.get("group") or "").strip() != "library-write":
        issues.append("编号分配必须串行：concurrency.group 应为 library-write")
    if conc.get("cancel-in-progress") is not False:
        issues.append("入库不得被取消（cancel-in-progress 必须 false）")
    job = (doc.get("jobs") or {}).get("ingest")
    if not job:
        return issues + ["缺作业：ingest"]
    gate = str(job.get("if") or "")
    if "startsWith" not in gate or "【NF投稿】" not in gate:
        issues.append("ingest 缺标题守卫（startsWith 【NF投稿】）")
    perm = job.get("permissions") or {}
    if sorted(perm.items()) != sorted({"contents": "write", "issues": "write"}.items()):
        issues.append("ingest 权限必须恰为 contents: write + issues: write")
    timeout = job.get("timeout-minutes")
    if not isinstance(timeout, int) or not 1 <= timeout <= 20:
        issues.append(f"ingest 的 timeout-minutes 必须 1..20：{timeout!r}")
    runs = _runs(job)
    if ".github/scripts/library_ingest.py" not in runs:
        issues.append("缺入库脚本调用：python3 .github/scripts/library_ingest.py")
    body = text if text else ""
    if "github.event.issue.body" in body:
        issues.append("正文不得走 env（E2BIG 会让超长拒收判据失效）：改为 API 取正文")
    if "persist-credentials: false" in body:
        issues.append("checkout 不得写 persist-credentials: false（git push 依赖注入凭据）")
    if "凭据" not in body:
        issues.append("checkout 的凭据保留必须显式说明（写清为什么与其它 workflow 不同）")
    if TOKEN_SHAPE.search(body):
        issues.append("workflow 里出现明文 token 形状字符串")
    for step in _steps(job):
        if "upload-artifact" not in str(step.get("uses") or ""):
            continue
        if str(step.get("if") or "").strip() != "always()":
            issues.append("诊断工件必须 if: always()")
        days = (step.get("with") or {}).get("retention-days")
        if not isinstance(days, int) or not 1 <= days <= MAX_RETENTION:
            issues.append(f"诊断工件 retention-days 必须 1..{MAX_RETENTION}：{days!r}")
    return issues


def script_issues(script_text: str) -> list:
    """脚本口径：正文走 API、有上限判据、有白名单/闸门、推送走 git。"""
    issues = []
    for needle, why in (("resolve_body", "正文必须经 API 取（不走 env）"),
                        ("MAX_BODY_CHARS", "必须保留正文上限判据"),
                        ("author_only", "必须保留投稿人白名单/闸门"),
                        ("'push'", "必须保留 git push 入库")):
        if needle not in script_text:
            issues.append(f"脚本缺口径：{why}")
    return issues


class LibraryIngestWorkflowContractTest(unittest.TestCase):
    def setUp(self):
        self.text = WORKFLOW.read_text(encoding="utf-8")
        self.doc = load_workflow()

    def test_workflow_matches_contract(self):
        self.assertEqual([], workflow_issues(self.doc, self.text), "library-ingest.yml 不满足契约")

    def test_issue_body_is_not_passed_via_env(self):
        """E2BIG 事故留痕：正文必须经 API 取，不许整段塞进步骤 env。"""
        self.assertNotIn("github.event.issue.body", self.text)

    def test_credentials_persistence_is_explicit(self):
        """入库要靠 checkout 注入的凭据 push——与其它 workflow 相反，必须写明。"""
        self.assertNotIn("persist-credentials: false", self.text)
        self.assertIn("凭据", self.text)

    def test_script_keeps_api_body_quota_and_allowlist(self):
        self.assertEqual([], script_issues(SCRIPT.read_text(encoding="utf-8")),
                         "入库脚本口径缺失")

    def test_contract_catches_broken_workflow(self):
        """变异自证（六类坏件都必须报）。

        覆盖：去 issues 权限 / 触发面放宽 / 正文走 env / 凭据 false / 无保留期 / 缺标题守卫。
        """
        import copy

        no_issues = copy.deepcopy(self.doc)
        del no_issues["jobs"]["ingest"]["permissions"]["issues"]
        self.assertTrue(any("issues: write" in i for i in workflow_issues(no_issues, self.text)),
                        "去掉 issues: write 必须报")
        wide = copy.deepcopy(self.doc)
        _on(wide)["issues"] = {"types": ["opened", "edited"]}
        self.assertTrue(any("opened" in i for i in workflow_issues(wide, self.text)),
                        "触发面放宽必须报")
        body_env = self.text + "\n# ISSUE_BODY: ${{ github.event.issue.body }}\n"
        self.assertTrue(any("E2BIG" in i for i in workflow_issues(self.doc, body_env)),
                        "正文走 env 必须报")
        creds = self.text + "\n# persist-credentials: false\n"
        self.assertTrue(any("persist-credentials: false" in i
                            for i in workflow_issues(self.doc, creds)),
                        "凭据 false 必须报")
        no_days = copy.deepcopy(self.doc)
        for step in no_days["jobs"]["ingest"]["steps"]:
            if "upload-artifact" in str(step.get("uses") or ""):
                (step.get("with") or {}).pop("retention-days", None)
        self.assertTrue(any("retention" in i for i in workflow_issues(no_days, self.text)),
                        "无保留期必须报")
        no_gate = copy.deepcopy(self.doc)
        no_gate["jobs"]["ingest"]["if"] = "true"
        self.assertTrue(any("守卫" in i for i in workflow_issues(no_gate, self.text)),
                        "缺标题守卫必须报")
        self.assertTrue(script_issues("no body via api"), "脚本缺口径必须报")
        with self.assertRaises(ValueError):
            load_workflow(ROOT / ".github" / "no_such_ingest.yml")


if __name__ == "__main__":
    unittest.main()
