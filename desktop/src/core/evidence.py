"""证据包（evidence bundle）——cc_verify 的自包含证据容器。

内部差距（2026-11-04 实证）：三件证据件其实都在——attest 给可验证信封（三级信任）、
receipts 给单根 + inclusion proof、transparency 给哈希链——但**没有一件是「给外部人
一个文件就能验」的形态**：对方要拿到整个仓库、要知道仓库相对路径、要复现 nf 的算法。
「第三方复验」于是不成立，只剩「你自己跑一遍」。（nf verify 是门禁，不是证据校验。）

本模块只做**容器与判定顺序**，密码学一律复用既有实现，不自造：
- 叶 / 内部节点 / 梅克尔根：core.receipts（RFC 6962 域分隔，见该文件 leaf_hash / node_hash）
- 信封与签名：core.attest（digest_only / hmac-sha256 / sigstore-keyless，缺锚拒绝）
- 透明日志链：域分隔前缀取自 core.transparency_log（单一真源，不在本文件复写常量）

判定词表固定为 ok / revoked / expired / invalid——这是 ABI 的稳定面
（docs/ccos/abi-v0.md §4），新增形容词等于改所有验证方。

纪律（对齐 core 零第三方依赖红线）：stdlib-only；**纯读**（校验路径不落盘、不改仓库；
唯一例外是校验期把 payload 解到进程私有临时目录，出作用域即销毁）。
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import tempfile
import zipfile
from collections.abc import Sequence
from typing import Any

from core import attest, receipts
from core.transparency_log import NODE_PREFIX

SCHEMA = "nf-evidence/1"
REVOCATION_SCHEMA = "nf-revocation/1"
BUNDLE_ENTRY = "bundle.json"
PAYLOAD_DIR = "payload/"
ATTEST_DIR = "attest/"
REVOCATIONS_ENTRY = "revocations.json"

#: 证据强度排序（弱 → 强）：判 level 时取「包内**通过校验**的最强一档」——
#: 不通过的不算，避免「有强信封就算强证据」这种虚假保证。
LEVELS = ("digest_only", "hmac-sha256", "ssh-sig", "sigstore-keyless")
VERDICTS = ("ok", "revoked", "expired", "invalid")
#: 判定 → CLI 退出码（稳定面；4 留给「输入不是证据包」这一用法错，不是判定）
EXIT_CODES = {"ok": 0, "invalid": 1, "revoked": 2, "expired": 3}

#: zip 成员固定时间戳：同一输入两次打包**逐字节一致**（可复现构建惯例）。
#: 不用压缩：deflate 输出随 zlib 版本变，跨机器就不再逐字节一致了。
_ZIP_EPOCH = (1980, 1, 1, 0, 0, 0)

GUIDE = "修复指引："


def canonical(obj: Any) -> bytes:
    """规范化 JSON 编码——与 attest.canonical 同一口径（摘要稳定的前提）。"""
    return attest.canonical(obj)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _norm(rel: str) -> str:
    """仓相对路径归一成 POSIX 形态：zip 成员名与回执 id 都用正斜杠。"""
    return rel.replace("\\", "/").lstrip("/")


def _leaf(path: str, digest: str) -> str:
    """回执叶定义（与 receipts.build_scope 逐字一致：sha256(0x00 || canonical{id,digest})）。

    这里不重写公式的「主意」，只复算同一表达式——两份实现不一致会被
    test_evidence.py::test_leaf_matches_receipts 当场钉住。
    """
    payload = json.dumps({"id": path, "digest": digest}, sort_keys=True,
                         ensure_ascii=False, separators=(",", ":")).encode()
    return receipts.leaf_hash(payload).hex()


def _chain_head(entries: Sequence[dict[str, Any]]) -> str:
    """透明日志链头：H(NODE_PREFIX | prev | leaf) 逐节折叠（公式同 transparency_log）。"""
    prev = "0" * 64
    for e in entries:
        h = hashlib.sha256()
        h.update(NODE_PREFIX)
        for part in (prev.encode("ascii"), str(e.get("leaf") or "").encode("ascii")):
            h.update(b"|")
            h.update(part)
        prev = h.hexdigest()
    return prev


# ------------------------------------------------------------------ 打包

def build(root: str, targets: Sequence[str], issuer: str = "",
          key: bytes | None = None, expires_at: str = "", created_at: str = "",
          revocations: dict[str, Any] | None = None) -> tuple[bytes, dict[str, Any]]:
    """把目标文件打成自包含证据包 → (zip 字节, 摘要信息)。

    - 回执与根：receipts.build_scope（本模块只排序去重，公式不复制）
    - 信封：每条目标一份 attest；给了密钥即 hmac-sha256 级（不给 = digest_only）
    - 链头：按回执条目顺序折叠（append-only 顺序可证，不可抵赖**不**由本包提供）
    """
    rels = _targets(root, targets)
    doc = receipts.build_scope(root, rels, scope="evidence")
    entries = doc["entries"]
    members: list[tuple[str, bytes]] = [(PAYLOAD_DIR + rel, _read_text(root, rel))
                                        for rel in rels]
    atts: list[str] = []
    for i, rel in enumerate(rels, 1):
        name = ATTEST_DIR + f"{i:04d}.json"
        members.append((name, _envelope(root, rel, issuer, key)))
        atts.append(name)
    if revocations is not None:
        members.append((REVOCATIONS_ENTRY, _json_bytes(revocations)))
    meta = _manifest(doc["root"], entries, atts, created_at, issuer, key,
                     str(expires_at or ""), revocations is not None)
    members.append((BUNDLE_ENTRY, _json_bytes(meta)))
    info = {"root": meta["root"], "count": meta["count"], "head": meta["chain"]["head"],
            "level": meta["level"], "attestations": len(atts),
            "revocations": revocations is not None, "created_at": meta["created_at"]}
    return _zip_bytes(members), info


def _targets(root: str, targets: Sequence[str]) -> list[str]:
    """目标归一 + 形状闸门（空集/不存在一律带指引拒绝，不打空包）。"""
    rels = sorted({_norm(t) for t in targets if str(t).strip()})
    if not rels:
        raise ValueError("证据包至少要一个目标文件（" + GUIDE + "请先 nf evidence pack "
                         "<文件…> 指定目标；缺省目标请显式传入，不要用空集合打空包）")
    missing = [r for r in rels if not os.path.isfile(os.path.join(root, r))]
    if missing:
        raise ValueError("目标不是文件：" + ", ".join(missing) + "（" + GUIDE + "证据包只收"
                         "已存在文件，请先 ls 定位，目录请逐个列出其中的文件）")
    return rels


def _read_text(root: str, rel: str) -> bytes:
    """读成员实体并保证是 UTF-8 文本（信封要记行数，非文本件进不来）。"""
    with open(os.path.join(root, rel), "rb") as fh:
        raw = fh.read()
    try:
        raw.decode()
    except UnicodeDecodeError as exc:
        raise ValueError(f"目标不是 UTF-8 文本：{rel}（{exc}）（{GUIDE}证据包的成员一律 "
                         "UTF-8 文本——信封要记行数；二进制件请先转成文本，或另立二进制"
                         "证据面，不要把非文本件塞进来）") from exc
    return raw


def _envelope(root: str, rel: str, issuer: str, key: bytes | None) -> bytes:
    env = attest.build(rel, root, issuer=issuer)
    if key:
        env = attest.sign_hmac(env, key)
    return _json_bytes(env)


def _json_bytes(obj: Any) -> bytes:
    return (json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True)
            + "\n").encode()


def _manifest(root_digest: str, entries: Sequence[dict[str, Any]], atts: list[str],
              created_at: str, issuer: str, key: bytes | None, expires_at: str,
              has_rev: bool) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "created_at": created_at or attest.issue_stamp(),
        "producer": {"tool": "nf", "issuer": issuer or ""},
        "algorithm": "RFC6962-style sha256 domain-separated",
        "level": "hmac-sha256" if key else "digest_only",
        "count": len(entries),
        "root": root_digest,
        "entries": list(entries),
        "chain": {"head": _chain_head(entries), "count": len(entries)},
        "attestations": atts,
        "revocations": REVOCATIONS_ENTRY if has_rev else "",
        "expires_at": expires_at,
        "boundary": ("本包可证：成员字节未被改动、成员集与根一致、单条可折叠到根、"
                     "条目顺序未被插删、信封与主体一致。"
                     "本包**不**提供：不可抵赖（需第三方见证）、内容质量、内容真实性"),
    }


def _zip_bytes(members: Sequence[tuple[str, bytes]]) -> bytes:
    """确定性 zip：成员名排序 + 固定时间戳 + 不压缩。"""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_STORED) as zf:
        for name, data in sorted(members, key=lambda m: m[0]):
            zi = zipfile.ZipInfo(name, date_time=_ZIP_EPOCH)
            zi.compress_type = zipfile.ZIP_STORED
            zi.external_attr = 0o644 << 16
            zf.writestr(zi, data)
    return buf.getvalue()


def default_out() -> str:
    """缺省落点：系统临时目录的 nf-evidence.zip（**不往仓库里写**）。

    为什么（2026-11-04 实测）：缺省落到仓根时，nf evidence pack 被 CLI 泛测以零参数调用，
    直接在仓库根造出 evidence.zip——仓内纪律是「产物不进仓」，于是缺省改到临时目录；
    要进仓的落点由调用方用 --out 显式给出。
    """
    return os.path.join(tempfile.gettempdir(), "nf-evidence.zip")


def write(root: str, out: str, targets: Sequence[str], issuer: str = "",
          key: bytes | None = None, expires_at: str = "", created_at: str = "",
          revocations: dict[str, Any] | None = None) -> tuple[str, dict[str, Any]]:
    """打包并落盘（单一写出处；调用方负责输出路径口径）。"""
    data, info = build(root, targets, issuer=issuer, key=key, created_at=created_at,
                       expires_at=expires_at, revocations=revocations)
    dest = out if os.path.isabs(out) else os.path.join(root, out)
    parent = os.path.dirname(dest)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(dest, "wb") as fh:
        fh.write(data)
    return dest, info


# ------------------------------------------------------------------ 读面

class _Reader:
    """证据包读面：zip 与目录两种落点同一接口（目录形态便于人工检查）。"""

    def __init__(self, path: str):
        self.path = path
        self._zf: zipfile.ZipFile | None = None
        self._dir = ""
        if os.path.isdir(path):
            self._dir = path
        elif os.path.isfile(path):
            try:
                self._zf = zipfile.ZipFile(path)
            except zipfile.BadZipFile as exc:
                raise ValueError(f"不是证据包（坏 zip）：{exc}（{GUIDE}请用 nf evidence pack "
                                 "产出的 .zip 或解包后的目录，不要喂别的东西）") from exc
        else:
            raise ValueError(f"证据包不存在：{path}（{GUIDE}请先 nf evidence pack --out "
                             "<包.zip> 生成证据包，再对生成的包执行 verify）")

    def names(self) -> list[str]:
        if self._zf is not None:
            return sorted(self._zf.namelist())
        out: list[str] = []
        for base, _dirs, files in os.walk(self._dir):
            for f in files:
                full = os.path.join(base, f)
                out.append(_norm(os.path.relpath(full, self._dir)))
        return sorted(out)

    def read(self, name: str) -> bytes | None:
        name = _norm(name)
        if self._zf is not None:
            try:
                return self._zf.read(name)
            except KeyError:
                return None
        full = os.path.join(self._dir, *name.split("/"))
        if not os.path.isfile(full):
            return None
        with open(full, "rb") as fh:
            return fh.read()

    def close(self) -> None:
        if self._zf is not None:
            self._zf.close()
            self._zf = None


def _load_meta(rd: _Reader) -> dict[str, Any]:
    raw = rd.read(BUNDLE_ENTRY)
    if raw is None:
        raise ValueError("缺 bundle.json：不是证据包（" + GUIDE + "请用 nf evidence pack 产出，"
                         "不要手工拼 zip）")
    try:
        meta = json.loads(raw.decode())
    except (ValueError, UnicodeDecodeError) as exc:
        raise ValueError(f"bundle.json 不是合法 UTF-8 JSON：{exc}（{GUIDE}请重新 nf evidence "
                         "pack 生成，坏件不要手工修补——补出来的包验不过才是对的）") from exc
    if not isinstance(meta, dict) or meta.get("schema") != SCHEMA:
        got = meta.get("schema") if isinstance(meta, dict) else meta
        raise ValueError(f"证据包 schema 不匹配（期望 {SCHEMA}，实得 {got!r}）（{GUIDE}请用与"
                         "当前 nf 同版本的 nf evidence pack 重新打包）")
    return meta


# ------------------------------------------------------------------ 校验（分段，便于逐段判据）

def _empty_result() -> dict[str, Any]:
    return {"verdict": "invalid", "level": "none", "root": "", "head": "", "count": 0,
            "issues": [], "created_at": "", "expires_at": "", "revoked_by": None}


def _fill_header(res: dict[str, Any], meta: dict[str, Any]) -> None:
    res["root"] = str(meta.get("root") or "")
    res["head"] = str((meta.get("chain") or {}).get("head") or "")
    res["created_at"] = str(meta.get("created_at") or "")
    res["expires_at"] = str(meta.get("expires_at") or "")


def _check_members(rd: _Reader, entries: Sequence[dict[str, Any]],
                   issues: list[str]) -> list[bytes]:
    """成员实体在场 + 摘要一致 + 叶复算一致（三道一起判，任一不符即不可信）。"""
    leaves: list[bytes] = []
    for e in entries:
        rel = _norm(str(e.get("path") or e.get("id") or ""))
        data = rd.read(PAYLOAD_DIR + rel) if rel else None
        if data is None:
            issues.append(f"缺 payload：{rel or '?'}（{GUIDE}证据包必须自带成员实体——缺实体"
                          "的包算 invalid，不要改成只看清单）")
            continue
        digest = _sha256(data)
        want = str(e.get("digest") or "")
        if digest != want:
            issues.append(f"成员摘要不符：{rel}（记录={want[:16]} 实测={digest[:16]}）"
                          f"（{GUIDE}成员被改过或打包后被替换——请重新 nf evidence pack "
                          "并向签发方核对）")
        want_leaf = _leaf(rel, digest)
        if want_leaf != str(e.get("leaf") or ""):
            issues.append(f"叶复算不符：{rel}（{GUIDE}叶定义须与 receipts 同源；"
                          "包被改过就重打）")
        leaves.append(bytes.fromhex(want_leaf))
    return leaves


def _check_root(leaves: Sequence[bytes], res: dict[str, Any]) -> None:
    root_hex = (receipts.merkle_root(list(leaves)) or b"").hex()
    if root_hex != res["root"]:
        res["issues"].append(
            f"根不一致：记录={res['root'][:16]} 实测={root_hex[:16]}（{GUIDE}成员集被增删"
            "或改序——证据包必须与根的生成时点一致）")


def _check_proofs(entries: Sequence[dict[str, Any]], res: dict[str, Any]) -> None:
    for e in entries:
        folded = receipts.fold_proof(str(e.get("leaf") or ""), e.get("proof") or [])
        if folded != res["root"]:
            res["issues"].append(f"包含证明不折叠到根：{_norm(str(e.get('path') or ''))}"
                                 f"（{GUIDE}单条证明与根不同源——请重打包）")


def _check_chain(entries: Sequence[dict[str, Any]], res: dict[str, Any]) -> None:
    if res["head"] and _chain_head(entries) != res["head"]:
        res["issues"].append("透明日志链头不一致（" + GUIDE +
                             "条目顺序被插删/改序——链可证顺序，对不上即 invalid）")


def _extract(rd: _Reader, entries: Sequence[dict[str, Any]], tmp: str) -> None:
    """把成员解到进程私有临时目录（只为让 attest.verify 能按相对路径算主体摘要）。"""
    for e in entries:
        rel = _norm(str(e.get("path") or ""))
        data = rd.read(PAYLOAD_DIR + rel) if rel else None
        if data is None:
            continue
        full = os.path.join(tmp, *rel.split("/"))
        parent = os.path.dirname(full)
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(full, "wb") as fh:
            fh.write(data)


def _one_envelope(rd: _Reader, name: str, by_path: dict[str, str], tmp: str,
                  key: bytes | None) -> tuple[str, list[str]]:
    """校验单份信封 → (level 或空串, 失败原因)。"""
    raw = rd.read(_norm(name))
    if raw is None:
        return "", [f"{name}：包内缺该信封（{GUIDE}清单与实体不一致，请重打包）"]
    try:
        env = json.loads(raw.decode())
    except (ValueError, UnicodeDecodeError) as exc:
        return "", [f"{name}：不是合法 JSON（{exc}）（{GUIDE}重打包）"]
    subj = _norm(str((env.get("subject") or {}).get("path") or ""))
    subj_sha = str((env.get("subject") or {}).get("sha256") or "")
    if subj and by_path.get(subj) != subj_sha:
        return "", [f"{name}：信封 subject 与包内成员不同源（{GUIDE}信封须指向包内成员——"
                    "请重打包）"]
    ok, att_issues, level = attest.verify(env, tmp, key=key)
    if ok:
        return level, []
    return "", [f"{name}：{'；'.join(att_issues)}（信封未通过校验）"]


def _check_attestations(rd: _Reader, meta: dict[str, Any],
                        entries: Sequence[dict[str, Any]], key: bytes | None,
                        res: dict[str, Any]) -> None:
    """至少一份信封通过；level 取通过的最强一档（缺密钥一律拒绝，不降级）。"""
    att_names = [str(n) for n in (meta.get("attestations") or [])]
    if not att_names:
        res["issues"].append("包内无 attestation（" + GUIDE + "证据必须带信封——只有摘要的包"
                             "证明不了签发方；请用 nf evidence pack，它会为每个成员生成一份）")
        return
    by_path = {_norm(str(e.get("path") or "")): str(e.get("digest") or "") for e in entries}
    passed: list[str] = []
    failed: list[str] = []
    with tempfile.TemporaryDirectory(prefix="nf_evidence_") as tmp:
        _extract(rd, entries, tmp)
        for name in att_names:
            level, why = _one_envelope(rd, name, by_path, tmp, key)
            passed.extend([level] if level else [])
            failed.extend(why)
    if not passed:
        joined = "；".join(failed[:3]) or "无可用信封"
        res["issues"].append(f"所有 attestation 均未通过校验：{joined}（{GUIDE}hmac 级须提供"
                             "同一密钥 --key-file；缺密钥一律拒绝，不降级为 digest_only）")
        return
    res["level"] = max(passed, key=lambda lv: LEVELS.index(lv) if lv in LEVELS else -1)
    res["attestations_ok"] = len(passed)


def _apply_revocation(rd: _Reader, entries: Sequence[dict[str, Any]],
                      revocations: dict[str, Any] | None,
                      res: dict[str, Any]) -> bool:
    """吊销判定：命中即 revoked（压过 expired，也压过 ok）。返回是否已定案。"""
    rev = revocations if revocations is not None else _embedded_revocations(rd)
    hit = _revocation_hit(rev, entries)
    if hit is None:
        return False
    res["verdict"] = "revoked"
    res["revoked_by"] = hit
    why = hit.get("reason") or hit.get("path") or hit.get("digest") or "未给理由"
    res["issues"].append(f"证据已被吊销：{why}（{GUIDE}吊销是不可逆判定——请向签发方确认是否"
                         "曾发生错签或内容下架，不要把它当临时失败重试）")
    return True


def _apply_expiry(res: dict[str, Any], at: str) -> bool:
    """时效判定：有效期早于判定时点即 expired。返回是否已定案。"""
    exp = res["expires_at"]
    if not exp:
        return False
    now = at or attest.issue_stamp()
    if now <= exp:
        return False
    res["verdict"] = "expired"
    res["issues"].append(f"证据已过期：有效期至 {exp}，判定时点 {now}（{GUIDE}过期须重签——"
                         "请用 nf evidence pack 配新的 --expires-at 重新签发）")
    return True


def verify(bundle: str, key: bytes | None = None,
           revocations: dict[str, Any] | None = None,
           at: str = "") -> dict[str, Any]:
    """校验证据包 → {verdict, level, root, head, issues, ...}。

    判定顺序固定（fail-closed，先失败先返回；**不**允许「证据弱就放行」）：
    结构 → 成员摘要 → 根 → 包含证明 → 链 → 信封 → 吊销 → 时效。
    """
    res = _empty_result()
    rd = _Reader(bundle)
    try:
        try:
            meta = _load_meta(rd)
        except ValueError as exc:
            res["issues"].append(str(exc))
            return res
        entries = meta.get("entries") or []
        res["count"] = len(entries)
        _fill_header(res, meta)
        if not entries:
            res["issues"].append("证据包为空（" + GUIDE + "pack 时请至少给一个目标文件；"
                                 "空包不给 ok）")
            return res
        leaves = _check_members(rd, entries, res["issues"])
        if res["issues"]:
            return res
        _check_root(leaves, res)
        if res["issues"]:
            return res
        _check_proofs(entries, res)
        _check_chain(entries, res)
        if res["issues"]:
            return res
        _check_attestations(rd, meta, entries, key, res)
        if res["issues"]:
            return res
        if _apply_revocation(rd, entries, revocations, res):
            return res
        if _apply_expiry(res, at):
            return res
        res["verdict"] = "ok"
        return res
    finally:
        rd.close()


def _embedded_revocations(rd: _Reader) -> dict[str, Any] | None:
    raw = rd.read(REVOCATIONS_ENTRY)
    if raw is None:
        return None
    try:
        doc = json.loads(raw.decode())
    except (ValueError, UnicodeDecodeError):
        return None
    return doc if isinstance(doc, dict) else None


def _revocation_hit(rev: dict[str, Any] | None,
                    entries: Sequence[dict[str, Any]]) -> dict[str, Any] | None:
    """吊销表命中判定（按摘要或仓相对路径）；表形状不对一律不认（宁可 invalid 也不放过）。"""
    if not rev or str(rev.get("schema") or "") != REVOCATION_SCHEMA:
        return None
    revoked = rev.get("revoked") or []
    if not isinstance(revoked, list):
        return None
    digests = {str(e.get("digest") or "") for e in entries}
    paths = {_norm(str(e.get("path") or "")) for e in entries}
    for item in revoked:
        if not isinstance(item, dict):
            continue
        dig = str(item.get("digest") or "")
        pat = _norm(str(item.get("path") or ""))
        if (dig and dig in digests) or (pat and pat in paths):
            return item
    return None


# ------------------------------------------------------------------ 机制自检

def _selfcheck_bundle(tmp: str, pin: str, **kw: Any) -> bytes:
    data, _info = build(tmp, ["d/subject.md"], issuer="selfcheck", created_at=pin, **kw)
    return data


def _selfcheck_tamper(tmp: str, data: bytes) -> tuple[str, str]:
    """改成员一字节 → 必红；返回 (verdict, 该成员摘要)。"""
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        members = {n: zf.read(n) for n in zf.namelist()}
    payload = PAYLOAD_DIR + "d/subject.md"
    digest = hashlib.sha256(members[payload]).hexdigest()
    members[payload] = b"# subject\n\n-body-X\n"
    path = os.path.join(tmp, "tampered.zip")
    with open(path, "wb") as fh:
        fh.write(_zip_bytes(list(members.items())))
    return verify(path)["verdict"], digest


def _selfcheck_revoked(tmp: str, digest: str) -> str:
    """吊销表命中 → 必判 revoked。"""
    rev = {"schema": REVOCATION_SCHEMA,
           "revoked": [{"digest": digest, "revoked_at": "2026-01-01T00:00:00Z",
                        "reason": "selfcheck"}]}
    return verify(os.path.join(tmp, "b.zip"), revocations=rev)["verdict"]


def selfcheck() -> tuple[bool, list[str], dict[str, Any]]:
    """机制体检：PASS 必过、改一字节必红、吊销必判 revoked、过期必判 expired。

    抓不到篡改的校验器就是摆设——这里用**自造夹具**跑四种判定，不依赖仓库内容。
    """
    issues: list[str] = []
    stats: dict[str, Any] = {}
    with tempfile.TemporaryDirectory(prefix="nf_evself_") as tmp:
        os.makedirs(os.path.join(tmp, "d"), exist_ok=True)
        with open(os.path.join(tmp, "d", "subject.md"), "wb") as fh:
            fh.write(b"# subject\n\n-body-\n")
        pin = "2026-01-01T00:00:00Z"      # 固定签发时刻：测的是**打包确定性**，不是墙钟
        data = _selfcheck_bundle(tmp, pin)
        bundle = os.path.join(tmp, "b.zip")
        with open(bundle, "wb") as fh:
            fh.write(data)
        res = verify(bundle)
        stats["pack"] = {"root": res["root"], "head": res["head"], "count": res["count"],
                         "level": res["level"], "created_at": res["created_at"]}
        if res["verdict"] != "ok":
            issues.append(f"自造证据包未通过校验：{'；'.join(res['issues'])}"
                          f"（{GUIDE}请先修 pack/verify 一侧）")
        stats["ok"] = {"verdict": res["verdict"], "level": res["level"],
                       "count": res["count"]}
        if _selfcheck_bundle(tmp, pin) != data:
            issues.append("两次打包不逐字节一致（" + GUIDE + "打包须确定性——请固定时间戳与"
                          "成员序，否则证据不可复算）")
        tam, digest = _selfcheck_tamper(tmp, data)
        if tam != "invalid":
            issues.append(f"篡改未被判否（实得 {tam}）（{GUIDE}摘要/根校验失效——证据是摆设，"
                          "请先修校验路径）")
        stats["tamper"] = tam
        rev = _selfcheck_revoked(tmp, digest)
        if rev != "revoked":
            issues.append(f"吊销未判 revoked（实得 {rev}）（{GUIDE}吊销表命中必须压过 ok，"
                          "请先修判定顺序）")
        stats["revoked"] = rev
        exp = _selfcheck_bundle(tmp, pin, expires_at="2020-01-01T00:00:00Z")
        exp_path = os.path.join(tmp, "expired.zip")
        with open(exp_path, "wb") as fh:
            fh.write(exp)
        ex = verify(exp_path)["verdict"]
        if ex != "expired":
            issues.append(f"过期未判 expired（实得 {ex}）（{GUIDE}时效判定须在证据有效之后"
                          "执行，请先修判定顺序）")
        stats["expired"] = ex
    return not issues, issues, stats
