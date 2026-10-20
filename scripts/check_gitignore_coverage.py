#!/usr/bin/env python3
"""gitignore 覆盖度自检（FX-07）：按**路径**断言五类各自至少命中一条规则。

手册 FX-07 的伪解②点名：检查写成「关键词出现在 .gitignore 文本里」不算数——注释里提到也会误判。
本脚本因此不信文本，只信 git 自己的判定：对每类样例路径执行 git check-ignore，
由 git 给出「是否被忽略 + 命中的是哪条规则」。

五类（对应手册 FX-01..FX-05）：
  依赖 / 产物 / 运行时 / 环境密钥 / 编辑器

用法：
  python scripts/check_gitignore_coverage.py
  python scripts/check_gitignore_coverage.py --repo DIR --json
负例自证：临时仓库的 .gitignore 删掉某类规则后必须 exit 1；恢复后 exit 0。
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

#: 每类给多个样例路径，命中任意一条即认为该类被覆盖（宽口径，避免为单一写法误伤）
CATEGORIES = {
    "依赖": ["node_modules/pkg/index.js", ".venv/lib/python3.11/site-packages/mod.py",
             "venv/bin/activate", "pkg.egg-info/PKG-INFO"],
    "产物": ["dist/app.js", "build/out.o", "src/__pycache__/mod.pyc", "main.pyc"],
    "运行时": ["logs/app.log", "app.log", "state.db", "cache.sqlite3", "run.pid"],
    "环境密钥": [".env", ".env.local", "cert.pem", "server.key"],
    "编辑器": [".DS_Store", "Thumbs.db", "main.py.swp", ".vscode/settings.json",
              ".idea/workspace.xml"],
}


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


def check(root="."):
    root = Path(root)
    if _git(root, "rev-parse", "--git-dir").returncode != 0:
        return {"ok": False, "error": f"不是 git 仓库：{root}", "categories": []}
    if not (root / ".gitignore").is_file():
        return {"ok": False, "error": "缺 .gitignore：%s" % (root / ".gitignore"), "categories": []}
    rows, missing = [], []
    for name, samples in CATEGORIES.items():
        hit = None
        for sample in samples:
            p = _git(root, "check-ignore", "-v", "--no-index", "--", sample)
            if p.returncode == 0:
                rule = p.stdout.decode("utf-8", "replace").splitlines()[0]
                hit = {"sample": sample, "rule": rule}
                break
        if hit is None:
            missing.append(name)
            rows.append({"category": name, "ok": False, "samples": samples})
        else:
            rows.append({"category": name, "ok": True, **hit})
    return {"ok": not missing, "error": "", "missing": missing, "categories": rows}


def main(argv=None):
    _utf8_stdout()
    ap = argparse.ArgumentParser(description=".gitignore 五类覆盖度自检")
    ap.add_argument("--repo", default=".")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    res = check(args.repo)
    if args.json:
        print(json.dumps(res, ensure_ascii=False, indent=2))
    elif res.get("error"):
        print("[ERROR] {}".format(res["error"]))
    else:
        print(".gitignore 覆盖度（按 git check-ignore 判定，非文本匹配）：")
        for row in res["categories"]:
            if row["ok"]:
                print(f"  [PASS] {row['category']}  样例={row['sample']}  "
                      f"规则={row['rule']}")
            else:
                print(f"  [FAIL] {row['category']}  样例均未被忽略："
                      f"{chr(44).join(row['samples'])}")
        if res["missing"]:
            missing = "、".join(res["missing"])
            print(f"修复指引：在 .gitignore 补 {missing} 类路径规则"
                  "（注释里写关键词不算覆盖）")
        else:
            print("通过：五类各至少命中一条路径规则")
    return 0 if res["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
