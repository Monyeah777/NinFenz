#!/usr/bin/env python3
"""docs/decision-layer.md 契约：决策层文档必须「三原语/适配器/候选/计数与真源一致」。

为什么必须有：决策层是「端口」而非模型本体——它的可信度来自声明真源与门禁纪律（只许 stub、
fail-closed、概率不是证书）。本轮修的三处陈旧计数（未定型字段 104→101、advisory 102→1142、
工单候选 206→1244）与一处适配器清单不全（漏 openai-json），都会让读者按错规模判断
「决策层能挑多少活」、也让「门禁只许 stub」失去上下文。本判据把三原语、三适配器（门禁标志）、
三候选（pulled）、三处计数、check33 面、20 例判据全部活绑定。

范围：只判本文与 decision_layer/backlog/advisory/workloop 事实自洽（不改协议）。
同族判据：test_decision_layer.py（20 例）/ test_decisions.py / test_workloop*.py /
test_doc_hygiene.py / test_doc_examples.py。
契约：最后更新位 + 复核、三原语、三适配器（含 openai-json 与 in_gate_path 语义）、三候选 pulled、
三处计数与真源相等、check33 在 verify.sh、20 例判据、现状对照 + 复现三命令。
"""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

DOC = ROOT / "docs" / "decision-layer.md"
DATA = ROOT / "protocol" / "decision_layer.json"
BACKLOG = ROOT / "protocol" / "type_backlog.json"
ADVISORY = ROOT / "protocol" / "pipeline_advisory.json"
VERIFY = ROOT / "verify.sh"
TEST = ROOT / "desktop" / "tests" / "test_decision_layer.py"
SECTIONS = ("## 是什么", "## 为什么", "## 怎么用", "## 候选模型", "## 判据（门禁",
            "## 边界（不宣称）", "## 构建回路", "## 现状对照", "## 复现与引用口径")
PRIMITIVES = ("choice", "noul", "score")
ADAPTERS = ("stub", "systemone-http", "openai-json")
CANDIDATES = ("laya-typed-decisions", "laya-multilingual", "open-jev-9b")


def load_text(path: Path = DOC) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"决策层文档不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("决策层文档为空")
    return text


def layer() -> dict:
    return json.loads(DATA.read_text(encoding="utf-8"))


def counts() -> dict:
    b = json.loads(BACKLOG.read_text(encoding="utf-8"))
    a = json.loads(ADVISORY.read_text(encoding="utf-8"))
    return {"backlog": int(b.get("count") or len(b.get("fields") or [])),
            "advisory": int(a.get("total") or len(a.get("items") or []))}


def decide_cases() -> int:
    return TEST.read_text(encoding="utf-8").count("def test")


def decision_issues(text: str) -> list:
    issues = []
    if not text.startswith("# 决策层（decide）"):
        issues.append("缺标题「# 决策层（decide）」")
    if "最后更新：" not in text:
        issues.append("缺「最后更新」位")
    if "复核" not in text:
        issues.append("缺「复核」说明")
    data = layer()
    prims = list((data.get("primitives") or {}).keys())
    if sorted(prims) != sorted(PRIMITIVES):
        issues.append(f"三原语已变：{prims}")
    for p in PRIMITIVES:
        if p not in text:
            issues.append(f"正文缺原语：{p}")
    ads = {a.get("id"): a for a in data.get("adapters") or []}
    if sorted(ads) != sorted(ADAPTERS):
        issues.append(f"适配器集合已变：{sorted(ads)}")
    if ads.get("stub", {}).get("in_gate_path") is not True:
        issues.append("stub 未标 in_gate_path=true")
    for name in ads:
        if name not in text:
            issues.append(f"正文缺适配器：{name}")
    if "openai-json" not in text:
        issues.append("缺 openai-json 适配器（remote-http）")
    if ads.get("openai-json", {}).get("in_gate_path") is not False:
        issues.append("openai-json 不应在门禁路径")
    cands = {c.get("id"): c for c in data.get("candidates") or []}
    if sorted(cands) != sorted(CANDIDATES):
        issues.append(f"候选模型集合已变：{sorted(cands)}")
    for cid, c in cands.items():
        if cid not in text:
            issues.append(f"正文缺候选：{cid}")
        if c.get("pulled") is True and "已拉取" not in text:
            issues.append(f"{cid} 已拉取但正文未写")
    cn = counts()
    if cn["backlog"] != 101:
        issues.append(f"未定型字段数已变（{cn['backlog']}）")
    if cn["advisory"] != 1142:
        issues.append(f"advisory 条数已变（{cn['advisory']}）")
    if "101" not in text or "1142" not in text:
        issues.append("正文缺现行计数（101 / 1142）")
    if "1244" not in text:
        issues.append("正文缺工单候选 1244")
    if "check33" not in VERIFY.read_text(encoding="utf-8"):
        issues.append("verify.sh 缺 check33")
    if "check33" not in text:
        issues.append("正文缺 check33 面")
    n_cases = decide_cases()
    if n_cases != 20:
        issues.append(f"test_decision_layer 例数已变（{n_cases}）")
    if str(n_cases) + " 例" not in text:
        issues.append(f"未写判据数（{n_cases} 例）")
    positions = [text.find(s) for s in SECTIONS]
    for section, pos in zip(SECTIONS, positions, strict=True):
        if pos < 0:
            issues.append(f"缺段：{section}")
    if all(p >= 0 for p in positions) and positions != sorted(positions):
        issues.append("节顺序不对")
    for cmd in ("python scripts/nf.py decide", "python scripts/nf.py workloop",
                "python -m pytest desktop/tests/test_decision_layer.py"):
        if cmd not in text:
            issues.append(f"复现口径缺命令：{cmd}")
    if "不生成正文" not in text:
        issues.append("缺「不生成正文」边界")
    if "TODO" in text or "待补" in text:
        issues.append("含 TODO/待补 占位")
    return issues


class DecisionLayerDocTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_decision_doc_matches_contract(self):
        self.assertEqual([], decision_issues(self.text), "决策层文档不满足契约")

    def test_data_live(self):
        data = layer()
        self.assertEqual(3, len(data["primitives"]))
        self.assertEqual(3, len(data["adapters"]))
        self.assertEqual(3, len(data["candidates"]))
        cn = counts()
        self.assertEqual(101, cn["backlog"])
        self.assertEqual(1142, cn["advisory"])
        self.assertEqual(20, decide_cases())

    def test_contract_catches_mutations(self):
        """变异自证：计数回退 / 缺 openai-json / 缺候选 / 缺 check33 / 缺命令。"""
        old = self.text.replace("1142", "102")
        self.assertTrue(any("1142" in i for i in decision_issues(old)))
        no_ad = self.text.replace("openai-json", "openai")
        self.assertTrue(any("openai-json" in i for i in decision_issues(no_ad)))
        no_c = self.text.replace("open-jev-9b", "jev")
        self.assertTrue(any("open-jev-9b" in i for i in decision_issues(no_c)))
        no_g = self.text.replace("check33", "check30")
        self.assertTrue(any("check33" in i for i in decision_issues(no_g)))
        no_cmd = self.text.replace("python scripts/nf.py workloop", "看工单")
        self.assertTrue(any("workloop" in i for i in decision_issues(no_cmd)))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_decision.md")


if __name__ == "__main__":
    unittest.main()
