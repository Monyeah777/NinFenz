#!/usr/bin/env python3
"""Markdown 内链检查（DC-06）：仓内相对链接 404 直接失败；外链不在这里判（见 external-links.yml）。

为什么要分级：外链可达性取决于网络与第三方站点，天天抖动会让红灯失去信号；
本仓把外链交给独立的定时任务（仅告警），把**仓内相对链接**做成必过闸门。

判定口径：
- 扫描仓库全部 tracked Markdown（--include-untracked 时连未跟踪的也扫，CI 中无差别）；
- 只判相对链接/图片目标：跳过 http(s)/mailto/tel/data 等 scheme、跳过纯锚点 #xxx；
- 目标去 query 与 #fragment 后按 UTF-8 百分号解码，再相对所在 md 解析；
- 大小写敏感比较（逐级目录名精确匹配），避免 Windows 大小写不敏感掩盖 Linux 上的 404；
- 裸标识符（无 / 无扩展名的 current_day 这类）不当作路径引用——伪代码里的函数调用
  会自然出现 "x[...](y)" 形态，把它们算死链只会训练人们关掉检查；
- 存量欠账走 scripts/internal_link_baseline.json（逐条 file+target+reason），新增死链仍必须红。

用法：
  python scripts/check_internal_links.py
  python scripts/check_internal_links.py --json --report .artifacts/internal-links.json
负例自证：临时造一个死链后必须 exit 1；删掉后 exit 0。
"""
import argparse
import json
import os
import re
import subprocess
import sys
import urllib.parse
from pathlib import Path

