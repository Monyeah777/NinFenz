"""演练保真度**量化**（动态可执行面 · 顶层化：drill 全绿 / 回合级回放 / 保真度量化）。

为什么需要：既有两套演练此前只有「逐例 PASS/FAIL」的文本结论——**没有一个数**。于是
「保真度」无法比较、无法回归、无法作为发布判据（顶层化实测：全仓 `保真` 一词只出现在
`import_adapter` 的「高保真重建」，与演练无关）。

本模块把演练结果压成**保真度数字**并给判据：

- **执行演练保真度**：逐个用例集跑 `execution_drill.run_case`，判「捕获无漏报
  （expect_captured ⊆ hits）+ guard 无误报（无期望命中时不得有命中）」，保真度 = 通过例数 / 总例数。
- **回合级回放保真度**：对 `fixtures/execution/rounds/*.json` 逐个回放，判实测 verdict
  是否复现样本声明（`good → conformant` / `bad → non-conformant`），保真度 = 复现数 / 样本数。
- **真实语料命中裁定**（2026-10-20 加）：把唯一真实战例 `docs/完整版样本_西幻生存流P03.md`
  逐非空行回放 `execution_drill`，命中必须逐条给出 TP/FP 裁定与依据（裁定表写在待裁定回合样本的
  `real_corpus.adjudications` 里）；**命中未裁定 / TP 命中消失 /
  裁定声称现存而实测已消失** 都判 FAIL。
  这条判据的动机：74/74 的 drill 全是自造样本（写样本的人与写实现的人互证），
  保真度 100% 是**自指绿**；
  真实语料上的命中精度必须单列成数（`metrics.hits / tp / fp`）。
- **待裁定样本**（`verdict/label_status = pending`）：不参与「声明 vs 实测」分子分母
  （未裁定就无声明可复现），
  但**必须解析出回合标记**（parse 失败 ⇒ 裁定前提不成立，判 FAIL），其命中同样须逐条裁定。
- **判据**：任一例不达标 → FAIL（保真度必须 100%）；**找不到用例/样本 → FAIL**（标准不得无载体）。

纪律：纯标准库；只读（唯 `write()` 落盘度量结果供机器消费）；错误消息带修复指引。
"""
from __future__ import annotations

import hashlib
import json
import re

from core import atomic_write
from pathlib import Path
from typing import Any
from core import json_doc

EXEC_GLOB = "desktop/tests/fixtures/execution/p*_drill_cases.json"
ROUND_GLOB = "desktop/tests/fixtures/execution/rounds/*.json"
REPORT_REL = "protocol/drill_fidelity.json"
#: 唯一真实战例（仓内非自造语料）；真实语料裁定表从待裁定回合样本的 `real_corpus` 块读取。
REAL_CORPUS_REL = "docs/完整版样本_西幻生存流P03.md"
#: 注册表投影行（`| M00 | 数据结构 | …`）——用于核对裁定表 `real_ids` 没被裁剪。
REGISTRY_ROW = re.compile(r"^\|\s*((?:[\u4e00-\u9fff]+:)?M\d{2,3})\s*\|")
SCHEMA = "nf-drill-fidelity/1"
#: 回合级样本的 verdict 词表 → 判据口径（样本侧写 good/bad，drill 侧吐 conformant/non-conformant）
VERDICT_MAP = {"good": "conformant", "conformant": "conformant",
               "bad": "non-conformant", "non-conformant": "non-conformant"}
#: 待裁定标记（2026-10-20）：`verdict` 或 `label_status` 为它 ⇒ 不参与声明复现，只过 parse/裁定门。
PENDING = "pending"


def _exec_sets(root: Path) -> list[dict[str, Any]]:
    from core import execution_drill as ed

    out: list[dict[str, Any]] = []
    for f in sorted(root.glob(EXEC_GLOB)):
        try:
            data = json_doc.load(f, dict, what=f.name)
        except ValueError as exc:
            out.append({"set": f.name, "cases": 0, "passed": 0,
                        "error": f"JSON 不可解析：{exc}"})
            continue
        real, sem, src = data.get("real_ids") or [], data.get("semantics") or {}, data.get("source_"
            "text", "")
        other, keys = data.get("other_ids") or [], data.get("asset_keys") or []
        lexicon = data.get("lexicon") or {}
        n = ok = 0
        for case in data.get("cases", []):
            hits = ed.run_case(case, real, sem, src, other, keys, lexicon)
            expect = set(case.get("expect_captured") or [])
            good = (not expect and not hits) or expect <= set(hits)
            n += 1
            ok += 1 if good else 0
        out.append({"set": f.name, "cases": n, "passed": ok})
    return out


def _round_adjudications(doc: dict[str, Any], hits: list[str]) -> list[dict[str, Any]]:
    """待裁定样本的逐条裁定表（`adjudication`: hit / verdict=TP|FP / basis）——只留命中过的。"""
    out: list[dict[str, Any]] = []
    for item in doc.get("adjudication") or []:
        if not isinstance(item, dict):
            continue
        out.append({"hit": str(item.get("hit") or ""),
                    "verdict": str(item.get("verdict") or "").upper(),
                    "basis": str(item.get("basis") or "")})
    return out


