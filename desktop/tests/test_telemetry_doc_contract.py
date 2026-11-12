#!/usr/bin/env python3
"""docs/45_执行遥测规范契约：格式文档必须与 trace 写入点/映射载体/E3 待办一致 + 复现口径。

为什么必须有：本文写「phase = plan | clarify | check」——但 assembly 的 --trace 写入点实际有
**四值**（还有 build）；且记录字段是**按 phase 子集**（plan 带 allowed_modules、check 才带
issues/stats），示例若按并集读会误判格式。本轮补四值、子集说明、records 包裹形态、映射载体
（telemetry_semconv.py）与现状对照，并把写入点/载体/边界立成机检断言。

范围：只判本文与 nf.py 写入点/telemetry_semconv 事实自洽（不改格式）。同族判据：
test_telemetry_semconv.py（8 例）/ test_doc_hygiene.py（指令档标识）/
test_doc_examples.py（命令块）/ test_payload_proposal_contract.py（相邻 45 波记录）。
契约：⛔ 标识 + last-updated、目的 + 格式 + 采集纪律 + 对外消费 + 现状对照 + 复现口径、
phase 四值在文且 nf.py 四个写入点在场、记录子集说明、records 包裹、semconv 载体与常量、
schema_url 未填、execution phase 仍待、8 例判据在文。
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "desktop" / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import telemetry_semconv as semconv  # noqa: E402

DOC = ROOT / "docs" / "45_执行遥测规范.md"
NF = ROOT / "scripts" / "nf.py"
SEMCONV = ROOT / "desktop" / "src" / "core" / "telemetry_semconv.py"
TEST = ROOT / "desktop" / "tests" / "test_telemetry_semconv.py"
SECTIONS = ("## 目的", "## 格式", "## 采集纪律", "## 对外消费", "## 现状对照",
            "## 复现与引用口径")
PHASES = ("plan", "clarify", "build", "check")
ATTRS = ("A_OPERATION", "A_TOOL_NAME", "A_TOOL_CALL_ID", "A_TOOL_ARGS",
         "A_TOOL_RESULT", "A_AGENT_NAME", "A_CONVERSATION")


def load_text(path: Path = DOC) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"遥测规范不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("遥测规范为空")
    return text


def case_count() -> int:
    return TEST.read_text(encoding="utf-8").count("def test")


def telemetry_issues(text: str) -> list:
    issues = []
    if not text.startswith("# 45 · 执行遥测规范"):
        issues.append("缺标题「# 45 · 执行遥测规范」")
    if "⛔ 操作指令" not in text:
        issues.append("缺「⛔ 操作指令」标识")
    if "最后更新：" not in text:
        issues.append("缺「最后更新」位")
    if "格式口径沿用" not in text:
        issues.append("缺「格式口径沿用」状态声明")
    positions = [text.find(s) for s in SECTIONS]
    for section, pos in zip(SECTIONS, positions, strict=True):
        if pos < 0:
            issues.append(f"缺段：{section}")
    if all(p >= 0 for p in positions) and positions != sorted(positions):
        issues.append("节顺序不对")
    nf = NF.read_text(encoding="utf-8")
    for phase in PHASES:
        if '"phase": "' + phase + '"' not in nf:
            issues.append(f"nf.py 缺 --trace 写入点：phase={phase}")
        if phase not in text:
            issues.append(f"正文缺 phase：{phase}")
    if "按 phase" not in text or "子集" not in text:
        issues.append("缺「字段按 phase 子集」说明")
    if "records" not in text:
        issues.append("缺 records 包裹形态")
    if not SEMCONV.is_file():
        issues.append("缺映射实现 telemetry_semconv.py")
    for attr in ATTRS:
        if not hasattr(semconv, attr):
            issues.append(f"telemetry_semconv 缺常量：{attr}")
    if "telemetry_semconv.py" not in text:
        issues.append("未点名映射实现文件")
    if "schema_url" not in text:
        issues.append("缺 schema_url 未填边界")
    if "phase=execution" not in text:
        issues.append("缺 E3 / execution phase 仍待口径")
    if "仍待" not in text:
        issues.append("缺「仍待」如实标注")
    n_cases = case_count()
    if n_cases != 8:
        issues.append(f"test_telemetry_semconv 例数已变（{n_cases}）")
    if str(n_cases) + " 例" not in text:
        issues.append(f"未写常驻判据例数（{n_cases} 例）")
    for cmd in ("python scripts/nf.py assemble --help",
                "python scripts/nf.py telemetry <trace.json>",
                "python -m pytest desktop/tests/test_telemetry_semconv.py"):
        if cmd not in text:
            issues.append(f"复现口径缺命令：{cmd}")
    return issues


class TelemetryDocContractTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_telemetry_doc_matches_contract(self):
        self.assertEqual([], telemetry_issues(self.text), "遥测规范不满足契约")

    def test_phases_and_mapping_live(self):
        nf = NF.read_text(encoding="utf-8")
        for phase in PHASES:
            self.assertIn('"phase": "' + phase + '"', nf)
        for attr in ATTRS:
            self.assertTrue(hasattr(semconv, attr), attr)
        self.assertEqual(8, case_count())

    def test_contract_catches_mutations(self):
        """变异自证：去标识 / 缺 build / 缺子集 / 缺 records / 假称 execution 已完成 / 缺命令。"""
        no_marker = self.text.replace("⛔ 操作指令", "操作指令")
        self.assertTrue(any("⛔" in i for i in telemetry_issues(no_marker)))
        no_build = self.text.replace("build", "bak")
        self.assertTrue(any("build" in i for i in telemetry_issues(no_build)))
        no_subset = self.text.replace("子集", "整体")
        self.assertTrue(any("子集" in i for i in telemetry_issues(no_subset)))
        no_records = self.text.replace("records", "多条")
        self.assertTrue(any("records" in i for i in telemetry_issues(no_records)))
        done_exec = self.text.replace("phase=execution", "execution")
        self.assertTrue(any("execution" in i or "仍待" in i
                            for i in telemetry_issues(done_exec)))
        no_cmd = self.text.replace("python scripts/nf.py telemetry <trace.json>", "看映射")
        self.assertTrue(any("telemetry" in i for i in telemetry_issues(no_cmd)))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_telemetry.md")


if __name__ == "__main__":
    unittest.main()
