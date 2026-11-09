"""密钥透明目录 v0（nf-key-transparency/1）：补「这把公钥属于谁」的最后一环。

问题（2026-11-08）：现有吊销信任锚（nf-revocation-trust/1）靠「钉根 + 有界委派」，
它能判「这把公钥是否被某个根承认」，但**判不了分叉**——两个验证方可能看到不同的密钥集
（一方被喂了伪造目录），而被骗的一方无从发现。

做法（借鉴 IETF Key Transparency 协议的关键机制，见 docs/ccos/key-transparency-v0.md）：
- **版本化根**：每版密钥目录 → 排序叶 → Merkle 根；
- **只追加日志**：每版记录 {seq, root, prev}，链式相连；verify 检查链与根可复算；
- **包含证明**：单个 key_id 可只凭 proof 折叠到根（客户端不必存全量）；
- **一致性**：新版本必须能追到旧版本的根（链上有该 root），否则视为分叉；
- **分叉见证**：同版本不同根 / 链上缺旧根 → 产出结构化 witness（这是钉根方案没有的）。

**不做什么**（诚实边界）：不做 KT 的**前缀树**（可搜索可证），只做「键值表 + 版本链」；
因此查找是 O(n) 且目录大小会暴露——隐私面尚未做；abridged proof / 审计者角色也未做。
这些在 docs 里标为后续，不假装已实现。
"""
from __future__ import annotations

import json
from typing import Any

from core import receipts

SCHEMA = "nf-key-transparency/1"
GUIDE = "修复指引："
HEX64_LEN = 64


def canonical(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":")).encode("utf-8")


def _leaf_payload(key_id: str, pub: str) -> bytes:
    return canonical({"id": key_id, "pub": pub})


def _keys_leaves(keys: dict[str, str]) -> list[bytes]:
    return [receipts.leaf_hash(_leaf_payload(k, keys[k])) for k in sorted(keys)]


def _root(keys: dict[str, str]) -> str:
    leaves = _keys_leaves(keys)
    root = receipts.merkle_root(leaves)
    return root.hex() if root else ""


def _validate_keys(keys: Any) -> list[str]:
    issues: list[str] = []
    if not isinstance(keys, dict) or not keys:
        return ["keys 必须是非空对象（" + GUIDE + "key_id → 公钥 hex）"]
    for kid, pub in keys.items():
        if not isinstance(kid, str) or not kid.strip():
            issues.append("key_id 必须是非空字符串（" + GUIDE + "用稳定的标识，如 org/team/key-1）")
        if not isinstance(pub, str) or len(pub) != HEX64_LEN:
            issues.append("公钥必须是 64 位十六进制（" + GUIDE + "key_id=" + str(kid))
    return issues


def build(keys: dict[str, str], prev: dict[str, Any] | None = None) -> dict[str, Any]:
    """造一版密钥目录（可接在 prev 后面）→ nf-key-transparency/1。"""
    issues = _validate_keys(keys)
    if issues:
        raise ValueError("密钥目录不合法：" + "；".join(issues[:3]))
    version = 1
    log: list[dict[str, Any]] = []
    if prev is not None:
        pv = verify(prev)
        if not pv["ok"]:
            raise ValueError("上一版目录不可用：" + "；".join(pv["issues"][:3]))
        version = int(prev["version"]) + 1
        log = [dict(item) for item in prev["log"]]
    root = _root(keys)
    prev_root = log[-1]["root"] if log else ""
    log.append({"seq": version, "root": root, "prev": prev_root})
    return {"schema": SCHEMA, "version": version, "keys": dict(sorted(keys.items())),
            "root": root, "log": log,
            "note": "版本链只证追加；分叉检测需与另一份目录对比"
                    "（nf evidence revocations trust kt-split）"}


def verify(doc: Any) -> dict[str, Any]:
    """校验目录自洽 → {ok, verdict, version, root, issues, warnings}。"""
    res: dict[str, Any] = {"ok": False, "verdict": "invalid", "version": 0, "root": "",
                           "issues": [], "warnings": []}
    if not isinstance(doc, dict) or str(doc.get("schema") or "") != SCHEMA:
        res["issues"].append("目录 schema 不匹配（" + GUIDE + "需要 " + SCHEMA + "）")
        return res
    keys = doc.get("keys")
    issues = _validate_keys(keys)
    if issues:
        res["issues"].extend(issues)
        return res
    version = doc.get("version")
    if not isinstance(version, int) or version < 1:
        res["issues"].append("version 必须是 ≥1 的整数（" + GUIDE +
                "由 build/append 生成，不手改）")
        return res
    log = doc.get("log")
    if not isinstance(log, list) or len(log) != version:
        res["issues"].append("log 条数必须等于 version（" + GUIDE + "手改版本号会破坏链）")
        return res
    prev_root = ""
    for i, item in enumerate(log, 1):
        if not isinstance(item, dict):
            res["issues"].append("log[" + str(i) + "] 不是对象（" + GUIDE + "重建目录）")
            return res
        if item.get("seq") != i:
            res["issues"].append("log 序号不连续（" + GUIDE + "第 " + str(i) + " 条 seq="
                                 + str(item.get("seq")) + "）")
            return res
        if str(item.get("prev") or "") != prev_root:
            res["issues"].append("log 链断在第 " + str(i) + " 条（" + GUIDE +
                    "prev 必须等于上一条 root）")
            return res
        prev_root = str(item.get("root") or "")
        if len(prev_root) != HEX64_LEN:
            res["issues"].append("log[" + str(i) + "].root 必须是 64 位十六进制（" + GUIDE +
                    "重建）")
            return res
    recomputed = _root(keys)
    if recomputed != str(doc.get("root") or ""):
        res["issues"].append("重算根与记录不符（" + GUIDE + "keys 被改过或根被手改）")
        return res
    if recomputed != prev_root:
        res["issues"].append("最新 log 根与 keys 重算根不一致（" + GUIDE + "目录与日志不同源）")
        return res
    res.update({"ok": True, "verdict": "ok", "version": version, "root": recomputed})
    res["warnings"].append("目录只证「这一版自洽」；是否被分叉需与另一份目录对比")
    return res


