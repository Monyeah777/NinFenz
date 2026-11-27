#!/usr/bin/env bash
# 真机 Macrobenchmark：安装 benchmark 变体 APK + 测试 APK，跑 Startup/Frame/BaselineProfile。
# 前置：手机已连接并授权（adb devices 显示 device）；APK 已构建：
#   cd app/android && ./gradlew :app:assembleBenchmark :benchmark:assembleBenchmark
# 输出：每次 instrument 的原始输出（含 P50/P90、jank 等 metric）。
set -euo pipefail
ADB="${ADB:-adb}"
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
APP_APK="${APP_APK:-$ROOT/app/android/app/build/outputs/apk/benchmark/app-benchmark.apk}"
TEST_APK="${TEST_APK:-$ROOT/app/android/benchmark/build/outputs/apk/benchmark/benchmark-benchmark.apk}"
PKG="dev.ninfenz.mobile"
TEST_PKG="dev.ninfenz.mobile.benchmark"
RUNNER="androidx.test.runner.AndroidJUnitRunner"

if ! "$ADB" devices | grep -q "device$"; then
  echo "未发现已授权设备；先连接手机、开启 USB 调试并 adb devices" >&2
  exit 2
fi
for f in "$APP_APK" "$TEST_APK"; do
  [ -f "$f" ] || { echo "缺 APK：$f" >&2; exit 2; }
done

echo "[device] $("$ADB" devices -l | sed -n '2p')"
# macrobenchmark 要求三档动画关闭，否则 jank/启动口径失真
"$ADB" shell settings put global window_animation_scale 0
"$ADB" shell settings put global transition_animation_scale 0
"$ADB" shell settings put global animator_duration_scale 0

# 被测 app 必须是 benchmark 变体（profileable + 与 release 同源），测试 APK 同进程运行
"$ADB" install -r -t "$APP_APK" >/dev/null
"$ADB" install -r -t "$TEST_APK" >/dev/null

run_class() {
  local cls="$1"
  echo "=== $cls ==="
  "$ADB" logcat -c || true
  "$ADB" shell am instrument -w -r \
    -e class "$TEST_PKG.$cls" \
    "$TEST_PKG/$RUNNER" 2>&1 | tee "${OUT_DIR:-.}/$cls.txt" | tail -40
  echo "[crash]"
  "$ADB" logcat -d -t 300 | grep -E "FATAL EXCEPTION|AndroidRuntime" || echo "none"
}

OUT_DIR="${OUT_DIR:-$ROOT/results/app/macrobenchmark-$(date +%Y%m%d-%H%M%S)}"
mkdir -p "$OUT_DIR"
run_class StartupBenchmark
run_class FrameBenchmark
run_class BaselineProfileBenchmark

# 复原动画设置（用户设备习惯）
"$ADB" shell settings put global window_animation_scale 1.0
"$ADB" shell settings put global transition_animation_scale 1.0
"$ADB" shell settings put global animator_duration_scale 1.0
echo "[done] 原始输出在 $OUT_DIR"
