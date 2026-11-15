#!/usr/bin/env bash
# 构建/测试 NF APP 共享核心（app/core）。
# 用法：bash app/scripts/build_core.sh [--release] [--test]
# 纪律：不取网（依赖由 Cargo.lock 钉死；离线机请先 cargo fetch）；构建产物落 app/core/target/（不入库）。
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT/app/core"
if [ ! -f Cargo.toml ]; then
  echo "缺 app/core/Cargo.toml（修复指引：确认共享核心入仓）" >&2
  exit 2
fi
if ! command -v cargo >/dev/null 2>&1; then
  echo "cargo 不在 PATH（修复指引：安装 Rust 工具链）" >&2
  exit 4
fi
MODE="debug"
for arg in "$@"; do
  case "$arg" in
    --release) MODE="release" ;;
    --test) cargo test --quiet ;;
    *) echo "未知参数：$arg" >&2; exit 2 ;;
  esac
done
if [ "$MODE" = "release" ]; then
  cargo build --release
  echo "✔ 共享核心：$ROOT/app/core/target/release/nf-app-core"
else
  cargo build
  echo "✔ 共享核心：$ROOT/app/core/target/debug/nf-app-core"
fi
