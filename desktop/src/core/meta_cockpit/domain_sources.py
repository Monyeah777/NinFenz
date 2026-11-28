"""NF community 域包索引：只读、确定性、按任务词面匹配。"""

from __future__ import annotations

import hashlib
import json
import re
from functools import lru_cache
from pathlib import Path

from .repo_context import repository_root

NF = repository_root()
COMMUNITY = NF / "community"
STOP_TERMS = {"通用", "核心", "基础", "领域", "组合", "域包"}
GENERIC_MATCH_TERMS = {
    "决策",
    "系统",
    "成本",
    "安全",
    "数据",
    "模型",
    "代码",
    "内容",
    "文本",
}


def _keywords(folder: str) -> list[str]:
    core = folder
    for suffix in ("领域包", "组合包", "基础包", "域包"):
        core = core.removesuffix(suffix)
    values = [core]
    values += re.split(r"[与和及、\-]", core)
    return sorted({value for value in values if len(value) >= 2 and value not in STOP_TERMS})


def _entry(folder: Path) -> dict | None:
    for filename in ("README.md", "protocol.yaml"):
        path = folder / filename
        if path.is_file():
            return {
                "id": "community:" + folder.name,
                "kind": "community-domain-pack",
                "path": str(path.relative_to(NF)),
                "keywords": _keywords(folder.name),
            }
    return None


def _scan() -> list[dict]:
    if not COMMUNITY.is_dir():
        return []
    entries = []
    for folder in sorted(COMMUNITY.iterdir(), key=lambda item: item.name):
        if not folder.is_dir():
            continue
        entry = _entry(folder)
        if entry is not None:
            entries.append(entry)
    return entries


DOMAINS = _scan()
BY_ID = {item["id"]: item for item in DOMAINS}
INDEX_BYTES = json.dumps(DOMAINS, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
    "utf-8"
)
INDEX_DIGEST = hashlib.sha256(INDEX_BYTES).hexdigest()
MODULE_TITLE = re.compile(r"^#\s*模块\s+(?:[^:]+:)?(M\d+)\s*[·:]\s*(.+)$")
PIPELINE_TITLE = re.compile(r"^#\s*管线\s+(P\d+)\s*[·:]\s*(.+)$")
DEPENDENCIES = re.compile(r"依赖：([^｜\n]+)")
LAYER = re.compile(r"挂载点：([P]\d+)")


def _text_hits(entry: dict, text: str) -> tuple[list[str], list[str]]:
    all_hits = [keyword for keyword in entry["keywords"] if keyword in text]
    specific_hits = [keyword for keyword in all_hits if keyword not in GENERIC_MATCH_TERMS]
    generic_hits = [keyword for keyword in all_hits if keyword in GENERIC_MATCH_TERMS]
    return specific_hits, generic_hits


def _match_of(entry: dict, specific_hits: list[str], generic_hits: list[str]) -> dict | None:
    if not specific_hits and not generic_hits:
        return None
    selected_hits = specific_hits or generic_hits
    return {
        **entry,
        "matched_keywords": sorted(selected_hits),
        "match_units": sum(len(keyword) for keyword in selected_hits),
        "specificity": max(len(keyword) for keyword in selected_hits),
        "match_tier": "specific" if specific_hits else "adjacent",
    }


def _match_sort_key(item: dict) -> tuple:
    return (-item["match_units"], -item["specificity"], item["id"])


def select_for_text(text: str, limit: int = 1, include_adjacent: bool = False) -> list[dict]:
    specific: list[dict] = []
    adjacent: list[dict] = []
    for entry in DOMAINS:
        specific_hits, generic_hits = _text_hits(entry, text)
        match = _match_of(entry, specific_hits, generic_hits)
        if match is None:
            continue
        if specific_hits:
            specific.append(match)
        else:
            adjacent.append(match)
    specific.sort(key=_match_sort_key)
    adjacent.sort(key=_match_sort_key)
    if not specific:
        return []
    matches = specific[:limit]
    if include_adjacent and len(matches) < limit:
        matches += adjacent[: limit - len(matches)]
    return matches


