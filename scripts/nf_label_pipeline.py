#!/usr/bin/env python3
"""nf-label 价值链统一入口：evaluate <file> [选项]（真源在 pipeline.py）。

用法：
  python3 scripts/nf_label_pipeline.py evaluate <file> [--platform 抖音]
      [--history history.json] [--out 目录] [--json]

退出码沿用报告 verdict：PASS/WARN=0，FAIL=1，用法或运行错误=2。
只做启动与参数解析，业务流程始终在 `desktop/src/core/labeling/pipeline.py`。
"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core.labeling import pipeline  # noqa: E402


def _parser():
    ap = argparse.ArgumentParser(
        prog="nf_label_pipeline", description="标识体检价值链：报告→规则→复测→交叉认证→渲染")
    sub = ap.add_subparsers(dest="cmd", required=True)
    ev = sub.add_parser("evaluate", help="对单个文件跑完整链路")
    ev.add_argument("file", help="待检文件（PNG/JPEG/PDF/DOCX/Markdown 等）")
    ev.add_argument("--platform", help="目标平台名称，如 抖音；省略则不做平台判定")
    ev.add_argument("--history", help="复测历史 JSON 路径（不存在则新建）")
    ev.add_argument("--out", help="产物目录；给定时落盘七件套")
    ev.add_argument("--json", action="store_true", help="输出完整 pipeline JSON")
    return ap


def main(argv=None):
    args = _parser().parse_args(argv)
    try:
        result = pipeline.evaluate(args.file, platform=args.platform,
                                   history=args.history)
        if args.out:
            pipeline.save_outputs(result, args.out)
    except (FileNotFoundError, ValueError, TypeError, ImportError, OSError) as exc:
        print("错误：%s" % exc, file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(pipeline.summary_text(result))
    verdict = (result.get("report") or {}).get("verdict")
    return 0 if verdict in ("PASS", "WARN") else 1


if __name__ == "__main__":
    for _stream in (sys.stdout, sys.stderr):   # 钉 UTF-8 stdio
        if hasattr(_stream, "reconfigure"):
            _stream.reconfigure(encoding="utf-8")
    raise SystemExit(main())
