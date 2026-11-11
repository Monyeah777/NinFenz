#!/usr/bin/env python3
"""rust-crate 契约判据：锁文件锁定、两平台矩阵、Linux 专属面显式、失败留证（2026-11-11）。

为什么必须有：旧 rust-parity 退役后，主 crate 的整批单测（含与 Python 真源逐字节对账的 oracle）
只靠这一条 workflow 跑。三处退化都不会被现有判据拦住：① --locked 被去掉（依赖静默漂移，
而 oracle 恰好依赖锁定的版本）；② Windows 矩阵被删（cfg(windows) 面只剩作者机器验证）；
③ 失败日志工件被删/无保留期。本件把锁定、矩阵、分工、证据钉成契约。

范围：只判 .github/workflows/rust-crate.yml 与其输入（engine/rust 的 Cargo.toml/Cargo.lock）。
同族判据：test_cross_lang_workflow_contract（cross-lang 只 build canonical）、
test_cross_platform_workflow_contract。
"""
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "rust-crate.yml"
MAIN_MANIFEST = ROOT / "engine" / "rust" / "Cargo.toml"
MAIN_LOCK = ROOT / "engine" / "rust" / "Cargo.lock"
PYO3_MANIFEST = ROOT / "engine" / "rust" / "pyo3" / "Cargo.toml"
PYO3_LOCK = ROOT / "engine" / "rust" / "pyo3" / "Cargo.lock"
OSES = ("ubuntu-latest", "windows-latest")
MAX_RETENTION = 7


def load_workflow(path: Path = WORKFLOW) -> dict:
    """读 workflow YAML（缺失 / 非法 / 非映射 → ValueError）。"""
    try:
        doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ValueError(f"rust-crate.yml 不可读/不可解析：{exc}") from exc
    if not isinstance(doc, dict):
        raise ValueError("rust-crate.yml 根节点必须是映射")
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
    """主 crate 测试契约问题列表（纯函数，便于变异自证）。"""
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
        issues.append("缺 pull_request 触发（Rust oracle 退化要在评审时暴露）")
    if "workflow_dispatch" not in triggers:
        issues.append("缺 workflow_dispatch（人工重跑入口）")
    job = (doc.get("jobs") or {}).get("rust-crate-tests")
    if not job:
        return issues + ["缺作业：rust-crate-tests"]
    name = str(job.get("name") or "")
    if "matrix.os" not in name:
        issues.append("作业名必须含 matrix.os（两平台可区分）")
    timeout = job.get("timeout-minutes")
    if not isinstance(timeout, int) or not 1 <= timeout <= 30:
        issues.append(f"timeout-minutes 必须 1..30：{timeout!r}")
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
    for cmd in ("rustc --version", "cargo --version"):
        if cmd not in runs:
            issues.append(f"工具链自述缺命令：{cmd}")
    if "cargo test --release --locked --manifest-path engine/rust/Cargo.toml" not in runs:
        issues.append("主 crate 单测必须 cargo test --release --locked（锁文件 + 对拍优化档）")
    if runs.count("--locked") < 3:
        issues.append("三处 cargo 调用（test / bin / pyo3）都必须 --locked")
    if "set -o pipefail" not in runs:
        issues.append("缺显式 set -o pipefail（tee 会吞退出码）")
    if "tee rust-crate-test.log" not in runs:
        issues.append("单测输出未落盘")
    linux_steps = [s for s in _steps(job) if "runner.os == 'Linux'" in str(s.get("if") or "")]
    if not linux_steps:
        issues.append("Linux 专属步骤必须显式 if: runner.os == 'Linux'（不可复现面不进 CI）")
    linux_runs = "\n".join(str(s.get("run") or "") for s in linux_steps)
    if "cargo build --release --locked" not in linux_runs:
        issues.append("Linux 专属面必须构建 nf-rs bin（parity 判据需要二进制在场）")
    for mod in ("test_rust_engine", "test_rust_fastlane", "test_rust_pyext"):
        if mod not in runs:
            issues.append(f"Linux 专属面缺 parity 判据：{mod}")
    if "engine/rust/pyo3/Cargo.toml" not in linux_runs:
        issues.append("PyO3 扩展构建必须显式构建 engine/rust/pyo3（cdylib 不被主 crate 覆盖）")
    for path in (MAIN_MANIFEST, MAIN_LOCK, PYO3_MANIFEST, PYO3_LOCK):
        if not path.is_file():
            issues.append(f"缺受跟踪输入：{path.relative_to(ROOT).as_posix()}")
    for marker in ("git commit", "git push", "git add "):
        if marker in runs:
            issues.append(f"只读作业不得出现写仓库动作：{marker}")
    uploads = [s for s in _steps(job) if "upload-artifact" in str(s.get("uses") or "")]
    if not uploads:
        issues.append("缺失败诊断工件")
    for step in uploads:
        if str(step.get("if") or "").strip() != "always()":
            issues.append("诊断工件必须 if: always()")
        with_args = step.get("with") or {}
        if "matrix.os" not in str(with_args.get("name") or ""):
            issues.append("工件名必须含 matrix.os（两平台不互相覆盖）")
        path_text = str(with_args.get("path") or "")
        for log in ("rust-crate-test.log", "pyo3-build.log"):
            if log not in path_text:
                issues.append(f"工件缺日志：{log}")
        days = with_args.get("retention-days")
        if not isinstance(days, int) or not 1 <= days <= MAX_RETENTION:
            issues.append(f"工件 retention-days 必须 1..{MAX_RETENTION}：{days!r}")
    return issues


