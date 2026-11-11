#!/usr/bin/env python3
"""cross-lang 契约判据：跨语言对拍须「full 模式、只读、三实现齐、退化留证」（2026-11-11）。

为什么必须有：本 workflow 是跨语言承诺的唯一常驻证据面。三处退化都不会被现有判据拦住：
① --require-full 被去掉（UNKNOWN 不再计入 → 三实现缺一也绿）；② 被塞进写仓库的动作
（违反"铁律：只读"）；③ 误调 verify.sh（整仓基线门有且只有 ci-verify 一份，test_ci_visibility
钉这一点）。本件把 full/只读/分工/证据钉成契约。

范围：只判 .github/workflows/cross-lang.yml 与其脚本 scripts/cross_lang_verify.py 的存在性。
同族判据：test_ci_visibility、test_cross_platform_workflow_contract。
"""
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "cross-lang.yml"
SCRIPT = ROOT / "scripts" / "cross_lang_verify.py"
MANIFEST_POS = "protocol/generated/test_vectors/jcs_conformance.json"
MANIFEST_NEG = "protocol/generated/test_vectors/jcs_reject.json"
MAX_RETENTION = 7
#: 只读不变量：出现这些即说明它开始写仓库/夺走基线门职责
WRITE_MARKERS = ("git commit", "git push", "git add ", " --write", "nf.py ")
BASELINE_MARKERS = ("bash verify.sh", "verify.sh --")


def load_workflow(path: Path = WORKFLOW) -> dict:
    """读 workflow YAML（缺失 / 非法 / 非映射 → ValueError）。"""
    try:
        doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ValueError(f"cross-lang.yml 不可读/不可解析：{exc}") from exc
    if not isinstance(doc, dict):
        raise ValueError("cross-lang.yml 根节点必须是映射")
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


def _effective(text: str) -> str:
    """去掉整行注释（注释里写「刻意不调 verify.sh」不算违规）。"""
    return "\n".join(ln for ln in text.splitlines() if not ln.strip().startswith("#"))


def workflow_issues(doc: dict, text: str = "") -> list:
    """跨语言对拍契约问题列表（纯函数，便于变异自证）。"""
    issues = []
    body = _effective(text) if text else ""
    if doc.get("permissions") != {"contents": "read"}:
        issues.append(f"顶层权限必须最小化（contents: read），实际 {doc.get('permissions')!r}")
    conc = doc.get("concurrency") or {}
    if conc.get("cancel-in-progress") is not True:
        issues.append("concurrency.cancel-in-progress 必须为 true")
    triggers = _on(doc)
    if (triggers.get("push") or {}).get("branches") != ["main"]:
        issues.append("push 触发必须限定 branches: [main]")
    if "pull_request" not in triggers:
        issues.append("缺 pull_request 触发（跨语言退化要在评审时暴露）")
    if "workflow_dispatch" not in triggers:
        issues.append("缺 workflow_dispatch（人工重跑入口）")
    for marker in WRITE_MARKERS:
        if marker in body:
            issues.append(f"只读铁律：不得出现写仓库动作 {marker}")
    for marker in BASELINE_MARKERS:
        if marker in body:
            issues.append(f"分工铁律：整仓基线门只归 ci-verify，本件不得调用 {marker}")
    job = (doc.get("jobs") or {}).get("cross-lang-matrix")
    if not job:
        return issues + ["缺作业：cross-lang-matrix"]
    if str(job.get("name") or "").strip() != "cross-lang-full-matrix":
        issues.append("作业名必须稳定（cross-lang-full-matrix）")
    timeout = job.get("timeout-minutes")
    if not isinstance(timeout, int) or not 1 <= timeout <= 30:
        issues.append(f"timeout-minutes 必须 1..30：{timeout!r}")
    runs = _runs(job)
    for cmd in ("python3 --version", "rustc --version", "cargo --version", "dotnet --list-sdks"):
        if cmd not in runs:
            issues.append(f"工具链自述缺命令：{cmd}")
    if "缺 .NET 8 SDK" not in runs:
        issues.append(".NET 主版本守卫必须显式报错（防 runner 升级后静默换 SDK）")
    for cmd in ("cargo build --release", "engine/rust/canonical/Cargo.toml",
                "dotnet build", "nf-canonical.csproj"):
        if cmd not in runs:
            issues.append(f"缺两实现构建要素：{cmd}")
    pos = runs.find(MANIFEST_POS)
    neg = runs.find(MANIFEST_NEG)
    if pos < 0:
        issues.append("缺正例矩阵清单")
    if neg < 0:
        issues.append("缺负例矩阵清单")
    if runs.count("--require-full") < 2:
        issues.append("正例与负例都必须 --require-full（UNKNOWN 必须为 0）")
    if "--digest" not in runs:
        issues.append("正例必须带 --digest（逐字节对账，不只比形状）")
    if "--coverage" not in runs:
        issues.append("缺覆盖棘轮（spec_clause 覆盖只增不减）")
    uploads = [s for s in _steps(job) if "upload-artifact" in str(s.get("uses") or "")]
    if not uploads:
        issues.append("缺退化证据工件")
    for step in uploads:
        with_args = step.get("with") or {}
        if str(with_args.get("name")) != "cross-lang-report":
            issues.append("工件名必须是 cross-lang-report")
        days = with_args.get("retention-days")
        if not isinstance(days, int) or not 1 <= days <= MAX_RETENTION:
            issues.append(f"工件 retention-days 必须 1..{MAX_RETENTION}：{days!r}")
    return issues


