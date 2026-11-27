"""core.drill_fidelity 私有实现分片 1/2（对外只经 core.drill_fidelity 门面导入）：EXEC_GLOB 等"""

from __future__ import annotations

import hashlib
import re
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


#: 正例对照夹具（2026-10-20）：真实语料的**注入变体**与期望命中（注入→必红 / 原版→必绿）。
POSITIVE_CONTROLS_REL = "desktop/tests/fixtures/execution/positive_controls/p03_injections.json"


def _case_good(hits: list[str], expect: set) -> bool:
    return (not expect and not hits) or expect <= set(hits)


def _exec_set_file(f: Path) -> dict[str, Any]:
    """单执行样本集：逐例回放 + 期望命中判据 → 计数行。"""
    from core import execution_drill as ed

    try:
        data = json_doc.load(f, dict, what=f.name)
    except ValueError as exc:
        return {"set": f.name, "cases": 0, "passed": 0,
                "error": f"JSON 不可解析：{exc}"}
    opts = ed.CaseOptions(
        semantics=data.get("semantics") or {},
        source_text=data.get("source_text", ""),
        other_ids=data.get("other_ids") or [],
        asset_keys=data.get("asset_keys") or [],
        lexicon=data.get("lexicon") or {})
    real: list[str] = data.get("real_ids") or []
    n = ok = 0
    for case in data.get("cases", []):
        hits = ed.run_case(case, real, opts=opts)
        n += 1
        ok += 1 if _case_good(hits, set(case.get("expect_captured") or [])) else 0
    return {"set": f.name, "cases": n, "passed": ok}


def _exec_sets(root: Path) -> list[dict[str, Any]]:
    return [_exec_set_file(f) for f in sorted(root.glob(EXEC_GLOB))]


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


