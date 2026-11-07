"""Ed25519（RFC 8032）纯标准库实现——为了让跨组织吊销不再共享对称密钥。

为什么需要（2026-11-07）：吊销件此前只有 hmac-sha256，而 hmac 是对称的——把验证能力
交给别人的同时就把伪造能力也交出去了，「谁吊销的」在跨组织场景里不成立。Ed25519 是公开
密钥签名：发布方持私钥签名、任何持公钥的人都能验证，且签名是确定性（同 key+msg 永远同字节），
便于进向量集。

只实现 RFC 8032 的纯 Ed25519（不实现预哈希 / context / X25519）：
- public_key(seed)：32 字节种子 → 32 字节公钥；
- sign(seed, msg)：确定性签名（64 字节）；
- verify(pub, msg, sig)：严格验证（S < L、A/R 解压成功、点等式成立），任何形状/数值异常
  一律 False（绝不 fail-open）。

判据见 desktop/tests/test_ed25519.py：RFC 8032 黄金向量 + 与 cryptography 库的交叉验证
（该库不在场时跳过，不冒充已验）+ 篡改必拒 + 形状边界。
"""
from __future__ import annotations

import hashlib

P = 2 ** 255 - 19
L = 2 ** 252 + 27742317777372353535851937790883648493
_D = -121665 * pow(121666, P - 2, P) % P
_SQRT_M1 = pow(2, (P - 1) // 4, P)


def _inv(x: int) -> int:
    return pow(x, P - 2, P)


# ---------------------------------------------------------------- 群运算（扩展坐标）
def _add(p1, p2):
    x1, y1, z1, t1 = p1
    x2, y2, z2, t2 = p2
    a = (y1 - x1) * (y2 - x2) % P
    b = (y1 + x1) * (y2 + x2) % P
    c = 2 * t1 * t2 * _D % P
    d = 2 * z1 * z2 % P
    e = b - a
    f = d - c
    g = d + c
    h = b + a
    return (e * f % P, g * h % P, f * g % P, e * h % P)


def _double(p1):
    x1, y1, z1, _t1 = p1
    a = x1 * x1 % P
    b = y1 * y1 % P
    c = 2 * z1 * z1 % P
    d = -a % P
    e = ((x1 + y1) * (x1 + y1) - a - b) % P
    g = d + b
    f = g - c
    h = d - b
    return (e * f % P, g * h % P, f * g % P, e * h % P)


_BY = 4 * _inv(5) % P
_BX = None


def _recover_x(y: int, sign: int):
    """y → x（Edwards 曲线）；无解返回 None。"""
    if y >= P:
        return None
    x2 = (y * y - 1) * _inv(_D * y * y + 1) % P
    if x2 == 0:
        return None if sign else 0
    x = pow(x2, (P + 3) // 8, P)
    if (x * x - x2) % P != 0:
        x = x * _SQRT_M1 % P
    if (x * x - x2) % P != 0:
        return None
    if x & 1 != sign:
        x = P - x
    return x


def _base_point():
    global _BX
    if _BX is None:
        _BX = _recover_x(_BY, 0)
    return (_BX, _BY, 1, _BX * _BY % P)


def _mul(scalar: int, point):
    """标量乘（双倍-加）。"""
    result = (0, 1, 1, 0)
    addend = point
    while scalar > 0:
        if scalar & 1:
            result = _add(result, addend)
        addend = _double(addend)
        scalar >>= 1
    return result


def _compress(point) -> bytes:
    x, y, z, _t = point
    zinv = _inv(z)
    x, y = x * zinv % P, y * zinv % P
    return int.to_bytes(y | ((x & 1) << 255), 32, "little")


def _decompress(raw: bytes):
    if len(raw) != 32:
        return None
    y = int.from_bytes(raw, "little")
    sign = (y >> 255) & 1
    y &= (1 << 255) - 1
    x = _recover_x(y, sign)
    if x is None:
        return None
    return (x, y, 1, x * y % P)


def _sha512_int(*parts: bytes) -> int:
    h = hashlib.sha512()
    for part in parts:
        h.update(part)
    return int.from_bytes(h.digest(), "little")


def _clamp(h: bytes) -> int:
    a = int.from_bytes(h[:32], "little")
    a &= (1 << 254) - 8
    a |= 1 << 254
    return a


# ---------------------------------------------------------------- 公开 API
def public_key(seed: bytes) -> bytes:
    """32 字节种子 → 32 字节公钥（RFC 8032 §5.1.5）。"""
    if len(seed) != 32:
        raise ValueError("Ed25519 种子必须是 32 字节（修复指引：用 32 字节随机种子）")
    h = hashlib.sha512(seed).digest()
    return _compress(_mul(_clamp(h), _base_point()))


def sign(seed: bytes, msg: bytes) -> bytes:
    """确定性签名：同种子 + 同消息 → 同 64 字节（便于进向量集）。"""
    pub = public_key(seed)
    h = hashlib.sha512(seed).digest()
    a = _clamp(h)
    prefix = h[32:]
    r = _sha512_int(prefix, msg) % L
    big_r = _compress(_mul(r, _base_point()))
    k = _sha512_int(big_r, pub, msg) % L
    s = (r + k * a) % L
    return big_r + int.to_bytes(s, 32, "little")


def verify(pub: bytes, msg: bytes, sig: bytes) -> bool:
    """严格验证：任何形状/数值异常一律 False（绝不 fail-open）。"""
    if len(pub) != 32 or len(sig) != 64:
        return False
    a_point = _decompress(pub)
    if a_point is None:
        return False
    big_r = _decompress(sig[:32])
    if big_r is None:
        return False
    s = int.from_bytes(sig[32:], "little")
    if s >= L:
        return False
    k = _sha512_int(sig[:32], pub, msg) % L
    check = _add(_mul(s, _base_point()), _mul(L - (k % L), a_point))
    return _compress(check) == sig[:32]
