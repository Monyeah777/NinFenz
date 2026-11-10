#!/usr/bin/env python3
"""REUSE 契约判据：许可声明须结构合法、覆盖完整、override 不空转、许可文本双向闭合（2026-11-10）。

为什么必须有：REUSE.toml 是许可分层唯一的机读声明，写错不会让任何测试红（原判据只查
「声明的 SPDX 是否有 LICENSES/ 支撑」），但会让每个文件在合规扫描里带上错误许可。
本件把「一份能用的 REUSE 声明」钉成契约：TOML 结构、聚合覆盖、override glob 必须命中真实文件、
声明的许可与 LICENSES/ 文本双向闭合、聚合许可与仓库主许可（LICENSE / CITATION / Zenodo）一致。

范围：只判 REUSE.toml。同族判据：test_governance_docs（REUSE ⇄ LICENSES 存在性）、
test_zenodo_contract（存档许可）、test_citation_contract（引用许可）。
"""
import re
import subprocess
import tempfile
import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REUSE = ROOT / "REUSE.toml"
LICENSE = ROOT / "LICENSE"
LICENSES = ROOT / "LICENSES"

#: precedence 的合法取值（REUSE 规范：aggregate / override / closest）
PRECEDENCE = ("aggregate", "override", "closest")
#: LicenseRef 命名规则（SPDX：字母数字与 . -，不含下划线/空格）
LICENSE_ID_RE = re.compile(r"^(?:[A-Za-z0-9.+-]+|LicenseRef-[A-Za-z0-9.-]+)$")
#: 投稿面根目录（其下文件必须显式落在 override 上，否则会被宽表静默判 MIT）
SUBMISSION_ROOTS = ("library", "community")
#: 投稿面里「登记件」白名单：仓库自己的索引 / 登记 / 摘要件，属 MIT 面
SUBMISSION_WHITELIST = (
    "library/INDEX.md", "library/ALIAS.md", "library/intake.json", "library/RECEIPTS.json",
)


def load_reuse(path: Path = REUSE) -> dict:
    """读 REUSE.toml（缺失 / 非法 TOML / 非映射 → ValueError）。"""
    try:
        doc = tomllib.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValueError(f"REUSE.toml 不可读：{exc}") from exc
    except tomllib.TOMLDecodeError as exc:
        raise ValueError(f"REUSE.toml 不是合法 TOML：{exc}") from exc
    if not isinstance(doc, dict):
        raise ValueError("REUSE.toml 根节点必须是映射")
    return doc


def repo_license_id() -> str:
    """仓库主许可真源：LICENSE 首行 `MIT License` → SPDX `MIT`。"""
    head = LICENSE.read_text(encoding="utf-8").splitlines()[0].strip()
    if head != "MIT License":
        raise ValueError(f"LICENSE 首行不是可识别的许可标题：{head!r}")
    return "MIT"


def glob_hits(pattern: str, root: Path = ROOT) -> list:
    """glob 命中的真实文件（目录不算；用于「override 不空转」判定）。"""
    try:
        if pattern.endswith("/**") or pattern.endswith("/**/*"):
            base = pattern.rsplit("**", 1)[0].rstrip("/")
            start = root / base if base else root
            if not start.is_dir():
                return []
            return [p for p in start.rglob("*") if p.is_file()]
        return [p for p in root.glob(pattern) if p.is_file()]
    except (OSError, ValueError):
        return []


def pattern_regex(pattern: str) -> re.Pattern:
    """REUSE 路径 glob → 正则（* 不跨 /，** 跨 /）。"""
    out = ["^"]
    i = 0
    while i < len(pattern):
        if pattern.startswith("**", i):
            out.append(".*")
            i += 2
        elif pattern[i] == "*":
            out.append("[^/]*")
            i += 1
        else:
            out.append(re.escape(pattern[i]))
            i += 1
    out.append("$")
    return re.compile("".join(out))


def tracked_submission_files(root: Path = ROOT) -> list:
    """git 追踪面里 library/ 与 community/ 下的文件（投稿面全覆盖检查的输入）。"""
    try:
        proc = subprocess.run(["git", "-C", str(root), "ls-files", "-z"],
                              capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=120)
    except (OSError, subprocess.SubprocessError) as exc:
        raise ValueError(f"git ls-files 不可用：{exc}") from exc
    rels = [rel for rel in proc.stdout.split("\0") if rel]
    return [rel for rel in rels if rel.split("/")[0] in SUBMISSION_ROOTS]


def submission_uncovered(doc: dict, root: Path = ROOT) -> list:
    """投稿面里既非白名单、又没被任何 override 命中的文件（会被宽表静默吞成 MIT）。"""
    overrides = []
    for ann in doc.get("annotations") or []:
        if str((ann or {}).get("precedence") or "") == "override":
            overrides += [pattern_regex(str(p)) for p in ann.get("path") or []]
    uncovered = []
    for rel in tracked_submission_files(root):
        if rel in SUBMISSION_WHITELIST:
            continue
        if any(rx.match(rel) for rx in overrides):
            continue
        uncovered.append(rel)
    return uncovered


