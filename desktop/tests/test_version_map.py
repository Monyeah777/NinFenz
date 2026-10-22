#!/usr/bin/env python3
"""编号体系映射表判据（审计 C1：四套版本口径必须各自自洽）。

三套口径（见 CONTRIBUTING §2.1）：
1. 协议 / 内容 vX.Y.Z —— CHANGELOG 最新已发布节 == VERSION-MATRIX 末行；
2. 门禁 verify vA.B —— protocol/repo_stats.json == quality_baseline 期望值 == llms.txt 质量凭证串；
3. CLI / npm / MCP 1.0.x —— NF_CLI_VERSION == npm package.json == MCP server.json（两处）。

（第四套「冻结目录」= 原 golden master 快照，2026-10-11 作者裁决退役并删除；本件反向断言
映射表**不得**再留该口径，防它悄悄回到文档里。）
"""
import json
import re
import subprocess
import sys
import tomllib
import unittest
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import quality_baseline as qb  # noqa: E402


class CliNpmMcpVersionTest(unittest.TestCase):
    """第三套口径：启动器 / npm / MCP 三处同版本。"""

    def test_three_faces_agree(self):
        text = (ROOT / "scripts" / "nf.py").read_text(encoding="utf-8")
        m = re.search(r'^NF_CLI_VERSION = "([^"]+)"', text, re.M)
        self.assertIsNotNone(m, "scripts/nf.py 里找不到 NF_CLI_VERSION")
        cli = m.group(1)
        npm = json.loads((ROOT / "packaging" / "npm" / "package.json")
                         .read_text(encoding="utf-8"))["version"]
        srv = json.loads((ROOT / "packaging" / "mcp" / "server.json")
                         .read_text(encoding="utf-8"))
        self.assertEqual(cli, npm, "NF_CLI_VERSION != npm package.json version")
        self.assertEqual(cli, srv.get("version"), "NF_CLI_VERSION != server.json.version")
        pkg0 = (srv.get("packages") or [{}])[0]
        self.assertEqual(cli, pkg0.get("version"),
                         "NF_CLI_VERSION != server.json packages[0].version")

        pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        self.assertEqual(cli, pyproject["project"]["version"],
                         "NF_CLI_VERSION != pyproject.toml [project].version")

        hf = (ROOT / "packaging" / "hf-space" / "Dockerfile").read_text(encoding="utf-8")
        m = re.search(r"^ARG NF_VERSION=(\d+\.\d+\.\d+)$", hf, re.M)
        self.assertIsNotNone(m, "HF Space Dockerfile 缺可解析的 NF_VERSION 默认值")
        self.assertEqual(cli, m.group(1), "NF_CLI_VERSION != HF Space NF_VERSION")

        dotnet = (ROOT / "engine" / "dotnet" / "tools" / "nf-dotnet" / "Program.cs").read_text(
            encoding="utf-8")
        m = re.search(r'const string NfCliVersion = "([^"]+)"', dotnet)
        self.assertIsNotNone(m, ".NET CLI 缺可解析的 NfCliVersion")
        self.assertEqual(cli, m.group(1), "NF_CLI_VERSION != .NET doctor 版本")

        declaration = json.loads((ROOT / "protocol" / "mcp_package.json")
                                 .read_text(encoding="utf-8"))
        self.assertEqual(cli, declaration.get("version"),
                         "NF_CLI_VERSION != protocol/mcp_package.json version")


class GateVersionTest(unittest.TestCase):
    """第二套口径：门禁版本三源一致。"""

    def test_repo_stats_matches_quality_baseline_and_llms(self):
        stats = json.loads((ROOT / "protocol" / "repo_stats.json")
                           .read_text(encoding="utf-8"))
        issues, qstats = qb.scan(str(ROOT))
        self.assertEqual([], issues, "quality_baseline 自检红：%s" % issues[:3])
        # verify.sh 里的版本写作 v2.30、repo_stats 写作 2.30 —— 归一后比（去前缀 v）。
        norm = lambda s: str(s).lstrip("v")  # noqa: E731 - 就地归一，避免引入第二个口径
        self.assertEqual(norm(qstats["verify_version"]), norm(stats["verify_version"]),
                         "verify.sh 版本 != repo_stats.verify_version")
        self.assertEqual(qb.EXPECTED_CHECKS, stats["verify_checks"])
        self.assertEqual(qb.EXPECTED_PASS, stats["baseline_pass"])
        llms = (ROOT / "llms.txt").read_text(encoding="utf-8")
        m = re.search(r"verify v(\d+\.\d+) · check(\d+)-(\d+) · PASS=(\d+)", llms)
        self.assertIsNotNone(m, "llms.txt 缺质量凭证真源串")
        self.assertEqual((m.group(1), int(m.group(3)), int(m.group(4))),
                         (stats["verify_version"], stats["verify_checks"],
                          stats["baseline_pass"]),
                         "llms.txt 质量凭证串与 repo_stats 不一致")


