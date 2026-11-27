"""core.evidence 私有实现分片 2/2（对外只经 core.evidence 门面导入）：bench、bench_markdown"""

from __future__ import annotations

from typing import Any


def bench_markdown(res: dict[str, Any]) -> str:
    """把基准结果渲染成可直接贴进报告的表（确定性输出）。"""
    lines = ["# 证据复验器攻击矩阵基准 v0", "",
             f"用例 {res['total']} 条 · 通过 {res['passed']} · 失败 {res['failed']} · "
             f"结论 {'PASS' if res['ok'] else 'FAIL'}", "",
             "| # | 用例 | 攻击 / 变化 | 期望 | 实际 | 结果 |",
             "|---|---|---|---|---|---|"]
    for i, r in enumerate(res["cases"], 1):
        mark = "✓" if r["ok"] else "✗"
        lines.append(f"| {i} | {r['id']} | {r['desc']} | {r['expected']} | "
                     f"{r['actual']} | {mark} |")
    lines.append("")
    lines.append("边界：本基准证明「这些已知攻击都判得出来」，**不**证明「所有攻击都判得"
                 "出来」；不可抵赖与可信时间戳仍需第三方见证，见证据包 boundary 声明。")
    return "\n".join(lines) + "\n"
