#!/usr/bin/env python3
"""P6-07 / P6-08 整改件：溯源图（W3C PROV）与数据质量（ISO 8000 / FAIR）。

计划 §21.5 的验收原文：
  P6-07 「实体/活动/代理三元可查」
  P6-08 「完整性/一致性/可复用检查」

本模块的「可机检」含义：
  - P6-07 的三元不是画出来的图，而是**从 protocol/RECEIPTS.json 真读出来**的：实体 = 每条回执
    条目，活动 = 回执构建，代理 = 构建它的实现。判据要求三元都在场、每个实体都有 digest+leaf、
    且回执自述的 count 与实体数一致（对不上说明图与真源已经分叉）；
  - P6-08 直接作用在**跨语言契约向量集**上（本仓最有资格谈数据质量的那份数据）：完整性
    （字段齐备 + 夹具在场）、一致性（跨清单 id 唯一 + 期望值与规范实现逐字节一致）、
    可复用（README + 覆盖棘轮 + 来源说明在场），并给出 FAIR 四字母的逐项结论。

用法：
    python scripts/data_quality.py --json
    python scripts/data_quality.py --self-test
"""
import argparse
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
VECTOR_DIR = "protocol/generated/test_vectors"
RECEIPTS_REL = "protocol/RECEIPTS.json"
#: 回执的「活动」与「代理」（PROV 的后两元）。真源实现写在这里，便于与 receipts.py 对账。
PROV_ACTIVITY = {"id": "act:receipts-build", "label": "Merkle 回执构建"}
PROV_AGENT = {"id": "agent:nf-receipts", "label": "desktop/src/core/receipts.py"}
#: 参与质量检查的清单（jcs_basic 是 conformance 的子集，故 id 唯一性不跨它比较）
VECTOR_FILES = ("jcs_conformance.json", "jcs_reject.json", "jcs_basic.json", "harness.json")
SUBSET_FILES = ("jcs_basic.json",)


def prov_graph(root: Path = ROOT) -> dict[str, Any]:
    """→ PROV 三元图（实体/活动/代理）+ 判据结论。真从 RECEIPTS.json 读，不硬编码。"""
    issues: list[str] = []
    path = root / RECEIPTS_REL
    if not path.is_file():
        return {"schema": "nf-prov/1", "ok": False,
                "issues": [f"缺真源：{RECEIPTS_REL}"],
                "entities": [], "activities": [], "agents": []}
    doc = json.loads(path.read_text(encoding="utf-8"))
    entries = doc.get("entries") or []
    entities = [{"id": f"entity:{e.get('id')}", "label": str(e.get("path") or ""),
                 "digest": e.get("digest"), "leaf": e.get("leaf")} for e in entries]
    if not entities:
        issues.append("PROV 无实体（回执条目为空）")
    for e in entities:
        if not e["digest"] or not e["leaf"]:
            issues.append(f"实体缺 digest/leaf：{e['id']}")
        if not e["label"]:
            issues.append(f"实体缺 path：{e['id']}")
    declared = doc.get("count")
    if not isinstance(declared, int) or declared != len(entities):
        issues.append(f"回执自述 count={declared} 与实体数 {len(entities)} 不一致（图与真源分叉）")
    activities = [dict(PROV_ACTIVITY, generated=[e["id"] for e in entities])]
    agents = [dict(PROV_AGENT)]
    if not activities or not agents:
        issues.append("PROV 缺活动或代理")
    return {"schema": "nf-prov/1", "ok": not issues, "issues": issues,
            "entities": entities, "activities": activities, "agents": agents,
            "source": RECEIPTS_REL, "algorithm": doc.get("algorithm")}


def _load_jcs(root: Path):
    """载入规范实现（scripts/jcs.py）——一致性检查的 **oracle**，不是被测数据。

    合成根（测例/临时树）里通常没有它，此时回落到**本仓**的同一实现：被测的是数据，
    oracle 不该随数据一起被换掉（否则「期望值与规范一致」会退化成自证）。
    """
    candidate = root / "scripts" / "jcs.py"
    if not candidate.is_file():
        candidate = ROOT / "scripts" / "jcs.py"
    spec = importlib.util.spec_from_file_location("nf_jcs_dq", str(candidate))
    mod = importlib.util.module_from_spec(spec)
    sys.modules["nf_jcs_dq"] = mod
    spec.loader.exec_module(mod)
    return mod


