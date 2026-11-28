"""evidence · _verify_core（自 evidence.py 拆出；只移动代码，行为/文案不变）。"""
from __future__ import annotations

import os
import tempfile
from collections.abc import Sequence
from typing import Any

from core import attest, json_doc, receipts

from ._const import (
    GUIDE,
    LEVELS,
    PAYLOAD_DIR,
)
from ._primitives import (
    UnsafeBundleError,
    _chain_head,
    _leaf,
    _norm,
    _safe_rel,
    _sha256,
)
from ._reader import (
    _Reader,
)


def _digest_issues(rel: str, data: bytes, e: dict[str, Any]) -> tuple[list[str], Any]:
    """摘要/叶一致性 → (issues, 记录叶)。"""
    digest = _sha256(data)
    want = str(e.get("digest") or "")
    out: list[str] = []
    if digest != want:
        out.append(f"成员摘要不符：{rel}（记录={want[:16]} 实测={digest[:16]}）"
                   f"（{GUIDE}成员被改过或打包后被替换——请重新 nf evidence pack "
                   "并向签发方核对）")
    want_leaf = _leaf(rel, digest)
    if want_leaf != str(e.get("leaf") or ""):
        out.append(f"叶复算不符：{rel}（{GUIDE}叶定义须与 receipts 同源；"
                   "包被改过就重打）")
    return out, bytes.fromhex(want_leaf)


def _one_member(rd: _Reader, e: dict[str, Any]) -> tuple[list[str], Any]:
    """单成员：实体在场 + 摘要一致 + 叶复算一致 → (issues, 记录叶或 None)。"""
    try:
        rel = _safe_rel(str(e.get("path") or e.get("id") or ""))
    except UnsafeBundleError as exc:
        return [str(exc)], None
    data = rd.read(PAYLOAD_DIR + rel) if rel else None
    if data is None:
        return [f"缺 payload：{rel or '?'}（{GUIDE}证据包必须自带成员实体——缺实体"
                "的包算 invalid，不要改成只看清单）"], None
    return _digest_issues(rel, data, e)


def _check_members(rd: _Reader, entries: Sequence[dict[str, Any]],
                   issues: list[str]) -> list[bytes]:
    """成员实体在场 + 摘要一致 + 叶复算一致（三道一起判，任一不符即不可信）。"""
    leaves: list[bytes] = []
    for e in entries:
        member_issues, leaf = _one_member(rd, e)
        issues.extend(member_issues)
        if leaf is not None:
            leaves.append(leaf)
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




def _path_digests(entries: Sequence[dict[str, Any]]) -> dict[str, str]:
    """成员归一路径 → 摘要（信封 subject 同源比对用）。"""
    return {_norm(str(e.get("path") or "")): str(e.get("digest") or "") for e in entries}


def _append_envelope_failure(res: dict[str, Any], failed: list[str]) -> None:
    """严格口径：清单里的**每一份**信封都必须通过。

    容忍「有一份过了就算过」等于给了「悄悄塞一份坏信封」的容错面——证据强度只能由最弱
    那环决定，不能挑最好看的报。
    """
    joined = "；".join(failed[:3]) or "无可用信封"
    res["issues"].append(f"信封未全部通过校验：{joined}（{GUIDE}hmac 级须提供同一密钥 "
                         "--key-file；缺密钥一律拒绝，不降级为 digest_only；坏信封请"
                         "重新 nf evidence pack）")


def _collect_envelopes(rd: _Reader, att_names: list, by_path: dict, tmp: str,
                       key: bytes | None) -> tuple[list[str], list[str], set[str]]:
    """逐份信封校验 → (通过等级, 失败原因, 覆盖成员)。"""
    passed: list[str] = []
    failed: list[str] = []
    covered: set[str] = set()
    for name in att_names:
        level, why, subj = _one_envelope(rd, name, by_path, tmp, key)
        if level:
            passed.append(level)
            covered.add(subj)
        else:
            failed.extend(why)
    return passed, failed, covered


def _uncovered_members(entries: Sequence[dict[str, Any]], covered: set[str]) -> list[str]:
    """没有信封背书的成员（相对路径排序）。"""
    return sorted({_norm(str(e.get("path") or e.get("id") or "")) for e in entries}
                  - covered)


