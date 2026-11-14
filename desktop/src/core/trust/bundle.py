"""nf-claim-bundle/1：claim 级 Merkle 包与单 claim 独立验证（FR-A1-01…03）。

冻结依据：ADR-006 与向量集 merkle 族。Merkle 原语**复用** `core.receipts`（RFC 6962，
与馆藏回执同一实现，拒绝第二套哈希口径）；本模块只加 claim 语义：叶预像、bundle_id
域分隔、splice 防护、单 claim 验证（只读 1 条 claim + 1 条 proof，哈希 O(log n)）。

叶预像（冻结）::

    data = b"nf:claim-bundle:v1:claim" + b"\x00" + canonical_bytes({bundle_id, index, claim})
    leaf = sha256(b"\x00" + data)          # RFC 6962 leaf hash

bundle_id / index / claim 全部进叶：换包、换位置、换内容都会改变叶——跨包拼接与重排可检测。

边界（不夸大）：本地可重建任意自洽 bundle（这是自洽性，不是不可篡改）；「删尾不可逆」要靠
签名 + 外部锚（G2）。本模块只证「这条 claim 与这个 bundle 根一致」。
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from core import json_doc, json_schema
from core.receipts import fold_proof, inclusion_proof, leaf_hash, merkle_root
from core.trust.canonical import canonical_bytes, is_digest

GUIDE = "修复指引："
SCHEMA = "nf-claim-bundle/1"
SCHEMA_REL = "protocol/trust/claim-bundle.schema.json"
#: 叶预像的域标签（与 ADR-006 的 nf:<schema>:v1:<field> 规则同形）。
LEAF_DOMAIN = b"nf:claim-bundle:v1:claim"
#: 域标签与载荷之间的分隔字节（防拼接歧义）。
LEAF_SEP = b"\x00"
#: proof 深度上限（2^64 叶足够；同时是 DoS 上限，与 schema maxItems 对齐）。
MAX_PROOF_DEPTH = 64


def load_schema(root: str = ".", rel: str = SCHEMA_REL) -> dict:
    """读冻结的 claim-bundle schema（缺件/坏 JSON 直接抛，不静默降级）。"""
    path = Path(root) / rel
    if not path.is_file():
        raise ValueError(f"缺 claim-bundle schema：{rel}（{GUIDE}先落 protocol/trust 定义）")
    doc = json_doc.load(path, dict, what=rel)
    const = str((doc.get("properties") or {}).get("schema", {}).get("const"))
    if const != SCHEMA:
        raise ValueError(f"{rel} 不是 {SCHEMA} 定义（{GUIDE}核对 properties.schema.const）")
    return doc


def claim_leaf_data(bundle_id: str, index: int, claim: Any) -> bytes:
    """叶预像：域标签 + 0x00 + canonical{bundle_id,index,claim}。"""
    if not is_digest(bundle_id):
        raise ValueError(f"bundle_id 须为 64 位小写 hex（{GUIDE}用 canonical.digest_of 生成）")
    if not isinstance(index, int) or isinstance(index, bool) or index < 0:
        raise ValueError(f"index 须为非负整数（{GUIDE}按 claims 顺序从 0 起）")
    if not isinstance(claim, dict):
        raise ValueError(f"claim 须为对象（{GUIDE}见 nf-claim-bundle/1 claims[] 定义）")
    body = canonical_bytes({"bundle_id": bundle_id, "index": index, "claim": claim})
    return LEAF_DOMAIN + LEAF_SEP + body


def claim_leaf(bundle_id: str, index: int, claim: Any) -> bytes:
    """单条 claim 的 RFC 6962 叶哈希（bytes）。"""
    return leaf_hash(claim_leaf_data(bundle_id, index, claim))


def build_bundle(bundle_id: str, contract_ref: str, claims: list,
                 evidence_refs: list | None = None) -> dict:
    """从 claim 列表构建自洽 bundle（确定性：同输入两次逐字节一致）。"""
    if not isinstance(claims, list) or not claims:
        raise ValueError(f"claims 至少 1 条（{GUIDE}空包没有根，也没有可验对象）")
    if not isinstance(contract_ref, str) or not contract_ref:
        raise ValueError(f"contract_ref 必须是非空字符串（{GUIDE}指向仲裁契约）")
    leaves = [claim_leaf(bundle_id, index, claim) for index, claim in enumerate(claims)]
    root = merkle_root(leaves)
    if root is None:
        raise ValueError(f"无法计算 Merkle 根（{GUIDE}确认 claims 非空）")
    proofs = [{"index": index, "leaf": leaves[index].hex(),
               "proof": inclusion_proof(leaves, index)}
              for index in range(len(leaves))]
    bundle = {"schema": SCHEMA, "bundle_id": bundle_id, "contract_ref": contract_ref,
              "claims": claims, "merkle_root": root.hex(), "inclusion_proofs": proofs}
    if evidence_refs is not None:
        bundle["evidence_refs"] = evidence_refs
    return bundle


def _proof_for(bundle: dict, index: int) -> dict | None:
    for item in bundle.get("inclusion_proofs") or []:
        if isinstance(item, dict) and item.get("index") == index:
            return item
    return None


def verify_claim(bundle: Any, index: int, proof: dict | None = None) -> dict:
    """单 claim 验证：只读 claims[index] + 一条 proof，哈希 O(log n)。

    返回 {ok, reason?, leaf?, root?, claim_id?}。proof 可由调用方直接给（脚手架/侧车），
    避免在 inclusion_proofs 里线性查找（完整包场景仍可用 bundle 自带 proof）。
    """
    if not isinstance(bundle, dict):
        return {"ok": False, "reason": "BUNDLE-NOT-OBJECT"}
    bundle_id = bundle.get("bundle_id")
    if not is_digest(bundle_id):
        return {"ok": False, "reason": "BUNDLE-ID-INVALID"}
    claims = bundle.get("claims")
    if not isinstance(claims, list) or not claims:
        return {"ok": False, "reason": "CLAIMS-MISSING"}
    if not isinstance(index, int) or isinstance(index, bool) or not 0 <= index < len(claims):
        return {"ok": False, "reason": "INDEX-OUT-OF-RANGE"}
    root = bundle.get("merkle_root")
    if not is_digest(root):
        return {"ok": False, "reason": "ROOT-INVALID"}
    if proof is None:
        proof = _proof_for(bundle, index)
    if not isinstance(proof, dict):
        return {"ok": False, "reason": "PROOF-MISSING"}
    if proof.get("index") != index:
        return {"ok": False, "reason": "PROOF-INDEX-MISMATCH"}
    steps = proof.get("proof")
    if not isinstance(steps, list) or len(steps) > MAX_PROOF_DEPTH:
        return {"ok": False, "reason": "PROOF-INVALID"}
    for step in steps:
        if not isinstance(step, dict) or step.get("side") not in ("left", "right"):
            return {"ok": False, "reason": "PROOF-INVALID"}
        if not is_digest(step.get("hash")):
            return {"ok": False, "reason": "PROOF-INVALID"}
    claim = claims[index]
    if not isinstance(claim, dict):
        return {"ok": False, "reason": "CLAIM-INVALID"}
    leaf = claim_leaf(bundle_id, index, claim)
    if proof.get("leaf") != leaf.hex():
        return {"ok": False, "reason": "LEAF-MISMATCH"}
    try:
        folded = fold_proof(leaf.hex(), steps)
    except ValueError:
        return {"ok": False, "reason": "PROOF-INVALID"}
    if folded != root:
        return {"ok": False, "reason": "ROOT-MISMATCH"}
    return {"ok": True, "index": index, "leaf": leaf.hex(), "root": root,
            "claim_id": claim.get("id")}


def verify_bundle(bundle: Any, schema: dict | None = None) -> dict:
    """整包验证：结构 + 全叶根重算 + 每条 proof 折叠 + 覆盖/唯一性。

    返回 {ok, issues[], stats}；判据顺序固定，先结构后密码学（fail-closed）。
    """
    issues: list[str] = []
    stats = {"claims": 0, "proofs": 0}
    if schema is not None:
        issues += [f"schema: {msg}" for msg in json_schema.json_schema_check(bundle, schema)]
    if not isinstance(bundle, dict):
        return {"ok": False, "issues": issues + ["bundle 不是对象"], "stats": stats}
    claims = bundle.get("claims")
    if not isinstance(claims, list) or not claims:
        return {"ok": False, "issues": issues + ["缺 claims"], "stats": stats}
    stats["claims"] = len(claims)
    bundle_id = bundle.get("bundle_id")
    if not is_digest(bundle_id):
        issues.append("bundle_id 非法（须 64 位小写 hex）")
    ids = [c.get("id") for c in claims if isinstance(c, dict)]
    if len(ids) != len(claims):
        issues.append("claims 里有非对象条目")
    elif len(set(ids)) != len(ids):
        issues.append("claim id 重复")
    leaves = []
    for index, claim in enumerate(claims):
        if not isinstance(claim, dict):
            leaves.append(b"")
            continue
        try:
            leaves.append(claim_leaf(bundle_id, index, claim))
        except ValueError as exc:
            issues.append(f"claims[{index}]: {exc}")
            leaves.append(b"")
    root = merkle_root(leaves) if leaves and all(leaves) else None
    if root is None or root.hex() != bundle.get("merkle_root"):
        issues.append("merkle_root 与 claims 重算不一致")
    proofs = bundle.get("inclusion_proofs")
    if not isinstance(proofs, list) or not proofs:
        issues.append("缺 inclusion_proofs")
        return {"ok": not issues, "issues": issues, "stats": stats}
    stats["proofs"] = len(proofs)
    seen = set()
    for item in proofs:
        if not isinstance(item, dict):
            issues.append("inclusion_proofs 里有非对象条目")
            continue
        index = item.get("index")
        if not isinstance(index, int) or isinstance(index, bool) or not 0 <= index < len(claims):
            issues.append(f"proof index 越界：{index!r}")
            continue
        if index in seen:
            issues.append(f"proof index 重复：{index}")
            continue
        seen.add(index)
        check = verify_claim(bundle, index, item)
        if not check["ok"]:
            issues.append(f"claims[{index}] 验证失败：{check.get('reason')}")
    missing = sorted(set(range(len(claims))) - seen)
    if missing:
        issues.append(f"proof 未覆盖 claims：{missing[:5]}")
    return {"ok": not issues, "issues": issues, "stats": stats}