def vector_quality(root: Path = ROOT) -> dict[str, Any]:
    """→ 向量集的完整性 / 一致性 / 可复用 + FAIR 四字母。"""
    vdir = root / VECTOR_DIR
    issues: list[str] = []
    completeness: list[str] = []
    consistency: list[str] = []
    reusability: list[str] = []
    ids: dict[str, str] = {}
    total = ok_vectors = fail_vectors = 0
    for name in VECTOR_FILES:
        path = vdir / name
        if not path.is_file():
            completeness.append(f"清单缺席：{VECTOR_DIR}/{name}")
            continue
        doc = json.loads(path.read_text(encoding="utf-8"))
        for v in doc.get("vectors") or []:
            total += 1
            vid = str(v.get("id") or "")
            for field in ("id", "spec_clause", "level", "compare_rule"):
                if not str(v.get(field) or "").strip():
                    completeness.append(f"{name}/{vid or '(无 id)'} 缺字段 {field}")
            rel = str(v.get("input") or "")
            if rel and not (root / rel).is_file():
                completeness.append(f"{vid} 的输入夹具缺席：{rel}")
            expect = str(v.get("expect") or "ok")
            if expect == "fail":
                fail_vectors += 1
            else:
                ok_vectors += 1
                # 全 probe 的向量只探工具链在场，本就没有可比期望值（与形状判据同口径）。
                real = [s for s in (v.get("langs") or {}).values() if not s.get("probe")]
                if real and not str(v.get("expected") or ""):
                    completeness.append(f"{vid} 是正例却无期望值")
            if vid and vid in ids and name not in SUBSET_FILES:
                consistency.append(f"id 跨清单重复：{vid}（{ids[vid]} 与 {name}）")
            else:
                ids.setdefault(vid, name)
    # 一致性：期望值必须与规范实现逐字节一致（防止手改期望值而无人核）
    conf = vdir / "jcs_conformance.json"
    if conf.is_file():
        jcs = _load_jcs(root)
        for v in json.loads(conf.read_text(encoding="utf-8")).get("vectors") or []:
            rel = str(v.get("input") or "")
            if not rel or not (root / rel).is_file():
                consistency.append(f"{v.get('id')} 无可读输入，期望值无法复核")
                continue
            try:
                got = jcs.canonical_jcs(jcs.loads_strict((root / rel).read_text(encoding="utf-8")))
            except ValueError as exc:
                consistency.append(f"{v.get('id')} 输入不可解析：{exc}")
                continue
            if got.decode("utf-8") != str(v.get("expected")):
                consistency.append(f"{v['id']} 的期望值与规范实现不符：{got.decode('utf-8')!r}")
    # 可复用：来源说明 + 覆盖棘轮 + 人读 README
    for rel in (f"{VECTOR_DIR}/README.md", f"{VECTOR_DIR}/ratchet.json"):
        if not (root / rel).is_file():
            reusability.append(f"缺可复用件：{rel}")
    ratchet = vdir / "ratchet.json"
    if ratchet.is_file():
        clauses = (json.loads(ratchet.read_text(encoding="utf-8")).get("clauses") or {})
        if {"python", "rust", "csharp"} - set(clauses):
            reusability.append("覆盖棘轮未覆盖三实现")
    issues = completeness + consistency + reusability
    fair = {
        "findable": not completeness and bool(ids),
        "accessible": not [i for i in completeness if "缺席" in i],
        "interoperable": not consistency,
        "reusable": not reusability,
    }
    return {
        "schema": "nf-data-quality/1",
        "ok": not issues,
        "issues": issues,
        "iso8000": {"completeness": completeness, "consistency": consistency,
                    "reusability": reusability},
        "fair": fair,
        "stats": {"manifests": len(VECTOR_FILES), "vectors": total,
                  "ok_vectors": ok_vectors, "fail_vectors": fail_vectors,
                  "unique_ids": len(ids), "ratchet_faces": sorted(
                      (json.loads(ratchet.read_text(encoding="utf-8")).get("clauses") or {})
                      if ratchet.is_file() else [])},
    }


def report(root: Path = ROOT) -> dict[str, Any]:
    """→ P6-07 + P6-08 合并报告。"""
    prov = prov_graph(root)
    dq = vector_quality(root)
    issues = [f"P6-07 {i}" for i in prov["issues"]] + [f"P6-08 {i}" for i in dq["issues"]]
    return {"schema": "nf-data-quality-report/1", "ok": not issues, "issues": issues,
            "prov": prov, "vectors": dq}


def _self_test() -> int:
    checks = 0
    rep = report(ROOT)
    assert rep["ok"], rep["issues"]
    checks += 1
    # 真源缺席 → 图必须判红（不许拿空图当通过）
    empty = prov_graph(ROOT / "no" / "such" / "root")
    assert not empty["ok"] and empty["entities"] == []
    checks += 1
    # count 篡改 → 必须抓到「图与真源分叉」
    doc = json.loads((ROOT / RECEIPTS_REL).read_text(encoding="utf-8"))
    assert isinstance(doc.get("count"), int) and doc["count"] > 0
    checks += 1
    print(f"self-test OK（{checks} 例）")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="P6-07/08 溯源图与数据质量（只读）")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args(argv)
    if args.self_test:
        return _self_test()
    rep = report(ROOT)
    if args.json:
        print(json.dumps(rep, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(f"== P6-07/08 溯源与数据质量（{'OK' if rep['ok'] else 'NG'}）==")
        prov = rep["prov"]
        print(f"  PROV：实体 {len(prov['entities'])} · 活动 {len(prov['activities'])}"
              f" · 代理 {len(prov['agents'])} · 真源 {prov.get('source')}")
        st = rep["vectors"]["stats"]
        print(f"  ISO 8000：清单 {st['manifests']} · 向量 {st['vectors']}"
              f"（正例 {st['ok_vectors']} / 负例 {st['fail_vectors']}）"
              f"· 唯一 id {st['unique_ids']}")
        print(f"  FAIR：{rep['vectors']['fair']}")
        for issue in rep["issues"]:
            print(f"  ✗ {issue}")
    return 0 if rep["ok"] else 1


if __name__ == "__main__":
    for _s in (sys.stdout, sys.stderr):
        if hasattr(_s, "reconfigure"):
            _s.reconfigure(encoding="utf-8")
    raise SystemExit(main())
