"""core.library 私有实现分片 2/2（对外只经 core.library 门面导入）：set_status 等"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from core import atomic_write
from core.library_entries import entries, entry_digest

from ._part1 import (
    _DATE,
    MIRRORS,
    RECOMMENDED_KEYS,
    REQUIRED_KEYS,
    STATUSES,
    _rewrite_frontmatter,
    write_projection,
)


def _supersede_check(root: str, hit: dict, superseded_by: str) -> None:
    """superseded 流转的前置校验（取代者必须存在且非自己）。"""
    if not superseded_by:
        raise ValueError("superseded 必须指定取代者"
                         "（修复指引：nf library supersede <旧编号> <新编号>）")
    ids = {e["id"] for e in entries(root)}
    if superseded_by not in ids:
        raise ValueError("取代者不存在：%s" % superseded_by)
    if superseded_by == hit["id"]:
        raise ValueError("取代者不能是自己（修复指引：指向另一条已入库条目，"
                         "如 nf library supersede NF-1 NF-2）")


def set_status(root: str, entry_id: str, status: str,
               superseded_by: str = "") -> str:
    """流转条目生命周期（active/deprecated/superseded）并同步重建投影。"""
    if status not in STATUSES:
        raise ValueError("status 非法：%s（取值 %s）" % (status, "/".join(STATUSES)))
    hit = None
    for e in entries(root):
        if e["id"].lower() == (entry_id or "").strip().lower():
            hit = e
            break
    if hit is None:
        raise ValueError("条目未找到：%s（nf library ls 可枚举）" % entry_id)
    if status == "superseded":
        _supersede_check(root, hit, superseded_by)
    _rewrite_frontmatter(
        os.path.join(root, hit["path"]),
        {"status": status,
         "superseded_by": superseded_by if status == "superseded" else None})
    write_projection(root)
    return hit["path"]


@dataclass(frozen=True)
class AttestationOptions:
    """参数对象（审计 C-007：把成组参数收成不可变对象）。"""
    issuer: str = 'nf library'
    key: Optional[bytes] = None
    ssh_key: str = ''
    ssh_identity: str = ''
    ssh_ns: str = ''


# ---------------------------------------------------------------- frontmatter






# ------------------------------------------------------------------- 校验
def _fm_required_issues(fm: Dict[str, Any], eid: str) -> List[str]:
    """frontmatter 必填键与 id 一致判据。"""
    out: List[str] = []
    for k in REQUIRED_KEYS:
        if not str(fm.get(k) or "").strip():
            out.append("%s frontmatter 缺必填键：%s" % (eid, k))
    if str(fm.get("id") or "") != eid:
        out.append("%s frontmatter id 与文件名不一致：%s" % (eid, fm.get("id")))
    return out


def _fm_license_issues(fm: Dict[str, Any], eid: str) -> List[str]:
    """license 词表判据（license_gate 不可用则跳过）。"""
    lic = str(fm.get("license") or "")
    try:
        from core.license_gate import ALLOWED
        if lic and lic not in ALLOWED:
            return ["%s license 不在词表：%s" % (eid, lic)]
    except Exception:  # nosec B110/B112 —— 尽力而为：跳过不可读/不可解析项；该类缺口由对应门禁与 AUD-0016 静默跳过清单另行报出
        pass  # best-effort 显式忽略（清理/探测失败不影响主流程）
    return []


def _superseded_by_issues(fm: Dict[str, Any], eid: str, ids: Any) -> List[str]:
    """superseded_by 指向判据（存在性 / 自指）。"""
    sb = str(fm.get("superseded_by") or "").strip()
    out: List[str] = []
    if sb and sb not in ids:
        out.append("%s superseded_by 指向不存在的条目：%s" % (eid, sb))
    if sb == eid:
        out.append("%s superseded_by 指向自身（取代链成环）" % eid)
    return out


def _fm_status_issues(fm: Dict[str, Any], eid: str, ids: Any) -> List[str]:
    """status 词表与 superseded 流转判据。"""
    st = str(fm.get("status") or "active")
    out: List[str] = []
    if st not in STATUSES:
        out.append("%s status 不在词表：%s（%s）" % (eid, st, "/".join(STATUSES)))
    if st == "superseded" and not str(fm.get("superseded_by") or "").strip():
        out.append("%s status=superseded 但缺 superseded_by" % eid)
    out.extend(_superseded_by_issues(fm, eid, ids))
    return out


def _fm_date_issues(fm: Dict[str, Any], eid: str) -> List[str]:
    """三个日期键的 YYYY-MM-DD 形状判据。"""
    out: List[str] = []
    for date_key in ("generated", "verified", "stale_after"):
        v = str(fm.get(date_key) or "").strip()
        if v and not _DATE.match(v):
            out.append("%s %s 非 YYYY-MM-DD：%s" % (eid, date_key, v))
    return out


def _drift_issues(root: str, eid: str, e: Dict[str, Any],
                  att: str) -> Tuple[bool, List[str]]:
    """attestation 摘要形状与内容漂移判据 → (是否漂移, issues)。"""
    out: List[str] = []
    if not re.fullmatch(r"[0-9a-fA-F]{64}", att):
        return False, ["%s attestation 非 64 位十六进制摘要：%s" % (eid, att[:16])]
    drifted = False
    try:
        live = entry_digest(root, e["path"])
        drifted = live != att.lower()
    except OSError:
        # fail-closed：读不到条目就无法核对摘要——**不能当作「未漂移」**（那等于
        # 给一个读不到的件发通行证）。如实报问题，由人处置（2026-09-30 收口）。
        out.append("%s 条目不可读，无法核对 attestation 摘要（修复指引：确认 "
                   "library/%s.md 在场可读；确认后 nf library verify 复跑）"
                   % (eid, eid))
    return drifted, out


def _sig_file(root: str, fm: Dict[str, Any]) -> str:
    """锚签名文件路径（缺省空串）。"""
    name = fm.get("anchor_sig_file")
    if not name:
        return ""
    return os.path.join(root, str(name))


def _anchor_material_issues(scheme: str, fm: Dict[str, Any],
                            opts: Dict[str, Any]) -> List[str]:
    """签名锚材料缺失判据（只 warn，不判 FAIL）。"""
    from core import attest as _attest
    if scheme == _attest.SCHEME_HMAC and opts.get("key") is None:
        return ["%s 有 hmac 签名锚但未提供密钥 → 本轮无法校验"
                "（修复指引：--key-file <同一密钥>）" % fm.get("id")]
    if scheme == _attest.SCHEME_SSH and not opts.get("allowed_signers"):
        return ["%s 有 ssh-sig 锚但未提供 allowed_signers → 本轮无法校验"
                "（修复指引：--ssh-allowed-signers <文件>）" % fm.get("id")]
    return []


def _scheme_anchor_issues(root: str, fm: Dict[str, Any], att: str, scheme: str,
                          opts: Dict[str, Any]) -> List[str]:
    """签名锚校验判据（材料缺失返回 warn 文案；校验失败即 FAIL）。"""
    material = _anchor_material_issues(scheme, fm, opts)
    if material:
        return material
    from core import attest as _attest
    a_ok, a_issues, a_level = _attest.verify_digest_anchor(
        att, {"scheme": scheme, "mac": str(fm.get("anchor_mac") or ""),
              "ns": str(fm.get("anchor_ns") or ""),
              "identity": str(fm.get("anchor_identity") or ""),
              "sig_file": _sig_file(root, fm)},
        opts.get("key"), {"allowed_signers": opts.get("allowed_signers") or "",
                          "identity": opts.get("identity") or ""})
    if not a_ok:
        return ["%s 签名锚校验失败（级 %s）：%s" % (fm.get("id"), a_level, "; ".join(a_issues))]
    return []


def _anchor_issues(root: str, eid: str, e: Dict[str, Any], att: str,
                   fm: Dict[str, Any], opts: Dict[str, Any]
                   ) -> Tuple[List[str], List[str]]:
    """签名锚判据 → (issues, warns)。"""
    issues: List[str] = []
    warns: List[str] = []
    drifted, drift_issues = _drift_issues(root, eid, e, att)
    issues.extend(drift_issues)
    scheme = str(fm.get("anchor_scheme") or "").strip()
    if drifted:
        if scheme:
            # 有锚却内容已改 = 签名不再覆盖当前内容 → 判 FAIL（读者不应被误导）
            issues.append("%s 签名锚已不覆盖当前内容（落锚后内容被改）"
                          "（修复指引：重新 nf library attest <编号> 并分发新回执）" % eid)
        else:
            warns.append("%s attestation 与当前内容不符（内容已改，需重签）" % eid)
    if scheme:
        anchor_issues = _scheme_anchor_issues(root, fm, att, scheme, opts)
        anchor_warns = [x for x in anchor_issues if "本轮无法校验" in x]
        issues.extend([x for x in anchor_issues if x not in anchor_warns])
        warns.extend(anchor_warns)
    return issues, warns


def _entry_verify_issues(e: Dict[str, Any], root: str, ids: Any, opts: Dict[str, Any]
                         ) -> Tuple[List[str], List[str]]:
    """单条目校验 → (issues, warns)；判序与文案同原实现。"""
    issues: List[str] = []
    warns: List[str] = []
    fm, eid = e["fm"], e["id"]
    if e.get("decode_issue"):
        issues.append("编码：%s（%s）" % (eid, e["decode_issue"]))
    if not fm:
        issues.append("%s 缺 YAML frontmatter（真源要求：type/id/title 起）" % eid)
        return issues, warns
    issues.extend(_fm_required_issues(fm, eid))
    issues.extend(_fm_license_issues(fm, eid))
    issues.extend(_fm_status_issues(fm, eid, ids))
    if not fm.get("sources"):
        warns.append("%s 缺 sources（provenance 未声明）" % eid)
    issues.extend(_fm_date_issues(fm, eid))
    att = str(fm.get("attestation") or "").strip()
    if att:
        anchor_issues, anchor_warns = _anchor_issues(root, eid, e, att, fm, opts)
        issues.extend(anchor_issues)
        warns.extend(anchor_warns)
    for k in RECOMMENDED_KEYS:
        if k not in fm:
            warns.append("%s 缺推荐键：%s" % (eid, k))
    return issues, warns


def verify(root: str = ".", key: Optional[bytes] = None,
           ssh_allowed_signers: str = "", ssh_identity: str = ""
           ) -> Tuple[List[str], List[str], Dict[str, Any]]:
    """校验条目 frontmatter → (issues FAIL, warns WARN, stats)。"""
    issues: List[str] = []
    warns: List[str] = []
    rows = entries(root)
    ids = {e["id"] for e in rows}
    opts = {"key": key, "allowed_signers": ssh_allowed_signers,
            "identity": ssh_identity}
    for e in rows:
        entry_issues, entry_warns = _entry_verify_issues(e, root, ids, opts)
        issues.extend(entry_issues)
        warns.extend(entry_warns)
    stats = {"entries": len(rows), "ids": sorted(ids),
             "active": sum(1 for e in rows
                           if str(e["fm"].get("status") or "active") == "active"),
             "warns": warns}
    return issues, warns, stats


def _find_entry(root: str, entry_id: str) -> Dict[str, Any]:
    """按编号找条目（大小写不敏感）；找不到即带指引拒绝。"""
    hit = None
    for e in entries(root):
        if e["id"].lower() == (entry_id or "").strip().lower():
            hit = e
            break
    if hit is None:
        raise ValueError("条目未找到：%s（修复指引：nf library ls 列全量编号）" % entry_id)
    return hit


def _ssh_anchor(root: str, digest: str, hit: Dict[str, Any],
                opts: AttestationOptions) -> tuple[Dict[str, Any], str, Dict[str, Any]]:
    """ssh 签名锚：落 library/anchors/<id>.sig → (空 anchor, level, 锚字段)。"""
    from core import attest as _attest
    info = _attest.sign_digest_ssh(digest, opts.ssh_key, opts.ssh_identity,
                                   ns=opts.ssh_ns or _attest.SSH_NAMESPACE)
    sig_rel = "library/anchors/%s.sig" % hit["id"]
    dest = os.path.join(root, sig_rel)
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    # 原子写（2026-09-30 收口）：签名锚是在仓产物，半截的 `.sig` 会让校验方判
    # 「签名无效」而不是「没写完」——读者永远该看到旧全量或新全量。
    with open(info["sig_file"], "rb") as src:
        atomic_write.write_bytes(dest, src.read())
    return {}, _attest.SCHEME_SSH, {"anchor_ns": info["ns"],
                                    "anchor_identity": info["identity"],
                                    "anchor_sig_file": sig_rel,
                                    "anchor_fingerprint": info["fingerprint"]}


def _hmac_anchor(digest: str, key: bytes, issuer: str) -> tuple[Dict[str, Any], str, Dict[str, Any]]:
    """hmac 签名锚 → (anchor, level, 锚字段)。"""
    from core import attest as _attest
    anchor = _attest.sign_digest_hmac(digest, key, issuer)
    level = str(anchor.get("scheme") or "hmac-sha256")
    return anchor, level, {"anchor_key_id": anchor.get("key_id"),
                           "anchor_issuer": anchor.get("issuer")}


def _anchor_update(digest: str, att: Dict[str, Any], anchor: Dict[str, Any], level: str,
                   anchor_fields: Dict[str, Any], opts: AttestationOptions) -> Dict[str, Any]:
    """frontmatter 的锚字段面（扁平键；不给密钥时 anchor 字段为 None 清旧锚）。"""
    return {
        "attestation": digest, "attested_at": att["issued_at"][:10],
        "anchor_scheme": (anchor.get("scheme") or level) if (opts.key or opts.ssh_key) else None,
        "anchor_mac": anchor.get("mac") if opts.key and not opts.ssh_key else None,
        "anchor_key_id": anchor_fields.get("anchor_key_id"),
        "anchor_issuer": anchor_fields.get("anchor_issuer"),
        "anchor_ns": anchor_fields.get("anchor_ns"),
        "anchor_identity": anchor_fields.get("anchor_identity"),
        "anchor_sig_file": anchor_fields.get("anchor_sig_file"),
        "anchor_fingerprint": anchor_fields.get("anchor_fingerprint"),
    }


def _refresh_receipts(root: str) -> str:
    """重签后刷新回执 → warn 文本（空 = 已刷新）。

    逐行审查修正（2026-09-20）：回执刷新失败**不得静默**——锚已写进条目而回执没跟上，
    读者侧会 fail-closed；把失败带回调用方（CLI 打印 / --json 可见）。
    """
    try:
        from core import receipts as _rc
        _rc.write(root)
        return ""
    except Exception as exc:
        return ("回执未刷新：%s（修复指引：手动跑 nf library receipts --write）" % exc)


def set_attestation(
    root: str,
    entry_id: str,
    opts: AttestationOptions | None = None,
) -> Dict[str, Any]:
    """把规范摘要写进条目 frontmatter；给了密钥就一并落 **hmac 签名锚**。

    锚字段（扁平键，frontmatter 解析器友好）：
    `anchor_scheme` / `anchor_mac` / `anchor_key_id` / `anchor_issuer`。
    不给密钥时清掉旧锚——避免"降级后残留旧锚"造成假可信。
    """

    opts = opts if opts is not None else AttestationOptions()
    from core import attest as _attest
    hit = _find_entry(root, entry_id)
    rel = hit["path"]
    att = _attest.build(rel, root, issuer=opts.issuer)
    # 存入的摘要必须**自指安全**（剔除 attestation 字段后计算），否则一落签即失效
    digest = entry_digest(root, rel)
    anchor: Dict[str, Any] = {}
    level = "digest_only"
    anchor_fields: Dict[str, Any] = {}
    if opts.ssh_key:
        anchor, level, anchor_fields = _ssh_anchor(root, digest, hit, opts)
    elif opts.key:
        anchor, level, anchor_fields = _hmac_anchor(digest, opts.key, opts.issuer)
    _rewrite_frontmatter(os.path.join(root, rel),
                         _anchor_update(digest, att, anchor, level, anchor_fields, opts))
    write_projection(root)
    # 锚信息进了回执（receipts.entries[].anchor），重签后必须同步刷新，
    # 否则读者拿到的回执仍指向旧锚（会在读者侧 fail-closed）。
    warn = _refresh_receipts(root)
    out = {"id": hit["id"], "path": rel, "attestation": digest,
           "envelope_digest": att["envelope_digest"], "level": level,
           "key_id": anchor.get("key_id", ""),
           "identity": anchor_fields.get("anchor_identity", ""),
           "sig_file": anchor_fields.get("anchor_sig_file", "")}
    if warn:
        out["warn"] = warn
    return out


def to_manifest(root: str = ".") -> Dict[str, Any]:
    """机器清单（MCP/llms.txt 复用同一份事实）。"""
    rows = entries(root)
    return {"schema": "nf-library/1", "count": len(rows),
            "mirrors": [m["raw"] for m in MIRRORS],
            "entries": [{"id": e["id"], "title": e["fm"].get("title", e["id"]),
                         "type": e["fm"].get("type", ""),
                         "status": e["fm"].get("status", "active"),
                         "license": e["fm"].get("license", ""),
                         "path": e["path"]} for e in rows]}
