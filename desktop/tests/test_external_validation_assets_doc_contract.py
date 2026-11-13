#!/usr/bin/env python3
"""E1 样本说明契约：体积/sha256/结构判定必须与盘上一致。

为什么必须有：这两件 JSON 是外部验证线 E1 的唯一 committed 样本——README 记的体积与 sha256 就是
「样本到底是什么」的唯一书面依据。本轮发现记录侧与盘上**已经不一致**：README/results 记
11,652 B / sha 528935dc…，盘上实为 **11,632 B / a91f402c…**（世界书一致）。若继续按旧记录引用，
外部复核者会拿错哈希对样本。本判据把两件样本的体积、sha256、CCv3 结构判定、P0 缺口与
「重出属作者触发」边界全部活绑定。

范围：只判本文与两件样本/export_schema 事实自洽（**只读**，绝不重写样本）。
同族判据：test_ccv3_adapter.py / test_interop_schemas*.py / test_doc_hygiene.py /
test_doc_examples.py。契约：最后更新位 + 现状对照、11,632 B 与 8,691 B、两个 sha256 前缀在文、
结构合法（data 块）、P0 仍 ✗ 且写明作者触发、只读复核三命令、「不重出/不覆盖」纪律。
"""
import hashlib
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "desktop" / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import export_schema as es  # noqa: E402

DIR = ROOT / "docs" / "external-validation-assets"
DOC = DIR / "README.md"
CHARA = DIR / "E1_ccv3_sample_lightmix_P04_chara.json"
WORLD = DIR / "E1_ccv3_sample_lightmix_P04_world.json"
SECTIONS = ("## 这是什么", "## 怎么重生成", "## 现状对照", "## 复核（只读、可执行）",
            "## 2026-09-21 · 结构性修正", "## 边界（不宣称）")


def load_text(path: Path = DOC) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"外部验证资产说明不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("外部验证资产说明为空")
    return text


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def assets() -> dict:
    return {"chara": CHARA, "world": WORLD}


def asset_issues(text: str) -> list:
    issues = []
    if not text.startswith("# 外部验证资产"):
        issues.append("缺标题「# 外部验证资产（E1 · CCV3 出口样本）」")
    if "最后更新：" not in text:
        issues.append("缺「最后更新」位")
    if "复核" not in text:
        issues.append("缺「复核」说明")
    a = assets()
    if not a["chara"].is_file() or not a["world"].is_file():
        issues.append("样本文件缺失")
        return issues
    n_chara = a["chara"].stat().st_size
    n_world = a["world"].stat().st_size
    if n_chara != 11632:
        issues.append(f"chara 体积已变（{n_chara}）")
    if n_world != 8691:
        issues.append(f"world 体积已变（{n_world}）")
    if "11,632 B" not in text or "8,691 B" not in text:
        issues.append("未写盘上体积 11,632 / 8,691")
    h_chara = sha256(a["chara"])
    h_world = sha256(a["world"])
    if h_chara[:8] not in text:
        issues.append(f"未写 chara sha 前缀：{h_chara[:8]}")
    if h_world[:8] not in text:
        issues.append(f"未写 world sha 前缀：{h_world[:8]}")
    if not h_chara.startswith("a91f402c"):
        issues.append(f"chara sha 已变：{h_chara[:16]}")
    issues_schema = es.check_ccv3_chara(str(a["chara"]))
    if issues_schema:
        issues.append(f"样本结构判定不合法：{issues_schema[:2]}")
    data = json.loads(a["chara"].read_text(encoding="utf-8"))
    if "data" not in data:
        issues.append("chara 缺 data 块")
    if "P0" not in text or "仍 ✗" not in text:
        issues.append("缺 P0 缺口与「仍 ✗」现状")
    if "作者显式触发" not in text and "作者触发" not in text:
        issues.append("缺「重出属作者触发」边界")
    if "不覆盖" not in text:
        issues.append("缺「不覆盖样本」纪律")
    positions = [text.find(s) for s in SECTIONS]
    for section, pos in zip(SECTIONS, positions, strict=True):
        if pos < 0:
            issues.append(f"缺段：{section}")
    if all(p >= 0 for p in positions) and positions != sorted(positions):
        issues.append("节顺序不对")
    for cmd in ("sha256sum docs/external-validation-assets",
                "ls -l docs/external-validation-assets",
                "check_ccv3_chara"):
        if cmd not in text:
            issues.append(f"复核口径缺要素：{cmd}")
    if "TODO" in text or "待补" in text:
        issues.append("含 TODO/待补 占位")
    return issues


class ExternalValidationAssetsTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_assets_readme_matches_contract(self):
        self.assertEqual([], asset_issues(self.text), "外部验证资产说明不满足契约")

    def test_assets_live(self):
        a = assets()
        self.assertEqual(11632, a["chara"].stat().st_size)
        self.assertEqual(8691, a["world"].stat().st_size)
        self.assertTrue(sha256(a["chara"]).startswith("a91f402c"))
        self.assertTrue(sha256(a["world"]).startswith("2499abe9"))
        self.assertEqual([], es.check_ccv3_chara(str(a["chara"])))
        self.assertIn("data", json.loads(a["chara"].read_text(encoding="utf-8")))

    def test_contract_catches_mutations(self):
        """变异自证：体积回退 / sha 回退 / P0 消失 / 缺只读命令 / 缺作者触发边界。"""
        old_n = self.text.replace("11,632 B", "11,652 B")
        self.assertTrue(any("11,632" in i for i in asset_issues(old_n)))
        old_h = self.text.replace("a91f402cdf59faaa", "528935dcf5be9caf")
        self.assertTrue(any("a91f402c" in i for i in asset_issues(old_h)))
        no_p0 = self.text.replace("仍 ✗", "已修")
        self.assertTrue(any("P0" in i or "仍 ✗" in i for i in asset_issues(no_p0)))
        no_cmd = self.text.replace("sha256sum docs/external-validation-assets", "算哈希")
        self.assertTrue(any("sha256sum" in i for i in asset_issues(no_cmd)))
        no_auth = self.text.replace("作者显式触发", "自动").replace("作者触发", "自动")
        self.assertTrue(any("作者" in i for i in asset_issues(no_auth)))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_assets.md")


if __name__ == "__main__":
    unittest.main()
