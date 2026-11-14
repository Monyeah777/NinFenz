#!/usr/bin/env python3
"""submissions 通用块契约：09（英文）/ 10（中文）的传输段逐字相同、字段块同义、JSON 可解析。

为什么必须有：09/10 是「任何未列出目录站」的兜底材料，读者直接整段粘。两份的**传输段**
（stdin JSON 配置 + 备用命令 + 同页字段）此前逐字相同却无判据；而中英字段块**同义不同文**，
最容易改一边忘另一边。本轮在 09 补「§自检」并加判据：传输段逐字相等、两份的 stdio 配置
JSON 都能解析且 args 正确、九项英文/九项中文字段齐全、平台侧未验、不钉计数、无邮箱。

范围：只判 09/10 两份与材料包/运行面事实自洽（不做网络请求）。
同族判据：test_short_form_submission_doc_contract.py（07/08 短表单族）。
契约：传输段逐字相等、两份 JSON args == [-y,ninfenz,serve]、字段名逐项、12+1 工具、
平台侧未验、不钉 check/PASS（无留痕词时）、无邮箱泄漏。
"""
import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "desktop" / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import mcp_runtime as mcp  # noqa: E402

SUB = ROOT / "packaging" / "mcp" / "submissions"
EN = SUB / "09-generic-en.md"
ZH = SUB / "10-generic-zh.md"
PIN = re.compile(r"check1-\d+|PASS=\d+")
TRACE = ("此前", "历史", "实测", "2026-", "漂移", "快照")
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
TRANSPORT = "## 传输配置（stdio）"
EN_FIELDS = ("Name:", "Tagline:", "Description:", "Install:", "Repo:",
             "Site:", "Category:", "Tags:", "License:")
ZH_FIELDS = ("名称：", "一句话：", "描述：", "安装：", "仓库：", "站点：",
             "类目：", "标签：", "许可：")


def load_text(path: Path) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"通用块不可读（{path.name}）：{exc}") from exc
    if not text.strip():
        raise ValueError(f"通用块为空（{path.name}）")
    return text


def transport_block(text: str) -> str:
    """传输段：从「## 传输配置」到下一个二级标题（含自检段）之前。"""
    if TRANSPORT not in text:
        return ""
    tail = text.split(TRANSPORT)[1]
    for stop in ("\n## 自检", "\n## 平台侧"):
        if stop in tail:
            tail = tail.split(stop)[0]
    clean = tail.strip()
    while clean.endswith("---"):
        clean = clean[:-3].rstrip()
    return clean


def json_args(text: str) -> list:
    cfg = text.split("```json")[1].split("```")[0]
    data = json.loads(cfg)
    return data.get("mcpServers", {}).get("ninfenz", {}).get("args")


def generic_issues(en: str, zh: str) -> list:
    issues = []
    if not en.startswith("# 09 · 通用块（英文）"):
        issues.append("09 缺标题「# 09 · 通用块（英文）」")
    if not zh.startswith("# 10 · 通用块（中文）"):
        issues.append("10 缺标题「# 10 · 通用块（中文）」")
    if "## 自检" not in en:
        issues.append("09 缺「§自检」段")
    if transport_block(en).strip() != transport_block(zh).strip():
        issues.append("09 与 10 的传输段不一致")
    for name, text in (("09", en), ("10", zh)):
        if TRANSPORT not in text:
            issues.append(f"{name} 缺传输段")
            continue
        try:
            args = json_args(text)
        except (IndexError, json.JSONDecodeError) as exc:
            issues.append(f"{name} 的 stdio JSON 不可解析：{exc}")
            continue
        if args != ["-y", "ninfenz", "serve"]:
            issues.append(f"{name} 的 stdio args 已变：{args}")
    for field in EN_FIELDS:
        if field not in en:
            issues.append(f"09 缺字段：{field}")
    for field in ZH_FIELDS:
        if field not in zh:
            issues.append(f"10 缺字段：{field}")
    if len(mcp.TOOL_DEFS) != 12 or len(mcp.PROMPT_DEFS) != 1:
        issues.append("工具面已变（应为 12 + 1）")
    for name, text in (("09", en), ("10", zh)):
        if "12 个只读工具 + 1 个 prompt" not in text and "12 read-only tools" not in text:
            issues.append(f"{name} 未写 12+1 工具面")
        # 自检段按文件逐步补齐：有自检段的件必须带平台侧/不钉计数口径
        if "## 自检" in text:
            if "平台侧未验" not in text:
                issues.append(f"{name} 缺平台侧未验")
            if "不钉运行时计数" not in text:
                issues.append(f"{name} 缺不钉计数口径")
        leaked = EMAIL.search(text)
        if leaked:
            issues.append(f"{name} 出现邮箱地址：{leaked.group(0)}")
        for line in text.splitlines():
            if PIN.search(line) and not any(w in line for w in TRACE):
                issues.append(f"{name} 钉运行时计数且无留痕词：{line.strip()[:30]}")
    return issues


class GenericBlocksTest(unittest.TestCase):
    def setUp(self):
        self.en = load_text(EN)
        self.zh = load_text(ZH)

    def test_generic_blocks_match_contract(self):
        self.assertEqual([], generic_issues(self.en, self.zh), "通用块不满足契约")

    def test_transport_and_args_live(self):
        self.assertEqual(transport_block(self.en).strip(),
                         transport_block(self.zh).strip())
        self.assertEqual(["-y", "ninfenz", "serve"], json_args(self.en))
        self.assertEqual(["-y", "ninfenz", "serve"], json_args(self.zh))

    def test_pair_cross_reference(self):
        """中英两份必须互指（各自点名对方文件名），否则读者不知道还有另一版。"""
        self.assertIn("10-generic-zh.md", self.en)
        self.assertIn("09-generic-en.md", self.zh)

    def test_contract_catches_mutations(self):
        """变异自证：传输段分叉 / args 改错 / 缺中文字段 / 缺平台标注。"""
        drift = self.zh.replace("Streamable HTTP 与 SSE 未提供", "也支持 HTTP")
        self.assertTrue(any("传输段" in i for i in generic_issues(self.en, drift)))
        bad = self.zh.replace("\"-y\", \"ninfenz\", \"serve\"", "\"-y\", \"ninfenz\"")
        self.assertTrue(any("args" in i for i in generic_issues(self.en, bad)))
        missing = self.zh.replace("许可：MIT", "证书 / MIT")
        self.assertTrue(any("许可：" in i for i in generic_issues(self.en, missing)))
        no_platform = self.en.replace("平台侧未验", "平台侧已验")
        self.assertTrue(any("平台侧" in i for i in generic_issues(no_platform, self.zh)))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_generic.md")


if __name__ == "__main__":
    unittest.main()
