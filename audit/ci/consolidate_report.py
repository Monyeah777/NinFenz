#!/usr/bin/env python3
"""从证据包汇总生成 audit/report.md（勿手改本产物）。

用法：
    python audit/ci/consolidate_report.py --evidence audit/evidence/c-dim
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--evidence", required=True)
    ap.add_argument("--out", default=str(ROOT / "audit" / "report.md"))
    args = ap.parse_args()
    ev = ROOT / args.evidence if not Path(args.evidence).is_absolute() else Path(args.evidence)
    meta = json.loads((ev / "meta.json").read_text(encoding="utf-8"))
    dims = meta["dimensions"]
    counts = meta.get("severity_counts", {})
    status = meta.get("status_counts", {})
    rules = meta.get("rules", {})
    lines = [
        "# NF 审计报告（汇总）",
        "",
        "> 本文件由 audit/ci/consolidate_report.py 生成，勿手改；明细见证据包与 remediation/calibration/trend。",
        "> 证据：" + args.evidence + "；commit：" + str(meta.get("commit")) + "；扫描根：" + str(meta.get("root", "")),
        "",
        "## 结论",
        "",
        "- 总分 **" + str(meta.get("score")) + "**（满分 100，口径 = 14 维加权）",
        "- 问题：P0=" + str(counts.get("P0", 0)) + " / P1=" + str(counts.get("P1", 0)) +
        " / P2=" + str(counts.get("P2", 0)) + " / P3=" + str(counts.get("P3", 0)),
        "- 规则：" + str(rules.get("total")) + " 条（script " + str(rules.get("script")) +
        " / tool " + str(rules.get("tool")) + " / manual " + str(rules.get("manual")) +
        "）；pass=" + str(status.get("pass", 0)) + " fail=" + str(status.get("fail", 0)) +
        " error=" + str(status.get("error", 0)) + " no_targets=" + str(status.get("no_targets", 0)) +
        " not-run=" + str(status.get("not-run", 0)),
        "",
        "## 维度分",
        "",
        "| 维度 | 名称 | 权重 | 得分 | 扣分 | 命中 |",
        "|---|---|---|---|---|---|",
    ]
    names = meta.get("dimension_names") or {}
    for dim in sorted(dims):
        d = dims[dim]
        lines.append("| " + dim + " | " + str(names.get(dim, d.get("name", ""))) + " | " + str(d.get("weight")) +
                     " | " + str(d.get("score")) + " | " + str(d.get("deduction")) + " | " + str(d.get("hits")) + " |")
    lines += [
        "",
        "## 门禁",
        "",
        "- 命令：bash audit/ci/gate.sh --evidence " + args.evidence,
        "- 阈值：audit/ci/thresholds.json（总分 / 单维 / P0 / error / no_targets）",
        "",
        "## 交付物索引",
        "",
        "| 文件 | 内容 |",
        "|---|---|",
        "| audit/rules.json | 规则库（机读，166 条） |",
        "| audit/evidence/<commit>/ | 证据包（issues/meta/report + 规则与 runner sha256） |",
        "| audit/remediation.md | 整改台账（问题 → 修复 → 验证 → 关闭） |",
        "| audit/calibration.md | 规则校准记录（证据 + owner + 到期） |",
        "| audit/trend.md | 趋势与前后对比 |",
        "| audit/ci/gate.sh | 一键门禁 |",
        "| audit/tools/ | 外部工具配置（未接入项标 not-run） |",
        "",
        "## 未跑项",
        "",
        "- tool/manual 共 " + str(status.get("not-run", 0)) + " 条未执行（离线无 detekt/ktlint/jscpd/jacoco/CodeQL 等）：不计分、不写成 pass，接 CI 后重跑。",
    ]
    Path(args.out).write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print("wrote", args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
