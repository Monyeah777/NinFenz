#!/usr/bin/env python3
"""library/NF-TECHDOC 契约：自包含装配样本必须「内嵌逐字一致 + 回执新鲜 + 投影一致 + 缺口头声明」。

为什么必须有：这是馆藏里唯一的**内容自包含**装配样本（15 件模块正文 + P06 管线全文内嵌）。
它承诺「内嵌正文 = 源文件逐字节复制」，但上游模块会演进——2026-11-12 实测 13/15 段已与源漂移
（本系列前几轮升级了官方核心模块）。本轮用官方重嵌工具 scripts/rebuild_selfcontained_sample.py
重嵌（段 16 全部无漂移）、更新快照声明与 verified 日期、补 §8 取件/核验面、重签回执，并把
「内嵌无漂移」立成机检断言。

范围：只判本条与其内嵌源/投影/回执的自洽（不改装配内容）。同族判据：
test_library_nf1_contract.py（引用式样本）/ test_selfcontained_rebuild.py（重嵌工具单测）/
test_library_index_contract.py（目录）/ check34（馆藏面）。
契约：frontmatter 十字段（含 attestation 与内容匹配）、正文头入库 == generated、§0–§8 齐、
§8 含重嵌/回执/协议层缺口、内嵌段 = 15 模块 + 1 管线且逐字无漂移、P06 段 == 管线源文件、
§4 段数与清单一致、INDEX 投影一致。
"""
import importlib.util
import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "desktop" / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import library as lib  # noqa: E402

ENTRY = ROOT / "library" / "NF-TECHDOC-Monyeah777-1.md"
P06 = ROOT / "community" / "技术文档域包" / "pipelines" / "P06_技术文档题材装配流管线.md"
INTAKE = ROOT / "library" / "intake.json"
INDEX = ROOT / "library" / "INDEX.md"
SECTIONS = ("## 0. 装配记录", "## 1. 文档域速览", "## 2. 管线", "## 3. 注册表投影",
            "## 4. 模块库", "## 5. 资产", "## 6.", "## 7. 自检清单", "## 8. 取件与核验")
SECTION8_MARKERS = ("rebuild_selfcontained_sample", "nf library attest", "nf library reindex",
                    "check34", "无漂移", "stale_after", "协议层缺口", "digest_only")
GAP_MARKERS = ("缺口声明", "协议层不自足", "2026-11-12 仓库快照", "内嵌 15 件")


def _rebuild_module():
    spec = importlib.util.spec_from_file_location(
        "selfcontained_rebuild_for_contract",
        ROOT / "scripts" / "rebuild_selfcontained_sample.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_text(path: Path = ENTRY) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"NF-TECHDOC 不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("NF-TECHDOC 为空")
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
        if line.startswith("| NF-TECHDOC-Monyeah777-1 |"):
            return [c.strip() for c in line.strip("|").split("|")]
    return []


def embedded_stats(text: str) -> tuple:
    sc = _rebuild_module()
    lines = text.splitlines()
    new_lines, changes = sc.rebuild(lines, str(P06.relative_to(ROOT)), str(ROOT))
    modules = [c for c in changes if c["kind"] == "module"]
    pipes = [c for c in changes if c["kind"] == "pipeline"]
    return len(modules), len(pipes), new_lines == lines


def techdoc_issues(text: str) -> list:
    issues = []
    fm = frontmatter(text)
    if not fm:
        issues.append("缺 frontmatter")
        return issues
    if fm.get("id") != "NF-TECHDOC-Monyeah777-1":
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
            raw = re.split(r"[（(]", str(src), maxsplit=1)[0].strip()
            if not (ROOT / raw).exists():
                issues.append(f"sources 路径不可解析：{src}")
    if not re.match(r"^[0-9a-f]{64}$", str(fm.get("attestation") or "")):
        issues.append("attestation 应为 64 位 hex")
    _issues, warns, _stats = lib.verify(str(ROOT))
    for warn in warns:
        if "NF-TECHDOC" in warn:
            issues.append(f"回执不新鲜：{warn}")
    if ("入库 " + str(fm.get("generated"))) not in text:
        issues.append("正文头入库日期应与 generated 一致：" + str(fm.get("generated")))
    if ("verified " + str(fm.get("verified"))) not in text:
        issues.append("§8 时效声明的 verified 与 frontmatter 不一致："
                      + str(fm.get("verified")))
    for section in SECTIONS:
        if section not in text:
            issues.append(f"缺节：{section}")
    for marker in GAP_MARKERS:
        if marker not in text:
            issues.append(f"缺缺口/快照声明要素：{marker}")
    for marker in SECTION8_MARKERS:
        if marker not in text:
            issues.append(f"§8 缺要素：{marker}")
    modules, pipes, same = embedded_stats(text)
    if modules != 15:
        issues.append(f"内嵌模块段数应为 15（实测 {modules}）")
    if pipes != 1:
        issues.append(f"内嵌管线声明段数应为 1（实测 {pipes}）")
    if not same:
        issues.append("内嵌正文与源文件有漂移（跑 rebuild_selfcontained_sample --write 重嵌）")
    if "§4 内嵌段数 = 15" not in text:
        issues.append("§7 自检清单缺「§4 内嵌段数 = 15」")
    row = index_row()
    if len(row) < 9:
        issues.append("INDEX 缺 NF-TECHDOC 投影行")
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


class LibraryTechdocContractTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_techdoc_matches_contract(self):
        self.assertEqual([], techdoc_issues(self.text), "library/NF-TECHDOC 不满足契约")

    def test_embedded_copies_are_byte_identical(self):
        modules, pipes, same = embedded_stats(self.text)
        self.assertEqual(15, modules)
        self.assertEqual(1, pipes)
        self.assertTrue(same, "内嵌正文与源文件有漂移")

    def test_attestation_is_fresh(self):
        _issues, warns, _stats = lib.verify(str(ROOT))
        self.assertEqual([], [w for w in warns if "NF-TECHDOC" in w])

    def test_contract_catches_mutations(self):
        """变异自证：内嵌漂移 / 缺回执 / 日期漂移 / 缺 §8 要素 / 缺快照声明。"""
        drift = self.text.replace("## 1. 职责\n", "## 1. 职责\n\n（内嵌篡改）\n", 1)
        self.assertTrue(any("漂移" in i for i in techdoc_issues(drift)))
        no_att = re.sub(r"attestation: [0-9a-f]{64}\n", "", self.text, count=1)
        self.assertTrue(any("attestation" in i for i in techdoc_issues(no_att)))
        bad_date = self.text.replace("verified: 2026-11-12", "verified: 2026-09-15", 1)
        self.assertTrue(any("verified" in i for i in techdoc_issues(bad_date)))
        no_s8 = self.text.replace("## 8. 取件与核验（本条机检面）", "## 8. 取件")
        self.assertTrue(any("缺节" in i for i in techdoc_issues(no_s8)))
        no_snap = self.text.replace("2026-11-12 仓库快照", "历史快照", 1)
        self.assertTrue(any("快照" in i for i in techdoc_issues(no_snap)))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_techdoc.md")


if __name__ == "__main__":
    unittest.main()
