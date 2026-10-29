"""Content-addressed bundle for offline cockpit A/B experiments."""

from __future__ import annotations

from . import cockpit_ab


def create(document: dict, ballots: list[dict] | None = None) -> dict:
    issues = cockpit_ab.validate_experiment(document)
    if issues:
        raise ValueError("invalid experiment: " + "; ".join(issues))
    packets = cockpit_ab.build_blind_packets(document)
    analysis = cockpit_ab.analyze(document, ballots) if ballots is not None else None
    manifest = {
        "schema": "nf-cockpit-ab-bundle-manifest/1",
        "experiment_id": document["experiment_id"],
        "experiment_digest": cockpit_ab.digest(document),
        "analysis_plan_digest": document["analysis_plan"]["plan_digest"],
        "packet_digest": packets["packet_digest"],
        "ballots_digest": cockpit_ab.digest(ballots) if ballots is not None else None,
        "analysis_digest": analysis["digest"] if analysis else None,
    }
    result = {
        "schema": "nf-cockpit-ab-bundle/1",
        "manifest": manifest,
        "experiment": document,
        "packets": packets,
        "ballots": ballots,
        "analysis": analysis,
    }
    result["bundle_digest"] = cockpit_ab.digest(result)
    return result


def verify(bundle: dict) -> list[str]:
    issues = []
    if bundle.get("schema") != "nf-cockpit-ab-bundle/1":
        issues.append("bundle schema")
        return issues
    document = bundle.get("experiment")
    packets = bundle.get("packets")
    ballots = bundle.get("ballots")
    analysis = bundle.get("analysis")
    manifest = bundle.get("manifest", {})
    if not isinstance(document, dict):
        return ["missing experiment"]
    issues += cockpit_ab.validate_experiment(document)
    expected_packets = cockpit_ab.build_blind_packets(document)
    if packets != expected_packets:
        issues.append("packet mismatch")
    if manifest.get("experiment_digest") != cockpit_ab.digest(document):
        issues.append("experiment digest mismatch")
    if manifest.get("analysis_plan_digest") != (document["analysis_plan"]["plan_digest"]):
        issues.append("analysis plan digest mismatch")
    if manifest.get("packet_digest") != expected_packets["packet_digest"]:
        issues.append("packet manifest digest mismatch")
    if ballots is None:
        if manifest.get("ballots_digest") is not None:
            issues.append("unexpected ballots digest")
        if analysis is not None:
            issues.append("analysis without ballots")
    else:
        if manifest.get("ballots_digest") != cockpit_ab.digest(ballots):
            issues.append("ballots digest mismatch")
        expected_analysis = cockpit_ab.analyze(document, ballots)
        if analysis != expected_analysis:
            issues.append("analysis mismatch")
        if manifest.get("analysis_digest") != expected_analysis["digest"]:
            issues.append("analysis digest mismatch")
    unsigned = {key: value for key, value in bundle.items() if key != "bundle_digest"}
    if bundle.get("bundle_digest") != cockpit_ab.digest(unsigned):
        issues.append("bundle digest mismatch")
    return issues
