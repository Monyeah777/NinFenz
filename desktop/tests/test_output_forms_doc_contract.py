#!/usr/bin/env python3
"""docs/output-forms.md 契约：产出形态文档必须「116/12 类别/状态分布/机验率」与基线一致。

为什么必须有：这页把「产出形态」变成一等对象——形态清单规模、状态分布、包级产出面数量、
总体机验率，任何一项漂移都会让读者误判「哪些形态真的机验、覆盖率多少」。
本轮补「§现状对照」「§复现与引用口径」：116 条 / 12 类别（可达 110 · 不可达 6）/
absorbed 17·supported 11·reference 10·planned 61·deferred 11·unfit 6 /
106 个包级产出面 / 1050 件 / 机验率 0.7688 / 34 例。

范围：只判本文与 output_forms 清单/基线/CLI/判据事实自洽（不改清单）。
同族判据：test_output_forms.py（34 例）/ test_doc_hygiene.py / test_live_doc_counts.py。
契约：最后更新位 + 复核、116 条、12 类别、六档状态分布、106 包、1050 件、0.7688、
6 条不可达、34 例、现状对照 + 复现三命令、机验率=回退闸口径。
"""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

DOC = ROOT / "docs" / "output-forms.md"
FORMS = ROOT / "protocol" / "output_forms.json"
BASE = ROOT / "protocol" / "output_forms_baseline.json"
SECTIONS = ("## 是什么", "## 怎么用", "## 现状对照", "## 复现与引用口径",
            "## 本仓现在的机验产出面", "## 哪些没做（边界，如实记档）")
STATUS = {"absorbed": 17, "supported": 11, "reference": 10,
          "planned": 61, "deferred": 11, "unfit": 6}


def load_text(path: Path = DOC) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"产出形态文档不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("产出形态文档为空")
    return text


def facts() -> dict:
    d = json.loads(FORMS.read_text(encoding="utf-8"))
    forms = d.get("forms") or []
    counts = {}
    for f in forms:
        s = f.get("status")
        counts[s] = counts.get(s, 0) + 1
    unreachable = sum(1 for f in forms
                      if (f.get("evidence") or {}).get("reachable") is False)
    base = json.loads(BASE.read_text(encoding="utf-8"))["totals"]
    packs = list(ROOT.glob("community/*/outputs/INDEX.json"))
    return {"forms": len(forms), "cats": len({f.get("category") for f in forms}),
            "counts": counts, "unreachable": unreachable,
            "packs": len(packs), "ratio": base["machine_verifiable_ratio"],
            "machine": base["machine_verifiable"], "prose": base["prose_assets"]}


def forms_issues(text: str) -> list:
    issues = []
    if not text.startswith("# 产出形态"):
        issues.append("缺标题「# 产出形态（output forms）」")
    if "最后更新：" not in text:
        issues.append("缺「最后更新」位")
    if "复核" not in text:
        issues.append("缺「复核」说明")
    f = facts()
    if f["forms"] != 116:
        issues.append(f"形态数已变（{f['forms']}）")
    if f["cats"] != 12:
        issues.append(f"类别数已变（{f['cats']}）")
    if f["counts"] != STATUS:
        issues.append(f"状态分布已变：{f['counts']}")
    if f["unreachable"] != 6:
        issues.append(f"不可达数已变（{f['unreachable']}）")
    for label in ("**116 条 / 12 类别**", "**6 条不可达**", "**1050 件**", "**0.7688**",
                  "**34 例**"):
        if label not in text:
            issues.append(f"现状缺要素：{label}")
    for key in STATUS:
        if key not in text:
            issues.append(f"状态分布缺：{key}")
    if str(f["packs"]) not in text:
        issues.append(f"未写包级产出面数（{f['packs']}）")
    if "T0" not in text or "T4" not in text:
        issues.append("缺 T0–T4 档位口径")
    if "回退" not in text:
        issues.append("缺「机验率挡回退」口径")
    positions = [text.find(s) for s in SECTIONS]
    for section, pos in zip(SECTIONS, positions, strict=True):
        if pos < 0:
            issues.append(f"缺段：{section}")
    if all(p >= 0 for p in positions) and positions != sorted(positions):
        issues.append("节顺序不对")
    for cmd in ("python scripts/nf.py output verify --json",
                "python scripts/nf.py output meter --write",
                "python -m pytest desktop/tests/test_output_forms.py"):
        if cmd not in text:
            issues.append(f"复现口径缺命令：{cmd}")
    if "T4" not in text or "复算" not in text:
        issues.append("缺 T4 可复算口径")
    if "TODO" in text:
        issues.append("含 TODO 占位")
    return issues


class OutputFormsDocTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_forms_matches_contract(self):
        self.assertEqual([], forms_issues(self.text), "产出形态文档不满足契约")

    def test_data_live(self):
        f = facts()
        self.assertEqual(116, f["forms"])
        self.assertEqual({"absorbed": 17, "supported": 11, "reference": 10,
                          "planned": 61, "deferred": 11, "unfit": 6}, f["counts"])
        self.assertEqual(6, f["unreachable"])
        self.assertAlmostEqual(0.7688, f["ratio"], places=4)

    def test_contract_catches_mutations(self):
        """变异自证：形态数回退 / 类别回退 / 缺状态 / 缺不可达 / 缺命令。"""
        old = self.text.replace("**116 条 / 12 类别**", "**100 条 / 12 类别**")
        self.assertTrue(any("116" in i for i in forms_issues(old)))
        no_cat = self.text.replace("**116 条 / 12 类别**", "**116 条 / 9 类别**")
        self.assertTrue(any("类别" in i for i in forms_issues(no_cat)))
        no_st = self.text.replace("deferred", "later")
        self.assertTrue(any("deferred" in i for i in forms_issues(no_st)))
        no_un = self.text.replace("**6 条不可达**", "**0 条不可达**")
        self.assertTrue(any("不可达" in i for i in forms_issues(no_un)))
        no_cmd = self.text.replace("python scripts/nf.py output meter --write", "重算")
        self.assertTrue(any("meter" in i for i in forms_issues(no_cmd)))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_forms.md")


if __name__ == "__main__":
    unittest.main()
