#!/usr/bin/env python3
"""docker-nfal 契约判据：不推注册表、基座 digest 固定、作业工件自证、冒烟必跑（2026-11-11）。

为什么必须有：镜像是「上游 tag 漂移 / 构建缓存假绿 / 工件记错作业」最易侵蚀的面。本 workflow 此前
零判据，且实测有两处真问题：①build 作业没有诊断工件、②nfal 的工件步骤被错放进 hf-space 作业
（失败时下载到的是另一份作业的证据）。本件把「不推注册表 / digest 固定 / 每作业自证 / 冒烟」
钉成契约。

范围：只判 .github/workflows/docker-nfal.yml 与其输入 Dockerfile。
同族判据：test_ci_diagnostics（DockerfileDigestPinTest）、test_ci_supply_chain。
"""
import re
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "docker-nfal.yml"
DOCKERFILES = (ROOT / "packaging" / "nfal" / "Dockerfile",
               ROOT / "packaging" / "hf-space" / "Dockerfile")
MAX_RETENTION = 7
#: 只 build 不推送：出现这些即说明引入了注册表/凭据面
PUSH_MARKERS = ("docker push", "docker login", "secrets.", "REGISTRY")
FROM_RE = re.compile(r"^\s*FROM\s+(\S+)", re.I | re.M)


def load_workflow(path: Path = WORKFLOW) -> dict:
    """读 workflow YAML（缺失 / 非法 / 非映射 → ValueError）。"""
    try:
        doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ValueError(f"docker-nfal.yml 不可读/不可解析：{exc}") from exc
    if not isinstance(doc, dict):
        raise ValueError("docker-nfal.yml 根节点必须是映射")
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


def digest_issues(files: dict) -> list:
    """所有 FROM 基座必须按 digest 钉（scratch 除外）。纯函数，便于变异自证。"""
    issues = []
    for name, text in files.items():
        for i, line in enumerate(text.splitlines(), 1):
            m = FROM_RE.match(line)
            if not m:
                continue
            image = m.group(1)
            if image == "scratch" or "@sha256:" in image:
                continue
            issues.append(f"{name}:{i} 基座未按 digest 钉：{image}")
    return issues


def workflow_issues(doc: dict, text: str = "") -> list:
    """容器构建契约问题列表（纯函数，便于变异自证）。"""
    issues = []
    body = text if text else ""
    if doc.get("permissions") != {"contents": "read"}:
        issues.append(f"顶层权限必须最小化（contents: read），实际 {doc.get('permissions')!r}")
    for marker in PUSH_MARKERS:
        if marker in body:
            issues.append(f"本 workflow 只 build 不推送：出现 {marker}")
    conc = doc.get("concurrency") or {}
    if conc.get("cancel-in-progress") is not True:
        issues.append("concurrency.cancel-in-progress 必须为 true")
    triggers = _on(doc)
    push = triggers.get("push") or {}
    if push.get("branches") != ["main"]:
        issues.append("push 触发必须限定 branches: [main]")
    push_paths = [str(p) for p in (push.get("paths") or [])]
    pr = triggers.get("pull_request") or {}
    pr_paths = [str(p) for p in (pr.get("paths") or [])]
    if "pull_request" not in triggers:
        issues.append("缺 pull_request 触发（镜像构建坏掉要在评审时暴露）")
    elif push_paths != pr_paths:
        issues.append("push 与 PR 的 paths 必须同一份（锚点复用，避免漂移）")
    if "workflow_dispatch" not in triggers:
        issues.append("缺 workflow_dispatch（人工重跑入口）")
    jobs = doc.get("jobs") or {}
    want = {"build": ("build-nfal-image", 15, "packaging/nfal/Dockerfile", ".",
                      "docker-nfal-diagnostics"),
            "build-hf-space": ("build-hf-space-image", 20, "packaging/hf-space/Dockerfile",
                               "packaging/hf-space", "docker-hf-space-diagnostics")}
    for job_id, (name, max_timeout, dockerfile, context, artifact_name) in want.items():
        job = jobs.get(job_id)
        if not job:
            issues.append(f"缺作业：{job_id}")
            continue
        if str(job.get("name") or "").strip() != name:
            issues.append(f"{job_id} 作业名必须稳定（{name}）")
        timeout = job.get("timeout-minutes")
        if not isinstance(timeout, int) or not 1 <= timeout <= max_timeout:
            issues.append(f"{job_id} 的 timeout-minutes 必须 1..{max_timeout}：{timeout!r}")
        runs = _runs(job)
        if f"-f {dockerfile}" not in runs:
            issues.append(f"{job_id} 未用指定 Dockerfile：{dockerfile}")
        if "docker build" not in runs:
            issues.append(f"{job_id} 缺 docker build")
        if context == "." and "docker build" in runs and " ." not in runs:
            issues.append(f"{job_id} 构建上下文必须是仓库根（.）")
        if "docker run --rm" not in runs:
            issues.append(f"{job_id} 缺容器冒烟")
        uploads = [s for s in _steps(job) if "upload-artifact" in str(s.get("uses") or "")]
        if len(uploads) != 1:
            issues.append(f"{job_id} 必须恰有 1 个诊断工件（实际 {len(uploads)}）")
        for step in uploads:
            if str(step.get("with", {}).get("name")) != artifact_name:
                issues.append(f"{job_id} 工件名必须是 {artifact_name}")
            if str(step.get("if") or "").strip() != "always()":
                issues.append(f"{job_id} 工件必须 if: always()")
            days = (step.get("with") or {}).get("retention-days")
            if not isinstance(days, int) or not 1 <= days <= MAX_RETENTION:
                issues.append(f"{job_id} 工件 retention-days 必须 1..{MAX_RETENTION}：{days!r}")
    return issues


