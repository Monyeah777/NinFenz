"""可信时间戳（TSA）模块：CMS SignedData / TSTInfo 解析与校验。

契约：docs/interfaces-x509-tsa.md（tsa.py 段，函数名与返回结构逐字一致）。
覆盖 RFC 3161 TimeStampToken 与 GB/T 20520 的 Time 字段形状。

结构链路（RFC 5652 + RFC 3161）：

    ContentInfo(id-signedData 1.2.840.113549.1.7.2)
      └─ SignedData
           ├─ encapContentInfo.eContentType = id-ct-TSTInfo
           ├─ encapContentInfo.eContent[0] = OCTET STRING(TSTInfo DER)
           ├─ certificates[0] = 签名者证书（可能多张）
           └─ signerInfos[0] = 签名者信息（sid/digestAlgorithm/
                                signedAttrs?/signatureAlgorithm/signature）

TSTInfo ::= SEQUENCE {
    version INTEGER, policy OID,
    messageImprint SEQUENCE { hashAlgorithm AlgorithmIdentifier,
                              hashedMessage OCTET STRING },
    serialNumber INTEGER, genTime GeneralizedTime,
    ... accuracy/ordering/nonce/tsa/extensions 可选 }

两种签名形态（RFC 5652 §5.4）：
- 有 signedAttrs：签名对象 = SignedAttributes 的 **DER SET OF 重编码**；
  另需校验 content-type / message-digest / signing-time 三个属性；
- 无 signedAttrs：签名对象 = eContent 的 OCTET STRING 内容（TSTInfo DER）。

纪律：
- 纯标准库；DER/SM2/SM3 复用 der.py / sm.py，证书与链复用 x509.py；
- 只支持 SM3withSM2；其它签名算法如实报失败，不降级、不外推；
- parse_token 对损坏数据抛 ValueError（带说明），不裸崩；
- 时间越界计入 issues 并置 ok=False；调用方可用 TIME_SKEW_PREFIX
  把该条降级为 WARN（WARN/FAIL 口径仍由调用方定）。

已知边界：
- signerIdentifier 支持 issuerAndSerialNumber；subjectKeyIdentifier
  形态仅在「证书只有一张」时按唯一候选选择；
- 不支持 BER 不定长编码、不支持 signedAttrs 的 BER 重排；
- 不验证 TSTInfo 的 accuracy/ordering/extensions 语义（只解析缺省）。
"""

from __future__ import annotations

import base64
import binascii
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from . import der, sm, x509

# ---------------------------------------------------------------- OID 常量
#: CMS ContentInfo 的 SignedData 类型。
OID_SIGNED_DATA = "1.2.840.113549.1.7.2"
#: 时间戳令牌的 eContentType（RFC 3161）。
OID_CT_TSTINFO = "1.2.840.113549.1.9.16.1.4"
#: signedAttrs 的 content-type 属性。
OID_ATTR_CONTENT_TYPE = "1.2.840.113549.1.9.3"
#: signedAttrs 的 message-digest 属性。
OID_ATTR_MESSAGE_DIGEST = "1.2.840.113549.1.9.4"
#: signedAttrs 的 signing-time 属性。
OID_ATTR_SIGNING_TIME = "1.2.840.113549.1.9.5"
#: SM3 杂凑算法（GM/T 0006）。
OID_SM3 = "1.2.156.10197.1.401"
#: SM3withSM2 签名算法（GM/T 0006）。
OID_SM3_WITH_SM2 = "1.2.156.10197.1.501"

#: 默认时间戳策略 OID（RFC 3161 示例策略；演示/测试用）。
DEFAULT_POLICY = "1.2.156.10197.1.1"
#: genTime 与校验时刻的最大容差（契约缺省 24h）。
MAX_TIME_SKEW = timedelta(hours=24)
#: 时间越界条目的稳定前缀（调用方据此降级为 WARN）。
TIME_SKEW_PREFIX = "时间越界（调用方可降级为 WARN）："
#: Time 字段的 14 位 UTC 形状（GB/T 20520 / 本工具 YYYYMMDDHHMMSSZ）。
_TIME_UTC_RE = re.compile(r"^\d{14}Z$")


@dataclass
class TstInfo:
    """TSTInfo 的机读投影（严格按契约字段顺序）。"""

    version: int
    policy: str
    hash_oid: str
    imprint: bytes
    serial: int
    gen_time: datetime
    tsa: str | None = None
    nonce: int | None = None


