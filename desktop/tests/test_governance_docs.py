#!/usr/bin/env python3
"""社区与内容治理件判据（审计 Z6：治理件在场且**承担语义**，不是占位文件）。

覆盖：行为准则（举报 + 处置 + 申诉）、维护者名单、支持与申诉通道、DCO/进站=出站授权、
REUSE 声明与 LICENSES/ 一致。
"""
import re
import tempfile
import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REQUIRED = ("CODE_OF_CONDUCT.md", "MAINTAINERS.md", "SUPPORT.md", "CONTRIBUTING.md",
            "SECURITY.md", "REUSE.toml", "LICENSES/MIT.txt",
            "LICENSES/LicenseRef-Community-Submission.txt")


def reuse_license_gaps(root: Path = ROOT) -> list:
    """REUSE.toml 里声明的每个许可证都必须有 LICENSES/ 文件或根 LICENSE 支撑。"""
    doc = tomllib.loads((root / "REUSE.toml").read_text(encoding="utf-8"))
    ids = set()
    for ann in doc.get("annotations") or []:
        v = ann.get("SPDX-License-Identifier")
        if isinstance(v, str):
            ids.add(v)
    gaps = []
    for i in sorted(ids):
        if not (root / "LICENSES" / (i + ".txt")).is_file() and \
                not (root / "LICENSE").is_file():
            gaps.append(i)
    return gaps


class GovernanceDocsTest(unittest.TestCase):
    def test_required_files_present(self):
        missing = [r for r in REQUIRED if not (ROOT / r).is_file()]
        self.assertEqual([], missing, "治理件缺失（Z6）：%s" % missing)

    def test_code_of_conduct_has_enforcement_and_appeal(self):
        text = (ROOT / "CODE_OF_CONDUCT.md").read_text(encoding="utf-8")
        for needle in ("举报", "处置", "申诉", "适用范围"):
            self.assertIn(needle, text, "行为准则缺 %s（Z6）" % needle)

    def test_support_has_report_and_appeal_channels(self):
        text = (ROOT / "SUPPORT.md").read_text(encoding="utf-8")
        for needle in ("举报", "申诉", "SECURITY.md"):
            self.assertIn(needle, text, "支持件缺 %s（Z6）" % needle)

    def test_maintainers_names_an_owner(self):
        text = (ROOT / "MAINTAINERS.md").read_text(encoding="utf-8")
        self.assertRegex(text, r"\|\s*Owner", "维护者名单未点名 Owner（Z6）")
        self.assertIn("CODE_OF_CONDUCT.md", text, "维护者件未指向行为准则")

    def test_contributing_declares_inbound_outbound(self):
        text = (ROOT / "CONTRIBUTING.md").read_text(encoding="utf-8")
        self.assertTrue(re.search(r"DCO|Developer Certificate of Origin", text),
                        "贡献指南缺 DCO（Z6）")
        self.assertTrue(re.search(r"inbound\s*=\s*outbound|入站\s*=\s*出站", text),
                        "贡献指南缺 inbound=outbound 授权口径（Z6）")

    def test_reuse_declaration_matches_licenses_dir(self):
        self.assertEqual([], reuse_license_gaps(), "REUSE 声明的许可证缺 LICENSES/ 支撑")

    def test_gap_checker_catches_mutation(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            (d / "LICENSES").mkdir()
            (d / "REUSE.toml").write_text(
                'version = 1' + chr(10) + '[[annotations]]' + chr(10) +
                'path = ["**/*"]' + chr(10) +
                'SPDX-License-Identifier = "LicenseRef-Nope"' + chr(10), encoding="utf-8")
            self.assertEqual(["LicenseRef-Nope"], reuse_license_gaps(d))


if __name__ == "__main__":
    unittest.main()
