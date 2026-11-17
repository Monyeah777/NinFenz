#!/usr/bin/env bash
# 真机 smoke：安装 debug APK、冷启动、检查前台 Activity 与崩溃日志。
set -euo pipefail
ADB="${ADB:-adb}"
APK="${APK:-$(dirname "$0")/../android/app/build/outputs/apk/debug/app-debug.apk}"
PKG="dev.ninfenz.mobile"
ACT="$PKG/.MainActivity"
if ! "$ADB" devices | grep -q "device$"; then
  echo "未发现已授权设备；先连接手机并 adb devices" >&2
  exit 2
fi
[ -f "$APK" ] || { echo "缺 APK：$APK" >&2; exit 2; }
echo "[device] $("$ADB" devices -l | sed -n '2p')"
"$ADB" install -r "$APK" >/dev/null
"$ADB" shell am force-stop "$PKG"
"$ADB" shell am start -W -n "$ACT" | tail -5
sleep 3
echo "[activity] $("$ADB" shell dumpsys activity activities | grep -m1 -E "mResumedActivity|topResumedActivity" || true)"
echo "[crash]"
"$ADB" logcat -d -t 200 | grep -E "FATAL EXCEPTION|AndroidRuntime" || echo "none"
echo "[crash] done"
CAPTURE_DIR="${CAPTURE_DIR:-}"
if [ -n "$CAPTURE_DIR" ]; then
  mkdir -p "$CAPTURE_DIR"
  "$ADB" exec-out screencap -p > "$CAPTURE_DIR/home.png"
  "$ADB" shell uiautomator dump /sdcard/nf-ui.xml >/dev/null 2>&1 || true
  "$ADB" pull /sdcard/nf-ui.xml "$CAPTURE_DIR/ui.xml" >/dev/null 2>&1 || true
  echo "[capture] $CAPTURE_DIR/home.png + ui.xml"
fi
echo "[device] smoke 完成"
