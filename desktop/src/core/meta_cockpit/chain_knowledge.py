"""第三内容链（向上抽象 / 知识体系）。

cluster -> abstraction -> knowledge system。
重点：图结构需要 invariant 原语（无环、根可达），这是前两条链压不出来的。
"""

from __future__ import annotations

import json
from pathlib import Path

from . import json_asset
from . import schema_compat as jsonschema
from .criteria_lexicon import CHECK, EVID, PRIMITIVES, frac

BASE = Path(__file__).parent
SCHEMA = json_asset.load(BASE / "cognition_method.schema.json")

ALL_CLAIMS = [f"C{i}" for i in range(1, 9)]

CLUSTERS = {
    "schema": "nf/cluster-set/1",
    "clusters": [
        {"id": "T1", "theme": "资源与生存", "members": ["C1", "C2", "C3"]},
        {"id": "T2", "theme": "关系与情感", "members": ["C4", "C5"]},
        {"id": "T3", "theme": "确定性与返工", "members": ["C6", "C7", "C8"]},
    ],
}

ABSTRACTIONS = {
    "schema": "nf/abstraction-set/1",
    "abstractions": [
        {
            "id": "A1",
            "theme": "资源约束决定叙事压力",
            "scope": ["T1"],
            "evidence": "P03 §1",
            "descent_check": "t51",
            "evidence_refs": [{"source": "P03", "ref": "§1"}],
        },
        {
            "id": "A2",
            "theme": "关系密度决定情感张力",
            "scope": ["T2"],
            "evidence": "NF-1 §2",
            "descent_check": "t52",
            "evidence_refs": [{"source": "NF-1", "ref": "§2"}],
        },
        {
            "id": "A3",
            "theme": "确定性要求决定返工成本",
            "scope": ["T3"],
            "evidence": "P90 §3",
            "descent_check": "t53",
            "evidence_refs": [{"source": "P90", "ref": "§3"}],
        },
        {
            "id": "A0",
            "theme": "约束强度决定产物形态",
            "scope": ["T1", "T2", "T3"],
            "evidence": "P03 §1 + NF-1 §2 + P90 §3",
            "descent_check": "t50",
            "evidence_refs": [
                {"source": "P03", "ref": "§1"},
                {"source": "NF-1", "ref": "§2"},
                {"source": "P90", "ref": "§3"},
            ],
        },
    ],
}

SYSTEM = {
    "schema": "nf/knowledge-system/1",
    "nodes": ["A0", "A1", "A2", "A3"],
    "edges": [{"from": "A0", "to": "A1"}, {"from": "A0", "to": "A2"}, {"from": "A0", "to": "A3"}],
}

BAD = (
    {"schema": "nf/cluster-set/1", "clusters": []},
    {"schema": "nf/abstraction-set/1", "abstractions": []},
    {"schema": "nf/knowledge-system/1", "nodes": [], "edges": []},
)

GAMING = (
    {
        "schema": "nf/cluster-set/1",
        "clusters": [
            {"id": "T1", "theme": "全部", "members": ALL_CLAIMS},
            {"id": "T2", "theme": "重复", "members": ALL_CLAIMS},
        ],
    },
    {
        "schema": "nf/abstraction-set/1",
        "abstractions": [
            {
                "id": "A1",
                "theme": "整体上很重要",
                "scope": ["T1"],
                "evidence": "看起来重要",
                "descent_check": "看起来可以",
            },
            {
                "id": "A2",
                "theme": "细节上要注意",
                "scope": ["T1"],
                "evidence": "看起来重要",
                "descent_check": "看起来可以",
            },
        ],
    },
    {
        "schema": "nf/knowledge-system/1",
        "nodes": ["A1", "A2"],
        "edges": [
            {"from": "A1", "to": "A2"},
            {"from": "A2", "to": "A1"},
            {"from": "A1", "to": "A9"},
        ],
    },
)


def validate_def(name: str, payload: dict) -> bool:
    sub = {"$schema": SCHEMA["$schema"], "$defs": SCHEMA["$defs"], "$ref": f"#/$defs/{name}"}
    return not list(jsonschema.Draft202012Validator(sub).iter_errors(payload))


