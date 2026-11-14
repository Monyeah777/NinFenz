"""法务/许可/IP/出口 + 开源治理登记（`nf-legal/1`）：把「用什么许可、怎么审计」做成可复算判据。

为什么（NF-Final WP-0C，P1 盲区 BL-07/BL-10）：许可/出口/商标/治理最容易「文档写了就算」。
本模块把事实与声称对齐：
- **许可**：SPDX id 必须与 LICENSE/REUSE 文本一致；投稿面 LicenseRef 的文本与覆盖范围必须真实存在；
  方案假设（AGPL/双许可）与本仓实际（MIT + LicenseRef）不一致时，登记里显式写偏差，不虚构；
- **第三方**：NOTICE/生成器/requirements/SBOM 在场；「运行时零第三方」用 pyproject 与 npm package.json 机检；
- **商标/署名**：规则与非背书条款成文；
- **合同**：四类模板登记（服务/试点/保密/数据处理），状态诚实（template-in-doc）；
- **出口**：加密组件清单逐件在场 + 评审触发条件 + 不构成法律意见；
- **开源治理**：贡献/行为准则/维护者/安全/支持/GOVERNANCE/CHANGELOG 与发布、废弃、SemVer、Scorecard 登记。
纪律：不提供法律意见；不声称合规/认证。
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

try:  # Python 3.11 stdlib
    import tomllib
except Exception:  # pragma: no cover - 3.10 及以下没有 tomllib
    tomllib = None

SCHEMA = "nf-legal/1"
REL = "protocol/legal.json"
GUIDE = "修复指引："
CONTRACT_TYPES = ("service", "pilot", "nda", "dpa")


def load(root: str = ".") -> Dict[str, Any]:
    path = Path(root) / REL
    if not path.is_file():
        raise ValueError("缺 %s（%s 补法务登记）" % (REL, GUIDE))
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError(REL + " 不是合法 JSON：" + str(exc)) from exc
    if not isinstance(doc, dict) or str(doc.get("schema")) != SCHEMA:
        raise ValueError(REL + " schema 不匹配（" + GUIDE + "需要 " + SCHEMA + "）")
    return doc


def _exists(root: str, rel: str) -> bool:
    return (Path(root) / str(rel)).is_file()


def _license_expression_ok(expr: str) -> bool:
    """SPDX 表达式词法体检（只判语法形态；兼容性判断不是门禁的活）。"""
    text = str(expr or "").strip()
    if not text:
        return False
    if text in ("专有", "未声明"):
        return True
    tokens = re.findall(r"\(|\)|[A-Za-z0-9.+\-]+", text)
    if "".join(tokens) != re.sub(r"\s+", "", text):
        return False
    if text.count("(") != text.count(")"):
        return False
    return bool(tokens)


def _package_json_deps(root: str) -> Any:
    path = Path(root) / "packaging" / "npm" / "package.json"
    if not path.is_file():
        return "missing"
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return "invalid"
    return doc.get("dependencies")


def _pyproject_deps(root: str) -> Any:
    path = Path(root) / "pyproject.toml"
    if not path.is_file() or tomllib is None:
        return "unreadable"
    try:
        doc = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return "invalid"
    return (doc.get("project") or {}).get("dependencies")


def _reuse_annotations(root: str) -> List[Dict[str, Any]]:
    if tomllib is None:
        return []
    path = Path(root) / "REUSE.toml"
    if not path.is_file():
        return []
    try:
        doc = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return list(doc.get("annotations") or [])


def validate(doc: Dict[str, Any], root: str = ".") -> List[str]:
    issues: List[str] = []
    lic = doc.get("license") or {}
    spdx = str(lic.get("spdx") or "")
    if not spdx or not _license_expression_ok(spdx):
        issues.append("license.spdx 非法：%s" % spdx)
    for field in ("file", "text"):
        if not _exists(root, str(lic.get(field) or "")):
            issues.append("license.%s 不在场：%s" % (field, lic.get(field)))
    if spdx == "MIT":  # 与本仓实际文本对齐（换许可须同时换文本与登记）
        try:
            head = (Path(root) / "LICENSE").read_text(encoding="utf-8")
            if "MIT License" not in head:
                issues.append("LICENSE 文本与 spdx=MIT 不一致（%s 换许可须同步文本/REUSE/登记）" % GUIDE)
        except OSError:
            pass
    community = lic.get("community_license") or {}
    if not str(community.get("spdx") or "").startswith("LicenseRef-"):
        issues.append("community_license 必须用 LicenseRef-<自定义> 显式自造许可")
    if not _exists(root, str(community.get("text") or "")):
        issues.append("community_license.text 不在场：%s" % community.get("text"))
    if not isinstance(community.get("scope"), list) or not community.get("scope"):
        issues.append("community_license 缺 scope（覆盖哪些投稿面）")
    reuse = doc.get("reuse") or {}
    if not _exists(root, str(reuse.get("toml") or "")):
        issues.append("reuse.toml 不在场：%s" % reuse.get("toml"))
    annotations = _reuse_annotations(root)
    if not annotations:
        issues.append("REUSE.toml 解析不出 annotations（%s 修 TOML）" % GUIDE)
    aggregate = [a for a in annotations if str(a.get("precedence")) == "aggregate"]
    if aggregate and str(aggregate[0].get("SPDX-License-Identifier")) != str(reuse.get("aggregate_license")):
        issues.append("REUSE 聚合许可 %r ≠ 登记 %r"
                      % (aggregate[0].get("SPDX-License-Identifier"), reuse.get("aggregate_license")))
    if str(reuse.get("aggregate_license")) != spdx:
        issues.append("reuse 聚合许可 %r ≠ license.spdx %r（换许可须同步 LICENSE/REUSE/登记，%s）"
                      % (reuse.get("aggregate_license"), spdx, GUIDE))
    overrides = [a for a in annotations if str(a.get("precedence")) == "override"]
    for scope in community.get("scope") or []:
        if not any(scope in [str(p) for p in (a.get("path") or [])] for a in overrides):
            issues.append("REUSE override 缺投稿面覆盖：%s" % scope)
    third = doc.get("third_party") or {}
    for field in ("notice", "generator", "sbom"):
        if not _exists(root, str(third.get(field) or "")):
            issues.append("third_party.%s 不在场：%s" % (field, third.get(field)))
    for rel in third.get("requirements") or []:
        if not _exists(root, str(rel)):
            issues.append("third_party.requirements 不在场：%s" % rel)
    deps = _pyproject_deps(root)
    if deps != []:
        issues.append("pyproject [project].dependencies 必须为空（运行时零第三方；实际 %r）" % (deps,))
    npm = _package_json_deps(root)
    if npm not in (None, {}):
        issues.append("npm package.json 不得有 dependencies（实际 %r）" % (npm,))
    trade = doc.get("trademark") or {}
    if not str(trade.get("name") or "").strip():
        issues.append("trademark 缺 name")
    if len(trade.get("rules") or []) < 2:
        issues.append("trademark.rules 至少 2 条（使用/分发边界）")
    if "不得" not in str(trade.get("no_endorsement") or ""):
        issues.append("trademark 缺非背书条款（不得暗示官方认证/背书）")
    if not str(trade.get("attribution") or "").strip():
        issues.append("trademark 缺 attribution（署名口径）")
    contracts = doc.get("contracts") or []
    types = [str(c.get("type")) for c in contracts if isinstance(c, dict)]
    if sorted(types) != sorted(CONTRACT_TYPES):
        issues.append("contracts 必须恰覆盖 %s（实际 %s）" % (list(CONTRACT_TYPES), types))
    for item in contracts:
        if not isinstance(item, dict):
            issues.append("contracts 含非对象")
            continue
        if not _exists(root, str(item.get("path") or "")):
            issues.append("合同模板 %s 的 path 不在场：%s" % (item.get("id"), item.get("path")))
        if str(item.get("status")) not in ("template-in-doc", "signed-external", "none"):
            issues.append("合同 %s 的 status 非法：%s" % (item.get("id"), item.get("status")))
    exp = doc.get("export") or {}
    comps = exp.get("crypto_components") or []
    if not comps:
        issues.append("export.crypto_components 为空（加密组件必须显式登记）")
    for rel in comps:
        if not _exists(root, str(rel)):
            issues.append("加密组件不在场：%s" % rel)
    if not exp.get("review_trigger"):
        issues.append("export 缺 review_trigger（何时须做出口/制裁评审）")
    if not str(exp.get("not_legal_advice") or "").strip():
        issues.append("export 缺 not_legal_advice（不构成法律意见）")
    oss = doc.get("oss_governance") or {}
    files = oss.get("files") or {}
    for key in ("contributing", "code_of_conduct", "maintainers", "security",
                "support", "governance", "changelog"):
        if not _exists(root, str(files.get(key) or "")):
            issues.append("oss_governance.files.%s 不在场：%s" % (key, files.get(key)))
    for key in ("release_policy", "deprecation_policy"):
        if not str(oss.get(key) or "").strip():
            issues.append("oss_governance 缺 %s" % key)
    if not _exists(root, str((oss.get("scorecard") or {}).get("workflow") or "")):
        issues.append("scorecard workflow 不在场：%s" % (oss.get("scorecard") or {}).get("workflow"))
    boundary = " ".join(str(x) for x in doc.get("claims_boundary") or [])
    for word in ("不提供法律意见", "不声称合规"):
        if word not in boundary:
            issues.append("claims_boundary 必须显式写「%s」" % word)
    return issues


def audit(root: str = ".") -> Tuple[List[str], Dict[str, Any]]:
    """许可/治理审计 → (issues, facts)；facts 供人读报告与测试断言。"""
    try:
        doc = load(root)
    except ValueError as exc:
        return [str(exc)], {}
    issues = validate(doc, root)
    notice = Path(root) / str((doc.get("third_party") or {}).get("notice") or "")
    rows = 0
    if notice.is_file():
        rows = sum(1 for line in notice.read_text(encoding="utf-8").splitlines()
                   if line.strip().startswith("| `"))
    facts = {
        "license": (doc.get("license") or {}).get("spdx"),
        "reuse_annotations": len(_reuse_annotations(root)),
        "third_party_rows": rows,
        "contracts": len(doc.get("contracts") or []),
        "crypto_components": len((doc.get("export") or {}).get("crypto_components") or []),
        "governance_files": len(((doc.get("oss_governance") or {}).get("files") or {})),
        "runtime_deps": _pyproject_deps(root),
        "npm_deps": _package_json_deps(root),
    }
    return issues, facts
