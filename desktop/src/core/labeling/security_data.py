"""TC260-PG-202511A 安全防护信息（SecurityData）构建与校验（按标准细节实现）。

依据：
- GB 45438—2025 第 6 章 / 规范性附录 E（七字段）
- TC260-PG-202511A V1.0-202508（安全防护技术指南）
- TC260-PG-20252A（27 位服务提供者编码规则）
细节来源见 docs/spec-notes.md（含 PDF 页码与复算命令）。

关键实现决定（与旧版不同，均已按标准纠正）：
1. 待签名数据（TBS）**在原始 JSON 文本上按词法切片**：生成方从 `"Label"` 到
   ProduceID 值结束；传播方到 PropagateID 值结束。禁止重新序列化后签名。
2. CntSel 取值 = PNG / JPEG / DFT；DFT = 除隐式标识字节外的全部文件字节。
3. Bindings 的 Type 可为 Hash（SM3）或 Soft（内容指纹），Value 十六进制大小写不敏感。
4. PubSD 是数组，元素 Type ∈ DS/PubKey/ExLink；DS 的 TBSData 是数组，
   元素 Type ∈ Cnt/Bnd/Md/Etc；多签名逐条验。
5. Version 是数字 1；Type 固定 "TC260PG"；SM3withSM2 签名 = 128 hex。
"""

from __future__ import annotations

import base64
import json

from . import sm

FIELDS = (
    "Label",
    "ContentProducer",
    "ProduceID",
    "ReservedCode1",
    "ContentPropagator",
    "PropagateID",
    "ReservedCode2",
)

LABEL_VALUES = {1: "属于生成合成", 2: "可能为生成合成（用户声明）", 3: "疑似生成合成（平台识别）"}
SM3_OID = "1.2.156.10197.1.401"
SM2_OID = "1.2.156.10197.1.501"
CNTSEL = ("PNG", "JPEG", "DFT")
SPANS = {"producer": 3, "propagator": 6}
TBS_TYPES = ("Cnt", "Bnd", "Md", "Etc")


# ---------------------------------------------------------------- TBS 切片

_WS = " \t\r\n"


def _skip_ws(s: str, i: int) -> int:
    while i < len(s) and s[i] in _WS:
        i += 1
    return i


def _scan_string(s: str, i: int) -> int:
    """i 指向起始引号，返回闭引号之后的偏移。"""
    if s[i] != '"':
        raise ValueError(f"期望字符串，偏移 {i}")
    i += 1
    while i < len(s):
        ch = s[i]
        if ch == "\\":
            i += 2
            continue
        if ch == '"':
            return i + 1
        i += 1
    raise ValueError("字符串未闭合")


def _scan_value(s: str, i: int) -> int:
    """扫描一个 JSON 值，返回值结束后的偏移。"""
    i = _skip_ws(s, i)
    if i >= len(s):
        raise ValueError("值缺失")
    ch = s[i]
    if ch == '"':
        return _scan_string(s, i)
    if ch in "{[":
        depth = 0
        while i < len(s):
            c = s[i]
            if c == '"':
                i = _scan_string(s, i)
                continue
            if c in "{[":
                depth += 1
            elif c in "}]":
                depth -= 1
                if depth == 0:
                    return i + 1
            i += 1
        raise ValueError("对象/数组未闭合")
    # 数字/布尔/null
    while i < len(s) and s[i] not in ",}]" + _WS:
        i += 1
    return i


def tbs_slice(raw: str, span: int) -> bytes:
    """从原始 JSON 文本中切出「Label 到第 span 个值结束」的字节。

    附录 A.1 的黄金示例见 tests/test_vectors.py。
    """
    key = raw.find('"Label"')
    if key < 0:
        raise ValueError("元数据中没有 Label 字段")
    pos = raw.find(":", key) + 1
    for n in range(1, span + 1):
        pos = _skip_ws(raw, pos)
        end = _scan_value(raw, pos)
        if n == span:
            return raw[key:end].encode("utf-8")
        # 跳到下一个 key 的冒号
        nxt = raw.find(",", end)
        if nxt < 0:
            raise ValueError(f"字段不足 {span} 个")
        colon = raw.find(":", nxt)
        if colon < 0:
            raise ValueError("JSON 结构异常")
        pos = colon + 1
    raise ValueError("无法切片")


