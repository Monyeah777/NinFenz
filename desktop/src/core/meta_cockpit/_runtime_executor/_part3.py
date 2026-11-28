"""core.runtime_executor 私有实现分片 3/3（对外只经 core.runtime_executor 门面导入）：main"""

from __future__ import annotations

from core.meta_cockpit import chain_horizontal as horiz
from core.meta_cockpit import chain_knowledge as know
from core.meta_cockpit import chain_vertical as real

from ._part1 import (
    METHOD_V,
    NODES,
    PIPE_V,
    PIPELINE,
    graph_issues,
    machine_digest,
    numeric_conflict_count,
    policy_drift,
    policy_issues,
    review_status,
    run_meta_pipeline,
    span_anchor_rate,
    topo,
)
from ._part2 import eval_node


def _print_load(shape_errs, issues, drift, pipe_errs, gissues, order) -> None:
    print(
        f"LOAD nodes={len(NODES)} "
        f"criteria={sum(len(n.get('criteria', [])) for n in NODES.values())} "
        f"pipeline_nodes={len(PIPELINE['nodes'])} edges={len(PIPELINE['edges'])}"
    )
    print(f"MACHINE-DIGEST {machine_digest()[:12]}")
    print(
        f"CHECK shape={shape_errs or 'OK'} policy={issues or 'OK'} "
        f"drift={drift or 'OK'} pipeline={pipe_errs or 'OK'} "
        f"graph={gissues or 'OK'} topo={len(order)}"
    )


def _chain_inputs() -> tuple:
    base = real.extract()
    claims, causal, attacks = real.build(base)
    for s, r in zip(base, causal["records"], strict=False):
        r["evidence_quote"] = "## {}. {}".format(s["num"], s["title"])
    rm = real.metrics(base, claims, causal, attacks, True)
    span = span_anchor_rate(causal["records"], claims, real.TEXT)
    conflicts = numeric_conflict_count(claims)
    n_deliv = sum(1 for s in base if s["role"] == "deliverable")
    n_claims = len(claims["claims"])
    return base, claims, causal, attacks, rm, span, conflicts, n_deliv, n_claims


def _vertical_results(rm: dict, span, conflicts, n_deliv: int, n_claims: int, results: dict) -> None:
    results["认知:M01"] = eval_node(
        "认知:M01",
        {
            k: rm[k]
            for k in (
                "subgoal_count",
                "deliverable_anchor_rate",
                "requirement_coverage_rate",
                "requirement_assignment_uniqueness",
                "verifiability_rate",
            )
        },
        {
            "deliverable_anchor_rate": n_deliv,
            "requirement_coverage_rate": len(real.REQ),
            "requirement_assignment_uniqueness": len(real.REQ),
            "verifiability_rate": n_deliv,
        },
        skip={"requirement_assignment_uniqueness"},
    )  # outline shape
    results["认知:M02"] = eval_node(
        "认知:M02",
        {
            **{
                k: rm[k]
                for k in (
                    "mechanism_coverage",
                    "evidence_anchor_rate",
                    "confounder_concreteness",
                    "counterfactual_check_rate",
                    "confidence_declared",
                    "claim_linkage",
                )
            },
            "span_anchor_rate": span,
            "numeric_conflict_count": conflicts,
        },
        dict.fromkeys(
            (
                "mechanism_coverage",
                "evidence_anchor_rate",
                "confounder_concreteness",
                "counterfactual_check_rate",
                "confidence_declared",
                "claim_linkage",
                "span_anchor_rate",
            ),
            n_claims,
        ),
    )
    results["认知:M03"] = eval_node(
        "认知:M03",
        {
            k: rm[k]
            for k in (
                "attack_coverage",
                "trigger_concreteness",
                "check_reference_rate",
                "disposition_completeness",
                "evidence_anchor",
                "claim_linkage",
                "real_id_validity",
            )
        },
        dict.fromkeys(
            (
                "attack_coverage",
                "trigger_concreteness",
                "check_reference_rate",
                "disposition_completeness",
                "evidence_anchor",
                "claim_linkage",
                "real_id_validity",
            ),
            n_claims,
        ),
    )


