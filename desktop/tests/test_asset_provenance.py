#!/usr/bin/env python3
"""素材来源与许可覆盖（审计 Z6：4 素材无来源的收口判据）。

口径：**图片资产**必须在其所在目录的 assets/README.md 里逐件登记「来源 + 许可」；
反向也判——README 里登记的件必须真实在场（不得挂空条目）。纯文本解析（无图像库依赖）。
"""
import re
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
#: 需要来源登记的素材目录（相对仓库根）；每目录旁必须有同为 assets 的 README.md。
ASSET_DIRS = ("site/assets", "packaging/mcp/assets")
IMAGE_SUFFIXES = (".png", ".gif", ".jpg", ".jpeg", ".svg", ".webp", ".ico")


def _rows(readme_text: str) -> list:
    """→ 登记表里出现的文件名（只认含图片后缀的 token）。"""
    names = []
    for line in readme_text.split(chr(10)):
        if not line.strip().startswith("|"):
            continue
        for tok in re.findall(r"[A-Za-z0-9._-]+\.[A-Za-z0-9]+", line):
            if tok.lower().endswith(IMAGE_SUFFIXES):
                names.append(tok)
    return names


def provenance_gaps(base: Path = ROOT) -> dict:
    """→ {"unlisted": [...], "dangling": [...], "missing_readme": [...]}（纯函数）。"""
    out = {"unlisted": [], "dangling": [], "missing_readme": []}
    for rel in ASSET_DIRS:
        d = base / rel
        if not d.is_dir():
            continue
        readme = d / "README.md"
        if not readme.is_file():
            out["missing_readme"].append(rel)
            continue
        text = readme.read_text(encoding="utf-8", errors="replace")
        listed = set(_rows(text))
        present = {p.name for p in d.iterdir()
                   if p.is_file() and p.suffix.lower() in IMAGE_SUFFIXES}
        for name in sorted(present - listed):
            out["unlisted"].append("%s/%s" % (rel, name))
        for name in sorted(listed - present):
            out["dangling"].append("%s/%s（README 登记了但件不在场）" % (rel, name))
    return out


class AssetProvenanceTest(unittest.TestCase):
    def test_every_image_is_listed_with_source_and_license(self):
        gaps = provenance_gaps()
        self.assertEqual([], gaps["missing_readme"], "素材目录缺 README.md（Z6）")
        self.assertEqual([], gaps["unlisted"], "素材未登记来源/许可（Z6）：%s" % gaps["unlisted"])
        self.assertEqual([], gaps["dangling"], "README 登记了不在场的件：%s" % gaps["dangling"])

    def test_readme_rows_carry_a_license_column(self):
        for rel in ASSET_DIRS:
            readme = ROOT / rel / "README.md"
            if not readme.is_file():
                continue
            text = readme.read_text(encoding="utf-8")
            head = next((ln for ln in text.split(chr(10)) if ln.strip().startswith("|")), "")
            self.assertIn("许可",
 head,
 "%s 登记表缺「许可」列（修复指引：来源与许可两列都要）" % rel)

    def test_mutation_is_caught(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp) / "site" / "assets"
            d.mkdir(parents=True)
            (d / "new.png").write_bytes(b"x")
            (d / "README.md").write_text("# 素材" + chr(10)
                                         + "| 文件 | 来源 | 许可 |" + chr(10)
                                         + "|---|---|---|" + chr(10)
                                         + "| other.png | x | MIT |" + chr(10), encoding="utf-8")
            gaps = provenance_gaps(Path(tmp))
        self.assertIn("site/assets/new.png", gaps["unlisted"])
        self.assertTrue(any("other.png" in x for x in gaps["dangling"]))


if __name__ == "__main__":
    unittest.main()
