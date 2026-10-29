"""Thin CLI bridge for optional command families kept outside scripts/nf.py."""

from __future__ import annotations

from typing import Any


def subparsers(parser):
    """Create the main command group, then register bridged families."""
    subparsers = parser.add_subparsers(dest="cmd", required=False)
    from core.meta_cockpit import nf_ab_cli, nf_cockpit_cli

    cockpit = subparsers.add_parser(
        "cockpit",
        help="认知方法驾驶舱：按当前任务即时组合元认知原子（离线、无内部评分）",
        description="认知方法驾驶舱：按任务即时组合 1-3 个元认知原子，"
        "多轮时持续重选并保留可重放轨迹；不生成内部 score/grade。",
    )
    nf_cockpit_cli.add_arguments(cockpit)
    cockpit.set_defaults(_meta_cli="cockpit")

    ab = subparsers.add_parser(
        "cockpit-ab",
        help="驾驶舱离线盲评 A/B：预注册、盲包、分析、bundle、实验库",
        description="驾驶舱离线盲评 A/B：同 prompt/model/seed 严格配对，"
        "评审包隐藏 arm/model/seed；结论只来自预注册门与配套盲评。",
    )
    nf_ab_cli.add_arguments(ab)
    ab.set_defaults(_meta_cli="cockpit-ab")
    return subparsers


def run(args: Any) -> int:
    """Dispatch commands whose implementation lives outside the main CLI."""
    if args.cmd == "nfal":
        from core import nfal_cli

        return nfal_cli.main(list(getattr(args, "nfal_args", []) or []))
    if args.cmd == "cockpit":
        from core.meta_cockpit import nf_cockpit_cli

        return nf_cockpit_cli.run(args)
    if args.cmd == "cockpit-ab":
        from core.meta_cockpit import nf_ab_cli

        return nf_ab_cli.run(args)
    raise ValueError(f"unknown bridged command: {args.cmd}")