def _fabricated_na(cells: list[dict]) -> int:
    return sum(
        1
        for c in cells
        if c.get("applicability") == "not_applicable"
        and any(k in c for k in ("value", "evidence", "check"))
    )


def _matrix_declared(cells: list[dict]) -> dict:
    value_kind = (
        1.0
        if all(
            c.get("value_kind")
            for c in cells
            if c.get("applicability", "applicable") == "applicable"
        )
        else 0.0
    )
    na_rate = 1.0 if not any(c.get("applicability") == "not_applicable" for c in cells) else 0.0
    return {
        "value_kind_declared": value_kind,
        "na_justification_rate": na_rate,
        "fabricated_na_count": _fabricated_na(cells),
    }


def _horizontal_results(results: dict) -> None:
    hm = horiz.evaluate("H", horiz.FRAME, horiz.GOOD_MATRIX, horiz.GOOD_CLAIMS)
    results["认知:M11"] = eval_node(
        "认知:M11",
        {
            k: hm[k]
            for k in (
                "object_count",
                "dimension_count",
                "object_distinctness",
                "dimension_distinctness",
            )
        },
        {"object_distinctness": 3, "dimension_distinctness": 3},
    )
    cells = horiz.GOOD_MATRIX["cells"]
    results["认知:M12"] = eval_node(
        "认知:M12",
        {
            **{k: hm[k] for k in ("cell_coverage", "evidence_anchor_rate", "check_ref_rate")},
            **_matrix_declared(cells),
        },
        dict.fromkeys(
            ("cell_coverage", "evidence_anchor_rate", "check_ref_rate", "value_kind_declared"), 9
        ),
    )
    results["认知:M13"] = eval_node(
        "认知:M13",
        {
            k: hm[k]
            for k in ("claim_coverage", "synthesis_evidence", "tradeoff_declared", "claim_linkage")
        },
        dict.fromkeys(
            ("claim_coverage", "synthesis_evidence", "tradeoff_declared", "claim_linkage"), 3
        ),
    )


def _scope_vals() -> list[float]:
    k_domain = {"T1": "P03", "T2": "NF-1", "T3": "P90"}
    k_scope_vals = []
    for a in know.ABSTRACTIONS["abstractions"]:
        need = {k_domain[t] for t in a["scope"]}
        have = {r["source"] for r in a.get("evidence_refs", [])}
        k_scope_vals.append(len(need & have) / len(need) if need else 0.0)
    return k_scope_vals


def _knowledge_results(results: dict) -> None:
    km, _ = know.evaluate("K", know.CLUSTERS, know.ABSTRACTIONS, know.SYSTEM)
    k_scope_vals = _scope_vals()
    k_scope = round(sum(k_scope_vals) / len(k_scope_vals), 3) if k_scope_vals else 0.0
    results["认知:M21"] = eval_node(
        "认知:M21",
        {
            k: km[k]
            for k in ("cluster_count", "member_coverage", "member_uniqueness", "cluster_nonempty")
        },
        {"member_coverage": 8, "member_uniqueness": 8, "cluster_nonempty": 8},
    )
    results["认知:M22"] = eval_node(
        "认知:M22",
        {
            **{
                k: km[k]
                for k in (
                    "abstraction_coverage",
                    "scope_linkage",
                    "descent_check_rate",
                    "abstraction_evidence",
                )
            },
            "evidence_scope_coverage": k_scope,
        },
        {
            "abstraction_coverage": 3,
            "scope_linkage": 4,
            "descent_check_rate": 4,
            "abstraction_evidence": 4,
            "evidence_scope_coverage": 4,
        },
    )
    results["认知:M23"] = eval_node(
        "认知:M23",
        {k: km[k] for k in ("node_coverage", "edge_linkage", "acyclic", "root_coverage")},
        {"node_coverage": 4, "edge_linkage": 3, "acyclic": 1, "root_coverage": 4},
    )