def _round_sample(f: Path) -> dict[str, Any]:
    from core import round_drill as rd

    name = f.name
    try:
        d = json_doc.load(f, dict, what=name)
    except ValueError as exc:
        return {"sample": name, "declared": "?", "live": "error", "matched": False,
                "label_status": "adjudicated", "pending": False, "turns": 0, "parse_ok": False,
                "hits": [], "first_issue": "", "adjudication": [],
                "error": f"JSON 不可解析：{exc}"}
    transcript = str(d.get("transcript") or "")
    issues, stats = rd.scan(transcript, list(d.get("allowed") or []))
    live = "non-conformant" if issues else "conformant"
    raw_verdict = str(d.get("verdict") or "")
    pending = (str(d.get("label_status") or "").lower() == PENDING
               or raw_verdict.lower() == PENDING)
    turns = int(stats.get("turns") or 0)
    declared = PENDING if pending else VERDICT_MAP.get(raw_verdict.lower(), raw_verdict)
    return {"sample": name,
            "declared": declared,
            "live": live,
            "matched": (None if pending else declared == live),
            "label_status": PENDING if pending else "adjudicated",
            "pending": pending,
            "turns": turns,
            "parse_ok": turns > 0,
            "hits": list(issues),
            "first_issue": (issues[0] if issues else ""),
            "adjudication": _round_adjudications(d, issues)}


def _round_samples(root: Path) -> list[dict[str, Any]]:
    return [_round_sample(f) for f in sorted(root.glob(ROUND_GLOB))]


def _registry_ids(text: str) -> list[str]:
    """从真实语料的注册表投影表行抽出模块号集（去重保序）。"""
    out: list[str] = []
    for line in text.splitlines():
        m = REGISTRY_ROW.match(line)
        if m and m.group(1) not in out:
            out.append(m.group(1))
    return out


def _real_corpus_block(root: Path) -> tuple[str, dict[str, Any], list[str]]:
    """找带 `real_corpus` 裁定的回合样本 → (样本名, 裁定块, 该样本 allowed)。"""
    for f in sorted(root.glob(ROUND_GLOB)):
        try:
            d = json_doc.load(f, dict, what=f.name)
        except ValueError:
            # 为何可以吞：单个回合样本解析失败不该让整份保真度报告崩掉——该样本会在
            # 上层按「缺件/不可解析」计数并以 issues 暴露，故此处只跳过本条、保住全量基线。
            continue
        block = d.get("real_corpus")
        if isinstance(block, dict):
            return f.name, block, [str(x) for x in (d.get("allowed") or [])]
    return "", {}, []


def _corpus_meta_problems(block: dict[str, Any], text: str, sha: str,
                          nonblank: list[tuple[int, str]],
                          allowed: list[str]) -> tuple[list[str], list[str]]:
    """裁定表元数据对账（防语料换了/允许集被裁剪后仍报旧数）→ (problems, real_ids)。"""
    problems: list[str] = []
    if block.get("sha256") and block["sha256"] != sha:
        problems.append(f"真实语料已变（sha256 不匹配）"
                        f"——逐条裁定表须重做：{REAL_CORPUS_REL}")
    if block.get("nonblank_lines") not in (None, len(nonblank)):
        problems.append(f"真实语料非空行数变了（裁定表记 {block.get('nonblank_lines')!r}，"
                        f"实测 {len(nonblank)}）——裁定表须重做")
    real_ids = [str(x) for x in (block.get("real_ids") or [])]
    if allowed and set(real_ids) != set(allowed):
        problems.append("裁定表 real_ids 与所属样本 allowed 不一致"
                        "（修复指引：两处须同为该管线在册集）")
    registry = _registry_ids(text)
    if registry and set(real_ids) != set(registry):
        problems.append(f"裁定表 real_ids 与语料注册表投影不一致（防裁剪允许集）"
                        f"——投影 {len(registry)} 件，裁定表 {len(real_ids)} 件")
    return problems, real_ids


def _corpus_live_hits(nonblank: list[tuple[int, str]], real_ids: list[str]
                      ) -> list[tuple[int, str]]:
    """逐非空行回放 `execution_drill` → 现存命中 `[(行号, 规则名)]`。"""
    from core import execution_drill as ed

    live: list[tuple[int, str]] = []
    for line_no, line in nonblank:
        for rule in ed.run_case({"output": line}, real_ids, {}):
            live.append((line_no, rule))
    return live


