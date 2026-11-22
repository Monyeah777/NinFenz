"""M25 Capability-Scoped Sharing 参考原型。

只判定只读/评论/再装配/导出/分享与到期/撤销；不涉及网络或密码学。
"""

from __future__ import annotations

from dataclasses import dataclass, field

CAPABILITIES = frozenset({"read", "comment", "reassemble", "export", "share"})


@dataclass(frozen=True)
class Grant:
    caps: frozenset[str] = field(default_factory=frozenset)
    expires_at: int | None = None
    revoked: bool = False


def normalize(caps) -> frozenset[str]:
    out = frozenset(caps)
    unknown = out - CAPABILITIES - {"admin"}
    if unknown:
        raise ValueError("未知能力：" + ", ".join(sorted(unknown)))
    return out


def allows(grant: Grant, cap: str, now: int) -> bool:
    if cap not in CAPABILITIES:
        return False
    if grant.revoked:
        return False
    if grant.expires_at is not None and now >= grant.expires_at:
        return False
    caps = normalize(grant.caps)
    return "admin" in caps or cap in caps
