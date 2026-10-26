#!/usr/bin/env python3
"""结构计数器记录/校验：`protocol/perf_counters.json`（**只许减少**的棘轮）。

为什么不是毫秒：本机同一命令当日漂移 13.1 s ↔ 24.3 s（热降频/杀毒/并行 CI），毫秒判据会把
噪声当回归。结构计数（open/stat/regex/spawn/ast_parse/read_text）跨机器稳定，直接刻画
「做了多少重复劳动」。

用法：
    python scripts/perf_counters.py --record   # 跑固定工作集并写基线
    python scripts/perf_counters.py --check    # 与基线比对（任一计数上升 → exit 1）
    python scripts/perf_counters.py --list     # 只打印

纪律：工作集是**进程内 API**（与 verify_report 的判据同一批入口），不跨进程测量——跨进程的
计数需要注入到子进程，成本大于收益；跨进程的成本由 `perf_budget` 的墙钟面承担。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import perf_counters  # noqa: E402

# 本脚本会输出中文判定信息：Windows 控制台默认 GBK，必须钉 UTF-8（与其余入口同一纪律）。
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

BASELINE_REL = "protocol/perf_counters.json"
SCHEMA = "nf-perf-counters/1"


def _workloads() -> list[tuple[str, object]]:
    """固定工作集（顺序稳定）：与 verify_report 的判据同一批入口。"""
    from core import (asset_contract, code_metrics, conformance_report,
                      judgement_coverage, redos_scan, role_model, verify_report)

    def _build():
        verify_report.build(".")

    return [
        ("verify_report.build", _build),
        ("conformance_report.run", lambda: conformance_report.run(".")),
        ("asset_contract.scan", lambda: asset_contract.scan(".")),
        ("role_model.scan", lambda: role_model.scan(".")),
        ("code_metrics.measure", lambda: code_metrics.measure(".")),
        ("redos_scan.scan", lambda: redos_scan.scan(".")),
        ("judgement_coverage.scan", lambda: judgement_coverage.scan(".")),
    ]


def measure() -> dict:
    """跑一遍工作集 → {"schema","note","workloads":{name:{counters}}}。"""
    out: dict = {"schema": SCHEMA,
                 "note": "结构计数器基线：只许减少（重复劳动棘轮）。跨平台稳定，替代毫秒判据。",
                 "workloads": {}}
    for name, fn in _workloads():
        perf_counters.snapshot()                      # 预热：首次导入不计入
        with perf_counters.count() as c:
            fn()
        out["workloads"][name] = {k: int(c[k]) for k in perf_counters.KEYS}
    return out


def load(root: str = ".") -> dict:
    p = Path(root) / BASELINE_REL
    if not p.is_file():
        return {}
    try:
        doc = json.loads(p.read_text(encoding="utf-8"))
    except ValueError:
        # 可吞：基线坏件 → 视为"无基线"，check() 会以「缺基线」fail-closed 报出来。
        return {}
    return doc if isinstance(doc, dict) else {}


def check(root: str = ".", live: dict | None = None) -> list[str]:
    """与基线比对：**任一工作集任一计数上升** → issue（棘轮只许下降/持平）。"""
    base = load(root)
    if not base:
        return ["缺结构计数基线 %s（修复指引：python scripts/perf_counters.py --record）"
                % BASELINE_REL]
    live = measure() if live is None else live
    issues: list[str] = []
    for name, live_c in (live.get("workloads") or {}).items():
        want = (base.get("workloads") or {}).get(name) or {}
        for key, got in live_c.items():
            was = int(want.get(key, 0) or 0)
            if int(got) > was:
                issues.append("结构计数上升 %s · %s：%d → %d（修复指引：消除重复劳动，或评审后 "
                              "--record 重冻——棘轮只许减少）" % (name, key, was, int(got)))
    return issues


def main(argv: list[str]) -> int:
    root = "."
    if "--record" in argv:
        doc = measure()
        from core import atomic_write
        atomic_write.write_text(Path(root) / BASELINE_REL,
                               json.dumps(doc, ensure_ascii=False, indent=2,
                                          sort_keys=True) + "\n")
        print("已写入 %s（%d 个工作集）" % (BASELINE_REL, len(doc["workloads"])))
        return 0
    if "--check" in argv:
        issues = check(root)
        for i in issues:
            print("  ✗", i)
        if issues:
            return 1
        print("  ✓ 结构计数未上升（棘轮通过）")
        return 0
    doc = load(root) or measure()
    for name, c in (doc.get("workloads") or {}).items():
        print("%-24s %s" % (name, " ".join("%s=%d" % (k, c[k]) for k in perf_counters.KEYS)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
