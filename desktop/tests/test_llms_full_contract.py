#!/usr/bin/env python3
"""llms-full 完整单文件契约：一站读全的内容必须「同源、同步、可判」。

为什么必须有：llms-full.txt 是检索面/爬虫/一次读全的入口（177 行手写静态面），但此前只有
「根件 == 站点源」的字节同步判据——内容本身零判据。实测本轮抓到 3 处真漂移：MCP 工具面漏了
library_read 与 knowledge_order_read（实际 12 工具只写了 10）、全量门禁期望写着 WARN=0
（当次实测 WARN=2，WARN 是非致命提示）、以及安装说明书的 Node 版本与 npm engines 不一致。

范围：只判本文件的内容同源与机器面事实（不改文案口径）。同族判据：
test_external_metadata（根件 == site 源）、test_version_map（公开数字）、
test_llms_contract（清单版）/ test_llms_install_contract（安装面）。
契约：十二节结构、官方入口与防伪声明、MCP 12 工具 + 1 prompt 与 mcp_package 同源、
Node engines 与 packaging/npm/package.json 同源、运行数字与 repo_stats / 实时 doctor 一致、
站点机器面清单在场、fail-closed 边界在场、根件与站点源逐字节一致。
"""
import importlib.util
import json
import re
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FULL = ROOT / "llms-full.txt"
SITE = ROOT / "site" / "llms-full.txt"
MCP = ROOT / "protocol" / "mcp_package.json"
NPMPKG = ROOT / "packaging" / "npm" / "package.json"
STATS = ROOT / "protocol" / "repo_stats.json"
NF = ROOT / "scripts" / "nf.py"

REQUIRED_SECTIONS = ("## 官方入口", "## 一、定义", "## 二、可引用事实", "## 三、按身份选入口",
                     "## 四、五分钟上手", "## 五、术语表", "## 六、它怎么工作", "## 七、FAQ",
                     "## 八、引用格式", "## 九、边界与信任纪律", "## 十、机器面清单",
                     "## 十一、版本")
REQUIRED_MARKERS = ("不是模型", "没有付费版", "fail-closed", "assemble_guide", "RFC 6962",
                    "ninfenz.dev", "check1-42", "PASS=76", "17/17", "12 工具",
                    "2026-07-28", "2025-11-25", "MIT", "如实报错并停止", "protocol/driver.json")
#: 站点机器面（本文件「十、机器面清单」必须逐条列出）
SITE_SURFACES = ("llms.txt", "llms-full.txt", "facts.json", "nf.txt", "agent.txt",
                 "run.sh", "sitemap.xml", "robots.txt")
#: 旧 / 失实口径（出现即说明事实回退）
STALE_PHRASES = ("WARN=0", "Node >= 20", "library_read / knowledge_order_read 缺失")
#: 安装说明书（本文件应指向它，agent 才能从「读全」走到「装好」）
INSTALL_DOC = ROOT / "llms-install.md"

_PARSER_CACHE = []
_DOCTOR_CACHE = []


def load_text(path: Path = FULL) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"llms-full 不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("llms-full 为空")
    return text


def mcp_face() -> dict:
    package = json.loads(MCP.read_text(encoding="utf-8"))["package"]
    return {"tools": list(package["tools"]), "prompts": list(package["prompts"])}


def npm_meta() -> dict:
    package = json.loads(NPMPKG.read_text(encoding="utf-8"))
    return {"version": str(package.get("version") or ""),
            "engines_node": str((package.get("engines") or {}).get("node") or "")}


def _nf_parser():
    if _PARSER_CACHE:
        return _PARSER_CACHE[0]
    spec = importlib.util.spec_from_file_location("nfcli_full", NF)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    parser = module._make_parser()
    _PARSER_CACHE.append(parser)
    return parser


def doctor_live() -> tuple:
    if _DOCTOR_CACHE:
        return _DOCTOR_CACHE[0]
    proc = subprocess.run([sys.executable, str(NF), "doctor", "--json"], cwd=str(ROOT),
                          capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=180)
    if proc.returncode != 0:
        raise ValueError(f"doctor --json 未通过：{proc.stderr[-300:]}")
    report = json.loads(proc.stdout)
    result = (int(report["passed"]), int(report["total"]))
    _DOCTOR_CACHE.append(result)
    return result