class ContentVersionTest(unittest.TestCase):
    """第一套口径：CHANGELOG 最新已发布节 == VERSION-MATRIX 末行。

    版本号格式 2026-10-20 起为内容线 0.x 两位小数（作者裁决：突破 +0.01 / 创新 +0.1），
    故正则同时接受 `0.93` 与旧 `2.12.0` 两种写法；不变量本身不变。
    """

    def test_changelog_and_matrix_agree(self):
        ch = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        versions = re.findall(r"^## \[(\d+\.\d+(?:\.\d+)?)\]", ch, re.M)
        self.assertTrue(versions, "CHANGELOG 没有已发布版本节")
        matrix = (ROOT / "docs" / "meta" / "VERSION-MATRIX.md").read_text(encoding="utf-8")
        rows = re.findall(r"^\| v(\d+\.\d+(?:\.\d+)?)", matrix, re.M)
        self.assertTrue(rows, "VERSION-MATRIX 没有版本行")
        self.assertEqual(versions[0], rows[-1],
                         "CHANGELOG 最新已发布版本 != VERSION-MATRIX 末行")


class MappingTableTest(unittest.TestCase):
    """映射表本身在册，且**在册的三套口径**都写到。"""

    def test_mapping_table_lists_the_living_families(self):
        text = (ROOT / "CONTRIBUTING.md").read_text(encoding="utf-8")
        for needle in ("编号体系映射表", "协议 / 内容", "门禁 verify", "CLI / npm / MCP",
                       "test_version_map.py"):
            self.assertIn(needle, text, "CONTRIBUTING 的编号映射表缺：%s" % needle)

    def test_retired_freeze_family_is_gone(self):
        """退役的第四套口径不得回流（2026-10-11 裁决）：映射表里再出现「冻结目录」即红。"""
        text = (ROOT / "CONTRIBUTING.md").read_text(encoding="utf-8")
        self.assertNotIn("冻结目录", text, "CONTRIBUTING 仍在列已退役的冻结目录口径")


_MD_LINK = re.compile(r"(?<!!)\[[^\]\n]*\]\(([^)\n]+)\)")
_FENCED = re.compile(r"```.*?```|~~~.*?~~~", re.S)
_INLINE_CODE = re.compile(r"`[^`\n]*`")


def managed_markdown():
    """公开/受治理的 Markdown 面；历史变更日志、社区内容和生成 payload 不计。"""
    roots = {"docs", "results", "protocol", "packaging", "integrations"}
    for p in ROOT.rglob("*.md"):
        rel = p.relative_to(ROOT)
        if any(part in {".git", ".rivet", "node_modules", "payload", "__pycache__"}
               for part in rel.parts):
            continue
        if rel.parts[0] in {"community", "CHANGELOG.md"}:
            continue
        if len(rel.parts) == 1 or rel.parts[0] in roots:
            yield p


def missing_local_links():
    """→ [(文档, 目标, 原因)]。只认真正的 Markdown 链接，跳过代码/锚点/外部 URL。"""
    out = []
    checked = 0
    for p in managed_markdown():
        try:
            text = p.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            continue
        text = _FENCED.sub("", text)
        text = _INLINE_CODE.sub("", text)
        for m in _MD_LINK.finditer(text):
            target = m.group(1).strip()
            if not target or target.startswith(("#", "<")):
                continue
            if re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", target):
                continue
            target = target.split()[0].strip("<>")
            target = unquote(target.split("#", 1)[0].split("?", 1)[0])
            if not target or "{" in target or "}" in target or " " in target:
                continue
            checked += 1
            resolved = (p.parent / target).resolve()
            try:
                resolved.relative_to(ROOT)
            except ValueError:
                out.append((p.relative_to(ROOT).as_posix(), target, "路径越出仓库"))
                continue
            if not resolved.exists():
                out.append((p.relative_to(ROOT).as_posix(), target, "目标不存在"))
    return out, checked


