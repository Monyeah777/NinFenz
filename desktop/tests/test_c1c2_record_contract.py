#!/usr/bin/env python3
"""docs/41_波C_C1_C2 实测记录 契约：快照状态 + 现状对照 + 复现口径 + 引用件在场。

为什么必须有：这是一份**历史实测快照**——它写着「35 份签名文档 / PASS=37」，但公开仓随后移除了
08–40 计划文档（2026-10 本地归档），被比的 24_/36_ 两件已不在公开仓。读者若把它当现状会误判。
本轮加「历史快照」状态横幅、「现状对照（当时→现行）」表、「复现与引用口径」段，并把
「状态横幅在场」「被引件归档事实一致」「签名面数字 = 现行根目录文档数」「复现命令真在 CLI」
立成机检断言。

范围：只判本文与引用事实/现行仓库状态的自洽（不改历史数值）。同族判据：
test_knowledge_sig.py（check25 语义）/ test_doc_reachability.py（引用可解析）/
test_doc_truth.py（命令面）/ verify.sh check25（签名可复现门禁）。
契约：标题 + 快照状态横幅、C1/C2/门禁与回归/现状对照/复现口径五段按序、历史数值保留、
24_/36_ 已归档事实一致（公开仓无此件且文中标注本地归档）、签名面「文档 N」= 根目录编号文档数、
实现/判据/门禁三引用件在场、复现三命令在 CLI 注册表。
"""
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "desktop" / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import prose_lint as pl  # noqa: E402

DOC = ROOT / "docs" / "41_波C_C1_C2_实测记录.md"
SECTIONS = ("## C1", "## C2", "## 门禁与回归", "## 现状对照", "## 复现与引用口径")
REFS = ("desktop/src/core/knowledge_sig.py", "desktop/tests/test_knowledge_sig.py",
        "scripts/nf.py", "verify.sh")
REPRO_COMMANDS = ("sig --verify", "explain check25", "diff")
ARCHIVED = ("24_v2.1.0_全链管道化方案.md", "36_v2.5.0_基础层深化续方案.md")


def load_text(path: Path = DOC) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"实测记录不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("实测记录为空")
    return text


def numbered_docs() -> list:
    return sorted(p.name for p in ROOT.glob("*.md") if re.match(r"^\d{2}_", p.name))


def record_issues(text: str) -> list:
    issues = []
    if not text.startswith("# 41 波C C1/C2 实测记录"):
        issues.append("缺标题「# 41 波C C1/C2 实测记录」")
    if "状态：历史实测快照" not in text:
        issues.append("缺「历史实测快照」状态横幅（读者会误当现状）")
    if "不随仓库演进而改写" not in text:
        issues.append("缺「不随演进改写」声明")
    positions = [text.find(s) for s in SECTIONS]
    for section, pos in zip(SECTIONS, positions, strict=True):
        if pos < 0:
            issues.append(f"缺段：{section}")
    if all(p >= 0 for p in positions) and positions != sorted(positions):
        issues.append("五段顺序不对")
    for ref in REFS:
        if not (ROOT / ref).is_file():
            issues.append(f"引用件不存在：{ref}")
        if ref.split("/")[-1] not in text:
            issues.append(f"正文未引用：{ref}")
    verify = (ROOT / "verify.sh").read_text(encoding="utf-8")
    if "check25" not in verify:
        issues.append("verify.sh 缺 check25（签名门禁）")
    nf = (ROOT / "scripts" / "nf.py").read_text(encoding="utf-8")
    for sub in ("sig", "diff", "explain"):
        if 'add_parser("' + sub + '"' not in nf:
            issues.append(f"CLI 缺子命令：nf {sub}")
    if "check25" not in text:
        issues.append("缺 check25 口径")
    if "PASS=37" not in text:
        issues.append("历史数值 PASS=37 被改写（历史快照不应改写）")
    if "390 OK" not in text:
        issues.append("历史数值 390 OK 被改写")
    docs = numbered_docs()
    want = "文档 " + str(len(docs)) + " · 可复现 1"
    if "文档 4 · 可复现 1" not in text:
        issues.append("缺现行签名面实测「文档 4 · 可复现 1」")
    if len(docs) != 4:
        issues.append(f"根目录编号文档数已变（{len(docs)}）：现状对照需复核（want {want}）")
    for name in ARCHIVED:
        if (ROOT / name).exists():
            issues.append(f"被引件仍在公开仓根目录，与「已归档」叙述矛盾：{name}")
    if "本地归档" not in text:
        issues.append("缺「24_/36_ 已本地归档」事实标注")
    if "实跑为准" not in text:
        issues.append("缺「数值以实跑为准」口径")
    if "TODO" in text or "待补" in text:
        issues.append("含 TODO/待补 占位")
    for cmd in REPRO_COMMANDS:
        if cmd not in text:
            issues.append(f"复现口径缺命令：nf {cmd}")
    cmds = pl.cli_commands(str(ROOT))
    if not cmds:
        issues.append("CLI 注册表读不到")
    return issues


class C1C2RecordContractTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_record_matches_contract(self):
        self.assertEqual([], record_issues(self.text), "实测记录不满足契约")

    def test_archived_citations_absent_from_root(self):
        for name in ARCHIVED:
            self.assertFalse((ROOT / name).exists(), name)
        self.assertIn("本地归档", self.text)

    def test_signature_count_matches_root(self):
        self.assertEqual(4, len(numbered_docs()))
        self.assertIn("文档 4 · 可复现 1", self.text)

    def test_contract_catches_mutations(self):
        """变异自证：去状态横幅 / 改历史数值 / 改签名面数字 / 去归档标注 / 缺复现命令。"""
        no_banner = self.text.replace("> **状态：历史实测快照**", "> **状态：现行**", 1)
        self.assertTrue(any("历史实测快照" in i for i in record_issues(no_banner)))
        rewritten = self.text.replace("PASS=37", "PASS=75", 1)
        self.assertTrue(any("PASS=37" in i for i in record_issues(rewritten)))
        wrong_count = self.text.replace("文档 4 · 可复现 1", "文档 35 · 可复现 1", 1)
        self.assertTrue(any("文档 4" in i or "编号文档数" in i
                            for i in record_issues(wrong_count)))
        no_archive = self.text.replace("本地归档", "已移除").replace("已本地归档", "已移除")
        self.assertTrue(any("归档" in i for i in record_issues(no_archive)))
        no_repro = self.text.replace("sig --verify", "sig")
        self.assertTrue(any("sig --verify" in i for i in record_issues(no_repro)))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_record.md")


if __name__ == "__main__":
    unittest.main()
