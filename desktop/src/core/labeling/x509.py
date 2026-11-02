"""X.509 证书解析与 SM2 证书链校验（纯标准库）。

作者：impl（DSH agent）· 2026-11-02
依据：nf-labelcheck 的 docs/interfaces-x509-tsa.md（函数名/返回结构逐字一致）。

只支持：
- 公钥算法 SM2（OID 1.2.156.10197.1.301），公钥为 SEC1 未压缩点 04‖x32‖y32；
- 签名算法 SM3withSM2（OID 1.2.156.10197.1.501），签名值为 r‖s（64 字节）；
- basicConstraints（2.5.29.19）与 keyUsage（2.5.29.15）两个扩展（其它扩展忽略）。

纪律：
- 纯标准库；DER 用 nf_labelcheck.der；
- 损坏数据抛 ValueError（带说明），不裸崩；
- 其它算法可解析（pub_hex=None），但 verify_cert_signature 一律返回 False。
"""

from __future__ import annotations

import base64
import hashlib
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import der, sm

#: SM2 公钥算法 OID（GM/T 0006）。
SM2_OID = "1.2.156.10197.1.301"
#: SM3withSM2 签名算法 OID（GM/T 0006）。
SM3WITHSM2_OID = "1.2.156.10197.1.501"
#: commonName 属性 OID。
CN_OID = "2.5.4.3"
#: basicConstraints 扩展 OID。
BASIC_CONSTRAINTS_OID = "2.5.29.19"
#: keyUsage 扩展 OID。
KEY_USAGE_OID = "2.5.29.15"
#: 证书链最大长度（含叶子证书）。
MAX_DEPTH = 5
#: keyUsage 位序（X.509 §4.2.1.3）。
KEY_USAGE_NAMES = (
    "digitalSignature", "contentCommitment", "keyEncipherment",
    "dataEncipherment", "keyAgreement", "keyCertSign", "cRLSign",
    "encipherOnly", "decipherOnly",
)
_PEM_RE = re.compile(
    rb"-----BEGIN CERTIFICATE-----(.*?)-----END CERTIFICATE-----", re.S)


@dataclass
class Cert:
    """一张已解析的 X.509 证书。"""

    der: bytes
    tbs: bytes                 # TBSCertificate 原始 DER（验签消息）
    version: int               # 1/2/3
    serial: int
    issuer: bytes              # Name 的 DER（逐字节匹配用）
    subject: bytes
    not_before: datetime       # UTC aware
    not_after: datetime
    spki_alg: str              # 公钥算法 OID 字符串
    pub_hex: str | None        # SM2 公钥 128 hex；其它算法 None
    sig_alg: str               # 签名算法 OID 字符串
    signature: bytes           # 签名值（SM2 为 64 字节 r‖s）
    is_ca: bool
    key_usage: set[str] = field(default_factory=set)
    subject_cn: str | None = None
    issuer_cn: str | None = None


# ---------------------------------------------------------------- DER 小工具
def _tlv(data: bytes, off: int = 0):
    """返回 (tag, value, next_off, 完整 TLV 原始字节)。"""
    tag, value, nxt = der.read_tlv(data, off)
    return tag, value, nxt, data[off:nxt]


def _children(content: bytes):
    """把 SEQUENCE/SET 内容拆成 [(tag, value, raw)]。"""
    out = []
    off = 0
    while off < len(content):
        tag, value, off, raw = _tlv(content, off)
        out.append((tag, value, raw))
    return out


def _need(cond: bool, message: str) -> None:
    if not cond:
        raise ValueError(message)


def _decode_time(tag: int, value: bytes) -> datetime:
    """解 UTCTime / GeneralizedTime；不支持的形式给可读 ValueError。"""
    try:
        return der.decode_time(tag, value)
    except ValueError:
        pass
    text = value.decode("ascii", "replace").strip()
    if tag == der.UTCTIME and len(text) == 11 and text.endswith("Z"):
        # YYMMDDHHMMZ（不带秒，X.509 允许）
        yy = int(text[0:2])
        year = 2000 + yy if yy < 50 else 1900 + yy
        dt = datetime.strptime(text[2:10], "%m%d%H%M")
        return dt.replace(year=year, tzinfo=timezone.utc)
    raise ValueError("时间字段格式不支持：%r" % text[:32])


