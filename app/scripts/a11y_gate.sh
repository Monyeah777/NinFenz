#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
if [ -f /d/tmp/app-toolchain/env.sh ]; then
  # shellcheck disable=SC1091
  source /d/tmp/app-toolchain/env.sh >/dev/null 2>&1
fi
cd "$ROOT/app/android"
./gradlew :app:testDebugUnitTest --tests dev.ninfenz.mobile.ui.A11yComposeTest --console=plain
echo "[a11y] PASS"
