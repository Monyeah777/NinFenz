"""core.runtime_executor 私有实现分片 1/2（对外只经 core.runtime_executor 门面导入）：BASE 等"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from core.meta_cockpit import json_asset
from core.meta_cockpit import meta_atom_runtime as atoms
from core.meta_cockpit import schema_compat as jsonschema
from core.meta_cockpit.repo_context import implementation_files

BASE = Path(__file__).parent.parent


METHOD_SCHEMA = json_asset.load(BASE / "cognition_method.schema.json")


PIPE_SCHEMA = json_asset.load(BASE / "cognition_pipeline.schema.json")


METHOD_V = jsonschema.Draft202012Validator(METHOD_SCHEMA)


PIPE_V = jsonschema.Draft202012Validator(PIPE_SCHEMA)


NODES = {}


for p in sorted(BASE.glob("method_*.json")):
    doc = json_asset.load(p)
    NODES[doc["id"]] = doc


PIPELINE = json_asset.load(BASE / "cognition_pipeline.json")


META_PIPELINE = json_asset.load(BASE / "cognition_meta_pipeline.json")


MAX_MISSING_CAP = 8


def bigrams(text: str) -> set[str]:
    chars = re.findall(r"[\u4e00-\u9fff]", text)
    return {chars[i] + chars[i + 1] for i in range(len(chars) - 1)}


def span_anchor_rate(records: list[dict], claims: dict, source: str) -> float:
    texts = {c["id"]: c["text"] for c in claims["claims"]}
    ok = 0
    for r in records:
        q = str(r.get("evidence_quote") or "")
        if q and q in source and bigrams(texts.get(r["claim"], "")) & bigrams(q):
            ok += 1
    return round(ok / len(records), 3) if records else 0.0


def numeric_conflict_count(claims: dict) -> int:
    vals: dict[str, set[str]] = {}
    for c in claims["claims"]:
        for m in re.finditer(r"([\u4e00-\u9fffA-Za-z_]+)\s*[=为]\s*(\d+)", c["text"]):
            vals.setdefault(m.group(1), set()).add(m.group(2))
    return sum(1 for v in vals.values() if len(v) > 1)


def machine_digest() -> str:
    names = implementation_files()
    payload = {n: hashlib.sha256((BASE / n).read_bytes()).hexdigest() for n in names}
    canon = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()


def _graph_edge_issues(p: dict, nodes: dict) -> list[str]:
    issues: list[str] = []
    for e in p["edges"]:
        if e["from"] not in nodes or e["to"] not in nodes:
            issues.append("edge-ref-missing")
            continue
        fo = {(x["token"], x["kind"]) for x in nodes[e["from"]]["outputs"]}
        ti = {(x["token"], x["kind"]) for x in nodes[e["to"]]["inputs"]}
        if (e["output"], e["kind"]) not in fo or (e["input"], e["kind"]) not in ti:
            issues.append("typed-edge-mismatch")
    return issues


def _graph_has_cycle(ids: list[str], adj: dict[str, list[str]]) -> bool:
    color = dict.fromkeys(ids, 0)

    def dfs(u: str) -> bool:
        color[u] = 1
        for v in adj[u]:
            if color[v] == 1 or (color[v] == 0 and not dfs(v)):
                return False
        color[u] = 2
        return True

    return not all(dfs(i) for i in ids if color[i] == 0)


def _graph_tail_issues(p: dict, ids: list[str]) -> list[str]:
    issues: list[str] = []
    outdeg: dict[str, int] = dict.fromkeys(ids, 0)
    for e in p["edges"]:
        if e["from"] in outdeg:
            outdeg[e["from"]] += 1
    for i in ids:
        if i not in p["exit"] and outdeg[i] == 0:
            issues.append("orphan-output:" + i)
    if sum(n["cost"] for n in p["nodes"]) > p["budget_envelope"]:
        issues.append("budget-overflow")
    return issues


def graph_issues(p: dict) -> list[str]:
    issues: list[str] = []
    ids = [n["id"] for n in p["nodes"]]
    if len(ids) != len(set(ids)):
        issues.append("duplicate-node-id")
    nodes = {n["id"]: n for n in p["nodes"]}
    issues += _graph_edge_issues(p, nodes)
    adj: dict[str, list[str]] = {i: [] for i in ids}
    for e in p["edges"]:
        if e["from"] in adj and e["to"] in adj:
            adj[e["from"]].append(e["to"])
    if _graph_has_cycle(ids, adj):
        issues.append("cycle")
    issues += _graph_tail_issues(p, ids)
    return issues


def _topo_state(p: dict, ids: list[str]) -> tuple[dict[str, list[str]], dict[str, int]]:
    adj: dict[str, list[str]] = {i: [] for i in ids}
    indeg: dict[str, int] = dict.fromkeys(ids, 0)
    for e in p["edges"]:
        if e["from"] in adj and e["to"] in indeg:
            adj[e["from"]].append(e["to"])
            indeg[e["to"]] += 1
    return adj, indeg


def topo(p: dict) -> list[str]:
    ids = [n["id"] for n in p["nodes"]]
    adj, indeg = _topo_state(p, ids)
    q = [i for i in ids if indeg[i] == 0]
    order: list[str] = []
    while q:
        u = q.pop(0)
        order.append(u)
        for v in adj[u]:
            indeg[v] -= 1
            if indeg[v] == 0:
                q.append(v)
    return order if len(order) == len(ids) else []


def _ratio_criterion_issues(nid: str, c: dict) -> list[str]:
    issues: list[str] = []
    if "max_missing" not in c:
        issues.append("{}/{} missing max_missing".format(nid, c["dimension"]))
    elif c["max_missing"] > MAX_MISSING_CAP:
        issues.append(
            "{}/{} max_missing={} exceeds cap {}".format(
                nid, c["dimension"], c["max_missing"], MAX_MISSING_CAP
            )
        )
    if c["threshold"] <= 0:
        issues.append(
            "{}/{} degenerate threshold={}".format(nid, c["dimension"], c["threshold"])
        )
    return issues


def _primitive_criterion_issues(nid: str, c: dict) -> list[str]:
    issues: list[str] = []
    if (
        c.get("primitive") == "count"
        and c["threshold"] < 1
        and c.get("direction") != "lower_better"
    ):
        issues.append("{}/{} count threshold<1".format(nid, c["dimension"]))
    if c.get("primitive") == "check_ref":
        if "ref_kind" not in c:
            issues.append("{}/{} missing ref_kind".format(nid, c["dimension"]))
        elif c["ref_kind"] == "identifier" and "requires_real_id" not in c:
            issues.append("{}/{} missing requires_real_id".format(nid, c["dimension"]))
    return issues


def policy_issues(nodes: dict | None = None) -> list[str]:
    nodes = nodes if nodes is not None else NODES
    issues: list[str] = []
    for nid, node in nodes.items():
        for c in node.get("criteria", []):
            unit = c.get("unit", "ratio")
            if unit == "ratio":
                issues += _ratio_criterion_issues(nid, c)
            issues += _primitive_criterion_issues(nid, c)
    return issues


def policy_signature(nodes: dict | None = None) -> tuple[list[dict], str]:
    nodes = nodes if nodes is not None else NODES
    rows = []
    for nid, node in nodes.items():
        for c in node.get("criteria", []):
            rows.append(
                {
                    "node": nid,
                    "name": node.get("name"),
                    "dimension": c.get("dimension"),
                    "primitive": c.get("primitive"),
                    "unit": c.get("unit", "ratio"),
                    "threshold": c.get("threshold"),
                    "granularity": c.get("granularity"),
                    "max_missing": c.get("max_missing"),
                    "role_scope": c.get("role_scope"),
                    "requires_real_id": c.get("requires_real_id"),
                    "ref_kind": c.get("ref_kind"),
                    "direction": c.get("direction"),
                }
            )
    rows.sort(key=lambda r: (r["node"], r["dimension"]))
    payload = {
        "schema": "nf-criterion-policy/1",
        "generated_from": sorted(p.name for p in BASE.glob("method_*.json")),
        "rows": rows,
    }
    canon = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return rows, hashlib.sha256(canon.encode("utf-8")).hexdigest()


def policy_drift(doc: dict | None = None, nodes: dict | None = None) -> list[str]:
    doc = doc if doc is not None else json_asset.load(BASE / "criterion_policy.json")
    rows, digest = policy_signature(nodes)
    issues = []
    if doc.get("digest") != digest:
        issues.append(
            "policy digest drift: file={} expected={}".format(
                str(doc.get("digest"))[:12], digest[:12]
            )
        )
    if doc.get("rows") != rows:
        issues.append("policy rows drift")
    return issues


def _review_validator() -> jsonschema.Draft202012Validator:
    hr_schema = json_asset.load(BASE / "human_review.schema.json")
    return jsonschema.Draft202012Validator(
        {"$schema": hr_schema["$schema"], "$defs": hr_schema["$defs"], "$ref": "#/$defs/record"}
    )


def _has_non_pass_check(rec: dict) -> bool:
    return any(c.get("verdict") != "pass" for c in rec.get("checks", []))


def _review_record_issues(rec: dict, gate: dict) -> list[str]:
    issues = [e.message for e in _review_validator().iter_errors(rec)]
    if rec.get("gate_id") != gate.get("gate_id"):
        issues.append("gate_id mismatch")
    if rec.get("machine_digest") != machine_digest():
        issues.append("stale machine_digest")
    if rec.get("decision") != "approve":
        issues.append("decision is not approve")
    if rec.get("decision") == "approve" and _has_non_pass_check(rec):
        issues.append("approve with non-pass check")
    return issues


def review_status() -> tuple[str, list[str]]:
    gate_path = BASE / "human_review_gate.json"
    rec_path = BASE / "human_review_record.json"
    if not gate_path.is_file():
        return "NOT-CONFIGURED", []
    gate = json_asset.load(gate_path)
    if not rec_path.is_file():
        return "PENDING", ["no human_review_record.json"]
    rec = json_asset.load(rec_path)
    issues = _review_record_issues(rec, gate)
    return ("APPROVED" if not issues else "REJECTED"), issues


def _pipeline_catalog() -> list[dict]:
    return [
        {
            "id": nid,
            "meta_level": n.get("meta_level"),
            "meta_function": n.get("meta_function"),
            "atoms": n.get("atoms", []),
        }
        for nid, n in sorted(NODES.items())
    ]


def _pipeline_verdicts(results: dict) -> list[dict]:
    return [
        {"id": nid, "ok": ok, "fails": [r["dimension"] for r in rows if r.get("ok") is False]}
        for nid, (ok, rows) in sorted(results.items())
    ]


def run_meta_pipeline(results: dict) -> dict:
    catalog = _pipeline_catalog()
    verdicts = _pipeline_verdicts(results)
    used = sum(n["cost"] for n in PIPELINE["nodes"])
    budget_state = {
        "envelope": PIPELINE["budget_envelope"],
        "used": used,
        "remaining": PIPELINE["budget_envelope"] - used,
    }
    frame = json_asset.load(BASE / "criterion_policy.json")
    gate = json_asset.load(BASE / "human_review_gate.json")
    evidence = [{"id": "HR-001", "task_type": "content-production", "gate": gate}]
    task_type = "content-production"
    task = {
        "task_type": task_type,
        "levels": ["M0", "M1"],
        "functions": ["knowledge", "evaluation", "integration"],
    }
    nodes: dict[str, dict] = {}
    traces: list[dict] = []

    m31 = atoms.execute_node(
        NODES["认知:M31"],
        {
            "requirement": task_type,
            "options": catalog,
            "goal": task,
            "budget": budget_state,
            "fallback": {},
        },
    )
    nodes["认知:M31"] = m31
    traces += m31["atom_trace"]
    if m31["status"] != "pass":
        return {"status": "fail", "nodes": nodes, "traces": traces, "error": m31["error"]}
    plan = m31["output"]["plan"]

    m32 = atoms.execute_node(
        NODES["认知:M32"], {"target": plan, "reference": catalog, "node_verdicts": verdicts}
    )
    m41 = atoms.execute_node(NODES["认知:M41"], {"plan": plan, "budget_state": budget_state})
    m51 = atoms.execute_node(
        NODES["认知:M51"], {"target": frame, "reference": verdicts, "frame": frame}
    )
    m52 = atoms.execute_node(
        NODES["认知:M52"],
        {
            "options": evidence,
            "goal": {"task_type": task_type},
            "library": evidence,
            "task_type": task_type,
        },
    )
    for nid, res in (("认知:M32", m32), ("认知:M41", m41), ("认知:M51", m51), ("认知:M52", m52)):
        nodes[nid] = res
        traces += res["atom_trace"]

    ok = all(v["status"] == "pass" for v in nodes.values())
    if m41["status"] == "pass" and m41["output"].get("decision", {}).get("action") == "stop":
        ok = False
    return {
        "status": "pass" if ok else "fail",
        "nodes": nodes,
        "traces": traces,
        "plan": plan,
        "budget_state": budget_state,
    }
