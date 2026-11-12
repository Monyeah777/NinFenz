#!/usr/bin/env python3
"""library/INDEX 契约：两段生成区必须等于实时重算，人读区（怎么读/投稿须知/怎么验/调用）
必须与 intake 声明件一致。

为什么必须有：INDEX 是本馆唯一的**公开入口**——AI 只拿 raw 链接就开始筛/取件。它有两段生成区
（mirror / 登记表）与四段人读区（怎么读 / 投稿须知 / 怎么验 / 调用方式）。生成区漂移会让目录与
真源不一致；人读区漂移（如日配额、分级口径、通道标签）会让投稿人按错误规则准备稿件。本轮补
「怎么读（三步取件）」与「怎么验（check34 判据面）」，并把两段生成区等价、投稿须知 ⇄ intake
三方一致立成机检断言。

范围：只判本文件与生成逻辑/声明件的自洽（不改馆藏语义）。同族判据：
test_alias_contract.py（ALIAS 投影）/ knowledge.verify_reuse（复用面）/ check34（图书馆面门禁）/
library.check_projection（INDEX 两段生成区）/ intake_surface（投稿面三方）。
契约：标记各一次且顺序正确、mirror/index 生成区 == render、人读区在标记外、投稿须知与
intake（通道标签/正文上限/分级词表/配额）逐项一致、登记表九列且行数 == 条目数。
"""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "desktop" / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import library as lib  # noqa: E402

INDEX = ROOT / "library" / "INDEX.md"
INTAKE = ROOT / "library" / "intake.json"
COLUMNS = ["编号", "标题", "形态/领域", "投稿人", "入库日期", "许可", "分级", "状态", "一句话"]
GUIDE_MARKERS = ("怎么读（三步取件）", "怎么验（本文件与馆藏的机检面）",
                 "投稿须知（入库前必读）", "调用方式", "消费纪律", "信任边界")


def load_text(path: Path = INDEX) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"library/INDEX 不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("library/INDEX 为空")
    return text


def intake() -> dict:
    return json.loads(INTAKE.read_text(encoding="utf-8"))


def region(text: str, begin: str, end: str) -> str:
    if begin not in text or end not in text:
        return ""
    return text[text.index(begin):text.index(end) + len(end)]


def data_rows(text: str) -> list:
    block = region(text, lib.BEGIN_INDEX, lib.END_INDEX)
    rows = []
    for line in block.splitlines():
        if not line.strip().startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if cells and cells[0] == COLUMNS[0]:
            continue
        if all(set(c) <= {"-", ":"} or not c for c in cells):
            continue
        rows.append(cells)
    return rows


