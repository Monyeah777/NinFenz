#!/usr/bin/env python3
"""CCOS 一条链复现（cc_check → cc_attest → cc_verify → cc_replay）。

为什么（Go/No-Go 判据）：方案要求「一条链可复现」。可复现的硬判据不是「四个命令都返回 0」，
而是**同一个对象字节的摘要必须逐个流下去**：体检里算出的 sha256、信封里的 subject.sha256、
证据包里的成员 digest、复现轨迹第一步的 output，必须**完全相同**。任何一环换了字节，
链条就在那里断——那时四个命令仍可能各自返回 0，但「同一条链」已经不成立。

缺环如实标注：cc_label 环节本仓不存在（labeling 子系统缺位，2026-11-04 实测），
故链从 cc_check 起，输出里显式写 missing 字段——不假装七环齐全。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "desktop", "src"))

from core import attest, check_policy, evidence  # noqa: E402

CHAIN_SCHEMA = "nf-ccos-chain/1"
#: 链上缺的环（本仓无 labeling 子系统；不得凭空补）
MISSING = ("cc_label",)


def _policy() -> dict:
    """链条自带的体检策略：只做与字节强相关的最小判定（UTF-8 + 非空）。"""
    return {"schema": check_policy.SCHEMA, "id": "ccos-chain-demo",
            "rules": [
                {"id": "utf8", "kind": "utf8", "severity": "fail",
                 "fix": "把对象转成 UTF-8 文本再进链"},
                {"id": "non-empty", "kind": "count_at_least", "field": "bytes", "n": 1,
                 "severity": "fail", "fix": "空对象没有可复现的内容，先补内容"},
            ]}


def run(root: str, target: str, key: bytes | None = None) -> dict:
    """跑四个环节 → {schema, target, links, digests, missing, ok}。"""
    rel = str(target).replace("\\", "/").lstrip("/")
    abs_path = os.path.join(root, rel) if not os.path.isabs(rel) else rel
    links: list[dict] = []
    digests: dict[str, str] = {}

    res = check_policy.check(abs_path, _policy())
    digests["check"] = res["object"]["sha256"]
    links.append({"link": "cc_check", "verdict": res["verdict"],
                  "digest": digests["check"], "ok": res["verdict"] == "ok",
                  "detail": f"policy={res['policy_id']} digest={res['policy_digest'][:16]}"})

    env = attest.build(rel, root, issuer="ccos-chain")
    if key:
        env = attest.sign_hmac(env, key)
    digests["attest"] = str((env.get("subject") or {}).get("sha256") or "")
    ok, issues, level = attest.verify(env, root, key=key)
    links.append({"link": "cc_attest", "verdict": "ok" if ok else "invalid",
                  "digest": digests["attest"], "ok": ok and digests["attest"] == digests["check"],
                  "detail": f"level={level}" + ("" if ok else "；" + "；".join(issues[:2]))})

    data, info = evidence.build(root, [rel], issuer="ccos-chain", key=key)
    with tempfile.TemporaryDirectory(prefix="nf_ccos_chain_") as tmp_dir:
        bundle = os.path.join(tmp_dir, "chain.zip")
        with open(bundle, "wb") as fh:
            fh.write(data)
        with zipfile.ZipFile(bundle) as zf:
            meta = json.loads(zf.read("bundle.json").decode())
        member = str(((meta.get("entries") or [{}])[0]).get("digest") or "")
        vres = evidence.verify(bundle, key=key)
        links.append({"link": "cc_verify", "verdict": vres["verdict"], "digest": member,
                      "ok": vres["verdict"] == "ok" and member == digests["check"],
                      "detail": f"level={vres['level']} root={info['root'][:16]}"})
        digests["verify"] = member

        rres = evidence.replay(bundle, key=key)
    steps = (rres.get("entries") or [{}])[0].get("steps") or []
    digests["replay"] = str(steps[0].get("output") or "") if steps else ""
    links.append({"link": "cc_replay", "verdict": "ok" if rres["ok"] else "invalid",
                  "digest": digests["replay"],
                  "ok": rres["ok"] and digests["replay"] == digests["check"],
                  "detail": f"steps={len(steps)} recomputed_root="
                            f"{str(rres.get('recomputed_root') or '')[:16]}"})

    same = all(digests.values()) and len({d for d in digests.values() if d}) == 1
    return {"schema": CHAIN_SCHEMA, "target": rel, "links": links,
            "digests": digests, "missing": list(MISSING), "digests_agree": same,
            "ok": same and all(link["ok"] for link in links)}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="ccos_chain", description="CCOS 一条链复现（cc_check→cc_attest→cc_verify→cc_replay）")
    ap.add_argument("--root", default=ROOT, help="仓库根（缺省 = 本脚本所在仓）")
    ap.add_argument("--target", default="STRATEGY.md", help="链上对象（仓库相对路径）")
    ap.add_argument("--key-file", default="", help="可选：给信封加 hmac-sha256 级")
    ap.add_argument("--json", action="store_true", help="输出结构化 JSON")
    args = ap.parse_args(argv)

    key = None
    if args.key_file:
        with open(args.key_file, "rb") as fh:
            key = fh.read().strip() or None
    try:
        res = run(args.root, args.target, key=key)
    except (OSError, ValueError) as exc:
        print(f"✗ 链条跑不通：{exc}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(res, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(f"== CCOS 一条链（{res['target']}）==")
        for link in res["links"]:
            mark = "✓" if link["ok"] else "✗"
            print(f"  {mark} {link['link']:<12} {link['digest'][:16]}  {link['detail']}")
        print(f"  缺环（如实标注）：{', '.join(res['missing']) or '无'}")
        print(f"  摘要逐个流下去：{'是' if res['digests_agree'] else '否'}")
        print(f"  => {'一条链可复现' if res['ok'] else '链条断了（见上）'}")
    return 0 if res["ok"] else 1


if __name__ == "__main__":
    for _stream in (sys.stdout, sys.stderr):
        if hasattr(_stream, "reconfigure"):
            _stream.reconfigure(encoding="utf-8")
    sys.exit(main())
