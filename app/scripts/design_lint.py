#!/usr/bin/env python3
"""NF 视觉令牌 lint：硬编码、栅格、色相、动作预算。

用法：
  python3 app/scripts/design_lint.py                  # 系统层（design + 演示屏）
  python3 app/scripts/design_lint.py --scope app      # 全 App，迁移债可见
  python3 app/scripts/design_lint.py --scope system --strict  # 系统层违规即退出 1

扫描范围：app/android/app/src/main/java/**/*.kt
豁免：ui/design/**（令牌实现本身）
"""
from __future__ import annotations

import argparse
import colorsys
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "app" / "android" / "app" / "src" / "main" / "java"
DESIGN = SRC / "dev" / "ninfenz" / "mobile" / "ui" / "design"

FONT_RE = re.compile(r"fontSize\s*=\s*([0-9.]+)\.sp")
COLOR_RE = re.compile(r"Color\(0x([0-9A-Fa-f]{8})\)")
DP_RE = re.compile(r"(?<![\w.])([0-9]+)\.dp")
FILLED_RE = re.compile(r"(?<!Outlined)(?<!Text)(?<!Icon)(?<!Nf)\bButton\(")

BRAND_HUE = 168.0
HUE_WINDOW = 10.0


def kotlin_files(scope: str) -> list[Path]:
    all_files = sorted(SRC.rglob("*.kt"))
    if scope == "app":
        return all_files
    demo = SRC / "dev" / "ninfenz" / "mobile" / "ui" / "screens" / "DesignSystemScreen.kt"
    return [p for p in all_files if DESIGN in p.parents or p == demo]


def is_design(path: Path) -> bool:
    return DESIGN in path.parents or path == DESIGN


def hue_of(argb: int) -> tuple[float, float, float]:
    r = ((argb >> 16) & 0xFF) / 255.0
    g = ((argb >> 8) & 0xFF) / 255.0
    b = (argb & 0xFF) / 255.0
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    return h * 360.0, s, l


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--scope", choices=["system", "app"], default="system")
    args = parser.parse_args()

    violations: list[str] = []
    warnings: list[str] = []
    button_counts: dict[str, int] = {}

    files = kotlin_files(args.scope)
    for path in files:
        rel = path.relative_to(ROOT)
        text = path.read_text(encoding="utf-8", errors="replace")
        if not is_design(path):
            for m in FONT_RE.finditer(text):
                violations.append(f"{rel}: 硬编码字号 {m.group(1)}sp（应改用 NfType 角色）")
            for m in COLOR_RE.finditer(text):
                argb = int(m.group(1), 16)
                if (argb >> 24) == 0:
                    continue
                h, s, _ = hue_of(argb)
                if s < 0.15 and not (BRAND_HUE - HUE_WINDOW <= h <= BRAND_HUE + HUE_WINDOW):
                    violations.append(
                        f"{rel}: 中性色 #{m.group(1)} 色相 {h:.0f}° 越出 {BRAND_HUE:.0f}±{HUE_WINDOW:.0f}°"
                    )
            for line in text.splitlines():
                if any(k in line for k in ("tonalElevation", "strokeWidth", "RoundedCornerShape", "Modifier.size(")):
                    continue
                for m in DP_RE.finditer(line):
                    v = int(m.group(1))
                    if v > 4 and v % 4 != 0:
                        warnings.append(f"{rel}: 间距 {v}dp 不在 4dp 栅格上")

        name = path.name
        if "screens/" in str(rel):
            button_counts[name] = len(FILLED_RE.findall(text))

    crowded = {k: v for k, v in button_counts.items() if v > 1}
    for name, count in sorted(crowded.items()):
        warnings.append(f"{name}: {count} 个填充按钮（一屏只允许 1 个主操作）")

    print(f"== NF 视觉令牌 lint（scope={args.scope}）==")
    print(f"扫描 Kotlin 文件：{len(files)}")
    print(f"违规：{len(violations)}")
    for item in violations:
        print("  FAIL", item)
    print(f"警告：{len(warnings)}")
    for item in warnings:
        print("  WARN", item)

    if args.strict and violations:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