def index_issues(text: str) -> list:
    issues = []
    if not text.startswith("# 📚 NF 云端图书馆 · 目录（INDEX）"):
        issues.append("缺标题「# 📚 NF 云端图书馆 · 目录（INDEX）」")
    for begin, end, renderer, label in (
            (lib.BEGIN_MIRROR, lib.END_MIRROR, lib.render_mirror_block(), "mirror"),
            (lib.BEGIN_INDEX, lib.END_INDEX, lib.render_index_block(str(ROOT)), "index")):
        if text.count(begin) != 1 or text.count(end) != 1:
            issues.append(f"{label} 生成区标记应各出现一次")
            continue
        current = region(text, begin, end)
        if current != renderer:
            issues.append(f"{label} 生成区与实时重算不一致（跑 nf library reindex）")
    if (lib.BEGIN_MIRROR in text and lib.BEGIN_INDEX in text
            and text.index(lib.BEGIN_MIRROR) > text.index(lib.BEGIN_INDEX)):
        issues.append("mirror 生成区应在 index 生成区之前")
    for marker in GUIDE_MARKERS:
        if marker not in text:
            issues.append(f"缺人读要素：{marker}")
    if (lib.BEGIN_MIRROR in text and "怎么读（三步取件）" in text
            and text.index("怎么读（三步取件）") > text.index(lib.BEGIN_MIRROR)):
        issues.append("「怎么读」应在 mirror 生成区之前（标记外）")
    if (lib.END_INDEX in text and "怎么验" in text
            and text.index("怎么验") < text.index(lib.END_INDEX)):
        issues.append("「怎么验」应在 index 生成区之后（标记外）")
    decl = intake()
    channels = decl.get("channels") or {}
    for name, channel in channels.items():
        label = str(channel.get("index_label") or "")
        if label and label not in text:
            issues.append(f"投稿须知缺通道 {name} 的 index_label：{label}")
    submission = decl.get("submission") or {}
    body_label = str(submission.get("body_limit_label") or "")
    if body_label and body_label not in text:
        issues.append(f"投稿须知缺正文上限标签：{body_label}")
    vocab = ((decl.get("rating") or {}).get("vocabulary") or [])
    for token in vocab:
        if token not in text:
            issues.append(f"投稿须知缺分级取值：{token}")
    quota = submission.get("quota") or {}
    per_author = quota.get("per_author_per_day")
    global_day = quota.get("global_per_day")
    if per_author and ("每作者每日 " + str(per_author) + " 篇") not in text:
        issues.append("投稿须知缺每作者日配额：" + str(per_author))
    if global_day and ("全仓每日 " + str(global_day) + " 篇") not in text:
        issues.append("投稿须知缺全仓日配额：" + str(global_day))
    if "SPDX" not in text:
        issues.append("投稿须知缺 SPDX 许可口径")
    if "36进制" not in text and "36 进制" not in text:
        issues.append("缺编号四级制/36 进制说明")
    rows = data_rows(text)
    entries = lib.entries(str(ROOT))
    if len(rows) != len(entries):
        issues.append(f"登记表行数应等于条目数：{len(rows)} ≠ {len(entries)}")
    block = region(text, lib.BEGIN_INDEX, lib.END_INDEX)
    header_words = [ln for ln in block.splitlines() if ln.strip().startswith("| 编号")][:1]
    if not header_words:
        issues.append("登记表缺表头")
    else:
        header = [c.strip() for c in header_words[0].strip("|").split("|")]
        if header != COLUMNS:
            issues.append(f"登记表列不符：{header}")
    return issues


class LibraryIndexContractTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_library_index_matches_contract(self):
        self.assertEqual([], index_issues(self.text), "library/INDEX 不满足契约")

    def test_generated_regions_equal_render(self):
        self.assertEqual(lib.render_mirror_block(), region(self.text, lib.BEGIN_MIRROR,
                                                          lib.END_MIRROR))
        self.assertEqual(lib.render_index_block(str(ROOT)),
                         region(self.text, lib.BEGIN_INDEX, lib.END_INDEX))

    def test_guide_matches_intake(self):
        decl = intake()
        for channel in (decl.get("channels") or {}).values():
            self.assertIn(str(channel.get("index_label")), self.text)
        self.assertIn(str(decl["submission"]["body_limit_label"]), self.text)
        for token in decl["rating"]["vocabulary"]:
            self.assertIn(token, self.text)
        self.assertIn(str(decl["submission"]["quota"]["per_author_per_day"]), self.text)
        self.assertIn(str(decl["submission"]["quota"]["global_per_day"]), self.text)

    def test_contract_catches_mutations(self):
        """变异自证：mirror 漂移 / 生成区缺失 / 人读区错位 / 日配额漂移 / 通道标签漂移。"""
        drift = self.text.replace("| github | raw（喂 AI · 主用） |",
                                  "| github | raw |", 1)
        self.assertTrue(any("mirror" in i for i in index_issues(drift)))
        no_mark = self.text.replace(lib.END_MIRROR, "", 1)
        self.assertTrue(any("mirror" in i for i in index_issues(no_mark)))
        misplaced = self.text.replace("## 怎么读（三步取件）", "", 1).replace(
            lib.BEGIN_MIRROR, lib.BEGIN_MIRROR + "\n## 怎么读（三步取件）", 1)
        self.assertTrue(any("怎么读" in i for i in index_issues(misplaced)))
        no_quota = self.text.replace("每作者每日 2 篇", "每作者每日 3 篇", 1)
        self.assertTrue(any("配额" in i for i in index_issues(no_quota)))
        no_label = self.text.replace("**投稿通道（仅作者本人自投）**",
                                     "**投稿通道**", 1)
        self.assertTrue(any("index_label" in i or "通道" in i for i in index_issues(no_label)))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_library_index.md")


if __name__ == "__main__":
    unittest.main()
