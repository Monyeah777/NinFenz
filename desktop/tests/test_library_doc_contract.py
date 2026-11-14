#!/usr/bin/env python3
"""docs/library.md 契约：图书馆机器面文档必须「条目数/分级/许可/词表与真源一致」。

为什么必须有：这页是「AI 凭编号取件」的唯一口径——条目数、状态、分级声明覆盖率、许可缺口、
分级词表、投影与门禁，任何一项漂移都会让取件人拿错件或误判「分级门是否覆盖全部藏品」。
本轮补可核现状（3 件全 active / 分级 3-of-3：teen 1+general 2 / 许可 MIT 2+未声明 1 /
词表 4 值 / verify 绿 WARN 0）与「§现状对照」「§复现与引用口径」。

范围：只判本文与 library 条目/INDEX/ALIAS/intake/CLI 事实自洽（不改馆藏）。
同族判据：test_library.py / test_library_index_contract.py / test_asset_library_readme_contract.py /
test_doc_hygiene.py / test_doc_examples.py。
契约：最后更新位 + 复核、3 件且全 active、分级词表 4 值逐值在文、许可 2+1、verify 绿口径、
投影不手改口径、现状对照 + 复现三命令。
"""
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

DOC = ROOT / "docs" / "library.md"
LIB = ROOT / "library"
INTAKE = LIB / "intake.json"
SECTIONS = ("## 是什么", "## 怎么用", "## 边界", "## 现状对照",
            "## 复现与引用口径", "## 内容分级")
MATURITIES = ("general", "teen", "mature", "unrated")


def load_text(path: Path = DOC) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"图书馆文档不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("图书馆文档为空")
    return text


def _field(head: str, name: str) -> str:
    m = re.search(r"^" + name + r":\s*(\S+)", head, re.M)
    return m.group(1) if m else ""


def entries() -> list:
    out = []
    for p in sorted(LIB.glob("NF-*.md")):
        text = p.read_text(encoding="utf-8")
        head = text.split("---")[1] if text.startswith("---") else ""
        out.append({"path": p, "rating": _field(head, "rating"),
                    "license": _field(head, "license"),
                    "status": _field(head, "status")})
    return out


def library_issues(text: str) -> list:
    issues = []
    if not text.startswith("# 云端图书馆机器面（library）"):
        issues.append("缺标题「# 云端图书馆机器面（library）」")
    if "最后更新：" not in text:
        issues.append("缺「最后更新」位")
    if "复核" not in text:
        issues.append("缺「复核」说明")
    ents = entries()
    if len(ents) != 3:
        issues.append(f"馆藏条目数已变（{len(ents)}）")
    if "**3 件**" not in text:
        issues.append("未写 3 件")
    statuses = {}
    ratings = {}
    lic = {}
    for e in ents:
        statuses[e["status"]] = statuses.get(e["status"], 0) + 1
        ratings[e["rating"]] = ratings.get(e["rating"], 0) + 1
        lic[e["license"]] = lic.get(e["license"], 0) + 1
    if statuses.get("active") != 3:
        issues.append(f"在役数已变：{statuses}")
    if ratings != {"teen": 1, "general": 2}:
        issues.append(f"分级分布已变：{ratings}")
    if "teen 1 / general 2" not in text:
        issues.append("未写分级 teen 1 / general 2")
    mit = lic.get("MIT", 0)
    if mit != 2:
        issues.append(f"MIT 许可数已变（{mit}）")
    if "MIT 2 / 未声明 1" not in text:
        issues.append("未写许可 MIT 2 / 未声明 1")
    intake = json.loads(INTAKE.read_text(encoding="utf-8"))
    vocab = list((intake.get("rating") or {}).get("vocabulary") or [])
    if tuple(vocab) != MATURITIES:
        issues.append(f"分级词表已变：{vocab}")
    for v in MATURITIES:
        if v not in text:
            issues.append(f"正文缺分级值：{v}")
    if "**4 值**" not in text:
        issues.append("未写词表 4 值")
    for marker in ("INDEX.md", "ALIAS.md", "library verify", "WARN 0"):
        if marker not in text:
            issues.append(f"现状/口径缺要素：{marker}")
    if "投影" not in text:
        issues.append("缺「INDEX/ALIAS 是投影」口径")
    if "手改" not in text:
        issues.append("缺「手改会被覆盖」口径")
    positions = [text.find(s) for s in SECTIONS]
    for section, pos in zip(SECTIONS, positions, strict=True):
        if pos < 0:
            issues.append(f"缺段：{section}")
    if all(p >= 0 for p in positions) and positions != sorted(positions):
        issues.append("节顺序不对")
    for cmd in ("python scripts/nf.py library ls",
                "python scripts/nf.py library verify",
                "python -m pytest desktop/tests/test_library.py"):
        if cmd not in text:
            issues.append(f"复现口径缺命令：{cmd}")
    if "library_search" not in text or "library_read" not in text:
        issues.append("缺 MCP 取用面（library_search / library_read）")
    if "TODO" in text or "待补" in text:
        issues.append("含 TODO/待补 占位")
    return issues


class LibraryDocTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_library_matches_contract(self):
        self.assertEqual([], library_issues(self.text), "图书馆文档不满足契约")

    def test_entries_live(self):
        ents = entries()
        self.assertEqual(3, len(ents))
        self.assertTrue(all(e["status"] == "active" for e in ents))
        self.assertEqual(1, sum(1 for e in ents if e["rating"] == "teen"))
        self.assertEqual(2, sum(1 for e in ents if e["rating"] == "general"))
        intake = json.loads(INTAKE.read_text(encoding="utf-8"))
        self.assertEqual(["general", "teen", "mature", "unrated"],
                         list(intake["rating"]["vocabulary"]))

    def test_contract_catches_mutations(self):
        """变异自证：条目数回退 / 分级回退 / 许可回退 / 缺词表值 / 缺命令。"""
        old = self.text.replace("**3 件**", "**4 件**")
        self.assertTrue(any("3 件" in i for i in library_issues(old)))
        bad = self.text.replace("teen 1 / general 2", "teen 2 / general 1")
        self.assertTrue(any("分级" in i for i in library_issues(bad)))
        no_lic = self.text.replace("MIT 2 / 未声明 1", "MIT 3")
        self.assertTrue(any("许可" in i for i in library_issues(no_lic)))
        no_v = self.text.replace("unrated", "unspecified")
        self.assertTrue(any("unrated" in i for i in library_issues(no_v)))
        no_cmd = self.text.replace("python scripts/nf.py library verify", "校验")
        self.assertTrue(any("library verify" in i for i in library_issues(no_cmd)))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_library.md")


if __name__ == "__main__":
    unittest.main()