class PublicSurfaceBindingTest(unittest.TestCase):
    """公开入口的数字与链接必须能落到当前仓库事实。"""

    def test_managed_markdown_local_links_resolve(self):
        missing, checked = missing_local_links()
        self.assertGreaterEqual(checked, 20, "本地链接扫描面塌缩（判据可能空转）")
        self.assertEqual([], missing, f"公开文档存在失效相对链接：{missing[:10]}")

    def test_instruction_prerequisites_are_publicly_reachable(self):
        """开工前置不得依赖未随公开仓发布、且当前不存在的本地计划档案。"""
        for rel in ("AGENTS.md", "STRATEGY.md"):
            text = (ROOT / rel).read_text(encoding="utf-8")
            self.assertNotIn("40_未来计划总纲", text,
                             f"{rel} 把不存在的本地计划写成通用开工前置")

    def test_live_numeric_claims_match_runtime(self):
        stats = json.loads((ROOT / "protocol" / "repo_stats.json")
                           .read_text(encoding="utf-8"))
        proc = subprocess.run([sys.executable, str(ROOT / "scripts" / "nf.py"),
                               "doctor", "--json"], cwd=str(ROOT), capture_output=True,
                              text=True, encoding="utf-8", errors="replace", timeout=120)
        self.assertEqual(0, proc.returncode, f"doctor --json 未通过：{proc.stderr[-500:]}")
        doctor = json.loads(proc.stdout)
        self.assertEqual(doctor["passed"], doctor["total"])

        live = [
            "README.md", "README.en.md", "README.ja.md", "llms.txt", "llms-install.md",
            "site/index.html", "site/en/index.html", "site/use/index.html",
            "site/en/use/index.html", "site/agent.txt", "site/llms.txt", "site/llms-full.txt",
            "site/facts.json", "site/nf.txt", "site/run.sh", "site/README.md",
            "packaging/hf-space/README.md", "packaging/hf-space/server.py",
            "site/tools/make-demo-gif.py",
        ]
        bad = []
        seen = 0
        for rel in live:
            text = (ROOT / rel).read_text(encoding="utf-8")
            for n in re.findall(r"check1-(\d+)", text):
                seen += 1
                if int(n) != stats["verify_checks"]:
                    bad.append(f"{rel}: check1-{n}（真源 check1-{stats['verify_checks']}）")
            for n in re.findall(r"PASS=(\d+)", text):
                seen += 1
                if int(n) != stats["baseline_pass"]:
                    bad.append(f"{rel}: PASS={n}（真源 PASS={stats['baseline_pass']}）")
            pairs = (re.findall(r"\bdoctor\b[^\n]{0,12}?[（(]?(\d+)\s*/\s*(\d+)", text)
                     + re.findall(r"体检[:：][^\n]{0,12}?(\d+)\s*/\s*(\d+)", text))
            for n in pairs:
                seen += 1
                if n != (str(doctor["passed"]), str(doctor["total"])):
                    bad.append(
                        f"{rel}: doctor {n[0]}/{n[1]}"
                        f"（真源 {doctor['passed']}/{doctor['total']}）")
            counts = (re.findall(r"\bdoctor\b[^\n]{0,20}?(\d+)\s*(?:项|checks?)", text)
                      + re.findall(r"体检[^\n]{0,12}?(\d+)\s*项", text))
            for n in counts:
                seen += 1
                if int(n) != doctor["total"]:
                    bad.append(f"{rel}: doctor {n} 项（真源 {doctor['total']} 项）")
        self.assertGreaterEqual(seen, 20, "公开数字扫描面塌缩（判据可能空转）")
        self.assertEqual([], bad, f"公开入口数字与运行时真源不一致：{bad[:12]}")


if __name__ == "__main__":
    unittest.main()
