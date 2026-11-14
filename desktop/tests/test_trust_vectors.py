#!/usr/bin/env python3
"""Trust Fabric 测试向量集判据（WP-03）：提交件 == 重算，且期望值可被独立复算。

为什么有它：向量集的价值全在**第三方可自验**——如果期望值只能由生成器自己的函数解释，
它就退化成生成器的快照，跨语言一致性无从谈起。本件用一套**独立实现**（本文件内的
canonical/域分隔/PAE/Merkle/step 链/准入/等级判定）逐族复算全部期望值，并做变异自证：
改一个期望值、删一族、复制一个 id 都必须被抓到。

范围：只判 results/trust/trust_vectors.json 与 scripts/trust_vectors.py 自洽（不改向量语义）。
同族判据：test_trust_schemas.py（结构门禁）、test_trust_threat_model_doc_contract.py（边界声明）。
契约：schema/族覆盖/唯一 id、确定性生成、独立复算、拒绝面（float/NaN/坏 tag/空 type/越界/断链/
错类型/错 issuer/等级与退出码）、无机器路径/密钥、变异自证。
"""
import base64
import copy
import hashlib
import importlib.util
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VECTORS_REL = "results/trust/trust_vectors.json"
GEN = ROOT / "scripts" / "trust_vectors.py"

TAG_RE = re.compile(r"^nf:[a-z0-9-]+:v[1-9][0-9]*:[a-z0-9-]+$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")
TS_RE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$")
LEVELS = ("T0", "T1", "T2", "T3", "T4")
MISSING = {"T1": "SIGNATURE-MISSING", "T2": "ANCHOR-MISSING",
           "T3": "WITNESS-MISSING", "T4": "PUBLIC-ANCHOR-MISSING"}
FACT = {"T1": "signature", "T2": "time_token", "T3": "transparency_sth",
        "T4": "public_anchor"}
MACHINE_MARKERS = ("C:\\", "\\\\Users", "/home/", "AppData", "PRIVATE KEY",
                   "BEGIN OPENSSH", "ghp_", "AKIA")


def _load_generator():
    spec = importlib.util.spec_from_file_location("nf_trust_vectors", GEN)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _doc():
    return json.loads((ROOT / VECTORS_REL).read_text(encoding="utf-8"))


