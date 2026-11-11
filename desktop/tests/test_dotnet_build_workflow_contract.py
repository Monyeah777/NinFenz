#!/usr/bin/env python3
"""dotnet-build 契约判据：树外构建、SDK 守卫、失败即红、证据可下载（2026-11-11）。

为什么必须有：这是 engine/dotnet 目前唯一的常驻 CI 面。三处退化都不会被现有判据拦住：
① 树外构建被改成树内（bin/obj 进仓库 → text-hygiene 判据假红，铁律见 RUNBOOK）；
② SDK 主版本守卫被去掉（runner 升级后换 SDK 静默变绿）；③ $LASTEXITCODE 检查被删（构建失败吞掉）。
本件把铁律、守卫、fail-closed、证据钉成契约。

范围：只判 .github/workflows/dotnet-build.yml 与其输入 csproj。
同族判据：test_rust_crate_workflow_contract（同构建家族）、test_cross_lang_workflow_contract。
"""
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "dotnet-build.yml"
CSPROJS = ("engine/dotnet/src/Nf.Engine/Nf.Engine.csproj",
           "engine/dotnet/tools/nf-dotnet/nf-dotnet.csproj",
           "engine/dotnet/tools/nfparity/nfparity.csproj")
OSES = ("ubuntu-latest", "windows-latest")
MAX_RETENTION = 7


def load_workflow(path: Path = WORKFLOW) -> dict:
    """读 workflow YAML（缺失 / 非法 / 非映射 → ValueError）。"""
    try:
        doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ValueError(f"dotnet-build.yml 不可读/不可解析：{exc}") from exc
    if not isinstance(doc, dict):
        raise ValueError("dotnet-build.yml 根节点必须是映射")
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
    """C# 构建契约问题列表（纯函数，便于变异自证）。"""
    issues = []
    if doc.get("permissions") != {"contents": "read"}:
        issues.append(f"顶层权限必须最小化（contents: read），实际 {doc.get('permissions')!r}")
    conc = doc.get("concurrency") or {}
    if conc.get("cancel-in-progress") is not True:
        issues.append("concurrency.cancel-in-progress 必须为 true")
    triggers = _on(doc)
    if (triggers.get("push") or {}).get("branches") != ["main"]:
        issues.append("push 触发必须限定 branches: [main]")
    if "pull_request" not in triggers:
        issues.append("缺 pull_request 触发（构建腐烂要在评审时暴露）")
    if "workflow_dispatch" not in triggers:
        issues.append("缺 workflow_dispatch（人工重跑入口）")
    job = (doc.get("jobs") or {}).get("dotnet-build")
    if not job:
        return issues + ["缺作业：dotnet-build"]
    if "matrix.os" not in str(job.get("name") or ""):
        issues.append("作业名必须含 matrix.os（两平台可区分）")
    timeout = job.get("timeout-minutes")
    if not isinstance(timeout, int) or not 1 <= timeout <= 20:
        issues.append(f"timeout-minutes 必须 1..20：{timeout!r}")
    strategy = job.get("strategy") or {}
    if strategy.get("fail-fast") is not False:
        issues.append("必须 fail-fast: false（一平台红不掩盖另一平台）")
    oses = [str(x) for x in ((strategy.get("matrix") or {}).get("os") or [])]
    if oses != list(OSES):
        issues.append(f"矩阵必须是两平台 {list(OSES)}，实际 {oses!r}")
    checkout = [s for s in _steps(job) if "actions/checkout" in str(s.get("uses") or "")]
    if not checkout:
        issues.append("缺 checkout")
    elif (checkout[0].get("with") or {}).get("persist-credentials") is not False:
        issues.append("checkout 必须 persist-credentials: false（只读作业）")
    runs = _runs(job)
    for cmd in ("dotnet --list-sdks", "dotnet --version"):
        if cmd not in runs:
            issues.append(f"SDK 自述缺命令：{cmd}")
    if "8\\." not in runs:
        issues.append("SDK 主版本守卫必须锚定 .NET 8（pinned 口径）")
    if "缺 .NET 8 SDK" not in runs:
        issues.append("SDK 守卫必须显式报错（防 runner 升级后静默换 SDK）")
    if "RUNNER_TEMP" not in runs:
        issues.append("树外构建铁律：必须用 RUNNER_TEMP（树内 bin/obj 会让 hygiene 判据假红）")
    if "Copy-Item" not in runs or "engine/dotnet" not in runs:
        issues.append("树外构建铁律：必须复制 engine/dotnet 到临时目录再 build")
    for csproj in CSPROJS:
        if csproj.split("/")[-1] not in runs:
            issues.append(f"构建清单缺 csproj：{csproj}")
    if runs.count("$LASTEXITCODE") < 3:
        issues.append("三处 build 都必须检查 $LASTEXITCODE（fail-closed）")
    if "$ErrorActionPreference" not in runs:
        issues.append("缺 $ErrorActionPreference = 'Stop'（PowerShell 失败即停）")
    for marker in ("git commit", "git push", "git add "):
        if marker in runs:
            issues.append(f"只读作业不得出现写仓库动作：{marker}")
    uploads = [s for s in _steps(job) if "upload-artifact" in str(s.get("uses") or "")]
    if not uploads:
        issues.append("缺构建日志工件")
    for step in uploads:
        if str(step.get("if") or "").strip() != "always()":
            issues.append("构建日志工件必须 if: always()")
        with_args = step.get("with") or {}
        if "matrix.os" not in str(with_args.get("name") or ""):
            issues.append("工件名必须含 matrix.os（两平台不互相覆盖）")
        if "dotnet-build.log" not in str(with_args.get("path") or ""):
            issues.append("工件未包含 dotnet-build.log")
        days = with_args.get("retention-days")
        if not isinstance(days, int) or not 1 <= days <= MAX_RETENTION:
            issues.append(f"工件 retention-days 必须 1..{MAX_RETENTION}：{days!r}")
    return issues


