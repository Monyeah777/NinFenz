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
import hmac
import io
import json
import os
import tempfile
import warnings
import zipfile
from collections.abc import Sequence
from typing import Any

from core import atomic_write, attest, json_doc, receipts
from core import revocations as revoc
from core.transparency_log import NODE_PREFIX

SCHEMA = "nf-evidence/1"
RECEIPTS_SCHEMA = "nf-receipts/1"
ATTEST_SCHEMA = "nf-attest/1"
ATTEST_SET_SCHEMA = "nf-attest-set/1"
REVOCATION_SCHEMA = "nf-revocation/1"
BUNDLE_ENTRY = "bundle.json"
PAYLOAD_DIR = "payload/"
ATTEST_DIR = "attest/"
REVOCATIONS_ENTRY = "revocations.json"

#: 证据强度排序（弱 → 强）：判 level 时取「包内**通过校验**的最强一档」——
#: 不通过的不算，避免「有强信封就算强证据」这种虚假保证。
LEVELS = ("digest_only", "receipts_only", "hmac-sha256", "ssh-sig", "sigstore-keyless")
#: 证据形态（cc_verify 的输入面）：自包含包 / 协议回执 / 信封
KINDS = ("bundle", "receipts", "attest")
#: 判定词表 = EXIT_CODES 的键（单一真源：词表与退出码一一对应，不再各执一份）
#: 判定 → CLI 退出码（稳定面；4 留给「输入不是证据包」这一用法错，不是判定）。
#: 这四个键就是判定词表本身——不再单独维护一份 VERDICTS（两份真源必然漂移）。
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


#: 单成员/整包解压上限（防 zip 炸弹）：我们自己打包用 STORED，但**验证器收的是不可信输入**。
MAX_MEMBER_BYTES = 16 * 1024 * 1024
MAX_TOTAL_BYTES = 96 * 1024 * 1024


class UnsafeBundleError(ValueError):
    """证据包含不安全/歧义结构（路径穿越、重名成员、超限膨胀）。"""


def _safe_rel(rel: str) -> str:
    """仓相对路径的安全闸门 → 归一后的 POSIX 路径；不安全就抛 UnsafeBundleError。

    为什么必须在这里拦（2026-11-05 实测）：成员路径来自**不可信包**，而验证过程会把它拼进
    临时目录落盘（信封主体摘要要对文件算）。不拦两点号段就等于给了「验证即任意写」——这是
    验证器最不该有的洞：它的全部价值建立在「敢拿去验敌意输入」上。
    """
    clean = _norm(str(rel or ""))
    if not clean:
        raise UnsafeBundleError("成员路径为空（修复指引：成员必须有仓相对路径）")
    parts = clean.split("/")
    for part in parts:
        if part in ("", ".", ".."):
            raise UnsafeBundleError(f"成员路径不安全：{clean}（修复指引：路径段不许是空串 / "
                                    "单点 / 双点，这一条防的是解包越界写）")
        if ":" in part:
            raise UnsafeBundleError(f"成员路径含盘符/备用流写法：{clean}（修复指引：只接受仓内 "
                                    "POSIX 相对路径）")
        if part != part.strip():
            raise UnsafeBundleError(f"成员路径含首尾空白：{clean!r}（修复指引：请去掉不可见字符）")
    return clean


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


def _chain_prefix_head(entries: Sequence[dict[str, Any]], upto: int) -> str:
    """前 upto 条折叠出的链头（锚点核对用：外部锚点记的是「当时那条链的链头」）。"""
    prev = "0" * 64
    for e in entries[:max(0, upto)]:
        h = hashlib.sha256()
        h.update(NODE_PREFIX)
        for part in (prev.encode("ascii"), str(e.get("leaf") or "").encode("ascii")):
            h.update(b"|")
            h.update(part)
        prev = h.hexdigest()
    return prev


def check_anchor(entries: Sequence[dict[str, Any]], meta: dict[str, Any],
                 anchor: dict[str, Any] | None, res: dict[str, Any]) -> None:
    """外部锚点核对（G1：防「整链被截断成更早版本」）。

    语义：锚点 = 某个**外部可核**的（条目数 count, 链头 head）二元组，例如上一次发布的链头、
    外部日志的序号+摘要。核对三件事：
      1) 本包的链必须包含锚点声称的那一段前缀（count 条）——少于它即**被截断**；
      2) 该前缀折叠出的链头必须等于锚点记录（否则历史被改写/分叉）；
      3) 包内声明的 anchor 与外部锚点材料必须一致（声称与证据不得互相矛盾）。
    没提供锚点材料时：不判死、不判 ok —— 只在 warnings 里写明「无法证明未被截断」，
    并且**不**提升 level（缺证据不等于证据成立）。
    """
    declared = meta.get("anchor")
    if isinstance(declared, dict) and declared:
        res["anchor_ref"] = {"count": declared.get("count"), "head": declared.get("head")}
    if anchor is None:
        if res["anchor_ref"]:
            res["warnings"].append("包声明了外部锚点但未提供锚点材料（" + GUIDE +
                                   "无法证明未被截断：请向发布方索要锚点文件并加 --anchor）")
        return
    cnt = anchor.get("count")
    head = str(anchor.get("head") or "")
    if not isinstance(cnt, int) or cnt < 0 or not head:
        res["issues"].append("锚点材料形状不对（" + GUIDE +
                             "需要 {count: 非负整数, head: 非空字符串}）")
        return
    if res["anchor_ref"] and (res["anchor_ref"].get("count") != cnt
                               or res["anchor_ref"].get("head") != head):
        res["issues"].append("包内 anchor 与外部锚点不一致（" + GUIDE +
                             "声称的锚点与证据互相矛盾——请以外部锚点为准重新打包）")
        return
    if len(entries) < cnt:
        res["issues"].append(f"证据包被截断：包只有 {len(entries)} 条，锚点记录 {cnt} 条"
                             f"（{GUIDE}截断的历史不能当现在——请索要完整包）")
        return
    if _chain_prefix_head(entries, cnt) != head:
        res["issues"].append("与外部锚点不符：该位置的链头不一致（" + GUIDE +
                             "历史被改写或来自另一条链，二者只能有一个是真的）")
        return
    res["anchor_verified"] = True


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
          revocations: dict[str, Any] | None = None,
          anchor: dict[str, Any] | None = None,
          decision: dict[str, Any] | None = None) -> tuple[bytes, dict[str, Any]]:
    """把目标文件打成自包含证据包 → (zip 字节, 摘要信息)。

    - 回执与根：receipts.build_scope（本模块只排序去重，公式不复制）
    - 信封：每条目标一份 attest；给了密钥即 hmac-sha256 级（不给 = digest_only）
    - 链头：按回执条目顺序折叠（append-only 顺序可证，不可抵赖**不**由本包提供）
    - decision（可选，Q0）：绑定「过过哪条策略」；声明面放 bundle.json，
      绑定面放进 object_sha256 相符的那份信封（纳入信封摘要；旧包无此键不受影响）
    """
    rels = _targets(root, targets)
    target = _decision_target(root, rels, decision)
    doc = receipts.build_scope(root, rels, scope="evidence")
    entries = doc["entries"]
    members: list[tuple[str, bytes]] = [(PAYLOAD_DIR + rel, _read_text(root, rel))
                                        for rel in rels]
    atts: list[str] = []
    for i, rel in enumerate(rels, 1):
        name = ATTEST_DIR + f"{i:04d}.json"
        env = _envelope(root, rel, issuer, key, decision if rel == target else None)
        members.append((name, env))
        atts.append(name)
    if revocations is not None:
        members.append((REVOCATIONS_ENTRY, _json_bytes(revocations)))
    meta = _manifest(doc["root"], entries, atts, created_at, issuer, key,
                     str(expires_at or ""), revocations is not None, anchor, decision)
    members.append((BUNDLE_ENTRY, _json_bytes(meta)))
    info = {"root": meta["root"], "count": meta["count"], "head": meta["chain"]["head"],
            "level": meta["level"], "attestations": len(atts),
            "revocations": revocations is not None, "created_at": meta["created_at"],
            "anchor": meta.get("anchor") or None}
    return _zip_bytes(members), info


def _decision_target(root: str, rels: Sequence[str],
                     decision: dict[str, Any] | None) -> str:
    """决策证据块校验 → 绑定主体的相对路径（空串 = 未声明 decision）。"""
    if decision is None:
        return ""
    digests = [_sha256(_read_text(root, rel)) for rel in rels]
    issues = attest.decision_issues(decision, digests)
    if issues:
        raise ValueError(f"决策证据块不合法：{'；'.join(issues)}"
                         f"（{GUIDE}见 docs/ccos/evidence-bundle-v0.md）")
    obj = str(decision.get("object_sha256") or "")
    return next((rel for rel, dig in zip(rels, digests, strict=True) if dig == obj), "")


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


