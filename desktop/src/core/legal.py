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


def _license_issues(lic: Dict[str, Any], root: str, spdx: str) -> List[str]:
    """license 判据（spdx 合法 / 文件在场 / MIT 文本一致）。"""
    out: List[str] = []
    if not spdx or not _license_expression_ok(spdx):
        out.append("license.spdx 非法：%s" % spdx)
    for field in ("file", "text"):
        if not _exists(root, str(lic.get(field) or "")):
            out.append("license.%s 不在场：%s" % (field, lic.get(field)))
    if spdx == "MIT":  # 与本仓实际文本对齐（换许可须同时换文本与登记）
        try:
            head = (Path(root) / "LICENSE").read_text(encoding="utf-8")
            if "MIT License" not in head:
                out.append("LICENSE 文本与 spdx=MIT 不一致（%s 换许可须同步文本/REUSE/登记）" % GUIDE)
        except OSError:
            pass
    return out


def _community_issues(community: Dict[str, Any], root: str) -> List[str]:
    """community_license 判据（LicenseRef 前缀 / 文本在场 / scope 非空）。"""
    out: List[str] = []
    if not str(community.get("spdx") or "").startswith("LicenseRef-"):
        out.append("community_license 必须用 LicenseRef-<自定义> 显式自造许可")
    if not _exists(root, str(community.get("text") or "")):
        out.append("community_license.text 不在场：%s" % community.get("text"))
    if not isinstance(community.get("scope"), list) or not community.get("scope"):
        out.append("community_license 缺 scope（覆盖哪些投稿面）")
    return out


def _reuse_toml_issues(reuse: Dict[str, Any], root: str) -> List[str]:
    """reuse.toml 在场判据。"""
    if not _exists(root, str(reuse.get("toml") or "")):
        return ["reuse.toml 不在场：%s" % reuse.get("toml")]
    return []


def _reuse_agg_issues(reuse: Dict[str, Any], annotations: List[Any],
                      spdx: str) -> List[str]:
    """REUSE annotations 非空 + 聚合许可对账判据。"""
    out: List[str] = []
    if not annotations:
        out.append("REUSE.toml 解析不出 annotations（%s 修 TOML）" % GUIDE)
    aggregate = [a for a in annotations if str(a.get("precedence")) == "aggregate"]
    if aggregate and str(aggregate[0].get("SPDX-License-Identifier")) != str(reuse.get("aggregate_license")):
        out.append("REUSE 聚合许可 %r ≠ 登记 %r"
                   % (aggregate[0].get("SPDX-License-Identifier"), reuse.get("aggregate_license")))
    if str(reuse.get("aggregate_license")) != spdx:
        out.append("reuse 聚合许可 %r ≠ license.spdx %r（换许可须同步 LICENSE/REUSE/登记，%s）"
                   % (reuse.get("aggregate_license"), spdx, GUIDE))
    return out


def _override_issues(community: Dict[str, Any], annotations: List[Any]) -> List[str]:
    """REUSE override 对投稿面的覆盖判据。"""
    overrides = [a for a in annotations if str(a.get("precedence")) == "override"]
    out: List[str] = []
    for scope in community.get("scope") or []:
        if not any(scope in [str(p) for p in (a.get("path") or [])] for a in overrides):
            out.append("REUSE override 缺投稿面覆盖：%s" % scope)
    return out


def _third_party_issues(third: Dict[str, Any], root: str) -> List[str]:
    """third_party 判据（三件在场 / requirements 逐条在场）。"""
    out: List[str] = []
    for field in ("notice", "generator", "sbom"):
        if not _exists(root, str(third.get(field) or "")):
            out.append("third_party.%s 不在场：%s" % (field, third.get(field)))
    for rel in third.get("requirements") or []:
        if not _exists(root, str(rel)):
            out.append("third_party.requirements 不在场：%s" % rel)
    return out


def _dep_issues(root: str) -> List[str]:
    """运行时零第三方依赖判据（pyproject / npm）。"""
    deps = _pyproject_deps(root)
    npm = _package_json_deps(root)
    out: List[str] = []
    if deps != []:
        out.append("pyproject [project].dependencies 必须为空（运行时零第三方；实际 %r）" % (deps,))
    if npm not in (None, {}):
        out.append("npm package.json 不得有 dependencies（实际 %r）" % (npm,))
    return out


def _trademark_issues(trade: Dict[str, Any]) -> List[str]:
    """trademark 判据（name / rules / 非背书 / attribution）。"""
    out: List[str] = []
    if not str(trade.get("name") or "").strip():
        out.append("trademark 缺 name")
    if len(trade.get("rules") or []) < 2:
        out.append("trademark.rules 至少 2 条（使用/分发边界）")
    if "不得" not in str(trade.get("no_endorsement") or ""):
        out.append("trademark 缺非背书条款（不得暗示官方认证/背书）")
    if not str(trade.get("attribution") or "").strip():
        out.append("trademark 缺 attribution（署名口径）")
    return out


