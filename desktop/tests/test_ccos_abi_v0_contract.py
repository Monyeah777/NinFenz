#!/usr/bin/env python3
"""docs/ccos/abi-v0.md 契约：CCOS ABI 文档必须「7 调用形状/状态与登记面一致 + 数字活绑定」。

为什么必须有：这是正式协议档（形状固定、判定词表稳定），但它的价值全在「实装状态不许虚标」——
而它写的判据数字（攻击矩阵 38 / 向量集 28 / 声明 23 / 链测 9 / 策略词表 5）必须与实现逐项一致。
既有 test_ccos_abi_docs.py 已守 id/状态/错误码/向量数/maps_to；本判据补的是**其余四个数字的活绑定**
与「本文已有常驻机检」这一事实被写进文档（否则读者以为它是纯散文）。

范围：只判本文与实现/数据事实自洽（不改 ABI 形状）。同族判据：
test_ccos_abi_docs.py（7 例，本文件第一道机检）/ test_evidence_vectors.py /
test_evidence.py（38 条 bench）/ test_check_policy.py / test_ccos_chain.py。
契约：⛔ 标识 + last-updated + 复核位、7 个调用 id 与状态标注、错误码登记位在文、
五个数字与实现一致（38 例 bench / 28 向量 / 23 声明 / 9 链测 / 5 词表）、现状对照与复现四命令。
"""
import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "desktop" / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import check_policy  # noqa: E402

DOC = ROOT / "docs" / "ccos" / "abi-v0.md"
NF = ROOT / "scripts" / "nf.py"
EVID = ROOT / "desktop" / "src" / "core" / "evidence.py"
VECTORS = ROOT / "results" / "ccos" / "evidence_verdict_vectors.json"
CONTRACTS = ROOT / "protocol" / "asset_contracts.json"
CHAIN = ROOT / "scripts" / "ccos_chain.py"
ABI_GUARD = ROOT / "desktop" / "tests" / "test_ccos_abi_docs.py"
CALLS = ("cc_label", "cc_check", "cc_attest", "cc_verify", "cc_replay", "cc_diff",
         "cc_resolve")


def load_text(path: Path = DOC) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"ABI 文档不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("ABI 文档为空")
    return text


def bench_cases() -> int:
    return len(re.findall(r"_bench_run\(rows, ", EVID.read_text(encoding="utf-8")))


def declaration_count() -> int:
    data = json.loads(CONTRACTS.read_text(encoding="utf-8"))
    return sum(len(data.get(k) or []) for k in ("data", "code", "script", "index",
                                                "chains"))


def vectors_count() -> int:
    data = json.loads(VECTORS.read_text(encoding="utf-8"))
    return int(data["count"])


def chain_cases() -> int:
    return (ROOT / "desktop" / "tests" / "test_ccos_chain.py").read_text(
        encoding="utf-8").count("def test")


def abi_issues(text: str) -> list:
    issues = []
    if not text.startswith("# CCOS ABI v0"):
        issues.append("缺标题「# CCOS ABI v0：7 个系统调用」")
    if "⛔ 操作指令" not in text:
        issues.append("缺「⛔ 操作指令」标识")
    if "最后更新：" not in text:
        issues.append("缺「最后更新」位")
    if "复核（2026-11-13）" not in text:
        issues.append("缺「复核（2026-11-13）」位")
    for call in CALLS:
        if call not in text:
            issues.append(f"正文缺调用：{call}")
    if "Status" not in text:
        issues.append("缺 Status 行")
    if "protocol/error_codes.json" not in text:
        issues.append("缺错误码登记位")
    if "test_ccos_abi_docs.py" not in text:
        issues.append("未写本文已有常驻机检")
    if "## 现状对照" not in text:
        issues.append("缺「§现状对照」")
    if "## 复现与引用口径" not in text:
        issues.append("缺「§复现与引用口径」")
    n_bench = bench_cases()
    n_vec = vectors_count()
    n_decl = declaration_count()
    n_chain = chain_cases()
    n_kinds = len(check_policy.KINDS)
    if n_bench != 38:
        issues.append(f"bench 用例数已变（{n_bench}）")
    if n_vec != 28:
        issues.append(f"向量集已变（{n_vec}）")
    if n_decl != 23:
        issues.append(f"契约声明面已变（{n_decl}）")
    if n_chain != 9:
        issues.append(f"链测例数已变（{n_chain}）")
    if n_kinds != 5:
        issues.append(f"策略词表已变（{n_kinds}）")
    for label in ("38 例", "28 条", "23 条声明", "9 项", "5 类"):
        if label not in text:
            issues.append(f"现状数字缺要素：{label}")
    for kind in check_policy.KINDS:
        if kind not in text:
            issues.append(f"正文缺策略词表项：{kind}")
    for cmd in ("python scripts/nf.py evidence bench",
                "python scripts/nf.py evidence verify --selfcheck",
                "python scripts/ccos_chain.py --target STRATEGY.md --json",
                "python -m pytest desktop/tests/test_ccos_abi_docs.py"):
        if cmd not in text:
            issues.append(f"复现口径缺命令：{cmd}")
    if not ABI_GUARD.is_file():
        issues.append("缺既有 ABI 机检件")
    if "稳定面" not in text:
        issues.append("缺「判定词表/退出码 = 稳定面」")
    if "TODO" in text or "待补" in text:
        issues.append("含 TODO/待补 占位")
    return issues


class AbiDocContractTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_abi_matches_contract(self):
        self.assertEqual([], abi_issues(self.text), "ABI 文档不满足契约")

    def test_numbers_live(self):
        self.assertEqual(38, bench_cases())
        self.assertEqual(28, vectors_count())
        self.assertEqual(23, declaration_count())
        self.assertEqual(9, chain_cases())
        self.assertEqual(5, len(check_policy.KINDS))
        self.assertTrue(ABI_GUARD.is_file())
        self.assertTrue(CHAIN.is_file())

    def test_contract_catches_mutations(self):
        """变异自证：去复核位 / 缺调用 / 数字回退 / 缺词表项 / 缺机检声明 / 缺命令。"""
        no_date = self.text.replace("复核（2026-11-13）", "说明")
        self.assertTrue(any("复核（2026-11-13）" in i for i in abi_issues(no_date)))
        no_call = self.text.replace("cc_resolve", "cc_other")
        self.assertTrue(any("cc_resolve" in i for i in abi_issues(no_call)))
        old_n = self.text.replace("28 条", "27 条")
        self.assertTrue(any("28" in i for i in abi_issues(old_n)))
        no_kind = self.text.replace("digest_pin", "digest_fixed")
        self.assertTrue(any("digest_pin" in i for i in abi_issues(no_kind)))
        no_guard = self.text.replace("test_ccos_abi_docs.py", "某测试")
        self.assertTrue(any("机检" in i for i in abi_issues(no_guard)))
        no_cmd = self.text.replace("python scripts/nf.py evidence bench", "跑基准")
        self.assertTrue(any("evidence bench" in i for i in abi_issues(no_cmd)))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_abi.md")


if __name__ == "__main__":
    unittest.main()
