#!/usr/bin/env python3
"""protocol/demo_signers/README.md 契约：允许清单 / 锚状态 / 两条命令结论必须与实跑一致。

为什么必须有：本页是「签名锚全链可复现」的入口，但它此前写「让任何读者都能端到端复现验证」——
本轮实测发现**口径过强**：NF-1 当前**未挂签名锚**，两条命令都是 exit 0 + 「真实性未验」，
并不构成「端到端签名验证通过」。这份文档若继续这样写，读者会把「机制可跑」当成「已签名」。
本轮补「§现状对照」「§复现与引用口径」并把落差写明，同时加判据：允许清单格式、锚状态短语、
两条命令实跑结论、以及**禁止出现「端到端签名验证通过」这类过强断言**。

范围：只判本页与 allowed_signers / nf_verify 实跑事实自洽（不改密钥）。
同族判据：test_attest*.py / test_library*.py /
test_fail_closed_pattern_doc_contract.py（同族口径）。
契约：复核位、允许清单 1 条且格式合法、现状对照 5 行、「未挂签名锚」「真实性未验」在文、
复现三命令、禁止过强断言、nf_verify 实跑 exit 0 且输出含「真实性」。
"""
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOC = ROOT / "protocol" / "demo_signers" / "README.md"
ALLOW = ROOT / "protocol" / "demo_signers" / "allowed_signers"
FORBIDDEN = ("端到端签名验证通过", "已签名并通过验证", "签名验证全绿")


def load_text(path: Path = DOC) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"demo_signers README 不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("demo_signers README 为空")
    return text


def reader_verify() -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "scripts/nf_verify.py", "--entry", "NF-1",
                           "--ssh-allowed-signers",
                           "protocol/demo_signers/allowed_signers"],
                          cwd=str(ROOT), capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=180, check=False)


def readme_issues(text: str) -> list:
    issues = []
    if not text.startswith("# 演示签名者（demo signers）"):
        issues.append("缺标题「# 演示签名者（demo signers）」")
    if "复核（2026-11-14）" not in text:
        issues.append("缺复核位")
    lines = [ln for ln in ALLOW.read_text(encoding="utf-8").splitlines() if ln.strip()]
    if len(lines) != 1:
        issues.append(f"allowed_signers 条目数已变（{len(lines)}，应为 1）")
    else:
        parts = lines[0].split()
        ok = (len(parts) == 4 and parts[1] == "ssh-ed25519"
              and parts[0].endswith("@local") and parts[0] == parts[3])
        if not ok:
            issues.append("allowed_signers 行格式不符"
                           "（期望「身份 ssh-ed25519 公钥 身份」四列、前后身份同名）")
    if "1 条" not in text:
        issues.append("现状未写允许清单 1 条")
    if "未挂签名锚" not in text:
        issues.append("未说明 NF-1 当前未挂签名锚")
    if "真实性未验" not in text and "真实性**未验**" not in text:
        issues.append("未写「真实性未验」口径")
    for section in ("## 现状对照", "## 复现与引用口径"):
        if section not in text:
            issues.append(f"缺段落：{section}")
    for line in text.splitlines():
        for bad in FORBIDDEN:
            if bad not in line:
                continue
            if any(w in line for w in ("不构成", "并非", "误读", "不等于")):
                continue
            issues.append(f"出现过强断言：{bad}")
    if "不构成「端到端签名验证通过」" not in text:
        issues.append("缺「机制可跑 != 已签名」的显式否认")
    for cmd in ("python scripts/nf_verify.py --entry NF-1",
                "python scripts/nf.py library verify"):
        if cmd not in text:
            issues.append(f"复现口径缺命令：{cmd}")
    if "TODO" in text:
        issues.append("含 TODO 占位")
    return issues


class DemoSignersReadmeTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_readme_matches_contract(self):
        self.assertEqual([], readme_issues(self.text), "demo_signers README 不满足契约")

    def test_reader_verify_runs_and_reports_truth_scope(self):
        proc = reader_verify()
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        self.assertIn("真实性", proc.stdout)
        self.assertIn("未验", proc.stdout)

    def test_contract_catches_mutations(self):
        """变异自证：缺锚状态 / 缺未验口径 / 出现过强断言 / 缺复现命令。"""
        no_anchor = self.text.replace("未挂签名锚", "已挂签名锚")
        self.assertTrue(any("未挂签名锚" in i for i in readme_issues(no_anchor)))
        no_scope = self.text.replace("真实性未验", "真实性已验")
        no_scope = no_scope.replace("真实性**未验**", "真实性**已验**")
        self.assertTrue(any("真实性未验" in i for i in readme_issues(no_scope)))
        strong = self.text + "\n本页结论：端到端签名验证通过。\n"
        self.assertTrue(any("过强断言" in i for i in readme_issues(strong)))
        no_cmd = self.text.replace("python scripts/nf_verify.py --entry NF-1", "验证 NF-1")
        self.assertTrue(any("nf_verify" in i for i in readme_issues(no_cmd)))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_demo_signers.md")


if __name__ == "__main__":
    unittest.main()
