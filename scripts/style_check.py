#!/usr/bin/env python3
"""风格/静态检查棘轮（审计 Z2：把只跑 4 条 select 的 lint 扩成独立风格门）。

为什么（2026-10-10 全仓审计 §11t / Z2）：ruff.toml 只启用 E9/F63/F7/F82 四条语法级规则，
而全规则集实测上万条真实违例——风格债零可见（CI 完全看不见）。本门按独立 job 跑更宽的一套
规则（E,W,F,B,UP,I,C4,SIM,RET），把当前违例冻结成基线只拦新增（与 sast_check / code_metrics
同一套棘轮）：新增 (文件,规则) 或计数上升 → FAIL；下降 → WARN（提示重冻）。

刻意不并入 verify.sh（作者已裁决放弃全量门禁，见审计 §14）；本门只做「不许更糟」。

用法：
  python scripts/style_check.py            # 只读校验（新增/上升即 exit 1）
  python scripts/style_check.py --write    # 评审后把当前计数冻结为基线
  python scripts/style_check.py --json     # 打印当前计数
"""
import argparse
import collections
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "desktop" / "src"))
from core import json_doc  # noqa: E402 - 承重件在 desktop/src，脚本须能独立运行

BASELINE_REL = "protocol/style_baseline.json"
SCHEMA = "nf-style/1"
#: 扫描面：与 sast_check 同口径，外加 tools 面（风格债不区分交付与测试）。
SCAN_TARGETS = ("desktop/src", "desktop/tests", "scripts", "tui", ".github/scripts")
#: 规则集 = 审计 Z2 的建议集 + RUF100（未使用的 noqa）。
#: RUF100 专门解决审计点名的「400 条 noqa 全部不生效」：只跑窄 select 时，noqa 里那些码
#: 从不被检查，于是 noqa 变成装饰。加上它，未使用的 noqa 立刻可见（存量按基线冻结）。
SELECT = "E,W,F,B,UP,I,C4,SIM,RET,RUF100"
NOTE = ("风格棘轮（(文件,规则) 计数只许下降；新增/上升判 FAIL，下降提示重冻）。"
        "规则集 = E,W,F,B,UP,I,C4,SIM,RET；与 sast_check 的 (工具,文件,规则) 棘轮同型。"
        "只拦新增，不要求清完存量——存量数字本身就是债务台账。")


def _run(argv) -> tuple:
    try:
        p = subprocess.run(argv, cwd=str(ROOT), capture_output=True, text=True, timeout=900,
                           encoding="utf-8", errors="replace")
    except subprocess.TimeoutExpired:
        return 124, "", ("风格工具超时（900 s 未返回）：%s（修复指引：手动跑该命令确认工具可用）"
                         % " ".join(argv))
    return p.returncode, p.stdout or "", p.stderr or ""


def tool_version() -> str:
    """本机 ruff 版本（进基线：版本一变计数口径可能变，比对时要能解释）。"""
    code, out, _err = _run([sys.executable, "-m", "ruff", "--version"])
    return out.strip() if code == 0 else ""


def _counts(rows: list) -> dict:
    """命中行 → {(仓库相对文件, 规则): 计数}（与 sast_check 的落键口径一致）。"""
    cnt = collections.Counter()
    for r in rows:
        fn = str(r.get("filename"))
        abs_fn = fn if os.path.isabs(fn) else os.path.join(str(ROOT), fn)
        rel = os.path.relpath(os.path.normpath(abs_fn), str(ROOT)).replace(chr(92), "/")
        cnt[(rel, str(r.get("code")))] += 1
    return dict(cnt)


def current() -> dict:
    """→ {"counts": {"文件::规则": n}, "meta": {...}}；工具跑不出来记 error（fail-closed）。"""
    code, out, err = _run([sys.executable, "-m", "ruff", "check", "--select", SELECT,
                           "--output-format", "json", "--no-cache", *SCAN_TARGETS])
    if "No module named" in err or code in (124, 127):
        why = err.strip().splitlines()[-1] if (code == 124 and err.strip()) else "ruff 不在"
        guide = "pip install -r .github/requirements-lint.txt"
        return {"counts": {}, "meta": {"error": "%s（修复指引：%s）" % (why, guide)}}
    try:
        rows = json_doc.loads(out, None, what="ruff 输出") if out.strip().startswith("[") else []
    except ValueError as exc:
        return {"counts": {}, "meta": {"error": "ruff 输出不可解析：%s" % exc}}
    counts = _counts(rows)
    return {"counts": {("%s::%s" % k): v for k, v in counts.items()},
            "meta": {"total": sum(counts.values()), "version": tool_version()}}


