#!/usr/bin/env python3
"""NF APP 门禁（QA0–QA6 + S0–S15 自审计）——APP 侧的唯一机检入口。

设计纪律（与仓库 verify.sh 同一套）：
- **判据只增不减**：gates.json 里的 check id 一旦入册不得删除（改口径要写进文档并保留旧 id）。
- **不许假绿**：required 的 check 缺件/失败即 FAIL；未完成的项显式 required=false + owner + next → 记 OPEN。
- **确定性**：输出不含时间戳/随机/绝对路径（HEAD 与输入摘要除外）；同一输入两次运行逐字节一致。
- **可复跑**：每条证据都带 argv 与 exit code；日志落 app/results/logs/。

用法：
  python app/gates/run_gates.py                 # 跑全部 gate，输出 GATES.json + SELF_AUDIT.json
  python app/gates/run_gates.py --only QA0 QA1  # 只跑指定 gate
  python app/gates/run_gates.py --json          # 机器面（stdout 摘要）
退出码：0 全部通过（FAIL=0）；1 有 FAIL；2 用法/IO。
"""
from __future__ import annotations

import argparse
import glob as globmod
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / "app"
RES = APP / "results"
LOGS = RES / "logs"


def _rel(p: Path) -> str:
    try:
        return p.resolve().relative_to(ROOT.resolve()).as_posix()
    except Exception:
        return p.name


def _head() -> str:
    try:
        out = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                             capture_output=True, text=True, timeout=30)
        return out.stdout.strip() if out.returncode == 0 else ""
    except Exception:
        return ""


