#!/usr/bin/env python3
"""workflow 权限最小化审计（BR-05）。

判据（手册 BR-05）：顶层默认只读；写权限按 job 单独授予，且能指出哪个 job 需要写、为什么。
本脚本只做**可证**的部分：
  1) 每个 workflow 必须有顶层 permissions（缺 → FAIL）；
  2) 顶层 permissions 不得出现 write（出现 → FAIL：写权限应下沉到 job）；
  3) 列出 job 级 write 授予，供 docs/meta/WORKFLOW-PERMISSIONS.md 对照「为什么需要」。

用法：python scripts/check_workflow_permissions.py [--json]
"""
import argparse
import contextlib
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _top_permissions(lines):
    """→ (是否存在, [授予行], jobs 之前的行号边界)。只认 jobs: 之前的那一段。"""
    present, grants, in_perm = False, [], False
    for raw in lines:
        s = raw.strip()
        if not s or s.startswith("#"):
            continue
        if raw.startswith("jobs:"):
            break
        if raw.startswith("permissions:"):
            present = True
            inline = s.split(":", 1)[1].strip()
            if inline:
                grants.append(inline)
            in_perm = True
            continue
        if in_perm:
            if raw.startswith((" ", "\t")) and ":" in s:
                grants.append(s)
            else:
                in_perm = False
    return present, grants


def _job_writes(lines):
    """→ [(job, 授予行)]：jobs: 之后、缩进 4 空格的 permissions 块里的 write。"""
    out, job, in_jobs, in_perm, base = [], "", False, False, 0
    for raw in lines:
        s = raw.strip()
        if not s or s.startswith("#"):
            continue
        if raw.startswith("jobs:"):
            in_jobs = True
            continue
        m = re.match(r"^  ([A-Za-z0-9_-]+):\s*$", raw)
        if in_jobs and m:
            job = m.group(1)
        if in_jobs and raw.startswith("    permissions:"):
            in_perm, base = True, 4
            inline = s.split(":", 1)[1].strip()
            if "write" in inline:
                out.append((job, inline))
            continue
        if in_perm:
            indent = len(raw) - len(raw.lstrip())
            if indent <= base and s and not s.startswith("-"):
                in_perm = False
            elif "write" in s:
                out.append((job, s))
    return out


def scan(root=ROOT):
    rows, problems = [], []
    for p in sorted(pathlib.Path(root).joinpath(".github/workflows").glob("*.yml")):
        rel = p.relative_to(root).as_posix()
        lines = p.read_text(encoding="utf-8").splitlines()
        present, grants = _top_permissions(lines)
        writes = [g for g in grants if "write" in g or g.strip() == "write-all"]
        if not present:
            problems.append(rel + "：缺顶层 permissions（修复指引：加 permissions: 且只给 read）")
        if writes:
            problems.append(rel + "：顶层 permissions 出现写权限（修复指引：下沉到具体 job）")
        rows.append({"file": rel, "top": grants, "job_writes": _job_writes(lines)})
    return rows, problems


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="workflow 权限最小化审计（BR-05）")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    for stream in (sys.stdout, sys.stderr):
        with contextlib.suppress(Exception):
            stream.reconfigure(encoding="utf-8")
    rows, problems = scan()
    if args.json:
        print(json.dumps({"workflows": rows, "problems": problems}, ensure_ascii=False, indent=2))
    else:
        print(f"workflow 数：{len(rows)}")
        for r in rows:
            mark = "OK " if not any(p.startswith(r["file"]) for p in problems) else "BAD"
            print(f"  [{mark}] {r['file']}")
        for p in problems:
            print("[FAIL] " + p)
        if not problems:
            print("通过：顶层只读；job 级写权限见 docs/meta/WORKFLOW-PERMISSIONS.md")
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main())