class CrossLangWorkflowContractTest(unittest.TestCase):
    def setUp(self):
        self.text = WORKFLOW.read_text(encoding="utf-8")
        self.doc = load_workflow()

    def test_workflow_matches_contract(self):
        self.assertEqual([], workflow_issues(self.doc, self.text), "cross-lang.yml 不满足契约")

    def test_read_only_and_single_baseline_gate(self):
        """只读 + 分工：不写仓库、不调用 verify.sh（基线门只在 ci-verify）。"""
        effective = _effective(self.text)
        for marker in WRITE_MARKERS:
            self.assertNotIn(marker, effective)
        self.assertNotIn("bash verify.sh", effective)

    def test_full_mode_and_byte_level_digest(self):
        runs = _runs(self.doc["jobs"]["cross-lang-matrix"])
        self.assertGreaterEqual(runs.count("--require-full"), 2)
        self.assertIn("--digest", runs)

    def test_contract_catches_broken_workflow(self):
        """变异自证（五类坏件都必须报）。

        覆盖：去 --require-full / 加 --write / 调 verify.sh / 去 --digest / 无保留期。
        """
        import copy

        weak = copy.deepcopy(self.doc)
        for step in weak["jobs"]["cross-lang-matrix"]["steps"]:
            run = str(step.get("run") or "")
            if "--require-full" in run:
                step["run"] = run.replace("--require-full", "")
        self.assertTrue(any("require-full" in i for i in workflow_issues(weak, self.text)),
                        "去 require-full 必须报")
        writer = copy.deepcopy(self.doc)
        for step in writer["jobs"]["cross-lang-matrix"]["steps"]:
            if "cross_lang_verify.py" in str(step.get("run") or ""):
                step["run"] = str(step["run"]) + "\n  git push origin main"
                break
        self.assertTrue(any("只读" in i
                            for i in workflow_issues(writer, yaml.safe_dump(writer))),
                        "加写动作必须报")
        baseline = copy.deepcopy(self.doc)
        for step in baseline["jobs"]["cross-lang-matrix"]["steps"]:
            if "cross_lang_verify.py" in str(step.get("run") or ""):
                step["run"] = str(step["run"]) + "\n  bash verify.sh --full"
                break
        self.assertTrue(any("分工" in i
                            for i in workflow_issues(baseline, yaml.safe_dump(baseline))),
                        "调 verify.sh 必须报")
        no_digest = copy.deepcopy(self.doc)
        for step in no_digest["jobs"]["cross-lang-matrix"]["steps"]:
            run = str(step.get("run") or "")
            if "--digest" in run:
                step["run"] = run.replace("--digest", "")
        self.assertTrue(any("digest" in i for i in workflow_issues(no_digest, self.text)),
                        "去 digest 必须报")
        no_days = copy.deepcopy(self.doc)
        for step in no_days["jobs"]["cross-lang-matrix"]["steps"]:
            if "upload-artifact" in str(step.get("uses") or ""):
                (step.get("with") or {}).pop("retention-days", None)
        self.assertTrue(any("retention" in i for i in workflow_issues(no_days, self.text)),
                        "无保留期必须报")
        self.assertTrue(SCRIPT.is_file())
        with self.assertRaises(ValueError):
            load_workflow(ROOT / ".github" / "no_such_cross_lang.yml")


if __name__ == "__main__":
    unittest.main()