@dataclass
class TimestampToken:
    """解析后的时间戳令牌。tbs 是被签名内容的精确字节。"""

    der: bytes
    tst: TstInfo
    signer_der: bytes
    sig_alg: str
    signature: bytes
    tbs: bytes
    certs: list[bytes]


# ---------------------------------------------------------------- 小工具
def _fail(message: str):
    """统一的解析失败出口（契约：损坏数据抛 ValueError）。"""
    raise ValueError(message)


def _read(data: bytes, off: int, what: str):
    """读一个 TLV，失败时补上上下文（不裸崩）。"""
    try:
        return der.read_tlv(data, off)
    except ValueError as exc:
        _fail("%s 解析失败：%s" % (what, exc))


def _children(value: bytes, what: str):
    try:
        return der.parse_sequence(value)
    except ValueError as exc:
        _fail("%s 解析失败：%s" % (what, exc))


def _raw(part) -> bytes:
    """把 (tag, value) 还原成完整 DER TLV（长度用最小编码，DER 下逐字节等）。"""
    return der.wrap(part[0], part[1])


def _int_of(part, what: str) -> int:
    if part[0] != der.INTEGER:
        _fail("%s 不是 INTEGER" % what)
    return der.decode_int(part[1])


def _oid_of(part, what: str) -> str:
    if part[0] != der.OID:
        _fail("%s 不是 OID" % what)
    try:
        return der.decode_oid(part[1])
    except ValueError as exc:
        _fail("%s OID 解析失败：%s" % (what, exc))


def _alg_oid(part, what: str) -> str:
    """AlgorithmIdentifier（SEQUENCE{oid, params?}）→ OID 字符串。"""
    if part[0] != der.SEQUENCE:
        _fail("%s 不是 SEQUENCE" % what)
    inner = _children(part[1], what)
    if not inner:
        _fail("%s 为空" % what)
    return _oid_of(inner[0], what)


def _time_of(part, what: str) -> datetime:
    if part[0] not in (der.UTCTIME, der.GENERALIZEDTIME):
        _fail("%s 不是时间类型" % what)
    try:
        return der.decode_time(part[0], part[1])
    except (ValueError, UnicodeDecodeError) as exc:
        _fail("%s 时间解析失败：%s" % (what, exc))


def _aware(dt: datetime | None) -> datetime:
    """naive 按 UTC 处理；aware 统一转 UTC（与 x509 同口径）。"""
    if dt is None:
        return datetime.now(timezone.utc)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _generalized_node(dt: datetime) -> bytes:
    """GeneralizedTime 节点（YYYYMMDDHHMMSSZ，UTC）。"""
    return der.wrap(
        der.GENERALIZEDTIME,
        _aware(dt).strftime("%Y%m%d%H%M%SZ").encode("ascii"))


def _dir_name_cn(value: bytes) -> str | None:
    """directoryName（EXPLICIT Name）→ commonName（找不到返回 None）。"""
    try:
        tag, name, _end = der.read_tlv(value, 0)
    except ValueError:
        return None
    if tag != der.SEQUENCE:
        return None
    try:
        rdn_sets = der.parse_sequence(name)
    except ValueError:
        return None
    for _set_tag, set_value in rdn_sets:
        try:
            attrs = der.parse_sequence(set_value)
        except ValueError:
            continue
        for atv in attrs:
            if atv[0] != der.SEQUENCE:
                continue
            try:
                parts = der.parse_sequence(atv[1])
            except ValueError:
                continue
            if len(parts) < 2 or parts[0][0] != der.OID:
                continue
            if der.decode_oid(parts[0][1]) != "2.5.4.3":
                continue
            try:
                return parts[1][1].decode("utf-8", "replace")
            except UnicodeDecodeError:      # 兜底：坏编码不拖垮解析
                return None
    return None


def _general_name(value: bytes) -> str | None:
    """tsa [0] GeneralName → 可读字符串。"""
    try:
        tag, inner, _end = der.read_tlv(value, 0)
    except ValueError:
        return None
    if tag == 0x82:                             # dNSName
        return inner.decode("ascii", "replace")
    if tag == 0x81:                             # rfc822Name
        return inner.decode("ascii", "replace")
    if tag == 0x87 and len(inner) == 4:         # iPAddress
        return ".".join(str(b) for b in inner)
    if tag == 0x88 and len(inner) == 16:        # iPAddress（IPv6）
        return inner.hex()
    if tag == 0xA4:                             # directoryName
        return _dir_name_cn(value)
    return inner.hex()


