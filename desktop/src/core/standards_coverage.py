"""Standards four-state ledger: catalogued, bound, asserted, consumable."""
from __future__ import annotations

import ast
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

from core import atomic_write, json_doc

CATALOG_REL = "protocol/standards_catalog.json"
BINDING_REL = "protocol/standards_binding.json"
LEDGER_REL = "protocol/standards_assertions.json"
ASSERTIONS_REL = "protocol/assertions.json"
REPORT_REL = "protocol/standards_coverage.json"
SCHEMA = "nf-standards-assertions/1"
REPORT_SCHEMA = "nf-standards-coverage/1"
LAYERS = ("data", "eng", "form", "gov", "iface")
STATES = ("catalogued", "bound", "asserted", "consumable")
CHECK_ID = re.compile(r"^check([1-9][0-9]*)$")


def _load(root: Path, rel: str) -> tuple[dict[str, Any] | None, str | None]:
    path = root / rel
    if not path.is_file():
        return None, f"{rel} 缺失（修复指引：恢复标准账本输入件）"
    try:
        return json_doc.load(path, dict, what=rel), None
    except ValueError as exc:
        return None, str(exc)


def _symbols(path: Path) -> set[str]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, SyntaxError) as exc:
        raise ValueError(f"{path}: 无法解析 Python 符号（修复指引：修复语法或编码）") from exc
    out: set[str] = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            out.add(node.name)
        if isinstance(node, ast.ClassDef):
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    out.add(f"{node.name}.{child.name}")
    return out


def _safe_file(root: Path, rel: str, label: str) -> tuple[Path | None, str | None]:
    from core.paths import PathEscapeError, validate_path

    try:
        path = Path(validate_path(str(root), rel)).resolve()
    except (PathEscapeError, OSError) as exc:
        return None, f"{label} 路径非法：{exc}"
    if not path.is_file():
        return None, f"{label} 指向的文件不存在：{rel}"
    return path, None


def _check_test_ref(root: Path, rel: str, label: str) -> list[str]:
    path_raw, sep, symbol = rel.partition("::")
    if not sep or not path_raw.startswith("desktop/tests/test") or not symbol:
        return [f"{label}: 必须是 desktop/tests/test*.py::Class.test_method"]
    path, problem = _safe_file(root, path_raw, label)
    if problem:
        return [problem]
    try:
        symbols = _symbols(path)
    except ValueError as exc:
        return [f"{label}: {exc}"]
    if symbol not in symbols:
        return [f"{label}: 测试方法不存在：{rel}"]
    if not symbol.rsplit(".", 1)[-1].startswith("test_"):
        return [f"{label}: 引用不是 unittest 测试方法：{rel}"]
    return []


def _check_consumer(root: Path, rel: str, label: str) -> list[str]:
    if not isinstance(rel, dict):
        return [f"{label}: consumer 必须是对象"]
    path_raw = str(rel.get("path") or "")
    path, problem = _safe_file(root, path_raw, label)
    if problem:
        return [problem]
    symbol = str(rel.get("symbol") or "")
    contains = str(rel.get("contains") or "")
    if symbol:
        try:
            symbols = _symbols(path)
        except ValueError as exc:
            return [f"{label}: {exc}"]
        if symbol not in symbols:
            return [f"{label}: consumer symbol 不存在：{path_raw}::{symbol}"]
        return []
    if contains:
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            return [f"{label}: consumer 不可读：{exc}"]
        return [] if contains in text else [
            f"{label}: consumer 缺声明锚 {contains!r}：{path_raw}"
        ]
    return [f"{label}: consumer 必须给 symbol 或 contains"]


