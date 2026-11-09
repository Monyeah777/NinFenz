#!/usr/bin/env python3
"""其余 ABI 调用的判定向量：cc_label（IR 校验）→ 期望结论（跨语言可复核）。

证据线已有 28 例、cc_check 已有 6 例；这份补 cc_label 的声明层。
口径一致：输入内联、判据面看 ok/level/missing（只看 verdict 会漏掉「缺哪条」这件事）。
"""
from __future__ import annotations

import argparse
import base64
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import atomic_write, json_doc, label_ir  # noqa: E402

SCHEMA = "nf-abi-call-vectors/1"
OUT_REL = "results/ccos/label_verdict_vectors.json"
GUIDE = "修复指引："
DIGEST = "a" * 64


def _ir(level: str = "minimal", *, explicit=None, implicit=None, embedded=False,
        standard: str = label_ir.STANDARD, digest: str = DIGEST) -> dict:
    return {"schema": label_ir.SCHEMA, "standard": standard, "level": level,
            "object": {"path": "d/a.md", "digest": digest},
            "explicit": explicit if explicit is not None else [
                {"face": "explicit", "id": "E1", "kind": "text",
                 "where": "start", "value": "AI 生成"}],
            "implicit": implicit if implicit is not None else [
                {"face": "implicit", "id": "I2", "kind": "metadata",
                 "key": "AIGC", "value": "yes"}],
            "carrier": {"embedded": embedded, "producer": "vectors"},
            "contract": "", "boundary": "声明面"}


def _case(cid: str, desc: str, ir: dict) -> dict:
    live = label_ir.validate(ir)
    return {"id": cid, "desc": desc, "ir": ir,
            "expected": {"ok": live["ok"], "level": live["level"],
                         "missing": live["missing"],
                         "warnings": len(live["warnings"])}}


def build_vectors() -> dict:
    full_items = ([{"face": "explicit", "id": "E1", "kind": "text", "where": "start",
                    "value": "AI 生成"}],
                  [{"face": "implicit", "id": "I2", "kind": "metadata",
                    "key": "AIGC", "value": "yes"}])
    rows = [
        _case("minimal_ok", "minimal 档 E1+I2 齐备", _ir()),
        _case("minimal_missing_e1", "minimal 档缺 E1",
              _ir(explicit=[])),
        _case("full_missing_items", "full 档缺 E2/I1（只有 E1、I2）",
              _ir("full", explicit=full_items[0], implicit=full_items[1])),
        _case("bad_standard", "standard 不是 GB 45438-2025",
              _ir(standard="GB 00000-1999")),
        _case("bad_digest", "object.digest 不是 64 hex", _ir(digest="xyz")),
        _case("carrier_embedded_warns", "carrier.embedded=true 只自称（warning）",
              _ir(embedded=True)),
        _case("bad_level", "level 非法", _ir("ultra")),
    ]
    return {"schema": SCHEMA, "count": len(rows), "vectors": rows}




ATTEST_REL = "results/ccos/attest_envelope_vectors.json"
REPLAY_REL = "results/ccos/replay_trace_vectors.json"
KEY = b"abi-vector-key-0123456789abcdef"


def build_attest_vectors() -> dict:
    """cc_attest：信封（digest_only / hmac-sha256）+ 篡改主体 → 期望 ok/level。"""
    import base64 as _b64
    import hashlib as _h
    import hmac as _hmac

    subject = b"d/a.md"
    rows = []

    def _envelope(key):
        base = {"schema": "nf-attest/1",
                "subject": {"path": "d/a.md",
                            "sha256": _h.sha256(subject).hexdigest(),
                            "bytes": len(subject),
                            "line_count": len(subject.decode().splitlines())},
                "producer": "vectors", "issued_at": "2026-01-01T00:00:00Z"}
        body = json.dumps(base, sort_keys=True, ensure_ascii=False,
                          separators=(",", ":")).encode()
        env = dict(base)
        env["envelope_digest"] = _h.sha256(body).hexdigest()
        if key:
            env["signature"] = {"scheme": "hmac-sha256",
                                "mac": _hmac.new(key, env["envelope_digest"].encode(),
                                                 _h.sha256).hexdigest()}
        return env

    for cid, desc, key in (("digest_only", "digest_only 级信封", None),
                           ("hmac_ok", "hmac-sha256 级信封", KEY)):
        rows.append({"id": cid, "desc": desc,
                     "subject_b64": _b64.b64encode(subject).decode(),
                     "envelope": _envelope(key),
                     "key_b64": _b64.b64encode(key).decode() if key else "",
                     "expected": {"ok": True,
                                  "level": "hmac-sha256" if key else "digest_only"}})
    bad = _envelope(None)
    bad["subject"] = {**bad["subject"], "sha256": "0" * 64}
    rows.append({"id": "subject_flip", "desc": "主体摘要被改",
                 "subject_b64": _b64.b64encode(subject).decode(), "envelope": bad,
                 "key_b64": "", "expected": {"ok": False, "level": "none"}})
    return {"schema": SCHEMA, "count": len(rows), "vectors": rows}




DIFF_REL = "results/ccos/diff_delta_vectors.json"


