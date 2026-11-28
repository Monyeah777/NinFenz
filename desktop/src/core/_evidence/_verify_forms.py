"""evidence · _verify_forms（自 evidence.py 拆出；只移动代码，行为/文案不变）。"""
from __future__ import annotations

import os
import tempfile
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from core import attest, json_doc

from ._const import (
    ATTEST_SCHEMA,
    ATTEST_SET_SCHEMA,
    BUNDLE_ENTRY,
    GUIDE,
    LEVELS,
    PAYLOAD_DIR,
    RECEIPTS_SCHEMA,
)
from ._freshness import (
    _apply_expiry,
    _apply_freshness,
    _apply_time_token,
)
from ._primitives import (
    _leaf,
    _norm,
    _sha256,
    check_anchor,
)
from ._reader import (
    _empty_result,
    _fill_header,
    _load_meta,
    _Reader,
)
from ._revocation import (
    _apply_revocation,
    _apply_revocation_doc,
)
from ._verify_core import (
    _check_attestations,
    _check_chain,
    _check_decision,
    _check_members,
    _check_proofs,
    _check_root,
)
from ._verify_forms_parts import (
    _attest_entries,
    _attest_payload,
    _attest_tail,
    _attest_verdicts,
    _payload_find,
    _receipt_entry_issues,
    _receipt_leaves,
    _receipts_tail,
)


def _verify_structure(rd: _Reader, res: dict[str, Any]) -> tuple:
    """结构 → 成员摘要 → 根（先失败先返回）→ (meta, entries) 或 (None, [])。"""
    try:
        meta = _load_meta(rd)
    except ValueError as exc:
        res["issues"].append(str(exc))
        return None, []
    entries = meta.get("entries") or []
    res["count"] = len(entries)
    _fill_header(res, meta)
    res["issues"].extend(rd.issues)
    if not entries:
        res["issues"].append("证据包为空（" + GUIDE + "pack 时请至少给一个目标文件；"
                             "空包不给 ok）")
        return None, []
    leaves = _check_members(rd, entries, res["issues"])
    if res["issues"]:
        return None, []
    _check_root(leaves, res)
    if res["issues"]:
        return None, []
    return meta, entries


def _verify_core_phase(rd: _Reader, meta: dict[str, Any], entries: list,
                       opts: Any, res: dict[str, Any]) -> bool:
    """包含证明 → 链 → 锚 → 信封 → 挂账 → 判定；False = 已定案失败。"""
    _check_proofs(entries, res)
    _check_chain(entries, meta, res)
    check_anchor(entries, meta, opts.anchor, res)
    _check_extras(rd, entries, res["issues"])
    if res["issues"]:
        return False
    _check_attestations(rd, meta, entries, opts.key, res)
    if res["issues"]:
        return False
    _check_decision(rd, meta, entries, res, opts.expected_policy_digest)
    return not res["issues"]


def _verify_time_phase(res: dict[str, Any], bundle: str, opts: Any, at: str):
    """时间令牌锚定 → 新 at；None = 已定案失败。"""
    if opts.time_record is not None:
        anchored = _apply_time_token(res, bundle, opts.time_record, opts.time_ca,
                                     opts.time_untrusted)
        if anchored is None:
            return None
        return anchored or at
    return at


def _verify_uncosted(bundle: str, opts: VerifyOptions | None = None) -> dict[str, Any]:
    """校验证据包 → {verdict, level, root, head, issues, ...}。

    判定顺序固定（fail-closed，先失败先返回；**不**允许「证据弱就放行」）：
    结构 → 成员摘要 → 根 → 包含证明 → 链 → 信封 → 吊销 → 时效 → 吊销新鲜度。
    最后两段互相独立：`revoked > expired > 新鲜度不足(invalid) > ok`。
    """

    opts = opts if opts is not None else VerifyOptions()
    key = opts.key
    revocations = opts.revocations
    at = opts.at
    anchor = opts.anchor
    expected_policy_digest = opts.expected_policy_digest
    require_fresh_revocations = opts.require_fresh_revocations
    time_record = opts.time_record
    time_ca = opts.time_ca
    time_untrusted = opts.time_untrusted
    res = _empty_result()
    rd = _Reader(bundle)
    try:
        meta, entries = _verify_structure(rd, res)
        if meta is None:
            return res
        if not _verify_core_phase(rd, meta, entries, opts, res):
            return res
        at = _verify_time_phase(res, bundle, opts, at)
        if at is None:
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