# ---------------------------------------------------------------- 结构解析
def _parse_imprint(part) -> tuple:
    """messageImprint SEQUENCE → (hash_oid, imprint bytes)。"""
    if part[0] != der.SEQUENCE:
        _fail("messageImprint 不是 SEQUENCE")
    inner = _children(part[1], "messageImprint")
    if len(inner) != 2:
        _fail("messageImprint 应为 hashAlgorithm + hashedMessage 两段")
    hash_oid = _alg_oid(inner[0], "messageImprint.hashAlgorithm")
    if inner[1][0] != der.OCTETSTRING:
        _fail("messageImprint.hashedMessage 不是 OCTET STRING")
    imprint = inner[1][1]
    if not imprint:
        _fail("messageImprint.hashedMessage 为空")
    return hash_oid, imprint


def _parse_tstinfo(econtent: bytes) -> TstInfo:
    """eContent（TSTInfo DER）→ TstInfo。"""
    tag, content, end = _read(econtent, 0, "TSTInfo")
    if tag != der.SEQUENCE:
        _fail("TSTInfo 顶层不是 SEQUENCE")
    if end != len(econtent):
        _fail("TSTInfo 后面还有多余字节")
    fields = _children(content, "TSTInfo")
    if len(fields) < 5:
        _fail("TSTInfo 字段不足（至少 version/policy/imprint/serial/genTime）")
    version = _int_of(fields[0], "TSTInfo.version")
    policy = _oid_of(fields[1], "TSTInfo.policy")
    hash_oid, imprint = _parse_imprint(fields[2])
    serial = _int_of(fields[3], "TSTInfo.serialNumber")
    gen_time = _time_of(fields[4], "TSTInfo.genTime")
    tsa = None
    nonce = None
    for tag, value in fields[5:]:
        if tag == der.SEQUENCE:                 # accuracy（忽略语义）
            continue
        if tag == der.BOOLEAN:                  # ordering（DEFAULT FALSE）
            continue
        if tag == der.INTEGER:                  # nonce
            if nonce is not None:
                _fail("TSTInfo 出现重复 nonce")
            nonce = der.decode_int(value)
            continue
        if tag == 0xA0:                         # tsa [0] GeneralName
            tsa = _general_name(value)
            continue
        if tag == 0xA1:                         # extensions
            continue
        _fail("TSTInfo 出现未知字段 tag=%#x" % tag)
    return TstInfo(
        version=version, policy=policy, hash_oid=hash_oid,
        imprint=imprint, serial=serial, gen_time=gen_time,
        tsa=tsa, nonce=nonce,
    )


def _parse_sid(part) -> tuple:
    """SignerIdentifier → ("issuer_serial", issuer_der, serial) 或 SKI。"""
    if part[0] == der.SEQUENCE:                 # issuerAndSerialNumber
        inner = _children(part[1], "issuerAndSerialNumber")
        if len(inner) != 2:
            _fail("issuerAndSerialNumber 应为 issuer + serialNumber 两段")
        if inner[0][0] != der.SEQUENCE:
            _fail("signerIdentifier.issuer 不是 Name（SEQUENCE）")
        issuer = _raw(inner[0])
        serial = _int_of(inner[1], "signerIdentifier.serialNumber")
        return ("issuer_serial", issuer, serial)
    if part[0] in (0x80, 0x81):                 # subjectKeyIdentifier [0]
        return ("ski", part[1])
    _fail("signerIdentifier 形态不支持 tag=%#x" % part[0])


def _parse_signer_info(value: bytes) -> dict:
    """SignerInfo 内容 → 解析结果 dict。"""
    fields = _children(value, "SignerInfo")
    if len(fields) < 5:
        _fail("SignerInfo 字段不足")
    version = _int_of(fields[0], "SignerInfo.version")
    sid = _parse_sid(fields[1])
    digest_alg = _alg_oid(fields[2], "SignerInfo.digestAlgorithm")
    idx = 3
    signed_attrs = None
    if idx < len(fields) and fields[idx][0] == 0xA0:
        attrs = _children(fields[idx][1], "signedAttrs")
        signed_attrs = [_raw(part) for part in attrs]
        idx += 1
    if idx >= len(fields):
        _fail("SignerInfo 缺 signatureAlgorithm")
    sig_alg = _alg_oid(fields[idx], "SignerInfo.signatureAlgorithm")
    idx += 1
    if idx >= len(fields):
        _fail("SignerInfo 缺 signature")
    if fields[idx][0] != der.OCTETSTRING:
        _fail("SignerInfo.signature 不是 OCTET STRING")
    signature = fields[idx][1]
    idx += 1
    # unsignedAttrs [1] 存在则忽略（本工具不消费）
    if idx < len(fields) and fields[idx][0] != 0xA1:
        _fail("SignerInfo 出现未知字段 tag=%#x" % fields[idx][0])
    return {
        "version": version,
        "sid": sid,
        "digest_alg": digest_alg,
        "signed_attrs": signed_attrs,
        "sig_alg": sig_alg,
        "signature": signature,
    }


