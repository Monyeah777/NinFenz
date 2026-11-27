#!/usr/bin/env bash
# NF 审计门禁：跑 runner + 阈值检查。
# 退出码：0 达标；1 有阈值未过；2 参数/环境错误。
# 用法：
#   bash audit/ci/gate.sh [--root ROOT] [--commit COMMIT] [--out DIR] [--thresholds FILE]
#   bash audit/ci/gate.sh --evidence DIR        # 复用已有证据，不重跑
# 环境变量：NF_AUDIT_ROOT / NF_AUDIT_COMMIT / NF_AUDIT_PYTHON
set -eo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
AUDIT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
REPO_ROOT="$(cd "$AUDIT_DIR/.." && pwd)"

ROOT="$NF_AUDIT_ROOT"
COMMIT="$NF_AUDIT_COMMIT"
THRESHOLDS="$AUDIT_DIR/ci/thresholds.json"
OUT=""
RUN=1
PYTHON="$NF_AUDIT_PYTHON"

usage() {
  echo "用法: bash audit/ci/gate.sh [--root ROOT] [--commit COMMIT] [--out DIR] [--thresholds FILE] [--evidence DIR] [--no-run]"
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --root) ROOT="$2"; shift 2 ;;
    --commit) COMMIT="$2"; shift 2 ;;
    --out) OUT="$2"; shift 2 ;;
    --thresholds) THRESHOLDS="$2"; shift 2 ;;
    --evidence) OUT="$2"; RUN=0; shift 2 ;;
    --no-run) RUN=0; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "[gate] 未知参数: $1"; usage; exit 2 ;;
  esac
done

if [ -z "$ROOT" ]; then ROOT="$REPO_ROOT"; fi
if [ -z "$COMMIT" ]; then COMMIT="$(git -C "$REPO_ROOT" rev-parse --short HEAD 2>/dev/null || true)"; fi
if [ -z "$COMMIT" ]; then COMMIT="unknown"; fi
if [ -z "$OUT" ]; then OUT="$AUDIT_DIR/evidence/$COMMIT"; fi
if [ -z "$PYTHON" ]; then
  if command -v python >/dev/null 2>&1; then PYTHON=python; else PYTHON=python3; fi
fi
if [ ! -f "$THRESHOLDS" ]; then
  echo "[gate] 阈值文件不存在: $THRESHOLDS"; exit 2
fi
export PYTHONIOENCODING=utf-8

# Windows 上的 python.exe 不认 /d/... 形式的 MSYS 路径，需要转成盘符形式再传参；
# 否则会把它解析成当前盘的相对路径（D:\d\NinFenz\...）并报文件不存在。
win_path() {
  if command -v cygpath >/dev/null 2>&1; then
    cygpath -m "$1"
  else
    printf '%s' "$1"
  fi
}
RUNNER_PY="$(win_path "$AUDIT_DIR/runner.py")"
THRESHOLDS_ARG="$(win_path "$THRESHOLDS")"
ROOT_ARG="$(win_path "$ROOT")"
OUT_ARG="$(win_path "$OUT")"

echo "[gate] 阈值文件: $THRESHOLDS"
if [ "$RUN" -eq 1 ]; then
  echo "[gate] 执行审计: root=$ROOT commit=$COMMIT out=$OUT"
  "$PYTHON" "$RUNNER_PY" --root "$ROOT_ARG" --commit "$COMMIT" --out "$OUT_ARG"
else
  echo "[gate] 复用证据: $OUT"
fi
if [ ! -f "$OUT/meta.json" ]; then
  echo "[gate] 缺少 meta.json: $OUT/meta.json"; exit 2
fi

"$PYTHON" - "$(win_path "$OUT/meta.json")" "$THRESHOLDS_ARG" <<'PYEOF'
import json
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

meta_path, thresholds_path = sys.argv[1], sys.argv[2]
with open(meta_path, encoding="utf-8") as fh:
    meta = json.load(fh)
with open(thresholds_path, encoding="utf-8") as fh:
    th = json.load(fh)

failures = []
warnings = []

def fmt(value):
    return ("%.2f" % float(value)).rstrip("0").rstrip(".")

total = float(meta.get("score", 0))
total_min = float(th.get("total_min", 0))
if total >= total_min:
    print("[gate] 总分 %s >= 阈值 %s  PASS" % (fmt(total), fmt(total_min)))
else:
    print("[gate] 总分 %s < 阈值 %s  FAIL" % (fmt(total), fmt(total_min)))
    failures.append("总分 %s < %s" % (fmt(total), fmt(total_min)))

dim_min = float(th.get("dimension_min", 0))
for dim in sorted(meta.get("dimensions", {})):
    score = float(meta["dimensions"][dim].get("score", 0))
    if score >= dim_min:
        print("[gate] 维度 %s %s >= %s  PASS" % (dim, fmt(score), fmt(dim_min)))
    else:
        print("[gate] 维度 %s %s < %s  FAIL" % (dim, fmt(score), fmt(dim_min)))
        failures.append("维度 %s 得分 %s < %s" % (dim, fmt(score), fmt(dim_min)))

counts = meta.get("severity_counts", {})
p0 = int(counts.get("P0", 0))
p0_max = int(th.get("p0_max", 0))
if p0 <= p0_max:
    print("[gate] P0 命中 %d <= 允许 %d  PASS" % (p0, p0_max))
else:
    print("[gate] P0 命中 %d > 允许 %d  FAIL" % (p0, p0_max))
    failures.append("P0 命中 %d > %d" % (p0, p0_max))

errors = len(meta.get("errors") or [])
error_max = int(th.get("rule_error_max", 0))
if errors <= error_max:
    print("[gate] 规则执行异常 %d <= 允许 %d  PASS" % (errors, error_max))
else:
    print("[gate] 规则执行异常 %d > 允许 %d  FAIL" % (errors, error_max))
    failures.append("规则执行异常 %d > %d" % (errors, error_max))

status = meta.get("status_counts", {})
no_targets = int(status.get("no_targets", 0))
nt_max = int(th.get("no_targets_max", 0))
if no_targets <= nt_max:
    print("[gate] 无目标规则 %d <= 允许 %d  PASS" % (no_targets, nt_max))
else:
    print("[gate] 无目标规则 %d > 允许 %d  FAIL" % (no_targets, nt_max))
    failures.append("无目标规则 %d > %d" % (no_targets, nt_max))

not_run = int(status.get("not-run", 0))
if not_run:
    warnings.append("tool/manual 未执行 %d 条（不计分，不视为通过）" % not_run)

print("[gate] 证据: %s" % meta_path)
print("[gate] commit: %s | 规则总数: %s | script: %s | tool: %s | manual: %s" % (
    meta.get("commit"), meta.get("rules", {}).get("total"),
    meta.get("rules", {}).get("script"), meta.get("rules", {}).get("tool"),
    meta.get("rules", {}).get("manual")))
for warning in warnings:
    print("[gate] 提示: " + warning)

if failures:
    print("[gate] 结果: FAIL")
    for item in failures:
        print("[gate]   未过: " + item)
    sys.exit(1)
print("[gate] 结果: PASS")
sys.exit(0)
PYEOF
