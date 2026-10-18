#!/usr/bin/env python3
"""门禁可见性回归测试 —— 「门禁本身有没有门禁」里**看得见**的那一半。

背景（实证）：2026-09-26～27 云端 `ci-verify` 连红 21 次（#155–#175，此前最后一次成功 #154），
仓库侧没有任何一处把这件事摆到人读面，也没有判据要求「push 触发的那条 workflow 跑的必须是
**全量** `verify.sh`」——`verify.sh` 与 core/scripts 的 check 都不读 `.github/`，该面此前只有
`test_ci_supply_chain` 管了 action 固定。于是「本机绿、云端红」可以静默持续三周。

本测试把两条钉住：
① 两份入口都带 ci-verify 徽章，且徽章指向的 workflow **真实在场**（改名即红，防徽章静默 404）；
② ci-verify.yml 跑的是全量 `bash verify.sh` 且 push→main 即触发（不是某个 check 子集、不是只手动）。
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = ROOT / ".github" / "workflows"
ENTRIES = ("README.md", "README.en.md")

#: GitHub 徽章 URL：https://github.com/<owner>/<repo>/actions/workflows/<wf>.yml/badge.svg
_BADGE = re.compile(
    r"https://github\.com/[^/\s)]+/[^/\s)]+/actions/workflows/([A-Za-z0-9_.\-]+\.ya?ml)/badge\.svg")
_RUN = re.compile(r"(?m)^\s*-?\s*run:\s*(.+?)\s*$")


def _read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


class GateVisibilityTest(unittest.TestCase):
    def test_entries_carry_ci_badge_pointing_at_real_workflow(self):
        """两份入口都须带徽章，且徽章指向的 workflow 件真实在场（改名即红）。"""
        for rel in ENTRIES:
            hits = _BADGE.findall(_read(ROOT / rel))
            self.assertTrue(hits, "%s 缺 CI 徽章 —— 云端连红将再次无人察觉" % rel)
            for wf in hits:
                self.assertTrue((WORKFLOWS / wf).is_file(),
                                "%s 的徽章指向不存在的 workflow：%s（徽章会静默 404）" % (rel, wf))

    def test_badge_covers_the_workflow_that_runs_the_gate(self):
        """徽章盯的必须是跑全量 `verify.sh` 的那条 workflow（不是 lint/coverage 之类旁支）。"""
        names = {wf for rel in ENTRIES for wf in _BADGE.findall(_read(ROOT / rel))}
        self.assertTrue(names, "两份入口都没有 CI 徽章")
        for wf in names:
            # P3+矩阵（2026-10-18）：全量门禁 = 静态作业 + 测试矩阵，两者缺一即不是全量。
            text = _read(WORKFLOWS / wf)
            self.assertRegex(text,
                             r"(?m)^\s*bash verify\.sh --checks-only( --no-cache)?"
                             r"(\s+2>&1\s*\|\s*tee\s+\S+)?\s*$",
                             "%s 缺「静态 42 条 check」作业（--checks-only）" % wf)
            self.assertRegex(text,
                             r"(?m)^\s*bash verify\.sh --tests-only --shard [\"']?"
                             r"\$\{\{ matrix\.shard \}\}/\d+[\"']?"
                             r"(\s+2>&1\s*\|\s*tee\s+\S+)?\s*$",
                             "%s 缺「测试矩阵分片」作业（--tests-only --shard）" % wf)

    def test_gate_workflow_runs_full_verify_not_a_subset(self):
        """唯一入口纪律（P3 分层后）：CI 必须跑 **full 档**（quick 是开发档，不是发布结论）。

        为什么改（2026-10-18）：verify.sh 默认档已改为 quick（静态 + 受影响测试），
        "裸跑"不再等于全量——裸跑反而是子集。CI 因此必须显式 `--full`（`--no-cache` 可选，
        用于强制真跑）；仍只允许一次调用（防"跑两遍拼出一个绿"）。
        """
        text = _read(WORKFLOWS / "ci-verify.yml")
        invocations = [ln.strip() for ln in text.splitlines()
                       if re.match(r"^\s*bash verify\.sh\b", ln)]
        self.assertEqual(2, len(invocations),
                         "ci-verify 必须恰好两次 verify.sh（静态 1 次 + 测试矩阵 1 次）：%s"
                         % invocations)
        checks = [ln for ln in invocations if "--checks-only" in ln]
        tests = [ln for ln in invocations if "--tests-only" in ln]
        self.assertEqual(1, len(checks), "静态作业必须只调一次：%s" % invocations)
        self.assertEqual(1, len(tests), "测试矩阵必须只调一次：%s" % invocations)
        self.assertRegex(checks[0], r"^bash verify\.sh --checks-only( --no-cache)?"
                                    r"(\s+2>&1\s*\|\s*tee\s+\S+)?$",
                         "静态作业必须只跑 check（不含测试）：%s" % checks[0])
        self.assertRegex(tests[0],
                         r"^bash verify\.sh --tests-only --shard [\"']?"
                         r"\$\{\{ matrix\.shard \}\}/(\d+)[\"']?"
                         r"(\s+2>&1\s*\|\s*tee\s+\S+)?$",
                         "测试作业必须按矩阵分片跑：%s" % tests[0])
        shards = int(re.search(r"--shard [\"']?\$\{\{ matrix\.shard \}\}/(\d+)",
                               tests[0]).group(1))
        self.assertGreaterEqual(shards, 16,
                                "分片数 %d 太少——单机全量瓶颈会原样搬进 CI" % shards)
        # 矩阵必须真的声明了对应数量的 shard（否则分片表达式取不到值，作业全跑 0/0）。
        block = text.split("matrix:", 1)[1]
        declared = [int(x) for x in re.findall(r"\b(\d{1,2})\b", block.split("steps:")[0])]
        self.assertIn(shards - 1, declared,
                      "workflow 的 matrix.shard 未声明到 %d" % (shards - 1))

    def test_gate_workflow_triggers_on_push_to_main(self):
        """推 main 即跑：徽章盯的是推送后的真实结论，不是手动才跑的空壳。"""
        text = _read(WORKFLOWS / "ci-verify.yml")
        self.assertRegex(text, r"(?m)^on:\s*$")
        self.assertRegex(text, r"(?m)^\s{2}push:\s*$")
        self.assertRegex(text, r"(?m)^\s{4}branches:\s*\[main\]\s*$")

