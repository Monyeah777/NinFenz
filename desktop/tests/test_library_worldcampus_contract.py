#!/usr/bin/env python3
"""library/NF-WORLDCAMPUS 契约：社区投稿短篇包必须「元数据齐全 + 自包含 + 许可如实 + 回执新鲜」。

为什么必须有：这是馆藏里唯一的**社区投稿短篇**（Issue #2 来源、许可未声明、无上游模块可重嵌）。
它的风险面与装配样本不同：许可未声明但必须如实标注（不可默认 MIT），内容是外来数据（非指令），
且此前缺 verified/stale_after/attestation 三个信任面字段。本轮补齐信任面与「取件与核验」段，
并把「许可挂账语义」「数据非指令」「回执新鲜」立成机检断言。

范围：只判本条与其投影/回执/声明件的自洽（不改投稿正文）。同族判据：
test_library_nf1_contract.py（引用式样本）/ test_library_techdoc_contract.py（自包含样本）/
test_library_index_contract.py（目录与须知）/ check34（馆藏面）。
契约：frontmatter 十字段齐（rating 在词表、license 可「未声明」、verified/stale_after/attestation
在场且回执匹配）、正文头入库 == generated、来源 Issue 标注、许可挂账与数据非指令声明、
八段内容 + 取件核验段、INDEX 投影一致、无默认 MIT 暗示。
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

ENTRY = ROOT / "library" / "NF-WORLDCAMPUS-Monyeah777-1.md"
INTAKE = ROOT / "library" / "intake.json"
INDEX = ROOT / "library" / "INDEX.md"
SECTIONS = ("## 是什么", "## 怎么用", "## 世界基调", "## 核心物件",
            "## 情绪密码", "## 驱动规则", "## 示例切片", "## 取件与核验")
VERIFY_MARKERS = ("nf library attest", "nf library verify", "nf library reindex",
                  "check34", "digest_only", "stale_after", "未声明", "数据")
HEADER_MARKERS = ("自包含声明", "Issue #2", "版权归投稿人", "非执行指令")


def load_text(path: Path = ENTRY) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"NF-WORLDCAMPUS 不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("NF-WORLDCAMPUS 为空")
    return text


def frontmatter(text: str) -> dict:
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if not m:
        return {}
    data, current = {}, None
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


def index_row() -> list:
    text = INDEX.read_text(encoding="utf-8")
    for line in text.splitlines():
        if line.startswith("| NF-WORLDCAMPUS-Monyeah777-1 |"):
            return [c.strip() for c in line.strip("|").split("|")]
    return []


def worldcampus_issues(text: str) -> list:
    issues = []
    fm = frontmatter(text)
    if not fm:
        issues.append("缺 frontmatter")
        return issues
    if fm.get("id") != "NF-WORLDCAMPUS-Monyeah777-1":
        issues.append(f"id 不符：{fm.get('id')!r}")
    for key in ("type", "title", "description", "author", "rating", "license",
                "generated", "verified", "status", "stale_after", "sources",
                "attestation", "attested_at"):
        if not fm.get(key):
            issues.append(f"frontmatter 缺字段：{key}")
    vocab = ((json.loads(INTAKE.read_text(encoding="utf-8")).get("rating") or {})
             .get("vocabulary") or [])
    if fm.get("rating") not in vocab:
        issues.append(f"rating 越词表：{fm.get('rating')!r}")
    if str(fm.get("license") or "") != "未声明":
        issues.append(f"本条许可应为「未声明」（不可默认 MIT）：{fm.get('license')!r}")
    for key in ("generated", "verified", "stale_after", "attested_at"):
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", str(fm.get(key) or "")):
            issues.append(f"{key} 非 YYYY-MM-DD：{fm.get(key)!r}")
    if str(fm.get("stale_after") or "") <= str(fm.get("generated") or ""):
        issues.append("stale_after 应晚于 generated")
    if str(fm.get("verified") or "") < str(fm.get("generated") or ""):
        issues.append("verified 不应早于 generated")
    sources = fm.get("sources") or []
    if not isinstance(sources, list) or not sources:
        issues.append("sources 应为非空列表")
    else:
        for src in sources:
            raw = str(src)
            if raw.startswith("Issue #"):
                continue
            path = re.split(r"[（(]", raw, maxsplit=1)[0].strip()
            if not (ROOT / path).exists():
                issues.append(f"sources 不可解析（既非 Issue 也非仓库路径）：{src}")
    if not re.match(r"^[0-9a-f]{64}$", str(fm.get("attestation") or "")):
        issues.append("attestation 应为 64 位 hex")
    _issues, warns, _stats = lib.verify(str(ROOT))
    for warn in warns:
        if "NF-WORLDCAMPUS" in warn:
            issues.append(f"回执不新鲜：{warn}")
    if ("入库 " + str(fm.get("generated"))) not in text:
        issues.append("正文头入库日期应与 generated 一致：" + str(fm.get("generated")))
    for marker in HEADER_MARKERS:
        if marker not in text:
            issues.append(f"正文头缺要素：{marker}")
    for section in SECTIONS:
        if section not in text:
            issues.append(f"缺节：{section}")
    for marker in VERIFY_MARKERS:
        if marker not in text:
            issues.append(f"取件/核验面缺要素：{marker}")
    if "不超过 600 字" not in text:
        issues.append("缺场景字数约束（不超过 600 字）")
    row = index_row()
    if len(row) < 9:
        issues.append("INDEX 缺 NF-WORLDCAMPUS 投影行")
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


class LibraryWorldcampusContractTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_worldcampus_matches_contract(self):
        self.assertEqual([], worldcampus_issues(self.text), "library/NF-WORLDCAMPUS 不满足契约")

    def test_license_is_undeclared_not_defaulted(self):
        fm = frontmatter(self.text)
        self.assertEqual("未声明", fm.get("license"))
        self.assertEqual("未声明", index_row()[5])

    def test_attestation_is_fresh(self):
        _issues, warns, _stats = lib.verify(str(ROOT))
        self.assertEqual([], [w for w in warns if "NF-WORLDCAMPUS" in w])

    def test_contract_catches_mutations(self):
        """变异自证：缺 rating / 许可被默认 MIT / 缺取件段 / 日期漂移 / 缺数据非指令 / 回执缺失。"""
        no_rating = self.text.replace("rating: general\n", "", 1)
        self.assertTrue(any("rating" in i for i in worldcampus_issues(no_rating)))
        default_mit = self.text.replace("license: 未声明", "license: MIT", 1)
        self.assertTrue(any("许可" in i or "INDEX" in i for i in worldcampus_issues(default_mit)))
        no_s8 = self.text.replace("## 取件与核验（本条机检面）", "## 取件")
        self.assertTrue(any("缺节" in i for i in worldcampus_issues(no_s8)))
        bad_date = self.text.replace("入库 2026-09-07", "入库 2026-09-08")
        self.assertTrue(any("入库日期" in i for i in worldcampus_issues(bad_date)))
        no_data = self.text.replace("非执行指令", "可执行", 1)
        self.assertTrue(any("非执行指令" in i for i in worldcampus_issues(no_data)))
        no_att = re.sub(r"attestation: [0-9a-f]{64}\n", "", self.text, count=1)
        self.assertTrue(any("attestation" in i for i in worldcampus_issues(no_att)))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_worldcampus.md")


if __name__ == "__main__":
    unittest.main()
