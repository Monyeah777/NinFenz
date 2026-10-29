"""把方法判据接到真实 NF 产物（P03）上做离线验证。

不调模型：从真实产物确定性抽取章节 -> 拆解树 -> claims -> 因果 -> 反例。
验两件真数据问题：
1. 角色盲区：概览节没有交付物，角色无关判据会误杀；
2. 引用存在性：M99 形状合法但不在真实模块集里，check_ref 判据抓不住。
"""

from __future__ import annotations

import re

from .criteria_lexicon import (
    ARROW,
    CHECK,
    CHECKABLE_FORM,
    CONCRETE,
    CONFIDENCE,
    DISPOSITIONS,
    EVID,
    frac,
)
from .repo_context import repository_root

TEXT = (repository_root() / "docs" / "完整版样本_西幻生存流P03.md").read_text(encoding="utf-8")
SEG = re.compile(r"^##\s*([0-7])\.\s*(.+)$", re.M)
REQ = ["生存", "经济", "战斗", "制造", "势力", "死亡重生", "校园情感", "遗憾"]
ID = re.compile(r"(?:[A-Za-z\u4e00-\u9fff]+:)?M\d+")
REAL_IDS = set(ID.findall(TEXT))


def extract() -> list[dict]:
    ms = list(SEG.finditer(TEXT))
    subs = []
    for i, m in enumerate(ms):
        end = ms[i + 1].start() if i + 1 < len(ms) else len(TEXT)
        body = TEXT[m.end() : end]
        mods = ID.findall(body)
        line = next(
            (
                x.strip()
                for x in body.splitlines()
                if re.search(r"表|清单|路径|文件|状态机|公式|schema", x)
            ),
            "",
        )
        subs.append(
            {
                "id": f"SG{i + 1}",
                "num": m.group(1),
                "title": m.group(2).strip(),
                "deliverable": line,
                "role": "deliverable" if line else "overview",
                "covers": [t for t in REQ if t in (m.group(2) + body)],
                "mod": mods[0] if mods else "",
            }
        )
    return subs


def build(subs: list[dict]):
    claims = {
        "schema": "nf/claims/1",
        "claims": [
            {
                "id": f"C{i}",
                "text": f"{s['title']}：{s['deliverable'] or s['title']}",
                "source": s["id"],
                "source_kind": "subgoal",
            }
            for i, s in enumerate(subs, 1)
        ],
    }
    causal = {
        "schema": "nf/causal-map/1",
        "records": [
            {
                "claim": f"C{i}",
                "mechanism": f"{s['title']} → {s['mod'] or 'M00'} 规则 → 产出",
                "evidence": f"{s['mod'] or 'M00'} §{s['num']}",
                "confounder": f"输入{s['num']}缺失或阈值冲突",
                "counterfactual": f"移除 {s['mod'] or 'M00'} 后 t{40 + i} 应失败",
                "confidence": "medium",
            }
            for i, s in enumerate(subs, 1)
        ],
    }
    attacks = {
        "schema": "nf/counterexample-ledger/1",
        "attacks": [
            {
                "claim": f"C{i}",
                "trigger": f"输入{s['num']}缺失或阈值冲突",
                "check": s["mod"] or "M00",
                "disposition": "survived",
                "reason": "机制在混杂因子下仍成立",
                "evidence": f"{s['mod'] or 'M00'} §{s['num']}",
                "causal_ref": f"C{i}",
            }
            for i, s in enumerate(subs, 1)
        ],
    }
    return claims, causal, attacks


def metrics(subs, claims, causal, attacks, role_aware: bool, req_terms=None) -> dict:
    req = list(req_terms or REQ)
    deliverable = [s for s in subs if (not role_aware or s["role"] == "deliverable")]
    covers = [set(s["covers"]) for s in subs]
    recs, atk = causal["records"], attacks["attacks"]
    real = [a for a in atk if ID.search(a["check"]) and ID.search(a["check"]).group(0) in REAL_IDS]
    return {
        "subgoal_count": len(subs),
        "deliverable_anchor_rate": frac(deliverable, lambda s: bool(s["deliverable"].strip())),
        "requirement_coverage_rate": round(len(set().union(*covers) & set(req)) / len(req), 3)
        if covers
        else 0.0,
        "requirement_assignment_uniqueness": frac(
            req, lambda r: sum(1 for c in covers if r in c) == 1
        ),
        "verifiability_rate": frac(
            deliverable, lambda s: bool(CHECKABLE_FORM.search(s["deliverable"]))
        ),
        "mechanism_coverage": frac(recs, lambda r: bool(ARROW.search(r["mechanism"]))),
        "evidence_anchor_rate": frac(recs, lambda r: bool(EVID.search(r["evidence"]))),
        "confounder_concreteness": frac(recs, lambda r: bool(CONCRETE.search(r["confounder"]))),
        "counterfactual_check_rate": frac(recs, lambda r: bool(CHECK.search(r["counterfactual"]))),
        "confidence_declared": frac(recs, lambda r: r["confidence"] in CONFIDENCE),
        "claim_linkage": frac(recs, lambda r: r["claim"] in {c["id"] for c in claims["claims"]}),
        "attack_coverage": frac(
            {c["id"] for c in claims["claims"]}, lambda c: any(a["claim"] == c for a in atk)
        ),
        "trigger_concreteness": frac(atk, lambda a: bool(CONCRETE.search(a["trigger"]))),
        "check_reference_rate": frac(atk, lambda a: bool(CHECK.search(a["check"]))),
        "disposition_completeness": frac(
            atk, lambda a: a["disposition"] in DISPOSITIONS and bool(a["reason"])
        ),
        "evidence_anchor": frac(atk, lambda a: bool(EVID.search(a["evidence"]))),
        "real_id_validity": round(len(real) / len(atk), 3) if atk else 0.0,
    }


