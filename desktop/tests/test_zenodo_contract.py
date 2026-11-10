#!/usr/bin/env python3
"""Zenodo 元数据契约判据：存档记录不得与仓库许可 / 引用件分叉（2026-11-10）。

为什么必须有：.zenodo.json 是 Zenodo / DOI 存档的机读记录，写错不会让任何测试红，
但会让每个 DOI 引用带上错误许可与失效文件指针。本轮实测的旧记录声明 AGPL-3.0-only，
而 LICENSE / pyproject / REUSE.toml / README / CITATION.cff 全是 MIT，并引用了三个
不存在的文件（LICENSING.md / COMMERCIAL.md / TRADEMARK.md）——只有判据能拦住这种漂移。

范围：只判 .zenodo.json。同族判据：test_governance_docs（REUSE ⇄ LICENSES 一致）、
test_citation_contract（CITATION.cff）。契约：许可四源一致 + title ⇄ CITATION + 无失效文件引用。
"""
import json
import re
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ZENODO = ROOT / ".zenodo.json"
CITATION = ROOT / "CITATION.cff"
LICENSE = ROOT / "LICENSE"
REUSE = ROOT / "REUSE.toml"
PYPROJECT = ROOT / "pyproject.toml"
REPO_URL = "https://github.com/Monyeah777/NinFenz"

#: Zenodo 记录必备键（缺一即解析/引用面残缺）
REQUIRED_KEYS = (
    "title", "upload_type", "access_right", "license", "creators",
    "description", "keywords", "language", "related_identifiers",
)
#: 只检查「根层文档/配置」形态的文件引用（.txt 等许可文本名不算，避免误报）
DOC_FILE = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.-]*\.(?:md|cff|toml|yml|yaml)")


def load_zenodo(path: Path = ZENODO) -> dict:
    """读 Zenodo 记录（缺失 / 非法 JSON / 非映射 → ValueError）。"""
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValueError(f"Zenodo 记录不可读：{exc}") from exc
    except ValueError as exc:
        raise ValueError(f"Zenodo 记录不是合法 JSON：{exc}") from exc
    if not isinstance(doc, dict):
        raise ValueError("Zenodo 记录根节点必须是映射")
    return doc


def repo_license_id() -> str:
    """仓库许可真源：LICENSE 首行 `MIT License` → SPDX `MIT`。"""
    text = LICENSE.read_text(encoding="utf-8").splitlines()
    head = text[0].strip() if text else ""
    if head != "MIT License":
        raise ValueError(f"LICENSE 首行不是可识别的许可标题：{head!r}")
    return "MIT"


