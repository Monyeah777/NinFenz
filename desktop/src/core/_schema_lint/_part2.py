"""core.schema_lint 私有实现分片 2/2（对外只经 core.schema_lint 门面导入）：_lint_obj_cached 等"""

from __future__ import annotations

import hashlib
import json
import os
from typing import Any, Dict, List, Tuple

from core import conformance_scan as _csc

from ._part1 import (
    _DOC_LINT_CACHE,
    _DOC_LINT_CACHE_MAX,
    _PATH_PLACEHOLDER,
    LINT_INPUTS,
    _lint_doc_cached,
    _read_json,
    _schema_fp,
    check_schema_files,
    discover,
    subset_validate,
)


def _lint_obj_cached(obj: Any, schema: Any, schema_fp: str, prefix: str) -> List[str]:
    """按**对象内容**缓存子集校验结果（`registry.modules` / `provenance.assets[i]` 这类逐条面）。

    与 `_lint_doc_cached` 同一套纪律：键 =（对象规范 JSON 的 sha256、schema 指纹），消息里的路径
    前缀用 `_PATH_PLACEHOLDER` 占位、取用时替换——于是**同一份条目内容出现在不同下标上也能复用**。
    判据：`test_schema_lint.DocLintCacheTest` 用未缓存参考实现在真仓库 registry / provenance 上逐条比对。
    """
    if schema is None:
        return []
    key = (hashlib.sha256(json.dumps(obj, ensure_ascii=False, sort_keys=True,
                                     default=str).encode("utf-8")).hexdigest(), schema_fp)
    hit = _DOC_LINT_CACHE.get(key)
    if hit is None:
        hit = tuple(subset_validate(obj, schema, _PATH_PLACEHOLDER))
        if len(_DOC_LINT_CACHE) >= _DOC_LINT_CACHE_MAX:
            _DOC_LINT_CACHE.clear()
        _DOC_LINT_CACHE[key] = hit
    return [m.replace(_PATH_PLACEHOLDER, prefix) for m in hit]


def _scan_impl(root: str = ".") -> Tuple[List[str], Dict[str, int]]:
    """真算（未命中缓存时走这里）。"""
    issues: List[str] = []
    if _csc.yaml is None:                     # PyYAML 惰性（见 `core.lazy_yaml`）：只在这里问一次
        issues.append("PyYAML 不在（schema_lint 依赖仓库既有 yaml 依赖）")
        stats = {"schema_files": 0, "module_docs": 0, "contract_covered": 0,
                 "pipelines": 0, "protocols": 0, "asset_entries": 0}
        return issues, stats

    schema_issues, schemas = check_schema_files(root)
    issues += schema_issues
    by_name = {os.path.basename(s["$id"]): s for s in schemas if "$id" in s}

    paths = discover(root)
    module_docs = paths["module_docs"]
    pipeline_docs = paths["pipeline_docs"]
    protocol_files = paths["protocol_files"]

    contract_schema = by_name.get("contract.schema.json")
    module_schema = by_name.get("module.schema.json")
    pipeline_schema = by_name.get("pipeline.schema.json")
    protocol_schema = by_name.get("protocol.schema.json")
    asset_schema = by_name.get("asset.schema.json")

    contract_covered = 0
    contract_fp = _schema_fp(contract_schema)
    for doc in module_docs:
        rel = os.path.relpath(doc, root).replace(os.sep, "/")
        try:
            text = _csc.read_text_cached(doc)     # 共享语料（memo 生效时同文只读一遍）
        except Exception as exc:
            issues.append(f"{rel}: 读取失败 {exc}")
            continue
        msgs = _lint_doc_cached(text, "machine_contract", contract_schema, contract_fp,
                                f"{rel} machine_contract")
        if msgs is None:
            continue  # 存量旧格式模块（check16 过渡策略：缺块不阻断）
        contract_covered += 1
        issues += msgs

    # registry 投影（module.schema.json）
    reg_path = os.path.join(root, "desktop", "src", "core", "registry.json")
    reg, err = _read_json(reg_path)
    if reg is None:
        issues.append(f"registry.json 读取/解析失败：{err}")
        reg_modules: List[Dict[str, Any]] = []
    else:
        reg_modules = reg.get("modules") or []
    if module_schema is not None:
        module_fp = _schema_fp(module_schema)
        for entry in reg_modules:
            issues += _lint_obj_cached(entry, module_schema, module_fp, "registry.modules")

    # 管线声明（pipeline.schema.json）
    pipeline_fp = _schema_fp(pipeline_schema)
    for doc in pipeline_docs:
        rel = os.path.relpath(doc, root).replace(os.sep, "/")
        try:
            text = _csc.read_text_cached(doc)     # 共享语料（memo 生效时同文只读一遍）
        except Exception as exc:
            issues.append(f"{rel}: 读取失败 {exc}")
            continue
        msgs = _lint_doc_cached(text, "Pipeline:", pipeline_schema, pipeline_fp,
                                f"{rel} Pipeline", obj_key="Pipeline")
        if msgs is None:
            issues.append(f"{rel}: Pipeline yaml 缺失/解析失败")
            continue
        issues += msgs

    # community 协议声明（protocol.schema.json）
    protocol_fp = _schema_fp(protocol_schema)
    for proto in protocol_files:
        rel = os.path.relpath(proto, root).replace(os.sep, "/")
        try:
            # 共享语料 + 内容键解析：同一份 protocol.yaml 在一轮里只读一次、只解析一次
            data = _csc.load_yaml_cached(_csc.read_text_cached(proto))
        except Exception as exc:
            issues.append(f"{rel}: protocol.yaml 解析失败 {exc}")
            continue
        issues += _lint_obj_cached(data, protocol_schema, protocol_fp, rel)

    # 资产台账（asset.schema.json）
    prov_path = os.path.join(root, "05_资产库", "provenance.json")
    prov, err = _read_json(prov_path)
    prov_entries: List[Dict[str, Any]] = []
    if prov is None:
        issues.append(f"provenance.json 读取/解析失败：{err}")
    else:
        prov_entries = prov.get("assets") or []
    if asset_schema is not None:
        asset_fp = _schema_fp(asset_schema)
        for i, entry in enumerate(prov_entries):
            issues += _lint_obj_cached(entry, asset_schema, asset_fp, f"provenance.assets[{i}]")

    stats = {
        "schema_files": len(schemas),
        "module_docs": len(module_docs),
        "contract_covered": contract_covered,
        "pipelines": len(pipeline_docs),
        "protocols": len(protocol_files),
        "asset_entries": len(prov_entries),
    }
    return issues, stats


def scan(root: str = ".") -> Tuple[List[str], Dict[str, int]]:
    """全量扫描协议件；返回 (issues, stats)。issues 空 = check28 通过。

    派生结果按**输入内容指纹**缓存（输入面见 `LINT_INPUTS`，已穷举）——与
    `conformance_scan.scan` 同一条纪律：键即内容 ⇒ 输入一变必换键，不存在陈旧；「读到的件必须
    落在输入面内」由 `test_conformance_scan.DerivedResultCacheTest` 的同一张表守着（将来给本函数
    加新读取，那条判据会先红、逼着把新输入补进来）。
    """
    return _csc.memo_pair("schema-lint", LINT_INPUTS, _scan_impl, root,
                          code_modules=("core.schema_lint",))