# ---------------------------------------------------------------- 独立参考实现
def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canon_strict(obj):
    """独立实现：float/NaN/Infinity 一律拒绝；其余按 keys 排序紧凑编码。"""
    stack = [obj]
    while stack:
        cur = stack.pop()
        if isinstance(cur, float):
            raise ValueError("NONFINITE-FORBIDDEN"
                             if cur != cur or cur in (float("inf"), float("-inf"))
                             else "FLOAT-FORBIDDEN")
        if isinstance(cur, dict):
            for key, sub in cur.items():
                if not isinstance(key, str):
                    raise ValueError("KEY-NOT-STR")
                stack.append(sub)
        elif isinstance(cur, list):
            stack.extend(cur)
    return json.dumps(obj, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode()


def _domain(tag: str, payload: bytes) -> str:
    if not TAG_RE.match(tag):
        raise ValueError("TAG-FORMAT")
    return _sha(tag.encode() + b"\x00" + payload)


def _pae(ptype: bytes, payload: bytes) -> bytes:
    if not ptype:
        raise ValueError("PAE-EMPTY-TYPE")
    return (b"DSSEv1 " + str(len(ptype)).encode() + b" " + ptype + b" "
            + str(len(payload)).encode() + b" " + payload)


def _leaf(data: bytes) -> str:
    return _sha(b"\x00" + data)


def _node(left: str, right: str) -> str:
    return _sha(b"\x01" + bytes.fromhex(left) + bytes.fromhex(right))


def _split(n: int) -> int:
    k = 1
    while k * 2 < n:
        k *= 2
    return k


def _root(leaves: list) -> str:
    if len(leaves) == 1:
        return leaves[0]
    mid = _split(len(leaves))
    return _node(_root(leaves[:mid]), _root(leaves[mid:]))


def _proof(leaves: list, index: int) -> list:
    if not 0 <= index < len(leaves):
        raise IndexError("INDEX-OUT-OF-RANGE")
    if len(leaves) == 1:
        return []
    mid = _split(len(leaves))
    if index < mid:
        return _proof(leaves[:mid], index) + [{"side": "right",
                                              "hash": _root(leaves[mid:])}]
    return _proof(leaves[mid:], index - mid) + [{"side": "left",
                                                "hash": _root(leaves[:mid])}]


def _fold(leaf: str, proof: list) -> str:
    cur = leaf
    for step in proof:
        cur = _node(step["hash"], cur) if step["side"] == "left" else _node(cur, step["hash"])
    return cur


def _step_digest(step: dict, prev: str) -> str:
    body = {
        "process_id": step["process_id"],
        "step": step["seq"],
        "prev": prev,
        "actor": {"id": step["actor_id"], "kind": "agent"},
        "authorization": {"kind": "human", "digest": "d" * 64},
        "input_refs": [],
        "output_refs": [],
        "state_digest": step["state_digest"],
        "type": step["type"],
    }
    return _domain("nf:process:v1:step", _canon_strict(body))


def _chain(steps: list) -> dict:
    head = "0" * 64
    digests = []
    for i, step in enumerate(steps):
        if not isinstance(step.get("prev"), str) or not HEX64.match(step["prev"]):
            return {"valid": False, "reason": "PREV-FORMAT"}
        if step.get("seq") != i + 1:
            return {"valid": False, "reason": "SEQ-ORDER"}
        if step["prev"] != head:
            return {"valid": False, "reason": "PREV-MISMATCH"}
        head = _step_digest(step, head)
        digests.append(head)
    return {"valid": True, "digests": digests, "head": head}


def _entity_structure(entity: dict):
    allowed = {"schema", "type", "subject", "issuer", "issued_at", "payload_digest",
               "refs", "validity"}
    required = {"schema", "type", "subject", "issuer", "issued_at", "payload_digest"}
    if not required <= set(entity):
        return "SCHEMA-INVALID"
    if set(entity) - allowed:
        return "SCHEMA-INVALID"
    if entity["schema"] != "nf-entity/1":
        return "SCHEMA-INVALID"
    if not re.match(r"^[a-z][a-z0-9-]*$", entity["type"]):
        return "SCHEMA-INVALID"
    subject = entity["subject"]
    if not isinstance(subject, dict) or set(subject) != {"kind", "ref", "digest"}:
        return "SCHEMA-INVALID"
    if subject["kind"] not in ("claim", "evidence", "process-step", "bundle", "card", "artifact"):
        return "SCHEMA-INVALID"
    if not isinstance(subject["ref"], str) or not subject["ref"]:
        return "SCHEMA-INVALID"
    for key in ("digest",):
        if not HEX64.match(subject[key]):
            return "SCHEMA-INVALID"
    if not HEX64.match(entity["payload_digest"]) or not TS_RE.match(entity["issued_at"]):
        return "SCHEMA-INVALID"
    return ""


def _admissible(entity: dict, policy: dict) -> dict:
    why = _entity_structure(entity)
    if why:
        return {"admissible": False, "reason": why}
    issuer = next((it for it in policy["issuers"] if it["id"] == entity["issuer"]), None)
    if issuer is None:
        return {"admissible": False, "reason": "ISSUER-UNKNOWN"}
    if entity["type"] not in issuer.get("types", []):
        return {"admissible": False, "reason": "TYPE-NOT-ALLOWED"}
    return {"admissible": True}


def _decide(case: dict) -> dict:
    if not case.get("policy_ok", True):
        return {"achieved": "none", "exit_code": 2, "missing": ["POLICY-INVALID"]}
    facts = case["facts"]
    if facts.get("hash") != "ok" or any(facts.get(k) == "invalid" for k in FACT.values()):
        return {"achieved": "none", "exit_code": 1, "missing": []}
    achieved = "T0"
    for level in LEVELS[1:]:
        if facts.get(FACT[level]) != "ok":
            break
        achieved = level
    required = case["required_level"]
    if LEVELS.index(achieved) >= LEVELS.index(required):
        return {"achieved": achieved, "exit_code": 0, "missing": []}
    missing = [MISSING[level] for level in LEVELS[LEVELS.index(achieved) + 1:
                                                LEVELS.index(required) + 1]]
    return {"achieved": achieved, "exit_code": 2, "missing": missing}


# ---------------------------------------------------------------- 判据
def vector_issues(doc: dict) -> list:
    issues = []
    if doc.get("schema") != "nf-trust-vectors/1":
        issues.append("schema 名称不符")
    vectors = doc.get("vectors") or []
    if doc.get("count") != len(vectors):
        issues.append("count 与 vectors 长度不一致")
    ids = [v.get("id") for v in vectors]
    if len(ids) != len(set(ids)):
        issues.append("向量 id 重复")
    families = {}
    for vec in vectors:
        families[vec.get("family")] = families.get(vec.get("family"), 0) + 1
    if families != doc.get("families"):
        issues.append("families 声明与实计不一致")
    for need in ("canonical", "domain", "pae", "merkle", "process", "entity", "level"):
        if families.get(need, 0) < 1:
            issues.append(f"缺向量族：{need}")
    if (doc.get("cross_language") or {}).get("target") != "G4":
        issues.append("cross_language 声明缺失（跨语言 parity 属 G4）")
    rules = doc.get("rules") or {}
    for key in ("canonical", "domain", "pae", "merkle", "process", "admissibility", "level"):
        if not rules.get(key):
            issues.append(f"rules 缺 {key} 的规则文本")
    if b"\r\n" in (ROOT / VECTORS_REL).read_bytes():
        issues.append("向量集含 CRLF")
    text = json.dumps(doc, ensure_ascii=False)
    for marker in MACHINE_MARKERS:
        if marker in text:
            issues.append(f"向量集夹带机器路径/密钥标记：{marker}")

    for vec in vectors:
        family = vec.get("family")
        inp = vec.get("input") or {}
        exp = vec.get("expected") or {}
        if not vec.get("desc"):
            issues.append(f"{vec.get('id')} 缺 desc")
        if family == "canonical":
            value = inp.get("value")
            if exp.get("valid"):
                try:
                    raw = _canon_strict(value)
                except ValueError as exc:
                    issues.append(f"{vec['id']} 独立复算失败：{exc}")
                    continue
                if exp.get("canonical_utf8") != raw.decode() or exp.get("sha256") != _sha(raw):
                    issues.append(f"{vec['id']} canonical 期望值与独立复算不符")
            else:
                probe = _nan_probe(value) if _has_nonfinite(value) else value
                try:
                    _canon_strict(probe)
                except ValueError as exc:
                    if exp.get("reason") not in str(exc):
                        issues.append(f"{vec['id']} 拒绝原因不符：{exc}")
                else:
                    issues.append(f"{vec['id']} 该拒绝却通过了")
        elif family == "domain":
            tag = inp.get("tag", "")
            payload = (inp.get("payload_utf8") or "").encode()
            if exp.get("tag_ok"):
                try:
                    mine = _domain(tag, payload)
                except ValueError as exc:
                    issues.append(f"{vec['id']} 独立复算失败：{exc}")
                    continue
                if exp.get("digest") != mine:
                    issues.append(f"{vec['id']} 域摘要不符")
                if exp.get("distinct_from") == mine:
                    issues.append(f"{vec['id']} 碰撞（distinct_from 与 digest 相同）")
            else:
                try:
                    _domain(tag, payload)
                except ValueError:
                    pass
                else:
                    issues.append(f"{vec['id']} 非法 tag 未被拒")
        elif family == "pae":
            ptype = (inp.get("payload_type_utf8") or "").encode()
            payload = base64.b64decode(inp.get("payload_b64") or "")
            if exp.get("valid"):
                raw = _pae(ptype, payload)
                if (exp.get("pae_b64") != base64.b64encode(raw).decode()
                        or exp.get("pae_sha256") != _sha(raw)):
                    issues.append(f"{vec['id']} PAE 期望值与独立复算不符")
            else:
                try:
                    _pae(ptype, payload)
                except ValueError:
                    pass
                else:
                    issues.append(f"{vec['id']} 空 type 未被拒")
        elif family == "merkle":
            if exp.get("valid"):
                payloads = [s.encode() for s in inp.get("leaves_utf8") or []]
                leaves = [_leaf(p) for p in payloads]
                root = _root(leaves)
                if exp.get("leaf_hashes") != leaves or exp.get("root") != root:
                    issues.append(f"{vec['id']} Merkle 期望值与独立复算不符")
                for proof in exp.get("proofs") or []:
                    if _fold(leaves[proof["index"]], proof["proof"]) != root:
                        issues.append(f"{vec['id']} proof 折叠不到根")
                    if proof.get("fold_root") != root:
                        issues.append(f"{vec['id']} fold_root 不符")
            else:
                payloads = [s.encode() for s in inp.get("leaves_utf8") or []]
                leaves = [_leaf(p) for p in payloads]
                try:
                    _proof(leaves, int(inp.get("index", -1)))
                except IndexError:
                    pass
                else:
                    issues.append(f"{vec['id']} 越界下标未被拒")
        elif family == "process":
            expected = _chain(inp.get("steps") or [])
            if expected != exp:
                issues.append(f"{vec['id']} 链期望值与独立复算不符：{expected}")
        elif family == "entity":
            expected = _admissible(inp.get("entity") or {}, inp.get("policy") or {})
            if expected != exp:
                issues.append(f"{vec['id']} 准入期望值与独立复算不符：{expected}")
        elif family == "level":
            expected = _decide(inp)
            if expected != exp:
                issues.append(f"{vec['id']} 等级期望值与独立复算不符：{expected}")
        else:
            issues.append(f"{vec.get('id')} 未知向量族：{family}")
    return issues


def _has_nonfinite(value) -> bool:
    if isinstance(value, dict):
        return any(key == "nonfinite" or _has_nonfinite(sub) for key, sub in value.items())
    if isinstance(value, list):
        return any(_has_nonfinite(sub) for sub in value)
    return False


def _nan_probe(value):
    if isinstance(value, dict):
        return {key: float("nan") if key == "nonfinite" else _nan_probe(sub)
                for key, sub in value.items()}
    if isinstance(value, list):
        return [_nan_probe(sub) for sub in value]
    return value


class TrustVectorsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.gen = _load_generator()
        cls.doc = _doc()

    def test_vectors_consistent(self):
        self.assertEqual([], vector_issues(self.doc), "向量集与独立复算不一致")

    def test_committed_equals_live(self):
        live = self.gen.render(self.gen.build_vectors())
        self.assertEqual((ROOT / VECTORS_REL).read_bytes(), live,
                         "提交件与重算不一致（修复指引：核实期望值后重跑 --write）")

    def test_generation_is_deterministic(self):
        self.assertEqual(self.gen.render(self.gen.build_vectors()),
                         self.gen.render(self.gen.build_vectors()))

    def test_check_entrypoint_agrees(self):
        issues, _live = self.gen.check()
        self.assertEqual([], issues)

    def test_contract_catches_mutations(self):
        def mutate(fn):
            bad = copy.deepcopy(self.doc)
            fn(bad)
            return vector_issues(bad)

        def flip_root(doc):
            vec = next(v for v in doc["vectors"] if v["id"] == "MK-01")
            vec["expected"]["root"] = "0" * 64

        def flip_pae(doc):
            vec = next(v for v in doc["vectors"] if v["id"] == "PA-02")
            vec["expected"]["pae_sha256"] = "0" * 64

        def flip_canonical(doc):
            vec = next(v for v in doc["vectors"] if v["id"] == "CV-01")
            vec["expected"]["canonical_utf8"] = "{}"

        def flip_level(doc):
            vec = next(v for v in doc["vectors"] if v["id"] == "LV-03")
            vec["expected"]["exit_code"] = 0

        def flip_entity(doc):
            vec = next(v for v in doc["vectors"] if v["id"] == "EA-02")
            vec["expected"] = {"admissible": True}

        def flip_chain(doc):
            vec = next(v for v in doc["vectors"] if v["id"] == "PR-01")
            vec["expected"]["head"] = "0" * 64

        def drop_family(doc):
            doc["vectors"] = [v for v in doc["vectors"] if v["family"] != "process"]
            doc["count"] = len(doc["vectors"])

        def dup_id(doc):
            doc["vectors"][1]["id"] = doc["vectors"][0]["id"]

        def machine_path(doc):
            doc["vectors"][0]["desc"] += " C:\\Users\\x"

        for fn, needle in ((flip_root, "Merkle"), (flip_pae, "PAE"),
                           (flip_canonical, "canonical"), (flip_level, "等级"),
                           (flip_entity, "准入"), (flip_chain, "链"),
                           (drop_family, "families"), (dup_id, "id 重复"),
                           (machine_path, "机器路径")):
            issues = mutate(fn)
            self.assertTrue(any(needle in issue for issue in issues),
                            f"{fn.__name__} 变异未被抓到：{issues[:3]}")

    def test_entity_vectors_use_frozen_schema(self):
        schema = json.loads((ROOT / "protocol" / "trust" / "entity.schema.json")
                            .read_text(encoding="utf-8"))
        self.assertEqual("nf-entity/1", schema["properties"]["schema"]["const"])
        for vec in self.doc["vectors"]:
            if vec["family"] != "entity":
                continue
            entity = vec["input"]["entity"]
            self.assertIn("schema", entity)
            self.assertEqual("nf-entity/1", entity["schema"])


if __name__ == "__main__":
    unittest.main()
