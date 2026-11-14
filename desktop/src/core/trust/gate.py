"""check45（G1）Trust 证据面门禁：对冻结向量复算 bundle 守恒 / 单 claim /
splice / prev 链 / 等级判定。

为什么单列 check（而不是只靠 unittest）：计划 §14.1 要求
「check45 = bundle 守恒 + 单 claim + splice」，
且判据必须**能在旧实现上变红**。本模块把判定做成可直接被 verify.sh 调用的 scan(root)：
- 输入 = 仓库内冻结向量（results/trust/trust_vectors.json）+ 冻结 schema；
- 复算 = 用 core.trust.{bundle,process,verify} 逐条对照 expected；
- 任一条不符 / 拒面漏拒（splice 未被拒）即 issue。
只看结果、不读测试代码：实现漂移会直接让门禁红。
"""
from __future__ import annotations

import copy
from pathlib import Path

from core import json_doc, json_schema
from core.trust import bundle as tb
from core.trust import process as tp
from core.trust import verify as tv

GUIDE = "修复指引："
VECTORS_REL = "results/trust/trust_vectors.json"
REQUIRED_FAMILIES = ("merkle", "process", "level")
#: 门禁自建的 claim 集（固定输入，保证确定性；不依赖任何本地运行态）。
FIXED_CLAIMS = [{"id": f"G45-{i:03d}", "type": "evidence",
                 "subject_digest": "b" * 64, "payload_digest": "c" * 64}
                for i in range(4)]
FIXED_BUNDLE_ID = "9" * 64


def _families(vectors: list) -> dict:
    out = {}
    for vec in vectors:
        out.setdefault(vec.get("family"), []).append(vec)
    return out


def _check_merkle(family: list, issues: list, stats: dict) -> None:
    for vec in family:
        expected = vec.get("expected") or {}
        if not expected.get("valid"):
            leaves = [tb.leaf_hash(s.encode()) for s in vec["input"]["leaves_utf8"]]
            try:
                tb.inclusion_proof(leaves, int(vec["input"]["index"]))
            except IndexError:
                stats["merkle"] += 1
                continue
            issues.append(f"{vec['id']}：越界下标未被拒（{GUIDE}收紧密闭集）")
            continue
        leaves = [tb.leaf_hash(s.encode()) for s in vec["input"]["leaves_utf8"]]
        if [leaf.hex() for leaf in leaves] != expected.get("leaf_hashes"):
            issues.append(f"{vec['id']}：叶哈希与向量不符")
        root = tb.merkle_root(leaves)
        if root is None or root.hex() != expected.get("root"):
            issues.append(f"{vec['id']}：Merkle 根与向量不符")
            continue
        for proof in expected.get("proofs") or []:
            folded = tb.fold_proof(leaves[proof["index"]].hex(), proof["proof"])
            if folded != expected["root"]:
                issues.append(f"{vec['id']}：index={proof['index']} proof 折叠不到根")
        stats["merkle"] += 1


def _check_live_bundle(root: str, issues: list, stats: dict) -> None:
    schema = tb.load_schema(root)
    built = tb.build_bundle(FIXED_BUNDLE_ID, "protocol/trust/claim-bundle.schema.json",
                            copy.deepcopy(FIXED_CLAIMS))
    problems = json_schema.json_schema_check(built, schema)
    if problems:
        issues.append(f"自建 bundle 不合冻结 schema：{problems[0]}")
    run = tb.verify_bundle(built, schema)
    if not run["ok"]:
        issues.append(f"自建 bundle 整包校验失败：{run['issues'][:2]}")
    one = tb.verify_claim(built, 2)
    if not one["ok"]:
        issues.append(f"单 claim 验证失败：{one.get('reason')}")
    spliced = copy.deepcopy(built)
    spliced["bundle_id"] = "8" * 64
    if tb.verify_claim(spliced, 2)["ok"]:
        issues.append("跨 bundle 拼接未被拒（splice 防护失效）")
    stats["bundles"] += 1
    stats["claims"] += len(built["claims"])


def _check_process(family: list, issues: list, stats: dict) -> None:
    for vec in family:
        got = tp.verify_chain(vec["input"]["steps"])
        if got != vec["expected"]:
            issues.append(f"{vec['id']}：prev 链判定与向量不符")
            continue
        stats["process"] += 1


def _check_level(family: list, issues: list, stats: dict) -> None:
    for vec in family:
        case = vec["input"]
        policy_ok = case.get("policy_ok")
        if not isinstance(policy_ok, bool):
            issues.append(f"{vec['id']}：policy_ok 缺失/非布尔（修复指引：向量须显式给出）")
            continue
        got = tv.decide(case["facts"], case["required_level"], policy_ok=policy_ok)
        if got != vec["expected"]:
            issues.append(f"{vec['id']}：等级/退出码判定与向量不符")
            continue
        stats["level"] += 1


def scan(root: str = ".") -> tuple:
    """返回 (issues, stats)；空 issues = check45 通过。"""
    issues: list[str] = []
    stats = {"merkle": 0, "process": 0, "level": 0, "bundles": 0, "claims": 0}
    path = Path(root) / VECTORS_REL
    if not path.is_file():
        return ([f"缺向量集 {VECTORS_REL}（{GUIDE}跑 python scripts/trust_vectors.py --write）"],
                stats)
    try:
        doc = json_doc.load(path, dict, what=VECTORS_REL)
    except ValueError as exc:
        return ([f"{VECTORS_REL} 不可读：{exc}"], stats)
    families = _families(doc.get("vectors") or [])
    for name in REQUIRED_FAMILIES:
        if not families.get(name):
            issues.append(f"向量族缺失：{name}（{GUIDE}重跑 --write）")
    _check_merkle(families.get("merkle", []), issues, stats)
    _check_live_bundle(root, issues, stats)
    _check_process(families.get("process", []), issues, stats)
    _check_level(families.get("level", []), issues, stats)
    if not stats["bundles"] or not stats["claims"]:
        issues.append(f"自建 bundle 未产生可验对象（{GUIDE}检查 FIXED_CLAIMS）")
    stats["families"] = len(families)
    return issues, stats
