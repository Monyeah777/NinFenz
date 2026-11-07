#!/usr/bin/env python3
"""Create and verify RFC 3161 timestamp tokens and distributable NF records."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import json_doc, timestamp  # noqa: E402


def _emit(result: timestamp.CheckResult, as_json: bool) -> None:
    if as_json:
        print(json.dumps(result.as_dict(), ensure_ascii=False, indent=2, sort_keys=True))
        return
    for warning in result.warnings:
        print(f"  [INFO] {warning}")
    for issue in result.issues:
        print(f"  ✗ {issue}", file=sys.stderr)
    if result.ok:
        print(
            f"✓ RFC 3161 {result.verdict}"
            + (f" · {result.gen_time}" if result.gen_time else "")
        )


def _paths(args: argparse.Namespace) -> tuple[str, str, str]:
    subject = str(Path(args.subject))
    query = args.query_out or subject + ".tsq"
    token = args.token_out or subject + ".tsr"
    return subject, query, token


def _cmd_create(args: argparse.Namespace) -> int:
    subject, query, token = _paths(args)
    made = timestamp.make_query(subject, query)
    if not made.ok:
        _emit(made, args.json)
        return 1
    submitted = timestamp.submit(query, args.tsa_url, token, timeout=args.timeout)
    if not submitted.ok:
        _emit(submitted, args.json)
        return 1
    record_path = args.record_out or subject + ".time.json"
    try:
        record = timestamp.write_record(
            subject, query, token, args.ca_file,
            untrusted=args.untrusted, out=record_path,
        )
    except (OSError, ValueError) as exc:
        result = timestamp.CheckResult(False, "invalid", [str(exc)])
        _emit(result, args.json)
        return 1
    result = timestamp.verify_record(subject, record, args.ca_file, args.untrusted)
    _emit(result, args.json)
    return 0 if result.ok else 1


def _cmd_verify(args: argparse.Namespace) -> int:
    result = timestamp.verify(
        args.subject, args.query, args.token, args.ca_file, args.untrusted
    )
    if result.ok and args.record_out:
        try:
            timestamp.write_record(
                args.subject, args.query, args.token, args.ca_file,
                untrusted=args.untrusted, out=args.record_out,
            )
        except (OSError, ValueError) as exc:
            result = timestamp.CheckResult(False, "invalid", [str(exc)])
    _emit(result, args.json)
    return 0 if result.ok else 1


def _cmd_verify_record(args: argparse.Namespace) -> int:
    try:
        record: Any = json_doc.load(Path(args.record), dict, what=args.record)
    except (OSError, ValueError) as exc:
        result = timestamp.CheckResult(
            False, "invalid", [f"时间记录不可读：{exc}（修复指引：提供合法 JSON 记录）"]
        )
        _emit(result, args.json)
        return 1
    result = timestamp.verify_record(
        args.subject, record, args.ca_file, args.untrusted
    )
    _emit(result, args.json)
    return 0 if result.ok else 1


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="RFC 3161 可信时间戳")
    sub = parser.add_subparsers(dest="cmd", required=True)

    create = sub.add_parser("create", help="生成 query、提交 TSA、离线验证并写记录")
    create.add_argument("--subject", required=True)
    create.add_argument("--tsa-url", required=True)
    create.add_argument("--ca-file", required=True)
    create.add_argument("--untrusted", default="")
    create.add_argument("--query-out", default="")
    create.add_argument("--token-out", default="")
    create.add_argument("--record-out", default="")
    create.add_argument("--timeout", type=float, default=30.0)
    create.add_argument("--json", action="store_true")

    verify = sub.add_parser("verify", help="用 subject/query/token/CA 离线验证")
    verify.add_argument("--subject", required=True)
    verify.add_argument("--query", required=True)
    verify.add_argument("--token", required=True)
    verify.add_argument("--ca-file", required=True)
    verify.add_argument("--untrusted", default="")
    verify.add_argument("--record-out", default="")
    verify.add_argument("--json", action="store_true")

    record = sub.add_parser("verify-record", help="验证自包含 nf-time-token/1 记录")
    record.add_argument("--subject", required=True)
    record.add_argument("--record", required=True)
    record.add_argument("--ca-file", required=True)
    record.add_argument("--untrusted", default="")
    record.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if not Path(args.ca_file).is_file():
        result = timestamp.CheckResult(
            False, "invalid", ["缺信任锚 --ca-file（修复指引：提供 TSA 根/中间证书）"]
        )
        _emit(result, args.json)
        return 1
    if args.cmd == "create":
        return _cmd_create(args)
    if args.cmd == "verify":
        return _cmd_verify(args)
    return _cmd_verify_record(args)


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    raise SystemExit(main())
