#!/usr/bin/env python3
"""docs/io_types.md 契约：I/O 类型面文档必须「9 值词表/覆盖率/判定原则与实现实读一致」。

为什么必须有：这页是「类型面到底覆盖多少」的唯一对外说明——词表、覆盖率、可证不匹配数、
untyped 的合法地位，任何一项漂移都会让读者以为「类型面已收窄」或「untyped 是缺陷」。
本轮补可核现状（248 模块 / 308-of-1141 = 27.0% / 0 不匹配 / write 幂等）与现状对照、复现口径。
本判据把 KINDS（9）、coverage() 四项统计、判定原则三条、write 幂等口径全部活绑定。

范围：只判本文与 io_types 实现/CLI/判据事实自洽（不改类型面）。
同族判据：test_io_types.py（10 例）/ test_machine_contract*.py / test_doc_hygiene.py。
契约：最后更新位 + 复核、9 值词表逐值在文、248/0/308/1141/27.0% 与 coverage() 相等、
三条判定原则在文、untyped 合法在文、现状对照 + 复现两命令。
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "desktop" / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import io_types  # noqa: E402

DOC = ROOT / "docs" / "io_types.md"
SECTIONS = ("## 是什么", "## 判定原则", "## 取值来源", "## 怎么用", "## 现状对照",
            "## 复现与引用口径", "## 边界", "## 相关")
KINDS = ("string", "integer", "number", "boolean", "array", "object", "event",
         "state", "untyped")


def load_text(path: Path = DOC) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"I-O 类型面文档不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("I-O 类型面文档为空")
    return text


def cov() -> dict:
    return io_types.coverage(str(ROOT))


def io_issues(text: str) -> list:
    issues = []
    if not text.startswith("# I/O 类型面（io_types）"):
        issues.append("缺标题「# I/O 类型面（io_types）」")
    if "最后更新：" not in text:
        issues.append("缺「最后更新」位")
    if "复核" not in text:
        issues.append("缺「复核」说明")
    kinds = tuple(io_types.KINDS)
    if kinds != KINDS:
        issues.append(f"词表已变：{kinds}")
    if len(kinds) != 9:
        issues.append(f"词表值数已变（{len(kinds)}）")
    for k in kinds:
        if k not in text:
            issues.append(f"正文缺词表值：{k}")
    c = cov()
    if int(c["modules_with_contract"]) != 248:
        issues.append(f"机读模块数已变（{c['modules_with_contract']}）")
    if int(c["l0_modules"]) != 0:
        issues.append(f"L0 未承载非 0（{c['l0_modules']}）")
    total = int(c["typed_fields"]) + int(c["untyped_fields"])
    if total != 1141:
        issues.append(f"字段总数已变（{total}）")
    if int(c["typed_fields"]) != 308:
        issues.append(f"已标注字段已变（{c['typed_fields']}）")
    if format(float(c["coverage"]), ".1f") != "27.0":
        issues.append(f"覆盖率已变（{c['coverage']}）")
    for marker in ("**248**", "**308**", "1141", "27.0%", "**0**"):
        if marker not in text:
            issues.append(f"现状对照缺要素：{marker}")
    for rule in ("越词表", "无一匹配", "WARN", "不判死"):
        if rule not in text:
            issues.append(f"判定原则缺要素：{rule}")
    if "禁止为省事编造类型" not in text:
        issues.append("缺「禁止编造类型」边界")
    if "untyped" not in text:
        issues.append("缺 untyped 合法口径")
    if "幂等" not in text:
        issues.append("缺 write 幂等口径")
    positions = [text.find(s) for s in SECTIONS]
    for section, pos in zip(SECTIONS, positions, strict=True):
        if pos < 0:
            issues.append(f"缺段：{section}")
    if all(p >= 0 for p in positions) and positions != sorted(positions):
        issues.append("节顺序不对")
    for cmd in ("python scripts/nf.py module types",
                "python -m pytest desktop/tests/test_io_types.py"):
        if cmd not in text:
            issues.append(f"复现口径缺命令：{cmd}")
    if "TODO" in text or "待补" in text:
        issues.append("含 TODO/待补 占位")
    return issues


class IoTypesDocTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_io_types_matches_contract(self):
        self.assertEqual([], io_issues(self.text), "I/O 类型面文档不满足契约")

    def test_coverage_live(self):
        c = cov()
        self.assertEqual(248, int(c["modules_with_contract"]))
        self.assertEqual(0, int(c["l0_modules"]))
        self.assertEqual(1141, int(c["typed_fields"]) + int(c["untyped_fields"]))
        self.assertEqual(9, len(io_types.KINDS))

    def test_contract_catches_mutations(self):
        """变异自证：词表回退 / 覆盖率回退 / 缺判定原则 / 缺命令 / 缺幂等口径。"""
        no_kind = self.text.replace("untyped", "any")
        self.assertTrue(any("untyped" in i for i in io_issues(no_kind)))
        old_c = self.text.replace("27.0%", "30.0%")
        self.assertTrue(any("27.0" in i for i in io_issues(old_c)))
        no_rule = self.text.replace("无一匹配", "不确定")
        self.assertTrue(any("判定原则" in i for i in io_issues(no_rule)))
        no_cmd = self.text.replace("python scripts/nf.py module types", "看覆盖率")
        self.assertTrue(any("module types" in i for i in io_issues(no_cmd)))
        no_idem = self.text.replace("幂等", "重复")
        self.assertTrue(any("幂等" in i for i in io_issues(no_idem)))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_io.md")


if __name__ == "__main__":
    unittest.main()
