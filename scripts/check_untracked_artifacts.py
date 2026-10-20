#!/usr/bin/env python3
"""索引层产物检查（FX-06）：产物路径重新进入索引即失败。

手册 FX-06 的自证要求：检查必须可重复执行、且有一条**可触发**的失败路径。
本脚本检查 git 索引（含已暂存新增），不看工作区内容——工作区里的 venv / 缓存是正常开发状态，
只有「进了索引」才是要被拦住的误跟踪。

用法：
  python scripts/check_untracked_artifacts.py
  python scripts/check_untracked_artifacts.py --repo DIR --json
负例自证：临时仓库里 git add -f 一个 .pyc，本脚本必须 exit 1。
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

#: 产物/依赖/缓存路径形态（按 posix 相对路径匹配，另按 basename 匹配无目录形态）
ARTIFACT_PATTERNS = (
    "*.pyc", "*.pyo", "*.pyd",
    "*/__pycache__/*", "__pycache__/*",
    "*.egg-info/*", "*/*.egg-info/*",
    "node_modules/*", "*/node_modules/*",
    ".venv/*", "*/.venv/*", "venv/*", "*/venv/*", "site-packages/*", "*/site-packages/*",
    "dist/*", "*/dist/*", "build/*", "*/build/*",
    ".coverage", ".coverage.*", "coverage.xml", "htmlcov/*", "*/htmlcov/*",
    ".pytest_cache/*", "*/.pytest_cache/*", ".mypy_cache/*", "*/.mypy_cache/*",
    "*.log", "logs/*", "*/logs/*",
    "*.db", "*.sqlite", "*.sqlite3", "*.sqlite-wal", "*.sqlite-shm",
    ".DS_Store", "Thumbs.db", "desktop.ini", "*.swp", "*.swo", "*.tmp",
    ".nf-logs/*", "*/.nf-logs/*", ".artifacts/*", "*/.artifacts/*",
)

#: 故意放行的 tracked 件（每行：glob  # 理由）。空表示「索引层应零产物」。
ALLOWLIST_REL = "scripts/artifact_allowlist.txt"


def _utf8_stdout():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass


def _git(root, *args):
    return subprocess.run(
        ["git", "-C", str(root), "-c", "core.quotepath=off"] + list(args),
        capture_output=True,
    )


def _load_allowlist(root):
    path = Path(root) / ALLOWLIST_REL
    entries = []
    if not path.is_file():
        return entries
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if line:
            entries.append(line)
    return entries


def _match(path, patterns):
    import fnmatch
    base = path.rsplit("/", 1)[-1]
    return any(fnmatch.fnmatch(path, p) or fnmatch.fnmatch(base, p) for p in patterns)


def check(root="."):
    root = Path(root)
    if _git(root, "rev-parse", "--git-dir").returncode != 0:
        return {"ok": False, "error": "不是 git 仓库：%s" % root, "violations": [], "checked": 0}
    raw = _git(root, "ls-files", "-z").stdout
    tracked = [x.decode("utf-8") for x in raw.split(b"\0") if x]
    allow = _load_allowlist(root)
    violations = []
    for path in tracked:
        if any(path == a or path.startswith(a.rstrip("/") + "/") for a in allow):
            continue
        if _match(path, ARTIFACT_PATTERNS):
            violations.append(path)
    return {"ok": not violations, "error": "", "checked": len(tracked),
            "allowed": allow, "violations": violations}


def main(argv=None):
    _utf8_stdout()
    ap = argparse.ArgumentParser(description="索引层产物检查（误跟踪即红）")
    ap.add_argument("--repo", default=".")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    res = check(args.repo)
    if args.json:
        print(json.dumps(res, ensure_ascii=False, indent=2))
    elif res["error"]:
        print("[ERROR] %s" % res["error"])
    else:
        print("索引层产物检查：已检查 tracked 文件 %d 件" % res["checked"])
        if res["violations"]:
            for v in res["violations"]:
                print("[FAIL] 产物路径进入索引：%s" % v)
            print("修复指引：git rm --cached <路径> 并在 .gitignore 覆盖该形态（FX-01..FX-05）")
        else:
            print("通过：索引层无产物路径")
    return 0 if res["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