class DotnetBuildWorkflowContractTest(unittest.TestCase):
    def setUp(self):
        self.doc = load_workflow()

    def test_workflow_matches_contract(self):
        self.assertEqual([], workflow_issues(self.doc), "dotnet-build.yml 不满足契约")

    def test_out_of_tree_build(self):
        """铁律：只许在 RUNNER_TEMP 里 build，树内不留 bin/obj。"""
        runs = _runs(self.doc["jobs"]["dotnet-build"])
        self.assertIn("RUNNER_TEMP", runs)
        self.assertIn("Copy-Item", runs)

    def test_csprojs_exist(self):
        for rel in CSPROJS:
            self.assertTrue((ROOT / rel).is_file(), f"缺 csproj：{rel}")

    def test_contract_catches_broken_workflow(self):
        """变异自证（五类坏件都必须报）。

        覆盖：树内构建 / 去 SDK 守卫 / 去 LASTEXITCODE / 去 Windows 矩阵 / 无保留期。
        """
        import copy

        in_tree = copy.deepcopy(self.doc)
        for step in in_tree["jobs"]["dotnet-build"]["steps"]:
            run = str(step.get("run") or "")
            if "RUNNER_TEMP" in run:
                step["run"] = run.replace("$env:RUNNER_TEMP 'nf-engine'", "'engine/dotnet'")
        self.assertTrue(any("树外" in i for i in workflow_issues(in_tree)),
                        "树内构建必须报")
        no_sdk = copy.deepcopy(self.doc)
        for step in no_sdk["jobs"]["dotnet-build"]["steps"]:
            run = str(step.get("run") or "")
            if "缺 .NET 8 SDK" in run:
                step["run"] = "$env:X = 1"
        self.assertTrue(any("SDK" in i for i in workflow_issues(no_sdk)),
                        "去 SDK 守卫必须报")
        no_exit = copy.deepcopy(self.doc)
        for step in no_exit["jobs"]["dotnet-build"]["steps"]:
            run = str(step.get("run") or "")
            if "$LASTEXITCODE" in run:
                step["run"] = run.replace("$LASTEXITCODE", "$null")
        self.assertTrue(any("LASTEXITCODE" in i for i in workflow_issues(no_exit)),
                        "去 LASTEXITCODE 必须报")
        one_os = copy.deepcopy(self.doc)
        one_os["jobs"]["dotnet-build"]["strategy"]["matrix"]["os"] = ["ubuntu-latest"]
        self.assertTrue(any("矩阵" in i for i in workflow_issues(one_os)),
                        "去掉 Windows 矩阵必须报")
        no_days = copy.deepcopy(self.doc)
        for step in no_days["jobs"]["dotnet-build"]["steps"]:
            if "upload-artifact" in str(step.get("uses") or ""):
                (step.get("with") or {}).pop("retention-days", None)
        self.assertTrue(any("retention" in i for i in workflow_issues(no_days)),
                        "无保留期必须报")
        with self.assertRaises(ValueError):
            load_workflow(ROOT / ".github" / "no_such_dotnet.yml")


if __name__ == "__main__":
    unittest.main()
