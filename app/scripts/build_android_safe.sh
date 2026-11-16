#!/usr/bin/env bash
# Windows/OneDrive 下 Gradle 偶发 lint jar 文件锁；失败时停止 daemon 重试一次。
set -euo pipefail
if [ -z "${ANDROID_HOME:-}" ]; then
  echo "请先 source 工具链 env（例如 D:/tmp/app-toolchain/env.sh）" >&2
  exit 2
fi
cd "$(dirname "$0")/../android"
run() {
  if ! ./gradlew "$@" --console=plain; then
    echo "[build] 首次失败，停止 daemon 后重试: $*" >&2
    ./gradlew --stop >/dev/null 2>&1 || true
    ./gradlew "$@" --console=plain
  fi
}
run clean :app:testDebugUnitTest :app:assembleDebug
run :app:assembleRelease
echo "[build] Debug/Release APK 完成"
