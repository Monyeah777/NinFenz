#!/usr/bin/env python3
"""门禁机器可读报告（CLI）：`protocol/verification_report.json`。

用法：
  python scripts/verify_report.py            # 只打印摘要（不落盘）
  python scripts/verify_report.py --json     # 打印完整 JSON
  python scripts/verify_report.py --write    # 落盘 protocol/verification_report.json
  python scripts/verify_report.py --check    # 已落盘报告 == 实时重算（CI 用；败即 exit 1）
  python scripts/verify_report.py --fresh    # 只判新鲜度（不看 FAIL 数；供入口指令自证，见下）

`--check` 与 `--fresh` 的分工（2026-09-29）：`--check` 是**闸门**（新鲜度 + 零 FAIL/ERROR，
CI 用）；`--fresh` 只判新鲜度。入口指令 `nf release` 与实测记录里的 `report` 用 `--fresh`——
它们的成败若包含「报告自身的 FAIL 数」，就与报告里的 `instruction_evidence` 判据构成不动点
（release 要绿 ⇒ 报告要零 FAIL ⇒ 要求 release 记录为绿 ⇒ 循环），闸门那侧的牙齿由
`--check` 与 `verify.sh` 保留，不靠入口指令兜。
"""
import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "desktop", "src"))

from core import atomic_write, verify_report as vr  # noqa: E402


#: Rust `verify-report` **不自算**的 5 条（其余 26 条由 engine/rust 自算并逐字节对账）。
#: 必须与 `engine/rust/src/verify_report.rs` 的 native 分派同步；`test_rust_fastlane` 的
#: native 集合 + `check_native_sync.py` 是这条清单的反向守护。喂入面越小，加速越大。
NON_NATIVE = ("redos", "instruction_evidence", "perf_budget", "asset_contract",
              "role_coordinates")


def _fed_results() -> dict:
    """只现算 5 条非 native 判据 → `--results` 的 `{id: {issues,warns,stats,status?}}`。"""
    by_id = {spec[0]: spec for spec in vr.SPECS}
    res = {}
    for sid in NON_NATIVE:
        spec = by_id.get(sid)
        if spec is None:
            continue
        status, issues, warns, stats = vr._call(spec, ROOT)
        entry = {"issues": issues, "warns": warns, "stats": stats}
        if status == "error":
            entry["status"] = "error"
        res[sid] = entry
    return res


def _rust_report():
    """可选的 Rust 快线：Python 只算 5 条喂入，其余 26 条由 Rust 自算（→ bytes, code / None）。"""
    from core import rust_engine as re
    if re.disabled() or not re.requested():
        return None
    fed = _fed_results()
    with tempfile.TemporaryDirectory(prefix="nf-vr-") as tmp:
        p = Path(tmp) / "results.json"
        atomic_write.write_text(p, json.dumps(fed, ensure_ascii=False))
        return re.run_face(["verify-report", "--root", ROOT, "--results", str(p), "--json"],
                           root=ROOT)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="门禁机器可读报告（静态可核验面）")
    ap.add_argument("--write", action="store_true",
                    help="落盘 protocol/verification_report.json")
    ap.add_argument("--check", action="store_true",
                    help="已落盘报告 == 实时重算（不一致即 exit 1）")
    ap.add_argument("--fresh", action="store_true",
                    help="只判新鲜度：已落盘 == 实时重算（不看 FAIL 数）")
    ap.add_argument("--json", action="store_true", help="打印完整 JSON")
    args = ap.parse_args(argv)

    # opt-in 快线：只接管只读的默认/--json 面（--write/--check/--fresh 仍走 Python 真源）。
    if not (args.write or args.check or args.fresh):
        _rust = _rust_report()
        if _rust is not None and _rust[0] == 0:
            _out = _rust[1]
            try:
                _doc = json.loads(_out.decode("utf-8"))
            except (ValueError, UnicodeDecodeError):
                _doc = None
            if _doc is not None and not isinstance(_doc, dict):
                _doc = None
            # 喂入面漂移护栏：若某条判据既非 Rust native、又没被本脚本喂入，Rust 会报
            # 「未移植且未喂入结果」；此时回退 Python 权威报告，绝不吐一份带缺口的报告。
            if _doc is not None and any(
                    i.get("status") == "error"
                    and any("未移植且未喂入" in s for s in (i.get("sample") or []))
                    for i in _doc.get("items", [])):
                _doc = None
            if _doc is not None:
                if args.json:
                    sys.stdout.buffer.write(_out)
                    sys.stdout.buffer.flush()
                else:
                    print("== 门禁机器可读报告（只读摘要） ==")
                    print("  %s" % vr.summary_line(_doc))
                    for i in _doc["items"]:
                        if i["status"] != "pass":
                            print("  [%s] %-20s issues=%d warns=%d%s"
                                  % (i["status"].upper(), i["id"], i["issues"], i["warns"],
                                     ("；例：" + i["sample"][0][:90]) if i["sample"] else ""))
                return 0 if (_doc["summary"]["fail"] == 0
                              and _doc["summary"]["error"] == 0) else 1

    if args.check or args.fresh:
        issues, report = vr.check(ROOT)
        if args.json:
            print(vr.render(report), end="")
        print("== 门禁机器可读报告 check ==", file=sys.stderr)
        print("  %s" % vr.summary_line(report), file=sys.stderr)
        for i in issues:
            print("  ✗ %s" % i, file=sys.stderr)
        if issues:
            return 1
        print("  ✓ 已落盘报告与实时重算一致", file=sys.stderr)
        if args.fresh:
            return 0
        return 0 if report["summary"]["fail"] == 0 and report["summary"]["error"] == 0 else 1

    if args.write:
        issues, report = vr.write(ROOT)
        print("== 门禁机器可读报告 write ==")
        print("  ✓ 已写入 %s" % vr.REPORT_REL)
        print("  %s" % vr.summary_line(report))
        for i in issues:
            print("  ✗ %s" % i, file=sys.stderr)
        return 1 if issues else 0

    report = vr.build(ROOT)
    if args.json:
        print(vr.render(report), end="")
    else:
        print("== 门禁机器可读报告（只读摘要） ==")
        print("  %s" % vr.summary_line(report))
        for i in report["items"]:
            if i["status"] != "pass":
                print("  [%s] %-20s issues=%d warns=%d%s"
                      % (i["status"].upper(), i["id"], i["issues"], i["warns"],
                         ("；例：" + i["sample"][0][:90]) if i["sample"] else ""))
    return 0 if report["summary"]["fail"] == 0 and report["summary"]["error"] == 0 else 1


if __name__ == "__main__":
    # stdio 钉 UTF-8：Windows 控制台 GBK 下 ✓/✗ 即 UnicodeEncodeError（同 nf.py）
    for _stream in (sys.stdout, sys.stderr):
        if hasattr(_stream, "reconfigure"):
            _stream.reconfigure(encoding="utf-8")
    raise SystemExit(main())