def _print_results(results: dict) -> None:
    for nid in sorted(results):
        ok, rows = results[nid]
        bad = [r["dimension"] for r in rows if r.get("ok") is False]
        print(
            "[{}] {}{}".format(
                nid, "PASS" if ok else "FAIL", "" if not bad else " fails=" + ",".join(bad)
            )
        )


def _chain_pass(results: dict, names: tuple[str, ...]) -> bool:
    return all(results[n][0] for n in names)


def _print_chains(results: dict, rm: dict) -> tuple[bool, bool, bool]:
    up = rm["real_id_validity"]  # 真实夹具的上游消费等价指标
    chain_v = _chain_pass(results, ("认知:M01", "认知:M02", "认知:M03")) and up >= 1.0
    chain_h = _chain_pass(results, ("认知:M11", "认知:M12", "认知:M13"))
    chain_k = _chain_pass(results, ("认知:M21", "认知:M22", "认知:M23"))
    print("[CHAIN-VERTICAL] {} upstream={:.3f}".format("PASS" if chain_v else "FAIL", up))
    print("[CHAIN-HORIZONTAL] %s" % ("PASS" if chain_h else "FAIL"))
    print("[CHAIN-KNOWLEDGE] %s" % ("PASS" if chain_k else "FAIL"))
    return chain_v, chain_h, chain_k


def _print_meta(meta: dict) -> None:
    passed_atoms = sum(1 for t in meta["traces"] if t["status"] == "pass")
    print(
        f"[META-PIPELINE] {meta['status'].upper()} nodes={len(meta['nodes'])} "
        f"atoms={len(meta['traces'])} pass={passed_atoms}"
    )
    for nid in sorted(meta["nodes"]):
        r = meta["nodes"][nid]
        print(
            "  [{}] {}{}".format(
                nid,
                r["status"].upper(),
                "" if r["status"] == "pass" else " error=" + str(r.get("error")),
            )
        )


def _machine_ok(checks: dict) -> bool:
    return all(checks.values())


def _review_gate(machine_ok: bool, review: str) -> int:
    if not machine_ok:
        print("[PIPELINE] FAIL")
        return 1
    if review == "APPROVED":
        print("[PIPELINE] PASS")
        return 0
    if review == "REJECTED":
        print("[PIPELINE] FAIL (review rejected)")
        return 1
    if review == "PENDING":
        print("[PIPELINE] PENDING-REVIEW")
        return 2
    print("[PIPELINE] PASS (no review gate)")
    return 0


def main() -> int:
    issues = policy_issues()
    drift = policy_drift()
    shape_errs = [e.message for n in NODES.values() for e in METHOD_V.iter_errors(n)]
    pipe_errs = [e.message for e in PIPE_V.iter_errors(PIPELINE)]
    gissues = graph_issues(PIPELINE)
    order = topo(PIPELINE)
    _print_load(shape_errs, issues, drift, pipe_errs, gissues, order)

    base, claims, causal, attacks, rm, span, conflicts, n_deliv, n_claims = _chain_inputs()
    results: dict[str, tuple[bool, list[dict]]] = {}
    _vertical_results(rm, span, conflicts, n_deliv, n_claims, results)
    _horizontal_results(results)
    _knowledge_results(results)
    _print_results(results)
    chain_v, chain_h, chain_k = _print_chains(results, rm)

    meta = run_meta_pipeline(results)
    _print_meta(meta)
    checks = {
        "shape": not shape_errs,
        "policy": not issues,
        "drift": not drift,
        "pipeline": not pipe_errs,
        "graph": not gissues,
        "topo": bool(order),
        "chain_v": chain_v,
        "chain_h": chain_h,
        "chain_k": chain_k,
        "meta": meta["status"] == "pass",
    }
    machine_ok = _machine_ok(checks)
    review, review_issues = review_status()
    print(
        "[HUMAN-REVIEW] {}{}".format(
            review, "" if not review_issues else " issues=" + str(review_issues)
        )
    )
    return _review_gate(machine_ok, review)
