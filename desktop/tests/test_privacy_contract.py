#!/usr/bin/env python3
"""隐私/数据生命周期契约（NF-Final WP-0B，P0 盲区 BL-01 的 closure 判据）。

真源 = `protocol/privacy.json`（`nf-privacy/1`）；人读面 = `PRIVACY.md` +
`docs/privacy/{DATA_MAP,DPIA,RETENTION}.md` + `docs/qa/PRIVACY_QA.md`。判据：
1. 登记：四级分类/四种保留模式词表固定；8 个数据类 id 固定；仓库内位置真实在场；
   非仓库位置必须写 external_reason；restricted 不得声明外部处理者；
2. 删除：每类的 `{kind,ref}` 过 `core.delete_evidence.check`；机密/受限必须 `blame_required`
   且 `missing_blame(require_blame=True)` 能红（删除失败面）；
3. 保留：ephemeral 位置必须被 `.gitignore` 覆盖（`git check-ignore` 机检）；
   immutable 类删除证据类型限 backup/vcs；
4. 扫描：PII（邮箱/手机号）用 `core.privacy_scan`、凭据用 `secret_guard`（唯一实现）；
   声明面 `results/`、`protocol/` 零命中且无 skipped；fixture 检测/脱敏抽样通过；
5. 文档一致性：每个 DC id 出现在 DATA_MAP 与 RETENTION；DPIA 覆盖 LINDDUN 七类；
   禁用词（合规/认证/不可抵赖）只允许出现在否定语境；
6. 变异自证：删类/错分类/缺 external_reason/缺删除 ref/受限类带处理者/重复 id/坏工具路径，
   判据都必须红。
"""
import copy
import json
import re
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import delete_evidence as de  # noqa: E402
from core import privacy_scan as ps  # noqa: E402
from core.meta_cockpit import secret_guard as sg  # noqa: E402

REG = ROOT / "protocol" / "privacy.json"
DOCS = {
    "PRIVACY": ROOT / "PRIVACY.md",
    "DATA_MAP": ROOT / "docs" / "privacy" / "DATA_MAP.md",
    "DPIA": ROOT / "docs" / "privacy" / "DPIA.md",
    "RETENTION": ROOT / "docs" / "privacy" / "RETENTION.md",
    "PRIVACY_QA": ROOT / "docs" / "qa" / "PRIVACY_QA.md",
}
CLASSIFICATION = {"public", "internal", "confidential", "restricted"}
RETENTION_MODES = {"user-managed", "ephemeral", "immutable", "rotation"}
EXPECTED_IDS = tuple("DC-%02d" % i for i in range(1, 9))
NEGATION = ("不", "非", "无", "未")