def _check_attestations(rd: _Reader, meta: dict[str, Any],
                        entries: Sequence[dict[str, Any]], key: bytes | None,
                        res: dict[str, Any]) -> None:
    """至少一份信封通过；level 取通过的最强一档（缺密钥一律拒绝，不降级）。"""
    att_names = [str(n) for n in (meta.get("attestations") or [])]
    if not att_names:
        res["issues"].append("包内无 attestation（" + GUIDE + "证据必须带信封——只有摘要的包"
                             "证明不了签发方；请用 nf evidence pack，它会为每个成员生成一份）")
        return
    by_path = _path_digests(entries)
    with tempfile.TemporaryDirectory(prefix="nf_evidence_") as tmp:
        _extract(rd, entries, tmp)
        passed, failed, covered = _collect_envelopes(rd, att_names, by_path, tmp, key)
    if failed:
        _append_envelope_failure(res, failed)
        return
    uncovered = _uncovered_members(entries, covered)
    if uncovered:
        res["issues"].append(f"成员缺信封：{', '.join(uncovered[:3])}（{GUIDE}每个成员都要有一份"
                             "信封——没有签发背书的成员不算证据，请重新 nf evidence pack）")
        return
    res["level"] = max(passed, key=lambda lv: LEVELS.index(lv) if lv in LEVELS else -1)
    res["attestations_ok"] = len(passed)




def _decision_envs(rd: _Reader, meta: dict[str, Any]) -> list[dict[str, Any]]:
    """读出清单声明的信封（坏信封由上游 fail-closed 判死，这里跳过不重复记账）。"""
    envs: list[dict[str, Any]] = []
    for name in [str(n) for n in (meta.get("attestations") or [])]:
        raw = rd.read(name)
        if raw is None:
            continue
        try:
            env = json_doc.loads(raw.decode(), dict, what="信封")
        except (ValueError, UnicodeDecodeError):
            continue
        if isinstance(env, dict):
            envs.append(env)
    return envs


def _decision_missing_issues(res: dict[str, Any], envs: list,
                             expected_policy_digest: str) -> None:
    """清单未声明 decision 时的两种诊断（绑定面仍在 / 只证字节）。"""
    if any(isinstance(env.get("decision"), dict) for env in envs):
        res["issues"].append("信封带 decision 但清单未声明（声明面被删，绑定面仍在）"
                             "（" + GUIDE + "重新 pack 让声明面与绑定面同源）")
    elif expected_policy_digest:
        res["warnings"].append("包内无 decision，无法比对策略（只证字节与信封；"
                               "" + GUIDE + "需要策略绑定请 pack 时带 decision）")


def _decision_binding(res: dict[str, Any], envs: list,
                      decision: dict[str, Any]) -> tuple[int, bool, bool]:
    """逐信封比对主体摘要与绑定面 → (匹配数, 是否签名, 是否一致)。"""
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
            return matched, signed, False
        signed = signed or bool(env.get("signature"))
    return matched, signed, True


def _decision_policy_issues(res: dict[str, Any], decision: dict[str, Any],
                            expected_policy_digest: str) -> None:
    """给了期望策略摘要时比对 policy_digest（不符即 fail-closed）。"""
    if not expected_policy_digest:
        return
    want = expected_policy_digest.strip().lower()
    got = str(decision.get("policy_digest") or "")
    if want != got:
        res["issues"].append(f"decision.policy_digest 与期望策略不符（期望={want[:16]} "
                             f"实际={got[:16]}）（{GUIDE}确认包与策略是同一份；"
                             "策略内容正确性只能由验方用自己信任的策略比对）")
        return
    res["policy_verified"] = True


def _check_decision(rd: _Reader, meta: dict[str, Any],
                    entries: Sequence[dict[str, Any]], res: dict[str, Any],
                    expected_policy_digest: str = "") -> None:
    """决策证据块（Q0）：声明面（bundle.json）必须与绑定面（相符信封）一致。

    只证明「这份证据绑定过一次 cc_check 的判定」；**不证明策略内容正确**——策略正确性
    需要验方用自己信任的 policy 重算 policy_digest 后比对（v0 不提供期望参数）。
    digest_only 级的信封只算 declared（没签名覆盖，证不了签发方认可该策略）。
    """
    envs = _decision_envs(rd, meta)
    decision = meta.get("decision")
    if decision is None:
        _decision_missing_issues(res, envs, expected_policy_digest)
        return
    issues = attest.decision_issues(decision, [str(e.get("digest") or "") for e in entries])
    if issues:
        res["issues"].extend(issues)
        return
    matched, signed, consistent = _decision_binding(res, envs, decision)
    if not consistent:
        return
    if not matched:
        res["issues"].append("decision 找不到主体摘要相符的信封（决策未绑定到任何签发面）"
                             "（" + GUIDE + "重新 pack，decision.object_sha256 必须等于某个"
                             "成员实体的 sha256）")
        return
    res["decision"] = dict(decision)
    res["decision_status"] = "bound" if signed else "declared"
    _decision_policy_issues(res, decision, expected_policy_digest)
