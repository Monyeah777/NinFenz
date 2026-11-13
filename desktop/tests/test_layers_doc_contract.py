#!/usr/bin/env python3
"""docs/layers.md 契约：抽象阶梯文档必须「四阶/五子级/入口 4/纵切 6/L1–L10 与真源一致」。

为什么必须有：这页是「一件东西属于哪一阶、谁可以依赖它」的唯一可判定入口——四阶、资产子级、入口面、
验证纵切件、判据规则数，任何一项漂移都会让归属判定失效。本轮补可核现状（4 阶 / 5 子级 / 4 入口 /
6 纵切件 / 7 派生 / 2 退役 / 10 规则 / 27+19 例）与「§现状对照」「§复现与引用口径」。
只改生成区外：生成区由 nf layers --write 渲染，手工改必被 L10 判红。

范围：只判本文（含生成区契约）与 LAYERS.json / layer_model 事实自洽（不改真源）。
同族判据：test_layer_model.py（27 例）/ test_architecture_layers.py（19 例）/ test_doc_hygiene.py。
契约：最后更新位 + 复核、四阶 id 与中文阶名在文、5 子级、入口面 4 件点名、纵切 6 件、
L1–L10 在文、生成区标记成对、现状对照 + 复现三命令。
"""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

DOC = ROOT / "docs" / "layers.md"
DATA = ROOT / "protocol" / "LAYERS.json"
BEGIN = "<!-- nf:layers:begin -->"
END = "<!-- nf:layers:end -->"
SECTIONS = ("## 这份文件解决什么", "## 怎么用", "## 阶梯（生成区", "## 现状对照",
            "## 复现与引用口径", "## 五条纪律")


def load_text(path: Path = DOC) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"抽象阶梯文档不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("抽象阶梯文档为空")
    return text


def layers() -> dict:
    return json.loads(DATA.read_text(encoding="utf-8"))


def layer_doc_issues(text: str) -> list:
    issues = []
    if not text.startswith("# NF 抽象阶梯（layers）"):
        issues.append("缺标题「# NF 抽象阶梯（layers）」")
    if "最后更新：" not in text:
        issues.append("缺「最后更新」位")
    if "复核" not in text:
        issues.append("缺「复核」说明")
    d = layers()
    tiers = [t.get("id") for t in d.get("tiers") or []]
    if tiers != ["contract", "asset", "engine", "export"]:
        issues.append(f"四阶已变：{tiers}")
    for name in ("契约", "资产", "引擎", "出口"):
        if name not in text:
            issues.append(f"正文缺阶名：{name}")
    if len(d.get("asset_levels") or []) != 5:
        issues.append("资产子级数已变")
    for lv in ("声明", "内容", "数据", "知识", "本体"):
        if lv not in text:
            issues.append(f"正文缺子级：{lv}")
    if len(d.get("surfaces") or []) != 4:
        issues.append("入口面数已变")
    for face in ("人机入口", "AI 装配线", "MCP 服务面", "图书馆取件面"):
        if face not in text:
            issues.append(f"正文缺入口面：{face}")
    comps = ((d.get("crosscut") or {}).get("components") or [])
    if len(comps) != 6:
        issues.append(f"纵切件数已变（{len(comps)}）")
    for cid in ("verify", "conformance", "audit", "receipts", "attest", "provenance"):
        if cid not in text:
            issues.append(f"正文缺纵切件：{cid}")
    if "**6**（verify" not in text:
        issues.append("未写纵切件 6")
    if len(d.get("rules") or []) != 10:
        issues.append("判据规则数已变")
    if "L1–L10（10 条）" not in text:
        issues.append("未写 L1–L10（10 条）")
    lines = [ln.strip() for ln in text.splitlines()]
    if lines.count(BEGIN) != 1 or lines.count(END) != 1:
        issues.append("生成区标记不成对")
    if "禁止手改" not in text:
        issues.append("缺「生成区禁止手改」口径")
    if "**4 阶**" not in text:
        issues.append("未写四阶计数")
    positions = [text.find(s) for s in SECTIONS]
    for section, pos in zip(SECTIONS, positions, strict=True):
        if pos < 0:
            issues.append(f"缺段：{section}")
    if all(p >= 0 for p in positions) and positions != sorted(positions):
        issues.append("节顺序不对")
    for cmd in ("python scripts/nf.py layers --verify",
                "python scripts/nf.py layers --json",
                "python -m pytest desktop/tests/test_layer_model.py"):
        if cmd not in text:
            issues.append(f"复现口径缺命令：{cmd}")
    if "依赖只许向下" not in text:
        issues.append("缺「依赖只许向下」纪律")
    if "TODO" in text or "待补" in text:
        issues.append("含 TODO/待补 占位")
    return issues


class LayersDocTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_layers_matches_contract(self):
        self.assertEqual([], layer_doc_issues(self.text), "抽象阶梯文档不满足契约")

    def test_truth_live(self):
        d = layers()
        self.assertEqual(["contract", "asset", "engine", "export"],
                         [t["id"] for t in d["tiers"]])
        self.assertEqual(5, len(d["asset_levels"]))
        self.assertEqual(4, len(d["surfaces"]))
        self.assertEqual(6, len(d["crosscut"]["components"]))
        self.assertEqual(10, len(d["rules"]))

    def test_contract_catches_mutations(self):
        """变异自证：缺阶名 / 纵切回退 / 缺规则数 / 生成区标记破坏 / 缺命令。"""
        no_tier = self.text.replace("引擎", "运行层")
        self.assertTrue(any("引擎" in i for i in layer_doc_issues(no_tier)))
        old_c = self.text.replace("**6**（verify", "**4**（verify")
        self.assertTrue(any("纵切件" in i for i in layer_doc_issues(old_c)))
        no_rule = self.text.replace("L1–L10（10 条）", "L1–L9")
        self.assertTrue(any("L1–L10" in i for i in layer_doc_issues(no_rule)))
        broken = self.text.replace(END, "")
        self.assertTrue(any("生成区标记" in i for i in layer_doc_issues(broken)))
        no_cmd = self.text.replace("python scripts/nf.py layers --verify", "体检")
        self.assertTrue(any("--verify" in i for i in layer_doc_issues(no_cmd)))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_layers.md")


if __name__ == "__main__":
    unittest.main()
