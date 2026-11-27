"""core.evidence 私有实现分片 1/2（对外只经 core.evidence 门面导入）：write、_members 等"""

from __future__ import annotations

import io
import os
import zipfile
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from core import atomic_write, json_doc
from core._evidence._build import BuildOptions, _zip_bytes, build
from core._evidence._const import ATTEST_DIR, BENCH_KEY, BUNDLE_ENTRY
from core._evidence._primitives import _json_bytes
from core._evidence._verify_forms import VerifyOptions, verify


def write(
    root: str,
    out: str,
    targets: Sequence[str],
    opts: BuildOptions | None = None,
) -> tuple[str, dict[str, Any]]:
    """打包并落盘（单一写出处；调用方负责输出路径口径）。"""

    opts = opts if opts is not None else BuildOptions()
    issuer = opts.issuer
    key = opts.key
    expires_at = opts.expires_at
    created_at = opts.created_at
    revocations = opts.revocations
    anchor = opts.anchor
    decision = opts.decision
    data, info = build(
        root,
        targets,
        opts=BuildOptions(
            issuer=issuer,
            key=key,
            expires_at=expires_at,
            created_at=created_at,
            revocations=revocations,
            anchor=anchor,
            decision=decision,
        ),
    )
    dest = out if os.path.isabs(out) else os.path.join(root, out)
    parent = os.path.dirname(dest)
    if parent:
        os.makedirs(parent, exist_ok=True)
    # 在仓落点走原子写出：半截证据包比没有更危险（读者会把它当完整件验）
    atomic_write.write_bytes(dest, data)
    return dest, info


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


@dataclass(frozen=True)
class _BenchOptions:
    """参数对象（审计 C-007：把成组参数收成不可变对象）。"""
    key: bytes | None = BENCH_KEY
    revocations: dict[str, Any] | None = None
    at: str = ''
    anchor: dict[str, Any] | None = None


def _bench_run(
    rows: list[dict[str, Any]],
    cid: str,
    desc: str,
    expected: str,
    path: str,
    opts: _BenchOptions | None = None,
) -> None:
    """跑一条用例并记账（认不出形态也记 invalid——判定面外不算通过）。"""

    opts = opts if opts is not None else _BenchOptions()
    key = opts.key
    revocations = opts.revocations
    at = opts.at
    anchor = opts.anchor
    try:
        actual = verify(path, opts=VerifyOptions(key=key, revocations=revocations, at=at, anchor=anchor))["verdict"]
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
