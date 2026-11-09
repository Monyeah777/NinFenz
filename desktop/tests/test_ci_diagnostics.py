#!/usr/bin/env python3
"""CI 失败诊断物（审计 Z5 / §11j N8 + N1 实锤）。

两条硬判据：
1. **artifact 不得是 git 跟踪的产物**：N1 实锤——ci-verify/cross-platform 用 if: always() 上传
   受跟踪的 protocol/verification_report.json，红跑也会送出一份写着 fail=0 的「自证绿」产物。
2. **关键门禁必须有失败时也可下载的产物**：日志目录 + 实时重算报告。
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WF = ROOT / ".github" / "workflows"

#: 受跟踪路径前缀/文件（这些**不许**当 artifact 上传——它们是仓库内容，不是本 run 的产物）。
TRACKED_PREFIXES = ("protocol/", "desktop/", "scripts/", "engine/", "packaging/", "community/",
                    "library/", "results/", "site/", "docs/", "tui/", ".github/")
TRACKED_FILES = ("llms.txt", "README.md", "README.en.md", "verify.sh", "CHANGELOG.md")

#: 关键门禁工作流：至少要有一步 upload-artifact（失败诊断物覆盖）。
KEY_WORKFLOWS = ("ci-verify.yml", "cross-platform.yml", "release-gate.yml", "coverage.yml",
                 "e2e-desktop.yml", "sast.yml", "lint.yml",
                 "dependency-audit.yml", "docker-nfal.yml")


def _upload_blocks(text: str) -> list:
    """切出每个 upload-artifact 步骤的文本块（缩进感知，避免把下一个步骤吞进来）。"""
    lines = text.split("\n")
    blocks = []
    i = 0
    while i < len(lines):
        if "uses: actions/upload-artifact" in lines[i]:
            indent = len(lines[i]) - len(lines[i].lstrip())
            j = i + 1
            while j < len(lines):
                ln = lines[j]
                if ln.strip() and (len(ln) - len(ln.lstrip())) <= indent and ln.lstrip().startswith("- "):
                    break
                j += 1
            blocks.append("\n".join(lines[max(0, i - 6):j]))
            i = j
        else:
            i += 1
    return blocks


def _paths_in_block(block: str) -> list:
    """取该步骤的 path: 值（含 path: | 块形式）。"""
    lines = block.split("\n")
    out = []
    for k, ln in enumerate(lines):
        m = re.match(r"(\s*)path:\s*(.*)$", ln)
        if not m:
            continue
        val = m.group(2).strip()
        if val and val != "|":
            out.append(val.strip("'\""))
            continue
        base = len(m.group(1))
        for nxt in lines[k + 1:]:
            if not nxt.strip():
                continue
            if (len(nxt) - len(nxt.lstrip())) <= base:
                break
            out.append(nxt.strip().strip("'\""))
    return out


def tracked_artifact_paths(text: str) -> list:
    """→ 该 workflow 里**上传了受跟踪产物**的路径（纯函数，可变异自证）。"""
    bad = []
    for b in _upload_blocks(text):
        for p in _paths_in_block(b):
            base = p.lstrip("./")
            if base.startswith(TRACKED_PREFIXES) or base in TRACKED_FILES:
                bad.append(p)
    return bad


class ArtifactPolicyTest(unittest.TestCase):
    def test_no_workflow_uploads_tracked_files(self):
        bad = {}
        for p in sorted(WF.glob("*.yml")):
            hits = tracked_artifact_paths(p.read_text(encoding="utf-8"))
            if hits:
                bad[p.name] = hits
        self.assertEqual({}, bad, "artifact 上传了 git 跟踪产物（Z5/N1）：%s" % bad)

    def test_mutation_is_caught(self):
        sample = (
            "      - name: 上传门禁报告\n"
            "        if: always()\n"
            "        uses: actions/upload-artifact@abc\n"
            "        with:\n"
            "          name: r\n"
            "          path: protocol/verification_report.json\n")
        self.assertEqual(["protocol/verification_report.json"],
                         tracked_artifact_paths(sample))

    def test_block_path_form_is_parsed(self):
        sample = (
            "      - uses: actions/upload-artifact@abc\n"
            "        with:\n"
            "          name: r\n"
            "          path: |\n"
            "            verify.log\n"
            "            .nf-logs/\n")
        self.assertEqual([], tracked_artifact_paths(sample), "块形式不该误报")

    def test_key_workflows_have_an_artifact_step(self):
        missing = [name for name in KEY_WORKFLOWS
                   if "upload-artifact" not in (WF / name).read_text(encoding="utf-8")]
        self.assertEqual([], missing, "关键门禁缺失败诊断物：%s" % missing)

    def test_gate_workflows_keep_machine_readable_evidence(self):
        for name in ("ci-verify.yml", "cross-platform.yml"):
            text = (WF / name).read_text(encoding="utf-8")
            self.assertIn("NF_VERIFY_TMP", text, "%s 未固定日志目录（Z5 0.2）" % name)
            self.assertIn(".artifacts/verification-report.json", text,
                          "%s 未上传本 run 实时重算的报告（Z5/N1）" % name)


class CiHealthAuditSourceTest(unittest.TestCase):
    """ci-health 的 main 审计两个已修 bug 的源码级回归守卫（2026-11-08 实测踩到）。

    为什么用源码断言而不是跑 workflow：这两个 bug 都是「修好了但改别处时容易回归」的结构点——
    ① 自指：审计把上一次失败的自已当最新失败 → 永远红（#218→#220 实测）；
    ② 窗口：main 一天 100+ 条运行，只取 100 条会让某些 workflow 滑出窗口而假绿（#222 修）。
    """

    def setUp(self):
        self.text = (WF / "ci-health.yml").read_text(encoding="utf-8")

    def test_audit_excludes_itself(self):
        self.assertIn('own = ".github/workflows/ci-health.yml"', self.text,
                      "ci-health 审计未排除自身（自指会让它在一次失败后永远红）")
        self.assertIn("if r.get(\"path\") == own:", self.text,
                      "ci-health 审计缺少「跳过自身运行」的分支")

    def test_audit_window_is_paginated(self):
        self.assertIn("for page in (1, 2, 3)", self.text,
                      "ci-health 审计窗口未分页（繁忙日 >100 条会假绿）")
        self.assertIn("runs.extend(page_runs)", self.text,
                      "ci-health 审计分页结果未并入 runs")

    def test_audit_skips_in_flight_runs(self):
        """最新一次还在跑 → 计 pending 跳过（否则「上次红、新一次在跑」会瞬时假红）。"""
        self.assertIn('pending = [r for r in latest.values() if r.get("status") != "completed"]',
                      self.text, "ci-health 审计未把 in-flight 运行记为 pending")
        self.assertIn("if pending:", self.text, "ci-health 审计缺少 pending 提示分支")
        # schedule 步也要 pending 跳过（2026-11-09 #243；此前只修了 main 步）
        self.assertIn("schedule 面：%d 个 workflow 的最新运行仍在进行", self.text,
                      "ci-health schedule 步未跳过 in-flight 运行")


class TeePipefailTest(unittest.TestCase):
    """`... | tee ...` 的退出码不得被吞（2026-11-09 实测 #251：sast job 绿但日志满屏 ✗）。

    为什么用源码断言：GitHub 默认 shell 是 `bash -e`（**无** pipefail），步骤里
    `python scripts/sast_check.py 2>&1 | tee sast.log` 的退出码来自 tee ⇒ 门禁假绿。
    修法是给该步骤 `shell: bash`（GitHub 的 bash 默认 `-eo pipefail`）或显式 `set -o pipefail`。
    """

    def test_all_tee_steps_have_pipefail(self):
        import re
        bad = []
        for p in sorted(WF.glob("*.yml")):
            text = p.read_text(encoding="utf-8")
            for block in re.split(r"(?m)^ {6}- ", text):
                if "| tee" not in block:
                    continue
                if "shell: bash" not in block and "set -o pipefail" not in block:
                    bad.append(p.name)
                    break
        self.assertEqual(
            [], bad,
            f"含 | tee 的步骤未启用 pipefail（退出码会被 tee 吞）：{bad}")


class GateAlwaysRunsTest(unittest.TestCase):
    """gate 不得因依赖失败而被「跳过」（2026-11-09 实测 #251）。

    GitHub 对 required check 的 skipped 视为通过：gate 若 `needs: [static-checks, unit-tests]`
    且没有 `if: always()`，unit-tests 有分片红时 gate 被跳过 ⇒ auto-merge 照样合并。
    """

    def test_gate_is_always_run_and_checks_dependencies(self):
        import re
        text = (WF / "ci-verify.yml").read_text(encoding="utf-8")
        m = re.search(r"(?ms)^  gate:\n(.*?)(?=^  [a-z0-9-]+:\n|\Z)", text)
        self.assertIsNotNone(m, "ci-verify.yml 找不到 gate job")
        block = m.group(1)
        self.assertIn("if: always()", block, "gate 未声明 if: always()（会被跳过）")
        self.assertIn("needs.static-checks.result", block, "gate 未校验 static-checks 结果")
        self.assertIn("needs.unit-tests.result", block, "gate 未校验 unit-tests 结果")


class ParityKeyCompareTest(unittest.TestCase):
    """linux-parity-refresh 的 posix SAST 漂移判定必须逐键比对（2026-11-09）。

    只比总数会漏「一规则 +1、另一规则 -1」的键级漂移（总数相等 → 漂移告警绿着放行）。
    """

    def test_parity_compares_keys_not_only_totals(self):
        text = (WF / "linux-parity-refresh.yml").read_text(encoding="utf-8")
        self.assertIn("键级漂移", text, "parity 漂移判定未做键级比对")
        self.assertIn("set(c) - set(b)", text, "parity 漂移判定缺少 extra 键集合")
        self.assertNotIn("got != want", text, "parity 仍在用总数比较（会漏键级漂移）")


class HiddenArtifactPathTest(unittest.TestCase):
    """artifact 的 path 不得指向隐藏**文件**（2026-11-09 #247/#248 实测）。

    actions/upload-artifact v4+ 默认 `include-hidden-files=false`：path 里以 `.` 开头
    的**文件**会被静默丢弃（sast-counts.json / sast-extra-*.json 曾整年没进 artifact）。
    隐藏**目录**（如 `.nf-logs/`）不受影响，故只查 basename 以点开头的纯文件路径。
    """

    def test_no_artifact_path_is_a_hidden_file(self):
        import re
        bad = {}
        for p in sorted(WF.glob("*.yml")):
            text = p.read_text(encoding="utf-8")
            for block in re.split(r"(?m)^ {6}- ", text):
                if "upload-artifact" not in block:
                    continue
                if "include-hidden-files: true" in block:
                    continue
                pat = r"(?ms)^\s+path: \|\n(.*?)(?=^\s+[a-z-]+:|\Z)"
                m = re.search(pat, block)
                if not m:
                    continue
                for line in m.group(1).splitlines():
                    item = line.strip()
                    if not item or item.startswith("#"):
                        continue
                    name = item.rstrip("/").split("/")[-1]
                    if name.startswith(".") and not item.endswith("/"):
                        bad.setdefault(p.name, []).append(item)
        self.assertEqual(
            {}, bad,
            f"artifact path 指向隐藏文件（会被 upload-artifact 静默丢弃）：{bad}")


if __name__ == "__main__":
    unittest.main()
