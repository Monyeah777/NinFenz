#!/usr/bin/env python3
"""CITATION.cff 契约判据：引用元数据须 schema 合法、作者是真自然人、与存档双源一致（2026-11-10）。

为什么必须有：CITATION.cff 被 GitHub「Cite this repository」直接解析，写错不会让任何测试红，
但会让每一个引用者拿到错误许可或把作者当成机构。本仓实测两处缺陷：唯一作者写成 entity 的
`name:`（person 不允许 name，会被当机构），且与 .zenodo.json 并存时 Zenodo 根本不读 CFF——
双源漂移会直接进 DOI 档案。只有判据能同时守住「schema 合法」与「双源一致」。

范围：只判 CITATION.cff。同族判据：test_zenodo_contract（存档记录）、test_governance_docs（REUSE）。
契约：CFF 1.2.0 必填/无未知键 + 作者为 person（family/given）+ 许可/标题与 .zenodo.json 逐字一致
+ 「不钉版本」策略有注释与判据 + 变异自证。
"""
import json
import re
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CITATION = ROOT / "CITATION.cff"
ZENODO = ROOT / ".zenodo.json"
LICENSE = ROOT / "LICENSE"
REPO_URL = "https://github.com/Monyeah777/NinFenz"

#: CFF 1.2.0 顶层允许键（schema: additionalProperties=false，未知键即整份校验失败）
ALLOWED_KEYS = (
    "abstract", "authors", "cff-version", "commit", "contact", "date-released", "doi",
    "identifiers", "keywords", "license", "license-url", "message", "preferred-citation",
    "references", "repository-artifact", "repository-code", "title", "type", "url", "version",
)
#: person 允许键（family/given/alias/website/orcid 等；**没有 name**）
PERSON_KEYS = (
    "address", "affiliation", "alias", "city", "country", "email", "family-names",
    "fax", "given-names", "name-particle", "name-suffix", "orcid", "post-code",
    "region", "tel", "website",
)
#: 必填四项（schema required）+ 本仓要求的两项元数据
REQUIRED_KEYS = ("cff-version", "message", "title", "authors")


def load_citation(path: Path = CITATION) -> dict:
    """读 CITATION.cff（缺失 / 非法 YAML / 非映射 → ValueError）。"""
    try:
        import yaml
    except ModuleNotFoundError as exc:
        raise ValueError(f"缺 PyYAML，无法校验引用件：{exc}") from exc
    try:
        doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ValueError(f"CITATION.cff 不可读/不可解析：{exc}") from exc
    if not isinstance(doc, dict):
        raise ValueError("CITATION.cff 根节点必须是映射")
    return doc


def repo_license_id() -> str:
    """仓库许可真源：LICENSE 首行 `MIT License` → SPDX `MIT`。"""
    head = LICENSE.read_text(encoding="utf-8").splitlines()[0].strip()
    if head != "MIT License":
        raise ValueError(f"LICENSE 首行不是可识别的许可标题：{head!r}")
    return "MIT"


