#!/usr/bin/env python3
"""nf-label-xcheck 启动器：独立交叉复核（不经过主 checker 的代码路径）。

用法：
  python3 scripts/nf_label_xcheck.py verify <file> [--report report.json] [--json]

退出码：0 一致/仅部分可比；1 冲突；2 用法或环境错误。
"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core.labeling import xcheck  # noqa: E402


def main(argv=None):
    ap = argparse.ArgumentParser(prog="nf-label-xcheck",
                                 description="标识独立交叉认证（结构级）")
    ap.add_argument("--version", action="version",
                    version="nf-label-xcheck %s" % xcheck.VERSION)
    sub = ap.add_subparsers(dest="cmd", required=True)
    v = sub.add_parser("verify", help="独立复核一个文件")
    v.add_argument("file")
    v.add_argument("--report", help="主报告 JSON（report.build_report 的落盘件）")
    v.add_argument("--json", action="store_true", help="只打 JSON 到 stdout")
    args = ap.parse_args(argv)
    report = None
    if args.report:
        try:
            report = json.loads(Path(args.report).read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            print("主报告读取失败：%s（修复指引：确认 --report 指向 report.json）"
                  % exc, file=sys.stderr)
            return 2
        if not isinstance(report, (dict, list)):
            print("主报告顶层不是对象/数组：%s（修复指引：确认 --report 指向 report.json）"
                  % args.report, file=sys.stderr)
            return 2
    try:
        xc = xcheck.verify(args.file, report)
    except (OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(xc, ensure_ascii=False, indent=2))
    else:
        print(xcheck.render_text(xc))
    return 0 if xc["trust"] != "conflict" else 1


if __name__ == "__main__":
    for _stream in (sys.stdout, sys.stderr):   # 钉 UTF-8 stdio
        if hasattr(_stream, "reconfigure"):
            _stream.reconfigure(encoding="utf-8")
    sys.exit(main())
