"""SM3 / SM2 纯 Python 实现（国密，供标识安全防护信息使用）。

设计约束：
- 只用标准库，不依赖 gmssl / openssl；
- 只做本工具需要的：SM3 杂凑、SM2 密钥生成/签名/验签；
- 所有字节串/十六进制转换显式，便于审计。

已知边界：
- SM2 未做 DER 编解码；签名输出为 r||s（各 32 字节，共 128 个十六进制字符），
  与 TC260-PG-202511A 对 SM3withSM2 签名值的长度要求一致；
- 用户标识 ID 默认 "1234567812345678"（GB/T 32918.2 默认值），可通过参数覆盖。
"""

from __future__ import annotations

import secrets
from typing import Tuple

# ---------------------------------------------------------------- SM3

_SM3_IV = (
    0x7380166F, 0x4914B2B9, 0x172442D7, 0xDA8A0600,
    0xA96F30BC, 0x163138AA, 0xE38DEE4D, 0xB0FB0E4E,
)


def _rotl32(x: int, n: int) -> int:
    n &= 31
    return ((x << n) | (x >> (32 - n))) & 0xFFFFFFFF if n else x & 0xFFFFFFFF


def _p0(x: int) -> int:
    return x ^ _rotl32(x, 9) ^ _rotl32(x, 17)


def _p1(x: int) -> int:
    return x ^ _rotl32(x, 15) ^ _rotl32(x, 23)


def _sm3_cf(v, block: bytes):
    w = [int.from_bytes(block[i * 4:i * 4 + 4], "big") for i in range(16)]
    for j in range(16, 68):
        w.append(
            _p1(w[j - 16] ^ w[j - 9] ^ _rotl32(w[j - 3], 15))
            ^ _rotl32(w[j - 13], 7)
            ^ w[j - 6]
        )
    w1 = [w[j] ^ w[j + 4] for j in range(64)]
    a, b, c, d, e, f, g, h = v
    for j in range(64):
        t = 0x79CC4519 if j < 16 else 0x7A879D8A
        ss1 = _rotl32((_rotl32(a, 12) + e + _rotl32(t, j)) & 0xFFFFFFFF, 7)
        ss2 = ss1 ^ _rotl32(a, 12)
        if j < 16:
            ff = a ^ b ^ c
            gg = e ^ f ^ g
        else:
            ff = (a & b) | (a & c) | (b & c)
            gg = (e & f) | ((~e & 0xFFFFFFFF) & g)
        tt1 = (ff + d + ss2 + w1[j]) & 0xFFFFFFFF
        tt2 = (gg + h + ss1 + w[j]) & 0xFFFFFFFF
        d = c
        c = _rotl32(b, 9)
        b = a
        a = tt1
        h = g
        g = _rotl32(f, 19)
        f = e
        e = _p0(tt2)
    return [(x ^ y) & 0xFFFFFFFF for x, y in zip(v, (a, b, c, d, e, f, g, h))]


def sm3(data: bytes) -> bytes:
    """SM3 杂凑，返回 32 字节。"""
    length = len(data)
    data = data + b"\x80" + b"\x00" * ((56 - (length + 1) % 64) % 64)
    data += (length * 8).to_bytes(8, "big")
    v = list(_SM3_IV)
    for i in range(0, len(data), 64):
        v = _sm3_cf(v, data[i:i + 64])
    return b"".join(x.to_bytes(4, "big") for x in v)


def sm3_hex(data: bytes) -> str:
    return sm3(data).hex()


# ---------------------------------------------------------------- SM2

_P = 0xFFFFFFFEFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF00000000FFFFFFFFFFFFFFFF
_A = 0xFFFFFFFEFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF00000000FFFFFFFFFFFFFFFC
_B = 0x28E9FA9E9D9F5E344D5A9E4BCF6509A7F39789F515AB8F92DDBCBD414D940E93
_N = 0xFFFFFFFEFFFFFFFFFFFFFFFFFFFFFFFF7203DF6B21C6052B53BBF40939D54123
_GX = 0x32C4AE2C1F1981195F9904466A39C9948FE30BBFF2660BE1715A4589334C74C7
_GY = 0xBC3736A2F4F6779C59BDCEE36B692153D0A9877CC62A474002DF32E52139F0A0

DEFAULT_UID = b"1234567812345678"


def _inv(x: int, m: int = _P) -> int:
    return pow(x, m - 2, m)