def _contract_issues(item: Dict[str, Any], root: str) -> List[str]:
    """单个合同模板判据（path 在场 / status 词表）。"""
    out: List[str] = []
    if not _exists(root, str(item.get("path") or "")):
        out.append("合同模板 %s 的 path 不在场：%s" % (item.get("id"), item.get("path")))
    if str(item.get("status")) not in ("template-in-doc", "signed-external", "none"):
        out.append("合同 %s 的 status 非法：%s" % (item.get("id"), item.get("status")))
    return out


def _contracts_issues(contracts: List[Any], root: str) -> List[str]:
    """contracts 类型覆盖 + 逐件判据。"""
    types = [str(c.get("type")) for c in contracts if isinstance(c, dict)]
    out: List[str] = []
    if sorted(types) != sorted(CONTRACT_TYPES):
        out.append("contracts 必须恰覆盖 %s（实际 %s）" % (list(CONTRACT_TYPES), types))
    for item in contracts:
        if not isinstance(item, dict):
            out.append("contracts 含非对象")
            continue
        out.extend(_contract_issues(item, root))
    return out


def _export_issues(exp: Dict[str, Any], root: str) -> List[str]:
    """export 判据（加密组件登记/在场 / review_trigger / 非法律意见）。"""
    out: List[str] = []
    comps = exp.get("crypto_components") or []
    if not comps:
        out.append("export.crypto_components 为空（加密组件必须显式登记）")
    for rel in comps:
        if not _exists(root, str(rel)):
            out.append("加密组件不在场：%s" % rel)
    if not exp.get("review_trigger"):
        out.append("export 缺 review_trigger（何时须做出口/制裁评审）")
    if not str(exp.get("not_legal_advice") or "").strip():
        out.append("export 缺 not_legal_advice（不构成法律意见）")
    return out


def _oss_files_issues(oss: Dict[str, Any], root: str) -> List[str]:
    """oss_governance.files 逐件在场判据。"""
    files = oss.get("files") or {}
    out: List[str] = []
    for key in ("contributing", "code_of_conduct", "maintainers", "security",
                "support", "governance", "changelog"):
        if not _exists(root, str(files.get(key) or "")):
            out.append("oss_governance.files.%s 不在场：%s" % (key, files.get(key)))
    return out


def _oss_policy_issues(oss: Dict[str, Any], root: str) -> List[str]:
    """oss_governance 策略文本 + scorecard workflow 判据。"""
    out: List[str] = []
    for key in ("release_policy", "deprecation_policy"):
        if not str(oss.get(key) or "").strip():
            out.append("oss_governance 缺 %s" % key)
    if not _exists(root, str((oss.get("scorecard") or {}).get("workflow") or "")):
        out.append("scorecard workflow 不在场：%s" % (oss.get("scorecard") or {}).get("workflow"))
    return out


def _boundary_issues(doc: Dict[str, Any]) -> List[str]:
    """claims_boundary 必写词判据。"""
    boundary = " ".join(str(x) for x in doc.get("claims_boundary") or [])
    out: List[str] = []
    for word in ("不提供法律意见", "不声称合规"):
        if word not in boundary:
            out.append("claims_boundary 必须显式写「%s」" % word)
    return out


def validate(doc: Dict[str, Any], root: str = ".") -> List[str]:
    lic = doc.get("license") or {}
    spdx = str(lic.get("spdx") or "")
    issues: List[str] = []
    issues.extend(_license_issues(lic, root, spdx))
    community = lic.get("community_license") or {}
    issues.extend(_community_issues(community, root))
    reuse = doc.get("reuse") or {}
    issues.extend(_reuse_toml_issues(reuse, root))
    annotations = _reuse_annotations(root)
    issues.extend(_reuse_agg_issues(reuse, annotations, spdx))
    issues.extend(_override_issues(community, annotations))
    third = doc.get("third_party") or {}
    issues.extend(_third_party_issues(third, root))
    issues.extend(_dep_issues(root))
    trade = doc.get("trademark") or {}
    issues.extend(_trademark_issues(trade))
    contracts = doc.get("contracts") or []
    issues.extend(_contracts_issues(contracts, root))
    exp = doc.get("export") or {}
    issues.extend(_export_issues(exp, root))
    oss = doc.get("oss_governance") or {}
    issues.extend(_oss_files_issues(oss, root))
    issues.extend(_oss_policy_issues(oss, root))
    issues.extend(_boundary_issues(doc))
    return issues


def _audit_facts(root: str, doc: Dict[str, Any], rows: int) -> Dict[str, Any]:
    """许可/治理事实（供人读报告与测试断言）。"""
    return {
        "license": (doc.get("license") or {}).get("spdx"),
        "reuse_annotations": len(_reuse_annotations(root)),
        "third_party_rows": rows,
        "contracts": len(doc.get("contracts") or []),
        "crypto_components": len((doc.get("export") or {}).get("crypto_components") or []),
        "governance_files": len(((doc.get("oss_governance") or {}).get("files") or {})),
        "runtime_deps": _pyproject_deps(root),
        "npm_deps": _package_json_deps(root),
    }


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
    return issues, _audit_facts(root, doc, rows)
