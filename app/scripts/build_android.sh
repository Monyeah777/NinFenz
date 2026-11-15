#!/usr/bin/env bash
# 构建 Android APP（app/android）：assembleDebug / assembleRelease。
# 用法：bash app/scripts/build_android.sh [debug|release]
# 环境要求：JDK 21 + Android SDK（ANDROID_HOME/ANDROID_SDK_ROOT）+ 可用 Gradle wrapper。
# 纪律：工具链缺失时退出码 4 并给修复指引——不假装构建过。
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VARIANT="${1:-debug}"
APP_DIR="$ROOT/app/android"
if [ ! -d "$APP_DIR" ]; then
  echo "缺 app/android 工程（修复指引：先落地 Android 工程）" >&2
  exit 4
fi
if ! command -v java >/dev/null 2>&1; then
  echo "JDK 不在 PATH（修复指引：安装 JDK 21）" >&2
  exit 4
fi
if [ -z "${ANDROID_HOME:-}" ] && [ -z "${ANDROID_SDK_ROOT:-}" ] && [ ! -d "${LOCALAPPDATA:-}/Android/Sdk" ]; then
  echo "Android SDK 不在场（修复指引：设 ANDROID_HOME，或按 app/results/TOOLCHAIN.md 安装 cmdline-tools）" >&2
  exit 4
fi
cd "$APP_DIR"
if [ -x ./gradlew ]; then GRADLE=./gradlew; elif command -v gradle >/dev/null 2>&1; then GRADLE=gradle; else
  echo "无 gradle wrapper 且 PATH 无 gradle（修复指引：生成 wrapper 或安装 Gradle 8.11+）" >&2; exit 4
fi
case "$VARIANT" in
  debug) "$GRADLE" :app:assembleDebug ;;
  release) "$GRADLE" :app:assembleRelease ;;
  *) echo "未知 variant：$VARIANT" >&2; exit 2 ;;
esac
echo "✔ APK 产物：$APP_DIR/app/build/outputs/apk/$VARIANT/"