def _envelope(root: str, rel: str, issuer: str, key: bytes | None,
              decision: dict[str, Any] | None = None) -> bytes:
    env = attest.build(rel, root, issuer=issuer, decision=decision)
    if key:
        env = attest.sign_hmac(env, key)
    return _json_bytes(env)


def _json_bytes(obj: Any) -> bytes:
    return (json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True)
            + "\n").encode()


def _manifest(root_digest: str, entries: Sequence[dict[str, Any]], atts: list[str],
              created_at: str, issuer: str, key: bytes | None, expires_at: str,
              has_rev: bool, anchor: dict[str, Any] | None = None,
              decision: dict[str, Any] | None = None) -> dict[str, Any]:
    doc: dict[str, Any] = {
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
                     "条目顺序未被插删、信封与主体一致；给出外部锚点时还可证"
                     "「不是被截断的更早版本」。"
                     "本包**不**提供：不可抵赖（需第三方见证）、内容质量、内容真实性"),
    }
    if isinstance(anchor, dict) and anchor:
        doc["anchor"] = {"count": anchor.get("count"), "head": anchor.get("head")}
    if decision is not None:
        doc["decision"] = dict(decision)
    return doc


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
          revocations: dict[str, Any] | None = None,
          anchor: dict[str, Any] | None = None,
          decision: dict[str, Any] | None = None) -> tuple[str, dict[str, Any]]:
    """打包并落盘（单一写出处；调用方负责输出路径口径）。"""
    data, info = build(root, targets, issuer=issuer, key=key, created_at=created_at,
                       expires_at=expires_at, revocations=revocations, anchor=anchor,
                       decision=decision)
    dest = out if os.path.isabs(out) else os.path.join(root, out)
    parent = os.path.dirname(dest)
    if parent:
        os.makedirs(parent, exist_ok=True)
    # 在仓落点走原子写出：半截证据包比没有更危险（读者会把它当完整件验）
    atomic_write.write_bytes(dest, data)
    return dest, info


# ------------------------------------------------------------------ 读面

class _Reader:
    """证据包读面：zip 与目录两种落点同一接口（目录形态便于人工检查）。"""

    def __init__(self, path: str):
        self.path = path
        self._zf: zipfile.ZipFile | None = None
        self._dir = ""
        #: 读面发现的结构问题（重名成员 / 超限膨胀）：由 verify 收进判定，不在这里抛
        self.issues: list[str] = []
        self._total = 0
        if os.path.isdir(path):
            self._dir = path
        elif os.path.isfile(path):
            try:
                self._zf = zipfile.ZipFile(path)
            except zipfile.BadZipFile as exc:
                raise ValueError(f"不是证据包（坏 zip）：{exc}（{GUIDE}请用 nf evidence pack "
                                 "产出的 .zip 或解包后的目录，不要喂别的东西）") from exc
            names = self._zf.namelist()
            dup = sorted({n for n in names if names.count(n) > 1})
            if dup:
                self.issues.append(f"包内有重名成员：{'、'.join(dup[:3])}（{GUIDE}重名 zip 的"
                                   "取字节在实现间不一致——判定不可复算，按 invalid 处理）")
            declared = sum(int(getattr(info, "file_size", 0) or 0)
                           for info in self._zf.infolist())
            if declared > MAX_TOTAL_BYTES:
                self.issues.append(f"包声明解压后 {declared} 字节，超过上限 {MAX_TOTAL_BYTES}"
                                   f"（{GUIDE}拒绝按声明膨胀解包——防 zip 炸弹）")
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
                with self._zf.open(name) as fh:
                    data = fh.read(MAX_MEMBER_BYTES + 1)
            except KeyError:        # 成员不在包里：按「缺件」返回 None，由调用方判 invalid
                return None
            except (zipfile.BadZipFile, RuntimeError, NotImplementedError) as exc:
                # 重叠成员 / 不支持的压缩法（zipfile 自己判成 zip bomb 的形态）：按不可信处理
                self.issues.append(f"成员 {name} 不可安全读取：{exc}"
                                   f"（{GUIDE}容器结构歧义或压缩不受支持——判 invalid，不猜）")
                return None
            if len(data) > MAX_MEMBER_BYTES:
                self.issues.append(f"成员 {name} 超过单件上限 {MAX_MEMBER_BYTES} 字节"
                                   f"（{GUIDE}拒绝解包超限成员——防 zip 炸弹）")
                return None
            self._total += len(data)
            if self._total > MAX_TOTAL_BYTES:
                self.issues.append(f"已解压超过整包上限 {MAX_TOTAL_BYTES} 字节"
                                   f"（{GUIDE}拒绝继续膨胀解包——防 zip 炸弹）")
                return None
            return data
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
        meta = json_doc.loads(raw.decode(), dict, what="证据文档")
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
            "issues": [], "warnings": [], "created_at": "", "expires_at": "",
            "revoked_by": None, "anchor_ref": None, "anchor_verified": False,
            "decision": None, "decision_status": "absent", "policy_verified": False,
            "revocations_fresh": "unknown", "revocations_source": "none",
            "revocations_basis": "none"}


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
        try:
            rel = _safe_rel(str(e.get("path") or e.get("id") or ""))
        except UnsafeBundleError as exc:
            issues.append(str(exc))
            continue
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
    # 读面在遍历过程中才发现的问题（超限成员/歧义结构）也要收进判定
    issues.extend(rd.issues)
    rd.issues.clear()
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


def _check_chain(entries: Sequence[dict[str, Any]], meta: dict[str, Any],
                 res: dict[str, Any]) -> None:
    """链段**必填且自洽**（缺段/空头/计数不符一律 invalid）。

    为什么必须严（2026-11-04 实测）：旧实现「有 head 才比」——攻击者删掉 chain 段或把 head
    置空，校验直接跳过并判 ok，等于把「顺序不可证」伪装成「顺序没问题」。缺证据 ≠ 证据成立。
    """
    chain = meta.get("chain")
    if not isinstance(chain, dict):
        res["issues"].append("缺 chain 段（" + GUIDE + "证据包必须带链头——没有它无法证明"
                             "条目顺序，请用 nf evidence pack 重新打包）")
        return
    head = str(chain.get("head") or "")
    if not head:
        res["issues"].append("chain.head 为空（" + GUIDE + "空链头证明不了任何顺序，"
                             "请重新 nf evidence pack）")
        return
    count = chain.get("count")
    if count != len(entries):
        res["issues"].append(f"chain.count 不符：记录={count} 实测={len(entries)}"
                             f"（{GUIDE}条目被增删后未重打包）")
        return
    res["head"] = head
    if _chain_head(entries) != head:
        res["issues"].append("透明日志链头不一致（" + GUIDE +
                             "条目顺序被插删/改序——链可证顺序，对不上即 invalid）")


def _extract(rd: _Reader, entries: Sequence[dict[str, Any]], tmp: str) -> None:
    """把成员解到进程私有临时目录（只为让 attest.verify 能按相对路径算主体摘要）。"""
    for e in entries:
        rel = _safe_rel(str(e.get("path") or ""))
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
                  key: bytes | None) -> tuple[str, list[str], str]:
    """校验单份信封 → (level 或空串, 失败原因, 主体相对路径)。"""
    raw = rd.read(_norm(name))
    if raw is None:
        return "", [f"{name}：包内缺该信封（{GUIDE}清单与实体不一致，请重打包）"], ""
    try:
        env = json_doc.loads(raw.decode(), dict, what="证据文档")
    except (ValueError, UnicodeDecodeError) as exc:
        return "", [f"{name}：不是合法 JSON（{exc}）（{GUIDE}重打包）"], ""
    subj = _norm(str((env.get("subject") or {}).get("path") or ""))
    subj_sha = str((env.get("subject") or {}).get("sha256") or "")
    if subj and by_path.get(subj) != subj_sha:
        return "", [f"{name}：信封 subject 与包内成员不同源（{GUIDE}信封须指向包内成员——"
                    "请重打包）"], subj
    ok, att_issues, level = attest.verify(env, tmp, key=key)
    if ok:
        return level, [], subj
    return "", [f"{name}：{'；'.join(att_issues)}（信封未通过校验）"], subj


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
    covered: set[str] = set()
    with tempfile.TemporaryDirectory(prefix="nf_evidence_") as tmp:
        _extract(rd, entries, tmp)
        for name in att_names:
            level, why, subj = _one_envelope(rd, name, by_path, tmp, key)
            if level:
                passed.append(level)
                covered.add(subj)
            else:
                failed.extend(why)
    if failed:
        # 严格口径：清单里的**每一份**信封都必须通过。容忍「有一份过了就算过」等于给了
        # 「悄悄塞一份坏信封」的容错面——证据强度只能由最弱那环决定，不能挑最好看的报。
        joined = "；".join(failed[:3]) or "无可用信封"
        res["issues"].append(f"信封未全部通过校验：{joined}（{GUIDE}hmac 级须提供同一密钥 "
                             "--key-file；缺密钥一律拒绝，不降级为 digest_only；坏信封请"
                             "重新 nf evidence pack）")
        return
    uncovered = sorted({_norm(str(e.get("path") or e.get("id") or "")) for e in entries}
                       - covered)
    if uncovered:
        res["issues"].append(f"成员缺信封：{', '.join(uncovered[:3])}（{GUIDE}每个成员都要有一份"
                             "信封——没有签发背书的成员不算证据，请重新 nf evidence pack）")
        return
    res["level"] = max(passed, key=lambda lv: LEVELS.index(lv) if lv in LEVELS else -1)
    res["attestations_ok"] = len(passed)


