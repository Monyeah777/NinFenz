#!/usr/bin/env python3
"""GLAMA.md 契约：上架教程必须「仓库侧证件可核 / 平台侧状态不冒充判据」。

为什么必须有：这篇 500 行的上架操作文档混着两类信息——仓库侧事实（Dockerfile 形态、glama.json
maintainers、版本口径、MCP 工具面）与平台侧状态（完成度 %、TDQS、Repository Ready、Releases）。
前者能机检、后者只能作者在浏览器里看；不分开就会被读成「本仓还没上架完成/已上架完成」。
本轮补「§现状对照（仓库侧可核 / 平台侧不可核）」与「§复现与引用口径」。

范围：只判本文与 Dockerfile/glama.json/pyproject/mcp_runtime 事实自洽（不改上架流程）。
同族判据：test_mcp_runtime.py / test_doc_hygiene.py / test_doc_reachability.py。
契约：复核位、仓库侧现状 8 行、Dockerfile 四条（钉版 / 非 root / CMD serve / 零 pip）、
glama.json maintainers、版本与 pyproject 一致、12 工具 + 1 prompt、平台侧标注未验、复现两命令。
"""
import json
import re
import sys
import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "desktop" / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import mcp_runtime as mcp  # noqa: E402

DOC = ROOT / "GLAMA.md"
DOCKERFILE = ROOT / "Dockerfile"
GLAMA = ROOT / "glama.json"
PYPROJECT = ROOT / "pyproject.toml"
SECTIONS = ("## 现状对照", "## 复现与引用口径", "## 0. 你截图里的每一项是什么意思")


def load_text(path: Path = DOC) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"Glama 教程不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("Glama 教程为空")
    return text


def docker_text() -> str:
    return DOCKERFILE.read_text(encoding="utf-8")


def glama_issues(text: str) -> list:
    issues = []
    if not text.startswith("# Glama 上架一步一步教程"):
        issues.append("缺标题「# Glama 上架一步一步教程（NinFenz Content Gate）」")
    if "复核" not in text:
        issues.append("缺「复核」说明")
    d = docker_text()
    if not re.search(r"^FROM python:3\.11-slim@sha256:[0-9a-f]{64}$", d, re.M):
        issues.append("Dockerfile 基座未按 sha256 钉版")
    if "USER nf" not in d:
        issues.append("Dockerfile 缺非 root 用户")
    if "scripts/nf.py" not in d or '"serve"' not in d:
        issues.append("Dockerfile CMD 不是 serve 入口")
    if re.search(r"(?m)^\s*RUN[^\n]*pip install", d):
        issues.append("Dockerfile 有 RUN pip install（运行期应为零依赖）")
    g = json.loads(GLAMA.read_text(encoding="utf-8"))
    if g.get("maintainers") != ["Monyeah777"]:
        issues.append(f"glama.json maintainers 已变：{g.get('maintainers')}")
    with open(PYPROJECT, "rb") as fh:
        version = tomllib.load(fh)["project"]["version"]
    if version not in text:
        issues.append(f"正文版本与 pyproject 不一致（应为 {version}）")
    names = [t["name"] for t in mcp.TOOL_DEFS]
    if len(names) != 12:
        issues.append(f"工具数已变（{len(names)}）")
    if "**12 工具 + 1 prompt**" not in text:
        issues.append("现状未写「12 工具 + 1 prompt」")
    if len(mcp.PROMPT_DEFS) != 1:
        issues.append(f"prompt 数已变（{len(mcp.PROMPT_DEFS)}）")
    if "平台侧未验" not in text:
        issues.append("缺「平台侧未验」标注")
    if "Dockerfile" not in text or "glama.json" not in text:
        issues.append("现状表未点名 Dockerfile / glama.json")
    positions = [text.find(s) for s in SECTIONS]
    for section, pos in zip(SECTIONS, positions, strict=True):
        if pos < 0:
            issues.append(f"缺段：{section}")
    if all(p >= 0 for p in positions) and positions != sorted(positions):
        issues.append("节顺序不对")
    for cmd in ("python scripts/nf.py serve --help",
                "python -m pytest desktop/tests/test_mcp_runtime.py"):
        if cmd not in text:
            issues.append(f"复现口径缺命令：{cmd}")
    if "TODO" in text:
        issues.append("含 TODO 占位")
    return issues


class GlamaDocTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_glama_matches_contract(self):
        self.assertEqual([], glama_issues(self.text), "Glama 教程不满足契约")

    def test_repo_side_facts_live(self):
        self.assertEqual(12, len(mcp.TOOL_DEFS))
        self.assertEqual(1, len(mcp.PROMPT_DEFS))
        self.assertIn("USER nf", docker_text())
        self.assertEqual(["Monyeah777"],
                         json.loads(GLAMA.read_text(encoding="utf-8"))["maintainers"])

    def test_contract_catches_mutations(self):
        """变异自证：缺平台侧标注 / 工具数与真源不符 / 版本漂移 / 缺命令。"""
        no_platform = self.text.replace("平台侧未验", "平台侧已验证")
        self.assertTrue(any("平台侧未验" in i for i in glama_issues(no_platform)))
        old_tools = self.text.replace("**12 工具 + 1 prompt**", "**8 工具 + 1 prompt**")
        self.assertTrue(any("12 工具" in i for i in glama_issues(old_tools)))
        with open(PYPROJECT, "rb") as fh:
            version = tomllib.load(fh)["project"]["version"]
        bad_ver = self.text.replace(version, "9.9.9")
        self.assertTrue(any("pyproject" in i for i in glama_issues(bad_ver)))
        no_cmd = self.text.replace("python scripts/nf.py serve --help", "看帮助")
        self.assertTrue(any("serve --help" in i for i in glama_issues(no_cmd)))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_glama.md")


if __name__ == "__main__":
    unittest.main()
