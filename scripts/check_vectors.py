#!/usr/bin/env python3
"""cc_check 判定向量集：策略 + 对象字节 → 期望 verdict（跨语言可复核）。

为什么单独一份（2026-11-07）：证据线已有 28 例跨语言向量，而 cc_check 此前只有本仓实现与
单测——换语言写第二实现没有锚点。这里把「输入 → 期望判定」固化下来，口径与证据向量一致：
- 对象字节内嵌（b64），策略内联，第三方只读这份 JSON 就能自证；
- 判据面包含 verdict / failed / warned 与**逐条规则 ok**（只看 verdict 会漏掉 warn 面的错）；
- 坏策略也入向量（期望「拒绝」，rc=4）：不许静默放过。

纪律：确定性（同输入逐字节一致），--write 两次相同，--check 比对提交件。
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import atomic_write, check_policy, json_doc  # noqa: E402

SCHEMA = "nf-check-vectors/1"
OUT_REL = "results/ccos/check_verdict_vectors.json"
GUIDE = "修复指引："
TEXT = "由 AI 生成的内容。\n本行用于长度与行数判定。\n".encode()
BINARY = b"\xff\xfe\x00\x01not-utf8"
PIN = hashlib.sha256(TEXT).hexdigest()


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def _policy(pid: str, rules: list) -> dict:
    return {"schema": check_policy.SCHEMA, "id": pid, "rules": rules}


def _rule(rid: str, kind: str, fix: str = "修复指引：示例", **extra) -> dict:
    return {"id": rid, "kind": kind, "fix": fix, **extra}


def _case(cid: str, desc: str, data: bytes, policy: dict, *,
          verdict: str = "", expect_reject: bool = False) -> dict:
    row = {"id": cid, "desc": desc, "object_b64": _b64(data),
           "object_sha256": hashlib.sha256(data).hexdigest(), "policy": policy}
    if expect_reject:
        row["expected"] = {"rejected": True, "exit_code": 4}
    else:
        row["expected"] = {"verdict": verdict, "exit_code": 0 if verdict == "ok" else 1}
    return row


def build_vectors() -> dict:
    rows = []
    ok_policy = _policy("ok-all", [
        _rule("r-utf8", "utf8"),
        _rule("r-present", "regex_present", pattern="AI"),
        _rule("r-count", "count_at_least", field="bytes", n=10),
        _rule("r-digest", "digest_pin", sha256=PIN),
    ])
    rows.append(_case("ok_all_kinds", "四类规则全过", TEXT, ok_policy, verdict="ok"))

    absent_hit = _policy("absent-hit", [
        _rule("r-absent", "regex_absent", pattern="AI"),
    ])
    rows.append(_case("regex_absent_hit", "禁止内容出现", TEXT, absent_hit,
                      verdict="invalid"))

    warn_only = _policy("warn-only", [
        _rule("r-warn", "regex_present", severity="warn", pattern="不存在的词"),
        _rule("r-utf8", "utf8"),
    ])
    rows.append(_case("warn_does_not_flip", "warn 级违规不改判定", TEXT, warn_only,
                      verdict="ok"))

    digest_bad = _policy("digest-bad", [
        _rule("r-digest", "digest_pin", sha256="0" * 64),
    ])
    rows.append(_case("digest_mismatch", "摘要钉不符", TEXT, digest_bad,
                      verdict="invalid"))

    rows.append(_case("non_utf8_fails", "非 UTF-8 对象", BINARY,
                      _policy("utf8-only", [_rule("r-utf8", "utf8")]),
                      verdict="invalid"))

    bad_policy = {"schema": "nope", "rules": []}
    rows.append(_case("bad_policy_rejected", "坏策略必须拒绝（rc=4）", TEXT, bad_policy,
                      expect_reject=True))
    return {"schema": SCHEMA, "count": len(rows), "vectors": rows}


def render(doc: dict) -> str:
    return json.dumps(doc, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def check_vectors() -> list:
    path = ROOT / OUT_REL
    live = build_vectors()
    if not path.is_file():
        return [f"缺向量集 {OUT_REL}（{GUIDE}跑 python scripts/check_vectors.py --write）"]
    try:
        recorded = json_doc.loads(path.read_text(encoding="utf-8"), dict, what=OUT_REL)
    except (OSError, ValueError) as exc:
        return [f"{OUT_REL} 不可读：{exc}（{GUIDE}重跑 --write）"]
    if render(recorded) != render(live):
        return [f"{OUT_REL} 与重算不一致（{GUIDE}重跑 --write 后再提交）"]
    return []


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="check_vectors",
                                 description="cc_check 判定向量集（跨语言可复核）")
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    if args.write:
        dest = ROOT / OUT_REL
        dest.parent.mkdir(parents=True, exist_ok=True)
        doc = build_vectors()
        atomic_write.write_text(str(dest), render(doc))
        print(f"OK 已写入 {OUT_REL}（{doc['count']} 例）")
        return 0
    issues = check_vectors()
    for issue in issues:
        print(f"  [FAIL] {issue}", file=sys.stderr)
    print("FAIL 向量集不一致" if issues else "OK 向量集与重算一致")
    return 1 if issues else 0


if __name__ == "__main__":
    for _stream in (sys.stdout, sys.stderr):
        if hasattr(_stream, "reconfigure"):
            _stream.reconfigure(encoding="utf-8")
    raise SystemExit(main())
