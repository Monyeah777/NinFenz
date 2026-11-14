#!/usr/bin/env python3
"""packaging/mcp/assets/README.md 契约：图标真实像素 / 替换流程 / 来源声明边界必须写清。

为什么必须有：这个目录只放两个图标（400 / 512），但它们是 Cline 审核的硬性材料——
「文件名叫 icon-400.png」不等于「像素是 400×400」；实测只能读 PNG 头（IHDR）确认。
此前 README 只写「变更图标请同时更新这两个尺寸」，
既没写像素实测方法，也没写「只换一个会分叉」的后果。
本轮补「§现状对照」「§复现与引用口径」，并明确「来源声明不可机检」这一诚实边界。

范围：只判本文与图标文件事实自洽（不判图像内容）。
同族判据：test_mcp_packaging.py / test_mcp_directories_doc_contract.py。
契约：来源/许可表在场、真实像素 400/512、字节数一致、替换流程含「两个一起」「记来源」、
「来源声明不可机检」诚实标注、复现命令可跑。
"""
import struct
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "packaging" / "mcp" / "assets"
DOC = BASE / "README.md"


def load_text(path: Path = DOC) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"图标素材 README 不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("图标素材 README 为空")
    return text


def size_of(name: str) -> tuple:
    data = (BASE / name).read_bytes()
    return struct.unpack(">II", data[16:24])


def assets_issues(text: str) -> list:
    issues = []
    if not text.startswith("# MCP 目录素材"):
        issues.append("缺标题「# MCP 目录素材（来源与许可）」")
    if "复核（2026-11-14）" not in text:
        issues.append("缺复核位")
    for section in ("## 现状对照", "## 复现与引用口径"):
        if section not in text:
            issues.append(f"缺段落：{section}")
    for name, px in (("icon-400.png", (400, 400)), ("icon-512.png", (512, 512))):
        if not (BASE / name).is_file():
            issues.append(f"图标不在场：{name}")
            continue
        if size_of(name) != px:
            issues.append(f"{name} 真实像素不是 {px[0]}x{px[1]}")
    if "**400×400**" not in text or "**512×512**" not in text:
        issues.append("现状表未写真实像素")
    for name in ("icon-400.png", "icon-512.png"):
        n = (BASE / name).stat().st_size
        if str(n) not in text:
            issues.append(f"现状表字节数与实际不符：{name}（当前 {n}）")
    if "MIT" not in text:
        issues.append("缺许可声明（MIT）")
    if "同时" not in text or "记来源" not in text:
        issues.append("缺替换流程（两个一起改 + 记来源）")
    if "不可机检" not in text:
        issues.append("缺「来源声明不可机检」诚实边界")
    if "分叉" not in text:
        issues.append("缺「只换一个会分叉」后果说明")
    if "struct.unpack" not in text:
        issues.append("缺像素实测命令")
    # 依赖面：test_mcp_packaging 需要本机 payload 暂存（gitignored 构建产物）。CI 的通用单测分片
    # 不跑 npm-package-check，payload 不在场 ⇒ 子进程必红。这里按「依赖前置缺失」跳过子判据，
    # 只保留本页自身可核项（不把环境缺失误判成 README 缺陷）。
    manifest = ROOT / "packaging" / "npm" / "payload" / "payload-manifest.json"
    if manifest.is_file():
        proc = subprocess.run([sys.executable, "-m", "pytest",
                               "desktop/tests/test_mcp_packaging.py", "-q"],
                              cwd=str(ROOT), capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=300, check=False)
        if proc.returncode != 0:
            issues.append("test_mcp_packaging 未通过（图标位判据）")
    if "TODO" in text:
        issues.append("含 TODO 占位")
    return issues


class McpAssetsReadmeTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_assets_readme_matches_contract(self):
        self.assertEqual([], assets_issues(self.text), "图标素材 README 不满足契约")

    def test_icon_sizes_live(self):
        self.assertEqual((400, 400), size_of("icon-400.png"))
        self.assertEqual((512, 512), size_of("icon-512.png"))

    def test_contract_catches_mutations(self):
        """变异自证：像素写错 / 字节数漂移 / 缺诚实边界 / 缺替换流程。"""
        bad = self.text.replace("**400×400**", "**400×300**")
        self.assertTrue(any("400x400" in i or "像素" in i for i in assets_issues(bad)))
        n512 = str((BASE / "icon-512.png").stat().st_size)
        off = self.text.replace(n512, "1", 1)
        self.assertTrue(any("字节数" in i for i in assets_issues(off)))
        no_edge = self.text.replace("不可机检", "可机检")
        self.assertTrue(any("不可机检" in i for i in assets_issues(no_edge)))
        no_flow = self.text.replace("同时", "依次")
        self.assertTrue(any("替换流程" in i for i in assets_issues(no_flow)))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_assets_readme.md")


if __name__ == "__main__":
    unittest.main()
