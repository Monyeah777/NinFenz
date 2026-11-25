#!/usr/bin/env bash
# 用环境变量里的 upload key 签名 release 产物。
# 必填：NF_UPLOAD_STORE_FILE / NF_UPLOAD_STORE_PASSWORD / NF_UPLOAD_KEY_ALIAS / NF_UPLOAD_KEY_PASSWORD
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
APK_DIR="$ROOT/app/android/app/build/outputs/apk/release"
AAB_DIR="$ROOT/app/android/app/build/outputs/bundle/release"
APK="$APK_DIR/app-release-unsigned.apk"
AAB="$AAB_DIR/app-release.aab"

: "${NF_UPLOAD_STORE_FILE:?缺 NF_UPLOAD_STORE_FILE}"
: "${NF_UPLOAD_STORE_PASSWORD:?缺 NF_UPLOAD_STORE_PASSWORD}"
: "${NF_UPLOAD_KEY_ALIAS:?缺 NF_UPLOAD_KEY_ALIAS}"
: "${NF_UPLOAD_KEY_PASSWORD:?缺 NF_UPLOAD_KEY_PASSWORD}"

[[ -f "$APK" ]] || { echo "缺 release APK，先跑 ./gradlew :app:assembleRelease"; exit 4; }
[[ -f "$AAB" ]] || { echo "缺 release AAB，先跑 ./gradlew :app:bundleRelease"; exit 4; }

OUT_APK="$APK_DIR/app-release-signed.apk"
OUT_AAB="$AAB_DIR/app-release-signed.aab"

apksigner sign \
  --ks "$NF_UPLOAD_STORE_FILE" \
  --ks-pass "pass:$NF_UPLOAD_STORE_PASSWORD" \
  --ks-key-alias "$NF_UPLOAD_KEY_ALIAS" \
  --key-pass "pass:$NF_UPLOAD_KEY_PASSWORD" \
  --out "$OUT_APK" "$APK"
apksigner verify --print-certs "$OUT_APK"

jarsigner \
  -keystore "$NF_UPLOAD_STORE_FILE" \
  -storepass "$NF_UPLOAD_STORE_PASSWORD" \
  -keypass "$NF_UPLOAD_KEY_PASSWORD" \
  -sigalg SHA256withRSA -digestalg SHA-256 \
  -signedjar "$OUT_AAB" "$AAB" "$NF_UPLOAD_KEY_ALIAS"
jarsigner -verify -strict "$OUT_AAB"

echo "signed: $OUT_APK"
echo "signed: $OUT_AAB"
