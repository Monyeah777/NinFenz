#!/usr/bin/env python3
"""library/ALIAS 契约：转译表必须「生成器实时重算一致 + 小写键唯一 + 双镜像直链正确 + 标题列在场」。

为什么必须有：ALIAS 是 AI 拿不准编号大小写时的唯一转译层——它是**全量生成件**（手工改会被
reindex 覆盖），所以它的正确性只能由「文件 == render_alias(root)」保证。此前没有文档级判据：
小写键唯一（撞车即转译歧义）、真实编号都在册、GitHub/Gitee 双镜像链接逐字节正确、新增的
「标题」列（本轮生成器增强）与条目 frontmatter 一致。本轮把这些立成机检断言。

范围：只判 ALIAS 与其生成逻辑/馆藏条目的自洽（不改转译语义）。同族判据：
knowledge.verify_reuse（小写键唯一 + 在册，check37）/ library.check_projection（投影一致，check34）/
test_library*.py（工具链语义）/ library/INDEX 投影。
契约：文件 == render_alias、表头六列、行数 == 条目数、键小写且唯一且 == 真实编号小写、
真实编号在册、双镜像链接 == MIRRORS 前缀 + library/<id>.md、标题与 frontmatter 一致。
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "desktop" / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import library as lib  # noqa: E402

ALIAS = ROOT / "library" / "ALIAS.md"
COLUMNS = ["小写键", "真实编号", "状态", "GitHub raw 链接", "Gitee raw 链接", "标题"]
STATUSES = {"active", "deprecated", "superseded"}
HEADER_MARKERS = ("用法", "全小写化", "真实编号", "取件基底", "nf library reindex")


def load_text(path: Path = ALIAS) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"ALIAS 不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("ALIAS 为空")
    return text


def table(text: str) -> list:
    return [ln.strip() for ln in text.splitlines() if ln.strip().startswith("|")]


def data_rows(text: str) -> list:
    rows = []
    for line in table(text):
        cells = [c.strip() for c in line.strip("|").split("|")]
        if cells and cells[0] == "小写键":
            continue
        if all(set(c) <= {"-", ":"} or not c for c in cells):
            continue
        rows.append(cells)
    return rows


def alias_issues(text: str) -> list:
    issues = []
    if not text.startswith("# 📖 大小写转译表（ALIAS）"):
        issues.append("缺标题「# 📖 大小写转译表（ALIAS）」")
    for marker in HEADER_MARKERS:
        if marker not in text:
            issues.append(f"缺表头说明：{marker}")
    expected = lib.render_alias(str(ROOT))
    if text.rstrip("\n") != expected.rstrip("\n"):
        issues.append("ALIAS 与 render_alias 实时重算不一致（跑 nf library reindex）")
    rows = table(text)
    header = [c.strip() for c in rows[0].strip("|").split("|")] if rows else []
    if header != COLUMNS:
        issues.append(f"表头列不符：{header}")
    entries = lib.entries(str(ROOT))
    by_id = {str(e["id"]): e for e in entries}
    data = data_rows(text)
    if len(data) != len(entries):
        issues.append(f"行数应等于条目数：{len(data)} ≠ {len(entries)}")
    seen = set()
    reals = set()
    for cells in data:
        if len(cells) != len(COLUMNS):
            issues.append(f"行列数不符：{cells}")
            continue
        key, real, status, gh, gitee, title = cells
        if key != real.lower():
            issues.append(f"小写键与真实编号不匹配：{key} ≠ {real.lower()}")
        if key in seen:
            issues.append(f"小写键重复（转译歧义）：{key}")
        seen.add(key)
        reals.add(real)
        entry = by_id.get(real)
        if not entry:
            issues.append(f"真实编号不在册：{real}")
            continue
        if status not in STATUSES:
            issues.append(f"{real} 状态越词表：{status}")
        expected_status = str(entry["fm"].get("status") or "active")
        if status != expected_status:
            issues.append(f"{real} 状态与 frontmatter 不一致")
        if gh != lib.MIRRORS[0]["raw"] + "library/" + real + ".md":
            issues.append(f"{real} GitHub 链接不符")
        if gitee != lib.MIRRORS[1]["raw"] + "library/" + real + ".md":
            issues.append(f"{real} Gitee 链接不符")
        if title != str(entry["fm"].get("title") or real):
            issues.append(f"{real} 标题与 frontmatter 不一致")
    if set(by_id) != reals:
        issues.append(f"有在册条目缺转译行：{sorted(set(by_id) - reals)}")
    return issues


class AliasContractTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_alias_matches_contract(self):
        self.assertEqual([], alias_issues(self.text), "library/ALIAS 不满足契约")

    def test_alias_equals_render(self):
        self.assertEqual(lib.render_alias(str(ROOT)).rstrip("\n"), self.text.rstrip("\n"))

    def test_keys_are_unique_lowercase_and_resolvable(self):
        data = data_rows(self.text)
        keys = [cells[0] for cells in data]
        self.assertEqual(len(keys), len(set(keys)))
        ids = {str(e["id"]) for e in lib.entries(str(ROOT))}
        for cells in data:
            self.assertEqual(cells[1].lower(), cells[0])
            self.assertIn(cells[1], ids)

    def test_contract_catches_mutations(self):
        """变异自证：键大小写错 / 真实编号漂移 / 链接漂移 / 标题漂移 / 缺列 / 缺表头说明。"""
        bad_key = self.text.replace("| nf-1 | NF-1 |", "| NF-1 | NF-1 |", 1)
        self.assertTrue(any("小写键" in i for i in alias_issues(bad_key)))
        bad_id = self.text.replace("| NF-1 |", "| NF-9 |", 1)
        self.assertTrue(any("不在册" in i or "不一致" in i for i in alias_issues(bad_id)))
        good = "raw.githubusercontent.com/Monyeah777/NinFenz/main/library/NF-1.md"
        bad_link = self.text.replace(good, "raw.githubusercontent.com/other/repo/main/NF-1.md", 1)
        self.assertTrue(any("链接" in i for i in alias_issues(bad_link)))
        bad_title = self.text.replace("| 校园情感流（高二 · 毕业遗憾线） |", "| 情感流 |", 1)
        self.assertTrue(any("标题" in i for i in alias_issues(bad_title)))
        no_col = self.text.replace("| Gitee raw 链接 | 标题 |", "| Gitee raw 链接 |", 1)
        self.assertTrue(any("表头" in i for i in alias_issues(no_col)))
        no_header = self.text.replace("全小写化", "小写化")
        self.assertTrue(any("表头说明" in i for i in alias_issues(no_header)))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_alias.md")


if __name__ == "__main__":
    unittest.main()
