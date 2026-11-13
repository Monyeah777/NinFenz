#!/usr/bin/env python3
"""docs/module_signature.md 契约：边界冻结文档必须「7 字段/248 全签/漂移 FAIL」与实现一致。

为什么必须有：这页是「模块对外承诺被冻结」的唯一说明——边界字段集、
签名覆盖面、WARN 与 FAIL 的分档，任何一项漂移都会让读者误判「哪些改动需要重签」。
本轮补可核现状（248 模块全签、7 个边界字段、
漂移 0、conformance 契约 module-signature、doc_hygiene 分类 how-to）
与「§现状对照」「§复现与引用口径」。

范围：只判本文与 module_signature/_BOUNDARY_KEYS/基线/判据事实自洽（不改基线）。
同族判据：test_machine_contract_doc_contract.py / test_design_checklist_contract.py /
test_conformance_run.py / test_doc_hygiene.py。
契约：最后更新位 + 复核、248 模块与已签数、7 个字段逐名、漂移即 FAIL / 未签撤下只 WARN、
conformance 契约 id、how-to 分类、现状对照 + 复现两命令。
"""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "desktop" / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import module_signature as ms  # noqa: E402

DOC = ROOT / "docs" / "module_signature.md"
BASELINE = ROOT / "protocol" / "module_signatures.json"
SECTIONS = ("## 是什么", "## 怎么用", "## 现状对照", "## 复现与引用口径", "## 边界")
FIELDS = ("inputs", "outputs", "events", "interfaces", "layer", "category", "io_types")


def load_text(path: Path = DOC) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"模块边界文档不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("模块边界文档为空")
    return text


def baseline() -> dict:
    return json.loads(BASELINE.read_text(encoding="utf-8"))


def sig_issues(text: str) -> list:
    issues = []
    if not text.startswith("# 模块边界冻结"):
        issues.append("缺标题「# 模块边界冻结（module signature）」")
    if "最后更新：" not in text:
        issues.append("缺「最后更新」位")
    if "复核" not in text:
        issues.append("缺「复核」说明")
    keys = tuple(ms._BOUNDARY_KEYS)
    if keys != FIELDS:
        issues.append(f"边界字段已变：{keys}")
    for f in FIELDS:
        if f not in text:
            issues.append(f"正文缺字段：{f}")
    if "**7**" not in text:
        issues.append("未写 7 个字段")
    b = baseline()
    n = len(b.get("modules") or [])
    if n != 248:
        issues.append(f"模块/已签数已变（{n}）")
    for label in ("**248**", "**248**（全签）"):
        if label not in text:
            issues.append(f"现状缺要素：{label}")
    if "漂移" not in text or "FAIL" not in text:
        issues.append("缺漂移即 FAIL 口径")
    if "WARN" not in text:
        issues.append("缺未签/撤下只 WARN 口径")
    if "module-signature" not in text:
        issues.append("缺 conformance 契约 id：module-signature")
    if "how-to" not in text:
        issues.append("缺 doc_hygiene 分类 how-to")
    positions = [text.find(s) for s in SECTIONS]
    for section, pos in zip(SECTIONS, positions, strict=True):
        if pos < 0:
            issues.append(f"缺段：{section}")
    if all(p >= 0 for p in positions) and positions != sorted(positions):
        issues.append("节顺序不对")
    for cmd in ("python scripts/nf.py module signature",
                "python scripts/nf.py conformance"):
        if cmd not in text:
            issues.append(f"复现口径缺命令：{cmd}")
    if "不参与" not in text:
        issues.append("缺「易变文本不参与」边界")
    if "TODO" in text:
        issues.append("含 TODO 占位")
    return issues


class ModuleSignatureDocTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_signature_matches_contract(self):
        self.assertEqual([], sig_issues(self.text), "模块边界文档不满足契约")

    def test_impl_live(self):
        self.assertEqual(FIELDS, tuple(ms._BOUNDARY_KEYS))
        self.assertEqual(248, len(baseline()["modules"]))

    def test_contract_catches_mutations(self):
        """变异自证：字段缺项 / 覆盖数回退 / 缺 WARN 分档 / 缺契约 id / 缺命令。"""
        no_f = self.text.replace("io_types", "typez")
        self.assertTrue(any("io_types" in i for i in sig_issues(no_f)))
        old_n = self.text.replace("**248**（全签）", "**200**（全签）")
        self.assertTrue(any("248" in i for i in sig_issues(old_n)))
        no_w = self.text.replace("WARN", "告警")
        self.assertTrue(any("WARN" in i for i in sig_issues(no_w)))
        no_c = self.text.replace("module-signature", "modules")
        self.assertTrue(any("module-signature" in i for i in sig_issues(no_c)))
        no_cmd = self.text.replace("python scripts/nf.py module signature", "校验签名")
        self.assertTrue(any("module signature" in i for i in sig_issues(no_cmd)))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_sig.md")


if __name__ == "__main__":
    unittest.main()
