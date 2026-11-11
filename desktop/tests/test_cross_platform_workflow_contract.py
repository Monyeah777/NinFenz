#!/usr/bin/env python3
"""cross-platform 契约判据：同口径全量、先判后写、矩阵不掩盖、工件有限留存（2026-11-11）。

为什么必须有：本 workflow 是「三平台 CI 全绿」这句话的唯一实证面，但口径极易回潮：
①把 --full 改回裸 verify.sh（silent quick：三平台绿但全量一条没跑）；②把 --check/--write 顺序写反
（--write 先改盘 → --check 永远通过，漂移检测失效，2026-11-11 实测修掉）；③矩阵 fail-fast 打开
（一门红掩盖另两门）；④工件无限留存。本件把这四条钉成契约。

范围：只判 .github/workflows/cross-platform.yml。同族判据：test_ci_visibility（档位机检）、
test_ci_verify_contract、test_ci_diagnostics（ArtifactPolicyTest）。
"""
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "cross-platform.yml"
OSES = ("ubuntu-latest", "macos-latest", "windows-latest")
MAX_RETENTION = 7
COLD_START = (".gitee/ISSUE_TEMPLATE", "engine/dotnet/dist", "engine/rust/canonical/target")
MATRIX_OS_EXPR = "${{ matrix.os }}"


def load_workflow(path: Path = WORKFLOW) -> dict:
    """读 workflow YAML（缺失 / 非法 / 非映射 → ValueError）。"""
    try:
        doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ValueError(f"cross-platform.yml 不可读/不可解析：{exc}") from exc
    if not isinstance(doc, dict):
        raise ValueError("cross-platform.yml 根节点必须是映射")
    return doc


def _on(doc: dict) -> dict:
    value = doc.get("on")
    if value is None:
        value = doc.get(True)
    return value if isinstance(value, dict) else {}


def _steps(job: dict) -> list:
    return [s for s in (job.get("steps") or []) if isinstance(s, dict)]


def job_text(job: dict) -> str:
    return "\n".join(str(s.get("run") or "") for s in _steps(job))


def workflow_issues(doc: dict) -> list:
    """三平台门禁契约问题列表（纯函数，便于变异自证）。"""
    issues = []
    if doc.get("permissions") != {"contents": "read"}:
        issues.append(f"顶层权限必须最小化（contents: read），实际 {doc.get('permissions')!r}")
    conc = doc.get("concurrency") or {}
    if conc.get("cancel-in-progress") is not True:
        issues.append("concurrency.cancel-in-progress 必须为 true")
    triggers = _on(doc)
    if (triggers.get("push") or {}).get("branches") != ["main"]:
        issues.append("push 触发必须限定 branches: [main]")
    if "pull_request" in triggers:
        issues.append("三平台全量太贵，不应在 pull_request 触发（main/dispatch 面）")
    if "workflow_dispatch" not in triggers:
        issues.append("缺 workflow_dispatch（人工三平台复跑入口）")
    job = (doc.get("jobs") or {}).get("gate")
    if not job:
        return issues + ["缺作业：gate"]
    name = str(job.get("name") or "")
    if "matrix.os" not in name and MATRIX_OS_EXPR not in name:
        issues.append("gate 作业名必须含 matrix.os（三平台可区分）")
    strategy = job.get("strategy") or {}
    if strategy.get("fail-fast") is not False:
        issues.append("必须 fail-fast: false（一个平台红不掩盖另两个）")
    oses = [str(x) for x in ((strategy.get("matrix") or {}).get("os") or [])]
    if oses != list(OSES):
        issues.append(f"矩阵必须是三平台 {list(OSES)}，实际 {oses!r}")
    timeout = job.get("timeout-minutes")
    if not isinstance(timeout, int) or not 1 <= timeout <= 60:
        issues.append(f"gate 的 timeout-minutes 必须 1..60：{timeout!r}")
    env = job.get("env") or {}
    if env.get("PYTHONUTF8") != "1" or "utf-8" not in str(env.get("PYTHONIOENCODING") or ""):
        issues.append("缺 Windows ANSI 兜底（PYTHONUTF8=1 / PYTHONIOENCODING=utf-8）")
    checkout = [s for s in _steps(job) if "actions/checkout" in str(s.get("uses") or "")]
    if not checkout:
        issues.append("缺 checkout")
    else:
        with_args = checkout[0].get("with") or {}
        if with_args.get("fetch-depth") != 0:
            issues.append("checkout 必须 fetch-depth: 0（全量门禁含 tag/全历史）")
        if with_args.get("fetch-tags") is not True:
            issues.append("checkout 必须 fetch-tags: true")
        if with_args.get("persist-credentials") is not False:
            issues.append("checkout 必须 persist-credentials: false")
    text = job_text(job)
    if "bash verify.sh --full" not in text:
        issues.append("必须显式 bash verify.sh --full（裸跑 = silent quick）")
    if "RUNNER_OS" not in text:
        issues.append("Linux 专属系统库安装必须以 RUNNER_OS 守卫")
    if "requirements-ci.txt" not in text or "--require-hashes" not in text:
        issues.append("依赖必须走固定清单 + --require-hashes")
    if "sast-windows.log" not in text:
        issues.append("缺 Windows 侧 SAST 基线步骤（nt 段需要 CI 面）")
    if "set -o pipefail" not in text:
        issues.append("缺显式 set -o pipefail（tee 步骤会吞退出码）")
    for path in COLD_START:
        if path not in text:
            issues.append(f"冷启动前置缺目录：{path}")
    if "NF_VERIFY_TMP" not in text:
        issues.append("缺 NF_VERIFY_TMP（失败日志要可下载）")
    check_at = text.find("verify_report.py --check")
    write_at = text.find("verify_report.py --write")
    if check_at < 0:
        issues.append("缺 verify_report --check（报告新鲜度闸门）")
    if write_at < 0:
        issues.append("缺 verify_report --write（工件落盘）")
    if 0 <= write_at < check_at:
        issues.append("必须先 --check 再 --write（反过来 --check 永远通过 = fail-open）")
    uploads = [s for s in _steps(job) if "upload-artifact" in str(s.get("uses") or "")]
    if len(uploads) < 2:
        issues.append("三平台应上传两份工件（验证日志 + 报告）")
    for step in uploads:
        if str(step.get("if") or "").strip() != "always()":
            issues.append("工件必须 if: always()（失败也要留证据）")
        days = (step.get("with") or {}).get("retention-days")
        if not isinstance(days, int) or not 1 <= days <= MAX_RETENTION:
            issues.append(f"工件 retention-days 必须 1..{MAX_RETENTION}：{days!r}")
    return issues


