#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""跨语言契约对拍器（W-10 / P-C0 走通件）。

读向量清单（nf-test-vectors/1），对每条向量跑各语言声明的命令，按 compare_rule 归一后
逐字节比对。纪律（§16.2/§16.8）：
  - 工具链缺席 → 该语言 UNKNOWN，**不下结论**；整条向量若无其他分歧则记 UNKNOWN；
  - 只有「可比且比错」才是 FAIL（偏离方标 FAIL，附期望值）；
  - probe 条目只探工具链在场，不比对输出（P-C1 起才是真契约向量）。
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROBES = {"python": "python", "rust": "cargo", "csharp": "dotnet"}
LANGS = tuple(PROBES)


def toolchains():
    """→ {语言: 可执行路径 或 None}（缺席即 None，由调用方记 UNKNOWN）。"""
    return {lang: shutil.which(exe) for lang, exe in sorted(PROBES.items())}


def canonical(rule, data):
    """按 compare_rule 归一。

    byte：**先把 CRLF 折成 LF**——同一实现在 Windows/Linux 的新行形态不同，这是平台噪声
    而非语义分歧（§16.3 要求规则显式，故此归一写在规则里）；
    jcs：sort_keys + 紧凑分隔（RFC 8785 的细节自 P-C1 起补）。
    """
    if rule == "byte":
        return data.replace(b"\r\n", b"\n")
    if rule == "jcs":
        obj = json.loads(data.decode("utf-8"))
        return (json.dumps(obj, ensure_ascii=False, sort_keys=True,
                           separators=(",", ":")) + "\n").encode("utf-8")
    raise ValueError("未知 compare_rule：%s" % rule)


def run_cmd(cmd, cwd, timeout=120):
    """跑一条命令 → (rc, stdout)。超时记 rc=-9（调用方标 FAIL 或按需记 UNKNOWN）。"""
    try:
        proc = subprocess.run([str(x) for x in cmd], cwd=cwd, capture_output=True,
                              timeout=timeout)
        return proc.returncode, proc.stdout
    except FileNotFoundError:
        return -2, b""
    except subprocess.TimeoutExpired:
        return -9, b""


def verify(doc, root=ROOT, runner=run_cmd, tools=None):
    """→ 报告：逐向量逐语言三态 + 整条/整体判决（PASS/FAIL/UNKNOWN）。"""
    tools = tools if tools is not None else toolchains()
    report = {"schema": "nf-cross-lang-report/1", "vectors": [], "verdict": "PASS"}
    for v in doc.get("vectors") or []:
        rule = str(v.get("compare_rule") or "byte")
        expected = canonical(rule, str(v.get("expected") or "").encode("utf-8"))
        row = {"id": str(v.get("id")), "rule": rule, "langs": {}}
        missing, mismatch = [], []
        for lang, spec in sorted((v.get("langs") or {}).items()):
            exe = tools.get(lang)
            if spec.get("probe"):
                if not exe:
                    row["langs"][lang] = {"status": "UNKNOWN",
                                          "detail": "工具链缺席：%s" % PROBES.get(lang, lang)}
                    missing.append(lang)
                    continue
                rc, out = runner(spec.get("cmd") or [], root)
                ok = (rc == 0 and bool(out.strip()))
                row["langs"][lang] = {
                    "status": "PASS" if ok else "UNKNOWN",
                    "detail": "工具链探针（rc=%d，输出 %d 字节%s）"
                              % (rc, len(out), "" if ok else "：在场但无可用 SDK")}
                if not ok:
                    missing.append(lang)
                continue
            if not exe:
                row["langs"][lang] = {"status": "UNKNOWN",
                                      "detail": "工具链缺席：%s" % PROBES.get(lang, lang)}
                missing.append(lang)
                continue
            rc, out = runner(spec.get("cmd") or [], root)
            got = canonical(rule, out)
            ok = (rc == 0 and got == expected)
            row["langs"][lang] = {"status": "PASS" if ok else "FAIL", "rc": rc,
                                  "got": got.decode("utf-8", "replace")[:120]}
            if not ok:
                mismatch.append(lang)
        row["verdict"] = "FAIL" if mismatch else ("UNKNOWN" if missing else "PASS")
        report["vectors"].append(row)
    if any(r["verdict"] == "FAIL" for r in report["vectors"]):
        report["verdict"] = "FAIL"
    elif any(r["verdict"] == "UNKNOWN" for r in report["vectors"]):
        report["verdict"] = "UNKNOWN"
    report["toolchains"] = tools
    report["arbitration"] = arbitrate(report["vectors"])
    return report