def _parse_encap(part) -> tuple:
    """EncapsulatedContentInfo → (eContentType, eContent bytes)。"""
    if part[0] != der.SEQUENCE:
        _fail("encapContentInfo 不是 SEQUENCE")
    fields = _children(part[1], "encapContentInfo")
    if not fields:
        _fail("encapContentInfo 为空")
    etype = _oid_of(fields[0], "encapContentInfo.eContentType")
    if len(fields) == 1:                        # 允许 detached（无 eContent）
        return etype, b""
    if fields[1][0] != 0xA0:
        _fail("encapContentInfo.eContent 不是 [0] 显式标签")
    tag, value, end = _read(fields[1][1], 0, "eContent")
    if end != len(fields[1][1]):
        _fail("eContent 后面还有多余字节")
    if tag == der.OCTETSTRING:                  # RFC 5652 标准形态
        return etype, value
    if tag == der.SEQUENCE:                     # 内联形态（部分实现直接放 TSTInfo）
        return etype, der.wrap(der.SEQUENCE, value)
    _fail("eContent 形态不支持（既不是 OCTET STRING 也不是 SEQUENCE）")


def _parse_certs(value: bytes) -> list:
    """certificates [0] IMPLICIT CertificateSet → 证书 DER 列表。"""
    certs = []
    off = 0
    while off < len(value):
        tag, _val, end = _read(value, off, "certificates")
        if tag == der.SEQUENCE:                 # 只收 Certificate
            certs.append(bytes(value[off:end]))
        off = end
    return certs


def _signed_attrs_set(attrs: list) -> bytes:
    """signedAttrs 的 DER SET OF 重编码（按编码逐字节排序，RFC 5652 §5.4）。"""
    return der.setof(*sorted(attrs))


def _parse_token(data: bytes) -> tuple:
    """解析令牌 DER → (TimestampToken, raw_signer, econtent_type, econtent)。"""
    if not isinstance(data, (bytes, bytearray)):
        _fail("令牌必须是 bytes")
    raw = bytes(data)
    if not raw:
        _fail("令牌数据为空")
    tag, content, end = _read(raw, 0, "ContentInfo")
    if tag != der.SEQUENCE:
        _fail("ContentInfo 顶层不是 SEQUENCE")
    if end != len(raw):
        _fail("ContentInfo 后面还有多余字节")
    outer = _children(content, "ContentInfo")
    if len(outer) != 2:
        _fail("ContentInfo 应为 contentType + content 两段")
    ct_oid = _oid_of(outer[0], "ContentInfo.contentType")
    if ct_oid != OID_SIGNED_DATA:
        _fail("ContentInfo 类型不是 id-signedData：%s" % ct_oid)
    if outer[1][0] != 0xA0:
        _fail("ContentInfo.content 不是 [0] 显式标签")
    sd_tag, sd_value, sd_end = _read(outer[1][1], 0, "SignedData")
    if sd_tag != der.SEQUENCE:
        _fail("SignedData 不是 SEQUENCE")
    if sd_end != len(outer[1][1]):
        _fail("SignedData 后面还有多余字节")
    sd = _children(sd_value, "SignedData")
    if len(sd) < 4:
        _fail("SignedData 字段不足")
    _int_of(sd[0], "SignedData.version")
    if sd[1][0] != der.SET:
        _fail("SignedData.digestAlgorithms 不是 SET")
    etype, econtent = _parse_encap(sd[2])
    certs = []
    signer_set = None
    for tag, value in sd[3:]:
        if tag == 0xA0:                         # certificates
            certs = _parse_certs(value)
        elif tag == 0xA1:                       # crls：不消费
            continue
        elif tag == der.SET:                    # signerInfos（DEFAULT 最后）
            signer_set = value
        else:
            _fail("SignedData 出现未知字段 tag=%#x" % tag)
    if signer_set is None:
        _fail("SignedData 缺 signerInfos")
    signers = _children(signer_set, "signerInfos")
    if not signers:
        _fail("signerInfos 为空")
    raw_signer = _parse_signer_info(signers[0][1])
    # 按 signerIdentifier 从 certificates 里选签名者证书
    signer_der = b""
    for cand in certs:
        try:
            cert = x509.parse_cert(cand)
        except ValueError:
            continue
        if _sid_matches(raw_signer["sid"], cert):
            signer_der = cand
            break
    if not signer_der and raw_signer["sid"][0] == "ski" and len(certs) == 1:
        # SKI 形态：x509.Cert 未暴露 SKI，唯一证书时按候选选择
        signer_der = certs[0]
    if raw_signer["signed_attrs"] is not None:
        tbs = _signed_attrs_set(raw_signer["signed_attrs"])
    else:
        tbs = econtent
    tst = _parse_tstinfo(econtent)
    token = TimestampToken(
        der=raw, tst=tst, signer_der=signer_der,
        sig_alg=raw_signer["sig_alg"], signature=raw_signer["signature"],
        tbs=tbs, certs=certs,
    )
    return token, raw_signer, etype, econtent


