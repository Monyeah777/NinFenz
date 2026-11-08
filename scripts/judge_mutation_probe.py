#!/usr/bin/env python3
"""门禁变异探针 v0：对**两条判据**做最小变异实验，量「杀死率」与「误报率」。

为什么（第 79 轮）：设计里「红不了的门禁等于没有门禁」已由 `gate_probe` 用命名代理量过一遍；
但命名代理只能说明「有没有拒绝型用例」，不能说明「判据对真实变异是否敏感」。
本件做最小闭环：对同一判据喂「合法变体」与「破坏变体」，前者必须不报（无误报），
后者必须报（能杀死）。

标的（都已有真实实现，本件不新写检查逻辑）：
1. `method_pack.vocabulary_mismatches`：词表核对；
2. `bridge.obligation_record_issues`：回灌记录与消息的对应核对。

口径：kill_rate = 被杀死的变异体 / 变异体总数；
false_positive_rate = 被误报的合法变体 / 合法变体总数。
只报数，不设阈值（阈值应由负责人定，agent 不自封）。

用法：python scripts/judge_mutation_probe.py [--write] [--json]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "desktop" / "src"))
OUT_REL = "results/ccos/judge_mutation.json"
SCHEMA = "nf-judge-mutation/1"


def _core():
    """按需导入（模块级只留纯逻辑，避开 E402）。"""
    from core import method_pack as mp
    from core.cognition_workspace import bridge as br

    return mp, br


def vocab_cases() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """→ (合法变体, 破坏变体)；每个 case 是 {name, packs, registry}。"""
    mp, _br = _core()
    packs = [mp.load_pack(str(ROOT), pid) for pid in
             [p["id"] for p in mp.list_packs(str(ROOT))]]
    registry = json.loads((ROOT / "protocol" / "criteria" / "registry.json")
                          .read_text(encoding="utf-8"))
    legal = [
        {"name": "原样", "packs": packs, "registry": registry},
        {"name": "词表顺序打乱", "packs": packs,
         "registry": dict(registry, claim_kinds=list(reversed(registry["claim_kinds"])))},
        # 工件不变性（台账 §7.2）：包顺序变了，判定不得变
        {"name": "包顺序打乱", "packs": list(reversed(packs)),
         "registry": registry},
    ]
    broken = [
        {"name": "删一个词", "packs": packs,
         "registry": dict(registry, claim_kinds=list(registry["claim_kinds"])[1:])},
        {"name": "加一个死词", "packs": packs,
         "registry": dict(registry, claim_kinds=list(registry["claim_kinds"]) + ["ghost"])},
        {"name": "包侧把词改错一个字母", "packs": [dict(packs[0], evidence_standards=[
            dict(packs[0]["evidence_standards"][0],
                 claim_kind=str(packs[0]["evidence_standards"][0]["claim_kind"]) + "x")])],
         "registry": registry},
    ]
    return legal, broken


def obligation_cases() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """→ (合法变体, 破坏变体)；用真实桥函数造记录，不手搓 digest。"""
    _mp, br = _core()
    from core.cognition_workspace import session as se

    bundle = se.begin("变异探针")
    cc = {"verdict": "invalid", "subject": "s", "detail": "d"}
    claim = {"schema": "nf-cog-claim/1", "claim": "x", "digest": "b" * 64,
             "obligations": [], "criteria": []}
    ob = br.obligation(br.commit(bundle, claim, cc), cc, failed=["A", "B"])
    rec = (br.apply_obligation(bundle, ob).get("control") or {})["records"][-1]
    legal = [{"name": "原样", "record": rec, "ob": ob},
             {"name": "重新计算证人", "record": dict(rec), "ob": ob}]
    broken = [{"name": "改来源标记", "record": dict(rec, trigger="manual"), "ob": ob},
              {"name": "失败集换序",
               "record": dict(rec, witness={"anomaly": rec["witness"]["anomaly"],
                                            "evidence": list(reversed(
                                                rec["witness"]["evidence"]))}),
               "ob": ob},
              {"name": "改证人 digest",
               "record": dict(rec, witness_digest="0" * 64), "ob": ob}]
    return legal, broken


def witness_cases() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """→ (合法变体, 破坏变体)；标的 = `moves._witness_shape_issues`（反例证人形状判据）。"""
    _mp, _br = _core()

    legal = [{"name": "标准证人", "witness": {"file": "results/ccos/x.json", "case": "c-01"}},
             {"name": "多余键", "witness": {"file": "f.json", "case": "c", "note": "额外"}}]
    broken = [{"name": "不是对象", "witness": "f.json"},
              {"name": "缺 case", "witness": {"file": "f.json"}},
              {"name": "case 空串", "witness": {"file": "f.json", "case": "  "}}]
    return legal, broken


def authority_cases() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """→ (合法变体, 破坏变体)；标的 = `control.authority_issues`（授权层）。"""
    _mp, _br = _core()

    allowed = {"tester"}
    legal = [{"name": "终态带授权", "record": {"op": "stop", "authority": "tester"},
              "allowed": allowed},
             {"name": "非终态无授权", "record": {"op": "observe", "authority": ""},
              "allowed": allowed}]
    broken = [{"name": "终态缺授权", "record": {"op": "stop", "authority": ""},
               "allowed": allowed},
              {"name": "授权方不在词表", "record": {"op": "stop", "authority": "ghost"},
               "allowed": allowed},
              {"name": "记录不是对象", "record": "stop", "allowed": allowed}]
    return legal, broken


def resource_cases() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """→ (合法变体, 破坏变体)；标的 = `bridge.resource_accounting_issues`（资源层）。"""
    _mp, br = _core()

    legal = [{"name": "两本账齐全", "commitment": {"cost": {"cog_steps": 3, "cc_cost_ms": 7}}},
             {"name": "缺值为 None", "commitment": {"cost": {"cog_steps": None,
                                                    "cc_cost_ms": None}}}]
    broken = [{"name": "缺 cost", "commitment": {}},
              {"name": "混记 total",
               "commitment": {"cost": {"cog_steps": 1, "cc_cost_ms": 2, "total": 3}}},
              {"name": "负数", "commitment": {"cost": {"cog_steps": -1,
                                               "cc_cost_ms": 7}}}]
    return legal, broken


def build() -> dict[str, Any]:
    mp, br = _core()
    judges = []
    vlegal, vbroken = vocab_cases()
    vl_hits = [c["name"] for c in vlegal
               if mp.vocabulary_mismatches(c["packs"], c["registry"]) != {"unknown": [],
                                                                          "unused": []}]
    vb_hits = [c["name"] for c in vbroken
               if mp.vocabulary_mismatches(c["packs"], c["registry"]) != {"unknown": [],
                                                                          "unused": []}]
    judges.append({"judge": "vocabulary_mismatches",
                   "legal": len(vlegal), "legal_flagged": vl_hits,
                   "broken": len(vbroken), "broken_caught": vb_hits})
    olegal, obroken = obligation_cases()
    ol_hits = [c["name"] for c in olegal
               if br.obligation_record_issues(c["record"], c["ob"])]
    ob_hits = [c["name"] for c in obroken
               if br.obligation_record_issues(c["record"], c["ob"])]
    judges.append({"judge": "obligation_record_issues",
                   "legal": len(olegal), "legal_flagged": ol_hits,
                   "broken": len(obroken), "broken_caught": ob_hits})
    wlegal, wbroken = witness_cases()
    from core.cognition_workspace import moves as mv
    wl_hits = [c["name"] for c in wlegal if mv._witness_shape_issues(c["witness"])]
    wb_hits = [c["name"] for c in wbroken if mv._witness_shape_issues(c["witness"])]
    judges.append({"judge": "_witness_shape_issues",
                   "legal": len(wlegal), "legal_flagged": wl_hits,
                   "broken": len(wbroken), "broken_caught": wb_hits})
    from core.cognition_workspace import control as ct
    alegal, abroken = authority_cases()
    al_hits = [c["name"] for c in alegal
               if ct.authority_issues(c["record"], c["allowed"])]
    ab_hits = [c["name"] for c in abroken
               if ct.authority_issues(c["record"], c["allowed"])]
    judges.append({"judge": "authority_issues",
                   "legal": len(alegal), "legal_flagged": al_hits,
                   "broken": len(abroken), "broken_caught": ab_hits})
    rlegal, rbroken = resource_cases()
    rl_hits = [c["name"] for c in rlegal
               if br.resource_accounting_issues(c["commitment"])]
    rb_hits = [c["name"] for c in rbroken
               if br.resource_accounting_issues(c["commitment"])]
    judges.append({"judge": "resource_accounting_issues",
                   "legal": len(rlegal), "legal_flagged": rl_hits,
                   "broken": len(rbroken), "broken_caught": rb_hits})
    legal_total = sum(j["legal"] for j in judges)
    broken_total = sum(j["broken"] for j in judges)
    legal_bad = sum(len(j["legal_flagged"]) for j in judges)
    broken_bad = sum(len(j["broken_caught"]) for j in judges)
    return {"schema": SCHEMA, "judges": len(judges),
            "kill_rate": round(broken_bad / broken_total, 6) if broken_total else 0.0,
            "false_positive_rate": round(legal_bad / legal_total, 6) if legal_total else 0.0,
            "mutants": broken_total, "legal_variants": legal_total,
            "detail": judges,
            "note": "只报数不设阈值；阈值与放行由负责人决定"}


def render(doc: dict[str, Any]) -> str:
    return json.dumps(doc, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="judge_mutation_probe",
                                 description="门禁变异探针：对两条判据量杀死率与误报率（只报数）")
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--check", action="store_true", help="与已提交结果比对（防陈旧）")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    try:
        doc = build()
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    if args.write:
        dest = ROOT / OUT_REL
        dest.parent.mkdir(parents=True, exist_ok=True)
        from core import atomic_write  # 写盘只在 --write 分支需要

        atomic_write.write_text(dest, render(doc))
        print("OK 已写入 " + OUT_REL + "（判据 " + str(doc["judges"]) + " · 杀死率 "
              + str(doc["kill_rate"]) + " · 误报率 " + str(doc["false_positive_rate"]) + "）")
        return 0
    if args.check:
        dest = ROOT / OUT_REL
        if not dest.is_file():
            print("缺 " + OUT_REL + "（先跑 --write）", file=sys.stderr)
            return 1
        if dest.read_text(encoding="utf-8") != render(doc):
            print("结果已陈旧（判据/变异体变了）——重跑 --write", file=sys.stderr)
            return 1
        print("OK 结果与重算一致")
        return 0
    if args.json:
        print(render(doc), end="")
        return 0
    print("判据 " + str(doc["judges"]) + " · 变异体 " + str(doc["mutants"])
          + " · 杀死率 " + str(doc["kill_rate"]))
    print("合法变体 " + str(doc["legal_variants"]) + " · 误报率 "
          + str(doc["false_positive_rate"]))
    for row in doc["detail"]:
        print("  " + row["judge"] + "：杀 " + str(len(row["broken_caught"])) + "/"
              + str(row["broken"]) + " · 误报 " + str(len(row["legal_flagged"])) + "/"
              + str(row["legal"]))
    return 0


if __name__ == "__main__":
    for _stream in (sys.stdout, sys.stderr):
        if hasattr(_stream, "reconfigure"):
            _stream.reconfigure(encoding="utf-8")
    raise SystemExit(main())