def _round_verdict_fields(d: dict[str, Any], live: str) -> dict[str, Any]:
    """声明侧判定：pending / declared / matched / label_status。"""
    raw_verdict = str(d.get("verdict") or "")
    pending = (str(d.get("label_status") or "").lower() == PENDING
               or raw_verdict.lower() == PENDING)
    declared = PENDING if pending else VERDICT_MAP.get(raw_verdict.lower(), raw_verdict)
    return {"declared": declared,
            "matched": (None if pending else declared == live),
            "label_status": PENDING if pending else "adjudicated",
            "pending": pending}


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
    turns = int(stats.get("turns") or 0)
    fields = _round_verdict_fields(d, live)
    return {"sample": name,
            "declared": fields["declared"],
            "live": live,
            "matched": fields["matched"],
            "label_status": fields["label_status"],
            "pending": fields["pending"],
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
        for rule in ed.run_case({'output': line}, real_ids, opts=ed.CaseOptions(semantics={})):
            live.append((line_no, rule))
    return live


def _text_hits(text: str, real_ids: list[str]) -> list[tuple[int, str]]:
    """整段文本逐非空行回放 `execution_drill` → `[(行号, 规则名)]`（正例对照用）。"""
    return _corpus_live_hits(
        [(i + 1, line) for i, line in enumerate(text.splitlines()) if line.strip()], real_ids)


def _pc_source(r: Path) -> dict[str, Any]:
    """读取正例对照清单与源语料 → `{manifest, source_rel, source_text, real_ids, sha, problems}`。

    清单/语料缺件时 `problems` 非空且 `manifest` 为 `None`（上层据此返回 `{}` 或带问题的块）。
    """
    manifest_p = r / POSITIVE_CONTROLS_REL
    out: dict[str, Any] = {"manifest": None, "source_rel": REAL_CORPUS_REL, "source_text": "",
                           "real_ids": [], "sha": "", "problems": []}
    if not manifest_p.is_file():
        return out
    try:
        manifest = json_doc.load(manifest_p, dict, what=POSITIVE_CONTROLS_REL)
    except ValueError as exc:
        out["problems"].append(f"{POSITIVE_CONTROLS_REL} {exc}")
        return out
    out["manifest"] = manifest
    out["source_rel"] = str(manifest.get("source") or REAL_CORPUS_REL)
    source_p = r / out["source_rel"]
    if not source_p.is_file():
        out["problems"].append(f"正例对照源语料缺件：{out['source_rel']}")
        return out
    out["source_text"] = source_p.read_text(encoding="utf-8")
    out["sha"] = hashlib.sha256(source_p.read_bytes()).hexdigest()
    out["real_ids"] = [str(x) for x in (manifest.get("real_ids") or [])]
    if manifest.get("source_sha256") and manifest["source_sha256"] != out["sha"]:
        out["problems"].append(f"正例对照源语料已变（sha256 不匹配）——须重生成变体："
                               f"{out['source_rel']}")
    return out


def _pc_expected_hits(hits: list[tuple[int, str]],
                       line_no: int) -> tuple[list[str], list[tuple[int, str]]]:
    """注入行的命中集与附带命中（行外命中）。"""
    got = sorted({rule for n, rule in hits if n == line_no})
    extra = [(n, rule) for n, rule in hits if n != line_no]
    return got, extra


def _pc_problems(cid: str, expect: list[str], got: list[str],
                 extra: list[tuple[int, str]], line_no: int) -> list[str]:
    if extra or not set(expect) <= set(got):
        return [f"正例对照 {cid} 未按预期命中：期望 {expect}，实得行 {line_no}={got}，"
                f"附带命中={extra}（修复指引：判据不得被改弱到什么都不报）"]
    return []


def _pc_case(r: Path, folder: str, item: dict[str, Any], base: str, source_lines: int,
             real_ids: list[str]) -> tuple[dict[str, Any], list[str]]:
    """单个注入变体：校验「变体 == 语料+注入」并回放 → (控制项记录, problems)。"""
    cid = str(item.get("id") or "?")
    injection = str(item.get("injection") or "")
    variant_rel = f"{folder}/{item.get('variant') or ''}"
    expect = [str(x) for x in (item.get("expect") or [])]
    variant_p = r / variant_rel
    if not injection or not variant_p.is_file():
        return {}, [f"正例对照 {cid} 缺注入文本或缺变体件：{variant_rel}"]
    want_text = base + injection + "\n"
    if variant_p.read_text(encoding="utf-8") != want_text:
        return {}, [f"正例对照 {cid} 的变体不是「语料+注入」（须重生成夹具）"]
    line_no = source_lines + 1
    got, extra = _pc_expected_hits(_text_hits(want_text, real_ids), line_no)
    problems = _pc_problems(cid, expect, got, extra, line_no)
    entry = {"id": cid, "kind": str(item.get("kind") or ""), "injection": injection,
             "expect": expect, "line": line_no, "hits": got, "extra_hits": extra,
             "passed": not problems}
    return entry, problems


def _pc_original_block(source_text: str,
                       real_ids: list[str]) -> tuple[list[tuple[int, str]], list[str]]:
    """原版真实语料必须 0 命中（命中即判据/语料之一有问题）。"""
    if not source_text:
        return [], []
    original_hits = _text_hits(source_text, real_ids)
    if original_hits:
        return original_hits, [f"原版真实语料必须 0 命中，实测 {original_hits}"]
    return [], []


def _pc_controls(r: Path, manifest: dict[str, Any], base: str, source_lines: int,
                 real_ids: list[str]) -> tuple[list[dict[str, Any]], list[str]]:
    folder = POSITIVE_CONTROLS_REL.rsplit("/", 1)[0]
    controls: list[dict[str, Any]] = []
    problems: list[str] = []
    for item in manifest.get("controls") or []:
        if not isinstance(item, dict):
            continue
        entry, case_problems = _pc_case(r, folder, item, base, source_lines, real_ids)
        problems += case_problems
        if entry:
            controls.append(entry)
    return controls, problems


def positive_controls(root: str = ".") -> dict[str, Any]:
    """正例对照（活判据）→ 度量块；找不到夹具时返回 `{}`。

    动机见模块头「正例对照」：hits=0 既可能是语料干净，也可能是判据失效；这里用
    「注入→必红 / 原版→必绿」区分。变体必须逐字节等于「语料+注入」，否则判夹具漂移。
    """
    r = Path(root)
    src = _pc_source(r)
    manifest = src["manifest"]
    if manifest is None:
        if not src["problems"]:
            return {}
        return {"source": "", "injections": [], "original_hits": [], "passed": 0, "total": 0,
                "problems": src["problems"]}
    source_text = src["source_text"]
    problems = list(src["problems"])
    base = source_text if source_text.endswith("\n") else source_text + "\n"
    source_lines = len(source_text.splitlines())
    real_ids = src["real_ids"]
    original_hits, orig_problems = _pc_original_block(source_text, real_ids)
    problems += orig_problems
    controls, ctl_problems = _pc_controls(r, manifest, base, source_lines, real_ids)
    problems += ctl_problems
    return {"source": src["source_rel"],
            "sha256": src["sha"],
            "source_lines": source_lines,
            "injections": controls,
            "original_hits": original_hits,
            "original_passed": not original_hits,
            "passed": sum(1 for c in controls if c["passed"]),
            "total": len(controls),
            "problems": problems}


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
