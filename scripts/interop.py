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
    import argparse
    import time
    ap = argparse.ArgumentParser(description="NF Interop Layer 演示服务（P-I0/P-I1）")
    ap.add_argument("--lines", action="store_true", help="换行分隔 JSON 传输（默认 Content-Length 帧）")
    ap.add_argument("--http", type=int, default=0, metavar="PORT",
                    help="起 HTTP loopback 服务（0=临时端口）")
    args = ap.parse_args()
    d = build()
    if args.http:
        server, _thread = ip.serve_http(d, port=args.http)
        host, port = server.server_address[:2]
        print("interop HTTP loopback: http://%s:%d/（POST JSON-RPC）" % (host, port), flush=True)
        try:
            while True:
                time.sleep(3600)
        except KeyboardInterrupt:
            return 0
        finally:
            server.shutdown()
    if args.lines:
        return ip.serve_lines(d, sys.stdin, sys.stdout)
    return ip.serve_stdio(d, sys.stdin, sys.stdout)


if __name__ == "__main__":
    for _s in (sys.stdout, sys.stderr):
        if hasattr(_s, "reconfigure"):
            _s.reconfigure(encoding="utf-8")
    raise SystemExit(main())
