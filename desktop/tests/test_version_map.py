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
import sys
import unittest
from pathlib import Path

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
    """第一套口径：CHANGELOG 最新已发布节 == VERSION-MATRIX 末行。"""

    def test_changelog_and_matrix_agree(self):
        ch = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        versions = re.findall(r"^## \[(\d+\.\d+\.\d+)\]", ch, re.M)
        self.assertTrue(versions, "CHANGELOG 没有已发布版本节")
        matrix = (ROOT / "docs" / "meta" / "VERSION-MATRIX.md").read_text(encoding="utf-8")
        rows = re.findall(r"^\| v(\d+\.\d+\.\d+)", matrix, re.M)
        self.assertTrue(rows, "VERSION-MATRIX 没有版本行")
        self.assertEqual(versions[0], rows[-1],
                         "CHANGELOG 最新已发布版本 != VERSION-MATRIX 末行")


class MappingTableTest(unittest.TestCase):
    """映射表本身在册，且**在册的三套口径**都写到。"""

    def test_mapping_table_lists_the_living_families(self):
        text = (ROOT / ".github" / "CONTRIBUTING.md").read_text(encoding="utf-8")
        for needle in ("编号体系映射表", "协议 / 内容", "门禁 verify", "CLI / npm / MCP",
                       "test_version_map.py"):
            self.assertIn(needle, text, "CONTRIBUTING 的编号映射表缺：%s" % needle)

    def test_retired_freeze_family_is_gone(self):
        """退役的第四套口径不得回流（2026-10-11 裁决）：映射表里再出现「冻结目录」即红。"""
        text = (ROOT / ".github" / "CONTRIBUTING.md").read_text(encoding="utf-8")
        self.assertNotIn("冻结目录", text, "CONTRIBUTING 仍在列已退役的冻结目录口径")


if __name__ == "__main__":
    unittest.main()