def sync_issues(target: bytes = None, source: bytes = None) -> list:
    """根件必须与站点源逐字节一致（目标缺失 / 漂移都算）。"""
    issues = []
    if source is None:
        source = SITE.read_bytes()
    if target is None:
        if not FULL.is_file():
            return ["根件 llms-full.txt 不在场"]
        target = FULL.read_bytes()
    if target != source:
        issues.append("根件 llms-full.txt 与 site/llms-full.txt 不一致（跑 sync_llms --write）")
    return issues


def full_issues(text: str) -> list:
    issues = []
    for section in REQUIRED_SECTIONS:
        if section not in text:
            issues.append(f"缺段落：{section}")
    for marker in REQUIRED_MARKERS:
        if marker not in text:
            issues.append(f"缺要素：{marker}")
    for phrase in STALE_PHRASES:
        if phrase in text:
            issues.append(f"仍写着旧 / 失实口径：{phrase}")
    face = mcp_face()
    for tool in face["tools"]:
        if tool not in text:
            issues.append(f"MCP 能力面缺工具：{tool}")
    for prompt in face["prompts"]:
        if prompt not in text:
            issues.append(f"MCP 能力面缺提示词：{prompt}")
    claimed = re.findall(r"(\d+)\s*工具", text)
    if claimed and int(claimed[0]) != len(face["tools"]):
        issues.append(f"工具计数写 {claimed[0]}（真源 {len(face['tools'])}）")
    meta = npm_meta()
    compact = re.sub(r"\s+", "", text)
    if meta["engines_node"] and re.sub(r"\s+", "", meta["engines_node"]) not in compact:
        issues.append(f"Node 版本口径缺 {meta['engines_node']}（真源 packaging/npm/package.json）")
    if meta["version"] and f"v{meta['version']}" not in text:
        issues.append(f"npm 版本口径缺 v{meta['version']}（真源 packaging/npm/package.json）")
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
    for surface in SITE_SURFACES:
        if f"ninfenz.dev/{surface}" not in text:
            issues.append(f"机器面清单缺站点入口：{surface}")
    for repo in ("github.com/Monyeah777/NinFenz", "gitee.com/monyeah777/ninfenz"):
        if repo not in text:
            issues.append(f"官方来源缺仓库：{repo}")
    if not INSTALL_DOC.is_file():
        issues.append("安装说明书 llms-install.md 不在场")
    issues.extend(sync_issues())
    return issues


class LlmsFullContractTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_full_matches_contract(self):
        self.assertEqual([], full_issues(self.text), "llms-full 不满足完整单文件契约")

    def test_root_copy_equals_site_source(self):
        self.assertEqual([], sync_issues(), "根件与站点源不同步")

    def test_mcp_and_npm_faces_are_same_source(self):
        face = mcp_face()
        for tool in face["tools"]:
            self.assertIn(tool, self.text, f"缺工具：{tool}")
        self.assertIn("12 工具", self.text)
        meta = npm_meta()
        compact = re.sub(r"\s+", "", self.text)
        self.assertIn(re.sub(r"\s+", "", meta["engines_node"]), compact)
        self.assertIn(f"v{meta['version']}", self.text)

    def test_contract_catches_broken_full(self):
        """变异自证：缺工具 / Node 口径漂移 / WARN=0 回潮 / 缺 fail-closed / 同步漂移都必须报。"""
        face = mcp_face()
        no_tool = self.text.replace(face["tools"][0], "gone_tool")
        self.assertTrue(any("能力面缺工具" in i for i in full_issues(no_tool)))
        wrong_node = self.text.replace("Node >= 18.17", "Node >= 20")
        self.assertTrue(any("Node 版本口径" in i or "失实口径" in i
                            for i in full_issues(wrong_node)))
        stale = self.text + "\n旧口径：WARN=0。\n"
        self.assertTrue(any("失实口径" in i for i in full_issues(stale)))
        no_stop = self.text.replace("如实报错并停止", "尽量处理")
        self.assertTrue(any("如实报错并停止" in i for i in full_issues(no_stop)))
        drift = sync_issues(target=b"changed", source=b"source")
        self.assertTrue(any("不一致" in i for i in drift))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_llms_full.txt")


if __name__ == "__main__":
    unittest.main()
