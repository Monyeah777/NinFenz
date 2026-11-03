"""NF 认知驾驶命令行：默认离线，不调用外部模型。"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import atomic_io, cockpit_service, cognition_event, file_model_adapter, json_asset, session_journal

MAX_PROMPT_FILE_BYTES = 262_144


def add_arguments(p: argparse.ArgumentParser) -> None:
    """Add the production options to either the main or standalone parser."""
    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument("--prompt", help="prompt text")
    group.add_argument("--prompt-file", type=Path, help="UTF-8 prompt file")
    p.add_argument("--store", type=Path, help="calibration store JSON")
    p.add_argument("--journal", type=Path, help="session journal JSON")
    p.add_argument("--handoff-out", type=Path, help="write markdown handoff")
    p.add_argument("--manifest-out", type=Path, help="write production manifest JSON")
    p.add_argument("--event-out", type=Path, help="write nf-cognition-event/1 JSON")
    p.add_argument("--injections", type=Path, help="turn->questions JSON")
    p.add_argument("--max-turns", type=int, default=8)
    p.add_argument("--max-seconds", type=float)
    p.add_argument("--max-context-units", type=int, default=36_000)
    p.add_argument("--json", action="store_true", help="emit JSON instead of markdown")
    p.add_argument("--responses", type=Path, help="JSONL model responses")
    p.add_argument("--context-dir", type=Path, help="write per-turn candidate payloads")
    p.add_argument("--reasoning", action="store_true", help="enable the deterministic reasoning plane")
    p.add_argument("--reasoning-mode", choices=("auto", "steer", "search", "off"), default="auto")
    p.add_argument("--search-nodes", type=int, default=200, help="per-session search node budget")
    p.add_argument("--reasoning-beta", type=float, default=0.0, help="candidate prior strength (<=0.5)")
    p.add_argument("--reasoning-policy", type=Path, help="nf-reasoning-policy/1 JSON")


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="nf cockpit", description="Run the NF cognitive cockpit offline"
    )
    add_arguments(p)
    return p


def run(args: argparse.Namespace) -> int:
    injections = None
    try:
        if args.prompt_file is not None and args.prompt_file.stat().st_size > MAX_PROMPT_FILE_BYTES:
            raise ValueError("prompt file too large")
        prompt = (
            args.prompt_file.read_text(encoding="utf-8").strip()
            if args.prompt_file is not None
            else args.prompt.strip()
        )
        if args.injections is not None:
            if args.injections.stat().st_size > MAX_PROMPT_FILE_BYTES:
                raise ValueError("injections file too large")
            raw = json_asset.load(args.injections)
            if not isinstance(raw, dict):
                raise ValueError("injections must be an object")
            injections = {}
            for key, values in raw.items():
                turn = int(key)
                if (
                    turn < 1
                    or not isinstance(values, list)
                    or not all(isinstance(value, str) and value.strip() for value in values)
                ):
                    raise ValueError("invalid injections")
                injections[turn] = values
    except (OSError, UnicodeError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    if not prompt:
        print("empty prompt", file=sys.stderr)
        return 2
    reasoning = None
    if args.reasoning or args.reasoning_policy is not None:
        try:
            from . import reasoning as reasoning_mod

            policy_doc = (
                json_asset.load(args.reasoning_policy)
                if args.reasoning_policy is not None
                else None
            )
            mode = args.reasoning_mode
            beta = args.reasoning_beta
            if mode == "steer":
                # “steer” 是“不搜索、只做候选先验”的便捷别名；默认 β=0.5（<= beta_cap）。
                mode = "off"
                beta = beta or 0.5
            reasoning = reasoning_mod.ReasoningSession(
                mode=mode,
                search_nodes=args.search_nodes,
                beta=beta,
                policy=policy_doc,
            )
        except (OSError, ValueError, UnicodeError) as exc:
            print(str(exc), file=sys.stderr)
            return 2
    adapter = None
    try:
        if args.responses is not None:
            adapter = file_model_adapter.FileModelAdapter(
                args.responses, context_dir=args.context_dir
            )
        elif args.context_dir is not None:
            print("--context-dir requires --responses", file=sys.stderr)
            return 2
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    try:
        result = cockpit_service.produce(
            prompt,
            adapter=adapter,
            store_path=args.store,
            journal_path=args.journal,
            max_turns=args.max_turns,
            max_seconds=args.max_seconds,
            max_context_units=args.max_context_units,
            injections=injections,
            reasoning=reasoning,
        )
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    if args.handoff_out is not None:
        atomic_io.write_text(args.handoff_out, result["markdown"])
    if args.manifest_out is not None:
        atomic_io.write_text(
            args.manifest_out,
            json.dumps(result["manifest"], ensure_ascii=False, indent=2) + "\n",
        )
    if args.event_out is not None:
        journal_doc = None
        if args.journal is not None:
            journal_doc, status = session_journal.load(Path(args.journal))
            if status != "ok":
                journal_doc = None
        event = cognition_event.build(result["manifest"], journal_doc)
        atomic_io.write_text(args.event_out,
                             json.dumps(event, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
        cognition_event.write(event)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(result["markdown"])
    if result["run"]["status"] == "fail":
        return 1
    if not result["run"]["complete"] or result["handoff"]["gaps"]:
        return 2
    if adapter is not None:
        try:
            adapter.assert_consumed()
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 2
    return 0


def main(argv: list[str] | None = None) -> int:
    return run(parser().parse_args(argv))


if __name__ == "__main__":
    sys.exit(main())
