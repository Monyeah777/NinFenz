#!/usr/bin/env python3
# ruff: noqa: E501, UP031
# nf-io: inputs=verify.sh,scripts/nf.py,docs/verification-cards.md,desktop/src/core/gate_engine.py outputs=protocol/check_registry.json
"""判据登记册导出器（方案 01 S1：从四处清单导出，不手抄）。

四处清单（2026-10-22 实测口径；与方案文档的措辞差异见下）：
  ① `verify.sh` 的 `checkN()` 函数集合——权威执行体；
  ② `gate_engine.REGISTRY ∪ gate_engine.PENDING`——引擎清单（历史缺口：从缺 check41/42 起）；
  ③ `scripts/nf.py` 的 `CHECK_GUIDE`——`nf explain` 修复指引清单；
  ④ `docs/verification-cards.md` 的卡片索引——人读卡册（由 verify.sh 生成）。

为什么 ② 不是方案文档写的 `verify_report.SPECS`：本仓 `verify_report.SPECS` 是**判据级**
抽查面（31 条，id 是字符串如 `purity`），不是 check 号清单，无法与 check 号做集合差；
`verify_checks.py` 是并行调度器、没有独立清单。故按仓库实况改用 `gate_engine` 与
`CHECK_GUIDE`——这正是 `INNOVATIONS-X1-gov.md` 实测的「4 份清单」：verify.sh 42 /
gate_engine 40 / CHECK_GUIDE 42 / 卡册 42。

用法：
  python scripts/gen_check_registry.py --dry-run    # 只读：打印 42 条与四处差集
  python scripts/gen_check_registry.py --json       # 只读：打印导出结果
  python scripts/gen_check_registry.py --write      # 落盘 protocol/check_registry.json
  python scripts/gen_check_registry.py --check      # 登记册 == 实时导出（diff 即 exit 1）
  python scripts/gen_check_registry.py --read-surface   # R3 读面合规（memo 观测面）
  python scripts/gen_check_registry.py --experiment-check  # #17 改基线实验单判据

纪律：只读（唯 --write 落盘）；同输入同输出；导出结果不包含手工维护内容。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import atomic_write  # noqa: E402
from core import check_registry as cr  # noqa: E402

REGISTRY = ROOT / cr.REGISTRY_REL


def _render(rows) -> str:
    doc = {"schema": cr.SCHEMA,
           "generator": "scripts/gen_check_registry.py",
           "checks": rows}
    return json.dumps(doc, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _diff_lines(lists) -> list:
    """两个集合间「谁多谁少」的人读行（R1 的导出侧诊断）。"""
    out = []
    for name in cr.SOURCES:
        got = lists[name]
        target = lists["verify_sh"]
        if got == target:
            continue
        bits = []
        missing = sorted(target - got)
        extra = sorted(got - target)
        if missing:
            bits.append("少 {}".format(",".join(map(str, missing))))
        if extra:
            bits.append("多 {}".format(",".join(map(str, extra))))
        out.append("  %-12s : %d 条｜%s  ← %s"
                   % (name, len(got), "；".join(bits), cr.SOURCE_HUMAN[name]))
    return out


def _main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="判据登记册导出器（只读）")
    ap.add_argument("--dry-run", action="store_true", help="打印 42 条与四处差集（不落盘）")
    ap.add_argument("--json", action="store_true", help="打印导出 JSON")
    ap.add_argument("--write", action="store_true", help="写 protocol/check_registry.json")
    ap.add_argument("--check", action="store_true", help="已落盘 == 实时导出（不一致即 exit 1）")
    ap.add_argument("--read-surface", action="store_true", help="R3 读面合规（memo 观测面）")
    ap.add_argument("--experiment-check", action="store_true", help="#17 改基线实验单判据")
    args = ap.parse_args(argv)

    if args.read_surface:
        warns, stats = cr.read_surface(str(ROOT))
        print("== 判据账本 R3 读面合规（memo 观测面）==")
        print("  已观测 %(observed)d 条 / 未观测 %(skipped)d 条" % stats)
        for w in warns:
            print(f"  [WARN] {w}")
        return 1 if warns else 0
    if args.experiment_check:
        issues, stats = cr.experiment_guard(str(ROOT))
        print("== 判据账本 #17 改基线实验单（%s）==" % (
            "无基线改动" if not stats.get("changed") else "改动 %d 件" % stats["changed"]))
        for i in issues:
            print(f"  [FAIL] {i}")
        return 1 if issues else 0

    rows = cr.derive(str(ROOT))
    if args.json:
        print(_render(rows))
        return 0
    if args.write:
        atomic_write.write_text(str(REGISTRY), _render(rows))
        print("== 判据登记册导出（写入）==")
        print("  ✓ %s（%d 条）" % (cr.REGISTRY_REL, len(rows)))
        return 0
    if args.check:
        try:
            committed = REGISTRY.read_text(encoding="utf-8")
        except OSError as exc:
            print(f"  ✗ 读不到 {cr.REGISTRY_REL}：{exc}", file=sys.stderr)
            return 1
        want = _render(rows)
        if committed != want:
            print("  ✗ 登记册 != 实时导出（修复指引：python scripts/gen_check_registry.py "
                  "--write）", file=sys.stderr)
            for line in want.splitlines():
                if line not in committed.splitlines():
                    print(f"    + {line}", file=sys.stderr)
                    break
            return 1
        print("  ✓ 登记册 == 实时导出")
        return 0

    # 默认 / --dry-run：只读报告
    lists = cr.four_lists(str(ROOT))
    print("== 判据登记册导出（只读）==")
    for name in cr.SOURCES:
        print("  %-12s : %d 条  ← %s" % (name, len(lists[name]), cr.SOURCE_HUMAN[name]))
    print("  导出结果     : %d 条（id %d..%d）" % (
        len(rows), rows[0]["id"], rows[-1]["id"]))
    diffs = _diff_lines(lists)
    if diffs:
        print("四处差集（以 verify.sh 为基准）：")
        for line in diffs:
            print(line)
        known = sorted(lists["verify_sh"] - lists["gate_engine"])
        print("  [i] 已知缺口（引擎清单）：%s —— R1 必须在补齐后才转绿"
              % (",".join(map(str, known)) or "无"))
    else:
        print("四处差集：无（四份清单 id 集合一致）")
    print("  [i] 差集实测 = {}".format(json.dumps(
        {k: sorted(v) for k, v in lists.items()}, ensure_ascii=False)))
    return 0


if __name__ == "__main__":
    for _s in (sys.stdout, sys.stderr):
        if hasattr(_s, "reconfigure"):
            _s.reconfigure(encoding="utf-8")
    raise SystemExit(_main())
