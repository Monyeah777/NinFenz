"""NF 认知驾驶单入口：驱动、恢复、模型 adapter 与生产交接。"""

from __future__ import annotations

import hashlib
from pathlib import Path

from . import cockpit_handoff, context_pack, json_asset, runtime_executor, session_journal
from . import constrained_loop as loop
from . import schema_compat as jsonschema

MAX_PROMPT_CHARS = 100_000
MANIFEST_SCHEMA = json_asset.load(Path(__file__).parent / "cockpit_manifest.schema.json")
MANIFEST_VALIDATOR = jsonschema.Draft202012Validator(MANIFEST_SCHEMA)


def produce(
    prompt: str,
    adapter=None,
    policy=None,
    store_path: str | Path | None = None,
    journal_path: str | Path | None = None,
    max_turns: int = 8,
    providers: list | None = None,
    max_seconds: float | None = None,
    max_context_units: int | None = 36_000,
    injections: dict[int, list[str]] | None = None,
) -> dict:
    if not isinstance(prompt, str) or not prompt.strip():
        raise ValueError("prompt must be non-empty")
    if len(prompt) > MAX_PROMPT_CHARS:
        raise ValueError("prompt too large")
    if adapter is not None and policy is not None:
        raise ValueError("adapter and policy are mutually exclusive")
    effective_policy = (
        loop.contextual_policy(adapter, providers=providers)
        if adapter is not None
        else policy or loop.first_policy
    )
    run = loop.run(
        prompt,
        effective_policy,
        store_path=store_path,
        journal_path=journal_path,
        max_turns=max_turns,
        max_seconds=max_seconds,
        max_context_units=max_context_units,
        injections=injections,
    )
    handoff = cockpit_handoff.build_handoff(run["state"], termination=run["termination"])
    journal_digest = None
    if journal_path is not None:
        document, status = session_journal.load(Path(journal_path))
        if document is not None and status == "ok":
            journal_digest = document["digest"]
    manifest = {
        "schema": "nf-cockpit-manifest/1",
        "prompt_digest": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
        "machine_digest": runtime_executor.machine_digest(),
        "runtime_digest": session_journal.runtime_digest(),
        "journal_digest": journal_digest,
        "handoff_digest": context_pack.digest(handoff),
        "context_digest": handoff["provenance"]["context_digest"],
        "status": run["status"],
        "termination": run["termination"],
        "complete": run["complete"],
        "turns": run["turns"],
        "context_units_spent": run.get("context_units_spent", 0),
        "abstention_status": handoff["abstention"]["status"],
        "human_action_required": handoff["abstention"]["human_action_required"],
    }
    issues = [error.message for error in MANIFEST_VALIDATOR.iter_errors(manifest)]
    if issues:
        raise ValueError("invalid manifest: {}".format("; ".join(issues)))
    return {
        "schema": "nf-cockpit-production-run/1",
        "prompt": prompt,
        "run": run,
        "handoff": handoff,
        "markdown": cockpit_handoff.render_markdown(handoff),
        "manifest": manifest,
    }