def _corpus_forward(live: list[tuple[int, str]], keyed: dict[tuple[int, str], dict[str, Any]]
                    ) -> tuple[int, int, list[dict[str, Any]], list[str]]:
    """正向：现存命中逐条裁定 → (tp, fp, detail, problems)。"""
    problems: list[str] = []
    tp = fp = 0
    detail: list[dict[str, Any]] = []
    for line_no, rule in live:
        entry = keyed.get((line_no, rule))
        if entry is None:
            problems.append(f"真实语料命中未裁定：第 {line_no} 行 {rule}（裁定表缺条目）")
            continue
        verdict = str(entry.get("verdict") or "").upper()
        basis = str(entry.get("basis") or "").strip()
        if verdict not in ("TP", "FP"):
            problems.append(f"裁定 verdict 必须 TP/FP：第 {line_no} 行 {rule} 实为 {verdict!r}")
            continue
        if not basis:
            problems.append(f"裁定缺依据（basis）：第 {line_no} 行 {rule}")
        if verdict == "TP":
            tp += 1
        else:
            fp += 1
        detail.append({"line": line_no, "rule": rule, "verdict": verdict, "basis": basis,
                       "live_before": bool(entry.get("live_before")), "live": True})
    return tp, fp, detail, problems


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
    nonblank = [(i + 1, line) for i, line in enumerate(text.splitlines()) if line.strip()]
    problems, real_ids = _corpus_meta_problems(block, text, sha, nonblank, allowed)
    entries = [e for e in (block.get("adjudications") or []) if isinstance(e, dict)]
    keyed = {(int(e.get("line") or 0), str(e.get("rule") or "")): e for e in entries}
    live = _corpus_live_hits(nonblank, real_ids)
    tp, fp, resolved, detail, verdict_problems = _corpus_adjudicate(live, keyed)
    problems += verdict_problems
    raw_turns = int(rd.scan(text, [])[1].get("turns") or 0)
    rules: dict[str, int] = {}
    for _n, rule in live:
        rules[rule] = rules.get(rule, 0) + 1
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


def measure(root: str = ".") -> dict[str, Any]:
    """→ 保真度度量（执行演练 + 回合级回放 + 真实语料裁定 + 总口径）。"""
    r = Path(root)
    ex = _exec_sets(r)
    rnd = _round_samples(r)
    ex_cases = sum(s["cases"] for s in ex)
    ex_pass = sum(s["passed"] for s in ex)
    adjudicated = [s for s in rnd if not s.get("pending")]
    rnd_total = len(adjudicated)
    rnd_pass = sum(1 for s in adjudicated if s.get("matched"))
    parsed = sum(1 for s in rnd if s.get("parse_ok"))
    corpus = real_corpus(str(r))
    #: 待裁定样本的规则命中（逐条裁定）——与真实语料命中分开计，口径不混。
    round_hits = [h for s in rnd if s.get("pending") for h in (s.get("hits") or [])]
    round_adj = {a["hit"]: a["verdict"] for s in rnd if s.get("pending")
                 for a in s.get("adjudication") or []}
    round_tp = sum(1 for h in round_hits if round_adj.get(h) == "TP")
    round_fp = sum(1 for h in round_hits if round_adj.get(h) == "FP")
    total, passed = ex_cases + rnd_total, ex_pass + rnd_pass
    return {"schema": SCHEMA,
            "execution": {"sets": ex, "cases": ex_cases, "passed": ex_pass,
                          "fidelity": round(ex_pass / ex_cases, 4) if ex_cases else 0.0},
            "rounds": {"samples": rnd, "total": rnd_total, "matched": rnd_pass,
                       "pending": len(rnd) - rnd_total,
                       "pending_samples": len(rnd) - rnd_total,
                       "parse_ok": parsed, "parse_total": len(rnd),
                       "parse_rate": round(parsed / len(rnd), 4) if rnd else 0.0,
                       "hits": round_hits, "tp": round_tp, "fp": round_fp,
                       "fidelity": round(rnd_pass / rnd_total, 4) if rnd_total else 0.0},
            "real_corpus": corpus,
            "overall": {"cases": total, "passed": passed,
                        "fidelity": round(passed / total, 4) if total else 0.0},
            "metrics": {"parse_rate": round(parsed / len(rnd), 4) if rnd else 0.0,
                        "parse_ok": parsed, "parse_total": len(rnd),
                        "raw_parse_rate": corpus.get("raw_parse_rate", 0.0),
                        "hits": corpus.get("hits", 0),
                        "tp": corpus.get("tp", 0),
                        "fp": corpus.get("fp", 0),
                        "hits_before": corpus.get("hits_before", 0),
                        "fp_resolved": corpus.get("fp_resolved", 0),
                        "round_hits": len(round_hits),
                        "round_tp": round_tp, "round_fp": round_fp}}


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


def _round_issues(samples: list[dict[str, Any]]) -> list[str]:
    """回合级样本的判据问题（声明未复现 / 待裁定样本 parse 或裁定缺位）。"""
    issues: list[str] = []
    for s in samples:
        if s.get("error"):
            issues.append("{} {}".format(s["sample"], s["error"]))
            continue
        if not s.get("pending"):
            if not s.get("matched"):
                issues.append("回合级回放未复现声明：{} 声明={} 实测={}（{}）（修复指引：修样本或"
                              "回合断言——回放须可复现声明结论）"
                              .format(s["sample"], s.get("declared"), s.get("live"),
                                      str(s.get("first_issue"))[:60]))
            continue
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