def acyclic(nodes: list[str], edges: list[dict]) -> bool:
    adj = {n: [] for n in nodes}
    for e in edges:
        if e["from"] in adj and e["to"] in adj:
            adj[e["from"]].append(e["to"])
    color = dict.fromkeys(nodes, 0)

    def dfs(u: str) -> bool:
        color[u] = 1
        for v in adj[u]:
            if color[v] == 1 or (color[v] == 0 and not dfs(v)):
                return False
        color[u] = 2
        return True

    return all(dfs(n) for n in nodes if color[n] == 0)


def root_coverage(nodes: list[str], edges: list[dict]) -> float:
    valid = [(e["from"], e["to"]) for e in edges if e["from"] in nodes and e["to"] in nodes]
    incoming = dict.fromkeys(nodes, 0)
    adj = {n: [] for n in nodes}
    for a, b in valid:
        incoming[b] += 1
        adj[a].append(b)
    roots = [n for n in nodes if incoming[n] == 0]
    seen: set[str] = set()

    def dfs(u: str) -> None:
        if u in seen:
            return
        seen.add(u)
        for v in adj[u]:
            dfs(v)

    for r in roots:
        dfs(r)
    return round(len(seen) / len(nodes), 3) if nodes else 0.0


def evaluate(name: str, clusters: dict, abstractions: dict, system: dict, universe=None):
    universe = list(universe or ALL_CLAIMS)
    cl = clusters["clusters"]
    ab = abstractions["abstractions"]
    nodes, edges = system["nodes"], system["edges"]
    members = [m for c in cl for m in c["members"]]
    cluster_ids = {c["id"] for c in cl}
    covered_clusters = {s for a in ab for s in a["scope"]} & cluster_ids
    m = {
        "cluster_count": len(cl),
        "member_coverage": round(len(set(members) & set(universe)) / len(universe), 3)
        if universe
        else 0.0,
        "member_uniqueness": frac(universe, lambda c: members.count(c) == 1),
        "cluster_nonempty": frac(cl, lambda c: len(c["members"]) > 0),
        "abstraction_coverage": round(len(covered_clusters) / len(cluster_ids), 3)
        if cluster_ids
        else 0.0,
        "scope_linkage": frac(ab, lambda a: all(s in cluster_ids for s in a["scope"])),
        "descent_check_rate": frac(ab, lambda a: bool(CHECK.search(a["descent_check"]))),
        "abstraction_evidence": frac(ab, lambda a: bool(EVID.search(a["evidence"]))),
        "node_coverage": round(
            len({a["id"] for a in ab} & set(nodes)) / len({a["id"] for a in ab}), 3
        )
        if ab
        else 0.0,
        "edge_linkage": frac(edges, lambda e: e["from"] in nodes and e["to"] in nodes),
        "acyclic": acyclic(nodes, edges),
        "root_coverage": root_coverage(nodes, edges),
    }
    ok = all(
        [
            m["cluster_count"] >= 2,
            m["member_coverage"] >= 0.995,
            m["member_uniqueness"] >= 0.995,
            m["cluster_nonempty"] >= 0.995,
            m["abstraction_coverage"] >= 0.995,
            m["scope_linkage"] >= 0.995,
            m["descent_check_rate"] >= 0.995,
            m["abstraction_evidence"] >= 0.875,
            m["node_coverage"] >= 0.995,
            m["edge_linkage"] >= 0.995,
            m["acyclic"] is True,
            m["root_coverage"] >= 0.995,
        ]
    )
    print(
        "[{}] {} -> {}".format(
            name, " ".join("{}={}".format(*kv) for kv in m.items()), "PASS" if ok else "FAIL"
        )
    )
    return m, ok


if __name__ == "__main__":
    for label, bundle in [
        ("GOOD", (CLUSTERS, ABSTRACTIONS, SYSTEM)),
        ("BAD", BAD),
        ("GAMING", GAMING),
    ]:
        io = all(
            [
                validate_def("cluster_set", bundle[0]),
                validate_def("abstraction_set", bundle[1]),
                validate_def("knowledge_system", bundle[2]),
            ]
        )
        print(f"[{label}] io={io}")
        evaluate(label, *bundle)

    print(
        "[VOCABULARY] has_invariant={} version_ok={}".format(
            "invariant" in PRIMITIVES, "invariant" in json.dumps(SCHEMA)
        )
    )
