#!/usr/bin/env python3
"""许可链契约判据：LICENSE 是唯一真源，其余四处只允许指向它（2026-11-11）。

为什么必须有：许可口径散在 LICENSE / pyproject / REUSE.toml / CITATION.cff / .zenodo.json /
codemeta.json / THIRD-PARTY-NOTICES / README 多处，各处虽有自己的判据，却**没有一条总闸**——
任何一处把 MIT 写成 AGPL（.zenodo.json 实测发生过）只能靠该文件自己的判据捕获，
「全链同一真源」这个事实从未被断言。本件把 LICENSE 钉成真源，其余逐处对账。

范围：只判许可链。同族判据：test_zenodo_contract / test_citation_contract / test_reuse_contract /
test_third_party_notices_contract（各管一处细节），本件管「全链一致」。

契约：①LICENSE 是 canonical MIT 文本；②LICENSES/MIT.txt 与 LICENSE 逐字节一致；
③六处声明全部等于 LICENSE 的 SPDX 标识；④入口文档不宣称 copyleft。
"""
import json
import re
import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LICENSE = ROOT / "LICENSE"
MIT_COPY = ROOT / "LICENSES" / "MIT.txt"
PYPROJECT = ROOT / "pyproject.toml"
REUSE = ROOT / "REUSE.toml"
CITATION = ROOT / "CITATION.cff"
ZENODO = ROOT / ".zenodo.json"
CODEMETA = ROOT / "codemeta.json"
NOTICES = ROOT / "THIRD-PARTY-NOTICES.md"

#: canonical MIT 必须出现的关键条款（少一条即被改过文本）
MIT_CLAUSES = (
    "Permission is hereby granted, free of charge",
    "The above copyright notice and this permission notice shall be included in all",
    'THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND',
    "IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE",
)
#: 入口文档允许出现的 copyleft 词——出现即说明「本仓许可」被写成别的
COPYLEFT = ("AGPL", "GNU General Public License", "GPL-3.0")


def _squash(text: str) -> str:
    return " ".join((text or "").split())


def load_text(path: Path = LICENSE) -> str:
    """读文本（缺失 / 空件显式报错）。"""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"许可文件不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("许可文件为空")
    return text


def spdx_id(text: str) -> str:
    """LICENSE 首行 → SPDX 标识（当前仅识别 MIT，见修复指引）。"""
    head = text.splitlines()[0].strip()
    if head == "MIT License":
        return "MIT"
    raise ValueError(f"LICENSE 首行不是已知许可标题：{head!r}"
                     "（修复指引：换许可要先改本判据的识别表与全部声明面）")


def canonical_issues(text: str) -> list:
    """canonical MIT 文本检查。"""
    issues = []
    head = text.splitlines()[0].strip() if text.splitlines() else ""
    if head != "MIT License":
        issues.append(f"LICENSE 首行必须是 MIT License，实际 {head!r}")
    if not re.search(r"(?m)^Copyright \(c\) \d{4} \S", text):
        issues.append("缺版权行（Copyright (c) <年> <持有者>）")
    flat = _squash(text)
    for clause in MIT_CLAUSES:
        if _squash(clause) not in flat:
            issues.append(f"canonical MIT 条款缺失：{clause[:40]}…")
    for token in COPYLEFT:
        if token in text:
            issues.append(f"LICENSE 出现 copyleft 词：{token}")
    return issues


def _yaml(path: Path) -> dict:
    import yaml

    try:
        doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ValueError(f"{path.name} 不可读/不可解析：{exc}") from exc
    return doc if isinstance(doc, dict) else {}


def claims() -> dict:
    """六处许可声明 → {来源: SPDX 标识}（缺一处即抛 ValueError）。"""
    out = {}
    project = tomllib.loads(PYPROJECT.read_text(encoding="utf-8")).get("project") or {}
    lic = project.get("license")
    if not isinstance(lic, dict) or lic.get("file") != "LICENSE":
        raise ValueError("pyproject [project].license 未指向 LICENSE 文件")
    classifiers = project.get("classifiers") or []
    if "License :: OSI Approved :: MIT License" not in classifiers:
        raise ValueError("pyproject 缺 MIT 分类器")
    out["pyproject"] = "MIT"
    reuse = tomllib.loads(REUSE.read_text(encoding="utf-8"))
    aggregate = [a for a in (reuse.get("annotations") or [])
                 if str((a or {}).get("precedence") or "") == "aggregate"]
    if not aggregate:
        raise ValueError("REUSE.toml 缺 aggregate 声明")
    out["reuse"] = str(aggregate[0].get("SPDX-License-Identifier") or "").strip()
    out["citation"] = str(_yaml(CITATION).get("license") or "").strip()
    out["zenodo"] = str((json.loads(ZENODO.read_text(encoding="utf-8")).get("license") or {})
                        .get("id") or "").strip()
    codemeta = json.loads(CODEMETA.read_text(encoding="utf-8"))
    out["codemeta"] = str(codemeta.get("license") or "").strip()
    if "MIT" not in NOTICES.read_text(encoding="utf-8"):
        raise ValueError("THIRD-PARTY-NOTICES.md 未提及本仓 MIT 许可")
    out["notices"] = "MIT"
    return out