def _decode_dir_string(tag: int, value: bytes) -> str:
    """DirectoryString / IA5String 解码。"""
    if tag == der.UTF8STRING:
        return value.decode("utf-8", "replace")
    if tag == 0x1E:                      # BMPString
        return value.decode("utf-16-be", "replace")
    if tag == 0x14:                      # TeletexString
        return value.decode("latin-1", "replace")
    if tag in (der.PRINTABLESTRING, der.IA5STRING):
        return value.decode("ascii", "replace")
    return value.decode("latin-1", "replace")


def _name_cn(name_raw: bytes) -> str | None:
    """从 Name（RDNSequence）DER 里取第一个 commonName。"""
    try:
        tag, value, _nxt, _raw = _tlv(name_raw, 0)
        if tag != der.SEQUENCE:
            return None
        for rdn_tag, rdn_val, _rr in _children(value):
            if rdn_tag != der.SET:
                continue
            for atv_tag, atv_val, _ar in _children(rdn_val):
                if atv_tag != der.SEQUENCE:
                    continue
                kids = _children(atv_val)
                if len(kids) < 2 or kids[0][0] != der.OID:
                    continue
                if der.decode_oid(kids[0][1]) != CN_OID:
                    continue
                return _decode_dir_string(kids[1][0], kids[1][1])
    except (ValueError, IndexError):
        return None
    return None


def _algorithm_oid(seq_content: bytes) -> str:
    """AlgorithmIdentifier 内容 → OID 字符串（缺 OID 抛 ValueError）。"""
    kids = _children(seq_content)
    _need(bool(kids) and kids[0][0] == der.OID, "AlgorithmIdentifier 缺 OID")
    return der.decode_oid(kids[0][1])


def _hex_of(raw: bytes) -> str:
    return raw.hex()


def _extension_index(exts_content: bytes) -> dict:
    """SEQUENCE OF Extension → {oid: (critical, 扩展值 DER 内容)}。"""
    out = {}
    for tag, value, _raw in _children(exts_content):
        if tag != der.SEQUENCE:
            continue
        kids = _children(value)
        if not kids or kids[0][0] != der.OID:
            continue
        oid = der.decode_oid(kids[0][1])
        idx = 1
        critical = False
        if idx < len(kids) and kids[idx][0] == der.BOOLEAN:
            critical = kids[idx][1] != b"\x00"
            idx += 1
        if idx < len(kids) and kids[idx][0] == der.OCTETSTRING:
            out[oid] = (critical, kids[idx][1])
    return out


def _basic_constraints(value: bytes) -> bool:
    """basicConstraints 扩展值（OCTET STRING 里的 DER）→ cA 布尔。"""
    try:
        tag, content, _nxt, _raw = _tlv(value, 0)
    except ValueError:
        return False
    if tag != der.SEQUENCE:
        return False
    for item_tag, val, _raw2 in _children(content):
        if item_tag == der.BOOLEAN:
            return val != b"\x00"
    return False


