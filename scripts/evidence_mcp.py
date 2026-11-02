#!/usr/bin/env python3
"""NF Evidence MCP server（stdio，换行分隔 JSON-RPC；本地只读证据面）。"""
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "desktop" / "src"))
from core import evidence_mcp as em  # noqa: E402


def _write(obj) -> None:
    if not obj:
        return
    text = json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
    sys.stdout.write(text.replace("\n", "\\n").replace("\r", "\\r") + "\n")
    sys.stdout.flush()


def main() -> int:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except ValueError:
            _write({"jsonrpc": "2.0", "id": None,
                    "error": {"code": -32700, "message": "JSON 解析失败"}})
            continue
        _write(em.handle(req, ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
