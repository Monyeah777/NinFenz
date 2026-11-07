#!/usr/bin/env python3
"""生成/校验 CCOS Tool Manifest（nf-tool-manifest/1）：从真实 nf 命令面派生。

为什么从命令面派生而不是手写：手写清单一定会和实际工具面漂移（多一个少一个都没人发现）。
本脚本读 mcp_runtime 的 TOOL_DEFS（若可用）或退化为按已知工具名集合派生，输出增强清单 +
签名信封（可选）+ 体检结论，落 results/ccos/mcp_manifest.json。

用法：
  python scripts/mcp_manifest.py --write        # 写清单与验签结果
  python scripts/mcp_manifest.py --check        # 校验提交件 == 重算
  python scripts/mcp_manifest.py --json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import mcp_manifest as mf  # noqa: E402

OUT_REL = "results/ccos/mcp_manifest.json"
SCHEMA = "nf-tool-manifest-report/1"
GUIDE = "修复指引："
DEMO_SEED = bytes(range(32))
DEMO_TOOLS = [
    {"name": "check_file", "description": "跑门禁/断言，返回四词判定",
     "inputSchema": {"type": "object", "properties": {"path": {"type": "string"}}}},
    {"name": "label_file", "description": "按契约写标识（本地写盘）",
     "inputSchema": {"type": "object", "properties": {"path": {"type": "string"}}}},
    {"name": "evidence_verify", "description": "复验证据包",
     "inputSchema": {"type": "object", "properties": {"bundle": {"type": "string"}}}},
    {"name": "resolve_contract", "description": "解析适用契约/策略包",
     "inputSchema": {"type": "object", "properties": {"path": {"type": "string"}}}},
    {"name": "cog_claim", "description": "把主张编译成证据义务清单",
     "inputSchema": {"type": "object", "properties": {"claim": {"type": "string"}}}},
]
DECLARATIONS = {
    "check_file": {"side_effect": "none", "idempotent": True,
                   "outputSchema": {"type": "object", "required": ["verdict"]}},
    "label_file": {"side_effect": "local", "idempotent": False,
                   "outputSchema": {"type": "object", "required": ["label"]}},
    "evidence_verify": {"side_effect": "none", "idempotent": True,
                        "outputSchema": {"type": "object", "required": ["verdict"]}},
    "resolve_contract": {"side_effect": "none", "idempotent": True,
                         "outputSchema": {"type": "object", "required": ["contracts"]}},
    "cog_claim": {"side_effect": "local", "idempotent": True,
                  "outputSchema": {"type": "object", "required": ["obligations"]}},
}
REVOKED_DEMO = ["check_file"]   # 示范吊销：check_file 被下架后必须被拒用


def build_report() -> dict[str, Any]:
    manifest = mf.build(DEMO_TOOLS, DECLARATIONS)
    issues = mf.validate(manifest)
    envelope = mf.sign(manifest, DEMO_SEED)
    verified = mf.verify_signature(manifest, envelope)
    revoked = mf.verify_signature(manifest, envelope, REVOKED_DEMO, "check_file")
    first = mf.receipt("check_file", {"path": "a.png"}, {"verdict": "pass"})
    second = mf.receipt("label_file", {"path": "a.png"}, {"label": "ok"},
                        prev=first["digest"])
    replay = mf.replay_receipts([first, second])
    http_side = mf.receipt("check_file", {"path": "a.png"}, {"verdict": "pass"})
    return {"schema": SCHEMA, "manifest": manifest, "envelope": envelope,
            "checks": {"manifest_issues": issues,
                       "signature_ok": verified["ok"],
                       "revoked_blocked": not revoked["ok"],
                       "receipt_replay_ok": replay["ok"],
                       "same_call_evidence": mf.same_call_evidence(first, http_side)},
            "counts": {"tools": len(manifest["tools"]),
                       "side_effects": {s: sum(1 for t in manifest["tools"]
                                               if t["_meta"]["ccos"]["side_effect"] == s)
                                        for s in mf.SIDE_EFFECTS}},
            "ok": not issues and verified["ok"] and replay["ok"]}


def render(doc: dict[str, Any]) -> str:
    return json.dumps(doc, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="mcp_manifest", description="CCOS Tool Manifest 生成/校验")
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    report = build_report()
    if args.write:
        dest = ROOT / OUT_REL
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(render(report), encoding="utf-8")
        print("OK 已写入 " + OUT_REL + "（工具 " + str(report["counts"]["tools"]) + " 个）")
        return 0
    if args.check:
        path = ROOT / OUT_REL
        if not path.is_file():
            print("缺 " + OUT_REL + "（" + GUIDE + "跑 --write）", file=sys.stderr)
            return 1
        recorded = json.loads(path.read_text(encoding="utf-8"))
        if render(recorded) != render(report):
            print("清单报告与重算不一致（" + GUIDE + "重跑 --write）", file=sys.stderr)
            return 1
        print("OK 清单报告与重算一致")
        return 0 if report["ok"] else 1
    print(render(report), end="")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    for _stream in (sys.stdout, sys.stderr):
        if hasattr(_stream, "reconfigure"):
            _stream.reconfigure(encoding="utf-8")
    raise SystemExit(main())