def _json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _text(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def registry_issues(doc, root=ROOT):
    """登记表判据（供正例与变异共用）。"""
    issues = []
    if doc.get("schema") != "nf-privacy/1":
        return ["schema 不匹配（期望 nf-privacy/1）"]
    if list((doc.get("classification_vocabulary") or {}).keys()) != \
            ["public", "internal", "confidential", "restricted"]:
        issues.append("分类词表必须恰为 public/internal/confidential/restricted")
    if set((doc.get("retention_modes") or {}).keys()) != RETENTION_MODES:
        issues.append("保留模式词表必须恰为 %s" % sorted(RETENTION_MODES))
    classes = doc.get("data_classes") or []
    ids = [str(c.get("id")) for c in classes if isinstance(c, dict)]
    if tuple(ids) != EXPECTED_IDS:
        issues.append("数据类 id 必须恰为 %s（实际 %s）" % (list(EXPECTED_IDS), ids))
    if len(ids) != len(set(ids)):
        issues.append("数据类 id 重复：%s" % ids)
    for c in classes:
        if not isinstance(c, dict):
            issues.append("data_classes 含非对象")
            continue
        cid = str(c.get("id"))
        cls = str(c.get("classification"))
        if cls not in CLASSIFICATION:
            issues.append("%s 的 classification 非法：%s" % (cid, cls))
        if str(c.get("storage")) != "local-only":
            issues.append("%s 的 storage 必须 local-only（本仓不做外部处理）" % cid)
        if not isinstance(c.get("processors"), list):
            issues.append("%s 缺 processors 列表" % cid)
        if cls == "restricted" and (c.get("processors") or c.get("repo_local")):
            issues.append("%s 是 restricted，不得声明处理者/入仓" % cid)
        locs = c.get("locations") or []
        if not locs:
            issues.append("%s 缺 locations" % cid)
        if c.get("repo_local"):
            for rel in locs:
                if not (Path(root) / rel).exists():
                    issues.append("%s 的仓库位置不在场：%s" % (cid, rel))
        elif not str(c.get("external_reason") or "").strip():
            issues.append("%s 非仓库位置必须写 external_reason" % cid)
        ret = c.get("retention") or {}
        if ret.get("mode") not in RETENTION_MODES:
            issues.append("%s 的保留模式非法：%s" % (cid, ret.get("mode")))
        dele = c.get("deletion") or {}
        if str(dele.get("evidence_kind")) not in de.KINDS:
            issues.append("%s 的删除证据类型非法：%s" % (cid, dele.get("evidence_kind")))
        removals = [{"target": cid, "kind": str(dele.get("evidence_kind")),
                     "ref": str(dele.get("method") or "")}]
        for i in de.check(removals):
            issues.append("%s 删除证据不合法：%s" % (cid, i))
        want_blame = cls in ("confidential", "restricted")
        if bool(dele.get("blame_required")) != want_blame:
            issues.append("%s 的 blame_required 与分级不符（机密/受限必须 true）" % cid)
    for rule in doc.get("minimization_rules") or []:
        rel = str(rule.get("evidence"))
        if not (Path(root) / rel).is_file():
            issues.append("最小化规则 %s 的证据不在场：%s" % (rule.get("id"), rel))
    scan = doc.get("pii_scan") or {}
    for key in ("tool", "secrets_tool"):
        mod = str(scan.get(key) or "").replace(".", "/") + ".py"
        if not (Path(root) / "desktop" / "src" / mod).is_file():
            issues.append("pii_scan.%s 指向不存在的模块：%s" % (key, scan.get(key)))
    if not scan.get("surfaces"):
        issues.append("pii_scan 缺扫描面")
    for rel in scan.get("surfaces") or []:
        if not (Path(root) / rel).exists():
            issues.append("扫描面不在场：%s" % rel)
    rule = doc.get("deletion_rule") or {}
    if set(rule.get("kinds") or []) != set(de.KINDS):
        issues.append("删除 kind 词表必须与 core.delete_evidence.KINDS 同源")
    return issues


def doc_issues(doc, texts):
    """文档与真源一致性（供正例与变异共用）。"""
    issues = []
    ids = [str(c.get("id")) for c in doc.get("data_classes") or []]
    for key, text in texts.items():
        if not text.strip():
            issues.append("文档为空：%s" % DOCS[key])
    data_map = texts.get("DATA_MAP", "")
    for cid in ids:
        if cid not in data_map:
            issues.append("DATA_MAP 缺数据类：%s" % cid)
    retention = texts.get("RETENTION", "")
    for cid in ids:
        if cid not in retention:
            issues.append("RETENTION 缺数据类：%s" % cid)
    # 反向：文档里出现、真源没登记的数据类 = 第二真源（删类变异靠这条红）
    for key, text in (("DATA_MAP", data_map), ("RETENTION", retention)):
        extra = sorted(set(re.findall(r"DC-\d{2}", text)) - set(ids))
        if extra:
            issues.append("%s 引用了未登记的数据类：%s" % (key, extra))
    for mode in RETENTION_MODES:
        if mode not in retention:
            issues.append("RETENTION 缺保留模式：%s" % mode)
    dpia = texts.get("DPIA", "")
    for mark in ("链接", "识别", "不可否认", "可检测性", "披露", "无意识", "不合规"):
        if mark not in dpia:
            issues.append("DPIA 缺 LINDDUN 类别：%s" % mark)
    return issues


def overclaim_lines(texts):
    """禁用词只在否定语境（返回违规行）。"""
    bad = []
    for key, text in texts.items():
        for line in text.splitlines():
            for word in ("合规", "认证", "不可抵赖"):
                if word in line and not any(m in line for m in NEGATION):
                    bad.append("%s:%s" % (key, line.strip()))
    return bad


class PrivacyContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc = _json(REG)
        cls.texts = {k: _text(p) for k, p in DOCS.items()}

    def test_registry_valid(self):
        self.assertEqual([], registry_issues(self.doc))

    def test_docs_consistent(self):
        for key, path in DOCS.items():
            self.assertTrue(path.is_file(), "缺文档：%s" % path)
        self.assertEqual([], doc_issues(self.doc, self.texts))
        self.assertEqual([], overclaim_lines(self.texts), "禁用词出现在正向语境")

    def test_deletion_evidence_positive(self):
        for c in self.doc["data_classes"]:
            removals = [{"target": c["id"], "kind": c["deletion"]["evidence_kind"],
                         "ref": c["deletion"]["method"]}]
            self.assertEqual([], de.check(removals), c["id"])

    def test_deletion_failure_red(self):
        self.assertTrue(de.check([{"target": "DC-X", "kind": "vcs", "ref": ""}]),
                        "缺 ref 必须红")
        self.assertTrue(de.check([{"target": "DC-X", "kind": "magic", "ref": "x"}]),
                        "非法 kind 必须红")
        for c in self.doc["data_classes"]:
            if not c["deletion"].get("blame_required"):
                continue
            removals = [{"target": c["id"], "kind": c["deletion"]["evidence_kind"],
                         "ref": c["deletion"]["method"]}]
            self.assertTrue(de.missing_blame(removals, require_blame=True),
                            "%s 缺 blame 必须红" % c["id"])

    def test_retention_constraints(self):
        for c in self.doc["data_classes"]:
            mode = c["retention"]["mode"]
            if c["id"] == "DC-05":
                self.assertIn(".nf-logs/", " ".join(c["locations"]))
        proc = subprocess.run(["git", "check-ignore", "-q", ".nf-logs/probe.log"],
                              cwd=str(ROOT))
        self.assertEqual(0, proc.returncode, "ephemeral 落点未被 .gitignore 覆盖")
        for c in self.doc["data_classes"]:
            if c["retention"]["mode"] != "immutable":
                continue
            self.assertIn(c["deletion"]["evidence_kind"], ("backup", "vcs"),
                          "%s: immutable 删除必须走归档/版本证据" % c["id"])

    def test_privacy_scan_fixture_and_redaction(self):
        text = ("联系人邮箱 a.b@example.com，手机 13800138000；"
                "token sk-" "abcdefghijklmnopqrst 与 -----BEGIN RSA PRIVATE KEY-----")
        self.assertEqual(["email", "cn-mobile"], ps.scan_text(text))
        self.assertTrue(sg.scan_text(text), "凭据检测必须命中")
        cleaned = ps.redact(text)
        self.assertEqual([], ps.scan_text(cleaned), "脱敏后不得残留 PII")
        self.assertEqual([], sg.scan_text(cleaned), "脱敏后不得残留凭据")
        self.assertGreaterEqual(cleaned.count(ps.REDACTION), 3, "脱敏抽样：至少 3 处替换")
        for secret in ("a.b@example.com", "13800138000", "sk-" "abcdefghijklmnopqrst"):
            self.assertNotIn(secret, cleaned)

    def test_declared_surfaces_clean(self):
        scan = self.doc["pii_scan"]
        result = ps.scan_paths(str(ROOT), scan["surfaces"])
        self.assertEqual([], result["findings"], "声明面出现 PII：%s" % result["findings"])
        self.assertEqual([], result["skipped"], "有不可判定件（必须显式处理）：%s"
                         % result["skipped"])
        for rel in scan["surfaces"]:
            base = ROOT / rel
            paths = [base] if base.is_file() else sorted(base.rglob("*")) if base.is_dir() else []
            for path in paths:
                if not path.is_file() or path.suffix.lower() not in ps.TEXT_EXT:
                    continue
                try:
                    text = path.read_text(encoding="utf-8")
                except (OSError, UnicodeDecodeError):
                    continue
                self.assertEqual([], sg.scan_text(text), "声明面出现凭据：%s" % path)

    def test_mutation_self_proof(self):
        dropped = copy.deepcopy(self.doc)
        dropped["data_classes"] = [c for c in dropped["data_classes"] if c["id"] != "DC-04"]
        self.assertTrue(registry_issues(dropped), "删数据类必须红")
        self.assertTrue(doc_issues(dropped, self.texts), "文档仍引用被删类必须红")

        bad_class = copy.deepcopy(self.doc)
        bad_class["data_classes"][0]["classification"] = "secret"
        self.assertTrue(registry_issues(bad_class), "非法分级必须红")

        no_reason = copy.deepcopy(self.doc)
        next(c for c in no_reason["data_classes"] if not c["repo_local"])["external_reason"] = ""
        self.assertTrue(registry_issues(no_reason), "缺 external_reason 必须红")

        no_ref = copy.deepcopy(self.doc)
        no_ref["data_classes"][2]["deletion"]["method"] = ""
        self.assertTrue(registry_issues(no_ref), "缺删除 ref 必须红")

        restricted_processor = copy.deepcopy(self.doc)
        next(c for c in restricted_processor["data_classes"]
             if c["classification"] == "restricted")["processors"] = [{"name": "x"}]
        self.assertTrue(registry_issues(restricted_processor), "受限类带处理者必须红")

        dup = copy.deepcopy(self.doc)
        dup["data_classes"].append(copy.deepcopy(dup["data_classes"][0]))
        self.assertTrue(registry_issues(dup), "重复 id 必须红")

        bad_tool = copy.deepcopy(self.doc)
        bad_tool["pii_scan"]["tool"] = "core.nonexistent_privacy"
        self.assertTrue(registry_issues(bad_tool), "坏扫描工具路径必须红")


if __name__ == "__main__":
    unittest.main()