def annotation_license_ids(doc: dict) -> set:
    """所有 annotation 声明的 SPDX 标识集合。"""
    ids = set()
    for ann in doc.get("annotations") or []:
        ids.add(str((ann or {}).get("SPDX-License-Identifier") or "").strip())
    return {i for i in ids if i}


def license_texts() -> set:
    """LICENSES/ 下许可文本的 SPDX 标识集合。"""
    if not LICENSES.is_dir():
        return set()
    return {p.stem for p in LICENSES.glob("*.txt")}


def reuse_issues(doc: dict, text: str = "", root: Path = ROOT) -> list:
    """REUSE 契约问题列表（纯函数，便于变异自证）。"""
    issues = []
    if doc.get("version") != 1:
        issues.append(f"version 必须为 1，实际 {doc.get('version')!r}")
    for key in ("SPDX-PackageName", "SPDX-PackageSupplier", "SPDX-PackageDownloadLocation"):
        if not str(doc.get(key) or "").strip():
            issues.append(f"缺本仓包级元数据（非 REUSE 3.3 字段）：{key}")
    anns = doc.get("annotations") or []
    if not anns:
        issues.append("缺 [[annotations]]（全仓许可无从声明）")
    aggregate = [a for a in anns if str((a or {}).get("precedence") or "") == "aggregate"]
    if not aggregate:
        issues.append("缺 precedence=aggregate 的聚合声明")
    else:
        covered = [p for a in aggregate for p in (a.get("path") or [])]
        if not any(str(p).strip() in ("**/*", "**") for p in covered):
            issues.append("聚合声明的 path 未覆盖全仓（应为 **/*）")
        agg_ids = {str(a.get("SPDX-License-Identifier") or "").strip() for a in aggregate}
        want = repo_license_id()
        if agg_ids != {want}:
            issues.append(f"聚合许可与 LICENSE 不一致：{sorted(agg_ids)} ≠ {want!r}")
    agg_idx = [i for i, a in enumerate(anns)
               if str((a or {}).get("precedence") or "") == "aggregate"]
    ovr_idx = [i for i, a in enumerate(anns)
               if str((a or {}).get("precedence") or "") == "override"]
    if agg_idx and ovr_idx and max(agg_idx) > min(ovr_idx):
        issues.append("顺序错误：override 必须排在聚合声明之后（否则被宽表吞掉）")
    for i, ann in enumerate(anns):
        ann = ann or {}
        prec = str(ann.get("precedence") or "").strip()
        if prec not in PRECEDENCE:
            issues.append(f"annotations[{i}] 的 precedence 非法：{prec!r}")
        paths = [str(p).strip() for p in (ann.get("path") or [])]
        if not paths:
            issues.append(f"annotations[{i}] 缺 path")
        if not str(ann.get("SPDX-FileCopyrightText") or "").strip():
            issues.append(f"annotations[{i}] 缺 SPDX-FileCopyrightText")
        if not str(ann.get("SPDX-License-Identifier") or "").strip():
            issues.append(f"annotations[{i}] 缺 SPDX-License-Identifier")
        if prec == "override":
            for pattern in paths:
                if not glob_hits(pattern, root):
                    issues.append(f"override glob 空转（未命中任何文件）：{pattern}")
    declared = annotation_license_ids(doc)
    texts = license_texts()
    for lic in sorted(declared - texts):
        issues.append(f"声明的许可缺 LICENSES/{lic}.txt")
    for lic in sorted(texts - declared):
        issues.append(f"LICENSES/{lic}.txt 未被任何 annotation 引用（单向声明）")
    for lic in sorted(declared):
        if not LICENSE_ID_RE.match(lic):
            issues.append(f"许可标识不合规（SPDX 命名）：{lic!r}")
    if "投稿" not in text:
        issues.append("缺投稿面 override 的口径注释（条款范围必须写明）")
    return issues


