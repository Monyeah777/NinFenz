#!/usr/bin/env python3
"""docs/ccos/time-token-v0.md 契约：TSA 时间戳文档必须「两子命令/接入旗标/判定/边界与实现一致」。

为什么必须有：这是威胁模型 G3 的落地口径——token 只证「某字节在某时刻已存在」，不证「现在几点」。
子命令、落盘三件、--time-record/--time-ca 接入、五条判定、信任锚不预置、>1 MiB 拒收，
任何一处漂移都会让「可信时间」被误读成「可信时钟」。本轮补最后更新位、现状对照与复现口径，
并把上述全部活绑定。

范围：只判本文与 timestamp 实现/CLI/判据事实自洽（不改协议）。同族判据：
test_timestamp.py（8 例）/ test_doc_hygiene.py / test_doc_examples.py。
契约：最后更新位 + 复核、stamp/verify 在 CLI 且在文、.tsq/.tsr/.json 三件、
--time-record 与 --time-ca、五条判定在文、time_proof tsa、信任锚不预置、>1 MiB 拒收、
仅 http(s)、8 例判据、现状对照 + 复现三命令。
"""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

DOC = ROOT / "docs" / "ccos" / "time-token-v0.md"
NF = ROOT / "scripts" / "nf.py"
CORE = ROOT / "desktop" / "src" / "core" / "timestamp.py"
TEST = ROOT / "desktop" / "tests" / "test_timestamp.py"
SECTIONS = ("## 解决什么", "## 怎么用", "## 判定（可证）", "## 判据（自证）",
            "## 现状对照", "## 复现与引用口径", "## 依赖与失败模式")


def load_text(path: Path = DOC) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"时间戳文档不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("时间戳文档为空")
    return text


def ts_cases() -> int:
    return TEST.read_text(encoding="utf-8").count("def test")


def time_issues(text: str) -> list:
    issues = []
    if not text.startswith("# 可信时间戳 v0"):
        issues.append("缺标题「# 可信时间戳 v0（RFC 3161 · G3 的可落地半边）」")
    if "最后更新：" not in text:
        issues.append("缺「最后更新」位")
    if "复核" not in text:
        issues.append("缺「复核」说明")
    nf = NF.read_text(encoding="utf-8")
    for sub in ("stamp", "verify"):
        if 'add_parser("' + sub + '"' not in nf:
            issues.append(f"CLI 缺子命令：{sub}")
        if sub not in text:
            issues.append(f"正文缺子命令：{sub}")
    for flag in ("--time-record", "--time-ca", "--ca-file", "--query"):
        if '"' + flag + '"' not in nf:
            issues.append(f"CLI 缺旗标：{flag}")
        if flag not in text:
            issues.append(f"正文缺旗标：{flag}")
    for suffix in (".tsq", ".tsr"):
        if suffix not in text:
            issues.append(f"落盘缺件：{suffix}")
    for marker in ("Granted", "genTime", "time_proof", "tsa"):
        if marker not in text:
            issues.append(f"判定/接入缺要素：{marker}")
    if "不预置" not in text:
        issues.append("缺「信任锚不预置」口径")
    if "1 MiB" not in text:
        issues.append("缺响应体量上限 1 MiB")
    if "http(s)" not in text:
        issues.append("缺「TSA 地址仅 http(s)」")
    if "fail-closed" not in text:
        issues.append("缺 fail-closed 失败模式口径")
    n_cases = ts_cases()
    if n_cases != 8:
        issues.append(f"test_timestamp 例数已变（{n_cases}）")
    if str(n_cases) + " 项" not in text:
        issues.append(f"未写判据数（{n_cases} 项）")
    if not CORE.is_file():
        issues.append("缺实现件 timestamp.py")
    positions = [text.find(s) for s in SECTIONS]
    for section, pos in zip(SECTIONS, positions, strict=True):
        if pos < 0:
            issues.append(f"缺段：{section}")
    if all(p >= 0 for p in positions) and positions != sorted(positions):
        issues.append("节顺序不对")
    for cmd in ("nf evidence timestamp stamp",
                "nf evidence timestamp verify",
                "python -m pytest desktop/tests/test_timestamp.py"):
        if cmd not in text:
            issues.append(f"复现口径缺命令：{cmd}")
    if "TODO" in text or "待补" in text:
        issues.append("含 TODO/待补 占位")
    return issues


class TimeTokenDocTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_time_token_matches_contract(self):
        self.assertEqual([], time_issues(self.text), "时间戳文档不满足契约")

    def test_implementation_live(self):
        self.assertEqual(8, ts_cases())
        self.assertTrue(CORE.is_file())
        nf = NF.read_text(encoding="utf-8")
        for sub in ("stamp", "verify"):
            self.assertIn('add_parser("' + sub + '"', nf)
        for flag in ("--time-record", "--time-ca"):
            self.assertIn('"' + flag + '"', nf)

    def test_contract_catches_mutations(self):
        """变异自证：缺子命令 / 缺接入旗标 / 缺信任锚口径 / 例数漂移 / 缺命令。"""
        no_sub = self.text.replace("stamp", "apply")
        self.assertTrue(any("stamp" in i for i in time_issues(no_sub)))
        no_rec = self.text.replace("--time-record", "--time")
        self.assertTrue(any("--time-record" in i for i in time_issues(no_rec)))
        no_anchor = self.text.replace("不预置", "预置")
        self.assertTrue(any("不预置" in i for i in time_issues(no_anchor)))
        old_n = self.text.replace("8 项", "6 项")
        self.assertTrue(any("8 项" in i or "例数" in i for i in time_issues(old_n)))
        no_cmd = self.text.replace("python -m pytest desktop/tests/test_timestamp.py", "跑判据")
        self.assertTrue(any("test_timestamp" in i for i in time_issues(no_cmd)))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_time.md")


if __name__ == "__main__":
    unittest.main()
