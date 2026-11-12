#!/usr/bin/env python3
"""llms-install 安装面契约：装好这件事必须「可判、同源、失败即停」。

为什么必须有：llms-install.md 是 agent 唯一的安装说明书，但此前零专属判据——它写着
「全量门禁：40 检查 · 约 2500 单测」（真源已是 check1-42 / 全量测试数千条），版本与 MCP
能力面（12 工具 + 1 prompt + 双时代协议）全靠手抄，探针期望还把帧序号写错（通知帧不响应、
tools/list 是第 3 帧）。agent 照做要么低估门禁、要么在探针处误判「MCP 没活」。

范围：只判本文件的安装/自检/接入事实与可执行性（不改安装路线）。同族判据：
test_version_map（全仓公开数字）、test_llms_contract（机器入口清单）/ test_mcp_runtime（机器面）。
契约：七节结构、三条安装路线、MCP 能力面与 protocol/mcp_package.json 同源、双时代协议与
mcp_runtime 常量同源、运行数字与 repo_stats / 实时 doctor 一致、探针四帧可解析、失败即停。
"""
import importlib.util
import json
import re
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
INSTALL = ROOT / "llms-install.md"
MCP = ROOT / "protocol" / "mcp_package.json"
RUNTIME = ROOT / "desktop" / "src" / "core" / "mcp_runtime.py"
STATS = ROOT / "protocol" / "repo_stats.json"
NF = ROOT / "scripts" / "nf.py"

REQUIRED_SECTIONS = ("## 0 一句话", "## 1 前置", "## 2 安装", "### A 零安装",
                     "### B 克隆仓库", "### C 只要 MCP 面", "## 3 接进 MCP",
                     "## 4 装完自检", "## 5 停止条件", "## 6 常见问题", "## 7 出口面")
REQUIRED_MARKERS = ("只读", "无写路径", "assemble_guide", "nf-repo-live",
                    "inputSchema", "-32602", "2026-07-28", "2025-11-25",
                    "退出码 0", "任一条非 0", "如实报错并停止",
                    "无付费版", "ninfenz.dev/llms.txt", "ninfenz.dev/facts.json")
#: 旧口径（出现即说明运行数字回退）
STALE_PHRASES = ("40 检查", "约 2500", "2500 单测", "L0–L2 · 40")

_PARSER_CACHE = []


def load_text(path: Path = INSTALL) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"llms-install 不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("llms-install 为空")
    return text


def _nf_parser():
    """真 argparse 面（同 test_doc_reachability 口径：校验文档里的 nf 子命令与旗标）。"""
    if _PARSER_CACHE:
        return _PARSER_CACHE[0]
    spec = importlib.util.spec_from_file_location("nfcli_install", NF)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    parser = module._make_parser()
    _PARSER_CACHE.append(parser)
    return parser


def _subcommands() -> set:
    import argparse
    for action in _nf_parser()._actions:
        if isinstance(action, argparse._SubParsersAction):
            return set(action.choices)
    return set()


def mcp_face() -> dict:
    """→ {'tools': [...], 'prompts': [...]}（机读真源）。"""
    package = json.loads(MCP.read_text(encoding="utf-8"))["package"]
    return {"tools": list(package["tools"]), "prompts": list(package["prompts"])}


def protocol_versions() -> set:
    """从 mcp_runtime 常量取双时代协议版本（源码即真源）。"""
    text = RUNTIME.read_text(encoding="utf-8")
    return set(re.findall(r"(?:MODERN|LEGACY)_PROTOCOL_VERSION = \"([^\"]+)\"", text))


def probe_frames(text: str) -> list:
    """取探针代码块里的 JSON 帧（取含 jsonrpc 的 text 围栏）。"""
    frames = []
    for block in re.findall(r"```text\n(.*?)```", text, re.S):
        if "jsonrpc" not in block:
            continue
        for line in block.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                frames.append(json.loads(line))
            except ValueError:
                frames.append({"__bad__": line})
    return frames


def doctor_live() -> tuple:
    """实时 doctor 计数（缓存到模块级，避免每个用例重复跑）。"""
    key = "__doctor_cache__"
    cached = getattr(_nf_parser(), key, None)
    if cached:
        return cached
    proc = subprocess.run([sys.executable, str(NF), "doctor", "--json"], cwd=str(ROOT),
                          capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=180)
    if proc.returncode != 0:
        raise ValueError(f"doctor --json 未通过：{proc.stderr[-300:]}")
    report = json.loads(proc.stdout)
    result = (int(report["passed"]), int(report["total"]))
    setattr(_nf_parser(), key, result)
    return result


def face_issues(text: str) -> list:
    """MCP 能力面 / 双时代协议 / 工具计数与真源逐条对账。"""
    issues = []
    face = mcp_face()
    for tool in face["tools"]:
        if tool not in text:
            issues.append(f"能力面缺工具：{tool}")
    for prompt in face["prompts"]:
        if prompt not in text:
            issues.append(f"能力面缺提示词：{prompt}")
    claimed_tools = re.findall(r"(\d+)\s*个工具", text)
    if claimed_tools and int(claimed_tools[0]) != len(face["tools"]):
        issues.append(f"工具计数写 {claimed_tools[0]}（真源 {len(face['tools'])}）")
    claimed_prompts = re.findall(r"(\d+)\s*个 prompt", text)
    if claimed_prompts and int(claimed_prompts[0]) != len(face["prompts"]):
        issues.append(f"提示词计数写 {claimed_prompts[0]}（真源 {len(face['prompts'])}）")
    versions = protocol_versions()
    if len(versions) != 2:
        issues.append(f"mcp_runtime 双时代版本常量解析失败（{sorted(versions)}）")
    for version in versions:
        if version not in text:
            issues.append(f"缺协议版本：{version}")
    if "nf-repo-live" not in NF.read_text(encoding="utf-8"):
        issues.append("live 面 serverInfo.name 的真源（scripts/nf.py）里没有 nf-repo-live")
    return issues


