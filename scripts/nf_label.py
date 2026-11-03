#!/usr/bin/env python3
"""NF 标识体检统一入口：新能力子命令 + 旧 `nf labeling` 子命令透传。

用法：
  python3 scripts/nf_label.py check <file> ...        # 旧命令原样透传（core.labeling.cli）
  python3 scripts/nf_label.py report <file> [--out DIR]
  python3 scripts/nf_label.py pipeline <file> [--platform douyin] [--history f.json] [--out DIR]
  python3 scripts/nf_label.py xcheck <file> [--report report.json] [--json]
  python3 scripts/nf_label.py recheck <before.json> <after.json> [--out f.json]
  python3 scripts/nf_label.py platform <file> <platform> [--json]
  python3 scripts/nf_label.py matrix | selfcheck | info | check ...

设计：薄壳；实现真源在 core.labeling 各模块。不修改冻结的 cli.py。
"""

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "desktop" / "src"))

NEW_SUBS = {"report", "batch", "pipeline", "xcheck", "recheck", "platform"}


def _load(name):
    import importlib
    return importlib.import_module("core.labeling." + name)


def _read_json(path):
    with open(path, encoding="utf-8") as fh:
        obj = json.load(fh)
    if not isinstance(obj, dict):
        raise ValueError("%s 顶层不是对象（修复指引：复核输入须是 JSON 对象）" % path)
    return obj


def _cmd_report(args):
    return _load("report").main(["report", *args])


def _cmd_batch(args):
    return _load("report").main(["batch", *args])


def _cmd_pipeline(args):
    ap = argparse.ArgumentParser(prog="nf_label.py pipeline")
    ap.add_argument("file")
    ap.add_argument("--platform", default=None)
    ap.add_argument("--history", default=None)
    ap.add_argument("--out", default=None)
    ap.add_argument("--title", default=None)
    ap.add_argument("--json", action="store_true")
    ns = ap.parse_args(args)
    pipe = _load("pipeline")
    try:
        result = pipe.evaluate(ns.file, platform=ns.platform,
                               history=ns.history, title=ns.title)
    except FileNotFoundError as exc:
        print("文件不存在：%s" % exc, file=sys.stderr)
        return 2
    if ns.out:
        pipe.save_outputs(result, ns.out)
        print("已写入 %s" % ns.out)
    if ns.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(result["renders"]["console"])
        if result.get("platform_eval"):
            print("平台：%s → %s" % (result["platform_eval"].get("platform"),
                                    result["platform_eval"].get("overall")))
    return result.get("exit_code", 0)


def _cmd_xcheck(args):
    ap = argparse.ArgumentParser(prog="nf_label.py xcheck")
    ap.add_argument("file")
    ap.add_argument("--report", default=None)
    ap.add_argument("--json", action="store_true")
    ns = ap.parse_args(args)
    xc = _load("xcheck")
    report = _read_json(ns.report) if ns.report else None
    try:
        result = xc.verify(ns.file, report)
    except FileNotFoundError as exc:
        print("文件不存在：%s" % exc, file=sys.stderr)
        return 2
    if ns.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print("交叉认证：%s（一致 %d 项，冲突 %d 项）"
              % (result.get("trust"), result.get("agree_count", 0),
                 len(result.get("conflict") or [])))
    return 1 if result.get("conflict") else 0


def _cmd_recheck(args):
    ap = argparse.ArgumentParser(prog="nf_label.py recheck")
    ap.add_argument("before")
    ap.add_argument("after")
    ap.add_argument("--out", default=None)
    ns = ap.parse_args(args)
    rec = _load("recheck")
    record = rec.build_record(_read_json(ns.before), _read_json(ns.after))
    print(rec.summary(record))
    if ns.out:
        # 原子写：复核记录是交付件（阅读方按 JSON 解析），半截件比缺件更难判。
        from core import atomic_write
        atomic_write.write_text(ns.out, json.dumps(record, ensure_ascii=False,
                                                   indent=2) + "\n")
        print("已写入 %s" % ns.out)
    return 0


def _cmd_platform(args):
    ap = argparse.ArgumentParser(prog="nf_label.py platform")
    ap.add_argument("file")
    ap.add_argument("platform")
    ap.add_argument("--json", action="store_true")
    ns = ap.parse_args(args)
    rep_mod = _load("report")
    rules = _load("platform_rules")
    extra = _load("extra_integration")
    try:
        report = extra.build_report(ns.file) or rep_mod.build_report(ns.file)
    except FileNotFoundError as exc:
        print("文件不存在：%s" % exc, file=sys.stderr)
        return 2
    result = rules.evaluate(report, ns.platform)
    if ns.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print("%s → %s" % (result.get("platform_name"), result.get("overall")))
        for check in result.get("checks") or []:
            print("  - %s %s  %s" % (check["id"], check["verdict"],
                                     check.get("reason", "")))
    return {"PASS": 0, "WARN": 0, "FAIL": 1}.get(result.get("overall"), 1)


def _cmd_matrix(args):
    return _load("report").main(["matrix", *args])


HANDLERS = {
    "report": _cmd_report, "batch": _cmd_batch, "pipeline": _cmd_pipeline,
    "xcheck": _cmd_xcheck, "recheck": _cmd_recheck, "platform": _cmd_platform,
    "matrix": _cmd_matrix,
}


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] in HANDLERS:
        return HANDLERS[argv[0]](argv[1:])
    # 旧命令透传：check/sign/verify/keygen/selfcheck/info/matrix
    from core.labeling.cli import main as legacy
    return legacy(argv)


if __name__ == "__main__":
    for _stream in (sys.stdout, sys.stderr):   # 钉 UTF-8 stdio
        if hasattr(_stream, "reconfigure"):
            _stream.reconfigure(encoding="utf-8")
    sys.exit(main())