# ---------------------------------------------------------------- 消息构造

def _canonical(obj) -> bytes:
    return json.dumps(obj, ensure_ascii=True, separators=(",", ":")).encode("ascii")


def slice_fields(meta: dict, side: str = "producer") -> dict:
    span = SPANS[side]
    out = {}
    for key in FIELDS[:span]:
        if key in meta and meta[key] is not None:
            out[key] = meta[key]
    return out


def build_message(sd: dict, raw_text: str, bindings: list,
                  content: bytes | None = None) -> bytes:
    """按 TBSData 数组拼接签名消息。

    - {"Type":"Md"}            → 原始 JSON 切片（Label…value3/6）
    - {"Type":"Bnd","ID":"1"}  → 该 Binding 实体的紧凑 JSON
    - {"Type":"Cnt","CntSel":…}→ 内容字节（调用方已按 CntSel 选好）
    - {"Type":"Etc"}           → 不支持（抛 ValueError）
    """
    parts = []
    for tbs in sd.get("TBSData") or []:
        t = tbs.get("Type") if isinstance(tbs, dict) else None
        if t == "Md":
            span = SPANS["propagator"] if tbs.get("Side") == "propagator" else SPANS["producer"]
            parts.append(tbs_slice(raw_text, span))
        elif t == "Bnd":
            want = str(tbs.get("ID", ""))
            hit = [b for b in bindings if str(b.get("ID")) == want]
            if not hit:
                raise ValueError(f"TBSData 引用的 Binding ID={want} 不存在")
            parts.append(_canonical(hit[0]))
        elif t == "Cnt":
            if content is None:
                raise ValueError("TBSData 含 Cnt，但未提供内容字节")
            parts.append(content)
        elif t == "Etc":
            raise ValueError("Etc 类型需扩展定义，本实现不支持")
        else:
            raise ValueError(f"未知 TBSData 类型：{t!r}")
    if not parts:
        raise ValueError("TBSData 为空")
    return b"".join(parts)


# ---------------------------------------------------------------- 构建

def build_bindings(content: bytes, cntsel: str, value_upper: bool = True) -> list:
    digest = sm.sm3_hex(content)
    if value_upper:
        digest = digest.upper()
    return [{
        "Type": "Hash", "ID": "1", "AlgID": SM3_OID,
        "CntSel": cntsel, "Value": digest,
    }]


def build_security_data(raw_text: str, bindings: list, priv_hex: str,
                        tbsdata=None, uid: bytes = sm.DEFAULT_UID,
                        include_pub: bool = True, tsa_sign=None,
                        cert_der: bytes | None = None) -> dict:
    """生成 SecurityData（默认 TBSData=[Bnd#1, Md]：绑定内容 + 绑定元数据切片）。

    tsa_sign：可选的 TSA 回调 message(bytes)->token DER；提供时把令牌 BASE64 放入
    DS.Time（messageImprint 输入见 timestamp_message）。
    cert_der：可选签名者证书 DER，放入 PubKey.Certificate（BASE64）。
    """
    tbsdata = tbsdata or [{"Type": "Bnd", "ID": "1"}, {"Type": "Md"}]
    sd = {"Type": "TC260PG", "Version": 1, "TBSData": tbsdata}
    msg = build_message(sd, raw_text, bindings)
    sig = sm.sm2_sign(priv_hex, msg, uid)
    time_value = None
    if tsa_sign is not None:
        token = tsa_sign(timestamp_message(tbsdata, sig))
        time_value = base64.b64encode(token).decode("ascii")
    out = {
        "SecurityData": {
            "Type": "TC260PG",
            "Version": 1,
            "Bindings": bindings,
            "PubSD": [{
                "Type": "DS",
                "AlgID": SM2_OID,
                "TBSData": tbsdata,
                "KeyID": 0,
                "Signature": sig,
                "Time": time_value,
            }],
        }
    }
    if include_pub:
        pub = {"Type": "PubKey", "AlgID": SM2_OID, "KeyID": 0,
               "KeyValue": sm.sm2_public_from_private(priv_hex)}
        if cert_der:
            pub["Certificate"] = base64.b64encode(cert_der).decode("ascii")
        out["SecurityData"]["PubSD"].append(pub)
    return out