@lru_cache(maxsize=32)
def _concept_graph(path_text: str, mtime_ns: int, size: int) -> tuple[dict, ...]:
    del mtime_ns, size
    path = Path(path_text)
    if not path.is_file():
        return ()
    nodes: dict[str, dict] = {}
    rows = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.startswith("| `"):
            continue
        columns = [value.strip() for value in line.split("|")]
        if len(columns) < 7:
            continue
        node_id = columns[1].strip("`")
        prereq_ids = re.findall(r"`([^`]+)`", columns[4])
        nodes[node_id] = {
            "id": node_id,
            "concept": columns[2],
            "layer": columns[3],
            "prerequisites": prereq_ids,
        }
        rows.append(node_id)
    return tuple(nodes[node_id] for node_id in rows)


def concept_graph(entry: dict) -> tuple[dict, ...]:
    assets = (NF / entry["path"]).resolve().parent / "assets"
    candidates = []
    standard = assets / "CONCEPT_GRAPH.md"
    if standard.is_file():
        candidates.append(standard)
    if assets.is_dir():
        candidates += sorted(
            path for path in assets.glob("*GRAPH*.md") if path.is_file() and path not in candidates
        )
    for path in candidates:
        stat = path.stat()
        graph = _concept_graph(str(path), stat.st_mtime_ns, stat.st_size)
        if graph:
            return graph
    modules = _module_graph(entry)
    if modules:
        return modules
    pipelines = _pipeline_graph(entry)
    if pipelines:
        return pipelines
    return ()


def _module_node(path: Path) -> tuple[str, dict] | None:
    text = path.read_text(encoding="utf-8", errors="replace")
    title = next(
        (MODULE_TITLE.match(line) for line in text.splitlines() if MODULE_TITLE.match(line)),
        None,
    )
    if title is None:
        return None
    node_id = title.group(1)
    layer_match = LAYER.search(text)
    dependency_line = DEPENDENCIES.search(text)
    prerequisites = re.findall(r"M\d+", dependency_line.group(1)) if dependency_line else []
    return node_id, {
        "id": node_id,
        "concept": title.group(2).strip(),
        "layer": layer_match.group(1) if layer_match else "unknown",
        "prerequisites": prerequisites,
    }


def _module_externals(nodes: dict[str, dict]) -> None:
    for node in list(nodes.values()):
        for prerequisite in node["prerequisites"]:
            if prerequisite not in nodes:
                nodes[prerequisite] = {
                    "id": prerequisite,
                    "concept": prerequisite,
                    "layer": "external",
                    "prerequisites": [],
                }


def _module_order(nodes: dict[str, dict], order: list[str]) -> tuple[dict, ...]:
    return tuple(nodes[node_id] for node_id in order if node_id in nodes) + tuple(
        node for node_id, node in nodes.items() if node_id not in order
    )


def _module_graph(entry: dict) -> tuple[dict, ...]:
    folder = (NF / entry["path"]).resolve().parent / "modules"
    if not folder.is_dir():
        return ()
    nodes: dict[str, dict] = {}
    order: list[str] = []
    for path in sorted(folder.glob("*.md")):
        parsed = _module_node(path)
        if parsed is None:
            continue
        node_id, node = parsed
        nodes[node_id] = node
        order.append(node_id)
    _module_externals(nodes)
    return _module_order(nodes, order)


def _pipeline_graph(entry: dict) -> tuple[dict, ...]:
    folder = (NF / entry["path"]).resolve().parent / "pipelines"
    if not folder.is_dir():
        return ()
    nodes: list[dict] = []
    for path in sorted(folder.glob("*.md")):
        text = path.read_text(encoding="utf-8", errors="replace")
        title = next(
            (
                PIPELINE_TITLE.match(line)
                for line in text.splitlines()
                if PIPELINE_TITLE.match(line)
            ),
            None,
        )
        if title is None:
            continue
        nodes.append(
            {
                "id": title.group(1),
                "concept": title.group(2).strip(),
                "layer": "pipeline",
                "prerequisites": [],
            }
        )
    return tuple(nodes)


def _cycle_warnings(entry: dict, graph: tuple[dict, ...]) -> list[dict]:
    cycle = _cycle_path(graph)
    if not cycle:
        return []
    return [{"source": entry["id"], "kind": "module-dependency-cycle", "cycle": cycle}]


