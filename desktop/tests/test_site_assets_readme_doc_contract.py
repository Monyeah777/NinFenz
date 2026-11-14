#!/usr/bin/env python3
"""site/assets/README.md 契约：素材来源/许可/字节/尺寸必须与实盘一致。

为什么必须有：这是站点素材的**来源与许可声明**（公开面声明，法律与信任相关）。此前只有 4 行、
零判据：素材被替换、尺寸改了、许可从 MIT 变了，都不会被发现。
本轮补「§现状对照」「§复现与引用口径」，
并加判据：三件素材在盘且字节/尺寸与文中数字一致、无 webfont/CDN 声明仍在、生成器路径在场、
**并如实记录「入库 demo.gif 与当前生成器输出不一致」这一债**（不在判据里假装一致）。

范围：只判本页与 site/assets 实盘 + 生成器脚本一致（不改素材）。
同族判据：test_site_readme_doc_contract.py / test_deploy_cloudflare_doc_contract.py。
契约：复核位、三件素材逐件在盘、**og.png 尺寸 1136×790**、**demo.gif 尺寸 804×586**、
MIT 许可、无外部字体声明、生成器路径、复现三命令、**不一致债务在文**。
"""
import struct
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOC = ROOT / "site" / "assets" / "README.md"
ASSETS = ROOT / "site" / "assets"
GEN = ROOT / "site" / "tools" / "make-demo-gif.py"
FILES = ("og.png", "demo.gif", "site.css")


def load_text(path: Path = DOC) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"素材 README 不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("素材 README 为空")
    return text


def png_size(path: Path):
    data = path.read_bytes()
    if not data.startswith(b"\x89PNG"):
        return None
    return struct.unpack(">II", data[16:24])


def gif_size(path: Path):
    data = path.read_bytes()
    if not data.startswith(b"GIF"):
        return None
    return struct.unpack("<HH", data[6:10])


def doc_issues(text: str) -> list:
    issues = []
    if not text.startswith("# 站点素材（来源与许可）"):
        issues.append("缺标题「# 站点素材（来源与许可）」")
    if "复核（2026-11-14）" not in text:
        issues.append("缺复核位")
    for name in FILES:
        if not (ASSETS / name).is_file():
            issues.append(f"素材不在盘：{name}")
        if name not in text:
            issues.append(f"正文未列素材：{name}")
    og = ASSETS / "og.png"
    if og.is_file():
        size = png_size(og)
        if size != (1136, 790):
            issues.append(f"og.png 尺寸已变：{size}（文中写 1136×790）")
        if "1136×790" not in text:
            issues.append("正文未写 og.png 尺寸 1136×790")
    gif = ASSETS / "demo.gif"
    if gif.is_file():
        gsize = gif_size(gif)
        if gsize != (804, 586):
            issues.append(f"demo.gif 尺寸已变：{gsize}（文中写 804×586）")
        if "804×586" not in text:
            issues.append("正文未写 demo.gif 尺寸 804×586")
    if not GEN.is_file():
        issues.append("生成器 make-demo-gif.py 不在盘")
    if "make-demo-gif.py" not in text:
        issues.append("正文未写生成器路径")
    if "MIT" not in text:
        issues.append("缺 MIT 许可")
    if "webfont" not in text or "CDN" not in text:
        issues.append("缺「无 webfont / 无 CDN 字体」声明")
    for section in ("## 现状对照", "## 复现与引用口径"):
        if section not in text:
            issues.append(f"缺段落：{section}")
    if "字节不同" not in text:
        issues.append("缺「入库图与生成器输出字节不同」的债务登记")
    if "已登记的债" not in text:
        issues.append("未把不一致标成已登记的债")
    for cmd in ("python site/tools/make-demo-gif.py --out",
                "node site/tools/site-check.mjs --offline"):
        if cmd not in text:
            issues.append(f"复现口径缺命令：{cmd}")
    if "TODO" in text:
        issues.append("含 TODO 占位")
    return issues


class SiteAssetsReadmeTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_readme_matches_contract(self):
        self.assertEqual([], doc_issues(self.text), "素材 README 不满足契约")

    def test_asset_bytes_match_text(self):
        self.assertIn("82332 B", self.text)
        self.assertIn("34487 B", self.text)
        self.assertEqual(82332, (ASSETS / "og.png").stat().st_size)
        self.assertEqual(34487, (ASSETS / "demo.gif").stat().st_size)

    def test_contract_catches_mutations(self):
        """变异自证：缺素材 / 尺寸改错 / 缺许可 / 缺债务登记。"""
        no_og = self.text.replace("og.png", "preview.png")
        no_og = no_og.replace("`og:image`", "`preview`")
        self.assertTrue(any("og.png" in i for i in doc_issues(no_og)))
        bad_dim = self.text.replace("1136×790", "1200×630")
        self.assertTrue(any("1136×790" in i for i in doc_issues(bad_dim)))
        no_lic = self.text.replace("MIT", "保留所有权利")
        self.assertTrue(any("MIT" in i for i in doc_issues(no_lic)))
        no_debt = self.text.replace("字节不同", "字节一致").replace("已登记的债", "正常")
        self.assertTrue(any("字节不同" in i for i in doc_issues(no_debt)))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_assets_readme.md")


if __name__ == "__main__":
    unittest.main()
