#!/usr/bin/env python3
"""npm-package-check 契约判据：PR 面须只读、全量触发、数字对账、失败留证（2026-11-11）。

为什么必须有：payload 体积/件数/README 数字的漂移只在发布时才炸，本 workflow 是唯一在 PR 面上
兜住它的门；但它此前零判据——被加上 paths 过滤（漏掉普通 PR 引发的漂移）、被塞进 npm publish /
令牌（破坏只读）、或「工作树必须干净」的断言被删掉，都不会红。

范围：只判 .github/workflows/npm-package-check.yml 与其脚本（packaging/npm 的 stage/verify/
verify-tarball/smoke、site/tools/sync-numbers.mjs）。同族判据：test_npm_publish_workflow_contract。
"""
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "npm-package-check.yml"
NPM = ROOT / "packaging" / "npm"
REQUIRED_SCRIPTS = (NPM / "test" / "smoke.test.mjs", NPM / "tools" / "verify-tarball.mjs",
                    NPM / "bin" / "nf.mjs", ROOT / "site" / "tools" / "sync-numbers.mjs")
MAX_RETENTION = 7


def load_workflow(path: Path = WORKFLOW) -> dict:
    """读 workflow YAML（缺失 / 非法 / 非映射 → ValueError）。"""
    try:
        doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ValueError(f"npm-package-check.yml 不可读/不可解析：{exc}") from exc
    if not isinstance(doc, dict):
        raise ValueError("npm-package-check.yml 根节点必须是映射")
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
    """打包契约 PR 面问题列表（纯函数，便于变异自证）。"""
    issues = []
    body = text if text else ""
    if doc.get("permissions") != {"contents": "read"}:
        issues.append(f"顶层权限必须最小化（contents: read），实际 {doc.get('permissions')!r}")
    for marker in ("npm publish", "NODE_AUTH_TOKEN", "secrets."):
        if marker in body:
            issues.append(f"本 workflow 必须只读、无发布无密钥：出现 {marker}")
    conc = doc.get("concurrency") or {}
    if conc.get("cancel-in-progress") is not True:
        issues.append("concurrency.cancel-in-progress 必须为 true")
    triggers = _on(doc)
    pr = triggers.get("pull_request")
    if "pull_request" not in triggers:
        issues.append("缺 pull_request 触发（PR 面是它的存在理由）")
    elif isinstance(pr, dict) and pr.get("paths"):
        issues.append("PR 触发不应按 paths 限制（payload 受任意受跟踪文件影响）")
    if (triggers.get("push") or {}).get("branches") != ["main"]:
        issues.append("push 触发必须限定 branches: [main]")
    if "workflow_dispatch" not in triggers:
        issues.append("缺 workflow_dispatch（人工重跑入口）")
    job = (doc.get("jobs") or {}).get("npm-package-check")
    if not job:
        return issues + ["缺作业：npm-package-check"]
    if str(job.get("name") or "").strip() != "npm-package-check":
        issues.append("作业名必须稳定（npm-package-check）")
    timeout = job.get("timeout-minutes")
    if not isinstance(timeout, int) or not 1 <= timeout <= 20:
        issues.append(f"timeout-minutes 必须 1..20：{timeout!r}")
    runs = _runs(job)
    for needle, why in (("npm run stage", "必须跑 stage"),
                        ("npm run verify", "必须跑 verify-package"),
                        ("node --test test/smoke.test.mjs", "必须跑包内冒烟"),
                        ("npm pack --dry-run", "必须打包干跑"),
                        ("tools/verify-tarball.mjs", "必须做 tarball 逐字节核对"),
                        ("site/tools/sync-numbers.mjs", "必须对账站点数字"),
                        ("git diff --quiet", "必须断言 stage 不改受跟踪文件"),
                        ("node bin/nf.mjs --version", "必须冒烟 CLI")):
        if needle not in runs:
            issues.append(f"打包契约缺步骤：{why}")
    if "tee npm-package-check.log" not in runs:
        issues.append("stage/verify 输出未落盘（体积不一致时无诊断物）")
    if "修复" not in runs:
        issues.append("失败提示必须带修复指引（本仓文案纪律）")
    checkout = [s for s in _steps(job) if "actions/checkout" in str(s.get("uses") or "")]
    if not checkout:
        issues.append("缺 checkout")
    elif (checkout[0].get("with") or {}).get("persist-credentials") is not False:
        issues.append("checkout 必须 persist-credentials: false（只读作业）")
    uploads = [s for s in _steps(job) if "upload-artifact" in str(s.get("uses") or "")]
    if not uploads:
        issues.append("缺失败诊断工件")
    else:
        step = uploads[0]
        if str(step.get("if") or "").strip() != "always()":
            issues.append("诊断工件必须 if: always()")
        if "npm-package-check.log" not in str((step.get("with") or {}).get("path") or ""):
            issues.append("诊断工件未包含 stage 日志")
        days = (step.get("with") or {}).get("retention-days")
        if not isinstance(days, int) or not 1 <= days <= MAX_RETENTION:
            issues.append(f"工件 retention-days 必须 1..{MAX_RETENTION}：{days!r}")
    return issues


