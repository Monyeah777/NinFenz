#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""NF Interop Layer 演示服务（P-I0）：stdlib Content-Length 分帧上的 JSON-RPC 2.0 echo 方法面。

用法：echo '方法面' | python scripts/interop.py        # 从 stdin 读帧、向 stdout 写帧
注册方法：nf/echo、nf/version。这是 interop 分派核心的最小消费者（真接入层自 P-I1 起）。
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "desktop", "src"))

from core import interop as ip  # noqa: E402


def build() -> ip.Dispatcher:
    d = ip.Dispatcher()
    d.register("nf/echo", lambda params: params)
    d.register("nf/version", lambda _params: {"interop": "P-I0", "jsonrpc": "2.0"})
    return d


def main() -> int:
    return ip.serve_stdio(build(), sys.stdin, sys.stdout)


if __name__ == "__main__":
    for _s in (sys.stdout, sys.stderr):
        if hasattr(_s, "reconfigure"):
            _s.reconfigure(encoding="utf-8")
    raise SystemExit(main())
