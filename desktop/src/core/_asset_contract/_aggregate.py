"""asset_contract 私有子模块 _aggregate：聚合与入口：登记册、frictionless 导出、自检、反查、扫描、冻结、跑测试。

门面 core.asset_contract 按原 API 重新导出；本文件只承载实现，不改变对外面。
"""
from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import unittest
from pathlib import Path

from core import atomic_write

from ._base import _begin_repo_scope, _declaration_doc, _end_repo_scope, _schema_doc, _strict_json, digest_of, resolve
from ._code import _check_code, _code_warns
from ._const import DECL_REL, EXPORT_REL, FACES, SCHEMA, SCHEMA_REL
from ._data import _check_data, _schema_of
from ._script import _check_chain, _check_index, _check_script



# ---------------------------------------------------------------- 聚合 / 入口
def _registry_issues(root: str, doc: Dict[str, Any]) -> List[str]:
    """D1 两册合一：本册声明为数据的 `protocol/` 件必须已在 `protocol/data_contracts.json` 登记。

    为什么：仓库里已有「数据契约登记册」（ODCS 式：谁判 / 谁管 / 坏了怎么重建）。资产册再造一份
    「谁管」就是第二套词表——同型病。判据只问一句：**同一 artifact 不许只在资产册出现**。
    """
    targets = [rel for spec in doc.get("data") or [] for rel in resolve(root, spec)
               if rel.startswith("protocol/") and rel.endswith(".json")]
    if not targets:
        return []                      # 本册没有 protocol 真源件 ⇒ 登记册判据不适用（临时场景常见）
    p = Path(root) / "protocol/data_contracts.json"
    if not p.is_file():
        return ["缺 protocol/data_contracts.json"
                "（修复指引：补登记册——本册有 protocol 真源件须登记）"]
    try:
        reg = _strict_json(p.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return ["protocol/data_contracts.json 不可读：%s（修复指引：修好 JSON）" % exc]
    arts = {str(c.get("artifact")) for c in (reg.get("contracts") or []) if isinstance(c, dict)}
    issues: List[str] = []
    for spec in doc.get("data") or []:
        for rel in resolve(root, spec):
            if rel.startswith("protocol/") and rel.endswith(".json") and rel not in arts:
                issues.append("资产 %s 未在 protocol/data_contracts.json 登记"
                              "（修复指引：补一条契约——"
                              "同一 artifact 不许只在资产册出现）" % rel)
                break
    return issues



def load(root: str = ".") -> Tuple[Dict[str, Any], List[str]]:
    """读契约声明件 → (doc, issues)。缺件/坏件如实报，不抛裸异常。"""
    doc, err = _declaration_doc(root)
    if err:
        return {}, [err]
    if not isinstance(doc, dict) or doc.get("schema") != SCHEMA:
        return {}, ["%s schema 不匹配（期望 %s）（修复指引：改为声明件当前形态）" % (DECL_REL,
 SCHEMA)]
    return doc, []



_FRIENDLY = {"string": "string", "integer": "integer", "number": "number",
                      "boolean": "boolean", "array": "array", "object": "object",
                      "null": "any"}



def frictionless_export(root: str = ".") -> Tuple[Dict[str, Any], List[str]]:
    """S3 导出：把已声明的数据资产映射成 **Frictionless Data Package**（可被别的生态直接消费）。

    诚实边界：`fields` 是 JSON Schema `properties` 的**尽力映射**（类型名对齐 Frictionless Table
    Schema），原始 JSON Schema 仍在 `x-nf-json-schema` 里逐字段保留——映射丢信息就是装饰，故不丢。
    只导出**资产面**（包产物/库索引），协议层真源不外发。
    """
    doc, issues = load(root)
    if issues:
        return {}, issues
    res: List[Dict[str, Any]] = []
    for spec in doc.get("data") or []:
        if not isinstance(spec, dict):
            continue
        for rel in resolve(root, spec):
            if rel.startswith("protocol/"):
                continue
            item: Dict[str, Any] = {"name": rel.replace("/", "--"), "path": rel}
            fmt = str(spec.get("format") or "")
            if fmt:
                item["format"] = fmt
            sch_rel = _schema_of(root, rel, spec)
            if sch_rel:
                sch, err = _schema_doc(root, sch_rel)
                if not err:
                    keep = ("type", "required", "properties", "$schema", "title", "description")
                    if sch:
                        item["x-nf-json-schema"] = {k: sch[k] for k in keep if k in sch}
                        item["x-nf-schema-source"] = sch_rel
                    fields = [{"name": k, "type": _FRIENDLY.get(str(v.get("type") or ""), "any")}
                              for k, v in sorted((sch.get("properties") or {}).items())
                              if isinstance(v, dict)]
                    if fields:
                        item["schema"] = {"fields": fields}
            res.append(item)
    return {"profile": "data-package", "name": "ninfenz-asset-contracts",
            "title": "NinFenz 数字资产契约（Frictionless Data Package 导出）",
            "x-nf-generated-by": "nf asset contract --export",
            "x-nf-note": "由已声明契约面确定性导出；领域包产物按同名 schema 约定带 fields 映射",
            "resources": res}, []



def write_export(root: str = ".") -> int:
    """落盘导出件（原子写）；返回资源数。"""
    pkg, issues = frictionless_export(root)
    if issues:
        return 0
    atomic_write.write_text(Path(root) / EXPORT_REL,
                            json.dumps(pkg, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    return len(pkg.get("resources") or [])



def _schema_self_check(root: str) -> List[str]:
    """⑤ 声明必须过**可移植 schema**（S2）：规范要可执行，不做文档摆设。"""
    sp = Path(root) / SCHEMA_REL
    if not sp.is_file():
        return ["⑤ 缺可移植 schema %s（修复指引：补该件——对外可移植契约靠它定型）" % SCHEMA_REL]
    try:
        doc, err = _declaration_doc(root)
        if err:
            raise ValueError(err)
        sch = _strict_json(sp.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return ["⑤ 声明或 schema 不可读：%s（修复指引：修好 JSON）" % exc]
    from core import json_schema as js
    return ["⑤ 声明不符可移植 schema %s：%s（修复指引：改声明或改 schema——两者只能有一个对）"
            % (SCHEMA_REL, e) for e in js.json_schema_check(doc, sch)[:5]]



def _export_drift(root: str) -> List[str]:
    """④ 导出件 == 实时导出（缺件/漂移都 FAIL：导出面不许只在人手里新鲜）。"""
    p = Path(root) / EXPORT_REL
    live, errs = frictionless_export(root)
    if errs:
        return errs
    if not p.is_file():
        return ["④ 缺契约导出 %s（修复指引：nf asset contract --export）" % EXPORT_REL]
    try:
        disk = _strict_json(p.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return ["④ %s 不可读：%s（修复指引：nf asset contract --export）" % (EXPORT_REL, exc)]
    if disk != live:
        return ["④ %s 与实时导出不一致（修复指引：nf asset contract --export）" % EXPORT_REL]
    return []



def contracts_for_path(root: str, rel: str) -> dict[str, Any]:
    """给定对象 → 命中它的契约集（cc_resolve v0）。

    方向与 resolve（声明 → 文件清单）**相反**：那个回答「这份契约管哪些文件」，
    这个回答「这个文件该守哪些契约」——合规体检与责任归属要的是后一个方向。

    closure_closed 显式出现：没有契约认领该对象时也必须给出 false，不许用空数组糊过去
    （空数组读起来像「查过了，没问题」，那是假结论）。
    """
    target = str(rel).replace("\\", "/").lstrip("/")
    doc, issues = load(root)
    if issues:
        raise ValueError("契约声明不可用：" + "；".join(issues[:3]))
    _begin_repo_scope()
    try:
        hits: list[dict[str, Any]] = []
        for face in FACES:
            for spec in doc.get(face) or []:
                if not isinstance(spec, dict):
                    continue
                files = resolve(root, spec)
                if target not in files:
                    continue
                spec_bytes = json.dumps(spec, sort_keys=True, ensure_ascii=False,
                                        separators=(",", ":")).encode("utf-8")
                hits.append({"face": face, "id": str(spec.get("id") or ""),
                             "files": len(files),
                             "digest": hashlib.sha256(spec_bytes).hexdigest()})
    finally:
        _end_repo_scope()
    return {"schema": "nf-contract-resolve/1", "object": target, "contracts": hits,
            "closure_closed": bool(hits), "unclaimed": not hits}


def scan(root: str = ".", faces: Iterable[str] = ()
         ) -> Tuple[List[str], List[str], Dict[str, Any]]:
    """四面契约扫描（数据/代码/脚本/包清单）→ (issues, warns, stats)；门禁入口（check40 同源）。"""
    _begin_repo_scope()
    try:
        return _scan_impl(root, faces)
    finally:
        _end_repo_scope()



def _scan_impl(root: str = ".", faces: Iterable[str] = ()
               ) -> Tuple[List[str], List[str], Dict[str, Any]]:
    doc, issues = load(root)
    warns: List[str] = []
    stats: Dict[str, Any] = {f: 0 for f in FACES}
    stats.update({"files": 0, "chains": 0})
    if issues:
        return issues, warns, stats
    issues += _registry_issues(root, doc)
    if not faces:                      # ④/⑤ 是**声明面整体**判据；--face 是显式收窄，不判整体
        issues += _export_drift(root)
        issues += _schema_self_check(root)
    want = {str(x) for x in faces} or set(FACES)
    for face in FACES:
        if face not in want:
            continue
        for spec in doc.get(face) or []:
            if not isinstance(spec, dict):
                issues.append("契约 %s 面有非对象条目（修复指引：每条须是对象）" % face)
                continue
            if face == "data":
                sub, s = _check_data(root, spec)
            elif face == "code":
                sub, s = _check_code(root, spec)
                warns += _code_warns(root, spec)   # WARN 级治理面，不进 issues（见 _code_warns）
            elif face == "index":
                sub, s = _check_index(root, spec)
            else:
                sub, s = _check_script(root, spec)
            issues += sub
            stats[face] += 1
            stats["files"] += s.get("files", 0)
            stats["no_schema"] = int(stats.get("no_schema") or 0) + int(s.get("no_schema") or 0)
    specs = {str(s.get("id")): s for s in doc.get("script") or [] if isinstance(s, dict)}
    if "script" in want:
        for chain in doc.get("chains") or []:
            sub, _ = _check_chain(specs, chain if isinstance(chain, dict) else {})
            issues += sub
            stats["chains"] += 1
    return issues, warns, stats



def freeze(root: str = ".") -> Tuple[List[str], Dict[str, Any]]:
    """按当前内容重冻声明的 sha256（防篡改棘轮：改动须显式重冻，不由扫描器偷偷写）。"""
    doc, issues = load(root)
    if issues:
        return issues, {"frozen": 0}
    n = 0
    for spec in doc.get("data") or []:
        if not isinstance(spec, dict) or not spec.get("sha256"):
            continue
        rel = str(spec.get("path") or "")
        p = Path(root) / rel
        if not p.is_file():
            issues.append("数据契约 %s 的 %s 不在场（修复指引：补件后再冻）" % (spec.get("id"),
 rel))
            continue
        spec["sha256"] = digest_of(p)
        n += 1
    if not issues:
        atomic_write.write_text(Path(root) / DECL_REL,
                                json.dumps(doc,
 ensure_ascii=False,
 indent=2,
 sort_keys=True) + "\n")
    return issues, {"frozen": n}



def _run_test_file(path: Path) -> Tuple[List[str], int]:
    """按路径加载一个测试件并跑它（显式开启面；门禁默认不执行被声明脚本的代码）。"""
    name = "nf_asset_contract_test_%s" % hashlib.sha256(str(path).encode("utf-8")).hexdigest()[:12]
    spec = importlib.util.spec_from_file_location(name, str(path))
    if spec is None or spec.loader is None:
        return ["测试件不可加载：%s（修复指引：核对路径与扩展名）" % path], 0
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
    except Exception as exc:                                    # noqa: BLE001 —— 测试件任意错误都记档
        return ["测试件执行失败：%s（%s: %s）（修复指引：先修测试件）"
                % (path.name, type(exc).__name__, exc)], 0
    suite = unittest.defaultTestLoader.loadTestsFromModule(mod)
    res = unittest.TextTestRunner(stream=io.StringIO(), verbosity=0).run(suite)
    issues = []
    for case, tb in list(res.failures) + list(res.errors):
        issues.append("测试未过：%s（修复指引：修到全绿；%s）"
                      % (case, tb.strip().splitlines()[-1][:160]))
    return issues, res.testsRun



def run_tests(root: str = ".", ids: Iterable[str] = ()) -> Tuple[List[str], Dict[str, Any]]:
    """跑声明的测试件（nf asset contract --run-tests）→ (issues, stats)。"""
    doc, issues = load(root)
    out: Dict[str, Any] = {"files": 0, "tests": 0}
    if issues:
        return issues, out
    want = {str(x) for x in ids}
    for spec in doc.get("code") or []:
        if not isinstance(spec, dict) or (want and str(spec.get("id")) not in want):
            continue
        for t in spec.get("tests") or []:
            p = Path(root) / str(t)
            if not p.is_file():
                issues.append("测试件不在场：%s（修复指引：先写测试再改契约）" % t)
                continue
            out["files"] += 1
            sub, ran = _run_test_file(p)
            issues += sub
            out["tests"] += ran
    return issues, out
