#!/usr/bin/env python3
"""npm-publish 契约判据：两条发布通道须最小权限、版本对齐、幂等、证据留存（2026-11-11）。

为什么必须有：npm-publish 是 CLI 线唯一发布面，且发布不可撤销；但它此前零判据——去掉 id-token
（OIDC/provenance 静默降级）、把 cancel-in-progress 改回 true、删 tag-版本一致性检查、去掉
幂等跳过（重跑即 409）或删证据工件，都不会红。本件把「两条发布通道」钉成 fail-closed 契约。

范围：只判 .github/workflows/npm-publish.yml 与其真源（packaging/npm 的 stage/verify/tarball
脚本、package.json 的 publishConfig）。同族判据：test_release_gate_workflow_contract。
"""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "npm-publish.yml"
PKG = ROOT / "packaging" / "npm" / "package.json"
STAGE = ROOT / "packaging" / "npm" / "tools" / "stage-payload.mjs"
TARBALL = ROOT / "packaging" / "npm" / "tools" / "verify-tarball.mjs"
SMOKE = ROOT / "packaging" / "npm" / "test" / "smoke.test.mjs"
MAX_RETENTION = 30


def load_workflow(path: Path = WORKFLOW) -> dict:
    """读 workflow YAML（缺失 / 非法 / 非映射 → ValueError）。"""
    try:
        import yaml
    except ModuleNotFoundError as exc:
        raise ValueError(f"缺 PyYAML：{exc}") from exc
    try:
        doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ValueError(f"npm-publish.yml 不可读/不可解析：{exc}") from exc
    if not isinstance(doc, dict):
        raise ValueError("npm-publish.yml 根节点必须是映射")
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


def workflow_issues(doc: dict) -> list:
    """npm-publish 契约问题列表（纯函数，便于变异自证）。"""
    issues = []
    if doc.get("permissions") != {"contents": "read"}:
        issues.append(f"顶层权限必须最小化（contents: read），实际 {doc.get('permissions')!r}")
    conc = doc.get("concurrency") or {}
    if conc.get("cancel-in-progress") is not False:
        issues.append("发布必须 cancel-in-progress: false（发布不许被取消）")
    if "npm-publish-" not in str(conc.get("group") or ""):
        issues.append("concurrency group 必须按 npm-publish 隔离")
    triggers = _on(doc)
    if (triggers.get("push") or {}).get("tags") != ["v*"]:
        issues.append("push 触发必须是 tags: [v*]")
    if "workflow_dispatch" not in triggers:
        issues.append("缺 workflow_dispatch（手动补发/重跑入口）")
    jobs = doc.get("jobs") or {}
    publish = jobs.get("publish")
    gh = jobs.get("publish-github-packages")
    if not publish or not gh:
        return issues + ["缺发布作业：publish / publish-github-packages"]
    perm = publish.get("permissions") or {}
    if perm.get("contents") != "read" or perm.get("id-token") != "write":
        issues.append("publish 权限必须恰为 contents: read + id-token: write（OIDC/provenance）")
    gh_perm = gh.get("permissions") or {}
    if gh_perm.get("contents") != "read" or gh_perm.get("packages") != "write":
        issues.append("GitHub Packages 作业权限必须恰为 contents: read + packages: write")
    for job_id, job in (("publish", publish), ("publish-github-packages", gh)):
        if str(job.get("name") or "") not in ("npm-publish-provenance",
                                             "npm-publish-github-packages"):
            issues.append(f"{job_id} 作业名不稳定（会削弱 check 可读性）")
        gate = str(job.get("if") or "")
        if "workflow_dispatch" not in gate or "startsWith(github.ref_name, 'v1.')" not in gate:
            issues.append(f"{job_id} 的触发守卫必须含 workflow_dispatch 与 v1. 前缀判断")
        timeout = job.get("timeout-minutes")
        if not isinstance(timeout, int) or not 1 <= timeout <= 30:
            issues.append(f"{job_id} 的 timeout-minutes 必须 1..30：{timeout!r}")
    pub_runs = _runs(publish)
    for needle in ("package.json').version", "v$V", "npm install -g npm@",
                   "npm run stage", "npm run verify", "smoke.test.mjs",
                   "npm pack --dry-run", "verify-tarball.mjs",
                   "--provenance", "--access public", "npm view", "rm -f .npmrc"):
        if needle not in pub_runs:
            issues.append(f"publish 缺发布纪律步骤：{needle}")
    gh_runs = _runs(gh)
    for needle in ("@monyeah777/ninfenz", "publishConfig.provenance", "npm.pkg.github.com",
                   "--ignore-scripts", "npm view", "rm -f .npmrc", "v$V"):
        if needle not in gh_runs:
            issues.append(f"publish-github-packages 缺步骤：{needle}")
    for job_id, job in (("publish", publish), ("publish-github-packages", gh)):
        uploads = [s for s in _steps(job) if "upload-artifact" in str(s.get("uses") or "")]
        if not uploads:
            issues.append(f"{job_id} 缺失败诊断工件（发布失败必须有可下载证据）")
            continue
        step = uploads[0]
        if str(step.get("if") or "").strip() != "always()":
            issues.append(f"{job_id} 的证据工件必须 if: always()")
        with_args = step.get("with") or {}
        days = with_args.get("retention-days")
        if not isinstance(days, int) or not 1 <= days <= MAX_RETENTION:
            issues.append(f"{job_id} 证据 retention-days 必须 1..{MAX_RETENTION}：{days!r}")
    return issues


