"""Command-line interface for offline cockpit A/B experiments."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import atomic_io, cockpit_ab, cockpit_ab_bundle, cockpit_ab_store, json_asset

MAX_FILE_BYTES = 16 * 1024 * 1024


def add_arguments(p: argparse.ArgumentParser) -> None:
    """Add A/B subcommands to either the main or standalone parser."""
    sub = p.add_subparsers(dest="command", required=True)

    pre = sub.add_parser(
        "preregister",
        help="Bind thresholds and power requirements before blind review",
        description="Validate paired trials and freeze the analysis plan.",
    )
    pre.add_argument("--experiment", type=Path, required=True)
    pre.add_argument("--out", type=Path, required=True)
    pre.add_argument("--min-pairs", type=int, default=8)
    pre.add_argument("--min-effect", type=float, default=0.10)
    pre.add_argument("--alpha", type=float, default=0.05)
    pre.add_argument("--min-judges", type=int, default=2)
    pre.add_argument("--min-agreement", type=float, default=0.60)
    pre.add_argument("--min-pairs-per-model", type=int, default=3)
    pre.add_argument("--target-power", type=float)
    pre.add_argument("--planned-pairs", type=int)
    pre.add_argument("--max-pairs", type=int, default=500)

    packets = sub.add_parser(
        "packets",
        help="Build arm-blind review packets",
        description="Shuffle paired outputs deterministically and remove arm metadata.",
    )
    packets.add_argument("--experiment", type=Path, required=True)
    packets.add_argument("--out", type=Path, required=True)

    analyze = sub.add_parser(
        "analyze",
        help="Analyze ballots under the preregistered plan",
        description="Report paired wins, intervals, power and stratified outcomes.",
    )
    analyze.add_argument("--experiment", type=Path, required=True)
    analyze.add_argument("--ballots", type=Path, required=True)
    analyze.add_argument("--out", type=Path)

    bundle = sub.add_parser(
        "save",
        help="Create and store a content-addressed bundle",
        description="Bind experiment, ballot and analysis bytes into one bundle.",
    )
    bundle.add_argument("--experiment", type=Path, required=True)
    bundle.add_argument("--ballots", type=Path)
    bundle.add_argument("--store", type=Path, required=True)

    verify = sub.add_parser(
        "verify",
        help="Verify a stored bundle digest",
        description="Reject corrupted or cross-version bundle contents.",
    )
    verify.add_argument("--bundle", type=Path, required=True)

    index = sub.add_parser(
        "index",
        help="List a local experiment store",
        description="Render a deterministic index over stored bundles.",
    )
    index.add_argument("--store", type=Path, required=True)
    audit = sub.add_parser(
        "audit",
        help="Audit store integrity",
        description="Report invalid bundle files instead of silently skipping them.",
    )
    audit.add_argument("--store", type=Path, required=True)


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="nf cockpit-ab", description="NF offline blind A/B tools")
    add_arguments(p)
    return p


def _load(path: Path):
    if path.stat().st_size > MAX_FILE_BYTES:
        raise ValueError("file too large")
    return json_asset.load(path)


def _write_json(path: Path, value) -> None:
    atomic_io.write_text(path, json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def run(args: argparse.Namespace) -> int:
    try:
        if args.command == "preregister":
            experiment = cockpit_ab.preregister(
                _load(args.experiment),
                min_pairs=args.min_pairs,
                min_effect=args.min_effect,
                alpha=args.alpha,
                min_judges=args.min_judges,
                min_agreement=args.min_agreement,
                min_pairs_per_model=args.min_pairs_per_model,
                target_power=args.target_power,
                max_pairs=args.max_pairs,
                planned_pairs=args.planned_pairs,
            )
            _write_json(args.out, experiment)
            print(args.out)
        elif args.command == "packets":
            packets = cockpit_ab.build_blind_packets(_load(args.experiment))
            _write_json(args.out, packets)
            print(args.out)
        elif args.command == "analyze":
            analysis = cockpit_ab.analyze(_load(args.experiment), _load(args.ballots))
            if args.out is not None:
                _write_json(args.out, analysis)
            print(json.dumps(analysis, ensure_ascii=False, indent=2))
        elif args.command == "save":
            ballots = _load(args.ballots) if args.ballots else None
            bundle = cockpit_ab_bundle.create(_load(args.experiment), ballots)
            target = cockpit_ab_store.save(args.store, bundle)
            print(target)
        elif args.command == "verify":
            bundle = cockpit_ab_store.load(args.bundle)
            print(bundle["bundle_digest"])
        elif args.command == "index":
            print(json.dumps(cockpit_ab_store.index(args.store), ensure_ascii=False, indent=2))
        elif args.command == "audit":
            print(json.dumps(cockpit_ab_store.audit(args.store), ensure_ascii=False, indent=2))
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    return 0


def main(argv: list[str] | None = None) -> int:
    return run(parser().parse_args(argv))


if __name__ == "__main__":
    sys.exit(main())