def zenodo() -> dict:
    """同仓 Zenodo 记录（双源一致的另一半）。"""
    try:
        doc = json.loads(ZENODO.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError(f".zenodo.json 不可读/不可解析：{exc}") from exc
    return doc if isinstance(doc, dict) else {}


def citation_author_names(doc: dict) -> set:
    """作者名集合（person 用 family/given；entity 用 name）。"""
    names = set()
    for author in doc.get("authors") or []:
        author = author or {}
        name = str(author.get("family-names") or author.get("name") or "").strip()
        if name:
            names.add(name)
    return names


def citation_issues(doc: dict, zen: dict = None) -> list:
    """CITATION 契约问题列表（纯函数，便于变异自证）。"""
    issues = []
    for key in REQUIRED_KEYS:
        if not doc.get(key):
            issues.append(f"缺必填键：{key}")
    if str(doc.get("cff-version") or "") != "1.2.0":
        got = doc.get("cff-version")
        issues.append(f"cff-version 必须是 1.2.0（schema pattern），实际 {got!r}")
    unknown = [k for k in doc if k not in ALLOWED_KEYS]
    if unknown:
        issues.append(f"出现 schema 外键（additionalProperties=false）：{unknown}")
    authors = doc.get("authors") or []
    if not authors:
        issues.append("authors 为空")
    for i, author in enumerate(authors):
        author = author or {}
        bad = [k for k in author if k not in PERSON_KEYS]
        if bad:
            issues.append(f"authors[{i}] 用了 person 不允许的键：{bad}（机构写法会被当 entity）")
        if not (author.get("family-names") or author.get("given-names")):
            issues.append(f"authors[{i}] 缺 family-names/given-names（person 必填，否则被当机构）")
    if not doc.get("license"):
        issues.append("缺 license（SPDX）")
    elif str(doc.get("license")).strip() != repo_license_id():
        issues.append(f"license 与 LICENSE 不一致：{doc.get('license')!r} ≠ {repo_license_id()!r}")
    if str(doc.get("repository-code") or "").strip() != REPO_URL:
        issues.append("repository-code 与仓库 URL 不一致")
    if str(doc.get("type") or "").strip() not in ("software", "dataset"):
        issues.append("type 必须是 software / dataset")
    if "version" in doc or "date-released" in doc:
        issues.append("本仓策略：不钉 version / date-released（会与 .zenodo.json 版本漂移）")
    doi = str(doc.get("doi") or "")
    if doi and (doi.startswith("http") or not re.match(r"^10\.\d{4,9}/", doi)):
        issues.append(f"doi 必须裸 DOI（10.xxxx/…），实际 {doi!r}")
    if zen is None:
        zen = zenodo()
    if str(zen.get("title") or "").strip() != str(doc.get("title") or "").strip():
        issues.append("title 与 .zenodo.json 不一致（双源漂移）")
    if str((zen.get("license") or {}).get("id") or "").strip() != str(doc.get("license")).strip():
        issues.append("license 与 .zenodo.json 不一致（双源漂移）")
    zen_names = {str((c or {}).get("name") or "").strip() for c in (zen.get("creators") or [])}
    if zen_names and not zen_names.issubset(citation_author_names(doc)):
        issues.append("作者与 .zenodo.json creators 不一致")
    return issues


class CitationContractTest(unittest.TestCase):
    def setUp(self):
        self.doc = load_citation()
        self.text = CITATION.read_text(encoding="utf-8")

    def test_citation_matches_contract(self):
        self.assertEqual([], citation_issues(self.doc), "CITATION.cff 不满足契约")

    def test_person_not_entity(self):
        """作者必须是 person（family/given），不能用 entity 的 name——否则被当机构。"""
        for i, author in enumerate(self.doc["authors"]):
            author = author or {}
            self.assertIn("family-names", author, f"authors[{i}] 缺 family-names")
            self.assertNotIn("name", author, f"authors[{i}] 用了 entity 的 name（person 不允许）")

    def test_zenodo_double_source(self):
        """与 .zenodo.json 的双源一致（Zenodo 存在 .zenodo.json 时不读 CFF）。"""
        zen = zenodo()
        zen_title = str(zen.get("title") or "").strip()
        cit_title = str(self.doc.get("title") or "").strip()
        self.assertEqual(zen_title, cit_title)
        self.assertEqual(str((zen.get("license") or {}).get("id") or "").strip(),
                         str(self.doc.get("license")).strip())
        self.assertEqual(zenodo(), zen)
        self.assertTrue(citation_author_names(self.doc))

    def test_version_policy_is_documented(self):
        """不钉版本必须是显式策略：文件里没有 version/date-released，且有注释说明。"""
        self.assertNotIn("version", self.doc)
        self.assertNotIn("date-released", self.doc)
        self.assertIn("不设 version", self.text, "缺「不钉版本」策略注释")

    def test_contract_catches_broken_citation(self):
        """变异自证：加 version / 许可漂移 / 作者改 entity / schema 外键 / 标题漂移——都必须报。"""
        import copy

        bad_version = copy.deepcopy(self.doc)
        bad_version["version"] = "1.0.5"
        self.assertTrue(any("version" in i for i in citation_issues(bad_version)),
                        "加了 version 必须报（策略违约）")
        bad_license = copy.deepcopy(self.doc)
        bad_license["license"] = "AGPL-3.0-only"
        self.assertTrue(any("LICENSE" in i for i in citation_issues(bad_license)),
                        "许可与 LICENSE 不一致必须报")
        bad_author = copy.deepcopy(self.doc)
        bad_author["authors"] = [{"name": "Monyeah777"}]
        author_issues = citation_issues(bad_author)
        self.assertTrue(any("person" in i or "family-names" in i for i in author_issues),
                        "作者改成 entity 必须报")
        bad_key = copy.deepcopy(self.doc)
        bad_key["repository"] = "https://example.com"
        self.assertTrue(any("schema" in i for i in citation_issues(bad_key)),
                        "schema 外键必须报")
        bad_title = copy.deepcopy(self.doc)
        bad_title["title"] = "NinFenz"
        self.assertTrue(any("zenodo" in i for i in citation_issues(bad_title)),
                        "title 与 zenodo 漂移必须报")
        with tempfile.TemporaryDirectory() as tmp:
            bad_yaml = Path(tmp) / "bad.cff"
            bad_yaml.write_text("cff-version: [", encoding="utf-8")
            with self.assertRaises(ValueError):
                load_citation(bad_yaml)
        with self.assertRaises(ValueError):
            load_citation(ROOT / "no_such_citation.cff")


if __name__ == "__main__":
    unittest.main()