BASELINE_REL = "scripts/internal_link_baseline.json"
EXTERNAL_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*:")
FENCE_RE = re.compile(r"^\s*(`{3,}|~{3,})\s*([^\s]*)\s*$")
INLINE_CODE_RE = re.compile(r"`[^`\n]*`")
HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.S)
LINK_RE = re.compile(r"!?\[([^\]]*)\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
REF_DEF_RE = re.compile(r"^\s*\[[^\]]+\]:\s*(\S+)", re.M)


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


def _md_files(root, include_untracked=True):
    p = _git(root, "rev-parse", "--git-dir")
    if p.returncode != 0:
        return None
    raw = _git(root, "ls-files", "-z", "*.md").stdout
    files = [x.decode("utf-8") for x in raw.split(b"\0") if x]
    if include_untracked:
        raw = _git(root, "ls-files", "--others", "--exclude-standard", "-z", "*.md").stdout
        files += [x.decode("utf-8") for x in raw.split(b"\0") if x]
    return sorted(set(files))


def _strip_noise(text):
    """去掉 fenced code 块、行内代码、HTML 注释——它们不是链接面。"""
    out, in_fence, fence = [], False, ""
    for line in text.splitlines():
        m = FENCE_RE.match(line)
        if m:
            mark = m.group(1)
            if not in_fence:
                in_fence, fence = True, mark[0] * 3
            elif mark[0] == fence[0] and len(mark) >= len(fence):
                in_fence = False
                fence = ""
            out.append("")
            continue
        out.append("" if in_fence else line)
    body = "\n".join(out)
    body = HTML_COMMENT_RE.sub("", body)
    return INLINE_CODE_RE.sub("", body)


def _exact_exists(root, rel_parts):
    """逐级比较目录名（大小写敏感），模拟 Linux 上的路径解析。"""
    cur = root
    for part in rel_parts:
        if part in ("", "."):
            continue
        if part == "..":
            cur = cur.parent
            continue
        try:
            entries = os.listdir(cur)
        except OSError:
            return False
        if part not in entries:
            return False
        cur = cur / part
    return cur.exists()


def _looks_like_path(target):
    if "/" in target or "\\" in target:
        return True
    tail = target.rsplit("/", 1)[-1]
    return "." in tail


def scan(root=".", include_untracked=True, baseline_path=None):
    root = Path(root).resolve()
    files = _md_files(root, include_untracked=include_untracked)
    if files is None:
        return {"ok": False, "error": f"不是 git 仓库：{root}", "dead": []}
    dead, skipped_bare, total = [], [], 0
    for rel in files:
        path = root / rel
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            dead.append({"file": rel, "line": 1, "target": "<unreadable>", "why": str(exc)})
            continue
        body = _strip_noise(text)
        found = [(m.start(), m.group(2)) for m in LINK_RE.finditer(body)]
        found += [(m.start(), m.group(1)) for m in REF_DEF_RE.finditer(body)]
        for pos, raw_url in found:
            url = raw_url.strip()
            if url.startswith("<") and url.endswith(">"):
                url = url[1:-1]
            if not url or EXTERNAL_RE.match(url) or url.startswith("//") or url.startswith("#"):
                continue
            target = urllib.parse.unquote(url.split("#")[0].split("?")[0])
            if not target:
                continue
            if not _looks_like_path(target):
                skipped_bare.append({"file": rel, "target": url})
                continue
            total += 1
            base = root if target.startswith("/") else path.parent
            parts = Path(target.lstrip("/")).parts if target.startswith("/") else Path(target).parts
            if not _exact_exists(base, parts):
                line = body[:pos].count("\n") + 1
                dead.append({"file": rel, "line": line, "target": url})
    # 存量欠账白名单：逐条匹配 (file, target)
    baseline, stale = [], []
    bp = Path(baseline_path) if baseline_path else (root / BASELINE_REL)
    if bp.is_file():
        try:
            data = json.loads(bp.read_text(encoding="utf-8"))
            baseline = data.get("unresolved") or []
        except (OSError, ValueError) as exc:
            return {"ok": False, "error": f"baseline 解析失败：{exc}", "dead": dead}
    known = {(e.get("file"), e.get("target")) for e in baseline}
    suppressed, unexpected = [], []
    for d in dead:
        (suppressed if (d.get("file"), d.get("target")) in known else unexpected).append(d)
    used = {(d.get("file"), d.get("target")) for d in suppressed}
    stale = [e for e in baseline if (e.get("file"), e.get("target")) not in used]
    return {"ok": not unexpected, "error": "", "scanned_files": len(files),
            "relative_links": total, "dead": dead, "unexpected": unexpected,
            "suppressed": suppressed, "stale_baseline": stale,
            "ignored_bare_identifiers": skipped_bare}


def main(argv=None):
    _utf8_stdout()
    ap = argparse.ArgumentParser(description="Markdown 内链检查（内链 404 直接失败）")
    ap.add_argument("--root", default=".")
    ap.add_argument("--baseline", default=None,
                    help="存量白名单（默认 scripts/internal_link_baseline.json）")
    ap.add_argument("--tracked-only", action="store_true", help="只扫 tracked 文件")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--report", default=None, help="把 JSON 报告写到该路径")
    args = ap.parse_args(argv)
    res = scan(args.root, include_untracked=not args.tracked_only, baseline_path=args.baseline)
    if args.report:
        Path(args.report).parent.mkdir(parents=True, exist_ok=True)
        Path(args.report).write_text(json.dumps(res, ensure_ascii=False, indent=2) + "\n",
                                     encoding="utf-8")
    if args.json:
        print(json.dumps(res, ensure_ascii=False, indent=2))
    elif res.get("error"):
        print("[ERROR] {}".format(res["error"]))
    else:
        print(f"内链检查：md {res['scanned_files']} 件 / 相对链接 {res['relative_links']} 条 "
              f"/ 死链 {len(res['dead'])} 条（白名单抑制 {len(res['suppressed'])}，"
              f"裸标识符忽略 {len(res['ignored_bare_identifiers'])}）")
        for d in res["unexpected"]:
            print("[FAIL] {}:{} -> {}".format(d["file"], d.get("line", "?"), d["target"]))
        for d in res["suppressed"]:
            print("  [baseline] {}:{} -> {}".format(d["file"], d.get("line", "?"), d["target"]))
        for s in res["stale_baseline"]:
            print(f"  [baseline-stale] {s.get('file')} -> {s.get('target')}"
                  "（已不再死链，可删除该条）")
        if res["unexpected"]:
            print(f"修复指引：改正相对路径或补文件；若确属存量欠账，登记到 {BASELINE_REL}")
        else:
            print("通过：无新增内链 404")
    return 0 if res["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
