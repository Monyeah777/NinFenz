#!/usr/bin/env python3
"""结论可复用性查询（自省层的用法出口）：这份结论还是「当前验证器」判的吗？

为什么（第 101 轮）：自省层已经能让「改了工具没重跑」变红，但那是**仓库状态**的判据；
手里拿着一份结论文件（或一段 JSON）的人还需要一个直接答案：**它还能不能引用**。

三种输入：
  1. `--conclusion FILE`：读一份 `nf-release-conclusion/1`（或 `nf-self-audit/1`）文件；
  2. 不给参数：读仓库里记录的 `results/ccos/self_audit.json`；
  3. `--digest HEX`：直接给一个摘要（从日志/报告里抄来的）。

输出三态：`current`（摘要一致）/ `stale`（验证器已变）/ `unknown`（没有可比对的摘要）。
只读、不改任何文件；`stale` 时退出码 1，便于脚本里 gate。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "desktop" / "src"))
SELF_AUDIT_REL = "results/ccos/self_audit.json"
SCHEMA = "nf-verifier-status/1"


def _current_digest() -> str:
    from core import verifier_version

    return str(verifier_version.digest(ROOT)["verifier_digest"])


def _digest_from_file(path: Path) -> str:
    doc: Any = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(doc, dict):
        return ""
    for key in ("verifier_digest", "digest"):
        if str(doc.get(key) or ""):
            return str(doc[key])
    return ""


def build(conclusion: str = "", digest: str = "") -> dict[str, Any]:
    current = _current_digest()
    recorded = str(digest or "").strip()
    source = "cli"
    if not recorded and conclusion:
        recorded = _digest_from_file(Path(conclusion))
        source = "file:" + Path(conclusion).name
    if not recorded:
        path = ROOT / SELF_AUDIT_REL
        if path.is_file():
            recorded = _digest_from_file(path)
            source = SELF_AUDIT_REL
    if not recorded:
        status = "unknown"
    elif recorded == current:
        status = "current"
    else:
        status = "stale"
    return {"schema": SCHEMA, "status": status, "source": source,
            "recorded": recorded, "current": current,
            "note": "stale 表示这份结论由旧版验证器产出，引用前必须重跑"}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="verifier_status",
                                 description="结论可复用性：这份结论还是当前验证器判的吗？")
    ap.add_argument("--conclusion", default="", help="结论/自省文件路径")
    ap.add_argument("--digest", default="", help="直接给摘要（hex）")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    try:
        doc = build(args.conclusion, args.digest)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(doc, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print("状态：" + doc["status"] + "（来源 " + doc["source"] + "）")
        if doc["status"] == "current":
            print("  摘要一致：这份结论由当前验证器判出，可以引用")
        elif doc["status"] == "stale":
            print("  验证器已变：记录 " + doc["recorded"][:16] + " ≠ 当前 "
                  + doc["current"][:16] + "——引用前必须重跑")
        else:
            print("  没有可比对的摘要（给 --conclusion 或 --digest）")
    return 0 if doc["status"] == "current" else (1 if doc["status"] == "stale" else 0)


if __name__ == "__main__":
    for _stream in (sys.stdout, sys.stderr):
        if hasattr(_stream, "reconfigure"):
            _stream.reconfigure(encoding="utf-8")
    raise SystemExit(main())
