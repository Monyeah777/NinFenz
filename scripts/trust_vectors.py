#!/usr/bin/env python3
"""Trust Fabric 测试向量集：把 G1/G2 的实现契约固化成跨语言可复核的单一产物。

为什么有它（WP-03）：
- 计划 §11.2 WP-03 要求「测试向量」先于实现；G1（Merkle/claim bundle/prev 链）与
  G2（DSSE/锚/等级）的判定必须由**一份不绑定本仓代码的 JSON**锚定，否则跨实现/跨语言
  一致性无处可比（仓内已有 results/ccos/evidence_verdict_vectors.json 同族先例）。
- 本文件里的期望值由**独立参考函数**算出（canonical/域分隔/PAE/Merkle/step 链/等级判定），
  与将来 core/trust 的实现互为双实现：谁跟向量不一致谁红。

产物（results/trust/trust_vectors.json，schema nf-trust-vectors/1）每条：
  id / family / desc / input / expected。第三方只读这一份 JSON 即可自验，不需要读本仓代码。

纪律：确定性（无墙钟、无随机、固定输入），--write 两次逐字节一致；
--check 比对提交件与重算；family 覆盖与「期望值内部自洽」在生成期断言，不静默放过。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import atomic_write, json_doc, json_schema  # noqa: E402

SCHEMA = "nf-trust-vectors/1"
OUT_REL = "results/trust/trust_vectors.json"
ZERO = "0" * 64
TAG_RE = re.compile(r"^nf:[a-z0-9-]+:v[1-9][0-9]*:[a-z0-9-]+$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")
LEVELS = ("T0", "T1", "T2", "T3", "T4")
MISSING_CODES = {
    "T1": "SIGNATURE-MISSING",
    "T2": "ANCHOR-MISSING",
    "T3": "WITNESS-MISSING",
    "T4": "PUBLIC-ANCHOR-MISSING",
}
FACT_OF_LEVEL = {
    "T1": "signature",
    "T2": "time_token",
    "T3": "transparency_sth",
    "T4": "public_anchor",
}

AUTH_DIGEST = "d" * 64
STATE1 = "1" * 64
STATE2 = "2" * 64
STATE3 = "3" * 64


# ---------------------------------------------------------------- 参考实现
def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _reject_floats(value, path: str = "$") -> None:
    if isinstance(value, float):
        raise ValueError(f"{path}: 拒绝 float（修复指引：改用 int/string/bool/null/list/object）")
    if isinstance(value, dict):
        for key, sub in value.items():
            if not isinstance(key, str):
                raise ValueError(f"{path}: 对象键必须是字符串（修复指引：JSON 对象键只收字符串）")
            _reject_floats(sub, f"{path}.{key}")
    elif isinstance(value, list):
        for i, sub in enumerate(value):
            _reject_floats(sub, f"{path}[{i}]")


def canonical_bytes(obj) -> bytes:
    """参考实现：键排序 + UTF-8 + 紧凑分隔；只收 int/bool/null/str/list/object。"""
    _reject_floats(obj)
    return json.dumps(obj, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def domain_digest(tag: str, payload: bytes) -> str:
    if not TAG_RE.match(tag):
        raise ValueError(f"域标签格式非法：{tag}（修复指引：形如 nf:<schema>:v1:<field>）")
    return _sha256_hex(tag.encode("utf-8") + b"\x00" + payload)


def pae(payload_type: bytes, payload: bytes) -> bytes:
    return (b"DSSEv1 " + str(len(payload_type)).encode() + b" " + payload_type
            + b" " + str(len(payload)).encode() + b" " + payload)


def _leaf_hash(payload: bytes) -> str:
    return _sha256_hex(b"\x00" + payload)


def _node_hash(left: str, right: str) -> str:
    return _sha256_hex(b"\x01" + bytes.fromhex(left) + bytes.fromhex(right))


def _largest_pow2_below(n: int) -> int:
    k = 1
    while k * 2 < n:
        k *= 2
    return k


def merkle_root(leaves: list) -> str:
    if not leaves:
        raise ValueError("空叶集没有根（修复指引：至少给 1 个叶；空集的根无定义）")
    if len(leaves) == 1:
        return leaves[0]
    mid = _largest_pow2_below(len(leaves))
    return _node_hash(merkle_root(leaves[:mid]), merkle_root(leaves[mid:]))


def audit_path(leaves: list, index: int) -> list:
    if not 0 <= index < len(leaves):
        raise ValueError("index 越界（修复指引：index 取 0..len(leaves)-1）")
    if len(leaves) == 1:
        return []
    mid = _largest_pow2_below(len(leaves))
    if index < mid:
        return audit_path(leaves[:mid], index) + [
            {"side": "right", "hash": merkle_root(leaves[mid:])}]
    return audit_path(leaves[mid:], index - mid) + [
        {"side": "left", "hash": merkle_root(leaves[:mid])}]


def fold_proof(leaf: str, proof: list) -> str:
    cur = leaf
    for step in proof:
        cur = (_node_hash(step["hash"], cur) if step["side"] == "left"
               else _node_hash(cur, step["hash"]))
    return cur


def step_digest(step: dict) -> str:
    """单步摘要：canonical(step 去 digest) 经域分隔（step 为 nf-process/1 形状）。"""
    if not isinstance(step, dict):
        raise ValueError("step 必须是对象（修复指引：见 nf-process/1 定义）")
    body = {key: value for key, value in step.items() if key != "digest"}
    return domain_digest("nf:process:v1:step", canonical_bytes(body))


def chain_result(steps: list) -> dict:
    """按 prev 链规则重算；返回 {valid, digests, head} 或 {valid: false, reason}。"""
    digests = []
    head = ZERO
    for index, step in enumerate(steps):
        if not isinstance(step, dict):
            return {"valid": False, "reason": "STEP-NOT-OBJECT"}
        if not isinstance(step.get("prev"), str) or not HEX64.match(step["prev"]):
            return {"valid": False, "reason": "PREV-FORMAT"}
        if step.get("step") != index + 1:
            return {"valid": False, "reason": "SEQ-ORDER"}
        if step["prev"] != head:
            return {"valid": False, "reason": "PREV-MISMATCH"}
        head = step_digest(step)
        digests.append(head)
    return {"valid": True, "digests": digests, "head": head}


def admissibility(entity: dict, policy: dict, entity_schema: dict) -> dict:
    """实体准入：结构过 nf-entity/1 + issuer 在册 + type 被该 issuer 授权。"""
    errors = json_schema.json_schema_check(entity, entity_schema)
    if errors:
        return {"admissible": False, "reason": "SCHEMA-INVALID"}
    issuer = next((it for it in policy["issuers"] if it["id"] == entity["issuer"]), None)
    if issuer is None:
        return {"admissible": False, "reason": "ISSUER-UNKNOWN"}
    if entity["type"] not in issuer.get("types", []):
        return {"admissible": False, "reason": "TYPE-NOT-ALLOWED"}
    return {"admissible": True}


def level_decision(case: dict) -> dict:
    if not case.get("policy_ok", True):
        return {"achieved": "none", "exit_code": 2, "missing": ["POLICY-INVALID"]}
    facts = case["facts"]
    if facts.get("hash") != "ok" or any(
            facts.get(key) == "invalid" for key in FACT_OF_LEVEL.values()):
        return {"achieved": "none", "exit_code": 1, "missing": []}
    achieved = "T0"
    for level in LEVELS[1:]:
        if facts.get(FACT_OF_LEVEL[level]) != "ok":
            break
        achieved = level
    required = case["required_level"]
    if LEVELS.index(achieved) >= LEVELS.index(required):
        return {"achieved": achieved, "exit_code": 0, "missing": []}
    missing = [MISSING_CODES[level] for level in LEVELS[LEVELS.index(achieved) + 1:
                                                       LEVELS.index(required) + 1]]
    return {"achieved": achieved, "exit_code": 2, "missing": missing}


# ---------------------------------------------------------------- 向量构造
def _canonical_vectors() -> list:
    out = []
    cases = [
        ("CV-01", "键排序：b 在 a 前也必须规范成 a,b", {"b": 1, "a": 2}),
        ("CV-02", "非 ASCII 原样 UTF-8（不转 \\u 转义）", {"名": "值"}),
        ("CV-03", "嵌套对象/数组 + 紧凑分隔", {"a": [1, 2], "b": {"c": True}}),
    ]
    for vec_id, desc, value in cases:
        raw = canonical_bytes(value)
        out.append({"id": vec_id, "family": "canonical", "desc": desc,
                    "input": {"value": value},
                    "expected": {"valid": True, "canonical_utf8": raw.decode("utf-8"),
                                 "sha256": _sha256_hex(raw)}})
    out.append({"id": "CV-04", "family": "canonical", "desc": "float 拒绝（跨语言格式不确定）",
                "input": {"value": {"x": 1.5}},
                "expected": {"valid": False, "reason": "FLOAT-FORBIDDEN"}})
    out.append({"id": "CV-05", "family": "canonical",
                "desc": "NaN 拒绝（JSON 标准不允许；nonfinite 一律拒）",
                "input": {"value": {"x": {"nonfinite": "NaN"}}},
                "expected": {"valid": False, "reason": "NONFINITE-FORBIDDEN"}})
    return out


def _domain_vectors() -> list:
    tag_a = "nf:claim-bundle:v1:leaf"
    tag_b = "nf:claim-bundle:v1:root"
    digest_a = domain_digest(tag_a, b"abc")
    payload = tag_b.encode("utf-8")
    return [
        {"id": "DM-01", "family": "domain", "desc": "域分隔摘要：tag + 0x00 + payload",
         "input": {"tag": tag_a, "payload_utf8": "abc"},
         "expected": {"tag_ok": True, "digest": digest_a}},
        {"id": "DM-02", "family": "domain", "desc": "不同字段的 tag 必不同摘要",
         "input": {"tag": tag_b, "payload_utf8": "abc"},
         "expected": {"tag_ok": True,
                      "digest": domain_digest(tag_b, b"abc"),
                      "distinct_from": digest_a}},
        {"id": "DM-03", "family": "domain",
         "desc": "tag 走私：payload 等于另一个 tag 也不与那一个的摘要相同",
         "input": {"tag": tag_a, "payload_utf8": tag_b},
         "expected": {"tag_ok": True, "digest": domain_digest(tag_a, payload),
                      "distinct_from": domain_digest(tag_b, payload)}},
        {"id": "DM-04", "family": "domain", "desc": "非法 tag 拒绝（缺版本段）",
         "input": {"tag": "nf:claim-bundle:leaf", "payload_utf8": "abc"},
         "expected": {"tag_ok": False, "reason": "TAG-FORMAT"}},
    ]


def _pae_vectors() -> list:
    ptype = b"application/vnd.nf.claim-bundle+json"
    payload = b'{"schema":"nf-claim-bundle/1"}'
    spec_ptype = b"http://example.com/HelloWorld"
    spec_payload = b"hello world"
    unicode_ptype = b"application/vnd.nf.text+utf8"
    unicode_payload = "中文".encode()
    cases = [
        ("PA-01", "PAE 基本形（DSSEv1 前缀 + 字节长度）", ptype, payload),
        ("PA-02", "规范示例：type 29 字节 / payload 11 字节", spec_ptype, spec_payload),
        ("PA-03", "长度按字节不按字符（中文 2 字 = 6 字节）", unicode_ptype, unicode_payload),
    ]
    import base64
    out = []
    for vec_id, desc, pt, pl in cases:
        raw = pae(pt, pl)
        out.append({"id": vec_id, "family": "pae", "desc": desc,
                    "input": {"payload_type_utf8": pt.decode("utf-8"),
                              "payload_b64": base64.b64encode(pl).decode("ascii")},
                    "expected": {"valid": True, "pae_b64": base64.b64encode(raw).decode("ascii"),
                                 "pae_sha256": _sha256_hex(raw)}})
    out.append({"id": "PA-04", "family": "pae", "desc": "空 payloadType 拒绝",
                "input": {"payload_type_utf8": "", "payload_b64": "aGk="},
                "expected": {"valid": False, "reason": "PAE-EMPTY-TYPE"}})
    return out


def _merkle_vectors() -> list:
    out = []
    for count in (1, 2, 3, 5):
        payloads = [f"leaf-{i}".encode() for i in range(count)]
        leaves = [_leaf_hash(p) for p in payloads]
        root = merkle_root(leaves)
        proofs = []
        for index in range(count):
            proof = audit_path(leaves, index)
            folded = fold_proof(leaves[index], proof)
            if folded != root:
                raise ValueError(f"向量自检失败：n={count} index={index} 折叠不到根"
                         "（修复指引：检查 proof 顺序与节点拼接方向）")
            proofs.append({"index": index, "fold_root": folded, "proof": proof})
        out.append({"id": f"MK-{count:02d}", "family": "merkle",
                    "desc": f"{count} 叶 RFC 6962 根与逐叶 inclusion proof",
                    "input": {"leaves_utf8": [p.decode() for p in payloads]},
                    "expected": {"valid": True, "leaf_hashes": leaves, "root": root,
                                 "proofs": proofs}})
    out.append({"id": "MK-06", "family": "merkle", "desc": "越界下标拒绝",
                "input": {"leaves_utf8": ["a", "b"], "index": 2},
                "expected": {"valid": False, "reason": "INDEX-OUT-OF-RANGE"}})
    return out


def _process_vectors() -> list:
    base = {
        "schema": "nf-process/1",
        "process_id": "proc-vector",
        "type": "task-step",
        "actor": {"id": "nf:agent:vec", "kind": "agent"},
        "authorization": {"kind": "human", "digest": AUTH_DIGEST},
        "input_refs": [],
        "output_refs": [],
    }
    steps = [
        {**base, "step": 1, "prev": ZERO, "state_digest": STATE1},
        {**base, "step": 2, "prev": "", "state_digest": STATE2},
        {**base, "step": 3, "prev": "", "state_digest": STATE3},
    ]
    steps[1]["prev"] = step_digest(steps[0])
    steps[2]["prev"] = step_digest(steps[1])
    chain = steps
    result = chain_result(chain)
    if not result["valid"]:
        raise ValueError("向量自检失败：step 链参考实现不自洽"
                         "（修复指引：检查 step_digest 的 canonical 口径）")
    deleted = [chain[0], chain[2]]
    return [
        {"id": "PR-01", "family": "process", "desc": "3 步 prev 链：digest 与链头",
         "input": {"steps": chain}, "expected": {"valid": True,
                                                 "digests": result["digests"],
                                                 "head": result["head"]}},
        {"id": "PR-02", "family": "process", "desc": "删中间一步：prev 指向被删摘要即断链",
         "input": {"steps": deleted}, "expected": chain_result(deleted)},
        {"id": "PR-03", "family": "process", "desc": "重排：seq 不连续即拒",
         "input": {"steps": [chain[0], chain[2], chain[1]]},
         "expected": chain_result([chain[0], chain[2], chain[1]])},
        {"id": "PR-04", "family": "process", "desc": "prev 非 64 位 hex 即拒",
         "input": {"steps": [chain[0], {**chain[1], "prev": "ABC"}, chain[2]]},
         "expected": {"valid": False, "reason": "PREV-FORMAT"}},
    ]


def _entity_vectors(entity_schema: dict, policy: dict) -> list:
    a, b, c = "a" * 64, "b" * 64, "c" * 64
    entity = {
        "schema": "nf-entity/1", "type": "claim",
        "subject": {"kind": "claim", "ref": "results/trust/demo/claim-01.json", "digest": a},
        "issuer": "nf:local", "issued_at": "2026-11-14T00:00:00Z", "payload_digest": b,
    }
    out = []
    cases = [
        ("EA-01", "合法实体：issuer 在册且 type 被授权", entity),
        ("EA-02", "type 未被该 issuer 授权", {**entity, "type": "process-step"}),
        ("EA-03", "issuer 不在策略内", {**entity, "issuer": "nf:evil"}),
        ("EA-04", "结构非法（未知顶层字段）", {**entity, "unexpected_extension": 1}),
    ]
    for vec_id, desc, ent in cases:
        out.append({"id": vec_id, "family": "entity", "desc": desc,
                    "input": {"entity": ent, "policy": policy},
                    "expected": admissibility(ent, policy, entity_schema)})
    out.append({"id": "EA-05", "family": "entity",
                "desc": "摘要格式非法（大写 hex）先被结构层拒绝",
                "input": {"entity": {**entity, "payload_digest": c.upper()}, "policy": policy},
                "expected": admissibility({**entity, "payload_digest": c.upper()},
                                          policy, entity_schema)})
    return out


def _level_vectors() -> list:
    base = {"hash": "ok", "signature": "none", "time_token": "none",
            "transparency_sth": "none", "public_anchor": "none"}
    cases = [
        ("LV-01", "T0 要求 + 只哈希自洽", {"policy_ok": True, "required_level": "T0",
                                          "facts": dict(base)}),
        ("LV-02", "T1 要求但无签名 → exit 2 缺 SIGNATURE-MISSING",
         {"policy_ok": True, "required_level": "T1", "facts": dict(base)}),
        ("LV-03", "T2 要求、签名有效但无 TSA → exit 2 缺 ANCHOR-MISSING",
         {"policy_ok": True, "required_level": "T2",
          "facts": {**base, "signature": "valid"}}),
        ("LV-04", "TSA token 无效 → exit 1（验证失败，不是不可判定）",
         {"policy_ok": True, "required_level": "T2",
          "facts": {**base, "signature": "valid", "time_token": "invalid"}}),
        ("LV-05", "T3 要求且签名/TSA/STH 均有效 → exit 0",
         {"policy_ok": True, "required_level": "T3",
          "facts": {**base, "signature": "valid", "time_token": "valid",
                    "transparency_sth": "valid"}}),
        ("LV-06", "T4 要求但无公共锚 → exit 2 缺 PUBLIC-ANCHOR-MISSING",
         {"policy_ok": True, "required_level": "T4",
          "facts": {**base, "signature": "valid", "time_token": "valid",
                    "transparency_sth": "valid"}}),
        ("LV-07", "策略非法（未知算法/不可解析）→ exit 2 缺 POLICY-INVALID",
         {"policy_ok": False, "required_level": "T2", "facts": dict(base)}),
    ]
    out = []
    for vec_id, desc, case in cases:
        out.append({"id": vec_id, "family": "level", "desc": desc,
                    "input": case, "expected": level_decision(case)})
    return out


def build_vectors() -> dict:
    entity_schema = json_doc.load(ROOT / "protocol" / "trust" / "entity.schema.json",
                                  dict, what="protocol/trust/entity.schema.json")
    policy = {
        "schema": "nf-trust-policy/1",
        "issuers": [{"id": "nf:local", "keyid": "nf:local:ed25519:2026",
                     "alg": "ed25519", "types": ["claim", "evidence"]}],
        "algorithms": ["ed25519"],
        "tsa_roots": [],
        "required_level": "T2",
        "anchors": {"tsa": True, "transparency": False, "witness_threshold": 0},
    }
    vectors = (_canonical_vectors() + _domain_vectors() + _pae_vectors()
               + _merkle_vectors() + _process_vectors()
               + _entity_vectors(entity_schema, policy) + _level_vectors())
    families = {}
    for vec in vectors:
        families[vec["family"]] = families.get(vec["family"], 0) + 1
    return {
        "schema": SCHEMA,
        "note": "Trust Fabric 测试向量（WP-03）：第三方只读本文件即可自验；"
                "期望值由独立参考实现算出，与 core/trust 实现互为双实现。",
        "cross_language": {
            "target": "G4",
            "note": "Python/Go/.NET parity 在 G4 接线；当前以独立参考实现双算取证。",
        },
        "rules": {
            "canonical": "json.dumps(sort_keys=True, ensure_ascii=False, separators=(',', ':'), "
                         "allow_nan=False)；只收 int/bool/null/str/list/object；"
                         "float/NaN/Infinity 拒绝",
            "domain": "sha256(tag_bytes + 0x00 + payload_bytes)；tag 须匹配 "
                      "^nf:[a-z0-9-]+:v[1-9][0-9]*:[a-z0-9-]+$",
            "pae": "DSSEv1 <len(ptype)> <ptype> <len(payload)> <payload>（长度按字节）",
            "merkle": "RFC 6962：leaf=sha256(0x00||data)，node=sha256(0x01||left||right)；"
                      "root 在最大 2 的幂处分裂；inclusion proof 自底向上",
            "process": "step_digest=sha256(tag(nf:process:v1:step)+0x00+"
                       "canonical(step 去 digest))；prev=上一步 digest"
                       "（创世=64 个 0）；seq 从 1 连续",
            "admissibility": "entity 先过 nf-entity/1 schema；issuer 须在 policy.issuers；"
                             "entity.type 须在 issuer.types",
            "level": "T0 哈希自洽；T1 +签名；T2 +RFC3161；T3 +STH（witness 达阈值）；T4 +公共锚；"
                     "任一 invalid → exit 1；achieved < required → exit 2",
        },
        "count": len(vectors),
        "families": dict(sorted(families.items())),
        "vectors": vectors,
    }


def render(doc: dict) -> bytes:
    return (json.dumps(doc, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def check() -> tuple:
    live = render(build_vectors())
    path = ROOT / OUT_REL
    if not path.is_file():
        return ([f"缺向量集 {OUT_REL}（修复指引：跑 python scripts/trust_vectors.py --write）"],
                live)
    if path.read_bytes() != live:
        return ([f"{OUT_REL} 与重算不一致（修复指引：核实期望值后重跑 --write 再提交）"], live)
    return [], live


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Trust Fabric 测试向量集（确定性生成）")
    ap.add_argument("--write", action="store_true", help="重写向量集")
    ap.add_argument("--check", action="store_true", help="比对提交件与重算（缺省动作）")
    ap.add_argument("--json", action="store_true", help="打印生成结果摘要")
    args = ap.parse_args(argv)
    doc = build_vectors()
    if args.write:
        dest = ROOT / OUT_REL
        atomic_write.write_bytes(dest, render(doc))
        print(f"✓ 已写入 {OUT_REL}（{doc['count']} 条向量 · {len(doc['families'])} 族）")
        return 0
    issues, _live = check()
    for issue in issues:
        print(f"✗ {issue}", file=sys.stderr)
    if args.json:
        print(json.dumps({"count": doc["count"], "families": doc["families"]},
                         ensure_ascii=False, sort_keys=True))
    if not issues:
        print(f"✓ 向量集自洽：{doc['count']} 条 · {len(doc['families'])} 族")
    return 0 if not issues else 1


if __name__ == "__main__":
    sys.exit(main())
