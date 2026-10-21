#!/usr/bin/env python3
"""漏洞处置核对（SC-06）：依赖树里没有“未登记的”高危/严重漏洞。

输入：
  --audit   pip-audit -f json 的产物
  --disposition 处置表 results/audit/vuln-disposition.json（{accepted:[{id,reason,review_by}]}）
判定：severity 为 high/critical 且不在 accepted 里 → FAIL（缺处置）；review_by 早于今天 → FAIL（过期）。
"""
import argparse
import contextlib
import datetime
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "desktop" / "src"))
from core import json_doc  # noqa: E402

SEV = ("high", "critical")


def load_disposition(path):
    p = pathlib.Path(path)
    if not p.is_file():
        return {}
    doc = json_doc.load(p, dict, what="漏洞处置表")
    return {str(x.get("id") or "").upper(): x for x in (doc.get("accepted") or [])}


def findings(audit):
    out = []
    for dep in audit.get("dependencies") or []:
        for v in dep.get("vulns") or []:
            sev = str(v.get("severity") or "").lower()
            if sev in SEV:
                out.append((dep.get("name"), dep.get("version"), v.get("id"), sev))
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="漏洞处置核对")
    ap.add_argument("--audit", required=True)
    ap.add_argument("--disposition", default="results/audit/vuln-disposition.json")
    args = ap.parse_args(argv)
    for stream in (sys.stdout, sys.stderr):
        with contextlib.suppress(Exception):
            stream.reconfigure(encoding="utf-8")
    audit = json_doc.load(args.audit, dict, what="pip-audit 报告")
    disp = load_disposition(args.disposition)
    today = datetime.date.today()
    problems = []
    for name, ver, vid, sev in findings(audit):
        rec = disp.get(str(vid).upper())
        if not rec:
            problems.append("%s %s %s（%s）无处置记录" % (name, ver, vid, sev))
            continue
        by = str(rec.get("review_by") or "")
        try:
            if datetime.date.fromisoformat(by) < today:
                problems.append("%s 处置复核日期已过（review_by=%s）" % (vid, by))
        except ValueError:
            problems.append("%s 处置缺合法 review_by（应为 YYYY-MM-DD）" % vid)
    for p in problems:
        print("[FAIL] " + p)
    if not problems:
        print("通过：依赖树无未登记/过期处置的高危或严重漏洞（%d 条 accepted）" % len(disp))
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main())
