#!/usr/bin/env python3
"""docs/ccos/dual-core-invariants.md 契约：9 层与矩阵一致 + 判据/名单/门数活绑定。

为什么必须有：这份文档主张「同一不变量，两核各自证明一次」——最容易写成口号。它的可信度靠三个
硬绑定：① 9 层与矩阵数据件 covered 逐项一致（矩阵测试拒绝未登记层）；② 判定面脚本名单恰 10 个
（verifier_version.JUDGE_FILES）；③ 自省判据真在提交前自查里（precheck 23 门 + --full 2 慢门）。
旧版写「precheck 23 门」但没点名脚本与快/慢门口径；本轮补复核位、现状对照、复现口径并全部活绑定。

范围：只判本文与矩阵/verifier_version/precheck 事实自洽（不改不变量）。同族判据：
test_isomorphism_matrix.py（11 例）/ test_verifier_version.py /
precheck_gates.py（23+2）/ test_ccos_abi_docs.py / test_doc_hygiene.py。
契约：9 层名与矩阵 covered 集合相等且在文、矩阵件在场、11 例判据、JUDGE_FILES==10 且在文、
precheck GATES==23 / SLOW_GATES==2 且在文、self_audit.json 在场、现状对照与复现三命令。
"""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "desktop" / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "desktop" / "src"))
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

import precheck_gates  # noqa: E402
from core import verifier_version  # noqa: E402

DOC = ROOT / "docs" / "ccos" / "dual-core-invariants.md"
MATRIX = ROOT / "desktop" / "tests" / "fixtures" / "isomorphism_matrix.json"
ISO_TEST = ROOT / "desktop" / "tests" / "test_isomorphism_matrix.py"
SELF_AUDIT = ROOT / "results" / "ccos" / "self_audit.json"
PRECHECK = ROOT / "scripts" / "precheck.py"
LAYERS = ("时相", "身份", "观测", "语义", "负空间", "授权", "资源", "对抗", "自省")
SECTIONS = ("## 这份文档回答什么", "## 判据的形式", "## 九层一览", "## 自省闭环",
            "## 现状对照", "## 复现与引用口径", "## 边界")


def load_text(path: Path = DOC) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"双核不变量文档不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("双核不变量文档为空")
    return text


def matrix_layers() -> list:
    data = json.loads(MATRIX.read_text(encoding="utf-8"))
    out = []
    for item in data.get("covered") or []:
        out.append(item.get("layer") if isinstance(item, dict) else str(item))
    return out


def iso_cases() -> int:
    return ISO_TEST.read_text(encoding="utf-8").count("def test")


def invariant_issues(text: str) -> list:
    issues = []
    if not text.startswith("# 双核不变量 v0"):
        issues.append("缺标题「# 双核不变量 v0（九双生层 + 自省闭环）」")
    if "最后更新：" not in text:
        issues.append("缺「最后更新」位")
    if "复核" not in text:
        issues.append("缺「复核」说明")
    positions = [text.find(s) for s in SECTIONS]
    for section, pos in zip(SECTIONS, positions, strict=True):
        if pos < 0:
            issues.append(f"缺段：{section}")
    if all(p >= 0 for p in positions) and positions != sorted(positions):
        issues.append("节顺序不对")
    layers = matrix_layers()
    if sorted(layers) != sorted(LAYERS):
        issues.append(f"矩阵层集合已变：{layers}")
    if len(layers) != 9:
        issues.append(f"层数已变（{len(layers)}）")
    for layer in LAYERS:
        if layer not in text:
            issues.append(f"正文缺层：{layer}")
    if not MATRIX.is_file():
        issues.append("缺矩阵数据件")
    if "isomorphism_matrix.json" not in text:
        issues.append("未点名矩阵数据源")
    if iso_cases() != 11:
        issues.append(f"isomorphism 判据例数已变（{iso_cases()}）")
    if str(iso_cases()) + " 例" not in text:
        issues.append(f"未写常驻判据例数（{iso_cases()} 例）")
    n_judge = len(verifier_version.JUDGE_FILES)
    if n_judge != 10:
        issues.append(f"判定面脚本数已变（{n_judge}）")
    if "10" not in text:
        issues.append("未写判定面脚本数（10）")
    if "JUDGE_FILES" not in text:
        issues.append("缺判定面名单真源（verifier_version.JUDGE_FILES）")
    n_gates = len(precheck_gates.GATES)
    n_slow = len(precheck_gates.SLOW_GATES)
    if n_gates != 23 or n_slow != 2:
        issues.append(f"precheck 门数已变（{n_gates}+{n_slow}）")
    if "23 门" not in text:
        issues.append("未写 23 门快检")
    if "2 慢门" not in text and "慢门" not in text:
        issues.append("未写 --full 慢门口径")
    if "precheck.py" not in text:
        issues.append("未点名 precheck 脚本")
    if not PRECHECK.is_file():
        issues.append("缺 scripts/precheck.py")
    if not SELF_AUDIT.is_file():
        issues.append("缺 results/ccos/self_audit.json")
    if "self_audit.json" not in text:
        issues.append("未写自省产物")
    for cmd in ("python scripts/precheck.py --json",
                "python -m pytest desktop/tests/test_isomorphism_matrix.py",
                "python -m pytest desktop/tests/test_verifier_version.py"):
        if cmd not in text:
            issues.append(f"复现口径缺命令：{cmd}")
    for marker in ("覆盖 ≠ 完备", "同构不等于同值"):
        if marker not in text:
            issues.append(f"缺边界：{marker}")
    if "TODO" in text or "待补" in text:
        issues.append("含 TODO/待补 占位")
    return issues


class DualCoreInvariantsDocTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_invariants_matches_contract(self):
        self.assertEqual([], invariant_issues(self.text), "双核不变量文档不满足契约")

    def test_matrix_and_precheck_live(self):
        self.assertEqual(9, len(matrix_layers()))
        self.assertEqual(10, len(verifier_version.JUDGE_FILES))
        self.assertEqual(23, len(precheck_gates.GATES))
        self.assertEqual(2, len(precheck_gates.SLOW_GATES))
        self.assertTrue(SELF_AUDIT.is_file())
        self.assertEqual(11, iso_cases())

    def test_contract_catches_mutations(self):
        """变异自证：去复核位 / 缺层 / 层数回退 / 缺名单真源 / 缺门数 / 缺复现命令。"""
        no_date = self.text.replace("复核", "说明")
        self.assertTrue(any("复核" in i for i in invariant_issues(no_date)))
        no_layer = self.text.replace("负空间", "空间")
        self.assertTrue(any("负空间" in i for i in invariant_issues(no_layer)))
        old_n = self.text.replace("11 例", "9 例")
        self.assertTrue(any("例数" in i or "11" in i for i in invariant_issues(old_n)))
        no_judge = self.text.replace("JUDGE_FILES", "某名单")
        self.assertTrue(any("JUDGE_FILES" in i for i in invariant_issues(no_judge)))
        no_gate = self.text.replace("23 门", "20 门")
        self.assertTrue(any("23 门" in i for i in invariant_issues(no_gate)))
        no_cmd = self.text.replace("python scripts/precheck.py --json", "跑快检")
        self.assertTrue(any("precheck.py --json" in i for i in invariant_issues(no_cmd)))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_invariants.md")


if __name__ == "__main__":
    unittest.main()