def arbitrate(vectors):
    """多实现仲裁（P-C2）：**规范是权威**，多数票只作定位线索。

    可比值 = status ∈ {PASS, FAIL}（UNKNOWN 不参与投票）。
      - 无偏离 ⇒ PASS；
      - 单一偏离 ⇒ FAIL，该实现为首要嫌疑（规范为权威，不因多数而改判）；
      - 多数偏离 ⇒ **SPEC-GAP**：先怀疑规范/判据本身，禁止用多数票裁定"实现对"。
    """
    available, deviants = [], []
    for row in vectors:
        for lang, st in sorted((row.get("langs") or {}).items()):
            status = st.get("status")
            if status == "PASS":
                available.append("%s/%s" % (row.get("id"), lang))
            elif status == "FAIL":
                available.append("%s/%s" % (row.get("id"), lang))
                deviants.append("%s/%s" % (row.get("id"), lang))
    if not available:
        return {"outcome": "UNKNOWN", "clue": "无可比实现（工具链缺席）——不下结论"}
    if not deviants:
        return {"outcome": "PASS", "comparable": len(available),
                "clue": "所有可比实现与规范一致"}
    if len(deviants) * 2 >= len(available):
        return {"outcome": "SPEC-GAP", "suspects": deviants, "comparable": len(available),
                "clue": "多数可比实现偏离规范 ⇒ 先怀疑规范/判据本身；"
                        "多数票**不得**用作改判依据（INV-6：规范 > 实现）"}
    return {"outcome": "FAIL", "suspects": deviants, "comparable": len(available),
            "clue": "单一实现偏离规范 ⇒ 该实现为首要嫌疑；多数票仅作定位线索"}


# ---------------------------------------------------------------- self-test
#: 可执行名 → 语言键（命令首元素是 exe，不是语言名）。
_EXE_LANG = {"python": "python", "cargo": "rust", "dotnet": "csharp"}


def _fake(expected_by_lang, missing=()):
    tools = {lang: (None if lang in missing else "/fake/" + lang) for lang in LANGS}
    def runner(cmd, cwd, timeout=120):
        lang = _EXE_LANG.get(str(cmd[0]), str(cmd[0]))
        return 0, expected_by_lang.get(lang, b"")
    return tools, runner


def self_test():
    doc = {"schema": "nf-test-vectors/1", "vectors": [
        {"id": "t", "compare_rule": "byte", "expected": "ok\n",
         "langs": {"python": {"cmd": ["python"]}, "rust": {"cmd": ["cargo"]},
                   "csharp": {"cmd": ["dotnet"]}}}]}
    # 1) 三语言一致 → PASS
    tools, runner = _fake({"python": b"ok\n", "rust": b"ok\n", "csharp": b"ok\n"})
    assert verify(doc, runner=runner, tools=tools)["verdict"] == "PASS"
    # 2) 一语言偏离 → FAIL
    tools, runner = _fake({"python": b"ok\n", "rust": b"bad\n", "csharp": b"ok\n"})
    rep = verify(doc, runner=runner, tools=tools)
    assert rep["verdict"] == "FAIL" and rep["vectors"][0]["langs"]["rust"]["status"] == "FAIL"
    # 3) 工具链缺席且其余一致 → UNKNOWN（不下结论）
    tools, runner = _fake({"python": b"ok\n", "csharp": b"ok\n"}, missing=("rust",))
    rep = verify(doc, runner=runner, tools=tools)
    assert rep["verdict"] == "UNKNOWN", rep
    # 4) probe 只探在场：缺席即 UNKNOWN
    pdoc = {"schema": "nf-test-vectors/1", "vectors": [
        {"id": "p", "compare_rule": "byte", "expected": "",
         "langs": {"rust": {"cmd": ["cargo"], "probe": True}}}]}
    assert verify(pdoc, runner=runner, tools=tools)["verdict"] == "UNKNOWN"
    # 5) probe 在场但输出为空（有 exe 无 SDK）→ 仍 UNKNOWN
    all_tools = {lang: "/fake/" + lang for lang in LANGS}
    empty = lambda cmd, cwd, timeout=120: (0, b"")
    assert verify(pdoc, runner=empty, tools=all_tools)["verdict"] == "UNKNOWN"
    print("self-test OK（一致=PASS / 偏离=FAIL / 缺席=UNKNOWN / probe 三态 / 空 SDK=UNKNOWN）")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description="跨语言契约对拍器（只读）")
    ap.add_argument("--manifest", default="")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args(argv)
    if args.self_test:
        return self_test()
    if not args.manifest:
        print("  ✗ 缺 --manifest（修复指引：给向量清单路径）", file=sys.stderr)
        return 2
    doc = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
    rep = verify(doc, root=ROOT)
    if args.json:
        print(json.dumps(rep, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print("== 跨语言对拍（%s）==" % rep["verdict"])
        arb = rep.get("arbitration") or {}
        print("  仲裁：%s（%s）" % (arb.get("outcome"), arb.get("clue")))
        for s in arb.get("suspects") or []:
            print("    嫌疑：%s" % s)
        for row in rep["vectors"]:
            print("  %s [%s]" % (row["id"], row["verdict"]))
            for lang, st in sorted(row["langs"].items()):
                print("    %-7s %-8s %s" % (lang, st["status"], st.get("detail") or st.get("got", "")))
    return 1 if rep["verdict"] == "FAIL" else 0


if __name__ == "__main__":
    for _s in (sys.stdout, sys.stderr):
        if hasattr(_s, "reconfigure"):
            _s.reconfigure(encoding="utf-8")
    raise SystemExit(main())
