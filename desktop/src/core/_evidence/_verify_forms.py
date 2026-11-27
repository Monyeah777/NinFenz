"""evidence · _verify_forms（自 evidence.py 拆出；只移动代码，行为/文案不变）。"""
from __future__ import annotations

import os
import tempfile
from collections.abc import Sequence
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


def _verify_uncosted(bundle: str, key: bytes | None = None,
                     revocations: dict[str, Any] | None = None,
                     at: str = "", anchor: dict[str, Any] | None = None,
                     expected_policy_digest: str = "",
                     require_fresh_revocations: bool = False,
                     time_record: dict[str, Any] | None = None,
                     time_ca: str = "", time_untrusted: str = "") -> dict[str, Any]:
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
        if time_record is not None:
            anchored = _apply_time_token(res, bundle, time_record, time_ca, time_untrusted)
            if anchored is None:
                return res
            at = anchored or at
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



def verify(bundle: str, key: bytes | None = None,
           revocations: dict[str, Any] | None = None,
           at: str = "", anchor: dict[str, Any] | None = None,
           expected_policy_digest: str = "",
           require_fresh_revocations: bool = False,
           time_record: dict[str, Any] | None = None,
           time_ca: str = "", time_untrusted: str = "") -> dict[str, Any]:
    """校验证据包 → 判定（同 `_verify_uncosted`），并附 `cost_ms`（本次判定耗时）。

    为什么加成本（第 91 轮）：资源层同构缺的是「验证侧记账」——认知侧有 `budget.steps_used`，
    契约侧此前没有任何「这次判定花了多少」的记录。`cost_ms` 只记**本机实测耗时**（整数毫秒），
    不参与判定、不进任何质量分；跨机器不可比，只作同一环境下的相对成本。
    """
    import time

    started = time.perf_counter()
    res = _verify_uncosted(bundle, key=key, revocations=revocations, at=at, anchor=anchor,
                           expected_policy_digest=expected_policy_digest,
                           require_fresh_revocations=require_fresh_revocations,
                           time_record=time_record, time_ca=time_ca,
                           time_untrusted=time_untrusted)
    res["cost_ms"] = max(0, int((time.perf_counter() - started) * 1000))
    return res