def numeric_issues(text: str) -> list:
    """运行数字与 repo_stats / 实时 doctor 对账。"""
    issues = []
    stats = json.loads(STATS.read_text(encoding="utf-8"))
    for num in re.findall(r"check1-(\d+)", text):
        if int(num) != int(stats["verify_checks"]):
            issues.append(f"check1-{num} 与真源 check1-{stats['verify_checks']} 不一致")
    for num in re.findall(r"PASS=(\d+)", text):
        if int(num) != int(stats["baseline_pass"]):
            issues.append(f"PASS={num} 与真源 PASS={stats['baseline_pass']} 不一致")
    passed, total = doctor_live()
    for got in re.findall(r"(\d+)\s*/\s*(\d+)", text):
        if got != (str(passed), str(total)):
            issues.append(f"doctor {got[0]}/{got[1]} 与实时 {passed}/{total} 不一致")
    for num in re.findall(r"doctor[^\n]{0,12}?(\d+)\s*项", text):
        if int(num) != total:
            issues.append(f"doctor {num} 项与实时 {total} 项不一致")
    return issues


def command_issues(text: str) -> list:
    """文档里的 nf 子命令必须真实（安装命令写错 = 第一步就断）。"""
    issues = []
    valid = _subcommands()
    if len(valid) < 40:
        issues.append(f"CLI 命令面解析失败（{len(valid)} 条）")
    for token in re.findall(r"`([^`\n]+)`", text):
        for cmd in re.findall(r"\bnf\.py\s+([a-z][a-z0-9-]*)", token):
            if cmd not in valid:
                issues.append(f"引用了不存在的 nf 子命令：{cmd}")
    for sub in re.findall(r"npx -y ninfenz ([-a-z]+)", text):
        if sub.lstrip("-") not in ("version", "doctor", "serve"):
            issues.append(f"npx 入口写了未知子命令：{sub}")
    return issues


def probe_issues(text: str) -> list:
    """探针四帧必须可解析、方法序正确、期望描述对得上帧。"""
    issues = []
    frames = probe_frames(text)
    methods = [f.get("method") for f in frames]
    expected = ["initialize", "notifications/initialized", "tools/list", "prompts/list"]
    if methods != expected:
        issues.append(f"探针帧方法序不对：{methods}")
    if any("__bad__" in f for f in frames):
        issues.append("探针里存在无法解析的 JSON 帧")
    ids = [f.get("id") for f in frames if f.get("id") is not None]
    if ids != [1, 2, 3]:
        issues.append(f"探针请求 id 应为 1/2/3（实测 {ids}）")
    return issues


def install_issues(text: str) -> list:
    issues = []
    for section in REQUIRED_SECTIONS:
        if section not in text:
            issues.append(f"缺段落：{section}")
    for marker in REQUIRED_MARKERS:
        if marker not in text:
            issues.append(f"缺要素：{marker}")
    for phrase in STALE_PHRASES:
        if phrase in text:
            issues.append(f"仍写着旧运行数字：{phrase}")
    issues.extend(face_issues(text))
    issues.extend(numeric_issues(text))
    issues.extend(command_issues(text))
    issues.extend(probe_issues(text))
    return issues


class LlmsInstallContractTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_install_matches_contract(self):
        self.assertEqual([], install_issues(self.text), "llms-install 不满足安装契约")

    def test_mcp_face_is_same_source(self):
        self.assertEqual([], face_issues(self.text), "MCP 能力面与真源不一致")

    def test_numeric_claims_match_runtime(self):
        self.assertEqual([], numeric_issues(self.text), "运行数字与真源不一致")

    def test_probe_frames_are_executable(self):
        self.assertEqual([], probe_issues(self.text), "探针帧不可执行")

    def test_contract_catches_broken_install(self):
        """变异自证：缺工具 / 版本漂移 / 旧数字回潮 / 删停止条件 / 探针帧错都必须报。"""
        face = mcp_face()
        no_tool = self.text.replace(face["tools"][0], "gone_tool")
        self.assertTrue(any("能力面缺工具" in i for i in face_issues(no_tool)))
        old_version = self.text.replace("2026-07-28", "2026-01-01")
        self.assertTrue(any("缺协议版本" in i for i in face_issues(old_version)))
        stale = self.text + "\n旧口径：约 2500 单测。\n"
        self.assertTrue(any("旧运行数字" in i for i in install_issues(stale)))
        no_stop = self.text.replace("## 5 停止条件", "## 5 说明")
        self.assertTrue(any("停止条件" in i for i in install_issues(no_stop)))
        bad_probe = self.text.replace('"id":3', '"id":9')
        self.assertTrue(any("id" in i for i in probe_issues(bad_probe)))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_llms_install.md")


if __name__ == "__main__":
    unittest.main()
