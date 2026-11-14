#!/usr/bin/env python3
"""protocol/README.md 契约：IDL 层说明的「schema 件数 / 白名单 / 扫描面 / check 接线」与实现一致。

为什么必须有：这是「IDL 单一真相」层的唯一入口说明。本轮实测发现它多处陈旧：写「五份契约定义」
（实为 9 份 schema，其中 5 份才是内容契约）、「44 个模块文档（现行 23/44）」（实为 248 份模块文档，
其中在场机读块的 13 份）、「8 条管线文档」「5 份 community protocol.yaml」（实为 114 / 111）。
这些数字让读者低估扫描面；而它们是**内容侧**数字，本来就不该钉。本轮改为「以 LINT_INPUTS 实读为准」
并补判据：件数/白名单/扫描面/四道 check 必须与实现一致，且正文不得再出现旧钉数。

范围：只判本文与 schema_lint/verify.sh 事实自洽（不改 IDL 机制）。
同族判据：test_schema_reference.py（交叉对照）/ test_machine_contract_doc_contract.py（01 层）。
契约：复核位、9 schema（5+4 拆分在文）、白名单 16 逐名、LINT_INPUTS 9 条、check28/29/30/31 接线、
不钉件数、复现命令、**正文不含旧钉数（44/23/44、8 条管线、5 份 protocol.yaml）**。
"""
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "desktop" / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import schema_lint as sl  # noqa: E402

DOC = ROOT / "protocol" / "README.md"
SCHEMA_DIR = ROOT / "protocol" / "schema"
VERIFY = ROOT / "verify.sh"
STALE = ("44 个模块", "23/44", "8 条管线", "5 份 community protocol.yaml")


def load_text(path: Path = DOC) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"protocol README 不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("protocol README 为空")
    return text


def readme_issues(text: str) -> list:
    issues = []
    if not text.startswith("# protocol/ · 协议层 IDL"):
        issues.append("缺标题「# protocol/ · 协议层 IDL」")
    if "复核（2026-11-14）" not in text:
        issues.append("缺复核位")
    schemas = sorted(p.name for p in SCHEMA_DIR.glob("*.json"))
    if len(schemas) != 9:
        issues.append(f"schema 件数已变（{len(schemas)}）")
    if "九份" not in text:
        issues.append("标题未写「九份 IDL 定义」")
    for kw in sorted(sl.SUBSET_ALLOWED_KEYS):
        if kw not in text:
            issues.append(f"白名单关键字未列：{kw}")
    if "**16** 个关键字" not in text:
        issues.append("现状未写白名单 16 关键字")
    if len(sl.LINT_INPUTS) != 9:
        issues.append(f"LINT_INPUTS 条数已变（{len(sl.LINT_INPUTS)}）")
    if "**9** 条通配" not in text:
        issues.append("现状未写扫描面 9 条通配")
    verify_text = VERIFY.read_text(encoding="utf-8")
    for n in ("28", "29", "30", "31"):
        if f"check{n}()" not in verify_text:
            issues.append(f"verify.sh 缺 check{n}")
        if f"check{n}" not in text:
            issues.append(f"正文未点名 check{n}")
    for line in text.splitlines():
        for stale in STALE:
            if stale not in line:
                continue
            # 允许在「本轮修三处陈旧钉数…实为…」这类留痕句里出现
            if any(w in line for w in ("陈旧", "实为", "留痕", "修")):
                continue
            issues.append(f"正文仍有旧钉数：{stale}")
    if "不钉件数" not in text:
        issues.append("缺「不钉件数」口径")
    if "LINT_INPUTS" not in text:
        issues.append("未把扫描面指向 LINT_INPUTS")
    for cmd in ("python scripts/nf.py verify --only 28",
                "python -m pytest desktop/tests/test_schema_reference.py"):
        if cmd not in text:
            issues.append(f"复现口径缺命令：{cmd}")
    if "TODO" in text:
        issues.append("含 TODO 占位")
    return issues


class ProtocolReadmeTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_readme_matches_contract(self):
        self.assertEqual([], readme_issues(self.text), "protocol README 不满足契约")

    def test_schema_lint_live(self):
        self.assertEqual(9, len(list(SCHEMA_DIR.glob("*.json"))))
        self.assertEqual(9, len(sl.LINT_INPUTS))
        self.assertEqual(16, len(sl.SUBSET_ALLOWED_KEYS))

    def test_check28_runs(self):
        proc = subprocess.run([sys.executable, "scripts/nf.py", "verify", "--only", "28"],
                              cwd=str(ROOT), capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=300, check=False)
        self.assertEqual(0, proc.returncode, proc.stdout[-400:])

    def test_contract_catches_mutations(self):
        """变异自证：旧钉数回潮 / 白名单缺关键字 / 缺 check 点名 / 缺不钉口径。"""
        stale = self.text + "\n- 44 个模块文档全量纳入扫描（现行 23/44）。\n"
        self.assertTrue(any("旧钉数" in i for i in readme_issues(stale)))
        no_kw = self.text.replace("pattern", "pat")
        self.assertTrue(any("白名单" in i or "pattern" in i for i in readme_issues(no_kw)))
        no_check = self.text.replace("check31", "检查31")
        self.assertTrue(any("check31" in i for i in readme_issues(no_check)))
        no_pin = self.text.replace("不钉件数", "件数固定")
        self.assertTrue(any("不钉件数" in i for i in readme_issues(no_pin)))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_protocol_readme.md")


if __name__ == "__main__":
    unittest.main()