def _load(path: Path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _expand(pat: str) -> list[str]:
    hits = globmod.glob(str(ROOT / pat), recursive=True)
    return sorted(_rel(Path(h)) for h in hits if Path(h).is_file())


def _run(argv: list[str], cwd: Path | None = None) -> tuple[int, str]:
    LOGS.mkdir(parents=True, exist_ok=True)
    name = "_".join(re.sub(r"[^A-Za-z0-9._-]+", "-", a) for a in argv)[:120] + ".log"
    env = dict(os.environ)
    env.setdefault("PYTHONUTF8", "1")
    try:
        proc = subprocess.run(argv, cwd=(cwd or ROOT), capture_output=True, text=True,
                              encoding="utf-8", errors="replace",
                              timeout=1800, env=env)
        text = (proc.stdout or "") + (proc.stderr or "")
        code = proc.returncode
    except FileNotFoundError:
        text = "ENV-MISSING: %s" % argv[0]
        code = 4
    except subprocess.TimeoutExpired:
        text = "TIMEOUT after 1800s"
        code = 2
    (LOGS / name).write_text(text, encoding="utf-8")
    return code, _rel(LOGS / name)


def _summary(text: str) -> dict:
    """从 pytest / cargo 输出提取计数（贪婪但稳定；拿不到就记 null，不猜）。"""
    m = re.search(r"(\d+) passed", text)
    f = re.search(r"(\d+) failed", text)
    e = re.search(r"(\d+) error", text)
    t = re.search(r"(\d+) tests? collected|running (\d+) tests?", text)
    return {"passed": int(m.group(1)) if m else None,
            "failed": int(f.group(1)) if f else None,
            "errors": int(e.group(1)) if e else None,
            "collected": int(t.group(1) or t.group(2)) if t else None}


def _scan_voids() -> dict:
    """S1 代码空洞：core/cli 源码里的 TODO/FIXME/unimplemented!/todo!()/占位实现。"""
    pats = re.compile(r"\b(TODO|FIXME|XXX|unimplemented!|todo!|panic!\(\"TODO)")
    hits, scanned = [], 0
    for base in ("app/core/src", "app/cli"):
        for path in sorted((ROOT / base).rglob("*")) if (ROOT / base).is_dir() else []:
            if path.is_file() and path.suffix in (".rs", ".py"):
                scanned += 1
                try:
                    text = path.read_text(encoding="utf-8")
                except Exception:
                    continue
                for i, line in enumerate(text.splitlines(), 1):
                    if pats.search(line):
                        hits.append("%s:%d:%s" % (_rel(path), i, line.strip()[:120]))
    return {"scanned": scanned, "hits": hits}



#: 内置断言函数（kind=func 时按名调用，返回 (ok, detail, evidence)）
TEXT_EXT = {".json", ".md", ".py", ".rs", ".toml", ".kts", ".kt", ".xml", ".properties",
            ".sh", ".ps1", ".cfg", ".txt", ".yml", ".yaml", ".gitignore"}
BIN_EXT = {".apk", ".dll", ".so", ".jar", ".dex", ".png", ".jpg", ".jpeg", ".webp", ".zip", ".ico", ".class"}
SKIP_PARTS = {"target", "build", ".gradle", "node_modules", "__pycache__", ".git", "logs"}


def _skip(path: Path) -> bool:
    return any(part in SKIP_PARTS for part in path.parts)


def check_encoding() -> tuple:
    """app/ 文本文件：UTF-8 无 BOM + LF（仓库 text_hygiene 口径）。"""
    bad = []
    for path in sorted(APP.rglob("*")):
        if not path.is_file() or path.suffix.lower() in BIN_EXT or _skip(path):
            continue
        if path.suffix.lower() not in TEXT_EXT:
            continue
        raw = path.read_bytes()
        if raw.startswith(b"\xef\xbb\xbf"):
            bad.append("%s: BOM" % _rel(path))
        if b"\r\n" in raw:
            bad.append("%s: CRLF" % _rel(path))
    return (not bad, "坏件 %d" % len(bad), bad[:20])


def check_no_machine_paths() -> tuple:
    """app/{schema,core,cli,tests,fixtures,gates} 不得硬编码本机绝对路径/用户名。"""
    pats = re.compile(r"C:\\Users|C:/Users|D:\\NinFenz|D:/NinFenz|D:\\tmp|/d/NinFenz|mon_7")
    bad = []
    for base in ("app/core", "app/cli"):
        d = ROOT / base
        if not d.is_dir():
            continue
        for path in sorted(d.rglob("*")):
            if not path.is_file() or path.suffix.lower() in BIN_EXT or _skip(path):
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except Exception:
                continue
            for i, line in enumerate(text.splitlines(), 1):
                if pats.search(line):
                    bad.append("%s:%d" % (_rel(path), i))
    return (not bad, "命中 %d" % len(bad), bad[:20])


def _registry_checks(reg: dict, only: list[str]) -> tuple[list[dict], list[dict]]:
    results, failed = [], []
    for gate in reg["gates"]:
        if only and gate["id"] not in only:
            continue
        for chk in gate.get("checks", []):
            r = {"gate": gate["id"], "check": chk["id"], "title": chk.get("title", ""),
                 "required": chk.get("required", True), "kind": chk["kind"],
                 "status": "PASS", "detail": None, "evidence": None,
                 "owner": chk.get("owner"), "next": chk.get("next")}
            try:
                if chk["kind"] == "files":
                    missing = [p for p in chk["paths"] if not (ROOT / p).exists()]
                    if missing:
                        r["status"] = "FAIL" if r["required"] else "OPEN"
                        r["detail"] = "缺件：" + ", ".join(missing)
                    else:
                        r["evidence"] = sorted(chk["paths"])
                elif chk["kind"] == "glob_min":
                    hits = _expand(chk["glob"])
                    r["evidence"] = hits[:20]
                    if len(hits) < chk.get("min", 1):
                        r["status"] = "FAIL" if r["required"] else "OPEN"
                        r["detail"] = "命中 %d < %d（%s）" % (len(hits), chk.get("min", 1), chk["glob"])
                elif chk["kind"] == "glob_json":
                    hits = _expand(chk["glob"])
                    bad = []
                    for h in hits:
                        try:
                            _load(ROOT / h)
                        except Exception as exc:  # noqa: BLE001 - 报告到 detail，不抛
                            bad.append("%s: %s" % (h, exc))
                    r["evidence"] = hits[:20]
                    if len(hits) < chk.get("min", 1) or bad:
                        r["status"] = "FAIL" if r["required"] else "OPEN"
                        r["detail"] = "命中 %d / 坏件 %d" % (len(hits), len(bad))
                elif chk["kind"] == "cmd":
                    cwd = (ROOT / chk["cwd"]) if chk.get("cwd") else None
                    code, log = _run(chk["argv"], cwd)
                    r["evidence"] = {"argv": chk["argv"], "exit": code, "log": log,
                                     "summary": _summary((LOGS / Path(log).name).read_text(encoding="utf-8"))}
                    ok = code == chk.get("expect_exit", 0)
                    if not ok:
                        r["status"] = "FAIL" if r["required"] else "OPEN"
                        r["detail"] = "exit=%d（期望 %d），日志 %s" % (code, chk.get("expect_exit", 0), log)
                elif chk["kind"] == "func":
                    fn = {"check_encoding": check_encoding,
                          "check_no_machine_paths": check_no_machine_paths}.get(chk["name"])
                    if fn is None:
                        raise KeyError("未注册的 func：%s" % chk.get("name"))
                    ok, detail, ev = fn()
                    r["detail"] = detail
                    r["evidence"] = ev
                    if not ok:
                        r["status"] = "FAIL" if r["required"] else "OPEN"
                else:
                    r["status"] = "FAIL"
                    r["detail"] = "未知 check kind：%s" % chk["kind"]
            except Exception as exc:  # noqa: BLE001 - 单 check 异常不拖垮整轮，如实记
                r["status"] = "FAIL" if r["required"] else "OPEN"
                r["detail"] = "执行异常：%r" % (exc,)
            if r["status"] == "FAIL":
                failed.append(r)
            results.append(r)
    return results, failed


def _dimensions(dim: dict, gate_results: list[dict]) -> tuple[list[dict], list[dict], list[dict]]:
    voids = _scan_voids()
    out, gaps, opens = [], [], []
    for d in dim["dimensions"]:
        entry = {"id": d["id"], "title": d["title"], "status": d["status"],
                 "evidence": [], "owner": d.get("owner"), "next": d.get("next"), "note": d.get("note")}
        missing = [e for e in d.get("evidence", []) if not (ROOT / e).exists()]
        entry["evidence"] = [e for e in d.get("evidence", []) if e not in missing]
        if missing:
            entry["status"] = "gap"
            entry.setdefault("owner", "lead")
            entry["next"] = (entry.get("next") or "") + ("；缺证据：" + ", ".join(missing))
        if d["id"] == "S1":
            entry["probes"] = {"scanned_files": voids["scanned"], "void_hits": len(voids["hits"]),
                               "hits": voids["hits"][:20]}
            if voids["hits"]:
                entry["status"] = "gap"
                entry["owner"] = entry.get("owner") or "lead"
                entry["next"] = "清理空洞或换算子实现（见 hits）"
            else:
                entry["status"] = "covered"
        if entry["status"] == "covered":
            pass
        elif entry["status"] == "gap":
            if not entry.get("owner") or not entry.get("next"):
                entry["status"] = "gap"
                entry["owner"] = entry.get("owner") or "lead"
                entry["next"] = entry.get("next") or "未登记 next（按纪律必须补）"
            gaps.append(entry)
        elif entry["status"] == "open":
            opens.append(entry)
        out.append(entry)
    return out, gaps, opens


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="NF APP 门禁（QA0–QA6 + S0–S15）")
    ap.add_argument("--only", nargs="*", default=None, help="只跑指定 gate id（如 QA0 QA2）")
    ap.add_argument("--json", action="store_true", help="stdout 输出机器面摘要")
    args = ap.parse_args(argv)

    reg = _load(APP / "gates" / "gates.json")
    dim = _load(APP / "gates" / "dimensions.json")
    reg["gates"] = [g for g in reg["gates"] if not args.only or g["id"] in args.only]
    gate_results, failed = _registry_checks(reg, args.only)
    dims, gaps, opens = _dimensions(dim, gate_results)
    p0 = len(failed) + len([g for g in gaps if not g.get("owner") or not g.get("next")])
    p1 = len([g for g in gaps if g.get("owner") and g.get("next")]) + len(opens)

    summary = {
        "schema": "nf-app-gates/1",
        "head": _head(),
        "gates": {},
        "self_audit": {
            "dimensions": len(dims),
            "covered": len([d for d in dims if d["status"] == "covered"]),
            "gap": len(gaps), "open": len(opens),
            "p0": p0, "p1": p1,
            "stop_condition": "QA0–QA6 FAIL=0 且 P0=0 且 UNSUPPORTED 全部带 owner+next（连续两轮）",
        },
        "results": gate_results,
        "dimensions": dims,
        "open_items": [{"id": g["id"], "title": g["title"], "owner": g["owner"], "next": g["next"]}
                       for g in gaps + opens],
    }
    for r in gate_results:
        s = summary["gates"].setdefault(r["gate"], {"checks": 0, "pass": 0, "fail": 0, "open": 0})
        s["checks"] += 1
        s["pass" if r["status"] == "PASS" else ("fail" if r["status"] == "FAIL" else "open")] += 1
    RES.mkdir(parents=True, exist_ok=True)
    with open(RES / "GATES.json", "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    with open(RES / "SELF_AUDIT.json", "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps({
            "schema": "nf-app-self-audit/1", "head": summary["head"],
            "summary": summary["self_audit"], "dimensions": dims,
            "open_items": summary["open_items"]}, ensure_ascii=False, indent=2, sort_keys=True) + "\n")

    if args.json:
        print(json.dumps({"ok": p0 == 0, "p0": p0, "p1": p1,
                          "gates": summary["gates"], "head": summary["head"]},
                         ensure_ascii=False, sort_keys=True))
    else:
        print("== NF APP 门禁 ==")
        for gid, s in summary["gates"].items():
            print("  %-4s checks=%d pass=%d fail=%d open=%d"
                  % (gid, s["checks"], s["pass"], s["fail"], s["open"]))
        print("  自审计：covered=%d gap=%d open=%d p0=%d p1=%d"
              % (summary["self_audit"]["covered"], len(gaps), len(opens), p0, p1))
        for r in failed:
            print("  [FAIL] %s %s：%s" % (r["gate"], r["check"], r["detail"]))
    return 0 if p0 == 0 else 1


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    raise SystemExit(main())