def _seed_nodes(graph: tuple[dict, ...], entry: dict, text: str) -> list[dict]:
    return [
        node
        for node in graph
        if any(keyword in node["concept"] for keyword in entry["keywords"])
        or node["concept"] in text
    ]


def _selected_ids(graph: tuple[dict, ...], seeds: list[dict]) -> list[str]:
    selected = set()
    for node in seeds:
        selected.add(node["id"])
        selected.update(node["prerequisites"])
        selected.update(
            candidate["id"] for candidate in graph if node["id"] in candidate["prerequisites"]
        )
    return sorted(selected)


def _node_edges(
    by_id: dict[str, dict], node: dict, selected_ids: list[str], entry: dict
) -> list[dict]:
    edges = []
    for prerequisite in node["prerequisites"]:
        if prerequisite in selected_ids and prerequisite in by_id:
            edges.append(
                {
                    "from": by_id[prerequisite]["concept"],
                    "to": node["concept"],
                    "kind": "domain-prerequisite",
                    "source": entry["id"],
                }
            )
    return edges


def graph_slice_for_text(text: str, entries: list[dict], max_nodes: int = 6) -> dict:
    edges = []
    nodes: dict[str, dict] = {}
    matched = []
    warnings = []
    graph_sources = []
    for entry in entries:
        if len(nodes) >= max_nodes:
            break
        graph = concept_graph(entry)
        graph_sources += graph_source_snapshot(entry)
        warnings += _cycle_warnings(entry, graph)
        by_id = {node["id"]: node for node in graph}
        seeds = _seed_nodes(graph, entry, text)
        if not seeds:
            continue
        selected_ids = _selected_ids(graph, seeds)[: max_nodes - len(nodes)]
        for node_id in selected_ids:
            node = by_id[node_id]
            nodes[node["concept"]] = {
                "id": node["id"],
                "concept": node["concept"],
                "layer": node["layer"],
                "source": entry["id"],
            }
            edges += _node_edges(by_id, node, selected_ids, entry)
        matched += [node["concept"] for node in seeds]
    unique = {(edge["from"], edge["to"], edge["kind"], edge["source"]): edge for edge in edges}
    ordered_edges = [unique[key] for key in sorted(unique)]
    return {
        "matched_concepts": sorted(set(matched)),
        "nodes": [nodes[key] for key in sorted(nodes)],
        "edges": ordered_edges,
        "warnings": warnings,
        "sources": graph_sources,
    }


def graph_source_snapshot(entry: dict) -> list[dict]:
    folder = (NF / entry["path"]).resolve().parent
    assets = folder / "assets"
    graph_paths = []
    if assets.is_dir():
        graph_paths = sorted(assets.glob("*GRAPH*.md"))
    selected = []
    for path in graph_paths:
        stat = path.stat()
        if _concept_graph(str(path), stat.st_mtime_ns, stat.st_size):
            selected = [path]
            break
    if not selected:
        for name in ("modules", "pipelines"):
            root = folder / name
            if root.is_dir():
                selected = sorted(root.glob("*.md"))
            if selected:
                break
    return [
        {
            "source": entry["id"],
            "path": str(path.relative_to(NF)),
            "kind": "graph-source",
            "file_digest": hashlib.sha256(path.read_bytes()).hexdigest(),
        }
        for path in selected
    ]


def _cycle_path(graph: tuple[dict, ...]) -> list[str]:
    by_id = {node["id"]: node for node in graph}
    visiting: set[str] = set()
    done: set[str] = set()
    stack: list[str] = []

    def visit(node_id: str) -> list[str]:
        if node_id in done:
            return []
        if node_id in visiting:
            start = stack.index(node_id)
            return stack[start:] + [node_id]
        visiting.add(node_id)
        stack.append(node_id)
        found = []
        for prerequisite in by_id[node_id]["prerequisites"]:
            if prerequisite in by_id:
                found = visit(prerequisite)
                if found:
                    break
        stack.pop()
        visiting.remove(node_id)
        done.add(node_id)
        return found

    for node_id in by_id:
        if node_id not in done:
            found = visit(node_id)
            if found:
                return found
    return []