class RustCrateWorkflowContractTest(unittest.TestCase):
    def setUp(self):
        self.doc = load_workflow()

    def test_workflow_matches_contract(self):
        self.assertEqual([], workflow_issues(self.doc), "rust-crate.yml 不满足契约")

    def test_locked_and_two_platforms(self):
        runs = _runs(self.doc["jobs"]["rust-crate-tests"])
        self.assertGreaterEqual(runs.count("--locked"), 3)
        oses = self.doc["jobs"]["rust-crate-tests"]["strategy"]["matrix"]["os"]
        self.assertEqual(list(OSES), [str(x) for x in oses])

    def test_inputs_are_present_and_locked(self):
        for path in (MAIN_MANIFEST, MAIN_LOCK, PYO3_MANIFEST, PYO3_LOCK):
            self.assertTrue(path.is_file(), f"缺输入：{path.name}")

    def test_contract_catches_broken_workflow(self):
        """变异自证（五类坏件都必须报）。

        覆盖：去 --locked / 去 Windows 矩阵 / 去 pipefail / 去 Linux 门控 / 无保留期。
        """
        import copy

        unlocked = copy.deepcopy(self.doc)
        for step in unlocked["jobs"]["rust-crate-tests"]["steps"]:
            run = str(step.get("run") or "")
            if "--locked" in run:
                step["run"] = run.replace("--locked", "")
        self.assertTrue(any("locked" in i for i in workflow_issues(unlocked)),
                        "去 --locked 必须报")
        one_os = copy.deepcopy(self.doc)
        one_os["jobs"]["rust-crate-tests"]["strategy"]["matrix"]["os"] = ["ubuntu-latest"]
        self.assertTrue(any("矩阵" in i for i in workflow_issues(one_os)),
                        "去掉 Windows 矩阵必须报")
        no_pipe = copy.deepcopy(self.doc)
        for step in no_pipe["jobs"]["rust-crate-tests"]["steps"]:
            run = str(step.get("run") or "")
            if "set -o pipefail" in run:
                step["run"] = run.replace("set -o pipefail", "true")
        self.assertTrue(any("pipefail" in i for i in workflow_issues(no_pipe)),
                        "去 pipefail 必须报")
        ungated = copy.deepcopy(self.doc)
        for step in ungated["jobs"]["rust-crate-tests"]["steps"]:
            if "runner.os == 'Linux'" in str(step.get("if") or ""):
                step.pop("if", None)
        self.assertTrue(any("Linux" in i for i in workflow_issues(ungated)),
                        "去 Linux 门控必须报")
        no_days = copy.deepcopy(self.doc)
        for step in no_days["jobs"]["rust-crate-tests"]["steps"]:
            if "upload-artifact" in str(step.get("uses") or ""):
                (step.get("with") or {}).pop("retention-days", None)
        self.assertTrue(any("retention" in i for i in workflow_issues(no_days)),
                        "无保留期必须报")
        with self.assertRaises(ValueError):
            load_workflow(ROOT / ".github" / "no_such_rust.yml")


if __name__ == "__main__":
    unittest.main()
