#!/usr/bin/env python3
"""scorecard 契约判据：评分工作流须最小权限、发布语义固定、工件保留、摘要可追溯（2026-11-11）。

为什么必须有：OpenSSF Scorecard 是唯一对外发布的供应链评分面；它的 permissions 被放大、
publish_results 被关掉、upload-sarif 与 codeql 版本错位、摘要丢掉 run_id/sha256——都不会红，
但评分会静默失真（或发布不可追溯）。本件把评分工作流钉成契约，并与 codeql 固定版本交叉对账。

范围：只判 .github/workflows/scorecard.yml（交叉引用 codeql.yml 的 codeql-action SHA）。
同族判据：test_codeql_workflow_contract、test_ci_supply_chain。
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "scorecard.yml"
CODEQL = ROOT / ".github" / "workflows" / "codeql.yml"
PIN_RE = re.compile(r"^[^@/\s]+/[^@\s]+@[0-9a-f]{40}$")
CODEQL_SHA_RE = re.compile(r"github/codeql-action/(?:init|analyze|upload-sarif)@([0-9a-f]{40})")


def load_workflow(path: Path = WORKFLOW) -> dict:
    """读 workflow YAML（缺失 / 非法 / 非映射 → ValueError）。"""
    try:
        import yaml
    except ModuleNotFoundError as exc:
        raise ValueError(f"缺 PyYAML：{exc}") from exc
    try:
        doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ValueError(f"scorecard.yml 不可读/不可解析：{exc}") from exc
    if not isinstance(doc, dict):
        raise ValueError("scorecard.yml 根节点必须是映射")
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


def codeql_sha_of(path: Path) -> str:
    """从 workflow 文本抽 codeql-action 的 SHA（用于跨工作流一致性）。"""
    m = CODEQL_SHA_RE.search(path.read_text(encoding="utf-8"))
    return m.group(1) if m else ""


def workflow_issues(doc: dict, codeql_sha: str = "") -> list:
    """scorecard 契约问题列表（纯函数，便于变异自证）。"""
    issues = []
    if doc.get("permissions") not in ("read-all", {"contents": "read"}):
        issues.append(f"顶层权限必须是 read-all，实际 {doc.get('permissions')!r}")
    conc = doc.get("concurrency") or {}
    if conc.get("cancel-in-progress") is not False:
        issues.append("评分不得被取消（cancel-in-progress 必须 false）")
    triggers = _on(doc)
    for need in ("branch_protection_rule", "schedule", "push", "workflow_dispatch"):
        if need not in triggers:
            issues.append(f"缺触发面：{need}")
    if (triggers.get("push") or {}).get("branches") != ["main"]:
        issues.append("push 触发必须限定 branches: [main]")
    analysis = (doc.get("jobs") or {}).get("analysis")
    summary = (doc.get("jobs") or {}).get("summary")
    if not analysis or not summary:
        return issues + ["缺作业：analysis / summary"]
    perm = analysis.get("permissions") or {}
    if perm.get("security-events") != "write" or perm.get("id-token") != "write":
        issues.append("analysis 权限必须含 security-events: write + id-token: write")
    if perm.get("contents") != "read" or perm.get("actions") != "read":
        issues.append("analysis 权限必须含 contents: read + actions: read")
    summ_perm = summary.get("permissions") or {}
    if sorted(summ_perm.items()) != sorted({"actions": "read", "contents": "read"}.items()):
        issues.append("summary 权限必须恰为 actions: read + contents: read")
    timeout = analysis.get("timeout-minutes")
    if not isinstance(timeout, int) or not 1 <= timeout <= 30:
        issues.append(f"analysis 的 timeout-minutes 必须 1..30：{timeout!r}")
    needs = summary.get("needs") or []
    if isinstance(needs, str):
        needs = [needs]
    if sorted(needs) != ["analysis"]:
        issues.append("summary 必须 needs: analysis")
    uses = []
    publish = None
    results_format = None
    for step in _steps(analysis):
        ref = str(step.get("uses") or "")
        if ref:
            uses.append(ref)
        if "ossf/scorecard-action" in ref:
            with_args = step.get("with") or {}
            publish = with_args.get("publish_results")
            results_format = with_args.get("results_format")
            if "results.sarif" not in str(with_args.get("results_file") or ""):
                issues.append("scorecard 步骤 results_file 必须是 results.sarif")
    unpinned = [u for u in uses if not PIN_RE.match(u) and not u.startswith("./")]
    if unpinned:
        issues.append(f"action 未固定到 40 位 SHA：{unpinned}")
    if not any("ossf/scorecard-action" in u for u in uses):
        issues.append("缺 ossf/scorecard-action 步骤")
    if publish is not True:
        issues.append("publish_results 必须为 true（OIDC 发布）")
    if str(results_format or "").lower() != "sarif":
        issues.append("results_format 必须是 sarif")
    if codeql_sha:
        upload = [u for u in uses if "github/codeql-action/upload-sarif@" in u]
        if not upload:
            issues.append("缺 upload-sarif（Security 页不可见）")
        elif upload[0].split("@")[1] != codeql_sha:
            issues.append("upload-sarif 与 codeql.yml 的 codeql-action SHA 不一致（版本错位）")
    sarif_upload = {}
    for step in _steps(analysis):
        if "upload-artifact" in str(step.get("uses") or ""):
            with_args = step.get("with") or {}
            if "sarif" in str(with_args.get("name") or ""):
                sarif_upload = with_args
    days = sarif_upload.get("retention-days")
    if not isinstance(days, int) or not 1 <= days <= 7:
        issues.append(f"SARIF 工件 retention-days 必须 1..7：{days!r}")
    summary_uploads = [s.get("with") or {} for s in _steps(summary)
                       if "upload-artifact" in str(s.get("uses") or "")]
    if not summary_uploads:
        issues.append("summary 缺可追溯摘要工件")
    else:
        with_args = summary_uploads[0]
        days = with_args.get("retention-days")
        if not isinstance(days, int) or not 1 <= days <= 30:
            issues.append(f"摘要 retention-days 必须 1..30：{days!r}")
    summ_runs = _runs(summary)
    for needle in ("NF_SCORECARD_RUN_ID", "NF_SCORECARD_COMMIT", "sha256",
                   "empty_results_are_not_clean"):
        if needle not in summ_runs:
            issues.append(f"摘要缺可追溯字段：{needle}")
    return issues


class ScorecardWorkflowContractTest(unittest.TestCase):
    def setUp(self):
        self.doc = load_workflow()
        self.codeql_sha = codeql_sha_of(CODEQL)

    def test_workflow_matches_contract(self):
        self.assertEqual([], workflow_issues(self.doc, self.codeql_sha),
                         "scorecard.yml 不满足契约")

    def test_publish_semantics(self):
        """publish_results + id-token 必须成对：关掉一个会让评分静默消失。"""
        self.assertEqual("write", (self.doc["jobs"]["analysis"]["permissions"] or {})
                         .get("id-token"))
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("publish_results: true", text)

    def test_codeql_action_version_matches_codeql_workflow(self):
        """upload-sarif 与 codeql.yml 必须同 SHA（否则格式/版本错位）。"""
        self.assertTrue(self.codeql_sha, "codeql.yml 里找不到 codeql-action SHA")
        upload = [s.get("uses") for s in _steps(self.doc["jobs"]["analysis"])
                  if "upload-sarif" in str(s.get("uses") or "")]
        self.assertTrue(upload, "缺 upload-sarif")
        self.assertEqual(self.codeql_sha, str(upload[0]).split("@")[1])

    def test_contract_catches_broken_workflow(self):
        """变异自证（六类坏件都必须报）。

        覆盖：去 id-token / 允许取消 / 关 publish_results / 版本错位 / 摘要无 sha256 / 无保留期。
        """
        import copy

        no_oidc = copy.deepcopy(self.doc)
        del no_oidc["jobs"]["analysis"]["permissions"]["id-token"]
        self.assertTrue(any("id-token" in i for i in workflow_issues(no_oidc, self.codeql_sha)),
                        "去 id-token 必须报")
        cancellable = copy.deepcopy(self.doc)
        cancellable["concurrency"]["cancel-in-progress"] = True
        self.assertTrue(any("取消" in i for i in workflow_issues(cancellable, self.codeql_sha)),
                        "允许取消必须报")
        no_publish = copy.deepcopy(self.doc)
        for step in no_publish["jobs"]["analysis"]["steps"]:
            if "ossf/scorecard-action" in str(step.get("uses") or ""):
                (step.get("with") or {})["publish_results"] = False
        self.assertTrue(any("publish_results" in i
                            for i in workflow_issues(no_publish, self.codeql_sha)),
                        "关 publish_results 必须报")
        mismatched = copy.deepcopy(self.doc)
        for step in mismatched["jobs"]["analysis"]["steps"]:
            if "upload-sarif" in str(step.get("uses") or ""):
                step["uses"] = "github/codeql-action/upload-sarif@" + "b" * 40
        self.assertTrue(any("不一致" in i for i in workflow_issues(mismatched, self.codeql_sha)),
                        "版本错位必须报")
        no_hash = copy.deepcopy(self.doc)
        for step in no_hash["jobs"]["summary"]["steps"]:
            if "sha256" in str(step.get("run") or ""):
                step["run"] = str(step["run"]).replace("sha256", "md5")
        self.assertTrue(any("sha256" in i for i in workflow_issues(no_hash, self.codeql_sha)),
                        "摘要缺 sha256 必须报")
        no_days = copy.deepcopy(self.doc)
        for step in no_days["jobs"]["analysis"]["steps"]:
            if "upload-artifact" in str(step.get("uses") or ""):
                (step.get("with") or {}).pop("retention-days", None)
        self.assertTrue(any("retention" in i for i in workflow_issues(no_days, self.codeql_sha)),
                        "无保留期必须报")
        with self.assertRaises(ValueError):
            load_workflow(ROOT / ".github" / "no_such_scorecard.yml")


if __name__ == "__main__":
    unittest.main()