def _sid_matches(sid: tuple, cert) -> bool:
    """signerIdentifier 与证书是否匹配（issuer 逐字节 + serial）。"""
    if sid[0] != "issuer_serial":
        return False
    return bytes(sid[1]) == bytes(cert.issuer) and sid[2] == cert.serial


def parse_token(der_bytes: bytes) -> TimestampToken:
    """解析 TimeStampToken；损坏数据抛 ValueError。"""
    return _parse_token(der_bytes)[0]


# ---------------------------------------------------------------- 校验
def _chain_issues(signer_der: bytes, certs: list, roots, when) -> list:
    """签名者证书 → 信任根（委托 x509.build_chain）。"""
    if roots is None:
        return []                                # 调用方显式跳过链校验
    if not signer_der:
        return ["缺签名者证书：无法校验证书链"]
    try:
        signer = x509.parse_cert(signer_der)
    except ValueError as exc:
        return ["签名者证书解析失败：%s" % exc]
    root_certs, root_issues = _as_certs(roots)
    if root_issues:
        return root_issues
    if not root_certs:
        return ["未提供信任根：无法校验证书链"]
    pool = []
    for cand in certs:
        try:
            pool.append(x509.parse_cert(cand))
        except ValueError:
            continue
    when_dt = _aware(when) if when is not None else None
    ok, issues, _chain = x509.build_chain(signer, pool, root_certs, when_dt)
    if ok:
        return []
    return list(issues) or ["证书链不闭合"]


def _as_certs(roots) -> tuple:
    """roots 元素可以是 x509.Cert 或 DER/PEM bytes → (证书列表, 问题列表)。"""
    out = []
    for item in roots:
        if isinstance(item, x509.Cert):
            out.append(item)
        elif isinstance(item, (bytes, bytearray)):
            try:
                out.append(x509.parse_cert(bytes(item)))
            except ValueError as exc:
                return [], ["信任根解析失败：%s" % exc]
        else:
            return [], ["信任根类型不支持：%r" % type(item)]
    return out, []


def _signature_issues(token: TimestampToken) -> list:
    """签名验证：优先 signedAttrs 重编码，否则 eContent。"""
    if not token.signer_der:
        return ["缺签名者证书（或 signerIdentifier 无法匹配）"]
    try:
        cert = x509.parse_cert(token.signer_der)
    except ValueError as exc:
        return ["签名者证书解析失败：%s" % exc]
    issues = []
    if not cert.pub_hex:
        issues.append("签名者证书公钥不是 SM2（pub_hex 为空）")
    if token.sig_alg != OID_SM3_WITH_SM2:
        issues.append("签名算法不是 SM3withSM2：%s" % token.sig_alg)
    if len(token.signature) != 64:
        issues.append("签名值不是 64 字节（r‖s）")
    elif cert.pub_hex:
        try:
            good = sm.sm2_verify(cert.pub_hex, token.tbs,
                                 token.signature.hex())
        except (ValueError, TypeError):
            good = False
        if not good:
            issues.append("签名验不过（signedAttrs/eContent 与签名不匹配）")
    return issues


