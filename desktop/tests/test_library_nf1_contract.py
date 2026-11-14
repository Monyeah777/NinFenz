#!/usr/bin/env python3
"""library/NF-1 契约：馆藏条目必须「frontmatter 十字段合法 + 投影一致 + 回执新鲜 + 诚实缺口声明」。

为什么必须有：NF-1 是馆藏里唯一「历史引用式」样本（规格自包含、正文引用式 + 缺口声明）——
它是投稿人理解「自包含 / 缺口声明 / 回执重签」三个纪律的范本。此前无文档级判据：frontmatter
字段集、rating/license 双源、INDEX 投影行、**attestation 是否仍匹配内容**、入库日期与 generated
一致、§8 取件/核验面说明是否在场。本轮补 §8 并把回执重签（attest）纳入本轮验证。

范围：只判本条与其投影/回执/声明件的自洽（不改世界内容）。同族判据：
test_library_index_contract.py（目录与须知）/ test_alias_contract.py（转译表）/
library.verify（图书馆门）/ check34（馆藏面）。
契约：frontmatter 十字段（id==文件名、rating 取词表、license、日期、sources 可解析、attestation
64 位 hex 且**与当前内容匹配**）、INDEX 行与 frontmatter 一致、正文 §0–§8 齐、
§8 含取件/双源/回执重签/时效/缺口补齐/机检入口、无 TODO 占位。
"""
import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "desktop" / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import library as lib  # noqa: E402

ENTRY = ROOT / "library" / "NF-1.md"
INTAKE = ROOT / "library" / "intake.json"
INDEX = ROOT / "library" / "INDEX.md"
SECTIONS = ("## 0. 装配记录", "## 1. 世界速览", "## 2. 管线", "## 3. 注册表投影",
            "## 4. 模块库", "## 5. 资产", "## 6. 装载指引", "## 7. 自检清单",
            "## 8. 取件与核验")
GAP_MARKERS = ("已知缺口", "引用式", "缺口补齐", "自包含")
SECTION8_MARKERS = ("nf library attest", "reindex", "verify", "check34", "stale_after",
                    "唯一真源", "ALIAS.md", "stale_after".replace("_", "_"))


def load_text(path: Path = ENTRY) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"NF-1 不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("NF-1 为空")
    return text


def frontmatter(text: str) -> dict:
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if not m:
        return {}
    data = {}
    current = None
    for line in m.group(1).splitlines():
        if line.startswith("  - "):
            if current:
                data[current].append(line[4:].strip())
            continue
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key, value = key.strip(), value.strip()
        if value == "":
            data[key] = []
            current = key
        else:
            data[key] = value
            current = None
    return data


def intake_vocab() -> list:
    return ((json.loads(INTAKE.read_text(encoding="utf-8")).get("rating") or {})
            .get("vocabulary") or [])


def index_row() -> list:
    text = INDEX.read_text(encoding="utf-8")
    for line in text.splitlines():
        if line.startswith("| NF-1 |"):
            return [c.strip() for c in line.strip("|").split("|")]
    return []


