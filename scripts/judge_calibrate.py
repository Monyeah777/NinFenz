#!/usr/bin/env python3
"""judge 校准 CLI：读 labeled JSONL，输出整体/分类别 kappa 与偏差探针。

默认离线：只评分已记录的 human/judge 标签，不调用任何 API。
判定语义：`--gate` 时，not_reliable 非空即 exit 1；输入不合法 exit 2。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "desktop" / "src"))


def _read_jsonl(path: str) -> list[dict[str, Any]]:
    p = Path(path)
    rows = []
    for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError("第 " + str(i) + " 行不是 JSON：" + str(exc)) from exc
        if not isinstance(row, dict):
            raise ValueError("第 " + str(i) + " 行不是对象")
        rows.append(row)
    return rows


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="judge_calibrate",
                                 description="LLM-as-judge 与 human 的一致性校准")
    ap.add_argument("--labeled", required=True, help="labeled JSONL")
    ap.add_argument("--pairwise", default="", help="position probe JSONL（可选）")
    ap.add_argument("--kappa-threshold", type=float, default=0.6)
    ap.add_argument("--min-category-n", type=int, default=8)
    ap.add_argument("--positive-label", default="pass")
    ap.add_argument("--gate", action="store_true", help="not_reliable 非空则 exit 1")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    try:
        rows = _read_jsonl(args.labeled)
        if args.pairwise:
            pair_rows = _read_jsonl(args.pairwise)
            by_id = {str(r.get("id", "")): r for r in rows}
            for pair in pair_rows:
                target = by_id.get(str(pair.get("id", "")))
                if target is not None:
                    target["pick_original"] = pair.get("pick_original", "")
                    target["pick_swapped"] = pair.get("pick_swapped", "")
        from core.judge_calibration import calibrate
        out = calibrate(rows, args.kappa_threshold, args.min_category_n,
                        args.positive_label)
    except (OSError, ValueError, TypeError) as exc:
        print("judge_calibrate: " + str(exc), file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(out, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print("== judge calibration ==")
        print("  n=" + str(out["n"]) + " · accuracy=" + str(out["accuracy"])
              + " · kappa=" + str(out["kappa"]))
        for cat in out["categories"]:
            mark = "reliable" if cat["reliable"] else "NOT reliable"
            print("  " + cat["category"] + " · n=" + str(cat["n"])
                  + " · kappa=" + str(cat["kappa"]) + " · " + mark)
        print("  position: " + json.dumps(out["position"], ensure_ascii=False))
        print("  verbosity: " + json.dumps(out["verbosity"], ensure_ascii=False))
    if args.gate and out["not_reliable"]:
        return 1
    return 0


if __name__ == "__main__":
    for _stream in (sys.stdout, sys.stderr):
        if hasattr(_stream, "reconfigure"):
            _stream.reconfigure(encoding="utf-8")
    raise SystemExit(main())