def _signed_attr_issues(attrs: list, econtent: bytes,
                        econtent_type: str) -> list:
    """signedAttrs 属性判据：content-type / message-digest / signing-time。

    只报不崩：任何单个属性结构异常都记成 issue，不向外抛异常
    （parse_token 已保证整体可解析；此处是语义面）。
    """
    issues = []
    by_oid: dict = {}
    for attr in attrs:
        try:
            tag, value, end = der.read_tlv(attr, 0)
            if tag != der.SEQUENCE or end != len(attr):
                issues.append("signedAttrs 属性不是完整 SEQUENCE")
                continue
            parts = der.parse_sequence(value)
        except ValueError:
            issues.append("signedAttrs 含无法解析的属性")
            continue
        if len(parts) < 2 or parts[0][0] != der.OID:
            issues.append("signedAttrs 属性缺 OID")
            continue
        if parts[1][0] != der.SET:
            issues.append("signedAttrs 属性值不是 SET")
            continue
        try:
            aoid = der.decode_oid(parts[0][1])
        except ValueError:
            issues.append("signedAttrs 属性 OID 非法")
            continue
        try:
            values = der.parse_sequence(parts[1][1])
        except ValueError:
            issues.append("signedAttrs 属性值解析失败：%s" % aoid)
            continue
        by_oid.setdefault(aoid, []).extend(values)
    # content-type：必须指向 TSTInfo
    ctype_values = by_oid.get(OID_ATTR_CONTENT_TYPE, [])
    if not ctype_values:
        issues.append("signedAttrs 缺 content-type 属性")
    else:
        value = ctype_values[0]
        if value[0] != der.OID:
            issues.append("signedAttrs content-type 不是 OID")
        else:
            try:
                got = der.decode_oid(value[1])
            except ValueError:
                got = ""
            if got != OID_CT_TSTINFO:
                issues.append("signedAttrs content-type 不是 id-ct-TSTInfo")
    if econtent_type != OID_CT_TSTINFO:
        issues.append("eContentType 不是 id-ct-TSTInfo：%s" % econtent_type)
    # message-digest：必须等于 SM3(eContent)
    md_values = by_oid.get(OID_ATTR_MESSAGE_DIGEST, [])
    if not md_values:
        issues.append("signedAttrs 缺 message-digest 属性")
    elif md_values[0][0] != der.OCTETSTRING:
        issues.append("signedAttrs message-digest 不是 OCTET STRING")
    elif md_values[0][1] != sm.sm3(econtent):
        issues.append("signedAttrs message-digest 与 eContent 摘要不一致")
    # signing-time：必须存在且可解析
    st_values = by_oid.get(OID_ATTR_SIGNING_TIME, [])
    if not st_values:
        issues.append("signedAttrs 缺 signing-time 属性")
    else:
        try:
            der.decode_time(st_values[0][0], st_values[0][1])
        except (ValueError, UnicodeDecodeError):
            issues.append("signedAttrs signing-time 不是合法时间")
    return issues


def _time_issues(gen_time: datetime, when) -> list:
    """genTime 与校验时刻的容差判据（默认 ±24h）。"""
    moment = _aware(when)
    if gen_time is None:
        return ["TSTInfo 缺 genTime"]
    try:
        delta = abs(_aware(gen_time) - moment)
    except TypeError:
        return ["genTime 类型非法：%r" % type(gen_time)]
    if delta > MAX_TIME_SKEW:
        return [TIME_SKEW_PREFIX + "genTime=%s，校验时刻=%s，相差 %s"
                % (_aware(gen_time).isoformat(), moment.isoformat(),
                   str(delta))]
    return []


