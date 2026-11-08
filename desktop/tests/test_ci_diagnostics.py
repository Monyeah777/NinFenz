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


if __name__ == "__main__":
    unittest.main()
