#!/usr/bin/env python3
"""docs/42_M2 契约：回合状态头 v1 规范必须与 round_header.LAWS / 06 §11 双源一致 + 硬断言现状 6 条。

为什么必须有：本文是判级器与状态头的规范档——铁律集 L1–L5 的「名称/级别」是三方一致的契约面
（round_header.LAWS 机读 / 本文规范 / 06 §11 协议位），任何一处漂移都会让「必须/禁止」判定失真；
同时「演练硬断言四规则」的说法已过期（44 drill 扩到 6 条）。本轮把铁律双源、规则现状、状态头
格式、重入判据、测试调用立成机检断言。

范围：只判本文与 round_header/06 自洽（不改判级语义）。同族判据：
test_round_header.py（幂等/重入）/ test_round_drill.py / test_selftest_spec_contract.py
（M1 规则集）/ test_doc_hygiene.py（指令档标识与 last-updated）。
契约：⛔ 标识 + last-updated、六节 + 现状对照 + 复现口径、判级器三级表、铁律 L1–L5 == LAWS
（id/name/level）、状态头格式行、06 §11 在册且含 L1-L5、硬断言 6 条声明、测试调用可用、
单测 3 例在场。
"""
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "desktop" / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import round_header as rh  # noqa: E402

DOC = ROOT / "docs" / "42_M2_回合状态头_v1.md"
AGENT = ROOT / "06_Agent执行协议.md"
RH_TEST = ROOT / "desktop" / "tests" / "test_round_header.py"
SECTIONS = ("## 一、判级器", "## 二、回合状态头格式", "## 三、P03 第 5 回合状态头实例",
            "## 四、引用后执行", "## 五、五维自评", "## 六、遗留",
            "## 现状对照", "## 复现与引用口径")
LEVELS = ("必须", "禁止", "应", "可")


def load_text(path: Path = DOC) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"M2 规范档不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("M2 规范档为空")
    return text


def law_rows() -> list:
    return [(law["id"], law["name"], law["level"]) for law in rh.LAWS]


def m2_issues(text: str) -> list:
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
    if "v1 规范" not in text or "复核" not in text:
        issues.append("缺「v1 规范 → 复核」状态口径")
    rows = law_rows()
    if [r[0] for r in rows] != ["L1", "L2", "L3", "L4", "L5"]:
        issues.append(f"LAWS 铁律集已变：{[r[0] for r in rows]}")
    for law_id, name, level in rows:
        if law_id not in text:
            issues.append(f"正文缺铁律 id：{law_id}")
        if name not in text:
            issues.append(f"正文缺铁律名：{name}")
        if level not in text:
            issues.append(f"正文缺级别：{level}")
    for marker in ("必须", "禁止", "应", "可"):
        if marker not in text:
            issues.append(f"判级器表缺强度词：{marker}")
    if "【回合状态头 v1】" not in text:
        issues.append("缺状态头格式行")
    for field in ("管线：", "已执行段：", "本回合：", "本回合铁律："):
        if field not in text:
            issues.append(f"状态头格式缺字段：{field}")
    agent = AGENT.read_text(encoding="utf-8")
    if "判级器与回合状态头" not in agent:
        issues.append("06 缺「判级器与回合状态头」协议位")
    if "L1-L5" not in agent:
        issues.append("06 状态头格式缺 L1-L5")
    if "6 规则" not in text:
        issues.append("未写硬断言现状 6 规则")
    if "cross_pipeline_id" not in text or "fabricated_asset_key" not in text:
        issues.append("缺新增两条硬断言")
    if not RH_TEST.is_file():
        issues.append("缺 test_round_header（重入判据）")
    if "replay_identity" not in text:
        issues.append("缺 replay_identity 重入口径")
    for cmd in ("python -m unittest desktop.tests.test_round_header", "test_round_header"):
        if cmd not in text:
            issues.append(f"复现口径缺要素：{cmd}")
    if "TODO" in text or "待补" in text:
        issues.append("含 TODO/待补 占位")
    return issues


class M2RoundHeaderContractTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_m2_matches_contract(self):
        self.assertEqual([], m2_issues(self.text), "M2 规范不满足契约")

    def test_laws_source_matches_doc(self):
        rows = law_rows()
        self.assertEqual(["L1", "L2", "L3", "L4", "L5"], [r[0] for r in rows])
        for law_id, name, level in rows:
            self.assertIn(law_id, self.text)
            self.assertIn(name, self.text)
            self.assertIn(level, self.text)

    def test_unittest_entrypoint_runs(self):
        proc = subprocess.run([sys.executable, "-m", "unittest",
                               "desktop.tests.test_round_header"],
                              cwd=str(ROOT), capture_output=True, text=True, timeout=120)
        self.assertEqual(0, proc.returncode, (proc.stderr or "")[:300])
        self.assertIn("Ran 3 tests", (proc.stderr or "") + (proc.stdout or ""))

    def test_contract_catches_mutations(self):
        """变异自证：去标识 / 铁律名缺失 / 规则回退四 / 缺状态头格式 / 缺重入口径 / 缺现状对照。"""
        no_marker = self.text.replace("⛔ 操作指令", "操作指令")
        self.assertTrue(any("⛔" in i for i in m2_issues(no_marker)))
        no_law = self.text.replace("L5", "L6")
        self.assertTrue(any("L5" in i or "铁律" in i for i in m2_issues(no_law)))
        old_rules = self.text.replace("6 规则", "4 规则")
        self.assertTrue(any("6 规则" in i for i in m2_issues(old_rules)))
        no_header = self.text.replace("【回合状态头 v1】", "回合状态头")
        self.assertTrue(any("状态头格式" in i for i in m2_issues(no_header)))
        no_replay = self.text.replace("replay_identity", "重放")
        self.assertTrue(any("replay_identity" in i for i in m2_issues(no_replay)))
        no_sec = self.text.replace("## 现状对照（2026-11-13 · 以实跑为准）", "## 表格")
        self.assertTrue(any("缺段" in i for i in m2_issues(no_sec)))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_m2.md")


if __name__ == "__main__":
    unittest.main()