class ReuseContractTest(unittest.TestCase):
    def setUp(self):
        self.text = REUSE.read_text(encoding="utf-8")
        self.doc = load_reuse()

    def test_reuse_matches_contract(self):
        self.assertEqual([], reuse_issues(self.doc, self.text), "REUSE.toml 不满足契约")

    def test_override_globs_are_not_empty(self):
        """override 的每个 glob 都必须命中真实文件——空转的 override 等于没声明。"""
        for ann in self.doc.get("annotations") or []:
            if str((ann or {}).get("precedence") or "") != "override":
                continue
            for pattern in ann.get("path") or []:
                self.assertTrue(glob_hits(str(pattern)), f"override glob 空转：{pattern}")

    def test_license_texts_bidirectional(self):
        """声明 ⇄ LICENSES/ 双向闭合：声明的必须有文本，有文本的必须被声明。"""
        declared = annotation_license_ids(self.doc)
        texts = license_texts()
        self.assertEqual(set(), declared - texts, "声明了但缺许可文本")
        self.assertEqual(set(), texts - declared, "有许可文本但未声明")

    def test_override_after_aggregate(self):
        """顺序是语义：override 必须排在聚合声明之后（反序会被宽表吞掉）。"""
        precs = [str((a or {}).get("precedence") or "")
                 for a in (self.doc.get("annotations") or [])]
        agg = [i for i, p in enumerate(precs) if p == "aggregate"]
        ovr = [i for i, p in enumerate(precs) if p == "override"]
        self.assertTrue(agg and ovr, "必须同时有聚合与 override 声明")
        self.assertLess(max(agg), min(ovr), "override 必须在聚合声明之后")

    def test_submission_surface_is_declared(self):
        """投稿面每个文件都必须显式落在 override 或白名单上（否则被宽表静默判 MIT）。"""
        uncovered = submission_uncovered(self.doc)
        self.assertEqual([], uncovered, f"投稿面未被 override 覆盖：{uncovered[:5]}")
        for rel in SUBMISSION_WHITELIST:
            self.assertTrue((ROOT / rel).is_file(), f"白名单文件不在场：{rel}")

    def test_aggregate_matches_repo_license(self):
        """聚合许可必须与 LICENSE 真源一致（并与 CITATION/Zenodo 链条同源）。"""
        aggregate = [a for a in (self.doc.get("annotations") or [])
                     if str((a or {}).get("precedence") or "") == "aggregate"]
        self.assertTrue(aggregate, "缺聚合声明")
        ids = {str(a.get("SPDX-License-Identifier") or "").strip() for a in aggregate}
        self.assertEqual({repo_license_id()}, ids, "聚合许可漂移")

    def test_contract_catches_broken_reuse(self):
        """变异自证：删 version / 非法 precedence / 空转 override / 许可漂移 / 坏 TOML 都必须报。"""
        import copy

        no_version = copy.deepcopy(self.doc)
        no_version.pop("version", None)
        self.assertTrue(any("version" in i for i in reuse_issues(no_version, self.text)),
                        "删掉 version 必须报")
        bad_prec = copy.deepcopy(self.doc)
        bad_prec["annotations"].append({"path": ["docs/**"], "precedence": "highest",
                                        "SPDX-FileCopyrightText": "x",
                                        "SPDX-License-Identifier": "MIT"})
        self.assertTrue(any("precedence" in i for i in reuse_issues(bad_prec, self.text)),
                        "非法 precedence 必须报")
        empty_glob = copy.deepcopy(self.doc)
        empty_glob["annotations"].append({"path": ["no_such_dir/**"], "precedence": "override",
                                          "SPDX-FileCopyrightText": "x",
                                          "SPDX-License-Identifier": "MIT"})
        self.assertTrue(any("空转" in i for i in reuse_issues(empty_glob, self.text)),
                        "空转 override 必须报")
        reordered = copy.deepcopy(self.doc)
        reordered["annotations"] = [a for a in reordered["annotations"]
                                    if (a or {}).get("precedence") != "aggregate"] + [
            a for a in reordered["annotations"]
            if (a or {}).get("precedence") == "aggregate"]
        self.assertTrue(any("顺序" in i for i in reuse_issues(reordered, self.text)),
                        "override 抢在聚合前必须报")
        bad_id = copy.deepcopy(self.doc)
        bad_id["annotations"].append({"path": ["docs/**"], "precedence": "override",
                                      "SPDX-FileCopyrightText": "x",
                                      "SPDX-License-Identifier": "LicenseRef_Bad"})
        self.assertTrue(any("命名" in i for i in reuse_issues(bad_id, self.text)),
                        "非法 LicenseRef 命名必须报")
        drift = copy.deepcopy(self.doc)
        for ann in drift["annotations"]:
            if ann.get("precedence") == "aggregate":
                ann["SPDX-License-Identifier"] = "Apache-2.0"
        self.assertTrue(any("LICENSE" in i for i in reuse_issues(drift, self.text)),
                        "聚合许可漂移必须报")
        with tempfile.TemporaryDirectory() as tmp:
            bad_toml = Path(tmp) / "bad.toml"
            bad_toml.write_text("[[annotations]", encoding="utf-8")
            with self.assertRaises(ValueError):
                load_reuse(bad_toml)
        with self.assertRaises(ValueError):
            load_reuse(ROOT / "no_such_reuse.toml")


if __name__ == "__main__":
    unittest.main()
