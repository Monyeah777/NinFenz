#!/usr/bin/env python3
"""submissions/04-glama.md 契约：仓库侧证件可核、平台侧状态不冒充判据。

为什么必须有：04 号件是 Glama 的认领/提交文案。Glama 最容易把三件事混成一件：
仓库里证件齐（Dockerfile / glama.json / 工具 TDQS 面）、Claim 成功、平台评分与构建通过。
只有第一件能从仓库证明；后两件必须浏览器核对。本轮补「§口径分流」并加本判据，
同时要求本件与 GLAMA.md 的分流口径同源（两处不能各写一套）。

范围：只判本件与 glama.json/Dockerfile/运行面事实自洽（不发网络请求）。
同族判据：test_glama_doc_contract.py / test_mcp_submissions_doc_contract.py。
契约：口径分流段、仓库侧六项、平台侧未验、GLAMA.md 同源点名、不钉运行时计数、Claim 提示。
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

DOC = ROOT / "packaging" / "mcp" / "submissions" / "04-glama.md"
GLAMA = ROOT / "glama.json"
DOCKER = ROOT / "Dockerfile"
ICON = ROOT / "packaging" / "mcp" / "assets" / "icon-400.png"
PIN = re.compile(r"check1-\d+|PASS=\d+")
TRACE = ("此前", "历史", "实测", "2026-", "漂移", "快照")


def load_text(path: Path = DOC) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"Glama 提交件不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("Glama 提交件为空")
    return text


def glama_sub_issues(text: str) -> list:
    issues = []
    if not text.startswith("# 04 · Glama"):
        issues.append("缺标题「# 04 · Glama」")
    if "## 口径分流" not in text:
        issues.append("缺「§口径分流」段")
    if "平台侧未验" not in text:
        issues.append("缺「平台侧未验」标注")
    if "GLAMA.md" not in text:
        issues.append("未点名 GLAMA.md（两处口径必须同源）")
    if len(mcp.TOOL_DEFS) != 12 or len(mcp.PROMPT_DEFS) != 1:
        issues.append("工具面已变（应为 12 + 1）")
    if "**12 只读工具 + 1 prompt**" not in text:
        issues.append("未写 12+1 工具面")
    for era in ("2026-07-28", "2025-11-25"):
        if era not in text:
            issues.append(f"缺协议版本：{era}")
    maintainers = json.loads(GLAMA.read_text(encoding="utf-8")).get("maintainers")
    if maintainers != ["Monyeah777"]:
        issues.append(f"glama.json maintainers 已变：{maintainers}")
    if "Monyeah777" not in text:
        issues.append("正文未写 maintainers 账号")
    docker = DOCKER.read_text(encoding="utf-8")
    if "scripts/nf.py" not in docker or '"serve"' not in docker:
        issues.append("Dockerfile CMD 不是 serve 入口")
    if "@sha256" not in text:
        issues.append("未写基座钉版")
    if "400×400" not in text:
        issues.append("未写图标 400×400")
    if struct.unpack(">II", ICON.read_bytes()[16:24]) != (400, 400):
        issues.append("icon-400.png 真实像素不是 400x400")
    for line in text.splitlines():
        if PIN.search(line) and not any(w in line for w in TRACE):
            issues.append(f"钉运行时计数且无留痕词：{line.strip()[:40]}")
    if "不钉运行时计数" not in text:
        issues.append("缺「不钉运行时计数」口径")
    if "Claim" not in text:
        issues.append("缺 Claim 动作说明")
    if "TODO" in text:
        issues.append("含 TODO 占位")
    return issues


class GlamaSubmissionTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_glama_submission_matches_contract(self):
        self.assertEqual([], glama_sub_issues(self.text), "Glama 提交件不满足契约")

    def test_manifest_live(self):
        self.assertEqual(["Monyeah777"],
                         json.loads(GLAMA.read_text(encoding="utf-8"))["maintainers"])

    def test_contract_catches_mutations(self):
        """变异自证：缺平台标注 / 缺同源点名 / 残留钉数 / 图标像素。"""
        no_platform = self.text.replace("平台侧未验", "平台侧已验")
        self.assertTrue(any("平台侧" in i for i in glama_sub_issues(no_platform)))
        no_src = self.text.replace("GLAMA.md", "文档")
        self.assertTrue(any("GLAMA.md" in i for i in glama_sub_issues(no_src)))
        pinned = self.text + "\n- 门禁 check1-42 · PASS=76\n"
        self.assertTrue(any("钉运行时计数" in i for i in glama_sub_issues(pinned)))
        no_icon = self.text.replace("400×400", "512")
        self.assertTrue(any("图标" in i for i in glama_sub_issues(no_icon)))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_glama_sub.md")


if __name__ == "__main__":
    unittest.main()