def load_baseline() -> dict:
    p = ROOT / BASELINE_REL
    if not p.is_file():
        return {}
    try:
        return json_doc.load(p, dict, what=BASELINE_REL)
    except ValueError:  # 坏件 ⇒ 空基线：全部命中按新增判（fail-closed，宁可全报）
        return {}


def compare(cur: dict, base: dict) -> tuple:
    """纯函数比对（可单测）：→ (issues, warns, stats)。新增/上升 = FAIL；下降 = WARN。"""
    issues, warns = [], []
    meta = cur.get("meta") or {}
    if meta.get("error"):
        issues.append("风格工具未跑成：%s（fail-closed：不把跑不出来当零命中）" % meta["error"])
        return issues, warns, {"total": 0, "baseline": 0, "rules": 0}
    counts = cur.get("counts") or {}
    bcounts = (base or {}).get("counts") or {}
    if not bcounts:
        issues.append("缺风格基线 %s（修复指引：python scripts/style_check.py --write）"
                      % BASELINE_REL)
        return issues, warns, {"total": sum(counts.values()), "baseline": 0, "rules": 0}
    bver = str((base or {}).get("tool_version") or "")
    cver = str(meta.get("version") or "")
    if bver and cver and bver != cver:
        warns.append("ruff 版本与基线不同（基线 %s / 本机 %s）——计数口径可能变，确认后 --write 重冻"
                     % (bver, cver))
    for key, n in sorted(counts.items()):
        rule = key.split("::", 1)[1] if "::" in key else key
        show = key.replace("::", " · ")
        if key not in bcounts:
            issues.append("新增风格命中 %s（%s ×%d）（修复指引：修掉，或评审后 "
                          "python scripts/style_check.py --write 冻结）" % (show, rule, n))
        elif n > int(bcounts[key]):
            issues.append("风格命中上升 %s（%d → %d）（修复指引：同上）"
                          % (show, int(bcounts[key]), n))
    for key, n in sorted(bcounts.items()):
        if int(n) > int(counts.get(key, 0)):
            warns.append("风格命中下降 %s（%d → %d）（修复指引：从 %s 重冻）"
                         % (key.replace("::", " · "), int(n), int(counts.get(key, 0)),
                            BASELINE_REL))
    rules = len({k.split("::", 1)[1] for k in counts if "::" in k})
    return issues, warns, {"total": sum(counts.values()),
                           "baseline": sum(int(v) for v in bcounts.values()),
                           "rules": rules}


def write() -> dict:
    sys.path.insert(0, str(ROOT / "desktop" / "src"))
    from core import atomic_write
    cur = current()
    if (cur.get("meta") or {}).get("error"):
        raise SystemExit("✗ 风格工具未跑成：%s" % cur["meta"]["error"])
    doc = {"schema": SCHEMA, "note": NOTE, "select": SELECT,
           "tool_version": (cur.get("meta") or {}).get("version", ""),
           "counts": cur["counts"]}
    atomic_write.write_text(ROOT / BASELINE_REL,
                            json.dumps(doc, ensure_ascii=False, indent=2, sort_keys=True)
                            + chr(10))
    return doc


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="风格/静态检查棘轮（审计 Z2）")
    ap.add_argument("--write", action="store_true", help="评审后把当前计数冻结为基线")
    ap.add_argument("--json", action="store_true", help="打印当前计数")
    args = ap.parse_args(argv)
    if args.write:
        doc = write()
        print("== 冻结风格基线 ==")
        print("  ✓ 已写入 %s（%d 文件·规则对 · %d 条命中 · %s）"
              % (BASELINE_REL, len(doc["counts"]), sum(doc["counts"].values()),
                 doc["tool_version"]))
        return 0
    cur = current()
    if args.json:
        print(json.dumps(cur, ensure_ascii=False, indent=2, sort_keys=True))
        return 1 if (cur.get("meta") or {}).get("error") else 0
    issues, warns, stats = compare(cur, load_baseline())
    print("== 风格棘轮 ==")
    print("  命中 %d 条 · 基线 %d 条 · 规则 %d 类"
          % (stats["total"], stats["baseline"], stats["rules"]))
    for w in warns[:5]:
        print("  [WARN] %s" % w)
    for i in issues[:10]:
        print("  ✗ %s" % i, file=sys.stderr)
    return 1 if issues else 0


if __name__ == "__main__":
    # Windows 控制台 GBK 下 ✓/✗ 即 UnicodeEncodeError（与 scripts/nf.py 同纪律）。
    for _stream in (sys.stdout, sys.stderr):
        if hasattr(_stream, "reconfigure"):
            _stream.reconfigure(encoding="utf-8")
    raise SystemExit(main())
