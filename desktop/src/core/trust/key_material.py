"""密钥材料面：HMAC keygen + 0600 权限纪律（G4 收尾；plan OPEN-G2 keygen/0600）。

为什么需要：DSSE/registry 都假设「key 材料是安全分发的」，但仓库必须能给出一条**可执行**的
本地纪律：生成即 0600、拒绝覆盖、拒绝符号链接、拒绝组/他人可读（POSIX），读入时再校验一次。
不生成非对称私钥（core 零第三方加密库；ed25519/ecdsa 仍由调用方注入）。

边界：Windows 的 0600 语义来自 ACL，不是 st_mode 位；本模块在非 POSIX 平台只做 best-effort
chmod 并**如实返回 warning**，不把 POSIX 检查冒充为 Windows ACL 强制。
"""
from __future__ import annotations

import os
import secrets
from pathlib import Path

GUIDE = "修复指引："
HEX_RE = set("0123456789abcdef")
KEY_BYTES = 32
MAX_MATERIAL_BYTES = 4096
ALGS = ("hmac-sha256",)


def generate_hmac_key(path: str, alg: str = "hmac-sha256") -> dict:
    """生成 32 字节 HMAC key（hex 落盘，0600，拒绝覆盖/符号链接）。返回 metadata。"""
    if alg not in ALGS:
        raise ValueError(f"alg 越界：{alg!r}（{GUIDE}本模块只生成 hmac-sha256）")
    target = Path(path)
    if target.is_symlink():
        raise ValueError(f"拒绝写入符号链接：{path}（{GUIDE}换真实路径）")
    if target.exists():
        raise ValueError(f"拒绝覆盖既有 key：{path}（{GUIDE}换新路径或先人工处置）")
    target.parent.mkdir(parents=True, exist_ok=True)
    key = secrets.token_bytes(KEY_BYTES)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    mode = 0o600
    fd = os.open(str(target), flags, mode)
    try:
        os.write(fd, key.hex().encode("ascii") + b"\n")
    finally:
        os.close(fd)
    os.chmod(str(target), 0o600)
    return {"path": str(target), "alg": alg, "bytes": KEY_BYTES,
            "permissions": check_permissions(str(target))}


def check_permissions(path: str) -> dict:
    """检查 key 文件权限。POSIX 严格执行；非 POSIX 返回 warning（不冒充 ACL 强制）。"""
    target = Path(path)
    if not target.is_file() or target.is_symlink():
        return {"ok": False, "reason": "KEY-FILE-INVALID"}
    if os.name != "posix":
        return {"ok": True, "warning": "非 POSIX 平台：0600 依赖 ACL，本检查只做 best-effort 记录"}
    mode = os.stat(str(target)).st_mode & 0o777
    if mode & 0o077:
        return {"ok": False, "reason": "KEY-PERMISSIONS",
                "detail": f"mode={oct(mode)} 允许组/他人访问（{GUIDE}chmod 600）"}
    return {"ok": True, "mode": oct(mode)}


def load_hmac_key(path: str) -> bytes:
    """读 HMAC key（hex）：拒绝符号链接/超大文件/坏格式/不安全权限（POSIX）。"""
    target = Path(path)
    if target.is_symlink() or not target.is_file():
        raise ValueError(f"key 文件无效：{path}（{GUIDE}指向普通文件，不要符号链接）")
    size = target.stat().st_size
    if size > MAX_MATERIAL_BYTES:
        raise ValueError(f"key 文件过大（{size} B；{GUIDE}不是 key 材料）")
    text = target.read_text(encoding="ascii", errors="strict").strip()
    if not text or any(ch not in HEX_RE for ch in text):
        raise ValueError(f"key 必须是 hex 文本（{GUIDE}用 scripts/trust_keygen.py 生成）")
    key = bytes.fromhex(text)
    if len(key) != KEY_BYTES:
        raise ValueError(f"HMAC key 必须 {KEY_BYTES} 字节（{GUIDE}重生成）")
    perms = check_permissions(path)
    if not perms.get("ok"):
        raise ValueError(f"{perms.get('reason')}：{perms.get('detail', '')}"
                         f"（{GUIDE}收紧权限后重试）")
    return key
