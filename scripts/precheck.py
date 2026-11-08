#!/usr/bin/env python3
"""提交前自查（快车道）：把「新增一个 core 模块 / 一个 CLI 面 / 一处解析」最容易踩的横向门禁
一次跑完（约 2–4 分钟），而不是等 45 分钟的全量快照来告诉你红哪 4 片。

为什么不新增判据：**这里不实现任何检查**，只按名单调用既有测试模块——判据仍只有一处，
本件只是「跑得快的那一组」。名单腐烂由 `test_precheck` 守（每个名字必须真实存在）。

**边界**：本件只覆盖 22/378 个测试模块（高频横向面子集），**不是发布前检查**，
也不能替代 `release_conclusion.py` 的全量结论——目标是缩短发现时间，不是减少判据。

用法：python scripts/precheck.py [--full] [--json]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from precheck_gates import GATES, SLOW_GATES  # 名单是数据件，注释见该模块

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "desktop" / "src"))
GUIDE = "修复指引："
SCHEMA = "nf-precheck/1"



def _run_one(module: str) -> dict[str, Any]:
    """跑一个测试模块（经受控进程原子：argv 列表 / 无 shell / 超时回收）。"""
    from core.atoms import proc as proc_atom

    got = proc_atom.run_capture([sys.executable, "-m", "unittest", module],
                                cwd=str(ROOT), timeout=900)
    out = (got.get("out") or "") + (got.get("err") or "")
    tail = [ln for ln in out.splitlines() if ln.strip()][-3:]
    return {"module": module, "rc": got.get("code"), "tail": tail}


def run(full: bool = False) -> dict[str, Any]:
    """跑全部快车道闸门 → {ok, rows}（任何一条红即 ok=False）。"""
    gates = list(GATES) + (list(SLOW_GATES) if full else [])
    rows = []
    for gate_id, module in gates:
        res = _run_one(module)
        rows.append({"id": gate_id, "module": module, "rc": res["rc"],
                     "ok": res["rc"] == 0, "tail": res["tail"]})
    return {"schema": SCHEMA, "full": bool(full), "gates": len(rows),
            "ok": all(r["ok"] for r in rows),
            "failed": [r["id"] for r in rows if not r["ok"]],
            "rows": rows,
            "note": "本件只跑既有判据列表，不新增检查；红的时候按失败模块的修复指引处理"}


def render(doc: dict[str, Any]) -> str:
    lines = ["== 提交前自查" + ("（含慢闸门）" if doc["full"] else "") + " =="]
    for row in doc["rows"]:
        lines.append(("  ✓ " if row["ok"] else "  ✗ ") + row["id"] + "（" + str(row["rc"]) + "）")
        if not row["ok"]:
            for ln in row["tail"]:
                lines.append("      " + ln.strip()[:120])
    lines.append("  闸门 " + str(doc["gates"]) + " · "
                 + ("全绿" if doc["ok"] else "红：" + "、".join(doc["failed"])))
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="precheck",
                                 description="提交前自查：一次跑完容易踩的横向门禁（不新增判据）")
    ap.add_argument("--full", action="store_true", help="加上慢闸门（CLI 面 + 纯度）")
    ap.add_argument("--json", action="store_true", help="输出结构化 JSON")
    args = ap.parse_args(argv)
    doc = run(full=args.full)
    if args.json:
        print(json.dumps(doc, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        sys.stdout.write(render(doc))
    return 0 if doc["ok"] else 1


if __name__ == "__main__":
    for _stream in (sys.stdout, sys.stderr):
        if hasattr(_stream, "reconfigure"):
            _stream.reconfigure(encoding="utf-8")
    raise SystemExit(main())
