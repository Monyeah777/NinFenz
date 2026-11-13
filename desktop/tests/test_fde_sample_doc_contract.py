#!/usr/bin/env python3
"""docs/fde-sample/README.md 契约：五门数字/证据件/命令必须与证据实读一致。

为什么必须有：这份 README 是「NF 是 FDE 中游标准」的可跑证明入口——五道门的数字（声明面、schema 对、
图规模、装配链、标准锚）与证据件清单就是「样例有没有腐烂」的判据。原文只有一句「五门全 PASS」，
没有把 manifest 里的 6/2/48/47/4/370 写出来，读者无法自查。本轮补「§现状对照」+「§复现与引用口径」，
并把 README、evidence/manifest.json、gates.txt、check32 注册点全部活绑定。

范围：只判本文与样例证据件/脚本事实自洽（**不重跑 --run**，只读证据）。
同族判据：test_json_shape_contracts.py（manifest 形状）/ check32 的 fde_sample 子扫描 /
test_doc_hygiene.py / test_doc_examples.py。
契约：最后更新位 + 复核、六种事实（6/2/48/47/4/370）、五门名在文、证据四件在场、
--run/--check 两命令、check32 注册点、现状对照 + 复现口径。
"""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

DIR = ROOT / "docs" / "fde-sample"
DOC = DIR / "README.md"
MANIFEST = DIR / "evidence" / "manifest.json"
GATES = DIR / "evidence" / "gates.txt"
SCRIPT = ROOT / "scripts" / "fde_sample_run.py"
VERIFY = ROOT / "verify.sh"
SECTIONS = ("## 一、样例对象", "## 二、怎么跑", "## 三、五道门", "## 现状对照",
            "## 复现与引用口径", "## 四、复算与失败处置")
GATES_NAMES = ("G1", "G2", "G3", "G4", "G5")
EVIDENCE = ("deliverable.md", "gates.txt", "result.jsonl", "manifest.json")


def load_text(path: Path = DOC) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"FDE 样例说明不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("FDE 样例说明为空")
    return text


def manifest() -> dict:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def fde_issues(text: str) -> list:
    issues = []
    if not text.startswith("# FDE 交付样例"):
        issues.append("缺标题「# FDE 交付样例（可跑 · 可复算）」")
    if "最后更新：" not in text:
        issues.append("缺「最后更新」位")
    if "复核" not in text:
        issues.append("缺「复核」说明")
    man = manifest()
    facts = man.get("facts") or {}
    want = {"declared_outputs": 6, "schema_pairs": 2, "concept_nodes": 48,
            "topo_len": 47, "standards": 370}
    for k, v in want.items():
        if int(facts.get(k) or 0) != v:
            issues.append(f"facts.{k} 已变（{facts.get(k)}）")
    if facts.get("provenance_strength") != "external":
        issues.append("证据强度已变")
    for label in ("6", "2", "48", "47", "370"):
        if label not in text:
            issues.append(f"正文缺数字：{label}")
    if "external" not in text:
        issues.append("正文缺证据强度 external")
    if man.get("issues"):
        issues.append(f"manifest 有 issues：{man['issues']}")
    gates_txt = GATES.read_text(encoding="utf-8")
    for g in GATES_NAMES:
        if g not in text:
            issues.append(f"正文缺门：{g}")
        if ("[PASS] " + g) not in gates_txt:
            issues.append(f"gates.txt 缺 PASS：{g}")
    for name in EVIDENCE:
        if not (DIR / "evidence" / name).is_file():
            issues.append(f"证据件缺失：{name}")
    if "4 件" not in text:
        issues.append("未写证据四件")
    verify = VERIFY.read_text(encoding="utf-8")
    if "check32" not in verify:
        issues.append("verify.sh 缺 check32")
    if "fde_sample" not in verify:
        issues.append("check32 未注册 fde_sample")
    if "check32 子扫描" not in text:
        issues.append("未写门禁位置（check32 子扫描）")
    script = SCRIPT.read_text(encoding="utf-8") if SCRIPT.is_file() else ""
    for flag in ("--run", "--check"):
        if flag not in script:
            issues.append(f"脚本缺旗标：{flag}")
        if flag not in text:
            issues.append(f"正文缺命令旗标：{flag}")
    positions = [text.find(s) for s in SECTIONS]
    for section, pos in zip(SECTIONS, positions, strict=True):
        if pos < 0:
            issues.append(f"缺段：{section}")
    if all(p >= 0 for p in positions) and positions != sorted(positions):
        issues.append("节顺序不对")
    for cmd in ("python scripts/fde_sample_run.py --check",
                "python scripts/fde_sample_run.py --run"):
        if cmd not in text:
            issues.append(f"复现口径缺命令：{cmd}")
    if "不引入新真源" not in text:
        issues.append("缺「不引入新真源」边界")
    if "TODO" in text or "待补" in text:
        issues.append("含 TODO/待补 占位")
    return issues


class FdeSampleDocTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_fde_readme_matches_contract(self):
        self.assertEqual([], fde_issues(self.text), "FDE 样例说明不满足契约")

    def test_evidence_live(self):
        facts = manifest()["facts"]
        self.assertEqual(6, facts["declared_outputs"])
        self.assertEqual(2, facts["schema_pairs"])
        self.assertEqual(48, facts["concept_nodes"])
        self.assertEqual(47, facts["topo_len"])
        self.assertEqual(370, facts["standards"])
        self.assertEqual("external", facts["provenance_strength"])
        for name in EVIDENCE:
            self.assertTrue((DIR / "evidence" / name).is_file(), name)

    def test_contract_catches_mutations(self):
        """变异自证：声明面回退 / 图规模回退 / 缺门 / 缺证据件数 / 缺命令。"""
        old = self.text.replace("48", "44")
        self.assertTrue(any("48" in i for i in fde_issues(old)))
        old_t = self.text.replace("47", "44")
        self.assertTrue(any("47" in i for i in fde_issues(old_t)))
        no_g = self.text.replace("G4", "G6")
        self.assertTrue(any("G4" in i for i in fde_issues(no_g)))
        no_e = self.text.replace("4 件", "3 件")
        self.assertTrue(any(("4 件" in i) or ("四件" in i)
                            for i in fde_issues(no_e)))
        no_cmd = self.text.replace("python scripts/fde_sample_run.py --run", "重跑")
        self.assertTrue(any("--run" in i for i in fde_issues(no_cmd)))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_fde.md")


if __name__ == "__main__":
    unittest.main()
