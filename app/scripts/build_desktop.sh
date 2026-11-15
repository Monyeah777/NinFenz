#!/usr/bin/env bash
# 构建 Compose Multiplatform NF Studio（app/desktop）。
# 用法：bash app/scripts/build_desktop.sh [run|package]
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
APP_DIR="$ROOT/app/desktop"
MODE="${1:-package}"
if [ ! -d "$APP_DIR" ]; then
  echo "缺 app/desktop 工程（修复指引：先落地 CMP 工程）" >&2
  exit 4
fi
if ! command -v java >/dev/null 2>&1; then
  echo "JDK 不在 PATH（修复指引：安装 JDK 21）" >&2
  exit 4
fi
cd "$APP_DIR"
if [ -x ./gradlew ]; then GRADLE=./gradlew; elif command -v gradle >/dev/null 2>&1; then GRADLE=gradle; else
  echo "无 gradle wrapper 且 PATH 无 gradle（修复指引：生成 wrapper 或安装 Gradle 8.11+）" >&2; exit 4
fi
case "$MODE" in
  run) "$GRADLE" :run ;;
  package) "$GRADLE" packageDistributionForCurrentOS ;;
  *) echo "未知模式：$MODE" >&2; exit 2 ;;
esac