def _check_decision(rd: _Reader, meta: dict[str, Any],
                    entries: Sequence[dict[str, Any]], res: dict[str, Any],
                    expected_policy_digest: str = "") -> None:
    """决策证据块（Q0）：声明面（bundle.json）必须与绑定面（相符信封）一致。

    只证明「这份证据绑定过一次 cc_check 的判定」；**不证明策略内容正确**——策略正确性
    需要验方用自己信任的 policy 重算 policy_digest 后比对（v0 不提供期望参数）。
    digest_only 级的信封只算 declared（没签名覆盖，证不了签发方认可该策略）。
    """
    envs: list[dict[str, Any]] = []
    for name in [str(n) for n in (meta.get("attestations") or [])]:
        raw = rd.read(name)
        if raw is None:
            continue
        try:            # 坏信封由上游 fail-closed 判死，这里跳过不重复记账
            env = json_doc.loads(raw.decode(), dict, what="信封")
        except (ValueError, UnicodeDecodeError):
            continue
        if isinstance(env, dict):
            envs.append(env)
    decision = meta.get("decision")
    if decision is None:
        if any(isinstance(env.get("decision"), dict) for env in envs):
            res["issues"].append("信封带 decision 但清单未声明（声明面被删，绑定面仍在）"
                                 "（" + GUIDE + "重新 pack 让声明面与绑定面同源）")
        elif expected_policy_digest:
            res["warnings"].append("包内无 decision，无法比对策略（只证字节与信封；"
                                   "" + GUIDE + "需要策略绑定请 pack 时带 decision）")
        return
    issues = attest.decision_issues(decision, [str(e.get("digest") or "") for e in entries])
    if issues:
        res["issues"].extend(issues)
        return
    obj = str(decision.get("object_sha256") or "")
    matched, signed = 0, False
    for env in envs:
        if str((env.get("subject") or {}).get("sha256") or "") != obj:
            continue
        matched += 1
        bound = env.get("decision")
        if not isinstance(bound, dict) or bound != decision:
            res["issues"].append("decision 声明面与信封绑定面不一致（换策略/删块都会在这里断）"
                                 "（" + GUIDE + "重新 nf evidence pack 并把同一 decision 交给"
                                 " pack）")
            return
        signed = signed or bool(env.get("signature"))
    if not matched:
        res["issues"].append("decision 找不到主体摘要相符的信封（决策未绑定到任何签发面）"
                             "（" + GUIDE + "重新 pack，decision.object_sha256 必须等于某个"
                             "成员实体的 sha256）")
        return
    res["decision"] = dict(decision)
    res["decision_status"] = "bound" if signed else "declared"
    if expected_policy_digest:
        want = expected_policy_digest.strip().lower()
        got = str(decision.get("policy_digest") or "")
        if want != got:
            res["issues"].append(f"decision.policy_digest 与期望策略不符（期望={want[:16]} "
                                 f"实际={got[:16]}）（{GUIDE}确认包与策略是同一份；"
                                 "策略内容正确性只能由验方用自己信任的策略比对）")
            return
        res["policy_verified"] = True


#: `--revocations` 形状不对时的统一文案（M11）：坏形状 fail-closed，不许静默不命中
_BAD_REVOCATIONS = ("--revocations 既不是 nf-revocation/1 表也不是 nf-revocation-feed/1"
                    "（" + GUIDE + "给表或签名 feed；传 feed 时本仓会取 table 并读其有效期）")


def _revocation_source(rev: dict[str, Any] | None,
                       ) -> tuple[dict[str, Any] | None, dict[str, Any] | None, str]:
    """吊销来源归一化 → (表, feed 信封, 错误文本)。

    `--revocations` 现在**同时吃**普通 `nf-revocation/1` 表与签名 `nf-revocation-feed/1`
    （此前只认表：传签名 feed 会静默不命中、已吊销的证据照样判 ok——那是缺陷，不是特性）。
    吃 feed 时取里面的表并读它的有效期；裸表没有信封可读有效期 → freshness=unknown。
    **坏形状一律 fail-closed**：坏件不能当「无吊销」，也不能静默放过。
    """
    if not isinstance(rev, dict):
        return None, None, _BAD_REVOCATIONS
    schema = str(rev.get("schema") or "")
    if schema == REVOCATION_SCHEMA:
        table, feed = rev, None
    elif schema == revoc.FEED_SCHEMA:
        table = revoc.table_of(rev)
        feed = rev
        if table is None:
            return None, None, ("--revocations 的 feed 缺 nf-revocation/1 表（" + GUIDE +
                                "只放条目不算；请用签发方 feed 或先 revocations merge）")
    else:
        return None, None, _BAD_REVOCATIONS
    revoked = table.get("revoked")
    if not isinstance(revoked, list) or not all(isinstance(i, dict) for i in revoked):
        return None, None, ("--revocations 的 revoked 必须是对象数组（" + GUIDE +
                            "给合法的 nf-revocation/1 表或签名 feed）")
    return table, feed, ""


def _apply_revocation(rd: _Reader, entries: Sequence[dict[str, Any]],
                      revocations: dict[str, Any] | None,
                      res: dict[str, Any], fresh: dict[str, Any],
                      at: str = "") -> bool:
    """吊销判定：命中即 revoked（压过 expired/新鲜度，也压过 ok）。返回是否已定案。

    来源优先级：外部 `--revocations`（表或签名 feed）> 包内嵌（只认表）。
    未命中时**只记录新鲜度**（写进 `fresh` 与 res），不在这里判死——严格判定在时效之后。
    """
    if revocations is not None:
        table, feed, err = _revocation_source(revocations)
        res["revocations_source"] = "external"
    else:
        table, err = _embedded_revocations(rd)
        feed = None
        res["revocations_source"] = "embedded" if (table is not None or err) else "none"
    if err:
        res["issues"].append(err)
        return True                       # 坏吊销表 = 定案 invalid（不是「无吊销」）
    if table is None:
        return False                      # 没做吊销检查：不是「陈旧」，严格开关也不判死
    fresh.update(revoc.freshness(feed, at) if feed is not None
                 else {"state": "unknown", "expires_at": "", "basis": "none"})
    res["revocations_fresh"] = fresh["state"]
    res["revocations_basis"] = fresh["basis"]
    hit = _revocation_hit(table, entries)
    if hit is None:
        return False
    res["verdict"] = "revoked"
    res["revoked_by"] = hit
    why = hit.get("reason") or hit.get("path") or hit.get("digest") or "未给理由"
    res["issues"].append(f"证据已被吊销：{why}（{GUIDE}吊销是不可逆判定——请向签发方确认是否"
                         "曾发生错签或内容下架，不要把它当临时失败重试）")
    return True


