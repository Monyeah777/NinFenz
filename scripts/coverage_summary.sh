#!/usr/bin/env bash
# 42 M5.1 本地覆盖率摘要（与 CI coverage job 同构；coverage 为可选本地工具，
# 不触碰 verify.sh 零依赖红线）。
set -e
cd "$(dirname "$0")/.."
if ! python -m coverage --version >/dev/null 2>&1; then
  echo "缺少 coverage：pip install coverage 后重跑（可选本地工具，非 verify 依赖）" >&2
  exit 2
fi
jobs="${NF_TEST_JOBS:-4}"
rc=0
COVERAGE_FILE="$PWD/.coverage" NF_COVERAGE=1 NF_TEST_JOBS="$jobs" \
  python scripts/verify_tests.py --jobs "$jobs" || rc=$?
python -m coverage combine || rc=$?
python -m coverage report --include="desktop/src/core/*" || rc=$?
exit "$rc"
