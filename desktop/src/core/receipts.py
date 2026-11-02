"""图书馆回执 + 单根（机制借鉴 MCOP 的 Verifiable Reasoning Receipts / MMR）。

线性哈希链「证明某一条 ∈ 全量」要 O(n) 重放；馆藏长大后这是错形状。本模块给出
**逐条 inclusion proof + 一个全馆根**（RFC 6962 域分隔）：

- 叶子 = `SHA-256(0x00 || 规范载荷)`；内部节点 = `SHA-256(0x01 || 左 || 右)`；
- 每条回执只带 O(log n) 审计路径（几 KB），读者拿到**该条 + 根**即可本地折叠验证，
  不必取全馆其余部分；
- 载荷 = `{id, digest}`（digest 用 library.entry_digest：自指安全）。

纪律：纯标准库 hashlib；只读；不自造密码学（域分隔与折叠规则照 RFC 6962）。
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from core import atomic_write, json_doc

SCHEMA = "nf-receipts/1"
RECEIPTS_REL = "library/RECEIPTS.json"


def _h(data: bytes) -> bytes:
    return hashlib.sha256(data).digest()


def leaf_hash(payload: bytes) -> bytes:
    return _h(b"\x00" + payload)


def node_hash(left: bytes, right: bytes) -> bytes:
    return _h(b"\x01" + left + right)


def merkle_root(leaves: List[bytes]) -> Optional[bytes]:
    """RFC 6962 风格：空集 → None；单叶 → 该叶。"""
    if not leaves:
        return None
    if len(leaves) == 1:
        return leaves[0]
    mid = 1
    while mid * 2 < len(leaves):
        mid *= 2
    return node_hash(merkle_root(leaves[:mid]) or b"", merkle_root(leaves[mid:]) or b"")


def inclusion_proof(leaves: List[bytes], index: int) -> List[Dict[str, str]]:
    """返回 [{side, hash}]，**自底向上**（叶的兄弟在前，逐层向上）；
    side ∈ {'left','right'} 表示该兄弟在折叠时的位置。

    与 RFC 6962 audit path 同序；读者侧按列表顺序逐个 node() 即可得到根。
    （早期实现返回自顶向下，导致 n>2 时折叠不到根——已由规模回归测试钉住。）
    """
    if not leaves or index < 0 or index >= len(leaves):
        raise IndexError("叶子下标越界：%s（共 %d 叶）" % (index, len(leaves)))
    proof: List[Dict[str, str]] = []

    def walk(sub: List[bytes], i: int) -> None:
        if len(sub) <= 1:
            return
        mid = 1
        while mid * 2 < len(sub):
            mid *= 2
        if i < mid:
            sib = merkle_root(sub[mid:]) or b""
            proof.append({"side": "right", "hash": sib.hex()})
            walk(sub[:mid], i)
        else:
            sib = merkle_root(sub[:mid]) or b""
            proof.append({"side": "left", "hash": sib.hex()})
            walk(sub[mid:], i - mid)

    walk(leaves, index)
    return proof[::-1]


def fold_proof(leaf_hex: str, proof: List[Dict[str, str]]) -> str:
    """按证明折叠出根（读者侧验证路径，不依赖仓库其余内容）。"""
    cur = bytes.fromhex(leaf_hex)
    for step in proof:
        sib = bytes.fromhex(step["hash"])
        cur = (node_hash(sib, cur) if step["side"] == "left"
               else node_hash(cur, sib))
    return cur.hex()


def build(root: str = ".") -> Dict[str, Any]:
    """从馆藏实时算：{schema, root, count, entries:[{id, path, digest, leaf, proof}]}。"""
    from core import library_entries as nflib    # 叶子件：不再 import library（断 receipts ↔ library）

    rows = nflib.entries(root)
    payloads, leaves = [], []
    for e in rows:
        digest = nflib.entry_digest(root, e["path"])
        payload = json.dumps({"id": e["id"], "digest": digest},
                             sort_keys=True, ensure_ascii=False,
                             separators=(",", ":")).encode("utf-8")
        payloads.append((e, digest, payload))
        leaves.append(leaf_hash(payload))
    root_hash = merkle_root(leaves)
    entries = []
    for i, (e, digest, payload) in enumerate(payloads):
        fm = e["fm"]
        entries.append({"id": e["id"], "path": e["path"], "digest": digest,
                        "anchor": ({"scheme": str(fm.get("anchor_scheme")),
                                    "key_id": str(fm.get("anchor_key_id") or ""),
                                    "mac": str(fm.get("anchor_mac") or ""),
                                    "ns": str(fm.get("anchor_ns") or ""),
                                    "identity": str(fm.get("anchor_identity") or ""),
                                    "sig_file": str(fm.get("anchor_sig_file") or ""),
                                    "fingerprint": str(fm.get("anchor_fingerprint") or "")}
                                   if fm.get("anchor_scheme") else None),
                        "leaf": leaf_hash(payload).hex(),
                        "proof": inclusion_proof(leaves, i)})
    return {"schema": SCHEMA,
            "root": root_hash.hex() if root_hash else "",
            "count": len(rows), "algorithm": "RFC6962-style sha256 domain-separated",
            "entries": entries}


def verify(doc: Dict[str, Any], root: str = ".") -> Tuple[List[str], Dict[str, Any]]:
    """校验：每条回执折叠到根 + 根与实时重算一致（防挑单条伪造、防整体替换）。"""
    issues: List[str] = []
    if not isinstance(doc, dict) or doc.get("schema") != SCHEMA:
        return ["回执文件 schema 不匹配（期望 %s）" % SCHEMA], {}
    live = build(root)
    if doc.get("root") != live["root"]:
        issues.append("根不一致：记录=%s 实测=%s（修复指引：馆藏改动后跑 "
                      "nf library receipts --write）"
                      % (str(doc.get("root"))[:16], str(live["root"])[:16]))
    live_by_id = {e["id"]: e for e in live["entries"]}
    for e in doc.get("entries") or []:
        eid = e.get("id")
        if eid not in live_by_id:
            issues.append("回执指向不存在的条目：%s" % eid)
            continue
        live_e = live_by_id[eid]
        if e.get("digest") != live_e["digest"]:
            issues.append("条目内容已变：%s（修复指引：重签该条并重建回执）" % eid)
        if fold_proof(str(e.get("leaf")), e.get("proof") or []) != str(doc.get("root")):
            issues.append("包含证明不折叠到根：%s" % eid)
        # 2026-11-02（E1）：anchor 块此前不在任何判据覆盖内——既不在 Merkle 载荷里，
        # verify 也不与 frontmatter 对照（读者侧 nf_verify 只信这个块）。两条判据：
        # ① 形状/路径安全（scheme 词表、sig_file 必须仓内相对）；② 与实时 frontmatter 一致。
        got_anchor = e.get("anchor")
        if got_anchor is not None and not isinstance(got_anchor, dict):
            issues.append("锚块形状非法（须为对象或 null）：%s" % eid)
        elif isinstance(got_anchor, dict):
            scheme = str(got_anchor.get("scheme") or "")
            if scheme not in ("hmac-sha256", "ssh-sig", "sigstore-keyless"):
                issues.append("锚块方案非法：%s（%s）" % (scheme or "<空>", eid))
            sig = str(got_anchor.get("sig_file") or "")
            if sig and (Path(sig).is_absolute() or ".." in Path(sig).parts):
                issues.append("锚块 sig_file 逃逸仓库根：%s（%s）" % (sig, eid))
        if got_anchor != live_e.get("anchor"):
            issues.append("锚块与条目 frontmatter 不一致：%s（修复指引：nf library attest "
                          "重签后重建回执）" % eid)
    if len(doc.get("entries") or []) != live["count"]:
        issues.append("回执条数 %d ≠ 馆藏条数 %d"
                      % (len(doc.get("entries") or []), live["count"]))
    stats = {"entries": live["count"], "root": live["root"]}
    return issues, stats


def write(root: str = ".", rel: str = RECEIPTS_REL) -> str:
    doc = build(root)
    p = Path(root) / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    # 原子写（2026-10-01）：回执单根是**在仓产物**（check35 逐条断言），裸 `write_text` 在
    # 并发读者/杀软句柄扫描下会抛 `[Errno 22]`（本轮收口时真跑到一次，冒成「内部错误」），
    # 也可能留下半截 JSON——走唯一原子写出处（自带瞬时错短重试）。
    atomic_write.write_text(p, json.dumps(doc, ensure_ascii=False,
                                          indent=2, sort_keys=True) + "\n")
    return rel


def load(root: str = ".", rel: str = RECEIPTS_REL) -> Dict[str, Any]:
    # N11：顶层形状校验（非对象 → 带指引的 ValueError，不再裸 AttributeError）。
    return json_doc.load(Path(root) / rel, dict, what=rel)


# ---------------------------------------------------------------- 协议层回执
PROTOCOL_RECEIPTS_REL = "protocol/RECEIPTS.json"


#: 去重（2026-11-01 · F7）：`protocol/schema/asset_contracts.schema.json` 曾既在显式清单、
#: 又被 `protocol/schema/*.json` glob 收一次 → 回执 67 条只有 66 个不同 subject（同 id 两条叶、
#: 两条不同 inclusion proof）。回执是「逐件有主」的锚定面，重复叶会让根与条数口径不一致。
#: 故 `protocol_subjects` 出口按**首次出现顺序**去重（`dict.fromkeys`），条数 = 件数。
def protocol_subjects(root: str = ".") -> List[str]:
    """协议层机读产物清单（回执覆盖面；不存在的项自动跳过）。"""
    fixed = ["STRATEGY.md", "01_核心协议.md", "02_联动注册表.md",
             "06_Agent执行协议.md", "07_官方核心出厂与社区预设导航.md",
             "llms.txt", "library/INDEX.md", "library/ALIAS.md",
             "protocol/event_registry.json", "protocol/world_slots.json",
             "protocol/export_conformance.json", "protocol/community_asset_ledger.json",
             "protocol/external_events.json", "protocol/type_backlog.json",
             "protocol/pipeline_advisory.json", "protocol/score_baseline.json",
             "protocol/module_signatures.json", "protocol/conformance_report.json",
             "protocol/asset_line_baseline.json",
             "protocol/asset_contracts.json",
"protocol/schema/asset_contracts.schema.json",
             "protocol/role_coordinates.json",
             "protocol/code_metrics_baseline.json",
             "protocol/coupling_baseline.json",
             "protocol/drill_fidelity.json",
             "protocol/instruction_evidence.json",
             "protocol/perf_budget.json",
             "protocol/repo_stats.json",
             "protocol/sast_baseline.json",
             "protocol/CONFORMANCE.md", "protocol/driver.json",
             "protocol/rfc_index.json", "protocol/endpoint_contract.json",
             "protocol/knowledge_sources.json", "protocol/transform_log.json",
             "protocol/knowledge_usage.json",
             "protocol/assertions.json",
             "protocol/LAYERS.json",
             "protocol/locales.json", "protocol/release_policy.json",
             "protocol/vocabularies.json", "protocol/normative.json",
             "protocol/data_contracts.json",
             "decisions/INDEX.md",
             "protocol/handover.json",
             "protocol/postmortem.json",
             "protocol/audit.json",
             "protocol/glossary.json",
             "protocol/execution_modes.json",
             "protocol/st_quality.json",
             "protocol/mcp_package.json",
             "protocol/state_front.json",
             "protocol/decision_layer.json",
             "desktop/src/core/registry.json"]
    r = Path(root)
    fixed += [p.relative_to(r).as_posix() for p in sorted(r.glob("protocol/schema/*.json"))]
    fixed += [p.relative_to(r).as_posix() for p in sorted(r.glob("decisions/ADR-*.md"))]
    # closed 复盘件必须先被回执锚定；把真源复盘件纳入协议回执面，
    # 否则 postmortem 的 closed 判据永远无法从正常重建路径满足。
    fixed += [p.relative_to(r).as_posix() for p in sorted(r.glob("postmortems/PO-*.md"))]
    return list(dict.fromkeys(s for s in fixed if (r / s).is_file()))


def build_scope(root: str = ".", subjects: Optional[List[str]] = None,
                scope: str = "protocol") -> Dict[str, Any]:
    """任意文件集 → 回执（叶 = sha256(0x00‖{"id":相对路径,"digest":文件摘要})）。"""
    rels = subjects if subjects is not None else protocol_subjects(root)
    leaves, rows = [], []
    for rel in rels:
        p = Path(root) / rel
        if not p.is_file():
            continue
        digest = hashlib.sha256(p.read_bytes()).hexdigest()
        payload = json.dumps({"id": rel, "digest": digest}, sort_keys=True,
                             ensure_ascii=False,
                             separators=(",", ":")).encode("utf-8")
        rows.append((rel, digest, payload))
        leaves.append(leaf_hash(payload))
    root_hash = merkle_root(leaves)
    entries = [{"id": rel, "path": rel, "digest": digest,
                "leaf": leaf_hash(payload).hex(),
                "proof": inclusion_proof(leaves, i)}
               for i, (rel, digest, payload) in enumerate(rows)]
    return {"schema": SCHEMA, "scope": scope,
            "root": root_hash.hex() if root_hash else "",
            "count": len(entries), "algorithm": "RFC6962-style sha256 domain-separated",
            "entries": entries}


def verify_scope(doc: Dict[str, Any], root: str = ".",
                 expected_subjects: Optional[List[str]] = None
                 ) -> Tuple[List[str], Dict[str, Any]]:
    """协议层回执校验：每条折叠到根 + 文件摘要与记录一致 + 根与实时重算一致。

    `expected_subjects`（2026-11-01 · F1 补）：可选**覆盖面**判据。此前校验只用回执
    自带的 id 列表重算根——把某条从回执里删掉再重算根，校验仍然全绿（覆盖面可静默
    收缩）。馆藏层有计数断言挡着，协议层没有；调用方给出期望件集后，漏登/多登都会
    如实报 FAIL，不再只证明「记录下来的那几条自洽」。
    """
    issues: List[str] = []
    if not isinstance(doc, dict) or doc.get("schema") != SCHEMA:
        return ["协议回执 schema 不匹配"], {}
    if expected_subjects is None and str(doc.get("scope") or "") == "protocol":
        # 2026-11-02（R2 收尾）：协议面回执默认校验覆盖面（不再依赖调用方记得传参；
        # 也避免改 verify.sh 文本导致 .NET 内嵌真源摘要漂移）。
        expected_subjects = protocol_subjects(root)
    entries = doc.get("entries")
    if not isinstance(entries, list) or any(not isinstance(e, dict) for e in entries):
        return ["协议回执 entries 形状非法（须为对象数组；修复指引：nf receipts --scope "
                "protocol --write 重建）"], {}
    recorded = [str(e.get("id") or "") for e in entries]
    if expected_subjects is not None:
        miss = sorted(set(expected_subjects) - set(recorded))
        extra = sorted(set(recorded) - set(expected_subjects))
        if miss:
            issues.append("协议回执漏登 %d 件（覆盖面收缩）：%s（修复指引：nf receipts --scope "
                          "protocol --write）" % (len(miss), "、".join(miss[:6])))
        if extra:
            issues.append("协议回执含 %d 件不在册条目（已删除/改名？）：%s（修复指引：nf "
                          "receipts --scope protocol --write）"
                          % (len(extra), "、".join(extra[:6])))
    live = build_scope(root, [e["id"] for e in entries])
    if doc.get("root") != live["root"]:
        issues.append("协议回执根不一致：记录=%s 实测=%s（修复指引：nf receipts --scope protocol --"
            "write）"
                      % (str(doc.get("root"))[:16], str(live["root"])[:16]))
    live_by = {e["id"]: e["digest"] for e in live["entries"]}
    for e in entries:
        if live_by.get(e["id"]) != e.get("digest"):
            issues.append("文件内容已变：%s" % e["id"])
        if fold_proof(str(e.get("leaf")), e.get("proof") or []) != str(doc.get("root")):
            issues.append("包含证明不折叠到根：%s" % e["id"])
    return issues, {"entries": len(doc.get("entries") or []), "root": live["root"]}


def write_scope(root: str = ".", scope: str = "protocol") -> str:
    doc = build_scope(root, scope=scope)
    p = Path(root) / PROTOCOL_RECEIPTS_REL
    p.parent.mkdir(parents=True, exist_ok=True)
    # 原子写（2026-10-01）：同 `write()`——协议层回执也是 check35 的比对对象。
    atomic_write.write_text(p, json.dumps(doc, ensure_ascii=False,
                                          indent=2, sort_keys=True) + "\n")
    return PROTOCOL_RECEIPTS_REL