def lookup(doc: dict[str, Any], key_id: str) -> dict[str, Any]:
    """单键查找 + 包含证明（客户端只需 proof 与 root 即可离线验）。"""
    res: dict[str, Any] = {"ok": False, "key_id": key_id, "pub": "", "leaf": "",
                           "root": str(doc.get("root") or ""), "proof": [], "issues": []}
    checked = verify(doc)
    if not checked["ok"]:
        res["issues"].extend(checked["issues"])
        return res
    keys = dict(doc["keys"])
    if key_id not in keys:
        res["issues"].append("目录里没有该 key_id（" + GUIDE + "核对 id；或该键从未发布）")
        return res
    names = sorted(keys)
    leaves = _keys_leaves(keys)
    idx = names.index(key_id)
    res.update({"ok": True, "pub": keys[key_id], "leaf": leaves[idx].hex(),
                "proof": receipts.inclusion_proof(leaves, idx)})
    return res


def verify_inclusion(bundle: dict[str, Any]) -> bool:
    """离线验包含证明：proof 折叠回 root 且 leaf 与 {id,pub} 同源。"""
    try:
        key_id = str(bundle["key_id"])
        pub = str(bundle["pub"])
        root = str(bundle["root"])
        proof = bundle["proof"]
    except (KeyError, TypeError):  # 结构缺键 = 证明不可验，按失败处理（不是静默跳过）
        return False
    if len(root) != HEX64_LEN or not isinstance(proof, list):
        return False
    leaf = receipts.leaf_hash(_leaf_payload(key_id, pub)).hex()
    if str(bundle.get("leaf") or "") and str(bundle["leaf"]) != leaf:
        return False
    return receipts.fold_proof(leaf, proof) == root


def consistency(old: dict[str, Any], new: dict[str, Any]) -> dict[str, Any]:
    """新版本是否为旧版本的**合法追加** → {ok, kind, witness}。"""
    res: dict[str, Any] = {"ok": False, "kind": "incomparable", "witness": {}, "issues": []}
    for doc, label in ((old, "old"), (new, "new")):
        checked = verify(doc)
        if not checked["ok"]:
            res["issues"].append(label + " 目录不可用：" + "；".join(checked["issues"][:2]))
            return res
    ov, nv = int(old["version"]), int(new["version"])
    if nv < ov:
        res["kind"] = "incomparable"
        res["issues"].append("新版本号小于旧版本（" + GUIDE + "换参数再比）")
        return res
    old_root = str(old["root"])
    new_log = new["log"]
    if nv == ov:
        if str(new["root"]) == old_root:
            res.update({"ok": True, "kind": "identical"})
            return res
        res.update({"kind": "split", "witness": {"version": ov,
                                                 "root_a": old_root,
                                                 "root_b": str(new["root"])}})
        res["issues"].append("同一版本出现两个不同根——分叉（" + GUIDE + "比对双方 log 与来源）")
        return res
    # nv > ov：旧根必须出现在新 log 的第 ov 条
    entry = new_log[ov - 1] if isinstance(new_log, list) and len(new_log) >= ov else None
    if not isinstance(entry, dict) or str(entry.get("root")) != old_root:
        res.update({"kind": "fork", "witness": {"old_version": ov, "old_root": old_root,
                                                "new_version": nv,
                                                "entry_at_old_version":
                                                    str((entry or {}).get("root") or "")}})
        res["issues"].append("新版本链上没有旧根——历史被改写或来自另一条链（" + GUIDE + "追来源）")
        return res
    res.update({"ok": True, "kind": "append",
                "witness": {"from": ov, "to": nv, "old_root": old_root,
                            "new_root": str(new["root"])}})
    return res


def split_witness(a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
    """双向分叉检测（对称）：谁都不是谁的合法延伸即报分叉。"""
    ab = consistency(a, b)
    ba = consistency(b, a)
    if ab["ok"] or ba["ok"]:
        return {"split": False, "detail": ab if ab["ok"] else ba}
    return {"split": True, "detail": {"ab": ab, "ba": ba},
            "note": "两份目录互不为延伸——分叉；把两侧 witness 一起留存"}