def _coverage_issues(catalog: dict[str, Any], rows: list[dict[str, Any]]) -> list[str]:
    issues: list[str] = []
    coverage = catalog.get("coverage")
    if not isinstance(coverage, dict):
        return ["standards catalog 缺 coverage 对象"]
    layers = Counter(str(row.get("layer")) for row in rows)
    bodies = {str(row.get("body")) for row in rows if row.get("body")}
    reachable = sum(
        1 for row in rows
        if isinstance(row.get("evidence"), dict) and row["evidence"].get("reachable") is True
    )
    expected = {
        "standards": len(rows),
        "reachable": reachable,
        "unreachable": len(rows) - reachable,
        "bodies": len(bodies),
        "by_layer": {layer: layers.get(layer, 0) for layer in LAYERS},
    }
    for key, value in expected.items():
        if coverage.get(key) != value:
            issues.append(
                f"standards catalog coverage.{key}={coverage.get(key)!r}，实算 {value!r}"
                "（修复指引：重算标准目录 coverage）"
            )
    return issues


def _catalog_index(catalog: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], list[str]]:
    issues: list[str] = []
    rows = catalog.get("standards")
    if not isinstance(rows, list):
        return {}, ["standards catalog.standards 必须是数组（修复指引：恢复目录主体）"]
    by_id: dict[str, dict[str, Any]] = {}
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            issues.append(f"standards[{index}] 必须是对象（修复指引：删除标量条目）")
            continue
        ident = str(row.get("id") or "")
        if not ident or ident in by_id:
            issues.append(f"标准 id 缺失或重复：{ident!r}（修复指引：每个标准使用唯一稳定 id）")
            continue
        if row.get("layer") not in LAYERS:
            issues.append(f"{ident}: layer 越界（修复指引：使用 {' / '.join(LAYERS)}）")
        for key in ("body", "title", "url"):
            if not str(row.get(key) or "").strip():
                issues.append(f"{ident}: 缺 {key}（修复指引：补齐标准元数据）")
        by_id[ident] = row
    return by_id, issues


def _binding_issues(
    binding: dict[str, Any], catalog_ids: set[str]
) -> tuple[set[str], list[str]]:
    issues: list[str] = []
    bound: set[str] = set()
    packs = binding.get("packs")
    if not isinstance(packs, list):
        return bound, ["standards binding.packs 必须是数组（修复指引：恢复绑定清单）"]
    if binding.get("catalog") != CATALOG_REL:
        issues.append(f"standards binding.catalog 必须指向 {CATALOG_REL}")
    if binding.get("count") != len(packs):
        issues.append(f"standards binding.count={binding.get('count')!r}，实算 {len(packs)}")
    for pack in packs:
        if not isinstance(pack, dict) or not isinstance(pack.get("bindings"), list):
            issues.append("standards binding pack 缺 bindings 数组")
            continue
        for row in pack["bindings"]:
            if not isinstance(row, dict):
                issues.append("standards binding 条目必须是对象")
                continue
            for key in ("standard", "support_standard"):
                ident = str(row.get(key) or "")
                if ident:
                    bound.add(ident)
                    if ident not in catalog_ids:
                        issues.append(f"standards binding 引用未知标准 {ident}（修复指引：先登记 catalog）")
    return bound, issues


def _claim_issues(
    root: Path,
    ledger: dict[str, Any],
    catalog_ids: set[str],
    check_ids: set[int],
    assertion_ids: set[str],
) -> tuple[dict[str, list[dict[str, Any]]], list[str]]:
    issues: list[str] = []
    claims = ledger.get("claims")
    if not isinstance(claims, list):
        return {}, ["standards assertions.claims 必须是数组（修复指引：恢复声明清单）"]
    seen: set[str] = set()
    by_standard: dict[str, list[dict[str, Any]]] = {}
    for index, claim in enumerate(claims):
        before = len(issues)
        if not isinstance(claim, dict):
            issues.append(f"claims[{index}] 必须是对象")
            continue
        cid = str(claim.get("id") or "")
        standard = str(claim.get("standard") or "")
        if not cid:
            issues.append("claim id 缺失（修复指引：每个 claim 使用唯一 id）")
        elif cid in seen:
            issues.append(f"claim id 重复：{cid!r}（修复指引：每个 claim 使用唯一 id）")
        seen.add(cid)
        if standard not in catalog_ids:
            issues.append(f"{cid}: 未知 standard {standard!r}（修复指引：先登记 standards catalog）")
        if not str(claim.get("assertion") or "").strip():
            issues.append(f"{cid}: assertion 不能为空（修复指引：写可判定的实现声明）")
        issues.extend(_claim_test_issues(root, cid, claim))
        issues.extend(_claim_path_issues(root, cid, claim, "evidence"))
        issues.extend(_claim_consumer_issues(root, cid, claim))
        issues.extend(_claim_ref_issues(cid, claim, check_ids, assertion_ids))
        if len(issues) == before:
            by_standard.setdefault(standard, []).append(claim)
    return by_standard, issues


