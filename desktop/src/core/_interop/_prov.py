"""interop_export 私有子模块 _prov：PROV-O 派生面的节点构造（供 _docs_b.prov_document 复用）。

门面 core.interop_export 按原 API 重新导出；本文件只承载实现，不改变对外面。
"""
from __future__ import annotations

import os
import re

def _add_node(nodes: dict, node: dict) -> None:
    """去重入图（同 id 只留一次——同一投稿人/同一文件会自然重复出现）。"""
    nodes.setdefault(str(node.get("@id")), node)


def _asset_entities(prov: dict) -> list[dict]:
    """① 实体：资产（键 / 归属模块 / 状态）。"""
    out: list[dict] = []
    for a in prov.get("assets") or []:
        out.append({"@id": "nf:asset/%s" % a.get("key"), "@type": "prov:Entity",
                    "prov:label": str(a.get("key") or ""),
                    "nf:file": str(a.get("file") or ""),
                    "nf:module": str(a.get("module") or ""),
                    "nf:status": str(a.get("status") or ""),
                    "nf:version": str(a.get("version") or "")})
    return out


def _library_nodes(root: str) -> list[dict]:
    """② 实体 + 入库活动：馆藏条目（活动与代理来自 INDEX 行的真值）。"""
    idx = os.path.join(root, "library", "INDEX.md")
    out: list[dict] = []
    if not os.path.isfile(idx):
        return out
    with open(idx, encoding="utf-8") as fh:
        for line in fh:
            if not re.match(r"^\|\s*NF-[A-Za-z0-9\-]+\s*\|", line):
                continue
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if len(cells) < 6:
                continue
            eid, author, date, lic = cells[0], cells[3], cells[4], cells[5]
            out.append({"@id": "nf:library/%s" % eid, "@type": "prov:Entity",
                        "prov:label": cells[1], "nf:license": lic})
            out.append({"@id": "nf:activity/library-ingest/%s" % eid,
                        "@type": "prov:Activity", "prov:endedAtTime": date,
                        "prov:wasAssociatedWith": "nf:agent/%s" % author,
                        "prov:generated": "nf:library/%s" % eid})
            out.append({"@id": "nf:agent/%s" % author, "@type": "prov:Person",
                        "prov:label": author})
    return out


def _receipt_entities(rec: dict) -> list[dict]:
    """③ 实体：回执绑定的协议层文件（内容寻址）。"""
    out: list[dict] = []
    for e in rec.get("entries") or []:
        out.append({"@id": "nf:file/%s" % e.get("path"), "@type": "prov:Entity",
                    "nf:sha256": str(e.get("digest") or "")})
    return out


def _transform_activities(transform: dict) -> list[dict]:
    """④ 活动：消化记录（「参考级源 → 本地产物」的转换，逐条绑 digest）。"""
    out: list[dict] = []
    for i, t in enumerate(transform.get("entries") or [], 1):
        out.append({"@id": "nf:transform/%d" % i, "@type": "prov:Activity",
                    "prov:used": "nf:file/%s" % (t.get("source") or t.get("from") or ""),
                    "prov:generated": "nf:file/%s" % (t.get("product") or t.get("to") or ""),
                    "nf:digest": str(t.get("digest") or "")})
    return out


def _verify_agent(root: str) -> dict:
    """⑤ 代理：仓本体（软件代理）。"""
    return {"@id": "nf:agent/verify-sh", "@type": "prov:SoftwareAgent",
            "prov:label": "NinFenz verify.sh 门禁",
            "nf:present": os.path.isfile(os.path.join(root, "verify.sh"))}


def _prov_counts(graph: list) -> dict:
    """@graph 各类型的计数面。"""
    return {"entities": sum(1 for n in graph if n["@type"] == "prov:Entity"),
            "activities": sum(1 for n in graph if n["@type"] == "prov:Activity"),
            "agents": sum(1 for n in graph
                          if n["@type"] in ("prov:Person", "prov:SoftwareAgent"))}
