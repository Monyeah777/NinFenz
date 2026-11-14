#!/usr/bin/env python3
"""docs/ccos/threat-model.md 契约：A1–A9/G1–G6 齐 + 载体面与 G4 自洽 + 不承诺不矛盾。

为什么必须有：这份文件是「能证明什么、不能证明什么」的边界声明——它的价值全在**自洽**。本轮修的两处
真实缺陷正是「同页自相矛盾」：性质表写「无水印/其它格式无载体写入」、文末写「不做水印」，而 G4 明确
「PNG LSB 水印已实装、五格式载体已实装」。矛盾会让外部读者既高估（以为有抗转码水印）
又低估（以为载体没做）。本判据把 A1–A9、G1–G6、载体面表述、不承诺清单、三条复核命令全部活绑定。

范围：只判本文与 label/evidence/TSA 实现事实自洽（不改承诺面）。同族判据：
test_evidence.py（66 例，含攻击矩阵）/ test_label_carrier.py（33 例）/ test_timestamp.py /
test_doc_hygiene.py / test_doc_examples.py。
契约：最后更新位 + 复核、A1–A9 与 G1–G6 全在、载体面含五格式 + PNG LSB、不承诺清单不再「不做水印」、
「可剥离」边界在文、复核三命令。
"""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

DOC = ROOT / "docs" / "ccos" / "threat-model.md"
CARRIER = ROOT / "desktop" / "src" / "core" / "label_carrier.py"
WATERMARK = ROOT / "desktop" / "src" / "core" / "label_watermark.py"
SECTIONS = ("## 为什么要写这一节", "## 信任根与本机边界", "## 攻击者模型",
            "## 逐条性质", "## 已知缺口", "## 现状对照", "## 复核（可执行的攻击矩阵）",
            "## 不承诺")


def load_text(path: Path = DOC) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"威胁模型不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("威胁模型为空")
    return text


def threat_issues(text: str) -> list:
    issues = []
    if not text.startswith("# CCOS 威胁模型 v0"):
        issues.append("缺标题「# CCOS 威胁模型 v0（能证明什么、不能证明什么）」")
    if "最后更新：" not in text:
        issues.append("缺「最后更新」位")
    if "复核" not in text:
        issues.append("缺「复核」说明")
    for n in range(1, 10):
        if ("A" + str(n)) not in text:
            issues.append(f"缺攻击者能力：A{n}")
    for n in range(1, 7):
        if ("G" + str(n)) not in text:
            issues.append(f"缺缺口：G{n}")
    for fmt in ("PNG", "JPEG", "WebP", "MP4", "PDF"):
        if fmt not in text:
            issues.append(f"载体面缺格式：{fmt}")
    if "LSB" not in text and "像素水印" not in text:
        issues.append("缺 PNG 像素水印口径")
    if "可剥离" not in text:
        issues.append("缺「载体可剥离」边界")
    bad = [ln for ln in text.splitlines()
           if "不做水印" in ln and "原写" not in ln]
    if bad:
        issues.append("不承诺清单仍写「不做水印」（与 G4 矛盾）")
    bad2 = [ln for ln in text.splitlines()
            if "无水印" in ln and "原写" not in ln]
    if bad2:
        issues.append("性质表仍写「无水印」（与 G4 矛盾）")
    for marker in ("抗截屏", "抗转贴", "fail-closed"):
        if marker not in text:
            issues.append(f"边界缺要素：{marker}")
    if not CARRIER.is_file() or not WATERMARK.is_file():
        issues.append("缺实现件（label_carrier / label_watermark）")
    positions = [text.find(s) for s in SECTIONS]
    for section, pos in zip(SECTIONS, positions, strict=True):
        if pos < 0:
            issues.append(f"缺段：{section}")
    if all(p >= 0 for p in positions) and positions != sorted(positions):
        issues.append("节顺序不对")
    for cmd in ("python scripts/nf.py evidence bench",
                "python -m unittest desktop.tests.test_evidence",
                "python scripts/release_conclusion.py --dry-run"):
        if cmd not in text:
            issues.append(f"复核命令缺：{cmd}")
    if "TODO" in text or "待补" in text:
        issues.append("含 TODO/待补 占位")
    return issues


class ThreatModelDocTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_threat_model_matches_contract(self):
        self.assertEqual([], threat_issues(self.text), "威胁模型不满足契约")

    def test_implementation_faces_live(self):
        self.assertTrue(CARRIER.is_file())
        self.assertTrue(WATERMARK.is_file())
        carrier = CARRIER.read_text(encoding="utf-8")
        for fmt in ("webp", "mp4", "pdf"):
            self.assertIn("_" + fmt, carrier)

    def test_contract_catches_mutations(self):
        """变异自证：回退「不做水印」/ 回退「无水印」/ 缺 A9 / 缺 G6 / 缺复核命令。"""
        back1 = self.text + "\n不做 DRM、不做水印、不做内容审核。\n"
        self.assertTrue(any("不做水印" in i for i in threat_issues(back1)))
        back2 = self.text + "\nPNG iTXt 只写可见文本段，无水印/无抗转码。\n"
        self.assertTrue(any("无水印" in i for i in threat_issues(back2)))
        no_a9 = self.text.replace("A9", "A8")
        self.assertTrue(any("A9" in i for i in threat_issues(no_a9)))
        no_g6 = self.text.replace("G6", "G5")
        self.assertTrue(any("G6" in i for i in threat_issues(no_g6)))
        no_cmd = self.text.replace("python scripts/nf.py evidence bench", "跑基准")
        self.assertTrue(any("evidence bench" in i for i in threat_issues(no_cmd)))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_threat.md")


if __name__ == "__main__":
    unittest.main()
