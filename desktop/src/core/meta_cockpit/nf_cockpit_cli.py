"""NF 认知驾驶命令行：默认离线，不调用外部模型。"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import atomic_io, cockpit_service, file_model_adapter, json_asset

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
    p.add_argument("--injections", type=Path, help="turn->questions JSON")
    p.add_argument("--max-turns", type=int, default=8)
    p.add_argument("--max-seconds", type=float)
    p.add_argument("--max-context-units", type=int, default=36_000)
    p.add_argument("--json", action="store_true", help="emit JSON instead of markdown")
    p.add_argument("--responses", type=Path, help="JSONL model responses")
    p.add_argument("--context-dir", type=Path, help="write per-turn candidate payloads")


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
