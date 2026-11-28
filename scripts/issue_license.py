#!/usr/bin/env python3
"""NF Pro 离线授权码签发（内部工具，纯标准库）。

码格式：NF1.<base64url(payload)>.<base64url(ed25519_sig)>
payload（canonical JSON：sort_keys + 无空格 + UTF-8）：
  {"batch":"earlybird-2026-12","edition":"pro","issued_at":"2026-12-01",
   "major":0,"order":"AF20261201-0001","product":"nf-mobile","v":1}

纪律：
- 私钥只在本机（默认 ~/.nf-license/ed25519.key，0600），绝不入库/上传；
- 签发结果写 CSV（order,code,edition,major,issued_at,batch,status）；
- 公钥需 pin 进 app/core/src/license_entitlement.rs 的 PINNED_PUBLIC_KEY_HEX。

用法：
  python scripts/issue_license.py --gen-key
  python scripts/issue_license.py --show-pubkey
  python scripts/issue_license.py --issue --count 100 --order-prefix AF20261201 \
      --batch earlybird-2026-12 --issued-at 2026-12-01 --out codes.csv
  python scripts/issue_license.py --verify --code NF1.xxx.yyy --pubkey <hex>
  python scripts/issue_license.py --self-test
"""

from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import json
import os
import sys
import time

# ---------------------------------------------------------------- Ed25519（RFC 8032 参考实现）

Q = 2**255 - 19
L = 2**252 + 27742317777372353535851937790883648493


def _inv(x: int) -> int:
    return pow(x, Q - 2, Q)


