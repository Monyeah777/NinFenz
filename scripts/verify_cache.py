#!/usr/bin/env python3
"""门禁判定缓存：输入摘要 → 判定摘要（**只加速，不替代判定**）。

为什么（2026-10-18 实测）：check12 占全量门禁 95%；分片并行后仍有数分钟量级，而开发日常里
"树没变又跑一遍闸门"是纯浪费。Bazel/Nix 的口径是**输入内容寻址**：判定是输入的纯函数，
输入没变就不该重算——但"输入"必须被**完整**枚举，否则缓存就是假绿装置。

key 覆盖（逐项都有理由，缺一项都可能假绿）：
- `git rev-parse HEAD`：提交级身份；
- `git stash create`：**tracked 改动的内容寻址提交**（含 index；不改工作树、不产生 stash 条目）；
- 未跟踪件：`git ls-files -o --exclude-standard` 的路径 + 内容 sha256
  （新脚本/新数据件同样进判据面）；
- 门禁档位（full/quick）：两档跑的测试集不同，必须分开；
- 运行时：python 版本 + 平台（判据里有真跑进程与编码相关断言）；
- `verify.sh` / `scripts/verify_tests.py` / 本文件的内容 sha256
  （它们虽是 tracked，显式再算一次是防「绕过 git 改文件」）。

纪律：
- **只缓存 rc=0**：红是瞬态（环境未就绪、外部会话改了树），必须重跑；
- 缓存文件带 `key` 与 `head/mode` 自证；读取时逐项核对，不符即未命中（不做"差不多就用"）；
- 缓存放在 `NF_HOME`（用户态），不入仓、不进 payload；条目极小（每份几百字节），
  需要清空时直接删目录即可（**本脚本刻意不含任何删除面**：删除 sink 会扩大 purity 面，
  并与 Rust 快线的允许表产生口径分叉——2026-10-18 实测修复）。

用法（verify.sh 调用）：
    python scripts/verify_cache.py --mode full --key                  # 打印 key
    python scripts/verify_cache.py --mode full --key <K> --get         # 命中→打印摘要并 exit 0
    python scripts/verify_cache.py --mode full --key <K> --put --pass 76 --warn 1
    python scripts/verify_cache.py --clear
"""
import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "desktop" / "src"))
from core import atomic_write, json_doc  # noqa: E402 - 先用后置（scripts 面统一写法）

CACHE_VERSION = 1


def _run(argv: list) -> str:
    try:
        proc = subprocess.run(argv, cwd=str(ROOT), capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=120)
    except (OSError, subprocess.SubprocessError):
        return ""
    return (proc.stdout or "").strip() if proc.returncode == 0 else ""


def _sha_file(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return ""


def _cache_root() -> Path:
    home = os.environ.get("NARRATIVE_FORGE_HOME") or str(Path.home() / ".NinFenz")
    return Path(home) / "verify_cache"


def compute_key(mode: str) -> str:
    """输入摘要（16 进制 64 位）。任何一项取不到就返回空 → 调用方视为"不可缓存"。"""
    head = _run(["git", "rev-parse", "HEAD"])
    if not head:
        return ""
    # `git stash create` 的 **commit** 哈希含作者/提交时间戳 ⇒ 同一棵树每次调用都不同，
    # 拿它当缓存 key 会导致**永不命中**（2026-10-27 实测：连续两次 key 不同）。
    # 正确口径是取它指向的 **tree**（再取 index 侧 tree），tree 是纯内容寻址、稳定可复现。
    stash = _run(["git", "stash", "create"])
    dirty = ""
    if stash:
        wt = _run(["git", "rev-parse", "%s^{tree}" % stash])
        ix = _run(["git", "rev-parse", "%s^2^{tree}" % stash])
        dirty = "wt:%s|ix:%s" % (wt, ix)
    untracked = _run(["git", "ls-files", "-o", "--exclude-standard"]).splitlines()
    untracked_hashes = sorted(
        "%s=%s" % (rel, _sha_file(ROOT / rel)) for rel in untracked if rel)
    gate = {
        "verify.sh": _sha_file(ROOT / "verify.sh"),
        "verify_tests.py": _sha_file(ROOT / "scripts" / "verify_tests.py"),
        "verify_cache.py": _sha_file(ROOT / "scripts" / "verify_cache.py"),
    }
    payload = {
        "v": CACHE_VERSION,
        "mode": mode,
        "head": head,
        "dirty": dirty,
        "untracked": untracked_hashes,
        "gate": gate,
        "py": platform.python_version(),
        "plat": sys.platform,
    }
    blob = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _path_for(key: str) -> Path:
    return _cache_root() / (key[:2]) / (key + ".json")


def cmd_get(key: str, mode: str) -> int:
    path = _path_for(key)
    try:
        doc = json_doc.load(path, dict, what="门禁判定缓存件")
    except ValueError:
        # 缓存件坏/缺 → 视为未命中（重算是安全方向；缓存永不因坏件让门禁绿）。
        return 1
    if doc.get("key") != key or doc.get("mode") != mode or doc.get("v") != CACHE_VERSION:
        return 1
    print("  缓存命中（输入未变：HEAD %s · 档位 %s · %s）"
          % (str(doc.get("head", ""))[:8], mode, doc.get("at", "")))
    print("  上次判定：PASS=%s WARN=%s FAIL=0（未重跑；--no-cache 或 NF_VERIFY_CACHE=0 可强制重算）"
          % (doc.get("pass"), doc.get("warn")))
    return 0


def cmd_put(key: str, mode: str, n_pass: int, n_warn: int) -> int:
    path = _path_for(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    doc = {"v": CACHE_VERSION, "key": key, "mode": mode,
           "head": _run(["git", "rev-parse", "HEAD"]),
           "at": time.strftime("%Y-%m-%d %H:%M:%S"),
           "pass": n_pass, "warn": n_warn}
    # 走 core.atomic_write（同目录临时件 + os.replace 的唯一出处）：脚本面不允许裸写。
    atomic_write.write_text(path, json.dumps(doc, ensure_ascii=False, sort_keys=True))
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="门禁判定缓存（输入内容寻址）")
    ap.add_argument("--mode", choices=("full", "quick", "checks"), default="full")
    ap.add_argument("--key", nargs="?", const="", default=None,
                    help="给定 key（缺省=现算）；--put 时必给")
    ap.add_argument("--get", action="store_true")
    ap.add_argument("--put", action="store_true")
    ap.add_argument("--pass", dest="n_pass", type=int, default=0)
    ap.add_argument("--warn", dest="n_warn", type=int, default=0)
    a = ap.parse_args(argv)
    key = a.key if a.key else compute_key(a.mode)
    if not key:
        return 2
    if a.put:
        if not a.key:
            return 2
        return cmd_put(key, a.mode, a.n_pass, a.n_warn)
    if a.get:
        return cmd_get(key, a.mode) if a.key else 2
    print(key)
    return 0


if __name__ == "__main__":
    for _stream in (sys.stdout, sys.stderr):
        if hasattr(_stream, "reconfigure"):
            _stream.reconfigure(encoding="utf-8")
    raise SystemExit(main())
