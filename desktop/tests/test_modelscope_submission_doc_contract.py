#!/usr/bin/env python3
"""submissions/06-modelscope.md 契约：中文表单字段同源 / 仅 stdio / 平台侧不冒充判据。

为什么必须有：这是中文站表单件，结构比英文件复杂（含 stdio 传输配置、备用命令、同页字段），
最容易出两类错：① 表单里多填一个未支持的传输（HTTP/SSE）= 虚假声明；② 中文措辞与材料包
同源但无人比对（改材料包时只改英文件）。本轮补「§字段自检」并加判据，
把字段值、「仅 stdio」与中文口径钉住。

范围：只判本件与材料包/运行面/图标事实自洽（不做网络请求）。
同族判据：test_pulsemcp_submission_doc_contract.py / test_mcp_submissions_doc_contract.py。
契约：八字段逐项、12+1 工具、仅 stdio、图标真 400x400、MIT、平台侧未验、
不钉 check/PASS（无留痕词时）、正文不得出现邮箱、stdio 配置 args 正确。
"""
import json
import re
import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "desktop" / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import mcp_runtime as mcp  # noqa: E402

DOC = ROOT / "packaging" / "mcp" / "submissions" / "06-modelscope.md"
ICON = ROOT / "packaging" / "mcp" / "assets" / "icon-400.png"
SHARED = {
    "name": "NinFenz Content Gate",
    "repo": "https://github.com/Monyeah777/NinFenz",
    "site": "https://ninfenz.dev/",
    "install": "npx -y ninfenz serve",
}
PIN = re.compile(r"check1-\d+|PASS=\d+")
TRACE = ("此前", "历史", "实测", "2026-", "漂移", "快照")
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


def load_text(path: Path = DOC) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"ModelScope 提交件不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("ModelScope 提交件为空")
    return text


def modelscope_issues(text: str) -> list:
    issues = []
    if not text.startswith("# 06 · 魔搭 ModelScope"):
        issues.append("缺标题「# 06 · 魔搭 ModelScope」")
    if "## 字段自检" not in text:
        issues.append("缺「§字段自检」段")
    for key, val in SHARED.items():
        if val not in text:
            issues.append(f"缺共享值 {key}：{val}")
    if len(mcp.TOOL_DEFS) != 12 or len(mcp.PROMPT_DEFS) != 1:
        issues.append("工具面已变（应为 12 + 1）")
    if "12 个只读工具 + 1 个 prompt" not in text:
        issues.append("正文未写 12+1 工具面")
    if struct.unpack(">II", ICON.read_bytes()[16:24]) != (400, 400):
        issues.append("icon-400.png 真实像素不是 400x400")
    if "**真实 400×400**" not in text:
        issues.append("自检段未写真实 400x400")
    if "仅 stdio" not in text:
        issues.append("缺「仅 stdio」声明")
    if "Streamable HTTP" not in text or "SSE" not in text:
        issues.append("未点明未提供的两种传输")
    if "MIT" not in text:
        issues.append("缺许可 MIT")
    if "平台侧未验" not in text:
        issues.append("缺平台侧未验")
    if "同义不同文" not in text:
        issues.append("缺「中文口径同义不同文」提醒")
    leaked = EMAIL.search(text)
    if leaked:
        issues.append(f"正文出现邮箱地址：{leaked.group(0)}")
    for line in text.splitlines():
        if PIN.search(line) and not any(w in line for w in TRACE):
            issues.append(f"钉运行时计数且无留痕词：{line.strip()[:40]}")
    if "不钉运行时计数" not in text:
        issues.append("缺「不钉运行时计数」口径")
    try:
        cfg = text.split("```json")[1].split("```")[0]
        data = json.loads(cfg)
    except (IndexError, json.JSONDecodeError) as exc:
        issues.append(f"stdio 配置块不是合法 JSON：{exc}")
        data = {}
    args = data.get("mcpServers", {}).get("ninfenz", {}).get("args")
    if args != ["-y", "ninfenz", "serve"]:
        issues.append(f"stdio 配置 args 已变：{args}")
    if "TODO" in text:
        issues.append("含 TODO 占位")
    return issues


class ModelScopeSubmissionTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_modelscope_matches_contract(self):
        self.assertEqual([], modelscope_issues(self.text), "ModelScope 提交件不满足契约")

    def test_transport_config_live(self):
        cfg = self.text.split("```json")[1].split("```")[0]
        data = json.loads(cfg)
        self.assertEqual(["-y", "ninfenz", "serve"],
                         data["mcpServers"]["ninfenz"]["args"])

    def test_contract_catches_mutations(self):
        """变异自证：缺仅 stdio / 配置 args 改错 / 邮箱泄漏 / 残留钉数。"""
        no_stdio = self.text.replace("仅 stdio", "stdio 与 HTTP")
        self.assertTrue(any("仅 stdio" in i for i in modelscope_issues(no_stdio)))
        bad_args = self.text.replace('"-y", "ninfenz", "serve"', '"-y", "ninfenz"')
        self.assertTrue(any("args" in i for i in modelscope_issues(bad_args)))
        leak = self.text + "\n- 联系人：ops@example.com\n"
        self.assertTrue(any("邮箱地址" in i for i in modelscope_issues(leak)))
        pinned = self.text + "\n- check1-42 · PASS=76\n"
        self.assertTrue(any("钉运行时计数" in i for i in modelscope_issues(pinned)))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_modelscope.md")


if __name__ == "__main__":
    unittest.main()