def verdict(name, m, n_subs, n_deliv, n_req, n_rec, n_atk) -> bool:
    def miss(rate, n):
        return round((1 - rate) * n)

    rules = [
        ("deliverable_anchor_rate", miss(m["deliverable_anchor_rate"], n_deliv), 0),
        ("requirement_coverage_rate", miss(m["requirement_coverage_rate"], n_req), 1),
        ("verifiability_rate", miss(m["verifiability_rate"], n_deliv), 0),
        ("mechanism_coverage", miss(m["mechanism_coverage"], n_rec), 0),
        ("evidence_anchor_rate", miss(m["evidence_anchor_rate"], n_rec), 0),
        ("confounder_concreteness", miss(m["confounder_concreteness"], n_rec), 0),
        ("counterfactual_check_rate", miss(m["counterfactual_check_rate"], n_rec), 0),
        ("confidence_declared", miss(m["confidence_declared"], n_rec), 0),
        ("claim_linkage", miss(m["claim_linkage"], n_rec), 0),
        ("attack_coverage", miss(m["attack_coverage"], n_atk), 0),
        ("trigger_concreteness", miss(m["trigger_concreteness"], n_atk), 0),
        ("check_reference_rate", miss(m["check_reference_rate"], n_atk), 0),
        ("disposition_completeness", miss(m["disposition_completeness"], n_atk), 0),
        ("evidence_anchor", miss(m["evidence_anchor"], n_atk), 0),
        ("real_id_validity", miss(m["real_id_validity"], n_atk), 0),
    ]
    fails = [(k, got, allowed) for k, got, allowed in rules if got > allowed]
    print(
        "[{}] {} -> {}".format(
            name, f"FAILS={fails}" if fails else "all-ok", "FAIL" if fails else "PASS"
        )
    )
    return not fails


if __name__ == "__main__":
    base = extract()
    claims, causal, attacks = build(base)
    n_deliv = sum(1 for s in base if s["role"] == "deliverable")
    print("REAL_IDS", len(REAL_IDS), "M99_present", "M99" in REAL_IDS)
    verdict(
        "BASELINE-ROLE-BLIND",
        metrics(base, claims, causal, attacks, False),
        len(base),
        len(base),
        len(REQ),
        len(claims["claims"]),
        len(attacks["attacks"]),
    )
    verdict(
        "BASELINE-ROLE-AWARE",
        metrics(base, claims, causal, attacks, True),
        len(base),
        n_deliv,
        len(REQ),
        len(claims["claims"]),
        len(attacks["attacks"]),
    )

    mut = [dict(s) for s in base]
    for s in mut:
        s["covers"] = [c for c in s["covers"] if c not in ("遗憾", "校园情感")]
    cm, cc, ca = build(mut)
    verdict(
        "MUT-COVERAGE",
        metrics(mut, cm, cc, ca, True),
        len(mut),
        sum(1 for s in mut if s["role"] == "deliverable"),
        len(REQ),
        len(cm["claims"]),
        len(ca["attacks"]),
    )

    mut2 = [dict(s) for s in base]
    for s in mut2:
        if s["role"] == "deliverable":
            s["deliverable"] = ""
            break
    cm2, cc2, ca2 = build(mut2)
    verdict(
        "MUT-DELIVERABLE",
        metrics(mut2, cm2, cc2, ca2, True),
        len(mut2),
        sum(1 for s in mut2 if s["role"] == "deliverable"),
        len(REQ),
        len(cm2["claims"]),
        len(ca2["attacks"]),
    )

    _, _, at3 = build(base)
    at3["attacks"][0]["check"] = "M99"
    verdict(
        "MUT-FABRICATED-ID",
        metrics(base, claims, causal, at3, True),
        len(base),
        n_deliv,
        len(REQ),
        len(claims["claims"]),
        len(at3["attacks"]),
    )

    _, _, at4 = build(base)
    at4["attacks"][0]["evidence"] = ""
    verdict(
        "MUT-NO-EVIDENCE",
        metrics(base, claims, causal, at4, True),
        len(base),
        n_deliv,
        len(REQ),
        len(claims["claims"]),
        len(at4["attacks"]),
    )