class CrossPlatformWorkflowContractTest(unittest.TestCase):
    def setUp(self):
        self.doc = load_workflow()

    def test_workflow_matches_contract(self):
        self.assertEqual([], workflow_issues(self.doc), "cross-platform.yml 不满足契约")

    def test_check_precedes_write(self):
        """fail-open 修复的钉死：先判已落盘报告，再落盘工件。"""
        text = job_text(self.doc["jobs"]["gate"])
        self.assertGreaterEqual(text.find("verify_report.py --check"), 0)
        self.assertLess(text.find("verify_report.py --check"),
                        text.find("verify_report.py --write"))

    def test_three_os_matrix(self):
        strategy = self.doc["jobs"]["gate"]["strategy"]
        self.assertEqual(list(OSES), [str(x) for x in strategy["matrix"]["os"]])
        self.assertIs(False, strategy.get("fail-fast"))

    def test_contract_catches_broken_workflow(self):
        """变异自证（五类坏件都必须报）。

        覆盖：裸跑 verify.sh / 反序 check-write / 开 fail-fast / 加 PR 触发 / 无保留期。
        """
        import copy

        bare = copy.deepcopy(self.doc)
        for step in bare["jobs"]["gate"]["steps"]:
            if "bash verify.sh --full" in str(step.get("run") or ""):
                step["run"] = str(step["run"]).replace("bash verify.sh --full", "bash verify.sh")
        self.assertTrue(any("--full" in i for i in workflow_issues(bare)), "裸跑必须报")
        reordered = copy.deepcopy(self.doc)
        for step in reordered["jobs"]["gate"]["steps"]:
            run = str(step.get("run") or "")
            if "verify_report.py --check" in run and "verify_report.py --write" in run:
                lines = run.splitlines()
                ci = next(i for i, ln in enumerate(lines)
                          if "verify_report.py --check" in ln)
                wi = next(i for i, ln in enumerate(lines)
                          if "verify_report.py --write" in ln)
                lines[ci], lines[wi] = lines[wi], lines[ci]
                step["run"] = "\n".join(lines)
        self.assertTrue(any("fail-open" in i for i in workflow_issues(reordered)),
                        "反序必须报")
        fast = copy.deepcopy(self.doc)
        fast["jobs"]["gate"]["strategy"]["fail-fast"] = True
        self.assertTrue(any("fail-fast" in i for i in workflow_issues(fast)),
                        "开 fail-fast 必须报")
        pr = copy.deepcopy(self.doc)
        _on(pr)["pull_request"] = {}
        self.assertTrue(any("pull_request" in i for i in workflow_issues(pr)),
                        "加 PR 触发必须报")
        no_days = copy.deepcopy(self.doc)
        for step in no_days["jobs"]["gate"]["steps"]:
            if "upload-artifact" in str(step.get("uses") or ""):
                (step.get("with") or {}).pop("retention-days", None)
        self.assertTrue(any("retention" in i for i in workflow_issues(no_days)),
                        "无保留期必须报")
        with self.assertRaises(ValueError):
            load_workflow(ROOT / ".github" / "no_such_cross_platform.yml")


if __name__ == "__main__":
    unittest.main()