def _schema_of(raw: bytes | None) -> str:
    if raw is None:
        return ""
    try:
        doc = json_doc.loads(raw.decode(), dict, what="证据文档")
    except (ValueError, UnicodeDecodeError):
        return ""
    return str(doc.get("schema") or "") if isinstance(doc, dict) else ""




def _found_docs(rd: _Reader) -> dict[str, dict[str, Any]]:
    """容器内按 schema 找证据文档 → {schema: doc}（坏件跳过，首见为准）。"""
    found: dict[str, dict[str, Any]] = {}
    for name in [n for n in rd.names() if n.endswith(".json")]:
        raw = rd.read(name)
        schema = _schema_of(raw)
        if schema in (RECEIPTS_SCHEMA, ATTEST_SCHEMA, ATTEST_SET_SCHEMA) and schema not in found:
            try:
                found[schema] = json_doc.loads(raw.decode(), dict, what="证据文档")  # type: ignore[arg-type]
            except (ValueError, UnicodeDecodeError):
                continue
    return found


def _detect_container(rd: _Reader, kind: str = "") -> tuple[str, dict[str, Any]]:
    """容器（zip / 目录）→ (形态, 文档)。显式 --kind 时只做形状确认，不猜。"""
    if rd.read(BUNDLE_ENTRY) is not None:
        return "bundle", _load_meta(rd)
    found = _found_docs(rd)
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
    leaves = _receipt_leaves(entries, read, issues)
    if issues:
        return res
    _check_root(leaves, res)
    if issues:
        return res
    _check_proofs(entries, res)
    if issues:
        return res
    res["level"] = "receipts_only"
    if not _receipts_tail(res, entries, revocations, require_fresh_revocations, at):
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
    with tempfile.TemporaryDirectory(prefix="nf_attestset_") as tmp:
        entries = _attest_entries(envs, read, tmp, issues)
        if issues:
            return res
        if not _attest_verdicts(envs, tmp, key, res):
            return res
    if not _attest_tail(res, entries, revocations, require_fresh_revocations, at):
        return res
    res["verdict"] = "ok"
    return res



@dataclass(frozen=True)
class VerifyOptions:
    """参数对象（审计 C-007：把成组参数收成不可变对象）。"""
    key: bytes | None = None
    revocations: dict[str, Any] | None = None
    at: str = ''
    anchor: dict[str, Any] | None = None
    expected_policy_digest: str = ''
    require_fresh_revocations: bool = False
    time_record: dict[str, Any] | None = None
    time_ca: str = ''
    time_untrusted: str = ''


def verify(bundle: str, opts: VerifyOptions | None = None) -> dict[str, Any]:
    """校验证据包 → 判定（同 `_verify_uncosted`），并附 `cost_ms`（本次判定耗时）。

    为什么加成本（第 91 轮）：资源层同构缺的是「验证侧记账」——认知侧有 `budget.steps_used`，
    契约侧此前没有任何「这次判定花了多少」的记录。`cost_ms` 只记**本机实测耗时**（整数毫秒），
    不参与判定、不进任何质量分；跨机器不可比，只作同一环境下的相对成本。
    """

    opts = opts if opts is not None else VerifyOptions()
    key = opts.key
    revocations = opts.revocations
    at = opts.at
    anchor = opts.anchor
    expected_policy_digest = opts.expected_policy_digest
    require_fresh_revocations = opts.require_fresh_revocations
    time_record = opts.time_record
    time_ca = opts.time_ca
    time_untrusted = opts.time_untrusted
    import time

    started = time.perf_counter()
    res = _verify_uncosted(
        bundle,
        opts=VerifyOptions(
            key=key,
            revocations=revocations,
            at=at,
            anchor=anchor,
            expected_policy_digest=expected_policy_digest,
            require_fresh_revocations=require_fresh_revocations,
            time_record=time_record,
            time_ca=time_ca,
            time_untrusted=time_untrusted,
        ),
    )
    res["cost_ms"] = max(0, int((time.perf_counter() - started) * 1000))
    return res