def citation_license() -> str:
    """CITATION.cff 声明的许可（同一许可的第二源）。"""
    try:
        import yaml
    except ModuleNotFoundError as exc:
        raise ValueError(f"缺 PyYAML，无法校验引用件：{exc}") from exc
    try:
        doc = yaml.safe_load(CITATION.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ValueError(f"CITATION.cff 不可读/不可解析：{exc}") from exc
    if not isinstance(doc, dict) or not doc.get("license"):
        raise ValueError("CITATION.cff 缺 license")
    return str(doc["license"]).strip()


def reuse_spdx_ids() -> set:
    """REUSE.toml 声明的 SPDX 标识集合（许可分层的机读真源）。"""
    text = REUSE.read_text(encoding="utf-8")
    return set(re.findall(r'SPDX-License-Identifier\s*=\s*"([^"]+)"', text))


def pyproject_declares_mit() -> bool:
    """pyproject 的许可分类器（第三源）。"""
    return "License :: OSI Approved :: MIT License" in PYPROJECT.read_text(encoding="utf-8")


def stale_file_refs(text: str, root: Path = ROOT) -> list:
    """文本里引用的根层文档/配置文件若不存在 → 失效引用清单。"""
    out = []
    for name in DOC_FILE.findall(text):
        if "/" in name:
            continue
        if not (root / name).exists() and name not in out:
            out.append(name)
    return out


def zenodo_issues(doc: dict, root: Path = ROOT) -> list:
    """Zenodo 记录契约问题列表（纯函数，便于变异自证）。"""
    issues = []
    for key in REQUIRED_KEYS:
        if not doc.get(key):
            issues.append(f"缺必备键：{key}")
    if not str(doc.get("title") or "").strip():
        issues.append("title 为空")
    lic = (doc.get("license") or {})
    lic_id = str((lic or {}).get("id") or "")
    want = repo_license_id()
    if lic_id != want:
        issues.append(f"许可与 LICENSE 不一致：{lic_id!r} ≠ {want!r}")
    if citation_license() != lic_id:
        issues.append(f"许可与 CITATION.cff 不一致：{lic_id!r} ≠ {citation_license()!r}")
    if lic_id not in reuse_spdx_ids():
        issues.append(f"许可 {lic_id!r} 不在 REUSE.toml 的 SPDX 声明里")
    if not pyproject_declares_mit():
        issues.append("pyproject 未声明 MIT 分类器（与 LICENSE 不一致）")
    if doc.get("upload_type") != "software":
        issues.append("upload_type 必须为 software")
    if doc.get("access_right") != "open":
        issues.append("access_right 必须为 open")
    creators = doc.get("creators") or []
    if not creators or any(not str((c or {}).get("name") or "").strip() for c in creators):
        issues.append("creators 缺名字")
    try:
        import yaml
        citation = yaml.safe_load(CITATION.read_text(encoding="utf-8")) or {}
    except (ImportError, OSError, ValueError):
        citation = {}
    cit_title = str(citation.get("title") or "").strip()
    if cit_title and cit_title != str(doc.get("title") or "").strip():
        issues.append("title 与 CITATION.cff 不一致（双源漂移）")
    cit_names = set()
    for author in citation.get("authors") or []:
        author = author or {}
        name = str(author.get("family-names") or author.get("name") or "").strip()
        if name:
            cit_names.add(name)
    zen_names = {str((c or {}).get("name") or "").strip() for c in creators}
    if cit_names and not zen_names.issubset(cit_names):
        issues.append("creators 与 CITATION.cff authors 不一致")
    identifiers = json.dumps(doc.get("related_identifiers") or [], ensure_ascii=False)
    if REPO_URL not in identifiers:
        issues.append("related_identifiers 缺仓库 URL")
    text = str(doc.get("description") or "") + "\n" + str(doc.get("notes") or "")
    for name in stale_file_refs(text, root):
        issues.append(f"引用不存在的文件：{name}（失效引用）")
    if len(doc.get("keywords") or []) < 5:
        issues.append("keywords 少于 5 个")
    return issues


class ZenodoContractTest(unittest.TestCase):
    def setUp(self):
        self.doc = load_zenodo()

    def test_zenodo_matches_contract(self):
        self.assertEqual([], zenodo_issues(self.doc), "Zenodo 记录不满足契约")

    def test_license_is_single_sourced(self):
        """许可必须是四源一致：LICENSE / pyproject / REUSE.toml / CITATION.cff。"""
        lic_id = str((self.doc.get("license") or {}).get("id") or "")
        self.assertEqual(repo_license_id(), lic_id, "Zenodo 许可与 LICENSE 不一致")
        self.assertEqual(citation_license(), lic_id, "Zenodo 许可与 CITATION 不一致")
        self.assertIn(lic_id, reuse_spdx_ids(), "许可不在 REUSE 声明里")
        self.assertTrue(pyproject_declares_mit(), "pyproject 未声明 MIT")

    def test_no_stale_file_references(self):
        """描述与备注里引用的根层文档必须存在（旧记录引用了三个不存在的文件）。"""
        text = str(self.doc.get("description") or "") + "\n" + str(self.doc.get("notes") or "")
        self.assertEqual([], stale_file_refs(text), "Zenodo 记录引用了不存在的文件")

    def test_contract_catches_broken_zenodo(self):
        """变异自证：许可改 AGPL / title 漂移 / 失效引用 / 删 creators——都必须报。"""
        import copy

        bad_license = copy.deepcopy(self.doc)
        bad_license["license"]["id"] = "AGPL-3.0-only"
        self.assertTrue(any("LICENSE" in i for i in zenodo_issues(bad_license)),
                        "许可与 LICENSE 不一致必须报")
        bad_title = copy.deepcopy(self.doc)
        bad_title["title"] = "NinFenz"
        self.assertTrue(any("CITATION" in i for i in zenodo_issues(bad_title)),
                        "title 与 CITATION 漂移必须报")
        bad_ref = copy.deepcopy(self.doc)
        bad_ref["notes"] = "许可见 LICENSING.md 与 COMMERCIAL.md"
        self.assertTrue(any("LICENSING.md" in i for i in zenodo_issues(bad_ref)),
                        "失效文件引用必须报")
        bad_creators = copy.deepcopy(self.doc)
        bad_creators["creators"] = []
        self.assertTrue(any("creators" in i for i in zenodo_issues(bad_creators)),
                        "删掉 creators 必须报")
        with tempfile.TemporaryDirectory() as tmp:
            bad_json = Path(tmp) / "bad.json"
            bad_json.write_text("{not json", encoding="utf-8")
            with self.assertRaises(ValueError):
                load_zenodo(bad_json)
        with self.assertRaises(ValueError):
            load_zenodo(ROOT / "no_such_zenodo.json")


if __name__ == "__main__":
    unittest.main()
