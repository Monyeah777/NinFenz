#!/usr/bin/env python3
"""submissions/05-pulsemcp.md 契约：字段同源 / 邮箱纪律 / Cloudflare 提示 / 平台侧不冒充判据。

为什么必须有：PulseMCP 表单件与 mcp.so 类似，但多两条本渠道特有风险：① 表单可能要邮箱，
而提交内容里出现真实邮箱/密码是绝不能犯的错；② 该站 Cloudflare 拦脚本，用 curl 探测会误判
站点不可用。本轮补「§字段自检」与「提交前须知」，并加判据把字段值、邮箱纪律、探测提示钉住。

范围：只判本件与材料包/运行面/图标事实自洽（不做网络请求）。
同族判据：test_mcpso_submission_doc_contract.py / test_mcp_submissions_doc_contract.py。
契约：八字段逐项、12+1 工具、图标真 400x400、MIT、平台侧未验、邮箱不得写进内容、
Cloudflare/curl 提示、不钉 check/PASS（无留痕词时）。
"""
import re
import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "desktop" / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import mcp_runtime as mcp  # noqa: E402

DOC = ROOT / "packaging" / "mcp" / "submissions" / "05-pulsemcp.md"
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
        raise ValueError(f"PulseMCP 提交件不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("PulseMCP 提交件为空")
    return text


def pulse_issues(text: str) -> list:
    issues = []
    if not text.startswith("# 05 · PulseMCP"):
        issues.append("缺标题「# 05 · PulseMCP」")
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
    if "MIT" not in text:
        issues.append("缺许可 MIT")
    if "平台侧未验" not in text:
        issues.append("缺平台侧未验")
    if "Cloudflare" not in text or "curl" not in text:
        issues.append("缺 Cloudflare / 不要用 curl 探测提示")
    if "把邮箱" not in text:
        issues.append("缺邮箱纪律（不得写进提交内容）")
    leaked = EMAIL.search(text)
    if leaked:
        issues.append(f"正文出现邮箱地址：{leaked.group(0)}")
    for line in text.splitlines():
        if PIN.search(line) and not any(w in line for w in TRACE):
            issues.append(f"钉运行时计数且无留痕词：{line.strip()[:40]}")
    if "不钉运行时计数" not in text:
        issues.append("缺「不钉运行时计数」口径")
    if "TODO" in text:
        issues.append("含 TODO 占位")
    return issues


class PulseMcpSubmissionTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_pulsemcp_matches_contract(self):
        self.assertEqual([], pulse_issues(self.text), "PulseMCP 提交件不满足契约")

    def test_shared_values_live(self):
        for val in SHARED.values():
            self.assertIn(val, self.text)

    def test_contract_catches_mutations(self):
        """变异自证：邮箱泄漏 / 缺 Cloudflare 提示 / 缺平台标注 / 残留钉数。"""
        leak = self.text + "\n- 联系邮箱：ops@example.com\n"
        self.assertTrue(any("邮箱地址" in i for i in pulse_issues(leak)))
        no_cf = self.text.replace("Cloudflare", "CDN")
        self.assertTrue(any("Cloudflare" in i for i in pulse_issues(no_cf)))
        no_platform = self.text.replace("平台侧未验", "平台侧已验")
        self.assertTrue(any("平台侧" in i for i in pulse_issues(no_platform)))
        pinned = self.text + "\n- check1-42 · PASS=76\n"
        self.assertTrue(any("钉运行时计数" in i for i in pulse_issues(pinned)))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_pulse.md")


if __name__ == "__main__":
    unittest.main()
