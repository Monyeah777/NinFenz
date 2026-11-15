"""独立 oracle（不含任何 nf_app / Rust 依赖）。

用途：与 Rust 核心输出对账（CONTRACT §2/§5 的复算口径）。刻意用另一套代码路径
重写 canonical / pack tree / 拓扑序 / verdict，避免"实现自己验证自己"。
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

_FORBIDDEN_FLOAT = True


def _escape(text: str) -> str:
    out = ['"']
    for ch in text:
        code = ord(ch)
        if ch == '"':
            out.append('\\"')
        elif ch == "\\":
            out.append("\\\\")
        elif ch == "\b":
            out.append("\\b")
        elif ch == "\f":
            out.append("\\f")
        elif ch == "\n":
            out.append("\\n")
        elif ch == "\r":
            out.append("\\r")
        elif ch == "\t":
            out.append("\\t")
        elif code < 0x20:
            out.append("\\u%04x" % code)
        else:
            out.append(ch)
    out.append('"')
    return "".join(out)


def canonical(value) -> bytes:
    """nf-canonical/1 的独立重写：键码点升序、紧凑分隔、禁浮点。"""

    def encode(node) -> str:
        if node is None:
            return "null"
        if node is True:
            return "true"
        if node is False:
            return "false"
        if isinstance(node, int):
            return str(node)
        if isinstance(node, float):
            raise TypeError("oracle: canonical 禁浮点")
        if isinstance(node, str):
            return _escape(node)
        if isinstance(node, (list, tuple)):
            return "[" + ",".join(encode(item) for item in node) + "]"
        if isinstance(node, dict):
            for key in node:
                if not isinstance(key, str):
                    raise TypeError("oracle: 键必须是字符串")
            pairs = sorted(node.items(), key=lambda kv: kv[0])
            return "{" + ",".join(_escape(k) + ":" + encode(v) for k, v in pairs) + "}"
        raise TypeError(f"oracle: 不支持的类型 {type(node)!r}")

    return encode(value).encode("utf-8")


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def digest(value) -> str:
    return sha256_hex(canonical(value))


def digest_excluding(value: dict, exclude=()) -> str:
    dropped = set(exclude)
    declared = value.get("x-digest-exclude")
    if isinstance(declared, list):
        dropped |= set(declared)
    dropped.add("x-digest-exclude")
    return digest({k: v for k, v in value.items() if k not in dropped})


def tree_digest(items: list[dict]) -> str:
    rows = sorted(
        ({"path": item["path"], "sha256": item["sha256"], "size": item["size"]} for item in items),
        key=lambda row: row["path"],
    )
    return digest(rows)


def scan_pack(root: Path | str) -> list[dict]:
    """递归扫 pack 文件（排除 nf-pack.json / *.sig 根文件），返回按 path 升序 items。"""
    root = Path(root)
    rows: list[dict] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames.sort()
        for name in sorted(filenames):
            full = Path(dirpath) / name
            rel = full.relative_to(root).as_posix()
            if rel in ("nf-pack.json", "nf-pack.json.sig"):
                continue
            if "/" not in rel and rel.endswith(".sig"):
                continue
            data = full.read_bytes()
            rows.append({"path": rel, "sha256": sha256_hex(data), "size": len(data)})
    rows.sort(key=lambda row: row["path"])
    return rows


def topo_order(graph: dict) -> list[str]:
    """Kahn + 就绪集合按节点 id 码点升序取最小（与 Rust 核心约定一致）。"""
    nodes = [node["id"] for node in graph["nodes"]]
    indegree = {node_id: 0 for node_id in nodes}
    adj: dict[str, list[str]] = {node_id: [] for node_id in nodes}
    for edge in graph["edges"]:
        if edge["from"] in indegree and edge["to"] in indegree:
            adj[edge["from"]].append(edge["to"])
            indegree[edge["to"]] += 1
    ready = sorted(node_id for node_id, deg in indegree.items() if deg == 0)
    order: list[str] = []
    while ready:
        current = ready.pop(0)
        order.append(current)
        for nxt in adj[current]:
            indegree[nxt] -= 1
            if indegree[nxt] == 0:
                ready.append(nxt)
        ready.sort()
    if len(order) != len(nodes):
        raise ValueError("oracle: 图有环，无法拓扑排序")
    return order


def module_step_nodes(graph: dict) -> list[str]:
    modules = {node["id"] for node in graph["nodes"] if node["kind"] == "module"}
    return [node_id for node_id in topo_order(graph) if node_id in modules]


def stage_of(graph: dict, node_id: str) -> str | None:
    """最近上游 stage（沿入边反向 BFS；同一层取 id 码点最小者）。

    与核心 graph-compile 口径一致：N02→N01、N04→N03（不是全局可达最小）。
    """
    kinds = {node["id"]: node["kind"] for node in graph["nodes"]}
    incoming: dict[str, list[str]] = {}
    for edge in graph["edges"]:
        incoming.setdefault(edge["to"], []).append(edge["from"])
    seen: set[str] = {node_id}
    frontier = sorted(set(incoming.get(node_id, [])))
    while frontier:
        stages = [node for node in frontier if kinds.get(node) == "stage"]
        if stages:
            return min(stages)
        seen.update(frontier)
        nxt: set[str] = set()
        for node in frontier:
            nxt.update(parent for parent in incoming.get(node, []) if parent not in seen)
        frontier = sorted(nxt)
    return None


def step_inputs(graph: dict, node_id: str) -> list[str]:
    ports = [edge["from_port"] for edge in graph["edges"] if edge["to"] == node_id]
    return sorted(set(ports))


def verdict(issues: list[dict]) -> str:
    severities = {issue.get("severity") for issue in issues}
    if "error" in severities:
        return "fail"
    if "warn" in severities:
        return "warn"
    return "pass"


def summary(issues: list[dict]) -> dict:
    return {
        "error": sum(1 for issue in issues if issue.get("severity") == "error"),
        "warn": sum(1 for issue in issues if issue.get("severity") == "warn"),
        "info": sum(1 for issue in issues if issue.get("severity") == "info"),
    }
