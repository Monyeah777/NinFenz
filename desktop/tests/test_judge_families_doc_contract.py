#!/usr/bin/env python3
"""docs/ccos/judge-families.md 契约：判据族谱必须「8 族齐 + 族证据真实存在 + 探针数字活绑定」。

为什么必须有：这份族谱的灵魂是「每族的证据在哪、怎么失效」——如果族证据指向**不存在的测试文件**，
读者按图索骥会扑空，整页就从「族谱」退化成「传说」。本轮修的真实缺陷正是这类：结构判据族写
test_c2_envelopes，仓库里没有该文件（C2 信封断言实际在 test_cognition_bridge.py 内）。本判据把
「族证据文件必须存在且出现在对应族」与三个探针的现状数字（5/15/1.0/0.0；25/21/0.84；比例 0.264）
全部活绑定。

范围：只判本文与测试文件/探针结果事实自洽（不改族划分）。同族判据：
test_judge_questions_doc_contract.py（十一问）/ test_judge_mutation_probe.py /
test_gate_probe.py / test_judge_red_evidence.py / test_doc_hygiene.py。
契约：8 族标题齐 + 最后更新位 + 复核、族证据逐个文件在场且在文、无失效引用 test_c2_envelopes、
变异探针 5·15·1.0·0.0、闸门 25·21·0.84 与缺 4 门清单、红证据比例 0.264、现状对照 + 复现三命令。
"""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import judge_red_evidence as jr  # noqa: E402

DOC = ROOT / "docs" / "ccos" / "judge-families.md"
FAMILIES = ("## 一、内容判据", "## 二、结构判据", "## 三、引用面判据", "## 四、文档数字判据",
            "## 五、接线判据", "## 六、元判据", "## 七、棘轮判据", "## 八、执行面判据")
EVIDENCE = {
    "内容判据": ("desktop/tests/test_cognition_bridge.py",
             "desktop/tests/test_cognition_control.py",
             "desktop/tests/test_cognition_workspace.py",
             "desktop/tests/test_method_pack.py"),
    "结构判据": ("desktop/tests/test_cognition_bridge.py",
             "desktop/tests/test_isomorphism_matrix.py",
             "desktop/tests/test_path_flag_ratchet.py"),
    "引用面判据": ("desktop/tests/test_method_pack.py",
              "desktop/tests/test_ccos_docs_anchors.py",
              "desktop/tests/test_script_orphans.py"),
    "接线判据": ("desktop/tests/test_cog_cli_faces.py",
             "desktop/tests/test_release_conclusion.py"),
    "元判据": ("scripts/judge_mutation_probe.py", "scripts/gate_probe.py",
            "scripts/self_audit_probe.py",
            "desktop/tests/test_judge_mutation_probe.py"),
    "棘轮判据": ("desktop/tests/test_path_flag_ratchet.py",
             "desktop/tests/test_judge_red_evidence.py",
             "desktop/tests/test_core_judge_map.py"),
    "执行面判据": ("desktop/tests/test_pack_runnable_runs.py",
              "desktop/tests/test_method_pack.py"),
    "文档数字判据": ("desktop/tests/test_ccos_abi_docs.py",),
}
SECTIONS = ("## 现状对照", "## 复现与引用口径", "## 怎么读这张表")


def load_text(path: Path = DOC) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"判据族谱不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("判据族谱为空")
    return text


def family_issues(text: str) -> list:
    issues = []
    if not text.startswith("# 判据族谱 v0"):
        issues.append("缺标题「# 判据族谱 v0（谁在检查什么，以及它们怎么失效）」")
    if "最后更新：" not in text:
        issues.append("缺「最后更新」位")
    if "复核" not in text:
        issues.append("缺「复核」说明")
    for fam in FAMILIES:
        if fam not in text:
            issues.append(f"缺族：{fam}")
    legit = ("不存在", "修正", "旧写", "test_cognition_bridge")
    bad_ref = [ln for ln in text.splitlines()
               if "test_c2_envelopes" in ln and not any(k in ln for k in legit)]
    if bad_ref:
        issues.append("仍引用不存在的 test_c2_envelopes")
    for fam, paths in EVIDENCE.items():
        for rel in paths:
            if not (ROOT / rel).is_file():
                issues.append(f"{fam} 证据文件不存在：{rel}")
            name = rel.rsplit("/", 1)[-1].removesuffix(".py")
            if name not in text:
                issues.append(f"{fam} 正文缺证据：{name}")
    for label in ("5 判据 / 15 变异体", "杀死率 1.0", "误报率 0.0"):
        if label not in text:
            issues.append(f"变异探针口径缺要素：{label}")
    for label in ("25 闸门", "21", "0.84"):
        if label not in text:
            issues.append(f"闸门探针口径缺要素：{label}")
    for gate in ("coupling_fresh", "docs_anchors", "abi_docs", "verifier_version"):
        if gate not in text:
            issues.append(f"未列出缺拒绝型用例的闸门：{gate}")
    reg = json.loads((ROOT / jr.OUT_REL).read_text(encoding="utf-8"))
    ratio = reg["without_evidence"] / reg["modules"]
    if "0.264" not in text:
        issues.append("未写红证据比例 0.264")
    if ratio > 0.36:
        issues.append(f"红证据比例越线：{ratio:.4f}")
    positions = [text.find(s) for s in SECTIONS]
    for section, pos in zip(SECTIONS, positions, strict=True):
        if pos < 0:
            issues.append(f"缺段：{section}")
    if all(p >= 0 for p in positions) and positions != sorted(positions):
        issues.append("节顺序不对")
    for cmd in ("python scripts/judge_mutation_probe.py --check",
                "python scripts/gate_probe.py --check",
                "python scripts/judge_red_evidence.py --check"):
        if cmd not in text:
            issues.append(f"复现口径缺命令：{cmd}")
    if "TODO" in text or "待补" in text:
        issues.append("含 TODO/待补 占位")
    return issues


class JudgeFamiliesDocTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_families_match_contract(self):
        self.assertEqual([], family_issues(self.text), "判据族谱不满足契约")

    def test_evidence_files_live(self):
        for paths in EVIDENCE.values():
            for rel in paths:
                self.assertTrue((ROOT / rel).is_file(), rel)
        self.assertFalse((ROOT / "desktop" / "tests" / "test_c2_envelopes.py").exists())
        reg = json.loads((ROOT / jr.OUT_REL).read_text(encoding="utf-8"))
        self.assertLessEqual(reg["without_evidence"] / reg["modules"], 0.36)

    def test_contract_catches_mutations(self):
        """变异自证：去一族 / 回退失效引用 / 缺证据名 / 回退比例 / 缺复现命令。"""
        no_fam = self.text.replace("## 八、执行面判据", "## 九、执行面判据")
        self.assertTrue(any("缺族" in i for i in family_issues(no_fam)))
        back_ref = self.text + "\n证据：test_c2_envelopes\n"
        self.assertTrue(any("test_c2_envelopes" in i for i in family_issues(back_ref)))
        no_ev = self.text.replace("test_release_conclusion", "某测试")
        self.assertTrue(any("test_release_conclusion" in i
                            for i in family_issues(no_ev)))
        old_ratio = self.text.replace("0.264", "0.50")
        self.assertTrue(any("0.264" in i for i in family_issues(old_ratio)))
        no_cmd = self.text.replace("python scripts/gate_probe.py --check", "跑闸门")
        self.assertTrue(any("gate_probe.py --check" in i for i in family_issues(no_cmd)))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_families.md")


if __name__ == "__main__":
    unittest.main()