# ---------------------------------------------------------------- 结构判据

def _bad(issues, msg):
    issues.append(msg)


def structure_issues(container) -> list:
    """结构判据（不含密码学验证）。返回问题列表；空=合格。"""
    issues = []
    if not isinstance(container, dict):
        return ["ReservedCode 不是 JSON 对象"]
    sd = container.get("SecurityData")
    if not isinstance(sd, dict):
        return ["缺少 SecurityData 对象"]
    if sd.get("Type") != "TC260PG":
        _bad(issues, "SecurityData.Type 应为 TC260PG")
    if sd.get("Version") != 1 or isinstance(sd.get("Version"), str):
        _bad(issues, "SecurityData.Version 应为数字 1")
    tags = [k for k in ("Bindings", "PrivSD", "PubSD", "Extension", "Extensions")
            if k in sd]
    if len(tags) != len(set(tags)):
        _bad(issues, "同名标签重复")
    bindings = sd.get("Bindings")
    if bindings is not None and not isinstance(bindings, list):
        _bad(issues, "Bindings 应为数组")
    for i, b in enumerate(bindings or []):
        if not isinstance(b, dict):
            _bad(issues, f"Bindings[{i}] 不是对象")
            continue
        btype = b.get("Type")
        if btype not in ("Hash", "Soft"):
            _bad(issues, f"Bindings[{i}].Type 应为 Hash/Soft")
        if btype == "Hash":
            if b.get("AlgID") != SM3_OID:
                _bad(issues, f"Bindings[{i}].AlgID 应为 SM3 OID")
            if b.get("CntSel") not in CNTSEL:
                _bad(issues, f"Bindings[{i}].CntSel 应为 PNG/JPEG/DFT")
            val = b.get("Value")
            if not isinstance(val, str) or len(val) != 64:
                _bad(issues, f"Bindings[{i}].Value 应为 64 位十六进制")
    if "PubSD" in sd:
        pubs = sd.get("PubSD")
        if not isinstance(pubs, list) or not pubs:
            _bad(issues, "PubSD 应为非空数组")
        seen_keyid = set()
        for i, p in enumerate(pubs or []):
            if not isinstance(p, dict):
                _bad(issues, f"PubSD[{i}] 不是对象")
                continue
            ptype = p.get("Type")
            if ptype == "DS":
                if p.get("AlgID") != SM2_OID:
                    _bad(issues, f"PubSD[{i}].AlgID 应为 SM3withSM2 OID")
                sig = p.get("Signature")
                if not isinstance(sig, str) or len(sig) != 128:
                    _bad(issues, f"PubSD[{i}].Signature 应为 128 位十六进制")
                tbs = p.get("TBSData")
                if not isinstance(tbs, list) or not tbs:
                    _bad(issues, f"PubSD[{i}].TBSData 缺失")
                else:
                    for t in tbs:
                        if not isinstance(t, dict) or t.get("Type") not in TBS_TYPES:
                            _bad(issues, f"PubSD[{i}].TBSData 类型非法")
            elif ptype == "PubKey":
                v = p.get("KeyValue")
                if not isinstance(v, str) or len(v) not in (128,):
                    _bad(issues, f"PubSD[{i}].KeyValue 应为 128 位十六进制")
                cert = p.get("Certificate")
                if cert is not None and (not isinstance(cert, str)
                                         or "BEGIN" in cert):
                    _bad(issues, f"PubSD[{i}].Certificate 应为 BASE64(DER)")
                kid = p.get("KeyID", 0)
                if kid in seen_keyid:
                    _bad(issues, f"PubSD[{i}].KeyID 重复（验证方只认第一个）")
                seen_keyid.add(kid)
            elif ptype == "ExLink":
                if not isinstance(p.get("Value"), str):
                    _bad(issues, f"PubSD[{i}].Value 应为 URI")
            else:
                _bad(issues, f"PubSD[{i}].Type 应为 DS/PubKey/ExLink")
    return issues


