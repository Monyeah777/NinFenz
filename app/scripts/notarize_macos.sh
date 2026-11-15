#!/usr/bin/env bash
# macOS 签名 + 公证（Developer ID + Hardened Runtime + notarytool + staple + Sparkle）。
# 用法：bash app/scripts/notarize_macos.sh <App.app|.dmg>
# 纪律：非 macOS / 无 Developer ID 证书 / 无 Apple 凭据时退出码 4；不冒充已公证。
set -euo pipefail
TARGET="${1:-}"
if [ -z "$TARGET" ]; then echo "用法：notarize_macos.sh <App.app|.dmg>" >&2; exit 2; fi
if [ "$(uname -s)" != "Darwin" ]; then
  echo "OPEN-EXTERNAL: 本机不是 macOS（公证只能在 Apple 环境执行）" >&2
  exit 4
fi
if ! command -v xcrun >/dev/null 2>&1; then
  echo "OPEN-EXTERNAL: 缺 Xcode command line tools" >&2
  exit 4
fi
if [ -z "${NOTARY_PROFILE:-}" ]; then
  echo "OPEN-EXTERNAL: 未设 NOTARY_PROFILE（xcrun notarytool store-credentials 后的 profile 名）" >&2
  exit 4
fi
IDENTITY="${DEVELOPER_ID_APPLICATION:-}"
if [ -z "$IDENTITY" ]; then
  echo "OPEN-EXTERNAL: 未设 DEVELOPER_ID_APPLICATION（Developer ID Application 证书名）" >&2
  exit 4
fi
if [ -d "$TARGET" ]; then
  ZIP="$TARGET.zip"; ditto -c -k --keepParent "$TARGET" "$ZIP"; UPLOAD="$ZIP"
else
  UPLOAD="$TARGET"
fi
codesign --force --options runtime --timestamp --sign "$IDENTITY" "$TARGET"
xcrun notarytool submit "$UPLOAD" --keychain-profile "$NOTARY_PROFILE" --wait
xcrun stapler staple "$TARGET"
echo "✔ 公证 + staple 完成（证书：$IDENTITY）。请把 notarytool 输出写入 app/scripts/RELEASE_EVIDENCE.md"
