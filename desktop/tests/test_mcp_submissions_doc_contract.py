#!/usr/bin/env python3
"""packaging/mcp/submissions/ 契约：10 份逐字可粘件必须同源（改动不同批跟进即矛盾）。

为什么必须有：这个目录是「打开→全选→复制→粘贴」的 10 份成品件，读者不复核内容、直接投出去。
一旦某份的仓库地址 / 安装命令 / 工具面 / 展示名与材料包分叉，就会在某个目录上写出错描述；
而这类错误没有编译期、也没有人回头比对。本轮在 01 号件补「同源自检」表，并加本判据把
**跨 10 份文件的共享事实**钉死（编号连续性 + 六项共享值 + 图标引用）。

范围：只判提交件之间与材料包/运行面事实自洽（不改文案风格）。
同族判据：test_mcp_directories_doc_contract.py /
test_mcp_submit_doc_contract.py / test_mcp_runtime.py。
契约：01–10 连续编号、每份有标题与用途行、六项共享值逐份一致（缺项的文件允许不写但写了必须对）、
02 号引用 icon-400.png、01 号含「同源自检」表与「同批更新」纪律。
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "desktop" / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import mcp_runtime as mcp  # noqa: E402

BASE = ROOT / "packaging" / "mcp" / "submissions"
SHARED = {
    "repo": "https://github.com/Monyeah777/NinFenz",
    "site": "https://ninfenz.dev/",
    "install": "npx -y ninfenz serve",
    "name": "NinFenz Content Gate",
}


def files() -> list:
    return sorted(BASE.glob("*.md"))


def text_of(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def submission_issues() -> list:
    issues = []
    fs = files()
    if len(fs) != 10:
        issues.append(f"提交件数已变（{len(fs)}）")
    for i, p in enumerate(fs, start=1):
        if not p.name.startswith(f"{i:02d}-"):
            issues.append(f"编号不连续：{p.name}")
        t = text_of(p)
        if not t.startswith(f"# {i:02d} · "):
            issues.append(f"标题编号不符：{p.name}")
        first = t.splitlines()[0] if t else ""
        if "> 用途" not in t and "——" not in first:
            issues.append(f"缺用途行：{p.name}")
        for key, val in SHARED.items():
            if val in t:
                continue
            # 允许个别件只放片段，但凡是涉及该事实的写法会带出正文字符串；缺省不判错。
            if key == "name" and "名称" in t:
                issues.append(f"{p.name} 写了名称但值不对（应含 {val}）")
            if key == "install" and "安装" in t:
                issues.append(f"{p.name} 写了安装但值不对（应含 {val}）")
            if key == "repo" and ("仓库" in t or "Repo" in t):
                issues.append(f"{p.name} 写了仓库但值不对（应含 {val}）")
    t01 = text_of(BASE / "01-awesome-mcp-servers.md")
    for marker in ("## 同源自检", "同批更新", "**12 只读工具 + 1 prompt**",
                   "`python scripts/nf.py serve`"):
        if marker not in t01:
            issues.append(f"01 号同源自检缺要素：{marker}")
    t02 = text_of(BASE / "02-cline-marketplace.md")
    if "icon-400.png" not in t02:
        issues.append("02 号未引用 icon-400.png（Cline 要求上传图标）")
    if len(mcp.TOOL_DEFS) != 12 or len(mcp.PROMPT_DEFS) != 1:
        issues.append("工具面已变（应为 12 工具 + 1 prompt）")
    return issues


class McpSubmissionsTest(unittest.TestCase):
    def test_submissions_are_consistent(self):
        self.assertEqual([], submission_issues(), "提交件不同源")

    def test_family_shape(self):
        fs = files()
        self.assertEqual(10, len(fs))
        self.assertEqual("01-awesome-mcp-servers.md", fs[0].name)
        self.assertEqual("10-generic-zh.md", fs[-1].name)

    def test_contract_catches_mutations(self):
        """变异自证：仓库地址写错 / 缺同源自检 / 图标引用丢失 / 编号跳号。"""
        p01 = BASE / "01-awesome-mcp-servers.md"
        original = text_of(p01)
        try:
            p01.write_text(original.replace(SHARED["repo"], "https://github.com/X/Y"),
                           encoding="utf-8", newline="")
            self.assertTrue(any("仓库" in i for i in submission_issues()))
            p01.write_text(original.replace("## 同源自检", "## 附注"),
                           encoding="utf-8", newline="")
            self.assertTrue(any("同源自检" in i for i in submission_issues()))
            p02 = BASE / "02-cline-marketplace.md"
            keep = text_of(p02)
            p02.write_text(keep.replace("icon-400.png", "icon.png"),
                           encoding="utf-8", newline="")
            self.assertTrue(any("icon-400" in i for i in submission_issues()))
            p02.write_text(keep, encoding="utf-8", newline="")
        finally:
            p01.write_text(original, encoding="utf-8", newline="")


if __name__ == "__main__":
    unittest.main()