def _json_pair(cid, desc, a, b):
    from core import contract_history
    sig_a = contract_history._json_signature("a.json", json.dumps(a))
    sig_b = contract_history._json_signature("b.json", json.dumps(b))
    delta = contract_history._json_diff(sig_a["shape"], sig_b["shape"])
    return {"id": cid, "desc": desc, "a": a, "b": b,
            "expected": {"impact": delta["impact"], "verdict": delta["verdict"],
                         "changes": [{"pointer": c["pointer"], "kind": c["kind"]}
                                     for c in delta["changes"]]}}


def build_diff_vectors() -> dict:
    base = {"schema": "demo/1", "version": "1", "items": {"a": 1, "b": "x"}}
    rows = [
        _json_pair("editorial", "只改值（同类型）", base,
                   {**base, "items": {"a": 2, "b": "x"}}),
        _json_pair("additive", "新增可选字段", base,
                   {**base, "items": {"a": 1, "b": "x", "c": "y"}}),
        _json_pair("bump_removed", "字段被移除", base,
                   {**base, "items": {"a": 1}}),
        _json_pair("bump_type", "类型变化（int → str）", base,
                   {**base, "items": {"a": "1", "b": "x"}}),
        _json_pair("bump_required_added", "必填项增加", base,
                   {**base, "items": {"a": 1, "b": "x", "required": ["a"]}}),
        _json_pair("bump_version", "版本字段变化", base,
                   {**base, "version": "2", "items": {"a": 1, "b": "x"}}),
    ]
    return {"schema": SCHEMA, "count": len(rows), "vectors": rows}




RESOLVE_REL = "results/ccos/resolve_contract_vectors.json"


def build_resolve_vectors() -> dict:
    """cc_resolve：夹具目录（受跟踪件清单 + 声明件）→ 期望认领契约集。"""
    files = ["d/a.md", "d/b.txt", "code/x.py", "code/sub/y.py", "docs/readme.md"]
    decl = {"schema": "nf-asset-contracts/1",
            "code": [{"id": "C1", "glob": "code/**/*.py"}],
            "data": [{"id": "D1", "path": "d/a.md"},
                     {"id": "D2", "glob": "d/*.md"}],
            "script": [], "index": [{"id": "I1", "glob": "docs/*.md"}]}
    rows = []
    for cid, desc, target, want in (
        ("claimed_code", "代码件被 C1 认领", "code/sub/y.py", ["C1"]),
        ("claimed_data", "数据件同时命中 D1 与 D2", "d/a.md", ["D1", "D2"]),
        ("unclaimed", "未被任何契约认领（closure_closed=false）", "d/b.txt", []),
        ("claimed_index", "文档被 I1 认领", "docs/readme.md", ["I1"]),
    ):
        rows.append({"id": cid, "desc": desc, "files": files, "decl": decl,
                     "object": target,
                     "expected": {"ids": want, "closure_closed": bool(want),
                                  "unclaimed": not want}})
    return {"schema": SCHEMA, "count": len(rows), "vectors": rows}


def build_replay_vectors() -> dict:
    import tempfile
    from pathlib import Path

    from core import evidence
    rows = []
    with tempfile.TemporaryDirectory(prefix="nf_replay_vec_") as tmp:
        root = Path(tmp) / "repo"
        (root / "d").mkdir(parents=True)
        # 字节写入：文本模式在 Windows 会把 \n 换成 \r\n，同输入跨平台字节不同（合并自 main）
        atomic_write.write_bytes(root / "d" / "a.md", b"# A\n")
        atomic_write.write_bytes(root / "d" / "b.md", b"# B\n")
        data, _info = evidence.build(str(root), ["d/a.md", "d/b.md"],
                                     created_at="2026-01-01T00:00:00Z")
        bundle = Path(tmp) / "b.zip"
        atomic_write.write_bytes(str(bundle), data)
        live = evidence.replay(str(bundle))
        rows.append({"id": "bundle_ok", "desc": "完好包的可重放轨迹",
                     "bundle_b64": base64.b64encode(data).decode(),
                     "expected": {"ok": live["ok"],
                                  "entries": len(live["entries"]),
                                  "root": live["recomputed_root"],
                                  "head": live["recomputed_head"]}})
    return {"schema": SCHEMA, "count": len(rows), "vectors": rows}


def write_all() -> dict:
    docs = {
        OUT_REL: build_vectors(),
        ATTEST_REL: build_attest_vectors(),
        REPLAY_REL: build_replay_vectors(),
        DIFF_REL: build_diff_vectors(),
        RESOLVE_REL: build_resolve_vectors(),
    }
    for rel, doc in docs.items():
        dest = ROOT / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        atomic_write.write_text(str(dest), render(doc))
        print(f"OK 已写入 {rel}（{doc['count']} 例）")
    return docs


def render(doc: dict) -> str:
    return json.dumps(doc, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def check_vectors() -> list:
    path = ROOT / OUT_REL
    live = build_vectors()
    if not path.is_file():
        return [f"缺向量集 {OUT_REL}（{GUIDE}跑 python scripts/abi_call_vectors.py --write）"]
    try:
        recorded = json_doc.loads(path.read_text(encoding="utf-8"), dict, what=OUT_REL)
    except (OSError, ValueError) as exc:
        return [f"{OUT_REL} 不可读：{exc}（{GUIDE}重跑 --write）"]
    if render(recorded) != render(live):
        return [f"{OUT_REL} 与重算不一致（{GUIDE}重跑 --write 后再提交）"]
    return []


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="abi_call_vectors", description="其余 ABI 调用向量集")
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args(argv)
    if args.write:
        write_all()
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
