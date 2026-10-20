#!/usr/bin/env python3
"""仓库体检基线（MT-01）：17 条规则分 6 组，可本地跑，结果落 JSON 基线。

手册 MT-01 要的不是「分还不错」的一句印象，而是**可复核的清单**：
总分、每组得分、每条规则的状态与细节，以及缺失项清单。基线文件默认写到
results/audit/repo_doctor-baseline-<日期>.json，后续改动可拿它当对照基准。

17 条规则（6 组）：
  Hygiene(4)        H1 gitignore 五类覆盖 / H2 索引层零产物 / H3 无虚拟环境入库 / H4 仓库体积
  Security(3)       S1 SECURITY.md 可报告 / S2 明文密钥零命中 / S3 action 全 SHA 固定
  Basics(3)         B1 README 定位与快速开始 / B2 LICENSE / B3 .gitattributes 行尾基线
  Community(3)      C1 CONTRIBUTING / C2 CODE_OF_CONDUCT / C3 Issue+PR 模板
  Build(2)          D1 verify.sh 门禁入口 / D2 CI 有 PR 触发
  Reproducibility(2) R1 requirements 精确钉版 / R2 全部 job 有 timeout-minutes

用法：
  python scripts/repo_doctor.py                       # 默认写 results/audit/repo_doctor-baseline-<today>.json
  python scripts/repo_doctor.py --no-write --json     # 只打印
  python scripts/repo_doctor.py --out /tmp/x.json
"""
import argparse
import datetime
import json
import re
import subprocess
import sys
from pathlib import Path

