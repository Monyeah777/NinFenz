"""evidence · _verify_forms_parts（自 _verify_forms 拆出的形态复验子函数）。

起因：C-005 圈复杂度收敛把收据/信封形态的逐件校验抽成子函数后，_verify_forms 越过
400 行上限（C-001）；按「必要时先拆私有子模块」纪律把**只被 _verify_forms 调用的**
子函数移到这里，公开 API 不变、行为/文案逐字不动。
"""
from __future__ import annotations

import os
import tempfile
from typing import Any

from core import attest

from ._const import (
    GUIDE,
    LEVELS,
    PAYLOAD_DIR,
)
from ._freshness import (
    _apply_expiry,
    _apply_freshness,
)
from ._primitives import (
    _leaf,
    _norm,
    _sha256,
)
from ._revocation import (
    _apply_revocation_doc,
)
from ._reader import (
    _empty_result,
)

def _payload_find(read: Any, rel: str) -> bytes | None:
    """成员实体查找：先按原相对路径，再退化到 payload/ 前缀（bundle 形态用前缀）。"""
    for name in (rel, PAYLOAD_DIR + rel):
        data = read(name)
        if data is not None:
            return data
    return None


def _receipt_entry_issues(e: dict[str, Any], read: Any) -> tuple[list[str], bytes | None]:
    """单条回执：成员实体在场 → 摘要/叶复算 → (issues, 叶字节)。"""
    issues: list[str] = []
    rel = _norm(str(e.get("id") or e.get("path") or ""))
    data = _payload_find(read, rel) if rel else None
    if data is None:
        return [f"缺成员实体：{rel or '?'}（{GUIDE}回执只证明「根里有这条」，验它需要"
                "成员字节——请把成员与回执放在同一根下，或用 nf evidence pack 打包）"], None
    digest = _sha256(data)
    want = str(e.get("digest") or "")
    if digest != want:
        issues.append(f"成员摘要不符：{rel}（记录={want[:16]} 实测={digest[:16]}）"
                      f"（{GUIDE}成员被改过——回执证明的就是字节，字节变了判定必红）")
    want_leaf = _leaf(rel, digest)
    if want_leaf != str(e.get("leaf") or ""):
        issues.append(f"叶复算不符：{rel}（{GUIDE}叶定义须与 receipts 同源；改动后请重签回执）")
    return issues, bytes.fromhex(want_leaf)


def _receipt_leaves(entries: list, read: Any, issues: list) -> list[bytes]:
    """逐条回执 → 叶列表（失败原因进 issues）。"""
    leaves: list[bytes] = []
    for e in entries:
        entry_issues, leaf = _receipt_entry_issues(e, read)
        issues.extend(entry_issues)
        if leaf is not None:
            leaves.append(leaf)
    return leaves


def _attest_payload(env: dict[str, Any], read: Any, tmp: str) -> tuple[list[str], dict | None]:
    """单份信封的成员实体：在场 → 落到 tmp → (issues, 成员条目)。"""
    issues: list[str] = []
    subj = _norm(str((env.get("subject") or {}).get("path") or ""))
    data = _payload_find(read, subj) if subj else None
    if data is None:
        return [f"缺成员实体：{subj or '?'}（{GUIDE}信封只证明「这份内容被签过」，"
                "验它需要内容本身——请把成员与信封放在同一根下）"], None
    digest = _sha256(data)
    full = os.path.join(tmp, *subj.split("/"))
    parent = os.path.dirname(full)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(full, "wb") as fh:
        fh.write(data)
    return issues, {"path": subj, "digest": digest}


def _attest_entries(envs: list, read: Any, tmp: str, issues: list) -> list[dict[str, Any]]:
    """逐份信封收成员条目（失败原因进 issues）。"""
    entries: list[dict[str, Any]] = []
    for env in envs:
        if not isinstance(env, dict):
            issues.append("信封不是对象（" + GUIDE + "重跑 nf attest --out 生成）")
            continue
        env_issues, entry = _attest_payload(env, read, tmp)
        issues.extend(env_issues)
        if entry is not None:
            entries.append(entry)
    return entries


def _attest_verdicts(envs: list, tmp: str, key: bytes | None,
                     res: dict[str, Any]) -> bool:
    """逐份信封过 attest.verify → level 取最强；一份都不过即 False。"""
    passed: list[str] = []
    failed: list[str] = []
    for env in envs:
        ok, att_issues, level = attest.verify(env, tmp, key=key)
        passed.extend([level] if ok else [])
        failed.extend([] if ok else att_issues)
    if not passed:
        res["issues"].append(f"所有信封均未通过校验：{'；'.join(failed[:3]) or '无可用信封'}"
                             f"（{GUIDE}hmac 级须提供同一密钥 --key-file；缺密钥一律拒绝）")
        return False
    res["level"] = max(passed, key=lambda lv: LEVELS.index(lv) if lv in LEVELS else -1)
    res["attestations_ok"] = len(passed)
    return True


def _attest_tail(res: dict[str, Any], entries: list, revocations: dict[str, Any] | None,
                 require_fresh_revocations: bool, at: str) -> bool:
    """吊销 → 时效 → 新鲜度（先失败先返回）。"""
    fresh: dict[str, Any] = {"state": "unknown", "expires_at": "", "basis": "none"}
    if _apply_revocation_doc(revocations, entries, res, fresh, at):
        return False
    if _apply_expiry(res, at):
        return False
    if _apply_freshness(res, require_fresh_revocations, at, fresh):
        return False
    return True



def _receipts_tail(res: dict[str, Any], entries: list, revocations: dict[str, Any] | None,
                   require_fresh_revocations: bool, at: str) -> bool:
    """回执形态收尾：吊销 → 新鲜度（先失败先返回）。"""
    fresh: dict[str, Any] = {"state": "unknown", "expires_at": "", "basis": "none"}
    if _apply_revocation_doc(revocations, entries, res, fresh, at):
        return False
    if _apply_freshness(res, require_fresh_revocations, at, fresh):
        return False
    return True
