#!/usr/bin/env python3
"""docs/interop-thirdparty.md 契约：他证通道说明页必须「面谱分档/自跑≠他证/状态表对账一致」。

为什么必须有：这一页是「第三方可自跑」的入口——但状态表里已有 13 条回填（其中 PASS 的 run_by 都是
「执行者（本机 …）」即本仓自跑）。原页面只写「未回填 = 未他证」，没说「**自跑也不算他证**」，
读者很容易把 PASS 行折算成第三方背书。本轮在生成器里补：① 回填纪律第 4 条（自跑 ≠ 他证）；
② 面谱分档表（peer 2 / official-cli 5 / shape-only 4 / not-applicable 3）；③ 现状对照表
（14 卡 / 12 导出面 / 上游判据 / 状态表），再重出说明页。本判据把这些事实与状态表逐项绑定。

范围：只判说明页与生成器/状态表/上游判据事实自洽（**不重跑 --emit**，它会把回填表重置）。
同族判据：test_interop_thirdparty_kit.py（逐字投影 + 状态表字段）/ test_interop.py /
test_doc_hygiene.py / test_doc_examples.py。
契约：生成物头、回填纪律四条（含自跑≠他证）、面谱 2/5/4/3 与逐面点名、现状对照四行、
14 卡片、状态表 14 行 + 未回填恰 1（ccv3）、上游判据件在盘。
"""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BT = chr(96)

DOC = ROOT / "docs" / "interop-thirdparty.md"
STATUS = ROOT / "results" / "interop-thirdparty-status.md"
UPSTREAM = ROOT / "results" / "interop-schema-validation.md"
SCRIPT = ROOT / "scripts" / "interop_thirdparty_kit.py"
SECTIONS = ("## 两种证据，别混", "## 回填纪律", "## 面谱", "## 现状对照", "## 他证卡")
KINDS = {"peer-consumption": 2, "official-cli": 5, "shape-only": 4, "not-applicable": 3}


def load_text(path: Path = DOC) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"他证通道说明页不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("他证通道说明页为空")
    return text


def status_rows() -> list:
    lines = STATUS.read_text(encoding="utf-8").splitlines()
    return [ln for ln in lines if ln.startswith("| " + BT)]


def doc_issues(text: str) -> list:
    issues = []
    if not text.startswith("# 互操作性 · 他证通道"):
        issues.append("缺标题「# 互操作性 · 他证通道（第三方可自跑）」")
    if "禁止手改" not in text:
        issues.append("缺「生成物，禁止手改」标记")
    for section in SECTIONS:
        if section not in text:
            issues.append(f"缺段：{section}")
    for marker in ("自跑 ≠ 他证", "不得折算成他证通过数", "他证要求"):
        if marker not in text:
            issues.append(f"缺「自跑≠他证」要素：{marker}")
    for kind, n in KINDS.items():
        if ("| " + kind + " | " + str(n) + " |") not in text:
            issues.append(f"面谱分档不符：{kind} 应 {n}")
    faces_total = 14
    got = text.count("\n### ")
    if got != faces_total:
        issues.append(f"卡片数应为 {faces_total}（实测 {got}）")
    for marker in ("**14**", "**12**", "results/interop-schema-validation.md",
                   "results/interop-thirdparty-status.md"):
        if marker not in text:
            issues.append(f"现状对照缺要素：{marker}")
    rows = status_rows()
    if len(rows) != 14:
        issues.append(f"状态表行数应为 14（实测 {len(rows)}）")
    unfilled = [ln for ln in rows if "未回填" in ln]
    if len(unfilled) != 1:
        issues.append(f"未回填应恰 1 行（实测 {len(unfilled)}）")
    if not UPSTREAM.is_file():
        issues.append("上游判据件不在盘")
    script = SCRIPT.read_text(encoding="utf-8")
    if "_kind_count" not in script or "_kind_faces" not in script:
        issues.append("生成器缺面谱辅助函数")
    if "自跑 ≠ 他证" not in script:
        issues.append("生成器缺「自跑≠他证」文案")
    if "TODO" in text or "待补" in text:
        issues.append("含 TODO/待补 占位")
    return issues


class InteropThirdpartyDocTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_doc_matches_contract(self):
        self.assertEqual([], doc_issues(self.text), "他证通道说明页不满足契约")

    def test_status_and_faces_live(self):
        self.assertEqual(14, len(status_rows()))
        self.assertEqual(1, len([ln for ln in status_rows() if "未回填" in ln]))
        self.assertTrue(UPSTREAM.is_file())
        self.assertEqual(14, self.text.count("\n### "))

    def test_contract_catches_mutations(self):
        """变异自证：缺自跑条 / 分档回退 / 少卡片 / 缺现状行。"""
        no_self = self.text.replace("自跑 ≠ 他证", "自跑也算他证")
        self.assertTrue(any("自跑" in i for i in doc_issues(no_self)))
        bad_kind = self.text.replace("| official-cli | 5 |", "| official-cli | 8 |")
        self.assertTrue(any("official-cli" in i for i in doc_issues(bad_kind)))
        no_card = self.text.replace("### " + BT + "ccv3" + BT, "")
        self.assertTrue(any("卡片数" in i for i in doc_issues(no_card)))
        no_row = self.text.replace("**12**", "**11**")
        self.assertTrue(any("现状对照" in i for i in doc_issues(no_row)))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_thirdparty.md")


if __name__ == "__main__":
    unittest.main()