class NpmPublishWorkflowContractTest(unittest.TestCase):
    def setUp(self):
        self.doc = load_workflow()

    def test_workflow_matches_contract(self):
        self.assertEqual([], workflow_issues(self.doc), "npm-publish.yml 不满足契约")

    def test_permissions_are_minimal_per_job(self):
        """OIDC 只在 npmjs 发布 job；GitHub Packages 只在它自己的 job 提权。"""
        jobs = self.doc["jobs"]
        self.assertEqual({"contents": "read", "id-token": "write"},
                         jobs["publish"].get("permissions"))
        self.assertEqual({"contents": "read", "packages": "write"},
                         jobs["publish-github-packages"].get("permissions"))

    def test_sources_exist(self):
        pkg = json.loads(PKG.read_text(encoding="utf-8"))
        self.assertTrue((pkg.get("publishConfig") or {}).get("provenance"),
                        "package.json 缺 publishConfig.provenance=true")
        for path in (STAGE, TARBALL, SMOKE):
            self.assertTrue(path.is_file(), f"发布流程依赖的脚本不在场：{path.name}")

    def test_contract_catches_broken_workflow(self):
        """变异自证（六类坏件都必须报）。

        覆盖：去 id-token / 允许取消 / 去 tag-版本检查 / 去 provenance / 去幂等 / 无保留期。
        """
        import copy

        no_oidc = copy.deepcopy(self.doc)
        del no_oidc["jobs"]["publish"]["permissions"]["id-token"]
        self.assertTrue(any("id-token" in i for i in workflow_issues(no_oidc)),
                        "去掉 id-token 必须报")
        cancellable = copy.deepcopy(self.doc)
        cancellable["concurrency"]["cancel-in-progress"] = True
        self.assertTrue(any("取消" in i for i in workflow_issues(cancellable)),
                        "允许取消必须报")
        no_guard = copy.deepcopy(self.doc)
        no_guard["jobs"]["publish"]["if"] = "true"
        self.assertTrue(any("守卫" in i for i in workflow_issues(no_guard)),
                        "去掉触发守卫必须报")
        no_prov = copy.deepcopy(self.doc)
        for step in no_prov["jobs"]["publish"]["steps"]:
            if "--provenance" in str(step.get("run") or ""):
                step["run"] = str(step["run"]).replace("--provenance", "")
        self.assertTrue(any("provenance" in i for i in workflow_issues(no_prov)),
                        "去掉 provenance 必须报")
        no_idem = copy.deepcopy(self.doc)
        for step in no_idem["jobs"]["publish"]["steps"]:
            if "npm view" in str(step.get("run") or ""):
                step["run"] = str(step["run"]).replace("npm view", "true")
        self.assertTrue(any("npm view" in i for i in workflow_issues(no_idem)),
                        "去掉幂等检查必须报")
        no_retention = copy.deepcopy(self.doc)
        for step in no_retention["jobs"]["publish"]["steps"]:
            if "upload-artifact" in str(step.get("uses") or ""):
                (step.get("with") or {}).pop("retention-days", None)
        self.assertTrue(any("retention" in i for i in workflow_issues(no_retention)),
                        "证据无保留期必须报")
        with self.assertRaises(ValueError):
            load_workflow(ROOT / ".github" / "no_such_npm_publish.yml")


if __name__ == "__main__":
    unittest.main()