def _apply_freshness(res: dict[str, Any], require_fresh: bool, at: str,
                     fresh: dict[str, Any]) -> bool:
    """吊销表新鲜度：默认只 WARN；`--require-fresh-revocations` 才把 stale/unknown 定案。

    插在**时效之后、ok 之前**：`expired` 是更具体的正向判定，不该被「表陈旧」这种数据
    质量问题遮蔽；而「命中吊销」是事实，已在 `_apply_revocation` 里立即定案。
    **完全没有吊销来源时不算 unknown**——那是「没做吊销检查」，不是「陈旧」，严格开关下
    也不得判死（否则不传吊销表的离线复验会全红）。
    """
    if str(res.get("revocations_source") or "none") == "none":
        return False
    state = str(res.get("revocations_fresh") or "unknown")
    if state not in revoc.FRESH:
        state = "unknown"      # 来源给出词表外状态：按未知处理（绝不因错误状态放行）
    if state == "fresh":
        return False
    exp = str(fresh.get("expires_at") or "")
    if not require_fresh:
        if state == "stale":
            res["warnings"].append(f"吊销表已过期（expires_at={exp}）：未开 "
                                   "--require-fresh-revocations，本次判定不受影响（" + GUIDE +
                                   "需要「新鲜」保证时加上该开关）")
        else:
            res["warnings"].append("吊销表未给有效期，无法判新鲜（" + GUIDE +
                                   "签发时加 --expires-at/--ttl；本次判定不受影响）")
        return False
    now = at or attest.issue_stamp()
    if state == "stale":
        res["issues"].append(f"吊销表已过期（expires_at={exp}，判定时点={now}）：无法证明"
                             "「当前未吊销」（" + GUIDE + "向签发方取 seq 更大的新 feed 重跑；"
                             "或去掉 --require-fresh-revocations 接受「新鲜度未知」）")
    else:
        res["issues"].append("吊销表未给有效期（无 expires_at/ttl）："
                             "--require-fresh-revocations 下无法证明新鲜（" + GUIDE +
                             "签发方补 --expires-at 或 --ttl 重签；或去掉开关）")
    res["verdict"] = "invalid"
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
           at: str = "", anchor: dict[str, Any] | None = None,
           expected_policy_digest: str = "",
           require_fresh_revocations: bool = False) -> dict[str, Any]:
    """校验证据包 → {verdict, level, root, head, issues, ...}。

    判定顺序固定（fail-closed，先失败先返回；**不**允许「证据弱就放行」）：
    结构 → 成员摘要 → 根 → 包含证明 → 链 → 信封 → 吊销 → 时效 → 吊销新鲜度。
    最后两段互相独立：`revoked > expired > 新鲜度不足(invalid) > ok`。
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
        res["issues"].extend(rd.issues)
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
        _check_chain(entries, meta, res)
        check_anchor(entries, meta, anchor, res)
        _check_extras(rd, entries, res["issues"])
        if res["issues"]:
            return res
        _check_attestations(rd, meta, entries, key, res)
        if res["issues"]:
            return res
        _check_decision(rd, meta, entries, res, expected_policy_digest)
        if res["issues"]:
            return res
        fresh: dict[str, Any] = {"state": "unknown", "expires_at": "", "basis": "none"}
        if _apply_revocation(rd, entries, revocations, res, fresh, at):
            return res
        if _apply_expiry(res, at):
            return res
        if _apply_freshness(res, require_fresh_revocations, at, fresh):
            return res
        res["verdict"] = "ok"
        return res
    finally:
        rd.close()


def _embedded_revocations(rd: _Reader) -> tuple[dict[str, Any] | None, str]:
    """包内吊销表 → (表 或 None, 错误文本)。

    **坏件不能当「无吊销」**（2026-11-04 实测）：旧实现把解析失败折成 None，于是「把吊销表
    写坏」就能让已吊销的证据判 ok——坏件冒充合格。现在坏件/形状不符一律返回错误，判定 invalid。
    """
    raw = rd.read(REVOCATIONS_ENTRY)
    if raw is None:
        return None, ""
    try:
        doc = json_doc.loads(raw.decode(), dict, what="吊销表")
    except (ValueError, UnicodeDecodeError) as exc:
        return None, (f"包内吊销表不可解析：{exc}（{GUIDE}吊销表坏件不能当「无吊销」——"
                      "请重新打包，或提供合法的 nf-revocation/1）")
    if str(doc.get("schema") or "") != REVOCATION_SCHEMA:
        got = doc.get("schema")
        return None, (f"包内吊销表 schema 不匹配（期望 {REVOCATION_SCHEMA}，实得 {got!r}）"
                      f"（{GUIDE}形状不对的吊销表不能当「无吊销」）")
    return doc, ""


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


# ------------------------------------------------------------------ 多形态复验
#
# cc_verify 的输入不是「只有一种包」：仓里同时存在三种可独立验证的证据形态——
#   1) bundle   : nf evidence pack 产出的自包含 zip（bundle.json + payload/ + attest/）
#   2) receipts : nf receipts --scope protocol --write 产出的 nf-receipts/1（单根 + 每条包含证明）
#   3) attest   : nf attest 产出的 nf-attest/1 / nf-attest-set/1（信封，可带 hmac/ssh/sigstore 锚）
# 三种都必须能**脱离仓库**判：只给「文档 + 成员实体」，不查生产环境、不联网。
# 形态由**内容**（schema 字段）决定，不由扩展名或文件名决定——判据不依赖命名约定。

def _check_extras(rd: _Reader, entries: Sequence[dict[str, Any]],
                  issues: list[str]) -> None:
    """包内多出未登记的成员 → invalid（多出来的字节没有回执背书，包就不干净）。"""
    listed = {PAYLOAD_DIR + _norm(str(e.get('path') or e.get('id') or '')) for e in entries}
    for name in rd.names():
        if name.startswith(PAYLOAD_DIR) and name not in listed:
            issues.append(f"包内多出未登记成员：{name}（{GUIDE}成员集必须与根一致——多出来的"
                          "字节没有回执背书，请去掉或重新 nf evidence pack）")


def _payload_find(read: Any, rel: str) -> bytes | None:
    """成员实体查找：先按原相对路径，再退化到 payload/ 前缀（bundle 形态用前缀）。"""
    for name in (rel, PAYLOAD_DIR + rel):
        data = read(name)
        if data is not None:
            return data
    return None


def _schema_of(raw: bytes | None) -> str:
    if raw is None:
        return ""
    try:
        doc = json_doc.loads(raw.decode(), dict, what="证据文档")
    except (ValueError, UnicodeDecodeError):
        return ""
    return str(doc.get("schema") or "") if isinstance(doc, dict) else ""


def _detect_container(rd: _Reader, kind: str = "") -> tuple[str, dict[str, Any]]:
    """容器（zip / 目录）→ (形态, 文档)。显式 --kind 时只做形状确认，不猜。"""
    if rd.read(BUNDLE_ENTRY) is not None:
        return "bundle", _load_meta(rd)
    found: dict[str, dict[str, Any]] = {}
    for name in [n for n in rd.names() if n.endswith(".json")]:
        raw = rd.read(name)
        schema = _schema_of(raw)
        if schema in (RECEIPTS_SCHEMA, ATTEST_SCHEMA, ATTEST_SET_SCHEMA) and schema not in found:
            try:
                found[schema] = json_doc.loads(raw.decode(), dict, what="证据文档")  # type: ignore[arg-type]
            except (ValueError, UnicodeDecodeError):
                continue
    for schema, form in ((RECEIPTS_SCHEMA, "receipts"), (ATTEST_SCHEMA, "attest"),
                         (ATTEST_SET_SCHEMA, "attest")):
        if schema in found and (not kind or kind == form):
            return form, found[schema]
    raise ValueError(f"认不出证据形态：{rd.path}（{GUIDE}请给 nf evidence pack 的 .zip、或含 "
                     "nf-receipts/1 · nf-attest/1 · nf-attest-set/1 的目录/JSON；形态以文档 "
                     "schema 字段判定，不看扩展名）")


def _dir_read(root: str) -> Any:
    """目录成员读取器（单 JSON + 根目录形态用）。"""
    def read(rel: str) -> bytes | None:
        full = os.path.join(root, *_norm(rel).split("/"))
        if not os.path.isfile(full):
            return None
        with open(full, "rb") as fh:
            return fh.read()
    return read


def _verify_receipts(doc: dict[str, Any], read: Any,
                     revocations: dict[str, Any] | None = None,
                     require_fresh_revocations: bool = False,
                     at: str = "") -> dict[str, Any]:
    """回执形态：成员摘要 → 叶 → 根 → 每条包含证明（不回查仓库）。"""
    res = _empty_result()
    res["kind"] = "receipts"
    issues = res["issues"]
    if str(doc.get("schema") or "") != RECEIPTS_SCHEMA:
        issues.append(f"回执 schema 不匹配（期望 {RECEIPTS_SCHEMA}）（{GUIDE}用 nf receipts "
                      "--scope protocol --write 重新生成）")
        return res
    entries = doc.get("entries") or []
    res["count"] = len(entries)
    res["root"] = str(doc.get("root") or "")
    if not entries:
        issues.append("回执为空（" + GUIDE + "空根不能证明任何事——请生成含成员的回执）")
        return res
    leaves: list[bytes] = []
    for e in entries:
        rel = _norm(str(e.get("id") or e.get("path") or ""))
        data = _payload_find(read, rel) if rel else None
        if data is None:
            issues.append(f"缺成员实体：{rel or '?'}（{GUIDE}回执只证明「根里有这条」，验它需要"
                          "成员字节——请把成员与回执放在同一根下，或用 nf evidence pack 打包）")
            continue
        digest = _sha256(data)
        want = str(e.get("digest") or "")
        if digest != want:
            issues.append(f"成员摘要不符：{rel}（记录={want[:16]} 实测={digest[:16]}）"
                          f"（{GUIDE}成员被改过——回执证明的就是字节，字节变了判定必红）")
        want_leaf = _leaf(rel, digest)
        if want_leaf != str(e.get("leaf") or ""):
            issues.append(f"叶复算不符：{rel}（{GUIDE}叶定义须与 receipts 同源；改动后请重签回执）")
        leaves.append(bytes.fromhex(want_leaf))
    if issues:
        return res
    _check_root(leaves, res)
    if issues:
        return res
    _check_proofs(entries, res)
    if issues:
        return res
    res["level"] = "receipts_only"
    fresh: dict[str, Any] = {"state": "unknown", "expires_at": "", "basis": "none"}
    if _apply_revocation_doc(revocations, entries, res, fresh, at):
        return res
    if _apply_freshness(res, require_fresh_revocations, at, fresh):
        return res
    res["verdict"] = "ok"
    return res


def _verify_attest(doc: dict[str, Any], read: Any, key: bytes | None = None,
                   revocations: dict[str, Any] | None = None,
                   at: str = "",
                   require_fresh_revocations: bool = False) -> dict[str, Any]:
    """信封形态：每份信封必须自洽且指向真实成员；level 取通过的最强一档。"""
    res = _empty_result()
    res["kind"] = "attest"
    issues = res["issues"]
    envs = doc.get("attestations") if str(doc.get("schema") or "") == ATTEST_SET_SCHEMA else [doc]
    if not isinstance(envs, list) or not envs:
        issues.append("信封集为空（" + GUIDE + "nf-attest-set/1 必须至少含一份信封）")
        return res
    res["count"] = len(envs)
    entries: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="nf_attestset_") as tmp:
        for env in envs:
            if not isinstance(env, dict):
                issues.append("信封不是对象（" + GUIDE + "重跑 nf attest --out 生成）")
                continue
            subj = _norm(str((env.get("subject") or {}).get("path") or ""))
            data = _payload_find(read, subj) if subj else None
            if data is None:
                issues.append(f"缺成员实体：{subj or '?'}（{GUIDE}信封只证明「这份内容被签过」，"
                              "验它需要内容本身——请把成员与信封放在同一根下）")
                continue
            digest = _sha256(data)
            entries.append({"path": subj, "digest": digest})
            full = os.path.join(tmp, *subj.split("/"))
            parent = os.path.dirname(full)
            if parent:
                os.makedirs(parent, exist_ok=True)
            with open(full, "wb") as fh:
                fh.write(data)
        if issues:
            return res
        passed: list[str] = []
        failed: list[str] = []
        for env in envs:
            ok, att_issues, level = attest.verify(env, tmp, key=key)
            passed.extend([level] if ok else [])
            failed.extend([] if ok else att_issues)
        if not passed:
            res["issues"].append(f"所有信封均未通过校验：{'；'.join(failed[:3]) or '无可用信封'}"
                                 f"（{GUIDE}hmac 级须提供同一密钥 --key-file；缺密钥一律拒绝）")
            return res
        res["level"] = max(passed, key=lambda lv: LEVELS.index(lv) if lv in LEVELS else -1)
        res["attestations_ok"] = len(passed)
    fresh: dict[str, Any] = {"state": "unknown", "expires_at": "", "basis": "none"}
    if _apply_revocation_doc(revocations, entries, res, fresh, at):
        return res
    if _apply_expiry(res, at):
        return res
    if _apply_freshness(res, require_fresh_revocations, at, fresh):
        return res
    res["verdict"] = "ok"
    return res


def _apply_revocation_doc(revocations: dict[str, Any] | None,
                          entries: Sequence[dict[str, Any]],
                          res: dict[str, Any], fresh: dict[str, Any],
                          at: str = "") -> bool:
    """无容器形态的吊销判定（吊销表由调用方给，不内嵌；同样吃表或签名 feed）。"""
    if revocations is None:
        return False
    table, feed, err = _revocation_source(revocations)
    res["revocations_source"] = "external"
    if err:
        res["issues"].append(err)
        return True
    fresh.update(revoc.freshness(feed, at) if feed is not None
                 else {"state": "unknown", "expires_at": "", "basis": "none"})
    res["revocations_fresh"] = fresh["state"]
    res["revocations_basis"] = fresh["basis"]
    hit = _revocation_hit(table, entries)
    if hit is None:
        return False
    why = hit.get("reason") or hit.get("path") or hit.get("digest") or "未给理由"
    res["verdict"] = "revoked"
    res["revoked_by"] = hit
    res["issues"].append(f"证据已被吊销：{why}（{GUIDE}吊销是不可逆判定——请向签发方确认"
                          "是否曾发生错签或内容下架，不要当临时失败重试）")
    return True


def verify_any(path: str, key: bytes | None = None,
               revocations: dict[str, Any] | None = None, at: str = "",
               root: str = "", kind: str = "",
               anchor: dict[str, Any] | None = None,
               expected_policy_digest: str = "",
               require_fresh_revocations: bool = False) -> dict[str, Any]:
    """cc_verify 的统一入口：自动判三种形态并给出同一套四词判定。

    - 容器（.zip / 目录）按内容判形态；单 JSON 按 schema 判形态，成员从 `root` 找
      （缺省 = 该 JSON 所在目录）。
    - 判定词表与退出码对所有形态一致：ok / revoked / expired / invalid。
    """
    if os.path.isfile(path) and not zipfile.is_zipfile(path):
        res = _verify_single_json(path, key, revocations, at, root, kind,
                                  require_fresh_revocations)
        form = "bundle" if str(res.get("kind") or "") == "bundle" else "other"
    else:
        rd = _Reader(path)
        try:
            form, doc = _detect_container(rd, kind)
            if form == "bundle":
                return verify(path, key=key, revocations=revocations, at=at, anchor=anchor,
                              expected_policy_digest=expected_policy_digest,
                              require_fresh_revocations=require_fresh_revocations)
            if form == "receipts":
                res = _verify_receipts(doc, rd.read, revocations,
                                       require_fresh_revocations, at)
            else:
                res = _verify_attest(doc, rd.read, key, revocations, at,
                                     require_fresh_revocations)
        finally:
            rd.close()
    if expected_policy_digest and form != "bundle":
        res["warnings"].append("该证据形态不含 decision，无法比对策略（只证字节与信封）")
    return res


def _verify_single_json(path: str, key: bytes | None, revocations: dict[str, Any] | None,
                        at: str, root: str, kind: str,
                        require_fresh_revocations: bool = False) -> dict[str, Any]:
    with open(path, "rb") as fh:
        raw = fh.read()
    try:
        doc = json_doc.loads(raw.decode(), dict, what="证据文档")
    except (ValueError, UnicodeDecodeError) as exc:
        raise ValueError(f"不是合法 UTF-8 JSON：{path}（{exc}）（{GUIDE}请给 nf receipts / "
                         "nf attest 产出的 JSON，或 nf evidence pack 的 .zip）") from exc
    if not isinstance(doc, dict):
        raise ValueError(f"证据文档不是对象：{path}（{GUIDE}请给带 schema 字段的证据 JSON）")
    schema = str(doc.get("schema") or "")
    base = root or os.path.dirname(os.path.abspath(path)) or "."
    read = _dir_read(base)
    if schema == RECEIPTS_SCHEMA and (not kind or kind == "receipts"):
        return _verify_receipts(doc, read, revocations, require_fresh_revocations, at)
    if schema in (ATTEST_SCHEMA, ATTEST_SET_SCHEMA) and (not kind or kind == "attest"):
        return _verify_attest(doc, read, key, revocations, at, require_fresh_revocations)
    raise ValueError(f"认不出证据形态：{path}（schema={schema or '缺失'}）"
                     "（修复指引：请对照支持的四种——nf-evidence/1 容器、nf-receipts/1、"
                     "nf-attest/1、nf-attest-set/1；形态以文档 schema 字段判定）")


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


# ------------------------------------------------------------------ 复现轨迹（cc_replay）
#
# 把「这条证据是怎么算出来的」摊成确定性 trace：每一步给规则名 + 输入摘要 + 输出摘要。
# 用途不是重新执行生产，而是让第三方**逐步复核**——每一步都能自己重算，错在哪一步一眼可见。
# 稳定性：trace 不含时间戳，同输入两次 replay 逐字节一致（可 diff）。

REPLAY_SCHEMA = "nf-replay/1"


def _open_source(path: str, root: str = "",
                 kind: str = "") -> tuple[str, dict[str, Any], Any, Any]:
    """→ (形态, 文档, read(rel), close())。容器与单 JSON 统一读面。"""
    if os.path.isfile(path) and not zipfile.is_zipfile(path):
        with open(path, "rb") as fh:
            raw = fh.read()
        try:
            doc = json_doc.loads(raw.decode(), dict, what="证据文档")
        except (ValueError, UnicodeDecodeError) as exc:
            raise ValueError(f"不是合法 UTF-8 JSON：{path}（{exc}）"
                             f"（{GUIDE}请给证据 JSON 或证据包 .zip）") from exc
        schema = str(doc.get("schema") or "") if isinstance(doc, dict) else ""
        form = {RECEIPTS_SCHEMA: "receipts", ATTEST_SCHEMA: "attest",
                ATTEST_SET_SCHEMA: "attest"}.get(schema, "")
        if not form:
            raise ValueError(f"认不出证据形态：{path}（schema={schema or '缺失'}）"
                             f"（{GUIDE}请给 nf-receipts/1 · nf-attest/1 · nf-attest-set/1）")
        base = root or os.path.dirname(os.path.abspath(path)) or "."
        return form, doc, _dir_read(base), (lambda: None)
    rd = _Reader(path)
    form, doc = _detect_container(rd, kind)
    return form, doc, rd.read, rd.close


def _trace_member(e: dict[str, Any], read: Any, issues: list[str],
                  seen: set[str]) -> dict[str, Any] | None:
    """单个成员的推导链：字节 → 摘要 → 叶 → 证明折叠。返回 trace 段或 None。"""
    rel = _norm(str(e.get("path") or e.get("id") or ""))
    if not rel:
        issues.append("回执条目缺 path/id（" + GUIDE + "请重新生成回执）")
        return None
    if rel in seen:
        issues.append(f"成员重复出现：{rel}（{GUIDE}同一成员不许在证据里出现两次）")
        return None
    seen.add(rel)
    data = _payload_find(read, rel)
    if data is None:
        issues.append(f"缺成员实体：{rel}（{GUIDE}请把成员实体放进证据包/成员根）")
        return None
    digest = _sha256(data)
    leaf = _leaf(rel, digest)
    steps: list[dict[str, Any]] = [
        {"step": 1, "rule": "sha256-bytes", "subject": rel,
         "input": f"{len(data)} bytes", "output": digest},
        {"step": 2, "rule": "rfc6962-leaf", "subject": rel,
         "input": canonical({"id": rel, "digest": digest}).hex()[:32] + "…",
         "output": leaf},
    ]
    cur = leaf
    for i, step in enumerate(e.get("proof") or [], 1):
        side = str(step.get("side") or "")
        sibling = str(step.get("hash") or "")
        nxt = receipts.fold_proof(cur, [{"side": side, "hash": sibling}])
        steps.append({"step": 2 + i, "rule": "rfc6962-fold", "subject": rel,
                      "input": f"{side}:{sibling[:16]}… 折叠自 {cur[:16]}…",
                      "output": nxt})
        cur = nxt
    recorded = str(e.get("leaf") or "")
    if recorded and recorded != leaf:
        issues.append(f"叶复算不符：{rel}（记录={recorded[:16]} 实测={leaf[:16]}）"
                      f"（{GUIDE}叶定义须与 receipts 同源；证据被改过就重打）")
    return {"path": rel, "digest": digest, "leaf": leaf, "folded": cur,
            "steps": steps}


def _replay_bundle(doc: dict[str, Any], read: Any, entry: str,
                   key: bytes | None) -> dict[str, Any]:
    """包形态：成员链 + 链头 + 信封面。"""
    issues: list[str] = []
    entries = doc.get("entries") or []
    res: dict[str, Any] = {"root": str(doc.get("root") or ""),
                           "head": str((doc.get("chain") or {}).get("head") or ""),
                           "count": len(entries), "entries": [], "issues": issues}
    want = _norm(entry) if entry else ""
    leaves: list[bytes] = []
    prev = "0" * 64
    seen: set[str] = set()
    for e in entries:
        trace = _trace_member(e, read, issues, seen)
        if trace is None:
            return res
        leaves.append(bytes.fromhex(str(trace["leaf"])))
        node = hashlib.sha256(NODE_PREFIX + b"|" + prev.encode("ascii") + b"|"
                              + str(trace["leaf"]).encode("ascii")).hexdigest()
        trace["steps"].append({"step": len(trace["steps"]) + 1,
                               "rule": "nf-hashchain",
                               "subject": trace["path"],
                               "input": prev[:16] + "…", "output": node})
        prev = node
        if not want or trace["path"] == want:
            res["entries"].append(trace)
    res["recomputed_root"] = (receipts.merkle_root(leaves) or b"").hex()
    res["recomputed_head"] = prev
    if res["recomputed_root"] != res["root"]:
        issues.append(f"根不一致：记录={res['root'][:16]} 实测="
                      f"{res['recomputed_root'][:16]}（{GUIDE}成员集被增删或改序）")
    if not res["head"]:
        issues.append("缺 chain 段（" + GUIDE + "轨迹无法证明条目顺序——"
                      "请用 nf evidence pack 重新打包，缺证据不等于没问题）")
    elif res["recomputed_head"] != res["head"]:
        issues.append("链头不一致（" + GUIDE + "条目顺序被插删/改序）")
    if want and not res["entries"]:
        issues.append(f"证据里没有该成员：{entry}（{GUIDE}请核对相对路径写法）")
    return res


def _replay_receipts(doc: dict[str, Any], read: Any, entry: str) -> dict[str, Any]:
    """回执形态：成员链 → 根（无信封、无链头）。"""
    issues: list[str] = []
    entries = doc.get("entries") or []
    res: dict[str, Any] = {"root": str(doc.get("root") or ""), "head": "",
                           "count": len(entries), "entries": [], "issues": issues}
    want = _norm(entry) if entry else ""
    leaves: list[bytes] = []
    seen: set[str] = set()
    for e in entries:
        item = ({"path": e.get("id"), "digest": e.get("digest"),
                 "leaf": e.get("leaf"), "proof": e.get("proof")})
        trace = _trace_member(item, read, issues, seen)
        if trace is None:
            return res
        leaves.append(bytes.fromhex(str(trace["leaf"])))
        if not want or trace["path"] == want:
            res["entries"].append(trace)
    res["recomputed_root"] = (receipts.merkle_root(leaves) or b"").hex()
    res["recomputed_head"] = ""
    if res["recomputed_root"] != res["root"]:
        issues.append(f"根不一致：记录={res['root'][:16]} 实测="
                      f"{res['recomputed_root'][:16]}（{GUIDE}成员集被增删或改序）")
    if want and not res["entries"]:
        issues.append(f"回执里没有该成员：{entry}（{GUIDE}请核对编号写法）")
    return res


def _replay_attest(doc: dict[str, Any], read: Any, entry: str,
                   key: bytes | None) -> dict[str, Any]:
    """信封形态：主体摘要 → 信封摘要 → （可选）hmac。"""
    issues: list[str] = []
    if str(doc.get("schema") or "") == ATTEST_SET_SCHEMA:
        envs = doc.get("attestations") or []
    else:
        envs = [doc]
    res: dict[str, Any] = {"root": "", "head": "", "count": len(envs),
                           "entries": [], "issues": issues}
    want = _norm(entry) if entry else ""
    for env in envs:
        if not isinstance(env, dict):
            issues.append("信封不是对象（" + GUIDE + "请重新 nf attest --out）")
            continue
        subj = env.get("subject") or {}
        rel = _norm(str(subj.get("path") or ""))
        data = _payload_find(read, rel) if rel else None
        if data is None:
            issues.append(f"缺成员实体：{rel or '?'}（{GUIDE}请把成员放进成员根）")
            continue
        steps = [{"step": 1, "rule": "sha256-bytes", "subject": rel,
                  "input": f"{len(data)} bytes", "output": _sha256(data)}]
        base = {k: env.get(k) for k in ("schema", "subject", "producer", "issued_at")}
        digest_env = _sha256(canonical(base))
        steps.append({"step": 2, "rule": "nf-attest-envelope", "subject": rel,
                      "input": canonical(base).hex()[:32] + "…",
                      "output": digest_env})
        sig = env.get("signature") or {}
        if sig.get("scheme") == "hmac-sha256" and key:
            mac = hmac.new(key, digest_env.encode("utf-8"), hashlib.sha256).hexdigest()
            steps.append({"step": 3, "rule": "hmac-sha256", "subject": rel,
                          "input": digest_env[:16] + "…", "output": mac})
            if mac != str(sig.get("mac") or ""):
                issues.append(f"hmac 不匹配：{rel}（{GUIDE}密钥不符或信封被改）")
        if digest_env != str(env.get("envelope_digest") or ""):
            issues.append(f"信封摘要不一致：{rel}（{GUIDE}信封被改动）")
        if not want or rel == want:
            res["entries"].append({"path": rel, "digest": _sha256(data),
                                   "leaf": digest_env, "steps": steps})
    if want and not res["entries"]:
        issues.append(f"信封里没有该主体：{entry}（{GUIDE}请核对相对路径写法）")
    return res


def replay(target: str, entry: str = "", key: bytes | None = None,
           root: str = "", kind: str = "") -> dict[str, Any]:
    """把证据的推导过程摊成确定性 trace；`ok` = 每一步都复算得出且与记录一致。"""
    form, doc, read, close = _open_source(target, root, kind)
    try:
        if form == "bundle":
            res = _replay_bundle(doc, read, entry, key)
        elif form == "receipts":
            res = _replay_receipts(doc, read, entry)
        else:
            res = _replay_attest(doc, read, entry, key)
    finally:
        close()
    res["schema"] = REPLAY_SCHEMA
    res["kind"] = form
    res["target"] = target.replace("\\", "/")
    res["ok"] = not res["issues"]
    return res

# ------------------------------------------------------------------ 攻击矩阵基准 v0
#
# 目的：把「抓不到篡改的校验器就是摆设」变成**可复跑的数字**。对同一份金丝雀证据包施加
# 25 种已知攻击/退化（改字节、换成员、删证明、改根、改链、改信封、错密钥、良性重排…），
# 逐条比对「期望判定 vs 实际判定」。任何一条不达期望 = 复验器有洞，基准当场红。
#
# 这是**自测基准**，不是安全证明：它证明「这些已知攻击都判得出来」，不证明「所有攻击都
# 判得出来」——不可抵赖与可信时间戳仍需第三方见证，见包内 boundary 声明。

BENCH_SCHEMA = "nf-evidence-bench/1"
BENCH_KEY = b"nf-evidence-bench-key-0123456789"
BENCH_PIN = "2026-01-01T00:00:00Z"


def _members(data: bytes) -> dict[str, bytes]:
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        return {n: zf.read(n) for n in zf.namelist()}


def _rebuild(members: dict[str, bytes]) -> bytes:
    return _zip_bytes(list(members.items()))


def _mut_meta(data: bytes, fn: Any) -> bytes:
    """改清单后重打包（fn(meta) 原地改）。"""
    members = _members(data)
    meta = json_doc.loads(members[BUNDLE_ENTRY].decode(), dict, what="bundle.json")
    fn(meta)
    members[BUNDLE_ENTRY] = _json_bytes(meta)
    return _rebuild(members)


def _zip_unsorted(members: dict[str, bytes]) -> bytes:
    """良性重排：成员顺序打乱 + 时间戳变化（判定不该因此变化）。"""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_STORED) as zf:
        for name in sorted(members, reverse=True):
            zi = zipfile.ZipInfo(name, date_time=(2026, 1, 2, 3, 4, 6))
            zi.compress_type = zipfile.ZIP_STORED
            zf.writestr(zi, members[name])
    return buf.getvalue()


def _bench_write(tmp: str, name: str, data: bytes) -> str:
    path = os.path.join(tmp, name)
    with open(path, "wb") as fh:
        fh.write(data)
    return path


def _bench_run(rows: list[dict[str, Any]], cid: str, desc: str, expected: str,
               path: str, key: bytes | None = BENCH_KEY,
               revocations: dict[str, Any] | None = None, at: str = "",
               anchor: dict[str, Any] | None = None) -> None:
    """跑一条用例并记账（认不出形态也记 invalid——判定面外不算通过）。"""
    try:
        actual = verify(path, key=key, revocations=revocations, at=at,
                        anchor=anchor)["verdict"]
    except ValueError:
        actual = "invalid"
    rows.append({"id": cid, "desc": desc, "expected": expected,
                 "actual": actual, "ok": actual == expected})


def _drop_entry(meta: dict[str, Any]) -> None:
    meta["entries"] = meta["entries"][:-1]


def _flip_proof(meta: dict[str, Any]) -> None:
    proof = meta["entries"][0].get("proof") or []
    if proof:
        proof[0]["side"] = "left" if proof[0].get("side") == "right" else "right"


def _truncate_proof(meta: dict[str, Any]) -> None:
    meta["entries"][0]["proof"] = []


def _empty_head(meta: dict[str, Any]) -> None:
    meta["chain"]["head"] = ""


def _swap_entries(meta: dict[str, Any]) -> None:
    entries = meta["entries"]
    entries[0], entries[-1] = entries[-1], entries[0]


def _bump_subject(env: dict[str, Any]) -> None:
    (env.get("subject") or {})["sha256"] = "0" * 64


def _bump_mac(env: dict[str, Any]) -> None:
    (env.get("signature") or {})["mac"] = "0" * 64


def _mut_attest(data: bytes, fn: Any) -> bytes:
    """改第一份信封后重打包（fn(env) 原地改）。"""
    members = _members(data)
    env = json_doc.loads(members[ATTEST_DIR + "0001.json"].decode(), dict, what="信封")
    fn(env)
    members[ATTEST_DIR + "0001.json"] = _json_bytes(env)
    return _rebuild(members)


def bench() -> dict[str, Any]:
    """跑攻击矩阵 → {schema, cases, passed, failed, total, ok}。"""
    rows: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="nf_bench_") as tmp:
        os.makedirs(os.path.join(tmp, "d"), exist_ok=True)
        for name, body in (("a.md", "# A\n\n甲\n"), ("b.md", "# B\n\n乙\n"),
                           ("c.md", "# C\n\n丙\n")):
            with open(os.path.join(tmp, "d", name), "wb") as fh:
                fh.write(body.encode())
        base, _info = build(tmp, ["d/a.md", "d/b.md"], issuer="bench",
                            created_at=BENCH_PIN, key=BENCH_KEY)
        members = _members(base)
        digest_a = _sha256(members[PAYLOAD_DIR + "d/a.md"])
        base_path = _bench_write(tmp, "base.zip", base)
        # 正例与良性变化
        _bench_run(rows, "pass", "完好证据包必过", "ok", base_path)
        ddir = os.path.join(tmp, "unpacked")
        os.makedirs(ddir, exist_ok=True)
        with zipfile.ZipFile(base_path) as zf:
            zf.extractall(ddir)
        _bench_run(rows, "pass_dir", "解包目录形态等价", "ok", ddir)
        _bench_run(rows, "benign_reorder", "成员重排/时间戳变化不影响判定", "ok",
                   _bench_write(tmp, "reorder.zip", _zip_unsorted(members)))
        # 成员面
        m = dict(members)
        payload = members[PAYLOAD_DIR + "d/a.md"]
        m[PAYLOAD_DIR + "d/a.md"] = "# A\n\n甲改\n".encode()
        _bench_run(rows, "payload_flip", "成员字节被改", "invalid",
                   _bench_write(tmp, "flip.zip", _rebuild(m)))
        m = dict(members)
        m[PAYLOAD_DIR + "d/a.md"] = payload[:4]
        _bench_run(rows, "payload_truncate", "成员被截断", "invalid",
                   _bench_write(tmp, "trunc.zip", _rebuild(m)))
        m = dict(members)
        m[PAYLOAD_DIR + "d/a.md"] = b"X" * len(payload)
        _bench_run(rows, "payload_same_size", "等长替换（摘要必须变）", "invalid",
                   _bench_write(tmp, "samesize.zip", _rebuild(m)))
        m = dict(members)
        m.pop(PAYLOAD_DIR + "d/b.md")
        _bench_run(rows, "payload_removed", "成员实体缺失", "invalid",
                   _bench_write(tmp, "pop.zip", _rebuild(m)))
        m = dict(members)
        m[PAYLOAD_DIR + "d/sneak.md"] = b"# sneak\n"
        _bench_run(rows, "payload_extra", "夹带未登记成员", "invalid",
                   _bench_write(tmp, "extra.zip", _rebuild(m)))
        # 清单面
        _bench_run(rows, "manifest_digest", "清单里的摘要被改", "invalid",
                   _bench_write(tmp, "mdig.zip", _mut_meta(
                       base, lambda meta: meta["entries"][0].__setitem__("digest", "0" * 64))))
        _bench_run(rows, "manifest_root", "清单里的根被改", "invalid",
                   _bench_write(tmp, "mroot.zip", _mut_meta(
                       base, lambda meta: meta.__setitem__("root", "0" * 64))))
        _bench_run(rows, "manifest_leaf", "清单里的叶被改", "invalid",
                   _bench_write(tmp, "mleaf.zip", _mut_meta(
                       base, lambda meta: meta["entries"][0].__setitem__("leaf", "0" * 64))))
        _bench_run(rows, "manifest_drop_entry", "清单删条但实体仍在", "invalid",
                   _bench_write(tmp, "mdrop.zip", _mut_meta(base, _drop_entry)))
        # 证明 / 链
        _bench_run(rows, "proof_flip", "包含证明被翻面", "invalid",
                   _bench_write(tmp, "pflip.zip", _mut_meta(base, _flip_proof)))
        _bench_run(rows, "proof_truncate", "包含证明被截断", "invalid",
                   _bench_write(tmp, "ptrunc.zip", _mut_meta(base, _truncate_proof)))
        _bench_run(rows, "chain_head", "链头被改", "invalid",
                   _bench_write(tmp, "chead.zip", _mut_meta(
                       base, lambda meta: meta["chain"].__setitem__("head", "0" * 64))))
        _bench_run(rows, "chain_order", "条目顺序被换（链可证顺序）", "invalid",
                   _bench_write(tmp, "corder.zip", _mut_meta(base, _swap_entries)))
        _bench_run(rows, "chain_missing", "chain 段被整体删除（缺证据≠证据成立）", "invalid",
                   _bench_write(tmp, "chnone.zip",
                                _mut_meta(base, lambda meta: meta.pop("chain", None))))
        _bench_run(rows, "chain_head_empty", "链头被置空", "invalid",
                   _bench_write(tmp, "chzero.zip",
                                _mut_meta(base, _empty_head)))
        _bench_run(rows, "chain_count_wrong", "链条数与成员数不符", "invalid",
                   _bench_write(tmp, "chcnt.zip",
                                _mut_meta(base, lambda meta: meta["chain"]
                                          .__setitem__("count", 99))))
        # 决策证据（Q0）：正例 + 两条攻击（换策略摘要 / 删声明面）
        dec = {"syscall": "cc_check",
               "policy_digest": _sha256(b"nf-check-policy/1:bench"),
               "verdict": "ok", "object_sha256": digest_a}
        dec_bundle, _dec_info = build(tmp, ["d/a.md", "d/b.md"], issuer="bench",
                                      created_at=BENCH_PIN, decision=dec)
        _bench_run(rows, "decision_ok", "决策证据自洽（digest_only → declared）", "ok",
                   _bench_write(tmp, "decbase.zip", dec_bundle))
        _bench_run(rows, "decision_policy_swap", "换策略摘要（声明面与绑定面不一致）", "invalid",
                   _bench_write(tmp, "decswap.zip", _mut_meta(
                       dec_bundle,
                       lambda meta: meta["decision"].__setitem__("policy_digest", "1" * 64))))
        _bench_run(rows, "decision_strip", "删声明面（绑定面仍在）", "invalid",
                   _bench_write(tmp, "decstrip.zip",
                                _mut_meta(dec_bundle, lambda meta: meta.pop("decision", None))))
        m = dict(members)
        m[REVOCATIONS_ENTRY] = b"{not json"
        _bench_run(rows, "traversal_path", "成员路径含双点段（验证即任意写的入口）", "invalid",
                   _bench_write(tmp, "trav.zip", _mut_meta(
                       base, lambda meta: meta["entries"][0].update(
                           {"path": "../escape.md", "id": "../escape.md"}))))
        dup_zip = os.path.join(tmp, "dupym.zip")
        # 造重名 zip 时 zipfile 会发 UserWarning（"Duplicate name"）到 stderr；机器面比对要求
        # 直跑与守护逐字节一致，这条噪声必须在这里消掉（不是屏蔽判据，是屏蔽构造期提示）。
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            with zipfile.ZipFile(dup_zip, "w", zipfile.ZIP_STORED) as zf:
                for name, raw in sorted(_members(base).items()):
                    zi = zipfile.ZipInfo(name, date_time=_ZIP_EPOCH)
                    zf.writestr(zi, raw)
                zi = zipfile.ZipInfo(PAYLOAD_DIR + "d/a.md", date_time=_ZIP_EPOCH)
                zf.writestr(zi, b"shadow")
        _bench_run(rows, "dup_members", "重名成员（zip 歧义：判定不可复算）", "invalid", dup_zip)
        _bench_run(rows, "revocations_bad", "包内吊销表写坏（坏件不能当「无吊销」）", "invalid",
                   _bench_write(tmp, "revbad.zip", _rebuild(m)))
        # 信封 / 密钥 / 结构
        m = dict(members)
        m.pop(ATTEST_DIR + "0001.json")
        _bench_run(rows, "attest_removed", "信封实体缺失", "invalid",
                   _bench_write(tmp, "natt.zip", _rebuild(m)))
        _bench_run(rows, "attest_subject_sha", "信封主体摘要被改", "invalid",
                   _bench_write(tmp, "asub.zip", _mut_attest(base, _bump_subject)))
        _bench_run(rows, "attest_mac", "hmac 签名被改", "invalid",
                   _bench_write(tmp, "amac.zip", _mut_attest(base, _bump_mac)))
        _bench_run(rows, "no_key", "hmac 级缺密钥（不降级）", "invalid", base_path,
                   key=None)
        _bench_run(rows, "wrong_key", "hmac 级错密钥", "invalid", base_path,
                   key=b"wrong-key-wrong-key-wrong-key")
        _bench_run(rows, "schema_bumped", "包版本被改", "invalid",
                   _bench_write(tmp, "schema.zip", _mut_meta(
                       base, lambda meta: meta.__setitem__("schema", "nf-evidence/99"))))
        notzip = os.path.join(tmp, "notzip.bin")
        with open(notzip, "wb") as fh:
            fh.write(b"just a file")
        _bench_run(rows, "not_a_bundle", "不是证据包", "invalid", notzip)
        # 判定面（吊销 / 时效）
        rev = {"schema": REVOCATION_SCHEMA,
               "revoked": [{"digest": digest_a, "revoked_at": BENCH_PIN,
                             "reason": "bench"}]}
        _bench_run(rows, "revoked", "吊销表命中必须压过 ok", "revoked", base_path,
                   revocations=rev)
        expired, _x = build(tmp, ["d/a.md", "d/b.md"], issuer="bench",
                            created_at=BENCH_PIN, key=BENCH_KEY,
                            expires_at="2020-01-01T00:00:00Z")
        _bench_run(rows, "expired", "有效期已过", "expired",
                   _bench_write(tmp, "expired.zip", expired))
        # 外部锚点（G1：防整链截断）
        head2 = {"count": 2, "head": verify(base_path, key=BENCH_KEY)["head"]}
        v3, _i3 = build(tmp, ["d/a.md", "d/b.md", "d/c.md"], issuer="bench",
                        created_at=BENCH_PIN, key=BENCH_KEY, anchor=head2)
        v3_path = _bench_write(tmp, "v3.zip", v3)
        _bench_run(rows, "anchor_ok", "锚点对得上（正常追加，不得误杀）", "ok", v3_path,
                   anchor=head2)
        head3 = {"count": 3, "head": verify(v3_path, key=BENCH_KEY)["head"]}
        _bench_run(rows, "anchor_truncated", "用更早的包冒充现在（整链截断）", "invalid",
                   base_path, anchor=head3)
        _bench_run(rows, "anchor_forked", "锚点来自另一条链（历史被改写）", "invalid",
                   v3_path, anchor={"count": 2, "head": "0" * 64})
        _bench_run(rows, "anchor_bad_shape", "锚点材料形状不对", "invalid", v3_path,
                   anchor={"count": "two", "head": ""})
    passed = sum(1 for r in rows if r["ok"])
    return {"schema": BENCH_SCHEMA, "cases": rows, "passed": passed,
            "failed": len(rows) - passed, "total": len(rows),
            "ok": passed == len(rows)}


def bench_markdown(res: dict[str, Any]) -> str:
    """把基准结果渲染成可直接贴进报告的表（确定性输出）。"""
    lines = ["# 证据复验器攻击矩阵基准 v0", "",
             f"用例 {res['total']} 条 · 通过 {res['passed']} · 失败 {res['failed']} · "
             f"结论 {'PASS' if res['ok'] else 'FAIL'}", "",
             "| # | 用例 | 攻击 / 变化 | 期望 | 实际 | 结果 |",
             "|---|---|---|---|---|---|"]
    for i, r in enumerate(res["cases"], 1):
        mark = "✓" if r["ok"] else "✗"
        lines.append(f"| {i} | {r['id']} | {r['desc']} | {r['expected']} | "
                     f"{r['actual']} | {mark} |")
    lines.append("")
    lines.append("边界：本基准证明「这些已知攻击都判得出来」，**不**证明「所有攻击都判得"
                 "出来」；不可抵赖与可信时间戳仍需第三方见证，见证据包 boundary 声明。")
    return "\n".join(lines) + "\n"