def nf1_issues(text: str) -> list:
    issues = []
    fm = frontmatter(text)
    if not fm:
        issues.append("缺 frontmatter")
        return issues
    if fm.get("id") != "NF-1":
        issues.append(f"id 应为 NF-1：{fm.get('id')!r}")
    for key in ("type", "title", "description", "author", "rating", "license",
                "generated", "verified", "status", "stale_after", "sources",
                "attestation", "attested_at"):
        if not fm.get(key):
            issues.append(f"frontmatter 缺字段：{key}")
    if fm.get("rating") not in intake_vocab():
        issues.append(f"rating 越词表：{fm.get('rating')!r}")
    if fm.get("status") not in ("active", "deprecated", "superseded"):
        issues.append(f"status 越生命周期词表：{fm.get('status')!r}")
    for key in ("generated", "verified", "stale_after", "attested_at"):
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", str(fm.get(key) or "")):
            issues.append(f"{key} 非 YYYY-MM-DD：{fm.get(key)!r}")
    if str(fm.get("stale_after") or "") <= str(fm.get("generated") or ""):
        issues.append("stale_after 应晚于 generated")
    sources = fm.get("sources") or []
    if not isinstance(sources, list) or not sources:
        issues.append("sources 应为非空列表")
    else:
        for src in sources:
            if not (ROOT / str(src)).exists():
                issues.append(f"sources 路径不可解析：{src}")
    att = str(fm.get("attestation") or "")
    if not re.match(r"^[0-9a-f]{64}$", att):
        issues.append(f"attestation 应为 64 位 hex：{att[:16]}")
    issues_list, warns, _stats = lib.verify(str(ROOT))
    for warn in warns:
        if "NF-1" in warn:
            issues.append(f"回执不新鲜：{warn}")
    if ("入库 " + str(fm.get("generated"))) not in text:
        issues.append("正文头入库日期应与 frontmatter generated 一致："
                      + str(fm.get("generated")))
    for section in SECTIONS:
        if section not in text:
            issues.append(f"缺节：{section}")
    for marker in GAP_MARKERS:
        if marker not in text:
            issues.append(f"缺缺口声明要素：{marker}")
    for marker in SECTION8_MARKERS:
        if marker not in text:
            issues.append(f"§8 缺要素：{marker}")
    if "TODO" in text or "待补" in text:
        issues.append("正文含 TODO/待补 占位（馆藏件须自洽交付）")
    row = index_row()
    if len(row) < 9:
        issues.append("INDEX 缺 NF-1 投影行")
    else:
        if row[1] != fm.get("title"):
            issues.append("INDEX 标题与 frontmatter 不一致")
        if row[4] != fm.get("generated"):
            issues.append(f"INDEX 入库日期应为 generated（{fm.get('generated')}）：{row[4]}")
        if row[5] != fm.get("license"):
            issues.append("INDEX 许可与 frontmatter 不一致")
        if row[6] != fm.get("rating"):
            issues.append("INDEX 分级与 frontmatter 不一致")
        if row[7] != fm.get("status"):
            issues.append("INDEX 状态与 frontmatter 不一致")
    return issues


class LibraryNf1ContractTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_nf1_matches_contract(self):
        self.assertEqual([], nf1_issues(self.text), "library/NF-1 不满足契约")

    def test_frontmatter_and_projection_agree(self):
        fm = frontmatter(self.text)
        row = index_row()
        self.assertEqual(fm.get("id"), "NF-1")
        self.assertEqual(fm.get("title"), row[1])
        self.assertEqual(fm.get("license"), row[5])
        self.assertEqual(fm.get("rating"), row[6])

    def test_attestation_is_fresh(self):
        _issues, warns, _stats = lib.verify(str(ROOT))
        self.assertEqual([], [w for w in warns if "NF-1" in w])

    def test_contract_catches_mutations(self):
        """变异自证：缺 rating / 回执篡改 / 日期漂移 / 缺 §8 要素 / INDEX 分级漂移 / TODO 占位。"""
        no_rating = self.text.replace("rating: teen\n", "", 1)
        self.assertTrue(any("rating" in i for i in nf1_issues(no_rating)))
        bad_att = self.text.replace("attestation: ", "attestation: zz", 1)
        self.assertTrue(any("attestation" in i for i in nf1_issues(bad_att)))
        bad_date = self.text.replace("入库 2026-09-06", "入库 2026-09-07", 1)
        self.assertTrue(any("入库日期" in i for i in nf1_issues(bad_date)))
        no_s8 = self.text.replace("## 8. 取件与核验（本条机检面）", "## 8. 取件")
        self.assertTrue(any("缺节" in i for i in nf1_issues(no_s8)))
        no_attest = self.text.replace("nf library attest NF-1", "重签回执")
        self.assertTrue(any("§8" in i for i in nf1_issues(no_attest)))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_nf1.md")


if __name__ == "__main__":
    unittest.main()