def _claim_test_issues(root: Path, cid: str, claim: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    for key in ("tests", "negative_tests"):
        values = claim.get(key)
        if not isinstance(values, list) or not values:
            issues.append(f"{cid}: {key} 必须非空（修复指引：同时提供正例与负例证据）")
            continue
        for rel in values:
            issues.extend(_check_test_ref(root, str(rel), f"{cid}/{key}"))
    return issues


def _claim_path_issues(
    root: Path, cid: str, claim: dict[str, Any], key: str
) -> list[str]:
    values = claim.get(key)
    if not isinstance(values, list) or not values:
        return [f"{cid}: {key} 必须非空（修复指引：点名真实仓库件）"]
    issues: list[str] = []
    for rel in values:
        _path, problem = _safe_file(root, str(rel), f"{cid}/{key}")
        if problem:
            issues.append(problem)
    return issues


def _claim_consumer_issues(root: Path, cid: str, claim: dict[str, Any]) -> list[str]:
    values = claim.get("consumers")
    if not isinstance(values, list) or not values:
        return [f"{cid}: consumers 必须非空（修复指引：点名真实调用点）"]
    issues: list[str] = []
    for consumer in values:
        issues.extend(_check_consumer(root, consumer, f"{cid}/consumer"))
    return issues


def _claim_ref_issues(
    cid: str,
    claim: dict[str, Any],
    check_ids: set[int],
    assertion_ids: set[str],
) -> list[str]:
    issues: list[str] = []
    checks = claim.get("checks") or []
    if not isinstance(checks, list):
        issues.append(f"{cid}: checks 必须是数组")
    else:
        for value in checks:
            match = CHECK_ID.fullmatch(str(value))
            if not match or int(match.group(1)) not in check_ids:
                issues.append(f"{cid}: 未知 check {value!r}（修复指引：引用 verify.sh 真实 check）")
    refs = claim.get("assertion_ids") or []
    if not isinstance(refs, list):
        issues.append(f"{cid}: assertion_ids 必须是数组")
    else:
        for value in refs:
            if str(value) not in assertion_ids:
                issues.append(f"{cid}: 未知 assertion {value!r}（修复指引：登记到 assertions.json）")
    return issues


def validate_documents(
    root: str | Path,
    catalog: dict[str, Any],
    binding: dict[str, Any],
    ledger: dict[str, Any],
) -> tuple[list[str], dict[str, Any]]:
    """Validate all four state inputs and return a deterministic report body."""
    root = Path(root).resolve()
    issues: list[str] = []
    if catalog.get("schema") != "nf-standards-catalog/1":
        issues.append("standards catalog schema 不匹配")
    if binding.get("schema") != "nf-standards-binding/1":
        issues.append("standards binding schema 不匹配")
    if ledger.get("schema") != SCHEMA:
        issues.append(f"standards assertions schema 必须是 {SCHEMA}")
    catalog_by_id, catalog_issues = _catalog_index(catalog)
    catalog_rows = catalog.get("standards") if isinstance(catalog.get("standards"), list) else []
    issues.extend(catalog_issues)
    issues.extend(_coverage_issues(catalog, catalog_rows))
    bound, binding_issues = _binding_issues(binding, set(catalog_by_id))
    issues.extend(binding_issues)

    from core import assertions as assertion_runner

    check_ids = assertion_runner.verify_sh_checks(str(root))
    assertion_doc, assertion_error = _load(root, ASSERTIONS_REL)
    assertion_ids = {
        str(row.get("id"))
        for row in (assertion_doc or {}).get("assertions", [])
        if isinstance(row, dict) and row.get("id")
    }
    if assertion_error:
        issues.append(assertion_error)
    claims, claim_issues = _claim_issues(
        root, ledger, set(catalog_by_id), check_ids, assertion_ids
    )
    issues.extend(claim_issues)

    standards: list[dict[str, Any]] = []
    for ident in sorted(catalog_by_id):
        row = catalog_by_id[ident]
        found = claims.get(ident, [])
        domain_bound = ident in bound
        is_asserted = bool(found)
        is_consumable = bool(found and all(claim.get("consumers") for claim in found))
        is_bound = domain_bound or is_asserted
        state = (
            "consumable" if is_consumable else
            "asserted" if is_asserted else
            "bound" if is_bound else
            "catalogued"
        )
        standards.append({
            "id": ident,
            "body": row.get("body", ""),
            "title": row.get("title", ""),
            "url": row.get("url", ""),
            "layer": row.get("layer", ""),
            "domain_bound": domain_bound,
            "catalogued": True,
            "bound": is_bound,
            "asserted": is_asserted,
            "consumable": is_consumable,
            "state": state,
            "claims": sorted(str(claim.get("id")) for claim in found),
        })
    state_counts = Counter(row["state"] for row in standards)
    summary = {
        "catalogued": len(standards),
        "domain_bound": sum(1 for row in standards if row["domain_bound"]),
        "bound": sum(1 for row in standards if row["bound"]),
        "asserted": sum(1 for row in standards if row["asserted"]),
        "consumable": sum(1 for row in standards if row["consumable"]),
        "not_domain_bound": sum(1 for row in standards if not row["domain_bound"]),
        "states": {state: state_counts.get(state, 0) for state in STATES},
        "claims": int(ledger.get("claims") and len(ledger["claims"]) or 0),
    }
    body: dict[str, Any] = {
        "schema": REPORT_SCHEMA,
        "note": "四态仅表示仓库内部编目、绑定、断言与消费证据；不等于第三方认证。",
        "states": list(STATES),
        "summary": summary,
        "standards": standards,
        "not_domain_bound": [row["id"] for row in standards if not row["domain_bound"]],
    }
    digest_src = json.dumps(body, ensure_ascii=False, sort_keys=True).encode("utf-8")
    body["root_digest"] = hashlib.sha256(digest_src).hexdigest()
    return issues, body


def scan(root: str | Path = ".") -> tuple[list[str], dict[str, Any]]:
    root = Path(root).resolve()
    catalog, catalog_error = _load(root, CATALOG_REL)
    binding, binding_error = _load(root, BINDING_REL)
    ledger, ledger_error = _load(root, LEDGER_REL)
    errors = [item for item in (catalog_error, binding_error, ledger_error) if item]
    if errors:
        return errors, {}
    issues, report = validate_documents(root, catalog or {}, binding or {}, ledger or {})
    return issues, report.get("summary", {})


def build(root: str | Path = ".") -> tuple[list[str], dict[str, Any]]:
    root = Path(root).resolve()
    catalog, catalog_error = _load(root, CATALOG_REL)
    binding, binding_error = _load(root, BINDING_REL)
    ledger, ledger_error = _load(root, LEDGER_REL)
    errors = [item for item in (catalog_error, binding_error, ledger_error) if item]
    if errors:
        return errors, {}
    return validate_documents(root, catalog or {}, binding or {}, ledger or {})


def render(report: dict[str, Any]) -> str:
    return json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def write(root: str | Path = ".") -> tuple[list[str], dict[str, Any]]:
    root = Path(root).resolve()
    issues, report = build(root)
    if issues:
        return issues, report
    atomic_write.write_text(root / REPORT_REL, render(report))
    return [], report


def check(root: str | Path = ".") -> tuple[list[str], dict[str, Any]]:
    root = Path(root).resolve()
    issues, report = build(root)
    if issues:
        return issues, report
    recorded, error = _load(root, REPORT_REL)
    if error:
        return [error], report
    if recorded != report:
        return [
            f"{REPORT_REL} 与实时重算不一致"
            "（修复指引：运行 python scripts/standards_coverage.py --write）"
        ], report
    return [], report
