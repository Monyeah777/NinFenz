#!/usr/bin/env bash
# 用 upload keystore 签 Android release APK。凭据只从环境变量读取，不落命令行/仓库。
# 用法：
#   NF_KEYSTORE=/abs/upload.jks NF_KEYSTORE_PASS=*** NF_KEY_ALIAS=upload NF_KEY_PASS=*** \
#     bash app/scripts/sign_release.sh
# 前置：先 bash app/scripts/build_android_safe.sh 生成 release unsigned。
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
APP="$ROOT/app/android"
UNSIGNED="$APP/app/build/outputs/apk/release/app-release-unsigned.apk"
SIGNED="$APP/app/build/outputs/apk/release/app-release-signed.apk"

: "${NF_KEYSTORE:?need NF_KEYSTORE (keystore path)}"
: "${NF_KEYSTORE_PASS:?need NF_KEYSTORE_PASS}"
: "${NF_KEY_ALIAS:?need NF_KEY_ALIAS}"
: "${NF_KEY_PASS:?need NF_KEY_PASS}"
[ -f "$UNSIGNED" ] || { echo "missing $UNSIGNED；先 bash app/scripts/build_android_safe.sh" >&2; exit 1; }

SDK="${ANDROID_HOME:-${ANDROID_SDK_ROOT:-}}"
[ -n "$SDK" ] || { echo "need ANDROID_HOME or ANDROID_SDK_ROOT" >&2; exit 1; }
BT="$(ls -d "$SDK"/build-tools/* 2>/dev/null | sort -V | tail -1)"
[ -n "$BT" ] || { echo "no build-tools under $SDK" >&2; exit 1; }

run_tool() {
  local name="$1"; shift
  if [ -x "$BT/$name" ]; then "$BT/$name" "$@"
  elif [ -f "$BT/$name.bat" ]; then cmd //c "$(cygpath -w "$BT/$name.bat")" "$@"
  else echo "missing $name in $BT" >&2; exit 1
  fi
}

run_tool zipalign -c -P 16 4 "$UNSIGNED"
rm -f "$SIGNED"
run_tool apksigner sign \
  --ks "$NF_KEYSTORE" \
  --ks-pass env:NF_KEYSTORE_PASS \
  --key-pass env:NF_KEY_PASS \
  --ks-key-alias "$NF_KEY_ALIAS" \
  --out "$SIGNED" "$UNSIGNED"
run_tool apksigner verify --print-certs "$SIGNED"

sha256sum "$SIGNED"
echo "signed: $SIGNED"
