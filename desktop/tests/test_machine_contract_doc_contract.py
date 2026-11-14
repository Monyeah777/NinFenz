#!/usr/bin/env python3
"""机读块 retro-fit 契约：作用域/L0/字段映射/幂等必须与实读一致。

为什么必须有：这页决定「哪些模块已有机读契约、没契约的怎么补」——
作用域（官方核心 13 件 vs 全库 248）、L0=0、字段来源映射、--write 幂等口径，
任何一项漂移都会让补块范围与判据错位。本轮补可核现状
（checked 13 / L0 0 / 248 全库 / 6 组字段映射 / --write 0 件）与「§现状对照」「§复现与引用口径」。

范围：只判本文与 machine_contract.scan/CLI/判据事实自洽（不改模块）。
同族判据：test_module_m00_contract.py 等代表件 / test_io_types.py / test_doc_hygiene.py。
契约：最后更新位 + 复核、作用域 13 件、L0 0、全库 248、6 组字段、--write 幂等、
outputs 待补 1 件（M15 证据）、现状对照 + 复现两命令、边界（re-freeze / 事件登记）。
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "desktop" / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import machine_contract as mc  # noqa: E402

DOC = ROOT / "docs" / "machine_contract.md"
SECTIONS = ("## 是什么", "## 怎么用", "## 现状对照", "## 复现与引用口径", "## 边界")
FIELDS = ("id", "name", "category", "layer", "inputs",
          "events.publish/subscribe", "outputs", "interfaces", "conformance")


def load_text(path: Path = DOC) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"机读块文档不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("机读块文档为空")
    return text


def mc_issues(text: str) -> list:
    issues = []
    if not text.startswith("# 机读块 retro-fit"):
        issues.append("缺标题「# 机读块 retro-fit（L0 → L1/L2）」")
    if "最后更新：" not in text:
        issues.append("缺「最后更新」位")
    if "复核" not in text:
        issues.append("缺「复核」说明")
    _i, _w, stats = mc.scan(str(ROOT))
    if int(stats.get("checked") or 0) != 13:
        issues.append(f"取证模块数已变（{stats.get('checked')}）")
    if int(stats.get("l0") or 0) != 0:
        issues.append(f"L0 非 0（{stats.get('l0')}）")
    if "**13 件**" not in text:
        issues.append("未写取证范围 13 件")
    if "**0 件**" not in text:
        issues.append("未写 L0 0 件")
    if "248" not in text:
        issues.append("未写全库 248")
    for f in ("id", "name", "category", "layer", "inputs", "events",
              "outputs", "interfaces", "conformance"):
        if f not in text:
            issues.append(f"字段映射缺：{f}")
    if "**6 组**" not in text:
        issues.append("未写 6 组字段")
    if "M15" not in text or "事件载荷" not in text:
        issues.append("缺 outputs 待补（M15/事件载荷）说明")
    if "不落盘" not in text:
        issues.append("缺「本轮不落盘」说明")
    positions = [text.find(s) for s in SECTIONS]
    for section, pos in zip(SECTIONS, positions, strict=True):
        if pos < 0:
            issues.append(f"缺段：{section}")
    if all(p >= 0 for p in positions) and positions != sorted(positions):
        issues.append("节顺序不对")
    for cmd in ("python scripts/nf.py module contract",
                "python -m pytest desktop/tests/test_module_m00_contract.py"):
        if cmd not in text:
            issues.append(f"复现口径缺命令：{cmd}")
    if "nf module signature --write" not in text:
        issues.append("缺「补块后重冻结签名」边界")
    if "event_registry.json" not in text:
        issues.append("缺事件登记缺口口径")
    if "TODO" in text:
        issues.append("含 TODO 占位")
    return issues


class MachineContractDocTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_machine_contract_matches(self):
        self.assertEqual([], mc_issues(self.text), "机读块文档不满足契约")

    def test_scan_live(self):
        _i, _w, stats = mc.scan(str(ROOT))
        self.assertEqual(0, int(stats["l0"]))
        self.assertEqual(13, int(stats["checked"]))

    def test_contract_catches_mutations(self):
        """变异自证：L0 回退 / 作用域回退 / 缺字段 / 缺 M15 / 缺命令。"""
        old_l0 = self.text.replace("**0 件**", "**3 件**")
        self.assertTrue(any("0 件" in i for i in mc_issues(old_l0)))
        old_scope = self.text.replace("**13 件**", "**9 件**")
        self.assertTrue(any("13 件" in i for i in mc_issues(old_scope)))
        no_field = self.text.replace("events", "evt")
        self.assertTrue(any("events" in i for i in mc_issues(no_field)))
        no_m15 = self.text.replace("M15", "M99")
        self.assertTrue(any("M15" in i for i in mc_issues(no_m15)))
        no_cmd = self.text.replace("python scripts/nf.py module contract", "跑覆盖")
        self.assertTrue(any("module contract" in i for i in mc_issues(no_cmd)))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_mc.md")


if __name__ == "__main__":
    unittest.main()
