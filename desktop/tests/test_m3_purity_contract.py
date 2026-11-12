#!/usr/bin/env python3
"""docs/42_M3 契约：规则族现状 R1–R8 + 载体在场 + 文案差异如实 + 复现口径。

为什么必须有：本文首轮只写到 R1–R4（后补 R5/R6），但实现已扩到 **R1–R8**（R7 阶梯归属/越界、
R8 核心文面去叙述），单测 5→34 例。并且 nf explain check27 的文案仍写「五规则」，与实现不一致——
这类「规范档落后于实现 / 说明文案落后于规范」的漂移必须逐处标出，否则读者按旧规则集配置门禁。
本轮补状态横幅、R7/R8 行、现状对照（含文案差异如实标注）、复现口径，并把规则数/载体/例数立成断言。

范围：只判本文与 purity_scan/layer_model/domain_neutral 事实自洽（不改判据）。同族判据：
test_purity_scan.py（逐规则变异）/ test_doc_hygiene.py（指令档标识与 last-updated）/
verify.sh check27（门禁）。
契约：⛔ 标识 + last-updated、七节 + 现状对照 + 复现口径、R1–R8 全在文、
purity_scan 含 R1–R8 规则串、R7/R8 载体在场（layer_model.py / domain_neutral.py / LAYERS.json）、
单测 34 例、check27 在 verify.sh、explain 文案差异如实标注、历史值 PASS=41 保留。
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "desktop" / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "desktop" / "src"))

DOC = ROOT / "docs" / "42_M3_纯度体检.md"
PURITY = ROOT / "desktop" / "src" / "core" / "purity_scan.py"
LAYERS = ROOT / "protocol" / "LAYERS.json"
LAYER_MODEL = ROOT / "desktop" / "src" / "core" / "layer_model.py"
DOMAIN_NEUTRAL = ROOT / "desktop" / "src" / "core" / "domain_neutral.py"
TEST = ROOT / "desktop" / "tests" / "test_purity_scan.py"
VERIFY = ROOT / "verify.sh"
SECTIONS = ("## 一、四规则", "## 二、首轮实扫结果", "## 三、check27 变异自检",
            "## 四、门禁与回归", "## 五、五维自评", "## 六、R5 / R6",
            "## 七、R7 / R8", "## 现状对照", "## 复现与引用口径")


def load_text(path: Path = DOC) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"M3 规范档不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("M3 规范档为空")
    return text


def _test_count() -> int:
    return TEST.read_text(encoding="utf-8").count("def test")


def m3_issues(text: str) -> list:
    issues = []
    if "⛔ 操作指令" not in text:
        issues.append("指令档缺「⛔ 操作指令」标识")
    if "最后更新：" not in text:
        issues.append("缺「最后更新」位")
    positions = [text.find(s) for s in SECTIONS]
    for section, pos in zip(SECTIONS, positions, strict=True):
        if pos < 0:
            issues.append(f"缺段：{section}")
    if all(p >= 0 for p in positions) and positions != sorted(positions):
        issues.append("节顺序不对")
    if "R1–R8" not in text:
        issues.append("缺「规则族 R1–R8」现状声明")
    for n in range(1, 9):
        if f"R{n}" not in text:
            issues.append(f"正文缺规则：R{n}")
    purity = PURITY.read_text(encoding="utf-8")
    for n in range(1, 9):
        if f"R{n} " not in purity and f"R{n}：" not in purity:
            issues.append(f"purity_scan 缺规则串：R{n}")
    for path in (LAYERS, LAYER_MODEL, DOMAIN_NEUTRAL):
        if not path.is_file():
            issues.append(f"载体缺件：{path.relative_to(ROOT).as_posix()}")
    if "layer_model.py" not in text:
        issues.append("R7 未写语义判据载体 layer_model.py")
    if "domain_neutral.py" not in text:
        issues.append("R8 未写实现载体 domain_neutral.py")
    n_cases = _test_count()
    if n_cases != 34:
        issues.append(f"test_purity_scan 例数已变（{n_cases}）：现状对照需复核")
    if "34 例" not in text:
        issues.append("未写单测现行 34 例")
    verify = VERIFY.read_text(encoding="utf-8")
    if "check27" not in verify:
        issues.append("verify.sh 缺 check27")
    if "五规则" not in text:
        issues.append("缺 explain 文案「五规则」差异的如实标注")
    if "以实现为准" not in text:
        issues.append("缺「文案以实现为准」口径")
    if "39→41" not in text:
        issues.append("历史值 39→41 被改写")
    for cmd in ("bash verify.sh --checks-only", "test_purity_scan.py"):
        if cmd not in text:
            issues.append(f"复现口径缺要素：{cmd}")
    if "待补" in text or "TODO 占位" in text:
        issues.append("含 TODO/待补 占位")
    return issues


class M3PurityContractTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_m3_matches_contract(self):
        self.assertEqual([], m3_issues(self.text), "M3 规范不满足契约")

    def test_rules_and_carriers_live(self):
        purity = PURITY.read_text(encoding="utf-8")
        for n in range(1, 9):
            self.assertIn(f"R{n}", purity)
        self.assertTrue(LAYER_MODEL.is_file())
        self.assertTrue(DOMAIN_NEUTRAL.is_file())
        self.assertEqual(34, _test_count())

    def test_contract_catches_mutations(self):
        """变异自证：去标识 / 去 R7-R8 / 例数漂移 / 缺文案差异 / 缺现状对照 / 缺复现命令。"""
        no_marker = self.text.replace("⛔ 操作指令", "操作指令")
        self.assertTrue(any("⛔" in i for i in m3_issues(no_marker)))
        no_r7 = self.text.replace("R7", "R九").replace("R8", "R十")
        self.assertTrue(any("R7" in i or "R8" in i for i in m3_issues(no_r7)))
        wrong = self.text.replace("34 例", "5 例")
        self.assertTrue(any("34 例" in i for i in m3_issues(wrong)))
        no_note = self.text.replace("五规则", "旧文案")
        self.assertTrue(any("五规则" in i for i in m3_issues(no_note)))
        no_sec = self.text.replace("## 现状对照（2026-11-13 · 以实跑为准）", "## 表格")
        self.assertTrue(any("缺段" in i for i in m3_issues(no_sec)))
        no_cmd = self.text.replace("bash verify.sh --checks-only", "跑门禁")
        self.assertTrue(any("verify.sh" in i for i in m3_issues(no_cmd)))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_m3.md")


if __name__ == "__main__":
    unittest.main()
