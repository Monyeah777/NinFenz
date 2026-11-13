#!/usr/bin/env python3
"""docs/verification-cards.md 契约：卡册散文不得钉运行时计数，生成区必须与 verify.sh 一致。

为什么必须有：这份卡册自己写着「门禁变更后应重新生成，否则会静默漂移」——而 2026-11-13 复核实测：
标题与「为什么有」两段**停在「40 条 / check1-40 / PASS=70」**，
生成区却早就是 42 条 / check1-42 / PASS=76 —— 这正是它想防的那种漂移。
本轮把散文里的钉数改成「见生成区」，并加一条判据：
散文（生成区之外、非历史留痕行）一律不许出现 check 数 / PASS 数 / 「N 条 check」。

范围：只判本文与 verify.sh / quality_baseline / 生成器事实自洽（不改门禁）。
同族判据：build_verification_cards.py --check（本判据会实跑）/ test_doc_hygiene.py。
契约：标题不含钉数、生成区与 verify.sh 一致、卡片总数 / 索引行数 / 基线行三处互等、
散文无未留痕的运行时计数、重建说明在场。
"""
import re
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

DOC = ROOT / "docs" / "verification-cards.md"
VERIFY = ROOT / "verify.sh"
BASELINE = ROOT / "desktop" / "src" / "core" / "quality_baseline.py"
CHECK = re.compile(r"^check(\d+)\(\)\{", re.M)
PIN = re.compile(r"check1-\d+|PASS=\d+|\d+\s*条\s*check")
HISTORY = ("曾", "历史", "此前", "实测", "2026-", "2025-", "当次")


def load_text(path: Path = DOC) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"验证卡册不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("验证卡册为空")
    return text


def verify_checks() -> int:
    return len(CHECK.findall(VERIFY.read_text(encoding="utf-8")))


def baseline() -> tuple:
    src = BASELINE.read_text(encoding="utf-8")
    c = int(re.search(r"EXPECTED_CHECKS = (\d+)", src).group(1))
    p = int(re.search(r"EXPECTED_PASS = (\d+)", src).group(1))
    return c, p


def prose_lines(text: str) -> list:
    """生成区之外、且非历史留痕行。生成区 = 全册概况表 + 卡片索引表。"""
    out = []
    skip = False
    for ln in text.splitlines():
        if ln.startswith("## 全册概况") or ln.startswith("## 卡片索引"):
            skip = True
            continue
        if skip and ln.startswith("## "):
            skip = False
        if skip or not ln.strip():
            continue
        if any(h in ln for h in HISTORY):
            continue
        out.append(ln)
    return out


def cards_issues(text: str) -> list:
    issues = []
    if not text.startswith("# NF 验证卡册"):
        issues.append("缺标题「# NF 验证卡册（门禁的人读复跑说明）」")
    if "40 条" in text.splitlines()[0]:
        issues.append("标题仍钉「40 条」")
    n = verify_checks()
    idx_rows = [ln for ln in text.splitlines() if re.match(r"^\| \d+ \| 段", ln)]
    if len(idx_rows) != n:
        issues.append(f"卡片索引行数 {len(idx_rows)} != verify.sh check 数 {n}")
    if f"| 卡片总数 | {n}（= verify.sh 的 check 函数数，实测） |" not in text:
        issues.append(f"概况卡片总数与 verify.sh 不一致（应为 {n}）")
    c, p = baseline()
    if f"| 声明基线 | check1-{c} · PASS={p}（源自 quality_baseline.EXPECTED_*） |" not in text:
        issues.append(f"概况声明基线与 quality_baseline 不一致（应为 check1-{c} · PASS={p}）")
    bad = [ln for ln in prose_lines(text) if PIN.search(ln)]
    if bad:
        issues.append(f"散文仍钉运行时计数（{len(bad)} 行）：{bad[0][:60]}")
    if "build_verification_cards.py --write" not in text:
        issues.append("缺重建说明")
    if "--check" not in text:
        issues.append("缺只读校验说明")
    return issues


class VerificationCardsDocTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_cards_matches_contract(self):
        self.assertEqual([], cards_issues(self.text), "验证卡册不满足契约")

    def test_generated_regions_fresh(self):
        proc = subprocess.run([sys.executable, "scripts/build_verification_cards.py", "--check"],
                              cwd=str(ROOT), capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=300, check=False)
        self.assertEqual(0, proc.returncode, (proc.stdout + proc.stderr)[-400:])

    def test_contract_catches_mutations(self):
        """变异自证：散文钉数 / 标题钉数 / 索引缺行 / 概况基线回退。"""
        pinned = self.text.replace("但「PASS=N」本身不说话",
                                   "但「PASS=70」本身不说话")
        self.assertTrue(any("钉运行时计数" in i for i in cards_issues(pinned)))
        title = self.text.replace("# NF 验证卡册（门禁的人读复跑说明）",
                                  "# NF 验证卡册（既有 40 条门禁的人读复跑说明）")
        self.assertTrue(any("标题" in i for i in cards_issues(title)))
        drop = "\n".join(ln for ln in self.text.splitlines()
                         if not ln.startswith("| 1 | 段")) + "\n"
        self.assertTrue(any("索引行数" in i for i in cards_issues(drop)))
        old = re.sub(r"\| 声明基线 \| [^|]+\|", "| 声明基线 | check1-40 · PASS=70 |",
                     self.text, count=1)
        self.assertTrue(any("声明基线" in i for i in cards_issues(old)))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_cards.md")


if __name__ == "__main__":
    unittest.main()