class NpmPackageCheckWorkflowContractTest(unittest.TestCase):
    def setUp(self):
        self.text = WORKFLOW.read_text(encoding="utf-8")
        self.doc = load_workflow()

    def test_workflow_matches_contract(self):
        self.assertEqual([], workflow_issues(self.doc, self.text),
                         "npm-package-check.yml 不满足契约")

    def test_read_only_no_publish_no_secrets(self):
        for marker in ("npm publish", "NODE_AUTH_TOKEN", "secrets."):
            self.assertNotIn(marker, self.text)

    def test_pr_trigger_is_not_path_filtered(self):
        pr = _on(self.doc).get("pull_request")
        self.assertFalse(isinstance(pr, dict) and pr.get("paths"),
                         "PR 触发被 paths 限制（会漏普通 PR 引起的 payload 漂移）")

    def test_referenced_scripts_exist(self):
        for path in REQUIRED_SCRIPTS:
            self.assertTrue(path.is_file(), f"缺依赖脚本：{path.as_posix()}")

    def test_contract_catches_broken_workflow(self):
        """变异自证（五类坏件都必须报）。

        覆盖：加 publish / 加令牌 / 加 paths / 删干净树断言 / 无保留期。
        """
        import copy

        publisher = self.text + "\n# run: npm publish --access public\n"
        self.assertTrue(any("npm publish" in i for i in workflow_issues(self.doc, publisher)),
                        "加 publish 必须报")
        token = self.text + "\n# env: NODE_AUTH_TOKEN: x\n"
        self.assertTrue(any("NODE_AUTH_TOKEN" in i for i in workflow_issues(self.doc, token)),
                        "加令牌必须报")
        filtered = copy.deepcopy(self.doc)
        _on(filtered)["pull_request"] = {"paths": ["packaging/npm/**"]}
        self.assertTrue(any("paths" in i for i in workflow_issues(filtered, self.text)),
                        "加 PR paths 必须报")
        no_guard = copy.deepcopy(self.doc)
        no_guard["jobs"]["npm-package-check"]["steps"] = [
            s for s in no_guard["jobs"]["npm-package-check"]["steps"]
            if "git diff --quiet" not in str(s.get("run") or "")]
        self.assertTrue(any("受跟踪" in i for i in workflow_issues(no_guard, self.text)),
                        "删干净树断言必须报")
        no_days = copy.deepcopy(self.doc)
        for step in no_days["jobs"]["npm-package-check"]["steps"]:
            if "upload-artifact" in str(step.get("uses") or ""):
                (step.get("with") or {}).pop("retention-days", None)
        self.assertTrue(any("retention" in i for i in workflow_issues(no_days, self.text)),
                        "无保留期必须报")
        with self.assertRaises(ValueError):
            load_workflow(ROOT / ".github" / "no_such_npm_check.yml")


if __name__ == "__main__":
    unittest.main()
