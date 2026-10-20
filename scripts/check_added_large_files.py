#!/usr/bin/env python3
"""新增/变更文件的体积拦截（CI-04）：只看**提交内容**，不看工作区。

为什么要有它：check-added-large-files 类工具的工作区模式只能拦「还没提交的工作区文件」，
一旦大文件已经进了历史，工作区检查永远看不见它；而唯一能进历史的入口是**索引与提交**。
本脚本因此只读 git 对象：索引里的 blob（--staged）、某个提交的 blob（--range）或 HEAD 提交。

口径（对齐手册 CI-04：默认阈值 1 MiB，超限即失败）：
- 默认阈值 1048576 字节（1 MiB），--max-bytes 可覆盖，--max-mb 便于人读；
- 检查对象 = 本次新增/修改/重命名的**文件内容**（diff --diff-filter=ACMR），不是工作区；
- 历史里已存在的大文件不在本脚本的拦截面内（只能向前拦截，已在 evidence 写明）。

用法：
  python scripts/check_added_large_files.py --staged
  python scripts/check_added_large_files.py --range origin/main...HEAD
  python scripts/check_added_large_files.py                 # 默认 HEAD 提交
"""
import argparse
import fnmatch
import subprocess
import sys
from pathlib import Path

DEFAULT_MAX_BYTES = 1024 * 1024
#: git 空树对象（用于 root commit / 首次推送时给出「全部新增」的对比基准）
EMPTY_TREE = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"


def _utf8_stdout():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass


def git(root, *args, check=True):
    return subprocess.run(
        ["git", "-C", str(root), "-c", "core.quotepath=off"] + list(args),
        capture_output=True,
        check=check,
    )


def _names(raw):
    return [x.decode("utf-8") for x in raw.split(b"\0") if x]


def staged_files(root):
    raw = git(root, "diff", "--cached", "--name-only", "--diff-filter=ACMR", "-z").stdout
    return _names(raw), ""


def range_files(root, rev_range):
    start, _, end = rev_range.partition("...")
    if not _:
        start, _, end = rev_range.partition("..")
    if not end:
        raise SystemExit(f"--range 需要 A..B 或 A...B 形式：{rev_range}")
    if set(start) == {"0"}:  # 首次推送：before 为全零
        start = EMPTY_TREE
    raw = git(root, "diff", "--name-only", "--diff-filter=ACMR", "-z", start, end).stdout
    return _names(raw), end


def head_commit_files(root):
    raw = git(root, "diff-tree", "--no-commit-id", "-r", "--root",
              "--name-only", "--diff-filter=ACMR", "-z", "HEAD").stdout
    return _names(raw), "HEAD"


def blob_size(root, rev, path):
    spec = (f"{rev}:{path}") if rev else (f":{path}")
    p = git(root, "cat-file", "-s", spec, check=False)
    if p.returncode != 0:
        return None
    try:
        return int(p.stdout.strip())
    except ValueError:
        return None


def _allowed(path, patterns):
    return any(fnmatch.fnmatch(path, pat) or fnmatch.fnmatch(Path(path).name, pat)
               for pat in patterns)


def scan(root, max_bytes, staged=False, rev_range=None, allow=()):
    root = Path(root)
    probe = git(root, "rev-parse", "--git-dir", check=False)
    if not (root / ".git").exists() and probe.returncode != 0:
        return {"ok": False, "mode": "none", "checked": 0, "violations": [],
                "error": f"不是 git 仓库：{root}"}
    if staged:
        paths, rev = staged_files(root)
        mode = "staged"
    elif rev_range:
        paths, rev = range_files(root, rev_range)
        mode = f"range:{rev_range}"
    else:
        paths, rev = head_commit_files(root)
        mode = "head-commit"
    violations, checked = [], 0
    for path in paths:
        if not path or _allowed(path, allow):
            continue
        size = blob_size(root, rev, path)
        if size is None:  # 删除/不可读：不是本次新增内容
            continue
        checked += 1
        if size > max_bytes:
            violations.append({"path": path, "bytes": size})
    return {"ok": not violations, "mode": mode, "checked": checked,
            "max_bytes": max_bytes, "violations": violations, "error": ""}


def _fmt(n):
    return f"{n / 1048576.0:.2f} MiB ({n} bytes)"


def main(argv=None):
    _utf8_stdout()
    ap = argparse.ArgumentParser(description="拦截超过阈值的提交内容（默认 1 MiB）")
    ap.add_argument("--repo", default=".")
    ap.add_argument("--max-bytes", type=int, default=DEFAULT_MAX_BYTES)
    ap.add_argument("--max-mb", type=float, default=None)
    ap.add_argument("--staged", action="store_true", help="检查索引（暂存区）里的内容")
    ap.add_argument("--range", dest="rev_range", default=None, help="检查 A..B / A...B 的新增内容")
    ap.add_argument("--allow", nargs="*", default=[],
                    help="放行路径 glob（谨慎使用，需在 evidence 说明）")
    args = ap.parse_args(argv)
    max_bytes = int(args.max_mb * 1048576) if args.max_mb is not None else args.max_bytes
    res = scan(args.repo, max_bytes, staged=args.staged, rev_range=args.rev_range, allow=args.allow)
    if res["error"]:
        print("[ERROR] {}".format(res["error"]))
        return 2
    print(f"大文件拦截：模式={res['mode']} 阈值={_fmt(max_bytes)} "
          f"检查件数={res['checked']}")
    if res["violations"]:
        for v in res["violations"]:
            print("[FAIL] {} 超过阈值：{}".format(v["path"], _fmt(v["bytes"])))
        print("修复指引：删除该文件或改用外部存储/发布制品；"
              "确属必要须在 evidence 登记并调整 --allow")
        return 1
    print(f"通过：本次新增/变更内容均未超过 {_fmt(max_bytes)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
