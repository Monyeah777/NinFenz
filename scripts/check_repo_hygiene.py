#!/usr/bin/env python3
"""卫生项专项（MT-02）：gitignore 覆盖度 / 未提交虚拟环境 / 仓库体积 三项进 CI。

手册 MT-02 的伪解点名两类：① 体检只跑过一次，之后新增 venv 或大文件没人拦；
② 只在 pre-commit 里检查 gitignore，体积无人管。本脚本把三项做成**可重复执行的 CI 步骤**，
每项都有明确的失败阈值；阈值覆盖参数化，便于自证失败路径（--max-tracked-mb 0 之类）。

三项：
  1. gitignore 覆盖度 —— 委托 scripts/check_gitignore_coverage.py（按路径判定，五类各至少一条）；
  2. 未提交虚拟环境 —— 索引里不得出现 pyvenv.cfg / site-packages / .venv|venv|env 顶层目录；
     工作区存在但被忽略的本地环境只 WARN（那是正常开发态）；
  3. 仓库体积 —— tracked 内容总量、单文件最大、.git 目录大小三类阈值。

用法：
  python scripts/check_repo_hygiene.py
  python scripts/check_repo_hygiene.py --max-tracked-mb 0     # 自证体积拦截路径（应红）
  python scripts/check_repo_hygiene.py --repo DIR --json
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

DEFAULT_MAX_TRACKED_MB = 64.0
DEFAULT_MAX_BLOB_MB = 5.0
DEFAULT_MAX_GIT_MB = 256.0


def _utf8_stdout():
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:
            pass


def _git(root, *args, **kw):
    return subprocess.run(["git", "-C", str(root)] + list(args), capture_output=True, **kw)


def _tracked_sizes(root):
    raw = _git(root, "-c", "core.quotepath=off", "ls-files", "-z").stdout
    files = [x.decode("utf-8") for x in raw.split(b"\0") if x]
    if not files:
        return [], []
    inp = ("\n".join(":%s" % f for f in files) + "\n").encode("utf-8")
    out = _git(root, "cat-file", "--batch-check=%(objectsize)", input=inp).stdout.decode().split()
    sizes = []
    for f, s in zip(files, out):
        try:
            sizes.append((int(s), f))
        except ValueError:
            continue
    return files, sizes


def check(root=".", max_tracked_mb=DEFAULT_MAX_TRACKED_MB,
          max_blob_mb=DEFAULT_MAX_BLOB_MB, max_git_mb=DEFAULT_MAX_GIT_MB):
    root = Path(root).resolve()
    if _git(root, "rev-parse", "--git-dir").returncode != 0:
        return {"ok": False, "error": "不是 git 仓库：%s" % root, "checks": []}
    checks = []

    # ① gitignore 覆盖度
    script = root / "scripts" / "check_gitignore_coverage.py"
    if script.is_file():
        p = subprocess.run([sys.executable, str(script), "--repo", str(root), "--json"],
                           capture_output=True)
        try:
            data = json.loads(p.stdout.decode("utf-8", "replace") or "{}")
        except ValueError:
            data = {"ok": False, "error": "覆盖度脚本输出不可解析"}
        checks.append({
            "id": "gitignore-coverage",
            "ok": bool(data.get("ok")),
            "detail": ("五类各命中一条路径规则" if data.get("ok")
                       else "缺类别：%s" % ", ".join(data.get("missing") or [data.get("error", "?")])),
            "extra": {"missing": data.get("missing") or []},
        })
    else:
        checks.append({"id": "gitignore-coverage", "ok": False,
                       "detail": "scripts/check_gitignore_coverage.py 不在场", "extra": {}})

    # ② 未提交虚拟环境
    files, sizes = _tracked_sizes(root)
    tracked_venv = [f for f in files if f.endswith("pyvenv.cfg") or "/site-packages/" in f
                    or f.split("/")[0] in (".venv", "venv", "env")]
    local_venv = [d for d in (".venv", "venv", "env") if (root / d).is_dir()]
    if tracked_venv:
        checks.append({"id": "untracked-venv", "ok": False,
                       "detail": "虚拟环境文件进入索引：%s" % ", ".join(tracked_venv[:5]),
                       "extra": {"tracked": tracked_venv[:10]}})
    else:
        checks.append({"id": "untracked-venv", "ok": True,
                       "detail": ("索引无虚拟环境文件；本地环境目录 %s（已忽略，未入索引）"
                                  % ", ".join(local_venv) if local_venv
                                  else "索引无虚拟环境文件"),
                       "extra": {"local": local_venv}})

    # ③ 仓库体积
    total = sum(s for s, _ in sizes)
    largest = max(sizes) if sizes else (0, "")
    gitdir = root / ".git"
    git_bytes = sum(p.stat().st_size for p in gitdir.rglob("*") if p.is_file()) if gitdir.is_dir() else 0
    problems = []
    if total > max_tracked_mb * 1048576:
        problems.append("tracked %.2f MiB > %.0f MiB" % (total / 1048576.0, max_tracked_mb))
    if largest[0] > max_blob_mb * 1048576:
        problems.append("单文件 %s %.2f MiB > %.0f MiB"
                        % (largest[1], largest[0] / 1048576.0, max_blob_mb))
    if git_bytes > max_git_mb * 1048576:
        problems.append(".git %.2f MiB > %.0f MiB" % (git_bytes / 1048576.0, max_git_mb))
    checks.append({
        "id": "repo-volume",
        "ok": not problems,
        "detail": ("；".join(problems) if problems else
                   "tracked %.2f MiB（%d 件）/ 单文件最大 %s %.2f MiB / .git %.2f MiB"
                   % (total / 1048576.0, len(files), largest[1],
                      largest[0] / 1048576.0, git_bytes / 1048576.0)),
        "extra": {"tracked_mb": round(total / 1048576.0, 2),
                  "largest_mb": round(largest[0] / 1048576.0, 2),
                  "largest_path": largest[1],
                  "git_mb": round(git_bytes / 1048576.0, 2),
                  "limits": {"tracked_mb": max_tracked_mb, "blob_mb": max_blob_mb,
                             "git_mb": max_git_mb}},
    })
    return {"ok": all(c["ok"] for c in checks), "error": "", "checks": checks}


def main(argv=None):
    _utf8_stdout()
    ap = argparse.ArgumentParser(description="卫生项专项：gitignore 覆盖 / venv 入库 / 仓库体积")
    ap.add_argument("--repo", default=".")
    ap.add_argument("--max-tracked-mb", type=float, default=DEFAULT_MAX_TRACKED_MB)
    ap.add_argument("--max-blob-mb", type=float, default=DEFAULT_MAX_BLOB_MB)
    ap.add_argument("--max-git-mb", type=float, default=DEFAULT_MAX_GIT_MB)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    res = check(args.repo, args.max_tracked_mb, args.max_blob_mb, args.max_git_mb)
    if args.json:
        print(json.dumps(res, ensure_ascii=False, indent=2))
    elif res.get("error"):
        print("[ERROR] %s" % res["error"])
    else:
        print("卫生项专项（MT-02）：")
        for c in res["checks"]:
            print("  [%s] %-18s %s" % ("PASS" if c["ok"] else "FAIL", c["id"], c["detail"]))
        print("通过：三项卫生检查全绿" if res["ok"]
              else "修复指引：补齐 .gitignore 类别 / git rm --cached 掉环境文件 / 收敛仓库体积")
    return 0 if res["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
