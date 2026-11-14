#!/usr/bin/env python3
"""docs/ccos/label-ir-v0.md 契约：承诺表/载体/边界自洽 + 数字活绑定 + 无重复小节。

为什么必须有：本文是 cc_label 声明层的规范，最危险的失真不是数字错，而是**文档内部自相矛盾**——
上方说 WebP/MP4/PDF 已实装且有判据，文末边界却说「等格式没有实测，一律走 sidecar 回退」；同页还出现
两个同名「与 cc_label 的关系」小节。读者按哪段做都可能有错。本轮修此两处，并把「已实装格式」「不再说
没有实测」「小节唯一」「16+33 项判据」「四份水印探针结果件」全部活绑定。

范围：只判本文与 label 实现/判据事实自洽（不改协议）。同族判据：
test_label_ir.py（16 例）/ test_label_carrier.py（33 例）/ test_label_watermark.py /
test_label_sidecar.py / test_doc_hygiene.py / test_doc_examples.py。
契约：最后更新位 + 复核、唯一「与 cc_label 的关系」、载体承诺小节、边界含「已实装格式」且不再称
WebP/MP4/PDF 没有实测、16/33 项判据、四份水印结果件在场、现状对照 + 复现四命令。
"""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

DOC = ROOT / "docs" / "ccos" / "label-ir-v0.md"
CORE = ROOT / "desktop" / "src" / "core" / "label_carrier.py"
IR_TEST = ROOT / "desktop" / "tests" / "test_label_ir.py"
CAR_TEST = ROOT / "desktop" / "tests" / "test_label_carrier.py"
PROBES = ("results/ccos/watermark_bench.json", "results/ccos/watermark_dct_probe.json",
          "results/ccos/watermark_sync_probe.json",
          "results/ccos/watermark_geometry_probe.json")
REL_HEADER = "## 与 " + chr(96) + "cc_label" + chr(96) + " 的关系"
SECTIONS = ("## 是什么 / 不是什么", "## 规则表", "## 怎么用", "## 判定（可证）",
            "## sidecar 回退载体", "## 载体（v0 已实装", "## 载体承诺（三件能自证的事）",
            REL_HEADER, "## 现状对照", "## 复现与引用口径", "## 复核")


def load_text(path: Path = DOC) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"标注 IR 文档不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("标注 IR 文档为空")
    return text


def case_count(path: Path) -> int:
    return path.read_text(encoding="utf-8").count("def test")


def ir_issues(text: str) -> list:
    issues = []
    if not text.startswith("# 标注 IR v0"):
        issues.append("缺标题「# 标注 IR v0（cc_label 的声明层）」")
    if "最后更新：" not in text:
        issues.append("缺「最后更新」位")
    if "复核" not in text:
        issues.append("缺「复核」说明")
    for section in SECTIONS:
        if section not in text:
            issues.append(f"缺段：{section}")
    if text.count("## 与 " + chr(96) + "cc_label" + chr(96) + " 的关系") != 1:
        issues.append("「与 cc_label 的关系」小节不唯一（曾重复两处）")
    if "## 载体承诺（三件能自证的事）" not in text:
        issues.append("缺「载体承诺」小节（原重复小节改名后应存在）")
    bad_claim = [ln for ln in text.splitlines()
                 if "没有实测" in ln and "原写" not in ln]
    if bad_claim:
        issues.append("边界仍称 WebP/MP4/PDF「没有实测」（与载体节矛盾）")
    if "**已实装格式**" not in text:
        issues.append("边界未写「已实装格式 = PNG/JPEG/WebP/MP4/PDF」")
    core = CORE.read_text(encoding="utf-8")
    for fmt in ("webp", "mp4", "pdf"):
        if ("_" + fmt) not in core:
            issues.append(f"carrier 实现缺格式：{fmt}")
    n_ir = case_count(IR_TEST)
    n_car = case_count(CAR_TEST)
    if n_ir != 16:
        issues.append(f"test_label_ir 例数已变（{n_ir}）")
    if n_car != 33:
        issues.append(f"test_label_carrier 例数已变（{n_car}）")
    for label in ("16 项", "33 项"):
        if label not in text:
            issues.append(f"未写判据数：{label}")
    for rel in PROBES:
        if not (ROOT / rel).is_file():
            issues.append(f"缺水印探针结果件：{rel}")
    for marker in ("embedded", "partial"):
        if marker not in text:
            issues.append(f"缺 ABI 状态要素：{marker}")
    both_tests = ("python -m pytest desktop/tests/test_label_ir.py "
                  "desktop/tests/test_label_carrier.py")
    for cmd in (both_tests,
                "python scripts/watermark_bench.py --check",
                "python scripts/watermark_dct_probe.py --check",
                "python scripts/watermark_sync_probe.py --check"):
        if cmd not in text:
            issues.append(f"复现口径缺命令：{cmd}")
    if "TODO" in text or "待补" in text:
        issues.append("含 TODO/待补 占位")
    return issues


class LabelIRDocTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_ir_matches_contract(self):
        self.assertEqual([], ir_issues(self.text), "标注 IR 文档不满足契约")

    def test_carrier_and_probes_live(self):
        core = CORE.read_text(encoding="utf-8")
        for fmt in ("webp", "mp4", "pdf"):
            self.assertIn("_" + fmt, core)
        for rel in PROBES:
            self.assertTrue((ROOT / rel).is_file(), rel)
        self.assertEqual(16, case_count(IR_TEST))
        self.assertEqual(33, case_count(CAR_TEST))

    def test_contract_catches_mutations(self):
        """变异自证：回退「没有实测」/ 缺已实装格式 / 重复小节 / 例数漂移 / 缺命令。"""
        back = self.text.replace("**已实装格式** = PNG / JPEG / WebP / MP4 / PDF",
                                 "MP4/PDF/WebP 等格式没有实测")
        self.assertTrue(any("没有实测" in i for i in ir_issues(back)))
        dup = self.text + "\n" + REL_HEADER + "\n\n重复小节\n"
        self.assertTrue(any("不唯一" in i for i in ir_issues(dup)))
        no_n = self.text.replace("16 项", "12 项").replace("33 项", "20 项")
        self.assertTrue(any("16 项" in i or "33 项" in i for i in ir_issues(no_n)))
        no_cmd = self.text.replace("python scripts/watermark_bench.py --check", "跑基准")
        self.assertTrue(any("watermark_bench" in i for i in ir_issues(no_cmd)))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_label.md")


if __name__ == "__main__":
    unittest.main()
