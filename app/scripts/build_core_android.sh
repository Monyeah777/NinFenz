#!/usr/bin/env bash
# 交叉编译 NF APP 共享核心（app/core）为 Android .so：
#   libnf_app_core.so -> app/android/app/src/main/jniLibs/<abi>/
# ABI：arm64-v8a（aarch64-linux-android）、x86_64（x86_64-linux-android）
# 用法：bash app/scripts/build_core_android.sh [--clean]
# 纪律：NDK / rust target / cargo 任一缺失 -> exit 4 + 安装指引；不假装有 .so，也不写入假产物。
set -eo pipefail

ROOT="$(cd "$(dirname "$BASH_SOURCE")/../.." && pwd)"
CORE_DIR="$ROOT/app/core"
JNI_DIR="$ROOT/app/android/app/src/main/jniLibs"
NDK_API=26
MIN_PAGE_ALIGN="0x4000"

fail_env() {
  echo "NF-E-005（环境缺失）：$1" >&2
  echo "修复指引：$2" >&2
  exit 4
}

CLEAN=0
if [ "$#" -gt 0 ] && [ "$1" = "--clean" ]; then
  CLEAN=1
fi

command -v cargo >/dev/null 2>&1 || fail_env "cargo 不在 PATH" "安装 Rust 工具链（rustup）：https://rustup.rs"
command -v rustup >/dev/null 2>&1 || fail_env "rustup 不在 PATH" "安装 rustup（添加 Android target 需要它）"
[ -f "$CORE_DIR/Cargo.toml" ] || fail_env "缺 $CORE_DIR/Cargo.toml" "确认 app/core 已在仓库中"

# ---- NDK 探测：ANDROID_NDK_HOME > ANDROID_NDK_ROOT > \$ANDROID_HOME/ndk/<latest> ----
NDK="$ANDROID_NDK_HOME"
if [ -z "$NDK" ]; then
  NDK="$ANDROID_NDK_ROOT"
fi
if [ -z "$NDK" ]; then
  for BASE in "$ANDROID_HOME" "$ANDROID_SDK_ROOT" "/d/tmp/app-toolchain/android-sdk"; do
    if [ -n "$BASE" ] && [ -d "$BASE/ndk" ]; then
      CANDIDATE="$(ls -d "$BASE"/ndk/* 2>/dev/null | sort -V | tail -n 1)"
      if [ -n "$CANDIDATE" ]; then
        NDK="$CANDIDATE"
        break
      fi
    fi
  done
fi
if [ -n "$NDK" ] && command -v cygpath >/dev/null 2>&1; then
  NDK="$(cygpath -m "$NDK")"
fi
if [ -z "$NDK" ] || [ ! -d "$NDK" ]; then
  fail_env "未找到 Android NDK" "sdkmanager --sdk_root=\$ANDROID_HOME 'ndk;27.0.12077973'；或设 ANDROID_NDK_HOME 指向 NDK 根目录"
fi

HOST_TAG="$(ls "$NDK/toolchains/llvm/prebuilt" 2>/dev/null | head -n 1)"
if [ -z "$HOST_TAG" ]; then
  fail_env "NDK 缺 llvm prebuilt 工具链" "重装 NDK（sdkmanager 'ndk;27.0.12077973'）"
fi
BIN="$NDK/toolchains/llvm/prebuilt/$HOST_TAG/bin"
SYSROOT="$NDK/toolchains/llvm/prebuilt/$HOST_TAG/sysroot"
[ -d "$SYSROOT" ] || fail_env "NDK 缺 sysroot：$SYSROOT" "重装 NDK"

INSTALLED_TARGETS="$(rustup target list --installed)"
for TRIPLE in aarch64-linux-android x86_64-linux-android; do
  echo "$INSTALLED_TARGETS" | grep -qx "$TRIPLE" || fail_env "rust target 未安装：$TRIPLE" "rustup target add $TRIPLE"
done

if [ "$CLEAN" = "1" ]; then
  echo "[nf-core-android] 清理旧 .so"
  rm -f "$JNI_DIR/arm64-v8a/libnf_app_core.so" "$JNI_DIR/x86_64/libnf_app_core.so"
fi

mkdir -p "$JNI_DIR/arm64-v8a" "$JNI_DIR/x86_64"

build_one() {
  ABI="$1"
  TRIPLE="$2"
  UPPER="$(echo "$TRIPLE" | tr 'a-z-' 'A-Z_')"
  echo "[nf-core-android] 构建 $TRIPLE -> $ABI（API $NDK_API）"
  if [ -x "$BIN/clang.exe" ]; then
    # Windows 原生 rustc 不能直接执行 NDK 的 .cmd 包装器：用 clang.exe + 显式 target/sysroot
    LINKER="$BIN/clang.exe"
    TARGET_FLAGS="-C link-arg=--target=$TRIPLE$NDK_API -C link-arg=--sysroot=$SYSROOT"
  else
    LINKER="$BIN/$TRIPLE$NDK_API-clang"
    TARGET_FLAGS=""
    [ -x "$LINKER" ] || fail_env "缺 NDK clang：$LINKER" "确认 NDK 完整（llvm prebuilt）"
  fi
  export "CARGO_TARGET_${UPPER}_LINKER=$LINKER"
  export "CARGO_TARGET_${UPPER}_RUSTFLAGS=$TARGET_FLAGS -C link-arg=-Wl,-z,max-page-size=16384"
  ( cd "$CORE_DIR" && cargo build --release --target "$TRIPLE" )
  SRC="$CORE_DIR/target/$TRIPLE/release/libnf_app_core.so"
  [ -f "$SRC" ] || fail_env "构建产物缺失：$SRC" "重跑脚本并检查 cargo 输出（可能缺链接器/目标）"
  DST="$JNI_DIR/$ABI/libnf_app_core.so"
  cp "$SRC" "$DST"
  SIZE_BYTES="$(wc -c < "$DST" | tr -d ' ')"
  echo "[nf-core-android] 已复制：$DST（$SIZE_BYTES bytes）"
  READELF="$BIN/llvm-readelf.exe"
  if [ ! -x "$READELF" ]; then
    READELF="$BIN/llvm-readelf"
  fi
  if [ -x "$READELF" ]; then
    ALIGNS="$("$READELF" -l "$DST" | awk '/LOAD/{print $NF}' | sort -u | tr '\n' ' ')"
    echo "[nf-core-android] LOAD align：$ALIGNS（16KB page 需含 $MIN_PAGE_ALIGN）"
    case "$ALIGNS" in
      *"$MIN_PAGE_ALIGN"*) : ;;
      *) echo "[nf-core-android] 警告：未检测到 16KB 对齐（Android 15+ 的 16KB 设备可能拒绝加载）" >&2 ;;
    esac
  fi
}

build_one arm64-v8a aarch64-linux-android
build_one x86_64 x86_64-linux-android

echo "[nf-core-android] 完成：libnf_app_core.so 已就位（arm64-v8a + x86_64）"
echo "[nf-core-android] 重新构建 APK：cd app/android && ./gradlew :app:assembleDebug"
