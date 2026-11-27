"""core.drill_fidelity 私有实现分片 2/2（对外只经 core.drill_fidelity 门面导入）： 等"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from core import atomic_write

from ._part1 import (
    EXEC_GLOB,
    POSITIVE_CONTROLS_REL,
    REAL_CORPUS_REL,
    REPORT_REL,
    ROUND_GLOB,
    SCHEMA,
    _corpus_forward,
    _corpus_live_hits,
    _corpus_meta_problems,
    _exec_sets,
    _real_corpus_block,
    _round_samples,
    positive_controls,
)


def _corpus_reverse(keyed: dict[tuple[int, str], dict[str, Any]], live_keys: set
                    ) -> tuple[int, list[dict[str, Any]], list[str]]:
    """反向：裁定表里已不命中的条目必须改成 live=false（FP 记为已修，TP 记为漏报回归）。"""
    problems: list[str] = []
    resolved = 0
    detail: list[dict[str, Any]] = []
    for (line_no, rule), entry in sorted(keyed.items()):
        if (line_no, rule) in live_keys:
            continue
        verdict = str(entry.get("verdict") or "").upper()
        if entry.get("live") is True:
            problems.append(f"裁定表声称仍命中但实测已消失：第 {line_no} 行 {rule}"
                            f"（修复指引：若系修复所致，把该条 live 置 false）")
        elif verdict == "TP":
            problems.append(f"TP 命中消失（漏报回归）：第 {line_no} 行 {rule}"
                            f"（修复指引：不得为了指标放宽/删除判据——TP 消失必须解释并改裁定）")
        else:
            resolved += 1
            detail.append({"line": line_no, "rule": rule, "verdict": verdict,
                           "basis": str(entry.get("basis") or ""),
                           "live_before": bool(entry.get("live_before")), "live": False})
    return resolved, detail, problems


def _corpus_adjudicate(live: list[tuple[int, str]], keyed: dict[tuple[int, str], dict[str, Any]]
                       ) -> tuple[int, int, int, list[dict[str, Any]], list[str]]:
    """现存命中逐条裁定 + 裁定表反向核对 → (tp, fp, fp_resolved, detail, problems)。

    三条反向判据缺一不可，否则本判据会退化成「自报绿」：
    ① 现存命中没裁定 ⇒ FAIL；② 裁定为 TP 但已不命中 ⇒ 漏报回归；③ 裁定声称仍命中而实测消失 ⇒ FAIL。
    """
    tp, fp, detail, problems = _corpus_forward(live, keyed)
    resolved, resolved_detail, reverse_problems = _corpus_reverse(keyed, set(live))
    return tp, fp, resolved, detail + resolved_detail, problems + reverse_problems


def _corpus_nonblank(text: str) -> list[tuple[int, str]]:
    return [(i + 1, line) for i, line in enumerate(text.splitlines()) if line.strip()]


def _corpus_entries(block: dict[str, Any]) -> list[dict[str, Any]]:
    return [e for e in (block.get("adjudications") or []) if isinstance(e, dict)]


def _corpus_keyed(entries: list[dict[str, Any]]) -> dict[tuple[int, str], dict[str, Any]]:
    return {(int(e.get("line") or 0), str(e.get("rule") or "")): e for e in entries}


def _corpus_rules(live: list[tuple[int, str]]) -> dict[str, int]:
    rules: dict[str, int] = {}
    for _n, rule in live:
        rules[rule] = rules.get(rule, 0) + 1
    return rules


def real_corpus(root: str = ".") -> dict[str, Any]:
    """真实语料逐命中裁定（活判据）→ 度量块；找不到语料/裁定表时返回 `{}`。

    造这条判据的原因：74/74 drill 全是自造样本（0 份真实转录），保真度 100% 属自指绿。
    这里把唯一真实战例逐非空行回放 `execution_drill`，要求**每条命中**都有 TP/FP 与依据；
    裁定表写在待裁定回合样本的 `real_corpus.adjudications` 里（`live_before`/`live` 记录
    修复前后是否仍命中），命中集与裁定表不一致即 FAIL。
    """
    from core import round_drill as rd

    r = Path(root)
    doc_p = r / REAL_CORPUS_REL
    if not doc_p.is_file():
        return {}
    sample, block, allowed = _real_corpus_block(r)
    if not block:
        return {}
    text = doc_p.read_text(encoding="utf-8")
    sha = hashlib.sha256(doc_p.read_bytes()).hexdigest()
    nonblank = _corpus_nonblank(text)
    problems, real_ids = _corpus_meta_problems(block, text, sha, nonblank, allowed)
    entries = _corpus_entries(block)
    keyed = _corpus_keyed(entries)
    live = _corpus_live_hits(nonblank, real_ids)
    tp, fp, resolved, detail, verdict_problems = _corpus_adjudicate(live, keyed)
    problems += verdict_problems
    raw_turns = int(rd.scan(text, [])[1].get("turns") or 0)
    rules = _corpus_rules(live)
    return {"source": REAL_CORPUS_REL,
            "sample": sample,
            "sha256": sha,
            "sha256_matched": not any("sha256" in p for p in problems),
            "nonblank_lines": len(nonblank),
            "raw_round_turns": raw_turns,
            "raw_parse_rate": 1.0 if raw_turns else 0.0,
            "hits_before": len(entries),
            "hits": len(live),
            "tp": tp,
            "fp": fp,
            "fp_resolved": resolved,
            "rules": rules,
            "problems": problems,
            "adjudications": detail}


def _exec_cases(ex: list[dict[str, Any]]) -> tuple[int, int]:
    return sum(s["cases"] for s in ex), sum(s["passed"] for s in ex)


def _round_counts(rnd: list[dict[str, Any]]) -> tuple[int, int, int]:
    adjudicated = [s for s in rnd if not s.get("pending")]
    rnd_total = len(adjudicated)
    rnd_pass = sum(1 for s in adjudicated if s.get("matched"))
    parsed = sum(1 for s in rnd if s.get("parse_ok"))
    return rnd_total, rnd_pass, parsed


def _round_hits(rnd: list[dict[str, Any]]) -> list[str]:
    return [h for s in rnd if s.get("pending") for h in (s.get("hits") or [])]


def _round_adj(rnd: list[dict[str, Any]]) -> dict[str, str]:
    return {a["hit"]: a["verdict"] for s in rnd if s.get("pending")
            for a in s.get("adjudication") or []}


def _round_hit_counts(rnd: list[dict[str, Any]]) -> tuple[list[str], int, int]:
    round_hits = _round_hits(rnd)
    round_adj = _round_adj(rnd)
    round_tp = sum(1 for h in round_hits if round_adj.get(h) == "TP")
    round_fp = sum(1 for h in round_hits if round_adj.get(h) == "FP")
    return round_hits, round_tp, round_fp


def _exec_block(ex: list[dict[str, Any]], ex_cases: int, ex_pass: int) -> dict[str, Any]:
    return {"sets": ex, "cases": ex_cases, "passed": ex_pass,
            "fidelity": round(ex_pass / ex_cases, 4) if ex_cases else 0.0}


def _round_block(rnd: list[dict[str, Any]], counts: tuple[int, int, int],
                 hits: tuple[list[str], int, int]) -> dict[str, Any]:
    rnd_total, rnd_pass, parsed = counts
    round_hits, round_tp, round_fp = hits
    return {"samples": rnd, "total": rnd_total, "matched": rnd_pass,
            "pending": len(rnd) - rnd_total,
            "pending_samples": len(rnd) - rnd_total,
            "parse_ok": parsed, "parse_total": len(rnd),
            "parse_rate": round(parsed / len(rnd), 4) if rnd else 0.0,
            "hits": round_hits, "tp": round_tp, "fp": round_fp,
            "fidelity": round(rnd_pass / rnd_total, 4) if rnd_total else 0.0}


def _metrics_block(rnd: list[dict[str, Any]], parsed: int, corpus: dict[str, Any],
                   controls: dict[str, Any],
                   hits: tuple[list[str], int, int]) -> dict[str, Any]:
    round_hits, round_tp, round_fp = hits
    return {"parse_rate": round(parsed / len(rnd), 4) if rnd else 0.0,
            "parse_ok": parsed, "parse_total": len(rnd),
            "raw_parse_rate": corpus.get("raw_parse_rate", 0.0),
            "hits": corpus.get("hits", 0),
            "tp": corpus.get("tp", 0),
            "fp": corpus.get("fp", 0),
            "hits_before": corpus.get("hits_before", 0),
            "fp_resolved": corpus.get("fp_resolved", 0),
            "round_hits": len(round_hits),
            "round_tp": round_tp, "round_fp": round_fp,
            "positive_controls_passed": controls.get("passed", 0),
            "positive_controls_total": controls.get("total", 0)}


def measure(root: str = ".") -> dict[str, Any]:
    """→ 保真度度量（执行演练 + 回合级回放 + 真实语料裁定 + 总口径）。"""
    r = Path(root)
    ex = _exec_sets(r)
    rnd = _round_samples(r)
    ex_cases, ex_pass = _exec_cases(ex)
    rnd_total, rnd_pass, parsed = _round_counts(rnd)
    corpus = real_corpus(str(r))
    controls = positive_controls(str(r))
    #: 待裁定样本的规则命中（逐条裁定）——与真实语料命中分开计，口径不混。
    hits = _round_hit_counts(rnd)
    total, passed = ex_cases + rnd_total, ex_pass + rnd_pass
    return {"schema": SCHEMA,
            "execution": _exec_block(ex, ex_cases, ex_pass),
            "rounds": _round_block(rnd, (rnd_total, rnd_pass, parsed), hits),
            "real_corpus": corpus,
            "positive_controls": controls,
            "overall": {"cases": total, "passed": passed,
                        "fidelity": round(passed / total, 4) if total else 0.0},
            "metrics": _metrics_block(rnd, parsed, corpus, controls, hits)}


def _exec_issues(sets: list[dict[str, Any]]) -> list[str]:
    """执行演练集的判据问题（坏 JSON / 保真度不足）。"""
    issues: list[str] = []
    for s in sets:
        if s.get("error"):
            issues.append("{} {}".format(s["set"], s["error"]))
        elif s["passed"] != s["cases"]:
            issues.append(f"执行演练保真度不足：{s['set']} {s['passed']}/{s['cases']}"
                          f"（修复指引：先修样本集自身或捕获逻辑，演练集不达标不得入库）")
    return issues


def _replay_issues(s: dict[str, Any]) -> list[str]:
    if s.get("matched"):
        return []
    return ["回合级回放未复现声明：{} 声明={} 实测={}（{}）（修复指引：修样本或"
            "回合断言——回放须可复现声明结论）"
            .format(s["sample"], s.get("declared"), s.get("live"),
                    str(s.get("first_issue"))[:60])]


def _pending_issues(s: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    # 待裁定样本：parse 是裁定前提；命中必须逐条裁定，不许留「疑似」。
    if not s.get("parse_ok"):
        issues.append("待裁定回合样本未解析出回合标记：{}（parse 失败 ⇒ 裁定前提不成立；"
                      "修复指引：转录须含「回合 N：」/「第 N 回合」）".format(s["sample"]))
    declared = {a["hit"]: a["verdict"] for a in s.get("adjudication") or []}
    for hit in s.get("hits") or []:
        if declared.get(hit) not in ("TP", "FP"):
            issues.append("待裁定样本 {} 的规则命中未裁定：{}（修复指引：在样本 adjudication 里"
                          "逐条给 TP/FP + 依据）".format(s["sample"], hit))
    return issues


def _sample_issues(s: dict[str, Any]) -> list[str]:
    if s.get("error"):
        return ["{} {}".format(s["sample"], s["error"])]
    if not s.get("pending"):
        return _replay_issues(s)
    return _pending_issues(s)


def _round_issues(samples: list[dict[str, Any]]) -> list[str]:
    """回合级样本的判据问题（声明未复现 / 待裁定样本 parse 或裁定缺位）。"""
    issues: list[str] = []
    for s in samples:
        issues += _sample_issues(s)
    return issues


def scan(root: str = ".") -> tuple[list[str], list[str], dict[str, Any]]:
    """→ (issues, warns, stats)：任一例不达标 / 无载体 / 命中未裁定 = FAIL。"""
    m = measure(root)
    warns: list[str] = []
    issues: list[str] = []
    if m["execution"]["cases"] == 0:
        issues.append("找不到执行演练用例"
                      f"（修复指引：{EXEC_GLOB} 下须有 p*_drill_cases.json）")
    if m["rounds"]["parse_total"] == 0:
        issues.append("找不到回合级回放样本"
                      f"（修复指引：{ROUND_GLOB} 下须有样本，含 transcript/allowed/verdict）")
    issues += _exec_issues(m["execution"]["sets"])
    issues += _round_issues(m["rounds"]["samples"])
    for p in m["real_corpus"].get("problems") or []:
        issues.append(f"真实语料裁定：{p}（修复指引：按变更重做 real_corpus.adjudications，"
                      "不得放宽判据）")
    controls = m.get("positive_controls") or {}
    if controls:
        for p in controls.get("problems") or []:
            issues.append(f"正例对照失效：{p}（修复指引：注入必须被捕获——判据不得被改弱到"
                          "什么都不报）")
        if not controls.get("total"):
            issues.append("正例对照无载体（修复指引：新增注入变体并重生成 "
                          f"{POSITIVE_CONTROLS_REL}）")
    stats = m["overall"]
    stats.update({"exec_sets": len(m["execution"]["sets"]),
                  "round_samples": m["rounds"]["parse_total"]})
    return issues, warns, stats


def write(root: str = ".") -> tuple[list[str], dict[str, Any]]:
    """把度量结果落盘（供机器消费）→ (issues, doc)。"""
    m = measure(root)
    p = Path(root) / REPORT_REL
    atomic_write.write_text(p, json.dumps(m, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    issues, _w, _s = scan(root)
    return issues, m
