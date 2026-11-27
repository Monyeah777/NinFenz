"""evidence · _build（自 evidence.py 拆出；只移动代码，行为/文案不变）。"""
from __future__ import annotations

import io
import os
import tempfile
import zipfile
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from core import attest, receipts

from ._const import (
    _ZIP_EPOCH,
    ATTEST_DIR,
    BUNDLE_ENTRY,
    GUIDE,
    PAYLOAD_DIR,
    REVOCATIONS_ENTRY,
    SCHEMA,
)
from ._primitives import (
    _chain_head,
    _json_bytes,
    _norm,
    _sha256,
)

# ------------------------------------------------------------------ 打包

@dataclass(frozen=True)
class BuildOptions:
    """参数对象（审计 C-007：把成组参数收成不可变对象）。"""
    issuer: str = ''
    key: bytes | None = None
    expires_at: str = ''
    created_at: str = ''
    revocations: dict[str, Any] | None = None
    anchor: dict[str, Any] | None = None
    decision: dict[str, Any] | None = None


def build(
    root: str,
    targets: Sequence[str],
    opts: BuildOptions | None = None,
) -> tuple[bytes, dict[str, Any]]:
    """把目标文件打成自包含证据包 → (zip 字节, 摘要信息)。

    - 回执与根：receipts.build_scope（本模块只排序去重，公式不复制）
    - 信封：每条目标一份 attest；给了密钥即 hmac-sha256 级（不给 = digest_only）
    - 链头：按回执条目顺序折叠（append-only 顺序可证，不可抵赖**不**由本包提供）
    - decision（可选，Q0）：绑定「过过哪条策略」；声明面放 bundle.json，
      绑定面放进 object_sha256 相符的那份信封（纳入信封摘要；旧包无此键不受影响）
    """

    opts = opts if opts is not None else BuildOptions()
    issuer = opts.issuer
    key = opts.key
    expires_at = opts.expires_at
    created_at = opts.created_at
    revocations = opts.revocations
    anchor = opts.anchor
    decision = opts.decision
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
    meta = _manifest(
        doc['root'],
        entries,
        atts,
        opts=ManifestOptions(
            created_at=created_at,
            issuer=issuer,
            key=key,
            expires_at=str(expires_at or ''),
            has_rev=revocations is not None,
            anchor=anchor,
            decision=decision,
        ),
    )
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




@dataclass(frozen=True)
class ManifestOptions:
    """参数对象（审计 C-007：把成组参数收成不可变对象）。"""
    created_at: str
    issuer: str
    key: bytes | None
    expires_at: str
    has_rev: bool
    anchor: dict[str, Any] | None = None
    decision: dict[str, Any] | None = None


def _manifest(
    root_digest: str,
    entries: Sequence[dict[str, Any]],
    atts: list[str],
    opts: ManifestOptions,
) -> dict[str, Any]:
    created_at = opts.created_at
    issuer = opts.issuer
    key = opts.key
    expires_at = opts.expires_at
    has_rev = opts.has_rev
    anchor = opts.anchor
    decision = opts.decision
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
            # 跨平台确定性：ZipInfo.create_system 默认值在 Windows(0) 与 Linux(3) 不同，
            # 同一份成员在两岸生成的 zip 字节不同、证据包 digest 会漂——固定 0（合并自 main）。
            zi.create_system = 0
            zf.writestr(zi, data)
    return buf.getvalue()




def default_out() -> str:
    """缺省落点：系统临时目录的 nf-evidence.zip（**不往仓库里写**）。

    为什么（2026-11-04 实测）：缺省落到仓根时，nf evidence pack 被 CLI 泛测以零参数调用，
    直接在仓库根造出 evidence.zip——仓内纪律是「产物不进仓」，于是缺省改到临时目录；
    要进仓的落点由调用方用 --out 显式给出。
    """
    return os.path.join(tempfile.gettempdir(), "nf-evidence.zip")