def verify_token(tok, message: bytes, roots, when=None) -> tuple:
    """校验时间戳令牌，返回 (ok, issues)。

    - message：被盖时间戳的原始消息（bytes）；
    - roots：信任根列表（x509.Cert 或 DER/PEM bytes）；**None 表示跳过链校验**；
    - when：校验时刻（缺省现在；naive 按 UTC）。

    判据顺序严格按契约：messageImprint → 证书链 → 签名 → signedAttrs →
    genTime 容差。ok=True 仅当 issues 为空。
    """
    if isinstance(tok, (bytes, bytearray)):
        tok = parse_token(bytes(tok))
    if not isinstance(tok, TimestampToken):
        _fail("verify_token 需要 TimestampToken（或 DER bytes）")
    if not isinstance(message, (bytes, bytearray)):
        _fail("message 必须是 bytes")
    message = bytes(message)
    # 以 DER 为准重新解析：防止调用方手改数据类字段造成「看成绿」
    token, raw_signer, econtent_type, econtent = _parse_token(tok.der)
    issues = []
    if token.tst.version not in (1, 2):
        issues.append("TSTInfo.version 非法：%r（GB 为 2）" % (token.tst.version,))
    elif token.tst.version != 2:
        issues.append("TSTInfo.version=1：GB/T 20520—2025 要求 2（RFC 3161 兼容）")
    if econtent_type != OID_CT_TSTINFO:
        issues.append("eContentType 不是 id-ct-TSTInfo：%s" % econtent_type)
    # 1) messageImprint
    if token.tst.hash_oid != OID_SM3:
        issues.append("messageImprint 哈希算法不是 SM3：%s" % token.tst.hash_oid)
    if token.tst.imprint != sm.sm3(message):
        issues.append("messageImprint 与消息 SM3 摘要不一致（消息被篡改）")
    # 2) 证书链（roots=None 显式跳过）
    issues.extend(_chain_issues(token.signer_der, token.certs, roots, when))
    # 3) 签名
    issues.extend(_signature_issues(token))
    # 4) signedAttrs 属性判据（仅该形态）
    if raw_signer["signed_attrs"] is not None:
        issues.extend(_signed_attr_issues(
            raw_signer["signed_attrs"], econtent, econtent_type))
    # 5) genTime 容差
    issues.extend(_time_issues(token.tst.gen_time, when))
    return (not issues, issues)


# ---------------------------------------------------------------- 生成
def _build_tstinfo(imprint: bytes, policy: str, serial: int,
                   gen_time: datetime, nonce=None, tsa=None,
                   version: int = 2) -> bytes:
    """构造 TSTInfo DER（可带 nonce/tsa；测试钩子用）。

    version 默认 2：GB/T 20520—2025 的 TSTInfo.version 固定 2（RFC 3161 为 1）。
    """
    fields = [
        der.int_node(version),                  # GB: v2；RFC 3161: v1
        der.oid_node(policy),
        der.seq(der.seq(der.oid_node(OID_SM3)), der.octets(imprint)),
        der.int_node(serial),
        _generalized_node(gen_time),
    ]
    if nonce is not None:
        fields.append(der.int_node(nonce))
    if tsa:
        fields.append(der.wrap(0xA0, der.wrap(0x82, tsa.encode("ascii"))))
    return der.seq(*fields)


def _build_signed_attrs(tstinfo: bytes, gen_time: datetime,
                        content_type: str) -> tuple:
    """构造 signedAttrs：返回 (SET DER 作为签名对象, [0] IMPLICIT 字段)。"""
    attrs = [
        der.seq(der.oid_node(OID_ATTR_CONTENT_TYPE),
                der.setof(der.oid_node(content_type))),
        der.seq(der.oid_node(OID_ATTR_MESSAGE_DIGEST),
                der.setof(der.octets(sm.sm3(tstinfo)))),
        der.seq(der.oid_node(OID_ATTR_SIGNING_TIME),
                der.setof(_generalized_node(gen_time))),
    ]
    attrs.sort()                                # DER SET OF：按编码排序
    tbs = der.setof(*attrs)
    return tbs, der.wrap(0xA0, b"".join(attrs))