def _add(p1, p2):
    if p1 is None:
        return p2
    if p2 is None:
        return p1
    x1, y1 = p1
    x2, y2 = p2
    if x1 == x2:
        if (y1 + y2) % _P == 0:
            return None
        lam = (3 * x1 * x1 + _A) * _inv(2 * y1) % _P
    else:
        lam = (y2 - y1) * _inv(x2 - x1) % _P
    x3 = (lam * lam - x1 - x2) % _P
    y3 = (lam * (x1 - x3) - y1) % _P
    return (x3, y3)


def _mul(k: int, point):
    k %= _N
    r = None
    while k:
        if k & 1:
            r = _add(r, point)
        point = _add(point, point)
        k >>= 1
    return r


_G = (_GX, _GY)


def _za(pub_xy, uid: bytes = DEFAULT_UID) -> bytes:
    entl = (len(uid) * 8).to_bytes(2, "big")
    data = (
        entl + uid
        + _A.to_bytes(32, "big") + _B.to_bytes(32, "big")
        + _GX.to_bytes(32, "big") + _GY.to_bytes(32, "big")
        + pub_xy[0].to_bytes(32, "big") + pub_xy[1].to_bytes(32, "big")
    )
    return sm3(data)


def _e(msg: bytes, pub_xy, uid: bytes = DEFAULT_UID) -> int:
    return int.from_bytes(sm3(_za(pub_xy, uid) + msg), "big")


def sm2_keygen() -> dict:
    d = secrets.randbelow(_N - 1) + 1
    pub = _mul(d, _G)
    return {
        "private": f"{d:064x}",
        "public": f"{pub[0]:064x}{pub[1]:064x}",
    }


def sm2_public_from_private(priv_hex: str) -> str:
    d = int(priv_hex, 16)
    if not 1 <= d < _N:
        raise ValueError("私钥不在 [1, n-1]")
    pub = _mul(d, _G)
    return f"{pub[0]:064x}{pub[1]:064x}"


def sm2_sign(priv_hex: str, msg: bytes, uid: bytes = DEFAULT_UID,
             k_hex: str | None = None) -> str:
    """返回 r||s 的 128 位十六进制字符串。

    k_hex 仅用于标准向量复算（确定性签名）；生产环境不要传。
    """
    d = int(priv_hex, 16)
    pub = _mul(d, _G)
    e = _e(msg, pub, uid)
    fixed_k = int(k_hex, 16) if k_hex else None
    while True:
        k = fixed_k if fixed_k else secrets.randbelow(_N - 1) + 1
        kg = _mul(k, _G)
        r = (e + kg[0]) % _N
        if r == 0 or r + k == _N:
            continue
        s = (_inv(1 + d, _N) * (k - r * d)) % _N
        if s == 0:
            continue
        return f"{r:064x}{s:064x}"


def sm2_verify(pub_hex: str, msg: bytes, sig_hex: str, uid: bytes = DEFAULT_UID) -> bool:
    if len(pub_hex) != 128 or len(sig_hex) != 128:
        return False
    try:
        px = int(pub_hex[:64], 16)
        py = int(pub_hex[64:], 16)
        r = int(sig_hex[:64], 16)
        s = int(sig_hex[64:], 16)
    except ValueError:
        return False
    if not (1 <= r < _N and 1 <= s < _N):
        return False
    e = _e(msg, (px, py), uid)
    t = (r + s) % _N
    if t == 0:
        return False
    pt = _add(_mul(s, _G), _mul(t, (px, py)))
    if pt is None:
        return False
    return (e + pt[0]) % _N == r


# ---------------------------------------------------------------- 自检

SM3_VEC = {
    b"abc": "66c7f0f462eeedd9d1f2d46bdc10e4e24167c4875cf2f7a2297da02b8f4ba8e0",
    b"abcd" * 16: "debe9ff92275b8a138604889c18e5a4d6fdb70e5387e5765293dcba39c0c5732",
}


def selfcheck() -> list:
    """返回 [(名称, ok, detail)]，供 --selfcheck 使用。"""
    out = []
    for msg, want in SM3_VEC.items():
        got = sm3_hex(msg)
        out.append((f"SM3({msg[:8]!r}…)", got == want, got))
    keys = sm2_keygen()
    sig = sm2_sign(keys["private"], b"nf-labelcheck selfcheck")
    ok = sm2_verify(keys["public"], b"nf-labelcheck selfcheck", sig)
    bad = sm2_verify(keys["public"], b"nf-labelcheck selfcheck!", sig)
    out.append(("SM2 签名/验签往返", ok, keys["public"][:16] + "…"))
    out.append(("SM2 篡改消息必须失败", not bad, ""))
    return out


if __name__ == "__main__":
    import sys
    ok = True
    for name, good, detail in selfcheck():
        print(("PASS" if good else "FAIL"), name, detail)
        ok &= good
    sys.exit(0 if ok else 1)