TOOL_VERSION = "1.0.0"
GROUPS = ("Hygiene", "Security", "Basics", "Community", "Build", "Reproducibility")
PIN_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*(\[[A-Za-z0-9._,-]+\])?==[0-9][^#\s]*\s*\\?$")
USES_RE = re.compile(r"(?m)^\s*-?\s*uses:\s*(\S+)\s*(?:#.*)?$")
PINNED_RE = re.compile(r"^[^@/\s]+/[^@\s]+@[0-9a-f]{40}$")
SECRET_RE = (r"ghp_[0-9A-Za-z]{36}|github_pat_[0-9A-Za-z_]{22,}|gho_[0-9A-Za-z]{36}|"
             r"sk-[0-9A-Za-z]{20,}|AIza[0-9A-Za-z_-]{35}|AKIA[0-9A-Z]{16}|"
             r"xox[baprs]-[0-9A-Za-z-]{10,}")


def _utf8_stdout():
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:
            pass


def _git(root, *args, **kw):
    return subprocess.run(["git", "-C", str(root)] + list(args), capture_output=True, **kw)


def _run_script(root, name, *args):
    path = Path(root) / "scripts" / name
    if not path.is_file():
        return {"ok": False, "error": "脚本不在场：%s" % path}
    p = subprocess.run([sys.executable, str(path), "--repo", str(root), "--json"],
                       capture_output=True)
    try:
        data = json.loads(p.stdout.decode("utf-8", "replace") or "{}")
    except ValueError:
        return {"ok": False, "error": "输出不是 JSON：%s" % name}
    return data


def _tracked_sizes(root):
    raw = _git(root, "-c", "core.quotepath=off", "ls-files", "-z").stdout
    files = [x.decode("utf-8") for x in raw.split(b"\0") if x]
    if not files:
        return files, []
    inp = ("\n".join(":%s" % f for f in files) + "\n").encode("utf-8")
    out = _git(root, "cat-file", "--batch-check=%(objectsize)", input=inp).stdout.decode().split()
    sizes = []
    for f, s in zip(files, out):
        try:
            sizes.append((int(s), f))
        except ValueError:
            continue
    return files, sizes


def _yaml(path):
    import yaml
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return {}


def _triggers(doc):
    trig = doc.get(True, doc.get("on"))
    return trig


def _has_pr_trigger(trig):
    if isinstance(trig, dict):
        return "pull_request" in trig
    if isinstance(trig, list):
        return "pull_request" in trig
    return False


def _find(root, *rels):
    for rel in rels:
        if (Path(root) / rel).is_file():
            return Path(root) / rel
    return None


def rule_h1(root, ctx):
    data = _run_script(root, "check_gitignore_coverage.py")
    if data.get("ok"):
        rules = ["%s -> %s" % (row["category"], row.get("rule", "")) for row in data.get("categories", [])]
        return "pass", "五类各命中一条路径规则", {"rules": rules}
    return "fail", "缺类别：%s" % ", ".join(data.get("missing") or [data.get("error", "?")]), data


def rule_h2(root, ctx):
    data = _run_script(root, "check_untracked_artifacts.py")
    if data.get("ok"):
        return "pass", "索引层无产物路径（检查 %d 件）" % data.get("checked", 0), {}
    return "fail", "产物进入索引：%s" % ", ".join(data.get("violations", [])[:5]), data


def rule_h3(root, ctx):
    raw = _git(root, "-c", "core.quotepath=off", "ls-files", "-z").stdout
    tracked = [x.decode("utf-8") for x in raw.split(b"\0") if x]
    bad = [f for f in tracked if f.endswith("pyvenv.cfg") or "/site-packages/" in f
           or f.split("/")[0] in (".venv", "venv", "env")]
    local = [d for d in (".venv", "venv", "env") if (Path(root) / d).is_dir()]
    if bad:
        return "fail", "虚拟环境文件进入索引：%s" % ", ".join(bad[:5]), {"tracked": bad[:10]}
    if local:
        return "warn", "本地虚拟环境在场但未入索引（%s）——属正常开发态" % ", ".join(local), {"local": local}
    return "pass", "无虚拟环境入库，本地也没有残留环境目录", {}


def rule_h4(root, ctx):
    files, sizes = _tracked_sizes(root)
    total = sum(s for s, _ in sizes)
    largest = max(sizes) if sizes else (0, "")
    gitdir = Path(root) / ".git"
    git_bytes = sum(p.stat().st_size for p in gitdir.rglob("*") if p.is_file()) if gitdir.is_dir() else 0
    limits = {"tracked_mb": 64.0, "blob_mb": 5.0, "git_mb": 256.0}
    detail = {"tracked_mb": round(total / 1048576.0, 2),
              "largest": {"path": largest[1], "mb": round(largest[0] / 1048576.0, 2)},
              "git_mb": round(git_bytes / 1048576.0, 2),
              "limits": limits, "tracked_files": len(files)}
    bad = []
    if total > limits["tracked_mb"] * 1048576:
        bad.append("tracked 体积 %.2f MiB > %.0f" % (detail["tracked_mb"], limits["tracked_mb"]))
    if largest[0] > limits["blob_mb"] * 1048576:
        bad.append("最大文件 %s %.2f MiB > %.0f" % (largest[1], detail["largest"]["mb"], limits["blob_mb"]))
    if git_bytes > limits["git_mb"] * 1048576:
        bad.append(".git %.2f MiB > %.0f" % (detail["git_mb"], limits["git_mb"]))
    if bad:
        return "fail", "；".join(bad), detail
    return "pass", "tracked %.2f MiB / 最大 %s %.2f MiB / .git %.2f MiB" % (
        detail["tracked_mb"], largest[1], detail["largest"]["mb"], detail["git_mb"]), detail


def rule_s1(root, ctx):
    p = _find(root, ".github/SECURITY.md", "SECURITY.md")
    if not p:
        return "fail", "缺 SECURITY.md（或不在 .github/ 下）", {}
    text = p.read_text(encoding="utf-8", errors="replace")
    has_channel = any(k in text.lower() for k in
                      ("security/advisories", "security policy", "report a vulnerability",
                       "@", "advisory"))
    return ("pass", "SECURITY.md 在场且有可报告通道（%s）" % p.relative_to(root).as_posix(), {}) \
        if has_channel else ("fail", "SECURITY.md 在场但没有可报告通道", {})


def rule_s2(root, ctx):
    p = _git(root, "grep", "-I", "-n", "-E", SECRET_RE)
    if p.returncode == 1:
        return "pass", "明文密钥扫描零命中", {}
    if p.returncode != 0:
        return "warn", "git grep 执行失败（%d）" % p.returncode, {}
    hits = []
    for line in p.stdout.decode("utf-8", "replace").splitlines()[:10]:
        hits.append(re.sub(SECRET_RE, "<masked>", line))
    return "fail", "疑似明文密钥命中 %d 行" % len(hits), {"hits": hits}


def rule_s3(root, ctx):
    unpinned, total = [], 0
    for f in sorted((Path(root) / ".github" / "workflows").glob("*.yml")):
        text = f.read_text(encoding="utf-8", errors="replace")
        for m in USES_RE.finditer(text):
            ref = m.group(1)
            if ref.startswith("./") or ref.startswith("docker://"):
                continue
            total += 1
            if not PINNED_RE.match(ref):
                unpinned.append("%s -> %s" % (f.name, ref))
    if unpinned:
        return "fail", "未固定到提交 SHA 的 action：%s" % "; ".join(unpinned[:5]), {"unpinned": unpinned}
    return "pass", "全部 %d 处 action 引用固定到 40 位提交 SHA" % total, {"pinned_refs": total}


def rule_b1(root, ctx):
    p = Path(root) / "README.md"
    if not p.is_file():
        return "fail", "缺 README.md", {}
    text = p.read_text(encoding="utf-8", errors="replace")
    has_quick = any(k in text for k in ("快速开始", "Quick Start", "quickstart", "5 分钟", "五分钟"))
    has_en = (Path(root) / "README.en.md").is_file()
    if has_quick and has_en:
        return "pass", "README 有快速开始且中英双入口在场", {}
    if has_quick:
        return "warn", "README 有快速开始，但缺 README.en.md", {}
    return "fail", "README 无快速开始入口", {}


def rule_b2(root, ctx):
    lic = [p for p in Path(root).glob("LICENSE*") if p.is_file()]
    return ("pass", "LICENSE 在场（%s）" % lic[0].name, {}) if lic else ("fail", "缺 LICENSE", {})


def rule_b3(root, ctx):
    p = Path(root) / ".gitattributes"
    if not p.is_file():
        return "fail", "缺 .gitattributes（行尾基线无声明）", {}
    text = p.read_text(encoding="utf-8", errors="replace")
    if "eol=lf" in text:
        return "pass", ".gitattributes 声明 eol=lf", {}
    return "warn", ".gitattributes 在场但无 eol=lf 规则", {}


def rule_c1(root, ctx):
    p = _find(root, ".github/CONTRIBUTING.md", "CONTRIBUTING.md")
    return ("pass", "CONTRIBUTING 在场（%s）" % p.relative_to(root).as_posix(), {}) \
        if p else ("fail", "缺 CONTRIBUTING", {})


def rule_c2(root, ctx):
    p = _find(root, ".github/CODE_OF_CONDUCT.md", "CODE_OF_CONDUCT.md")
    return ("pass", "CODE_OF_CONDUCT 在场（%s）" % p.relative_to(root).as_posix(), {}) \
        if p else ("fail", "缺 CODE_OF_CONDUCT", {})


def rule_c3(root, ctx):
    tdir = Path(root) / ".github" / "ISSUE_TEMPLATE"
    n = len(list(tdir.glob("*"))) if tdir.is_dir() else 0
    pr = _find(root, ".github/PULL_REQUEST_TEMPLATE.md", "PULL_REQUEST_TEMPLATE.md")
    if n and pr:
        return "pass", "Issue 模板 %d 件 + PR 模板在场" % n, {}
    missing = []
    if not n:
        missing.append("Issue 模板")
    if not pr:
        missing.append("PR 模板")
    return "fail", "缺 %s" % "、".join(missing), {}


def rule_d1(root, ctx):
    p = Path(root) / "verify.sh"
    if not p.is_file():
        return "fail", "缺 verify.sh 门禁入口", {}
    if "check12" in p.read_text(encoding="utf-8", errors="replace"):
        return "pass", "verify.sh 门禁入口在场（含 check12 分段）", {}
    return "warn", "verify.sh 在场但未见 check12 分段", {}


def rule_d2(root, ctx):
    for f in sorted((Path(root) / ".github" / "workflows").glob("*.yml")):
        if _has_pr_trigger(_triggers(_yaml(f))):
            return "pass", "CI 有 pull_request 触发（%s）" % f.name, {}
    return "fail", "没有任何 workflow 在 PR 上触发", {}


def rule_r1(root, ctx):
    reqs = sorted((Path(root) / ".github").glob("requirements-*.txt"))
    if not reqs:
        return "fail", "缺 .github/requirements-*.txt", {}
    bad = []
    for p in reqs:
        for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("-"):
                continue
            if not PIN_RE.match(line):
                bad.append("%s: %s" % (p.name, line))
    ci = Path(root) / ".github" / "requirements-ci.txt"
    hashed = ci.is_file() and "--hash=sha256:" in ci.read_text(encoding="utf-8", errors="replace")
    if bad:
        return "fail", "未精确钉版：%s" % "; ".join(bad[:5]), {"bad": bad}
    if hashed:
        return "pass", "%d 份 requirements 全部精确钉版，主清单含 sha256 哈希" % len(reqs), {}
    return "warn", "requirements 精确钉版，但主清单无 --hash", {"files": [p.name for p in reqs]}


def rule_r2(root, ctx):
    missing, total = [], 0
    for f in sorted((Path(root) / ".github" / "workflows").glob("*.yml")):
        doc = _yaml(f)
        for jid, job in (doc.get("jobs") or {}).items():
            total += 1
            if not isinstance(job, dict) or job.get("timeout-minutes") in (None, ""):
                missing.append("%s:%s" % (f.name, jid))
    if missing:
        return "fail", ("%d 个 job 缺 timeout-minutes（共 %d 个 job）：%s"
                        % (len(missing), total, ", ".join(missing[:6]))), {"missing": missing}
    return "pass", "全部 %d 个 job 都有 timeout-minutes" % total, {"jobs": total}


RULES = (
    ("H1", "Hygiene", "gitignore 五类覆盖", rule_h1),
    ("H2", "Hygiene", "索引层零产物", rule_h2),
    ("H3", "Hygiene", "无虚拟环境入库", rule_h3),
    ("H4", "Hygiene", "仓库体积红线", rule_h4),
    ("S1", "Security", "SECURITY.md 可报告通道", rule_s1),
    ("S2", "Security", "明文密钥零命中", rule_s2),
    ("S3", "Security", "action 全 SHA 固定", rule_s3),
    ("B1", "Basics", "README 定位与快速开始", rule_b1),
    ("B2", "Basics", "LICENSE", rule_b2),
    ("B3", "Basics", "行尾基线 .gitattributes", rule_b3),
    ("C1", "Community", "CONTRIBUTING", rule_c1),
    ("C2", "Community", "CODE_OF_CONDUCT", rule_c2),
    ("C3", "Community", "Issue + PR 模板", rule_c3),
    ("D1", "Build", "verify.sh 门禁入口", rule_d1),
    ("D2", "Build", "CI 有 PR 触发", rule_d2),
    ("R1", "Reproducibility", "requirements 精确钉版", rule_r1),
    ("R2", "Reproducibility", "全 job timeout 保护", rule_r2),
)


def run(root="."):
    root = Path(root).resolve()
    if _git(root, "rev-parse", "--git-dir").returncode != 0:
        raise SystemExit("不是 git 仓库：%s" % root)
    ctx = {}
    rows, groups = [], {g: {"score": 0.0, "max": 0, "rules": []} for g in GROUPS}
    for rid, group, title, fn in RULES:
        try:
            status, detail, extra = fn(root, ctx)
        except Exception as exc:  # 规则自身异常不应静默变绿
            status, detail, extra = "fail", "规则执行异常：%s" % exc, {}
        score = {"pass": 1.0, "warn": 0.5, "fail": 0.0}.get(status, 0.0)
        groups[group]["max"] += 1
        groups[group]["score"] += score
        row = {"id": rid, "group": group, "title": title, "status": status,
               "detail": detail, "extra": extra}
        rows.append(row)
        groups[group]["rules"].append(rid)
    total = sum(r["score"] for r in groups.values())
    max_score = sum(g["max"] for g in groups.values())
    head = _git(root, "rev-parse", "--short", "HEAD").stdout.decode("utf-8", "replace").strip()
    branch = _git(root, "rev-parse", "--abbrev-ref", "HEAD").stdout.decode("utf-8", "replace").strip()
    percent = round(100.0 * total / max_score, 1) if max_score else 0.0
    report = {
        "schema": "repo-doctor/1",
        "tool": "scripts/repo_doctor.py",
        "tool_version": TOOL_VERSION,
        "generated_at": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
        "root": ".",
        "git": {"head": head, "branch": branch},
        "score": total,
        "max_score": max_score,
        "percent": percent,
        "groups": {g: {"score": v["score"], "max": v["max"], "rules": v["rules"]}
                   for g, v in groups.items()},
        "rules": rows,
        "missing": ["%s %s：%s" % (r["id"], r["title"], r["detail"])
                    for r in rows if r["status"] == "fail"],
        "warnings": ["%s %s：%s" % (r["id"], r["title"], r["detail"])
                     for r in rows if r["status"] == "warn"],
    }
    return report


def main(argv=None):
    _utf8_stdout()
    ap = argparse.ArgumentParser(description="仓库体检（17 条 6 组）并落 JSON 基线")
    ap.add_argument("--root", default=".")
    ap.add_argument("--out", default=None,
                    help="基线输出路径（默认 results/audit/repo_doctor-baseline-<today>.json）")
    ap.add_argument("--no-write", action="store_true")
    ap.add_argument("--json", action="store_true", help="把完整报告打印到 stdout（大）")
    ap.add_argument("--min-score", type=float, default=None, help="低于该总分则 exit 1")
    args = ap.parse_args(argv)
    report = run(args.root)
    out = Path(args.out) if args.out else (
        Path(args.root) / "results" / "audit"
        / ("repo_doctor-baseline-%s.json" % datetime.date.today().isoformat()))
    if not args.no_write:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print("仓库体检基线：%s" % ("（未落盘）" if args.no_write else out.as_posix()))
        for group in GROUPS:
            g = report["groups"][group]
            items = [r for r in report["rules"] if r["group"] == group]
            marks = " ".join("%s:%s" % (r["id"], {"pass": "PASS", "warn": "WARN", "fail": "FAIL"}[r["status"]])
                             for r in items)
            print("  %-16s %4.1f/%-2d  %s" % (group, g["score"], g["max"], marks))
        print("总分：%.1f/%d（%.1f%%）  git %s@%s"
              % (report["score"], report["max_score"], report["percent"],
                 report["git"]["head"], report["git"]["branch"]))
        for item in report["missing"]:
            print("  [MISSING] %s" % item)
        for item in report["warnings"]:
            print("  [WARN] %s" % item)
    if args.min_score is not None and report["score"] < args.min_score:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