# ---------------------------------------------------------------- 校验

def check_binding(sd: dict, content: bytes) -> tuple:
    """校验 Hash 类绑定。返回 (ok, issues, 实测 SM3)。"""
    issues = []
    got = sm.sm3_hex(content)
    for i, b in enumerate(sd.get("Bindings") or []):
        if not isinstance(b, dict) or b.get("Type") != "Hash":
            continue
        if b.get("AlgID") != SM3_OID:
            issues.append(f"Bindings[{i}] 算法不是 SM3（本工具只算 SM3）")
            continue
        want = str(b.get("Value", "")).lower()
        if want != got:
            issues.append(f"Bindings[{i}] 摘要与内容不一致")
    return (not issues, issues, got)


def key_entries(sd: dict) -> dict:
    """从 PubSD 提取 {KeyID: {"key": hex|None, "cert_der": bytes|None}}。"""
    out = {}
    for p in sd.get("PubSD") or []:
        if not isinstance(p, dict) or p.get("Type") != "PubKey":
            continue
        kid = p.get("KeyID", 0)
        if kid in out:
            continue  # 重复 KeyID 只认第一个
        cert_der = None
        cert_b64 = p.get("Certificate")
        if isinstance(cert_b64, str) and cert_b64:
            try:
                cert_der = base64.b64decode(cert_b64, validate=True)
            except Exception:
                cert_der = None
        out[kid] = {"key": p.get("KeyValue"), "cert_der": cert_der}
    return out


def public_keys(sd: dict) -> dict:
    """从 PubSD 提取 {KeyID: 公钥 hex}（KeyValue 优先，缺则用证书里的公钥）。"""
    out = {}
    for kid, entry in key_entries(sd).items():
        key = entry.get("key")
        if not key and entry.get("cert_der"):
            try:
                from . import x509
                key = x509.parse_cert(entry["cert_der"]).pub_hex
            except Exception:
                key = None
        out[kid] = key
    return out


def verify_signatures(sd: dict, meta: dict, raw_text: str, bindings: list,
                      content: bytes | None, pub_hex: str | None = None) -> tuple:
    """逐条验 DS。返回 (ok, issues)。

    pub_hex 用于 KeyID 0 且无 PubKey 实体的场景（外部提供公钥）。
    """
    issues = []
    keys = public_keys(sd)
    if pub_hex:
        keys[0] = pub_hex  # 外部公钥优先（用于独立性验证）
    ds_list = [p for p in (sd.get("PubSD") or [])
               if isinstance(p, dict) and p.get("Type") == "DS"]
    if not ds_list:
        return False, ["PubSD 中没有 DS 签名实体"]
    for i, ds in enumerate(ds_list):
        kid = ds.get("KeyID", 0)
        pub = keys.get(kid)
        if not pub:
            issues.append(f"DS[{i}] 缺 KeyID={kid} 的公钥")
            continue
        sig = ds.get("Signature")
        if not isinstance(sig, str):
            issues.append(f"DS[{i}] 缺 Signature")
            continue
        try:
            msg = build_message(ds, raw_text, bindings, content)
        except ValueError as exc:
            issues.append(f"DS[{i}] 消息构造失败：{exc}")
            continue
        if not sm.sm2_verify(pub, msg, sig):
            issues.append(f"DS[{i}] 签名验不过（消息或签名被改）")
    return (not issues, issues)