class DockerNfalWorkflowContractTest(unittest.TestCase):
    def setUp(self):
        self.text = WORKFLOW.read_text(encoding="utf-8")
        self.doc = load_workflow()

    def test_workflow_matches_contract(self):
        self.assertEqual([], workflow_issues(self.doc, self.text), "docker-nfal.yml 不满足契约")

    def test_build_only_no_registry(self):
        for marker in PUSH_MARKERS:
            self.assertNotIn(marker, self.text)

    def test_dockerfile_bases_are_digest_pinned(self):
        files = {}
        for path in DOCKERFILES:
            self.assertTrue(path.is_file(), f"缺 Dockerfile：{path.as_posix()}")
            files[path.name + "@" + path.parent.name] = path.read_text(encoding="utf-8")
        self.assertEqual([], digest_issues(files), "Dockerfile 基座未按 digest 钉")

    def test_each_job_owns_its_artifact(self):
        jobs = self.doc["jobs"]
        self.assertEqual(["docker-nfal-diagnostics"],
                         [s["with"]["name"] for s in _steps(jobs["build"])
                          if "upload-artifact" in str(s.get("uses") or "")])
        self.assertEqual(["docker-hf-space-diagnostics"],
                         [s["with"]["name"] for s in _steps(jobs["build-hf-space"])
                          if "upload-artifact" in str(s.get("uses") or "")])

    def test_contract_catches_broken_workflow(self):
        """变异自证（五类坏件都必须报）。

        覆盖：加 docker push / 工件放错作业 / 无保留期 / 去 PR 触发 / 基座未钉 digest。
        """
        import copy

        pusher = self.text + "\n# run: docker push nfal:ci\n"
        self.assertTrue(any("docker push" in i for i in workflow_issues(self.doc, pusher)),
                        "加 push 必须报")
        wrong_owner = copy.deepcopy(self.doc)
        wrong_owner["jobs"]["build"]["steps"] = [
            s for s in wrong_owner["jobs"]["build"]["steps"]
            if "upload-artifact" not in str(s.get("uses") or "")]
        self.assertTrue(any("诊断工件" in i for i in workflow_issues(wrong_owner, self.text)),
                        "工件放错作业必须报")
        no_days = copy.deepcopy(self.doc)
        for job in no_days["jobs"].values():
            for step in job["steps"]:
                if "upload-artifact" in str(step.get("uses") or ""):
                    (step.get("with") or {}).pop("retention-days", None)
        self.assertTrue(any("retention" in i for i in workflow_issues(no_days, self.text)),
                        "无保留期必须报")
        no_pr = copy.deepcopy(self.doc)
        _on(no_pr).pop("pull_request", None)
        self.assertTrue(any("pull_request" in i for i in workflow_issues(no_pr, self.text)),
                        "去 PR 触发必须报")
        self.assertTrue(digest_issues({"fake": "FROM python:3.12-slim\n"}),
                        "基座未钉 digest 必须报")
        with self.assertRaises(ValueError):
            load_workflow(ROOT / ".github" / "no_such_docker.yml")


if __name__ == "__main__":
    unittest.main()
