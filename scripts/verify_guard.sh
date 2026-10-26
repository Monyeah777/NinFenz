#!/usr/bin/env bash
# Process-level exclusion for mutating verify surfaces in one checkout.
#
# `verify.sh` builds and tests ignored package payloads inside the repository.
# Two concurrent runs can observe each other's half-written payload and report
# false failures. This guard serializes runs by repository root using an atomic
# directory and records the owner PID for stale-lock recovery.

VERIFY_GUARD_DIR=""

verify_guard_release() {
  if [ -n "${VERIFY_GUARD_DIR:-}" ] && [ -d "$VERIFY_GUARD_DIR" ]; then
    rm -f "$VERIFY_GUARD_DIR/owner" 2>/dev/null || true
    rmdir "$VERIFY_GUARD_DIR" 2>/dev/null || true
  fi
  VERIFY_GUARD_DIR=""
}

verify_guard_acquire() {
  local root="${1:-}"
  local wait_s="${NF_VERIFY_LOCK_WAIT:-900}"
  local base key lock owner elapsed missing_owner_checks
  local owner_file

  case "$wait_s" in
    ''|*[!0-9]*)
      echo "NF_VERIFY_LOCK_WAIT 必须是非负整数秒（收到：$wait_s）" >&2
      return 2
      ;;
  esac
  [ -n "$root" ] || {
    echo "verify_guard_acquire 需要仓库根路径" >&2
    return 2
  }

  base="$root/.rivet/verify-locks"
  mkdir -p "$base" || {
    echo "无法创建门禁锁目录：$base" >&2
    return 2
  }
  key="$(printf '%s' "$root" | sha256sum | awk '{print $1}')" || {
    echo "无法计算门禁锁键（sha256sum/awk 不可用）" >&2
    return 2
  }
  lock="$base/$key"
  owner_file="$lock/owner"
  elapsed=0
  missing_owner_checks=0

  while :; do
    if mkdir "$lock" 2>/dev/null; then
      printf '%s\n' "$$" >"$owner_file"
      VERIFY_GUARD_DIR="$lock"
      return 0
    fi

    owner=""
    if [ -f "$owner_file" ]; then
      IFS= read -r owner <"$owner_file" || true
      missing_owner_checks=0
    else
      missing_owner_checks=$((missing_owner_checks + 1))
    fi

    if [ -n "$owner" ] && kill -0 "$owner" 2>/dev/null; then
      :
    elif [ -z "$owner" ] && [ "$missing_owner_checks" -lt 5 ]; then
      # The owner writes its PID immediately after mkdir. Do not steal the lock
      # during that tiny window; only recover a genuinely orphaned directory.
      :
    else
      rm -f "$owner_file" 2>/dev/null || true
      rmdir "$lock" 2>/dev/null || true
      missing_owner_checks=0
      continue
    fi

    if [ "$elapsed" -ge "$wait_s" ]; then
      echo "另一个 verify.sh 正在此仓库运行（pid=${owner:-unknown}，等待 ${wait_s}s 超时）。" >&2
      echo "修复指引：等待该门禁结束，或设 NF_VERIFY_LOCK_WAIT=<秒数> 调整等待；不要在并发门禁中删除 payload。" >&2
      return 1
    fi
    sleep 1
    elapsed=$((elapsed + 1))
  done
}