def _key_usage(value: bytes) -> set[str]:
    """keyUsage 扩展值（OCTET STRING 里的 DER BIT STRING）→ 名称集合。"""
    try:
        tag, content, _nxt, _raw = _tlv(value, 0)
    except ValueError:
        return set()
    if tag != der.BITSTRING:
        return set()
    unused, payload = der.decode_bitstring(content)
    names = set()
    total = len(payload) * 8 - unused
    for i in range(max(0, total)):
        byte = payload[i // 8]
        if byte & (0x80 >> (i % 8)) and i < len(KEY_USAGE_NAMES):
            names.add(KEY_USAGE_NAMES[i])
    return names


def _spki_pub_hex(spki_content: bytes) -> tuple:
    """SubjectPublicKeyInfo 内容 → (算法 OID, SM2 pub_hex 或 None)。"""
    kids = _children(spki_content)
    _need(len(kids) >= 2, "SPKI 结构不完整")
    _need(kids[0][0] == der.SEQUENCE, "SPKI.algorithm 不是 SEQUENCE")
    alg_oid = _algorithm_oid(kids[0][1])
    _need(kids[1][0] == der.BITSTRING, "SPKI.subjectPublicKey 不是 BIT STRING")
    unused, payload = der.decode_bitstring(kids[1][1])
    pub_hex = None
    if alg_oid == SM2_OID and unused == 0:
        if len(payload) == 65 and payload[:1] == b"\x04":
            pub_hex = _hex_of(payload[1:])
        elif len(payload) == 64:
            # 少数实现省略 0x04 前缀：按裸 x‖y 处理
            pub_hex = _hex_of(payload)
    return alg_oid, pub_hex


# ---------------------------------------------------------------- PEM / 载入
def pem_to_der(data: bytes) -> bytes:
    """PEM → 第一张证书的 DER；不是 PEM 或 BASE64 坏则 ValueError。"""
    raw = bytes(data)
    m = _PEM_RE.search(raw)
    if not m:
        raise ValueError("不是 PEM 证书（缺 BEGIN CERTIFICATE 标记）")
    body = re.sub(rb"\s+", b"", m.group(1))
    try:
        return base64.b64decode(body, validate=True)
    except (ValueError, base64.binascii.Error) as exc:
        raise ValueError("PEM BASE64 解码失败：%s" % exc)


def _pem_blocks(data: bytes) -> list:
    """PEM 里的全部证书 DER（保持出现顺序）。"""
    out = []
    for m in _PEM_RE.finditer(bytes(data)):
        body = re.sub(rb"\s+", b"", m.group(1))
        try:
            out.append(base64.b64decode(body, validate=True))
        except (ValueError, base64.binascii.Error) as exc:
            raise ValueError("PEM BASE64 解码失败：%s" % exc)
    return out


def load_trust_store(path: str) -> list[Cert]:
    """读信任库：PEM 多证书或 DER 单证书。"""
    try:
        raw = Path(path).read_bytes()
    except OSError as exc:
        raise ValueError("无法读取信任库：%s（%s）" % (path, exc))
    blocks = _pem_blocks(raw)
    ders = blocks if blocks else [raw]
    certs = []
    for i, one in enumerate(ders, 1):
        try:
            certs.append(parse_cert(one))
        except ValueError as exc:
            raise ValueError("信任库第 %d 张证书解析失败：%s" % (i, exc))
    return certs


# ---------------------------------------------------------------- 解析
def _parse_cert_der(data: bytes) -> Cert:
    """解析 DER Certificate → Cert（内部；所有失败抛 ValueError）。"""
    tag, cert_content, end, _raw = _tlv(data, 0)
    _need(tag == der.SEQUENCE, "Certificate 顶层不是 SEQUENCE")
    _need(end == len(data), "Certificate 后面还有多余字节")
    items = _children(cert_content)
    _need(len(items) == 3, "Certificate 应为 tbs/sigAlg/signature 三段")
    _need(items[0][0] == der.SEQUENCE, "tbsCertificate 不是 SEQUENCE")
    tbs_raw = items[0][2]
    tbs_content = items[0][1]
    _need(items[1][0] == der.SEQUENCE, "signatureAlgorithm 不是 SEQUENCE")
    sig_alg = _algorithm_oid(items[1][1])
    _need(items[2][0] == der.BITSTRING, "signatureValue 不是 BIT STRING")
    _unused, signature = der.decode_bitstring(items[2][1])

    fields = _children(tbs_content)
    idx = 0
    version = 1
    if fields and fields[0][0] == 0xA0:           # [0] EXPLICIT version
        vtag, vval, _vn, _vr = _tlv(fields[0][1], 0)
        _need(vtag == der.INTEGER, "version 不是 INTEGER")
        version = der.decode_int(vval) + 1
        idx = 1
    _need(idx < len(fields) and fields[idx][0] == der.INTEGER,
          "serialNumber 缺失")
    serial = der.decode_int(fields[idx][1])
    idx += 1
    _need(idx < len(fields) and fields[idx][0] == der.SEQUENCE,
          "tbs.signature 算法缺失")
    idx += 1
    _need(idx < len(fields) and fields[idx][0] == der.SEQUENCE, "issuer 缺失")
    issuer_raw = fields[idx][2]
    idx += 1
    _need(idx < len(fields) and fields[idx][0] == der.SEQUENCE, "validity 缺失")
    validity = _children(fields[idx][1])
    _need(len(validity) >= 2, "validity 字段不足两个时间")
    not_before = _decode_time(validity[0][0], validity[0][1])
    not_after = _decode_time(validity[1][0], validity[1][1])
    idx += 1
    _need(idx < len(fields) and fields[idx][0] == der.SEQUENCE, "subject 缺失")
    subject_raw = fields[idx][2]
    idx += 1
    _need(idx < len(fields) and fields[idx][0] == der.SEQUENCE, "SPKI 缺失")
    spki_alg, pub_hex = _spki_pub_hex(fields[idx][1])
    idx += 1

    exts = {}
    for tag, value, _raw in fields[idx:]:
        if tag == 0xA3:                       # [3] EXPLICIT extensions
            etag, eval_, _en, _er = _tlv(value, 0)
            _need(etag == der.SEQUENCE, "extensions 不是 SEQUENCE")
            exts = _extension_index(eval_)
    is_ca = False
    key_usage = set()
    if BASIC_CONSTRAINTS_OID in exts:
        is_ca = _basic_constraints(exts[BASIC_CONSTRAINTS_OID][1])
    if KEY_USAGE_OID in exts:
        key_usage = _key_usage(exts[KEY_USAGE_OID][1])

    return Cert(
        der=bytes(data),
        tbs=bytes(tbs_raw),
        version=version,
        serial=serial,
        issuer=bytes(issuer_raw),
        subject=bytes(subject_raw),
        not_before=not_before,
        not_after=not_after,
        spki_alg=spki_alg,
        pub_hex=pub_hex,
        sig_alg=sig_alg,
        signature=bytes(signature),
        is_ca=is_ca,
        key_usage=key_usage,
        subject_cn=_name_cn(subject_raw),
        issuer_cn=_name_cn(issuer_raw),
    )


def parse_cert(data: bytes) -> Cert:
    """接受 DER 或 PEM，返回 Cert；损坏数据抛 ValueError（带说明）。"""
    raw = bytes(data)
    if not raw:
        raise ValueError("证书数据为空")
    if b"-----BEGIN" in raw[:4096]:
        raw = pem_to_der(raw)
    try:
        return _parse_cert_der(raw)
    except ValueError as exc:
        raise ValueError("证书解析失败：%s" % exc)
    except (IndexError, TypeError) as exc:
        raise ValueError("证书解析失败：结构不完整（%s）" % exc)


# ---------------------------------------------------------------- 验签 / 有效期
def _sig_hex(signature: bytes) -> str | None:
    """签名值 → r‖s 的 128 hex；支持裸 64 字节与 DER SEQUENCE{r,s}。"""
    if len(signature) == 64:
        return signature.hex()
    if signature[:1] == b"\x30":
        try:
            _tag, content, _nxt, _raw = _tlv(signature, 0)
            kids = _children(content)
            if len(kids) != 2:
                return None
            r = der.decode_int(kids[0][1])
            s = der.decode_int(kids[1][1])
            return "%064x%064x" % (r, s)
        except (ValueError, IndexError):
            return None
    return None


def _valid_pub_hex(pub_hex: str | None) -> bool:
    if not isinstance(pub_hex, str) or len(pub_hex) != 128:
        return False
    try:
        bytes.fromhex(pub_hex)
    except ValueError:
        return False
    return True


def verify_cert_signature(cert: Cert, issuer_pub_hex: str) -> bool:
    """用 issuer 的 SM2 公钥验 cert.tbs 上的 SM3withSM2 签名。"""
    if cert.sig_alg != SM3WITHSM2_OID:
        return False
    if not _valid_pub_hex(issuer_pub_hex):
        return False
    sig_hex = _sig_hex(cert.signature)
    if sig_hex is None:
        return False
    try:
        return sm.sm2_verify(issuer_pub_hex, cert.tbs, sig_hex)
    except (ValueError, TypeError):
        return False


def _aware(dt: datetime) -> datetime:
    """naive 时间按 UTC 处理；aware 统一转 UTC。"""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def cert_valid_at(cert: Cert, when: datetime | None = None) -> bool:
    """证书有效期判定（when 缺省 = 现在；naive 按 UTC）。"""
    moment = _aware(when) if when is not None else datetime.now(timezone.utc)
    try:
        return cert.not_before <= moment <= cert.not_after
    except TypeError:
        return False


# ---------------------------------------------------------------- 链校验
def build_chain(cert: Cert, pool: list[Cert], roots: list[Cert],
                when: datetime | None = None) -> tuple:
    """把 cert 链到 roots，返回 (ok, issues, chain)。

    规则（见 docs/interfaces-x509-tsa.md）：
    - issuer == 上一张的 subject，**DER 逐字节相等**；
    - 中间 CA 必须 is_ca 且（若有 keyUsage）含 keyCertSign；
    - 链尾必须是 roots 里的证书（DER 逐字节相等）；
    - 每张证书都校验有效期；最大深度 5（含叶子）。
    """
    issues: list = []
    moment = _aware(when) if when is not None else datetime.now(timezone.utc)
    chain = [cert]
    if not cert_valid_at(cert, moment):
        issues.append("叶子证书不在有效期：%s" % _label(cert))
    root_ders = {c.der for c in roots}
    if cert.der in root_ders:
        return (not issues, issues, chain)
    seen = {cert.der}
    cur = cert
    while True:
        if cur.der in root_ders:
            break
        if len(chain) >= MAX_DEPTH:
            issues.append("证书链超过最大深度 %d" % MAX_DEPTH)
            break
        cands = [c for c in roots + pool
                 if c.subject == cur.issuer and c.der not in seen]
        if not cands:
            issues.append("找不到签发者（issuer=%s 不在证书池/信任根中）"
                          % (cur.issuer_cn or "（无 CN）"))
            break
        picked = None
        sub_issues: list = []
        for cand in _prefer_roots(cands, root_ders):
            if cand.der in root_ders:
                pass
            else:
                if not cand.is_ca:
                    sub_issues.append("签发者不是 CA：%s" % _label(cand))
                    continue
                if cand.key_usage and "keyCertSign" not in cand.key_usage:
                    sub_issues.append(
                        "签发者 keyUsage 缺 keyCertSign：%s" % _label(cand))
                    continue
            if not _valid_pub_hex(cand.pub_hex):
                sub_issues.append(
                    "签发者公钥不是可用的 SM2 128 hex：%s" % _label(cand))
                continue
            if not cert_valid_at(cand, moment):
                sub_issues.append("签发者证书不在有效期：%s" % _label(cand))
                continue
            if not verify_cert_signature(cur, cand.pub_hex):
                sub_issues.append("签名验不过：%s ← %s"
                                  % (_label(cur), _label(cand)))
                continue
            picked = cand
            break
        if picked is None:
            issues.extend(sub_issues or ["没有可用的签发者证书"])
            break
        seen.add(picked.der)
        chain.append(picked)
        cur = picked
    if chain[-1].der not in root_ders:
        if not any("链尾" in x for x in issues):
            issues.append("链尾不是信任根（未链到 roots）")
    return (not issues and chain[-1].der in root_ders, issues, chain)


def _prefer_roots(cands: list, root_ders: set) -> list:
    """候选签发者排序：信任根优先，其余保持原顺序。"""
    roots = [c for c in cands if c.der in root_ders]
    others = [c for c in cands if c.der not in root_ders]
    return roots + others


def _label(cert: Cert) -> str:
    cn = cert.subject_cn or "（无 CN）"
    return "%s serial=%d" % (cn, cert.serial)


# ---------------------------------------------------------------- 生成夹具
def _hex_bytes(text: str, size: int, what: str) -> bytes:
    s = str(text).strip().lower()
    if len(s) != size * 2:
        raise ValueError("%s 长度须为 %d hex 字符（实际 %d）"
                         % (what, size * 2, len(s)))
    try:
        return bytes.fromhex(s)
    except ValueError:
        raise ValueError("%s 含非十六进制字符" % what)


def _build_name(cn: str) -> bytes:
    if not isinstance(cn, str) or not cn.strip():
        raise ValueError("CN 不得为空")
    atv = der.seq(der.oid_node(CN_OID), der.utf8(cn))
    return der.seq(der.setof(atv))


def _time_node(dt: datetime) -> bytes:
    dt = _aware(dt)
    if 1950 <= dt.year <= 2049:
        text = dt.strftime("%y%m%d%H%M%S") + "Z"
        return der.wrap(der.UTCTIME, text.encode("ascii"))
    text = dt.strftime("%Y%m%d%H%M%S") + "Z"
    return der.wrap(der.GENERALIZEDTIME, text.encode("ascii"))


def _extension(oid: str, critical: bool, inner: bytes) -> bytes:
    parts = [der.oid_node(oid)]
    if critical:
        parts.append(der.wrap(der.BOOLEAN, b"\xff"))
    parts.append(der.octets(inner))
    return der.seq(*parts)


def _key_usage_bitstring(names: set) -> bytes:
    unknown = set(names) - set(KEY_USAGE_NAMES)
    if unknown:
        raise ValueError("未知 keyUsage：%s" % "、".join(sorted(unknown)))
    if not names:
        raise ValueError("keyUsage 不得为空集")
    top = max(KEY_USAGE_NAMES.index(n) for n in names)
    nbytes = top // 8 + 1
    payload = bytearray(nbytes)
    for name in names:
        idx = KEY_USAGE_NAMES.index(name)
        payload[idx // 8] |= 0x80 >> (idx % 8)
    unused = nbytes * 8 - top - 1
    return der.bitstring(bytes(payload), unused)


def make_cert(subject_cn: str, issuer_cn: str, pub_hex: str,
              issuer_priv_hex: str | None, serial: int = 1,
              not_before: datetime | None = None,
              not_after: datetime | None = None,
              is_ca: bool = False,
              key_usage: set[str] | None = None) -> bytes:
    """生成最小 X.509 v3 证书（SM2 + SM3withSM2），返回 DER。

    - issuer_priv_hex=None ⇒ 自签：issuer=subject；此时**内部生成一次性 SM2
      密钥对**（无外部私钥就无法签名），传入的 pub_hex 被忽略；
    - 否则 issuer 名取 issuer_cn，签名用 issuer_priv_hex，主体公钥用 pub_hex；
    - 扩展固定写 basicConstraints（cA 标志）与 keyUsage；
    - 输出可被 parse_cert 解析、verify_cert_signature 通过。
    """
    now = datetime.now(timezone.utc).replace(microsecond=0)
    nb = _aware(not_before) if not_before is not None else now - timedelta(
        days=1)
    na = _aware(not_after) if not_after is not None else now + timedelta(
        days=365)
    if na < nb:
        raise ValueError("not_after 早于 not_before")
    if not isinstance(serial, int) or serial <= 0:
        raise ValueError("serial 须为正整数")
    if issuer_priv_hex is None:
        keys = sm.sm2_keygen()
        issuer_priv_hex = keys["private"]
        pub_hex = keys["public"]
        issuer_name = _build_name(subject_cn)
    else:
        _hex_bytes(issuer_priv_hex, 32, "issuer_priv_hex")
        issuer_name = _build_name(issuer_cn or subject_cn)
    _hex_bytes(pub_hex, 64, "pub_hex")
    subject_name = _build_name(subject_cn)
    if key_usage is None:
        key_usage = ({"keyCertSign", "cRLSign"} if is_ca
                     else {"digitalSignature"})
    alg = der.seq(der.oid_node(SM3WITHSM2_OID))
    spki = der.seq(
        der.seq(der.oid_node(SM2_OID)),
        der.bitstring(b"\x04" + bytes.fromhex(pub_hex)),
    )
    bc = der.seq(der.wrap(der.BOOLEAN, b"\xff")) if is_ca else der.seq()
    exts = der.wrap(0xA3, der.seq(
        _extension(BASIC_CONSTRAINTS_OID, True, bc),
        _extension(KEY_USAGE_OID, True, _key_usage_bitstring(key_usage)),
    ))
    validity = der.seq(_time_node(nb), _time_node(na))
    tbs = der.seq(
        der.wrap(0xA0, der.int_node(2)),      # version v3
        der.int_node(serial),
        alg,
        issuer_name,
        validity,
        subject_name,
        spki,
        exts,
    )
    sig_hex = sm.sm2_sign(issuer_priv_hex, tbs)
    return der.seq(tbs, alg, der.bitstring(bytes.fromhex(sig_hex)))


def fingerprint(cert: Cert) -> str:
    """证书 DER 的 SHA-256 指纹（十六进制；辅助显示用）。"""
    return hashlib.sha256(cert.der).hexdigest()
