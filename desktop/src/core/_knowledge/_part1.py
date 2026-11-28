"""core.knowledge 私有实现分片 1/2（对外只经 core.knowledge 门面导入）：DECL_REL、LOG_REL 等"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

from core import json_doc

DECL_REL = "protocol/knowledge_sources.json"


LOG_REL = "protocol/transform_log.json"


USAGE_REL = "protocol/knowledge_usage.json"


SCHEMA = "nf-knowledge-sources/1"


LOG_SCHEMA = "nf-transform-log/1"


USAGE_SCHEMA = "nf-knowledge-usage/1"


AUTHORITIES = ("contract", "reference")


KINDS = ("local-compiled", "external-retrieval")


VISIBILITIES = ("public", "internal", "restricted")


TIERS = ("machine-checkable", "reproducible", "externally-attestable")


TRIGGERS = ("reuse-frequency", "author-mark", "machine-check-pass")


FRESH_CONTRACT = ("stale_after",)


FRESH_REFERENCE = ("ttl", "no-cache")


REQUIRED_SRC = ("id", "authority", "kind", "locator", "requires_source_label",
                "visibility", "freshness")


REQUIRED_ENTRY = ("from", "to", "digest", "reviewed_by", "reviewed_at", "evidence")


_MODULE_ID = re.compile(r"^\s*id:\s*(M\d+|事件:M\d+|通用:M\d+)\s*$", re.M)


_DATED = re.compile(r"^\d{4}-\d{2}-\d{2}$")


#: 可见性秩：clearance 达到源的秩即可见（public ⊆ internal ⊆ restricted）
VISIBILITY_RANK = {"public": 0, "internal": 1, "restricted": 2}


def _read_json(path: Path) -> Dict[str, Any]:
    return json_doc.load(path, dict, what=path.name) if path.is_file() else {}


def load_decl(root: str = ".") -> Dict[str, Any]:
    return _read_json(Path(root) / DECL_REL)


def load_log(root: str = ".") -> Dict[str, Any]:
    return _read_json(Path(root) / LOG_REL)


def load_usage(root: str = ".") -> Dict[str, Any]:
    return _read_json(Path(root) / USAGE_REL)


def sha256_file(path: str) -> str:
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def _module_ids(root: str = ".") -> set:
    r = Path(root)
    out = set()
    for pat in ("04_模块库/*/*.md", "community/*/modules/*.md"):
        for p in sorted(r.glob(pat)):
            for m in _MODULE_ID.finditer(p.read_text(encoding="utf-8")):
                out.add(m.group(1))
    return out


def sources(root: str = ".") -> List[Dict[str, Any]]:
    return list(load_decl(root).get("sources") or [])


def reference_ids(root: str = ".") -> set:
    return {str(s.get("id")) for s in sources(root) if s.get("authority") == "reference"}


def visible_ids(root: str = ".", clearance: str = "restricted") -> set:
    """逐源可见性裁剪：clearance 达到源的可见性秩即可见（public ⊆ internal ⊆ restricted）。

    认知边界协同的**执行面**：消费方（含叙事域的 M23 裁剪）按 clearance 取源，
    越权源不进入查询顺序。
    """
    cap = VISIBILITY_RANK.get(str(clearance))
    if cap is None:
        return set()
    out = set()
    for s in sources(root):
        rank = VISIBILITY_RANK.get(str(s.get("visibility")), 99)
        if rank <= cap:
            out.add(str(s.get("id")))
    return out


def resolve_order(root: str = ".", clearance: str = "") -> List[Dict[str, str]]:
    """按声明的 query_order 解析查询顺序（先合同级，再参考级）。

    `clearance` 非空时先过逐源可见性裁剪（越权源不出现）。
    """
    decl = load_decl(root)
    by_id = {str(s.get("id")): s for s in sources(root)}
    allowed = visible_ids(root, clearance) if clearance else None
    out = []
    for sid in decl.get("query_order") or []:
        s = by_id.get(str(sid))
        if s is None:
            continue
        if allowed is not None and str(sid) not in allowed:
            continue
        out.append({"id": str(sid), "authority": str(s.get("authority")),
                    "kind": str(s.get("kind")), "locator": str(s.get("locator")),
                    "requires_source_label": str(bool(s.get("requires_source_label"))).lower(),
                    "visibility": str(s.get("visibility"))})
    return out


def _auth(rows: List[Dict[str, Any]], sid: str) -> str:
    for s in rows:
        if str(s.get("id")) == sid:
            return str(s.get("authority"))
    return ""


from ._scan import scan, verify_transform  # noqa: F401 - 门面按原模块面重新导出