def _build_token(message: bytes, signer_cert_der: bytes,
                 signer_priv_hex: str, gen_time=None, serial: int = 1,
                 policy: str = DEFAULT_POLICY, with_signed_attrs: bool = True,
                 certs=None, nonce=None, tsa=None,
                 content_type: str = OID_CT_TSTINFO,
                 attr_content_type: str | None = None,
                 sig_alg: str = OID_SM3_WITH_SM2) -> bytes:
    """令牌生成核心（make_token 与测试共用；certs/nonce 等是测试钩子）。"""
    if not isinstance(message, (bytes, bytearray)):
        _fail("message 必须是 bytes")
    message = bytes(message)
    try:
        signer = x509.parse_cert(bytes(signer_cert_der))
    except ValueError as exc:
        _fail("签名者证书不可解析：%s" % exc)
    if not signer.pub_hex:
        _fail("签名者证书公钥不是 SM2，无法签名")
    try:
        derived = sm.sm2_public_from_private(signer_priv_hex)
    except ValueError as exc:
        _fail("签名私钥非法：%s" % exc)
    if derived != signer.pub_hex:
        _fail("签名私钥与证书公钥不匹配")
    gen = _aware(gen_time) if gen_time is not None else _aware(None)
    tstinfo = _build_tstinfo(sm.sm3(message), policy, serial, gen,
                             nonce=nonce, tsa=tsa)
    encap = der.seq(
        der.oid_node(content_type),
        der.wrap(0xA0, der.octets(tstinfo)),
    )
    if with_signed_attrs:
        tbs, attrs_field = _build_signed_attrs(
            tstinfo, gen, attr_content_type or OID_CT_TSTINFO)
    else:
        tbs, attrs_field = tstinfo, b""
    try:
        sig_hex = sm.sm2_sign(signer_priv_hex, tbs)
    except ValueError as exc:
        _fail("签名失败：%s" % exc)
    signature = bytes.fromhex(sig_hex)
    if certs is None:
        certs = [bytes(signer_cert_der)]
    cert_list = [bytes(c) for c in certs]
    sid = der.seq(signer.issuer, der.int_node(signer.serial))
    signer_info = der.seq(
        der.int_node(1),
        sid,
        der.seq(der.oid_node(OID_SM3)),
        attrs_field,
        der.seq(der.oid_node(sig_alg)),
        der.octets(signature),
    )
    signed_data = der.seq(
        der.int_node(1),
        der.setof(der.seq(der.oid_node(OID_SM3))),
        encap,
        der.wrap(0xA0, b"".join(cert_list)),
        der.setof(signer_info),
    )
    return der.seq(der.oid_node(OID_SIGNED_DATA),
                   der.wrap(0xA0, signed_data))


def make_token(message: bytes, signer_cert_der: bytes, signer_priv_hex: str,
               gen_time: datetime | None = None, serial: int = 1,
               policy: str = DEFAULT_POLICY,
               with_signed_attrs: bool = True) -> bytes:
    """生成最小 TimeStampToken（CMS ContentInfo → SignedData → TSTInfo）。

    - with_signed_attrs=True：带 content-type/message-digest/signing-time，
      签名对象是 SignedAttributes 的 DER SET OF 重编码；
    - with_signed_attrs=False：直接对 eContent（TSTInfo DER）签名。
    """
    return _build_token(
        message, signer_cert_der, signer_priv_hex,
        gen_time=gen_time, serial=serial, policy=policy,
        with_signed_attrs=with_signed_attrs)


# ---------------------------------------------------------------- Time 字段
def time_value_issues(value) -> list:
    """校验 SecurityData 的 Time 字段形状（只判形状，不做密码学验证）。

    分支（契约）：
    - None / ""            → ["缺少时间"]；
    - "YYYYMMDDHHMMSSZ"    → 合法返回 []（另校验日历有效性）；
    - 其它                 → 视为 BASE64 时间戳令牌，解码失败/非 DER 报错。
    """
    if value is None:
        return ["缺少时间"]
    if isinstance(value, str) and not value.strip():
        return ["缺少时间"]
    if not isinstance(value, str):
        return ["Time 字段类型非法：%r（应为字符串）" % (value,)]
    text = value.strip()
    if _TIME_UTC_RE.match(text):
        try:
            datetime.strptime(text, "%Y%m%d%H%M%SZ")
        except ValueError:
            return ["时间格式非法（日历越界）：%s" % text]
        return []
    compact = "".join(text.split())
    try:
        raw = base64.b64decode(compact, validate=True)
    except (binascii.Error, ValueError) as exc:
        return ["Time 字段既不是 YYYYMMDDHHMMSSZ，也不是合法 BASE64：%s"
                % exc]
    if not raw:
        return ["Time 字段 BASE64 解码为空"]
    try:
        tag, _content, end = der.read_tlv(raw, 0)
    except ValueError as exc:
        return ["Time 字段 BASE64 解码后不是 DER 结构：%s" % exc]
    if tag != der.SEQUENCE or end != len(raw):
        return ["Time 字段 BASE64 解码后不是完整的 DER SEQUENCE"]
    return []


__all__ = [
    "TstInfo",
    "TimestampToken",
    "parse_token",
    "verify_token",
    "make_token",
    "time_value_issues",
    "OID_CT_TSTINFO",
    "OID_SM3",
    "OID_SM3_WITH_SM2",
    "DEFAULT_POLICY",
    "MAX_TIME_SKEW",
    "TIME_SKEW_PREFIX",
]