def chain_issues(license_text: str, claim_map: dict, mit_copy: str = "") -> list:
    """许可链问题列表（纯函数，便于变异自证）。"""
    issues = canonical_issues(license_text)
    want = None
    try:
        want = spdx_id(license_text)
    except ValueError as exc:
        issues.append(str(exc))
    if want:
        for source, got in sorted(claim_map.items()):
            if got != want:
                issues.append(f"{source} 的许可声明与 LICENSE 不一致：{got!r} ≠ {want!r}")
    if mit_copy and mit_copy != license_text:
        issues.append("LICENSES/MIT.txt 与 LICENSE 不是逐字节一致（REUSE 要求唯一文本）")
    return issues


def entry_doc_claims() -> dict:
    """入口文档的许可宣称（README / README.en / CONTRIBUTING）。"""
    docs = {}
    for rel in ("README.md", "README.en.md", "CONTRIBUTING.md"):
        docs[rel] = (ROOT / rel).read_text(encoding="utf-8")
    return docs


class LicenseChainContractTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_license_is_canonical_mit(self):
        self.assertEqual([], canonical_issues(self.text), "LICENSE 不是 canonical MIT")

    def test_mit_text_is_single_copy(self):
        """LICENSES/MIT.txt 必须与 LICENSE 逐字节一致。"""
        self.assertTrue(MIT_COPY.is_file(), "缺 LICENSES/MIT.txt")
        self.assertEqual(self.text, MIT_COPY.read_text(encoding="utf-8"),
                         "LICENSES/MIT.txt 与 LICENSE 不一致")

    def test_chain_is_single_sourced(self):
        """六处声明（pyproject / REUSE / CITATION / Zenodo / codemeta / notices）全部 = MIT。"""
        claim_map = claims()
        self.assertEqual({"MIT"}, set(claim_map.values()), "存在与 LICENSE 不一致的声明")
        self.assertEqual([], chain_issues(self.text, claim_map,
                                          MIT_COPY.read_text(encoding="utf-8")))

    def test_entry_docs_claim_mit(self):
        """入口文档不得把本仓许可写成 copyleft。"""
        for rel, text in entry_doc_claims().items():
            self.assertIn("MIT", text, f"{rel} 未声明 MIT")
            for token in COPYLEFT:
                self.assertNotIn(token, text, f"{rel} 出现 copyleft 宣称：{token}")

    def test_contract_catches_chain_drift(self):
        """变异自证：改 LICENSE 首行 / 改任一声明 / 文本不一致 / 缺件——都必须报。"""
        claims_ok = claims()
        mit_copy = MIT_COPY.read_text(encoding="utf-8")
        self.assertEqual([], chain_issues(self.text, claims_ok, mit_copy))
        broken = self.text.replace("MIT License", "Apache License", 1)
        self.assertTrue(chain_issues(broken, claims_ok, mit_copy), "改掉 LICENSE 首行必须报")
        truncated = self.text.replace(MIT_CLAUSES[0], "", 1)
        self.assertTrue(any("条款缺失" in i for i in chain_issues(truncated, claims_ok, mit_copy)),
                        "删条款必须报")
        drifted = dict(claims_ok)
        drifted["zenodo"] = "AGPL-3.0-only"
        self.assertTrue(any("zenodo" in i for i in chain_issues(self.text, drifted, mit_copy)),
                        "zenodo 声明漂移必须报")
        self.assertTrue(any("MIT.txt" in i for i in chain_issues(self.text, claims_ok, "x")),
                        "许可文本不一致必须报")
        self.assertTrue(canonical_issues("Copyright 2026\nMIT License\n"), "缺标准文本必须报")
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_license")


if __name__ == "__main__":
    unittest.main()