# ---------------------------------------------------------------- 证书与时间

def _as_roots(roots):
    if roots is None:
        return None
    if isinstance(roots, (bytes, str)):
        from . import x509
        if isinstance(roots, str):
            return x509.load_trust_store(roots)
        return [x509.parse_cert(roots)]
    return roots


def verify_cert_chain(sd: dict, roots, when=None) -> tuple:
    """校验 PubSD 里每张证书到信任根。返回 (ok, issues, details)。"""
    from . import x509
    entries = key_entries(sd)
    certs = {}
    for kid, e in entries.items():
        if e.get("cert_der"):
            try:
                certs[kid] = x509.parse_cert(e["cert_der"])
            except ValueError as exc:
                return False, [f"KeyID={kid} 证书解析失败：{exc}"], {}
    if not certs:
        return False, ["PubSD 中没有 Certificate"], {}
    roots = _as_roots(roots)
    details = {}
    issues = []
    for kid, cert in certs.items():
        if roots is None:
            details[kid] = {"subject": cert.subject_cn, "chain": None}
            issues.append("未提供信任根（--trust-store），只验了签名未验链")
            continue
        ok, chain_issues, chain = x509.build_chain(cert, list(certs.values()),
                                                   roots, when)
        details[kid] = {"subject": cert.subject_cn,
                        "chain": [c.subject_cn for c in chain]}
        if not ok:
            issues.extend(chain_issues)
    return (not [i for i in issues if "未提供信任根" not in i]), issues, details


def timestamp_message(tbsdata: list, signature_hex: str) -> bytes:
    """时间戳 messageImprint 的输入：SM3(TBSData‖Signature)。

    指南未规定 messageImprint 的输入（见 docs/timestamp-notes.md §6.5）；
    本实现采用「TBSData 的紧凑 JSON + 签名字节」拼接，验证方可按同一规则重算。
    """
    return _canonical(tbsdata) + bytes.fromhex(signature_hex)


def verify_time(ds: dict, roots=None, when=None, tolerance_h=24) -> tuple:
    """校验 DS.Time。返回 (ok, issues, detail)。"""
    from . import tsa
    value = ds.get("Time")
    issues = tsa.time_value_issues(value)
    if issues and not isinstance(value, str):
        return False, issues, {"kind": "none"}
    if isinstance(value, str) and len(value) == 15 and value.endswith("Z") \
            and value[:14].isdigit():
        return True, [], {"kind": "string", "value": value}
    try:
        token_der = base64.b64decode(str(value), validate=True)
        tok = tsa.parse_token(token_der)
    except Exception as exc:
        return False, [f"Time 既不是时间串也不是合法 BASE64 令牌：{exc}"], {"kind": "bad"}
    if not roots:
        return False, ["时间戳令牌需要信任根（--trust-store）"], {"kind": "token"}
    ok, issues = tsa.verify_token(tok, timestamp_message(
        ds.get("TBSData") or [], ds.get("Signature") or ""), roots, when)
    return ok, issues, {"kind": "token", "gen_time": str(tok.tst.gen_time),
                        "serial": tok.tst.serial}


def content_hash_hex(content: bytes) -> str:
    return sm.sm3_hex(content)


def describe_field(key: str) -> str:
    return {
        "Label": "生成合成标签（1/2/3）",
        "ContentProducer": "服务提供者名称或 27 位编码",
        "ProduceID": "内容编号",
        "ReservedCode1": "生成方安全防护信息",
        "ContentPropagator": "传播平台名称或编码",
        "PropagateID": "传播编号",
        "ReservedCode2": "传播方安全防护信息",
    }.get(key, key)
