#!/usr/bin/env python3
"""覆盖率趋势软门禁（RL-06）：与上一次基线比较，先 warn 后 fail。

口径（手册 RL-06）：PR 上能看见覆盖率数字，并有软门禁使“覆盖率下降”在被看见的状态下发生。
本脚本只做判定，不收集覆盖率（覆盖率由 coverage.py 产出 JSON）。
  - 下降 <= 0.5 个百分点：pass
  - 下降 > 0.5 且 <= 2：warn（不挡，但日志显式标出）
  - 下降 > 2 或低于 80%：fail
用法：python scripts/coverage_trend.py --current cov.json [--baseline ...] [--update]
"""
import argparse
import contextlib
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "desktop" / "src"))
from core import atomic_write  # noqa: E402
from core import json_doc  # noqa: E402

NL = chr(10)
DEFAULT_BASELINE = "results/audit/coverage-baseline.json"
FLOOR = 80.0
WARN_DROP, FAIL_DROP = 0.5, 2.0


def percent(doc: dict) -> float:
    pct = (doc.get("totals") or {}).get("percent_covered")
    if pct is None:
        raise SystemExit("当前覆盖率报告缺 totals.percent_covered（修复指引：coverage json 重出）")
    return float(pct)


def judge(current: float, baseline: float) -> tuple:
    drop = baseline - current
    if current < FLOOR:
        return "fail", "低于地板 %.1f%%（当前 %.2f%%）" % (FLOOR, current)
    if drop > FAIL_DROP:
        return "fail", "较基线下降 %.2f 个百分点（>%.1f）" % (drop, FAIL_DROP)
    if drop > WARN_DROP:
        return "warn", "较基线下降 %.2f 个百分点（>%.1f，仅告警）" % (drop, WARN_DROP)
    return "pass", "基线 %.2f%% 到当前 %.2f%%（变化 %+.2f）" % (baseline, current, -drop)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="覆盖率趋势软门禁")
    ap.add_argument("--current", required=True)
    ap.add_argument("--baseline", default=DEFAULT_BASELINE)
    ap.add_argument("--update", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    for stream in (sys.stdout, sys.stderr):
        with contextlib.suppress(Exception):
            stream.reconfigure(encoding="utf-8")
    cur = percent(json_doc.load(args.current, dict, what="覆盖率 JSON"))
    bp = pathlib.Path(args.baseline)
    base = percent(json_doc.load(bp, dict, what="覆盖率基线")) if bp.is_file() else cur
    status, detail = judge(cur, base)
    if args.update:
        doc = {"totals": {"percent_covered": cur}}
        atomic_write.write_text(bp, json.dumps(doc, ensure_ascii=False, indent=2) + NL)
        print("基线已更新：%s（%.2f%%）" % (args.baseline, cur))
        return 0
    if args.json:
        print(json.dumps({"status": status, "current": cur, "baseline": base,
                          "detail": detail}, ensure_ascii=False))
    else:
        print("覆盖率趋势：%s · %s" % (status, detail))
    return 1 if status == "fail" else 0


if __name__ == "__main__":
    sys.exit(main())
