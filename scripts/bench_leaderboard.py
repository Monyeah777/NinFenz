#!/usr/bin/env python3
# nf-io: inputs=results/bench/results,results/bench/gate_defect_report.json,protocol/schema/bench_result.schema.json outputs=results/bench/LEADERBOARD.md
"""公开 benchmark 榜与结果校验（T6.3）：把缺陷注入台升级成「可提交、可复算、可排序」的榜。

要回答的问题
------------
缺陷注入台（`scripts/gate_defect_bench.py`）回答「profile 能抓多少缺陷」；本件回答「**谁**在
同一台架上跑出了什么成绩，且这些成绩能不能被复核」。没有真实模型结果时**保持诚实空榜**——
不用台架基线冒充模型成绩，也不手写排名。

三条纪律
--------
1. **数据只来自可复算证据**：每条结果行（`results/bench/results/*.json`，schema
   `nf-bench-result/1`）的 `evidence_path` 必须指向 `results/bench/evidence/` 下的实际文件，
   `contract_digest` 是它的 sha256；榜单生成时**现场复算**，手改数字必红。
2. **数字自洽 + 判定复算**：`detection_rate == round(detected/cases,4)`、
   `fp_rate == round(false_positives/clean_cases,4)`；`verdict` 按台架阈值（≥90% / ≤10%）重算，
   不采信手填。
3. **榜是生成物**：`LEADERBOARD.md` 由本件生成；`--check` 与结果文件/基线报告对账，漂移即红
   （改结果不重生成、或手改榜面，都会被抓住）。

空榜语义
--------
模型结果 0 份 → 榜面显式写「尚无真实模型结果（诚实空榜）」，不排序、不占位。
台架基线（`gate_defect_report.json` 的 techdoc/regulatory 两 profile）单列 `baseline` 表，
标注 **baseline ≠ 模型成绩**；它具有真实证据摘要，可被复核，但不与模型排名混排。

用法
----
    python scripts/bench_leaderboard.py --write    # 校验 + 重生成 LEADERBOARD.md（默认动作）
    python scripts/bench_leaderboard.py --check    # 只校验：输入非法 / 榜面漂移 → rc 1
    python scripts/bench_leaderboard.py --json     # 机器面摘要
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
sys.path.insert(0, str(ROOT / "scripts"))

from core import atomic_write, json_doc, schema_lint  # noqa: E402

SCHEMA_NAME = "bench_result.schema.json"
RESULT_KIND = "nf-bench-result/1"
BASELINE_KIND = "nf-gate-defect-bench/1"
RESULTS_REL = "results/bench/results"
EVIDENCE_REL = "results/bench/evidence"
BASELINE_REL = "results/bench/gate_defect_report.json"
BOARD_REL = "results/bench/LEADERBOARD.md"
JSON_KIND = "nf-bench-leaderboard/1"


class BenchError(RuntimeError):
    """榜面构建前提不成立（schema 缺失/基线缺件等）——不猜、不生成半份榜。"""


# ---------------------------------------------------------------- 基础面
def _sha_text(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _sha_file(path: Path) -> str:
    try:
        return _sha_text(path.read_bytes())
    except OSError:
        return ""


def _slug(submission_id: str) -> str:
    """提交 id → 文件名安全 slug（与 schema pattern 同一词表）。"""
    return re.sub(r"[^A-Za-z0-9._-]+", "_", submission_id).strip("_") or "submission"


def _schema() -> dict:
    schema = schema_lint.load_schema(str(ROOT), SCHEMA_NAME)
    if not isinstance(schema, dict):
        raise BenchError("schema 缺失/非法：protocol/schema/%s（修复指引：先落盘 schema）"
                         % SCHEMA_NAME)
    return schema


def _registry() -> dict:
    """台架在册 profile + 阈值（真源 = gate_defect_bench，不在此手抄第二份）。"""
    import gate_defect_bench as gd

    return {"profiles": dict(gd.PROFILES),
            "min_detection": float(gd.MIN_DETECTION_RATE),
            "max_fp": float(gd.MAX_FP_RATE)}


def _rate(num: int, den: int) -> float:
    return round(num / den, 4) if den else 0.0


def _verdict(detection_rate: float, fp_rate: float, reg: dict) -> str:
    return "pass" if (detection_rate >= reg["min_detection"]
                      and fp_rate <= reg["max_fp"]) else "fail"


# ---------------------------------------------------------------- 结果行校验
def _semantic_errors(row: dict, rel: str, root: Path, reg: dict) -> list:
    errs: list = []
    pid = row["profile"]
    if pid not in reg["profiles"]:
        errs.append("%s: profile 不在册：%r（在册 %s）"
                    % (rel, pid, "、".join(sorted(reg["profiles"]))))
    cases, clean = int(row["cases"]), int(row["clean_cases"])
    detected, fp = int(row["detected"]), int(row["false_positives"])
    if detected > cases:
        errs.append("%s: detected=%d > cases=%d（数字不自洽）" % (rel, detected, cases))
    if fp > clean:
        errs.append("%s: false_positives=%d > clean_cases=%d（数字不自洽）"
                    % (rel, fp, clean))
    want_det = _rate(detected, cases)
    want_fp = _rate(fp, clean)
    if abs(float(row["detection_rate"]) - want_det) > 1e-9:
        errs.append("%s: detection_rate=%r 与复算值 %r 不符（detected/cases）"
                    % (rel, row["detection_rate"], want_det))
    if abs(float(row["fp_rate"]) - want_fp) > 1e-9:
        errs.append("%s: fp_rate=%r 与复算值 %r 不符（false_positives/clean_cases）"
                    % (rel, row["fp_rate"], want_fp))
    if pid in reg["profiles"] and row["verdict"] != _verdict(want_det, want_fp, reg):
        errs.append("%s: verdict=%r 与阈值复算不符（应为 %r）"
                    % (rel, row["verdict"], _verdict(want_det, want_fp, reg)))
    expected_suffix = "__%s.json" % pid
    if not Path(rel).name.endswith(expected_suffix):
        errs.append("%s: 文件名须以 %r 结尾（提交 id slug + profile；规范见 %s/README.md）"
                    % (rel, expected_suffix, RESULTS_REL))
    evidence = root / str(row["evidence_path"])
    if not evidence.is_file():
        errs.append("%s: 证据件不存在：%s（修复指引：把原始证据放 %s/）"
                    % (rel, row["evidence_path"], EVIDENCE_REL))
    elif _sha_file(evidence) != str(row["contract_digest"]):
        errs.append("%s: contract_digest 与在盘证据不符（证据被改过或摘要填错）" % rel)
    for key in ("model", "provider", "version", "date"):
        if not str(row[key]).strip():
            errs.append("%s: %s 不得为空" % (rel, key))
    return errs


def collect_rows(root: Path, schema: dict, reg: dict) -> tuple:
    """收集并校验全部结果行 → (rows, errors)；无效行**不进入**榜。"""
    rows: list = []
    errors: list = []
    results_dir = root / RESULTS_REL
    if not results_dir.is_dir():
        return rows, errors
    seen: dict = {}
    meta: dict = {}
    for path in sorted(results_dir.glob("*.json")):
        rel = str(path.relative_to(root)).replace("\\", "/")
        try:
            row = json_doc.load(path, dict, what=rel)
        except ValueError as exc:
            errors.append(str(exc))
            continue
        shape = schema_lint.subset_validate(row, schema, path=rel)
        if shape:
            errors += shape
            continue
        errs = _semantic_errors(row, rel, root, reg)
        if errs:
            errors += errs
            continue
        key = (str(row["submission_id"]), str(row["profile"]))
        if key in seen:
            errors.append("%s: 与 %s 重复（同一 submission_id × profile 只允许一条）"
                          % (rel, seen[key]))
            continue
        seen[key] = rel
        ident = (str(row["model"]), str(row["provider"]),
                 str(row["version"]), str(row["date"]))
        prev = meta.get(str(row["submission_id"]))
        if prev is not None and prev[0] != ident:
            errors.append("%s: 同一 submission_id 的模型元数据不一致（首见 %s）"
                          % (rel, prev[1]))
            continue
        meta.setdefault(str(row["submission_id"]), (ident, rel))
        rows.append(dict(row, _rel=rel))
    return rows, errors


# ---------------------------------------------------------------- 台架基线（非模型）
def baseline_rows(root: Path, reg: dict) -> tuple:
    """从 gate_defect_bench 报告派生 baseline 行（不改台架判定，只读其汇总）。"""
    path = root / BASELINE_REL
    if not path.is_file():
        return [], ["台架基线缺失：%s（修复指引：先跑 python scripts/gate_defect_bench.py）"
                    % BASELINE_REL]
    try:
        doc = json_doc.load(path, dict, what=BASELINE_REL)
    except ValueError as exc:
        return [], [str(exc)]
    if str(doc.get("schema") or "") != BASELINE_KIND:
        return [], ["%s: schema 非 %s：%r"
                    % (BASELINE_REL, BASELINE_KIND, doc.get("schema"))]
    digest = _sha_file(path)
    rows: list = []
    errors: list = []
    for pid in sorted(reg["profiles"]):
        totals = ((doc.get("profiles") or {}).get(pid) or {}).get("totals") or {}
        try:
            cases = int(totals["negatives"])
            clean = int(totals["clean_cases"])
            detected = int(totals["detected"])
            fp = int(totals["fail_flagged_clean"])
        except (KeyError, TypeError, ValueError):
            errors.append("%s: profile %s 的 totals 缺字段（negatives/clean_cases/"
                          "detected/fail_flagged_clean）" % (BASELINE_REL, pid))
            continue
        want_det = _rate(detected, cases)
        want_fp = _rate(fp, clean)
        if abs(float(totals.get("detection_rate", -1)) - want_det) > 1e-9:
            errors.append("%s: %s detection_rate 与复算不符（%r ≠ %r）"
                          % (BASELINE_REL, pid, totals.get("detection_rate"), want_det))
            continue
        if abs(float(totals.get("fp_rate", -1)) - want_fp) > 1e-9:
            errors.append("%s: %s fp_rate 与复算不符（%r ≠ %r）"
                          % (BASELINE_REL, pid, totals.get("fp_rate"), want_fp))
            continue
        rows.append({
            "submission_id": "nf-gate-defect-bench/baseline",
            "model": "gate-defect-bench baseline", "provider": "NinFenz",
            "version": "T5.3", "date": "2026-10-26", "profile": pid,
            "cases": cases, "clean_cases": clean, "detected": detected,
            "false_positives": fp, "detection_rate": want_det, "fp_rate": want_fp,
            "verdict": _verdict(want_det, want_fp, reg),
            "evidence_path": BASELINE_REL, "contract_digest": digest,
        })
    return rows, errors


# ---------------------------------------------------------------- 榜面渲染
def _rank(rows: list) -> list:
    """排序：pass 优先 → 检出率降序 → 误报率升序 → submission_id 升序（全确定）。"""
    return sorted(rows, key=lambda r: (0 if r["verdict"] == "pass" else 1,
                                       -float(r["detection_rate"]),
                                       float(r["fp_rate"]),
                                       str(r["submission_id"])))


def _fmt_rate(value: float) -> str:
    return "%.2f%%" % (float(value) * 100)


def _short_digest(digest: str) -> str:
    return str(digest).replace("sha256:", "")[:12]


def _model_table(rows: list) -> list:
    out = ["| 排名 | 提交 | 模型 | 提供方 | 版本 | 日期 | 负例 | 检出 | 误报 | 检出率 | 误报率 | 判定 | 证据摘要 |",
           "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for i, r in enumerate(_rank(rows), 1):
        out.append("| %d | %s | %s | %s | %s | %s | %d | %d | %d | %s | %s | %s | `%s` |"
                   % (i, r["submission_id"], r["model"], r["provider"], r["version"],
                      r["date"], r["cases"], r["detected"], r["false_positives"],
                      _fmt_rate(r["detection_rate"]), _fmt_rate(r["fp_rate"]),
                      r["verdict"], _short_digest(r["contract_digest"])))
    return out


def _baseline_table(rows: list) -> list:
    out = ["| profile | 来源 | 负例 | 检出 | 误报 | 检出率 | 误报率 | 判定 | 证据 |",
           "|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        out.append("| %s | baseline | %d | %d | %d | %s | %s | %s | `%s` |"
                   % (r["profile"], r["cases"], r["detected"], r["false_positives"],
                      _fmt_rate(r["detection_rate"]), _fmt_rate(r["fp_rate"]),
                      r["verdict"], r["evidence_path"]))
    return out


def render(model_rows: list, base_rows: list, reg: dict) -> str:
    profiles = sorted(reg["profiles"])
    lines = [
        "# NF Benchmark 榜（gate profile 缺陷注入台）",
        "",
        "> 本文件是**生成物**，勿手改：`python scripts/bench_leaderboard.py --write` 生成，"
        "`--check` 对账（漂移即红）。",
        "> 台架：`scripts/gate_defect_bench.py`（T5.3，10 类 × 8 负 + 2 正 × profile）；"
        "结果行 schema：`protocol/schema/bench_result.schema.json`（`nf-bench-result/1`）。",
        "> 判定阈值：负例检出率 ≥%.0f%% 且清洁件误报率 ≤%.0f%%（`verdict=pass`）。"
        % (reg["min_detection"] * 100, reg["max_fp"] * 100),
        "",
        "## 状态",
        "",
        "- 真实模型结果：**%d 条**%s" % (len(model_rows),
                                     "" if model_rows else
                                     " —— 尚无真实模型结果（诚实空榜：不伪造排名、不用基线冒充）"),
        "- 台架基线：%d 行（**baseline ≠ 模型成绩**；仅标定台架自身口径）" % len(base_rows),
        "",
    ]
    for pid in profiles:
        lines += ["## 模型榜 · %s" % pid, ""]
        own = [r for r in model_rows if r["profile"] == pid]
        if own:
            lines += _model_table(own)
        else:
            lines.append("尚无真实模型结果（诚实空榜）：本 profile 暂无可比的模型提交。")
        lines.append("")
    lines += ["## 台架基线（baseline ≠ 模型成绩）", ""]
    if base_rows:
        lines += _baseline_table(base_rows)
    else:
        lines.append("台架基线缺失（先跑 `python scripts/gate_defect_bench.py` 生成报告）。")
    lines += [
        "",
        "## 如何提交（目录规范）",
        "",
        "1. 把原始证据（台架可复算的 JSON）放 `results/bench/evidence/`；",
        "2. 结果行放 `results/bench/results/<submission slug>__<profile>.json`"
        "（schema：`nf-bench-result/1`；`contract_digest` = 证据件 sha256）；",
        "3. 一条命令重生成并自检：`python scripts/bench_leaderboard.py --write`；",
        "   CI/复核用：`python scripts/bench_leaderboard.py --check`（结果与榜面不一致即红）。",
        "",
        "> 诚实边界：本榜只聚合**在盘、可复算、数字自洽**的结果行；未提交证据的分数不进榜，",
        "> 台架基线不参与模型排名。",
        "",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------- 构建/校验
def build(root: Path = ROOT) -> dict:
    """→ {"text", "models", "baselines", "errors", "ok"}（纯函数：无时间戳，同输入同字节）。"""
    reg = _registry()
    schema = _schema()
    model_rows, errors = collect_rows(root, schema, reg)
    base_rows, base_errors = baseline_rows(root, reg)
    errors = list(errors) + list(base_errors)
    text = render(model_rows, base_rows, reg)
    return {"text": text, "models": model_rows, "baselines": base_rows,
            "errors": errors, "ok": not errors}


def check(root: Path = ROOT) -> list:
    """→ 差异/错误列表（空 = 输入合法且榜面与输入一致）。"""
    doc = build(root)
    problems = list(doc["errors"])
    board = root / BOARD_REL
    if not board.is_file():
        problems.append("%s 缺失（修复指引：python scripts/bench_leaderboard.py --write）"
                        % BOARD_REL)
    else:
        try:
            on_disk = board.read_text(encoding="utf-8")
        except OSError as exc:
            problems.append("%s 不可读：%s" % (BOARD_REL, exc))
            on_disk = None
        if on_disk is not None and on_disk != doc["text"]:
            problems.append("%s 与结果文件/基线报告不一致（漂移）——"
                            "请重跑 python scripts/bench_leaderboard.py --write" % BOARD_REL)
    return problems


def write_board(root: Path = ROOT) -> tuple:
    doc = build(root)
    if doc["errors"]:
        return doc, list(doc["errors"])
    out = root / BOARD_REL
    atomic_write.write_text(out, doc["text"])
    return doc, []


# ---------------------------------------------------------------- CLI
def main(argv: list | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="公开 benchmark 榜：收集/校验结果行 → 生成 LEADERBOARD.md（--check 防漂移）")
    act = ap.add_mutually_exclusive_group()
    act.add_argument("--write", action="store_true", help="校验 + 重生成榜（默认动作）")
    act.add_argument("--check", action="store_true", help="只校验：输入非法/榜面漂移 → rc 1")
    ap.add_argument("--root", default="", help="仓库根（默认本文件所在仓；测试/多仓用）")
    ap.add_argument("--json", action="store_true", help="机器面摘要")
    args = ap.parse_args(argv)
    root = Path(args.root).resolve() if args.root else ROOT

    if args.check:
        problems = check(root)
        if args.json:
            print(json.dumps({"schema": JSON_KIND, "ok": not problems,
                              "problems": problems}, ensure_ascii=False,
                             indent=2, sort_keys=True))
        else:
            for p in problems:
                print("  [FAIL] %s" % p, file=sys.stderr)
            if problems:
                print("榜/结果不自洽（%d 处）" % len(problems), file=sys.stderr)
            else:
                print("== benchmark 榜校验通过（输入合法、榜面未漂移）==")
        return 1 if problems else 0

    doc, errors = write_board(root)
    if errors:
        for e in errors:
            print("  [FAIL] %s" % e, file=sys.stderr)
        print("结果行/基线不合法（%d 处）——未更新榜" % len(errors), file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps({
            "schema": JSON_KIND, "ok": True,
            "models": len(doc["models"]), "baselines": len(doc["baselines"]),
            "board": BOARD_REL,
            "empty_board": not doc["models"],
        }, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print("== benchmark 榜已生成：%s ==" % BOARD_REL)
        print("  模型结果 %d 条 · 台架基线 %d 行%s"
              % (len(doc["models"]), len(doc["baselines"]),
                 "（诚实空榜：尚无真实模型结果）" if not doc["models"] else ""))
    return 0


if __name__ == "__main__":
    for _stream in (sys.stdout, sys.stderr):
        if hasattr(_stream, "reconfigure"):
            _stream.reconfigure(encoding="utf-8")
    raise SystemExit(main())
