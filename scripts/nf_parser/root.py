"""根 parser（自 nf.py::_make_parser 的引导段抽出；文案逐字保留）。"""
from __future__ import annotations

import argparse


def build_root(*, version: str, epilog: str) -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="nf", description=(
            "NinFenz 全链管道（B2：retrieve→compose→gate→export）。"
            "分层引导（40 总纲 v2.8 波B S7）：作者五分钟上手 = run / demo / pipeline new；"
            "开发者与仓库治理工具族 = asset / module / register / market / spec / render / serve / "
            "design / audit / who-refers / impact / rename / import——README「五分钟快速开始」"
            "含逐条示例。"),
        epilog=epilog,
    )
    p.add_argument("--version", action="version",
                   version="nf %s" % version,
                   help="显示版本号后退出")
    p.add_argument("--engine", dest="engine", default=None,
                   choices=("python", "rust", "auto"),
                   help="判据引擎：python（真源，缺省）/ rust（engine/rust 只读快线，需 nf-rs 二进制"
                        "在场，否则回退 python）/ auto（二进制在场且已逐字节对账的面走 rust，其余 "
                        "python）。NF_ENGINE 环境变量可作缺省。")
    return p
