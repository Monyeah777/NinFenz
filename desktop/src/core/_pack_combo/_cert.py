"""pack_combo 私有子模块 _cert：证书层：见证/判决缓存、声明组合证书的生成与 T4 复算、广度证明。

门面 core.pack_combo 按原 API 重新导出；本文件只承载实现，不改变对外面。
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Sequence, Tuple

from core import atomic_write

from core import pack_combo as _dm
from ._base import _core_contracts, _read_json, indexes
from ._const import CERT_REL, CERT_SCHEMA, _COMBO_CACHE, _COMBO_CACHE_MAX

#: 参与见证的包声明字段（`module_recs` 由**模块契约面**统一覆盖，不在这里重复计入）。
_COMBO_DECL_KEYS = ("package", "pipeline", "references", "assets", "layers",
                    "publishes", "subscribes")



def _canon(obj: Any) -> bytes:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")



def _combo_witness(root: str, prof: Dict[str, Any], contracts: Dict[str, Any]) -> str:
    """本轮「组合语义面」的**全局见证**：逐包声明 + 逐模块契约 + 核心发布集（规范 JSON 后哈希）。

    每次广度证明只算一遍（111 包 + 235 契约，实测 < 1 ms），其后 ~6900 次组合共用同一份。
    """
    h = hashlib.sha256()
    for p in sorted(prof):
        rec = prof[p] or {}
        h.update(_canon(["decl", str(p), {k: rec.get(k) for k in _COMBO_DECL_KEYS}]))
    for mid in sorted(contracts):
        h.update(_canon(["contract", str(mid), contracts[mid]]))
    _by_id, _pub, core_pub = indexes(root)
    h.update(_canon(["core_pub", sorted(core_pub)]))
    return h.hexdigest()



def _verdict_cached(root: str, names: Sequence[str], prof: Dict[str, Any],
                    contracts: Dict[str, Any],
                    witness: str) -> Tuple[bool, List[Any], List[Any]]:
    """`combine()` 的逐组合判决缓存 → `(legal, dangling[:2], unbridged[:2])`。

    只留广度证明真正消费的三个字段（不整个证书）：6700+ 条证书常驻守护会把内存顶起来，
    而判决是同一个纯函数的值。键见 `_COMBO_CACHE` 的说明。
    """
    key = (tuple(names), witness)
    hit = _COMBO_CACHE.get(key)
    if hit is None:
        cert = _dm.combine(root, packs=list(names), _prof=prof, _contracts=contracts)
        hit = (bool(cert["legal"]),
               list((cert.get("dependency_closure") or {}).get("dangling") or [])[:2],
               list((cert.get("event_closure") or {}).get("unbridged") or [])[:2])
        if len(_COMBO_CACHE) >= _COMBO_CACHE_MAX:
            _COMBO_CACHE.clear()
        _COMBO_CACHE[key] = hit
    return hit



def verify_certificate(root: str, cert: Dict[str, Any]) -> Tuple[List[str], Dict[str, Any]]:
    """T4 复算：按证书输入重算组合，与在盘证书逐字段比对。"""
    issues: List[str] = []
    fresh = _dm.combine(root, packs=cert.get("packs") or (),
                    extra_modules=cert.get("extra_modules") or ())
    for key in ("modules", "module_count", "layer_stacks", "dependency_closure",
                "event_closure", "assets_borrowed", "modules_borrowed", "legal", "digest"):
        if fresh.get(key) != cert.get(key):
            issues.append("字段不一致：%s（复算 %r ≠ 在盘 %r）"
                          % (key, fresh.get(key), cert.get(key)))
    return issues, {"legal": fresh.get("legal"), "modules": fresh.get("module_count")}



def declared(root: str = ".") -> Dict[str, Any]:
    return _read_json(Path(root) / CERT_REL) or {
        "schema": "nf-combo-certificates/1", "certificates": []}



def certify(root: str = ".", packs: Sequence[str] = (), label: str = "", note: str = "",
            extra_modules: Sequence[str] = (), write: bool = False) -> Dict[str, Any]:
    """生成/更新一条**声明组合**的证书（写进 `protocol/combo_certificates.json`）。"""
    cert = _dm.combine(root, packs=packs, extra_modules=extra_modules)
    if label:
        cert["label"] = label
    if note:
        cert["note"] = note
    if not write:
        return cert
    path = Path(root) / CERT_REL
    doc = _read_json(path) or _empty_cert_doc()
    # 去重键 = 组合输入本身（packs + extra_modules），**不是** digest：
    # 引擎升级后同一组合的摘要会变，按 digest 去重会留下历史快照（实测 26 条里 13 条过期）。
    certs = [c for c in doc["certificates"] if _cert_key(c) != _cert_key(cert)]
    certs.append(cert)
    doc["certificates"] = sorted(certs, key=_cert_sort_key)
    doc["count"] = len(doc["certificates"])
    doc["max_packs"] = _cert_max_packs(doc)
    path.parent.mkdir(parents=True, exist_ok=True)
    # 原子写（2026-09-30 收口）：组合证书是在仓产物（`protocol/` 侧），并发读者可能读到半截。
    atomic_write.write_text(path, json.dumps(doc, ensure_ascii=False, indent=2) + "\n")
    return cert


def _empty_cert_doc() -> Dict[str, Any]:
    """空证书册的骨架。"""
    return {
        "schema": "nf-combo-certificates/1",
        "note": "声明组合证书（公开结果面）。每条 = 一次 n 元组合的可机验凭证：包清单 / 模块集 / "
                "层位堆叠 / 依赖闭包 / 事件闭包 / 资产借阅 / 合法性 / 规范摘要。"
                "判据（check32 combos）：① 证书过 CERT_SCHEMA；② 按 packs+extra_modules **复算**"
                "逐字段一致（T4）；③ 广度证明（全部两两 + 定种子三元/四元）不变量全成立。",
        "certificates": [],
    }


def _cert_key(c: Dict[str, Any]) -> Tuple[Any, ...]:
    """证书去重键（组合输入本身）。"""
    return (tuple(c.get("packs") or ()), tuple(sorted(c.get("extra_modules") or ())))


def _cert_sort_key(c: Dict[str, Any]) -> Tuple[Any, ...]:
    """证书册排序键（包数 / label / digest）。"""
    return (len(c.get("packs") or []), c.get("label") or "", c["digest"])


def _cert_max_packs(doc: Dict[str, Any]) -> int:
    """证书册里最大包数。"""
    return max((len(c.get("packs") or []) for c in doc["certificates"]), default=0)



def core_contracts_fingerprint(root: str = ".") -> str:
    """**核心契约的解析结果**（`_core_contracts`）的内容指纹——供「组合语义见证」类调用方复用。

    为什么要有它（实测 2026-09-29）：`output_forms` 的逐包判决要经 `combine` 用到核心模块的
    `publish`（`core_pub`）⇒ 核心模块文档是它的输入。但**键应当按「解析后的契约」取**，不是正文：
    `04_模块库` 正文改动（改说明、加段落）不影响任何判决，按正文取键会让**每个包**都白重算一遍
    （实测：106 个包全重算 + 全落盘 ≈ +800 ms/条命令）；只有 `machine_contract` 围栏变了才该重算。
    """
    return hashlib.sha256(_canon(_core_contracts(root))).hexdigest()



_CERT_CACHE: Dict[Any, Any] = {}

_CERT_CACHE_MAX = 256



def _certificate_lines(root: str, cert: Dict[str, Any], witness: str) -> List[str]:
    """单张证书的 issue 行（schema 校验 + T4 复算），带**内容键缓存**。

    依据（实测 2026-09-29）：一次 `nf score` 里 `pack_combo.scan` 稳态 ~36 ms，其中证书复算
    **9.4–10.2 ms**、证书 schema 校验 **8.6–9.9 ms（1486 次嵌套调用）**——而这两者只是
    「**该证书正文** + 本轮契约面」的纯函数：改与组合无关的件（04 模块库正文、文档、协议件）时
    它们必然不变。键 = (证书正文 sha256, 本轮全局见证)；两者任一变即重算，无陈旧面。
    """
    from core import json_schema as _js  # 只取叶子校验器：不再 import output_forms（断双向对）
    key = (hashlib.sha256(_canon(cert)).hexdigest(), witness)
    hit = _CERT_CACHE.get(key)
    if hit is None:
        unsup: List[str] = []
        schema_errs = list(_js.json_schema_check(cert, CERT_SCHEMA, unsupported=unsup))
        sub, _st = verify_certificate(root, cert)
        hit = (schema_errs, sorted(set(unsup)), list(sub))
        if len(_CERT_CACHE) >= _CERT_CACHE_MAX:
            _CERT_CACHE.clear()
        _CERT_CACHE[key] = hit
    schema_errs, unsup, sub = hit
    name = cert.get("label") or "+".join(cert.get("packs") or []) or "<空>"
    out = ["组合 %s: 证书不合 schema: %s" % (name, e) for e in schema_errs[:4]]
    if unsup:
        out.append("组合 %s: 证书校验器遇到不支持关键字 %s" % (name, unsup[:2]))
    out += ["组合 %s: %s" % (name, s) for s in sub]
    return out