_D = -121665 * _inv(121666) % Q
_I = pow(2, (Q - 1) // 4, Q)


def _xrecover(y: int) -> int:
    xx = (y * y - 1) * _inv(_D * y * y + 1)
    x = pow(xx, (Q + 3) // 8, Q)
    if (x * x - xx) % Q != 0:
        x = (x * _I) % Q
    if x % 2 != 0:
        x = Q - x
    return x


_BY = 4 * _inv(5) % Q
_BX = _xrecover(_BY)
_B = [_BX % Q, _BY % Q, 1, (_BX * _BY) % Q]


def _edwards_add(p: list[int], q: list[int]) -> list[int]:
    x1, y1, z1, t1 = p
    x2, y2, z2, t2 = q
    a = (y1 - x1) * (y2 - x2) % Q
    b = (y1 + x1) * (y2 + x2) % Q
    c = t1 * 2 * _D * t2 % Q
    dd = z1 * 2 * z2 % Q
    e, f, g, h = b - a, dd - c, dd + c, b + a
    return [e * f % Q, g * h % Q, f * g % Q, e * h % Q]


def _scalarmult(p: list[int], e: int) -> list[int]:
    if e == 0:
        return [0, 1, 1, 0]
    q = _scalarmult(p, e // 2)
    q = _edwards_add(q, q)
    if e & 1:
        q = _edwards_add(q, p)
    return q


def _encodeint(y: int) -> bytes:
    return y.to_bytes(32, "little")


def _encodepoint(p: list[int]) -> bytes:
    x, y, z, _t = p
    zi = _inv(z)
    x, y = x * zi % Q, y * zi % Q
    bits = [(y >> i) & 1 for i in range(255)] + [x & 1]
    out = bytearray(32)
    for i in range(256):
        if bits[i]:
            out[i // 8] |= 1 << (i % 8)
    return bytes(out)


def _decodeint(s: bytes) -> int:
    return int.from_bytes(s, "little")


def _decodepoint(s: bytes) -> list[int]:
    if len(s) != 32:
        raise ValueError("point 长度必须是 32")
    y = int.from_bytes(s, "little") & ((1 << 255) - 1)
    x = _xrecover(y)
    if (x & 1) != (s[31] >> 7) & 1:
        x = Q - x
    p = [x, y, 1, x * y % Q]
    if not _isedwards(p):
        raise ValueError("非法点（请检查签名 R 段与公钥是否正确）")
    return p


def _isedwards(p: list[int]) -> bool:
    x, y, z, _t = p
    if z % Q == 0:
        return False
    zi = _inv(z)
    x, y = x * zi % Q, y * zi % Q
    return (y * y - x * x - 1 - _D * x * x * y * y) % Q == 0


def _expand(seed: bytes) -> tuple[int, bytes]:
    h = hashlib.sha512(seed).digest()
    a = int.from_bytes(h[:32], "little")
    a &= (1 << 254) - 8
    a |= 1 << 254
    return a, h[32:]


def public_key(seed: bytes) -> bytes:
    a, _prefix = _expand(seed)
    return _encodepoint(_scalarmult(_B, a))


def sign(seed: bytes, msg: bytes) -> bytes:
    a, prefix = _expand(seed)
    pub = _encodepoint(_scalarmult(_B, a))
    r = int.from_bytes(hashlib.sha512(prefix + msg).digest(), "little") % L
    rs = _encodepoint(_scalarmult(_B, r))
    k = int.from_bytes(hashlib.sha512(rs + pub + msg).digest(), "little") % L
    s = (r + k * a) % L
    return rs + _encodeint(s)


def verify(pub: bytes, msg: bytes, sig: bytes) -> bool:
    if len(pub) != 32 or len(sig) != 64:
        return False
    try:
        a = _decodepoint(pub)
        r = _decodepoint(sig[:32])
    except ValueError:
        return False
    s = _decodeint(sig[32:])
    if s >= L:
        return False
    k = int.from_bytes(hashlib.sha512(sig[:32] + pub + msg).digest(), "little") % L
    return _encodepoint(_edwards_add(_scalarmult(_B, s), _scalarmult(a, (L - k) % L))) == sig[:32]


# ---------------------------------------------------------------- 码格式

PREFIX = "NF1"
DEFAULT_KEY = os.path.join(os.path.expanduser("~"), ".nf-license", "ed25519.key")
EDITIONS = ("pro", "studio", "ccos")


def b64u(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def unb64u(text: str) -> bytes:
    pad = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode((text + pad).encode("ascii"))


def canonical_json(obj: dict) -> bytes:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def make_code(seed: bytes, payload: dict) -> str:
    raw = canonical_json(payload)
    return "%s.%s.%s" % (PREFIX, b64u(raw), b64u(sign(seed, raw)))


def parse_code(code: str, pub: bytes) -> dict:
    parts = code.strip().split(".")
    if len(parts) != 3 or parts[0] != PREFIX:
        raise ValueError("码格式非法（应为 NF1.<payload>.<sig>）")
    raw = unb64u(parts[1])
    sig = unb64u(parts[2])
    if not verify(pub, raw, sig):
        raise ValueError("验签失败（码被改动或使用了别的密钥）")
    payload = json.loads(raw.decode("utf-8"))
    if payload.get("v") != 1 or payload.get("product") != "nf-mobile":
        raise ValueError("载荷不是 nf-mobile/v1（请确认码由本仓库 issue_license.py 签发）")
    if payload.get("edition") not in EDITIONS:
        raise ValueError("edition 非法（应为 pro / studio / ccos）")
    return payload


def load_seed(path: str) -> bytes:
    text = open(path, "r", encoding="ascii").read().strip()
    raw = bytes.fromhex(text)
    if len(raw) != 32 or not any(raw):
        raise ValueError("私钥文件必须是 32 字节非全零 hex")
    return raw


def save_seed(path: str, seed: bytes) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    if os.path.exists(path):
        raise ValueError("私钥文件已存在，拒绝覆盖：%s" % path)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="ascii") as fh:
        fh.write(seed.hex() + "\n")
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


# ---------------------------------------------------------------- 命令

RFC_VECTOR = {
    "seed": "9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60",
    "pub": "d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a",
    "sig": "e5564300c360ac729086e2cc806e828a84877f1eb8e5d974d873e06522490155"
           "5fb8821590a33bacc61e39701cf9b46bd25bf5f0595bbe24655141438e7a100b",
}


def self_test() -> int:
    seed = bytes.fromhex(RFC_VECTOR["seed"])
    pub = public_key(seed)
    sig = sign(seed, b"")
    assert pub.hex() == RFC_VECTOR["pub"], "RFC8032 公钥向量不符"
    assert sig.hex() == RFC_VECTOR["sig"], "RFC8032 签名向量不符"
    payload = {"v": 1, "product": "nf-mobile", "edition": "pro", "major": 0,
               "order": "SELFTEST-0001", "issued_at": "2026-12-01", "batch": "selftest"}
    code = make_code(seed, payload)
    assert parse_code(code, pub) == payload, "往返失败"
    tampered = code[:-4] + ("AAAA" if not code.endswith("AAAA") else "BBBB")
    try:
        parse_code(tampered, pub)
    except ValueError:
        pass
    else:
        raise AssertionError("篡改码未被拒绝（请检查 verify 实现与自测向量）")
    print("self-test ok：RFC8032 向量 + 往返 + 篡改拒绝")
    return 0


def cmd_gen_key(args: argparse.Namespace) -> int:
    seed = os.urandom(32)
    save_seed(args.key, seed)
    print("私钥已写入：%s（权限 600，请离线备份 2 份，绝不入库）" % args.key)
    print("公钥（pin 进 app/core/src/license_entitlement.rs 的 PINNED_PUBLIC_KEY_HEX）：")
    print(public_key(seed).hex())
    return 0


def cmd_show_pubkey(args: argparse.Namespace) -> int:
    print(public_key(load_seed(args.key)).hex())
    return 0


def cmd_issue(args: argparse.Namespace) -> int:
    seed = load_seed(args.key)
    pub = public_key(seed)
    rows = []
    for i in range(args.count):
        seq = args.start + i
        order = "%s-%04d" % (args.order_prefix, seq)
        payload = {
            "v": 1,
            "product": "nf-mobile",
            "edition": args.edition,
            "major": args.major,
            "order": order,
            "issued_at": args.issued_at,
            "batch": args.batch,
        }
        code = make_code(seed, payload)
        assert parse_code(code, pub)["order"] == order
        rows.append([order, code, args.edition, str(args.major), args.issued_at, args.batch, "issued"])
    if args.out == "-":
        writer = csv.writer(sys.stdout, lineterminator="\n")
    else:
        fh = open(args.out, "w", encoding="utf-8", newline="")
        writer = csv.writer(fh, lineterminator="\n")
    writer.writerow(["order", "code", "edition", "major", "issued_at", "batch", "status"])
    writer.writerows(rows)
    if args.out != "-":
        fh.close()
        print("已签发 %d 条 → %s（公钥 %s）" % (len(rows), args.out, pub.hex()))
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    payload = parse_code(args.code, bytes.fromhex(args.pubkey))
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="NF Pro 离线授权码签发（纯标准库）")
    parser.add_argument("--key", default=DEFAULT_KEY, help="私钥路径（默认 %s）" % DEFAULT_KEY)
    sub = parser.add_mutually_exclusive_group(required=True)
    sub.add_argument("--self-test", action="store_true")
    sub.add_argument("--gen-key", action="store_true")
    sub.add_argument("--show-pubkey", action="store_true")
    sub.add_argument("--issue", action="store_true")
    sub.add_argument("--verify", action="store_true")
    parser.add_argument("--count", type=int, default=1)
    parser.add_argument("--start", type=int, default=1)
    parser.add_argument("--order-prefix", default="NF")
    parser.add_argument("--batch", default="manual")
    parser.add_argument("--edition", default="pro", choices=EDITIONS)
    parser.add_argument("--major", type=int, default=0)
    parser.add_argument("--issued-at", default=time.strftime("%Y-%m-%d"))
    parser.add_argument("--out", default="-")
    parser.add_argument("--code", default="")
    parser.add_argument("--pubkey", default="")
    args = parser.parse_args(argv)
    if args.self_test:
        return self_test()
    if args.gen_key:
        return cmd_gen_key(args)
    if args.show_pubkey:
        return cmd_show_pubkey(args)
    if args.issue:
        if args.count < 1 or args.count > 1000:
            parser.error("--count 必须在 1..1000")
        return cmd_issue(args)
    if args.verify:
        if not args.code or not args.pubkey:
            parser.error("--verify 需要 --code 与 --pubkey")
        return cmd_verify(args)
    return 2


if __name__ == "__main__":
    sys.exit(main())
