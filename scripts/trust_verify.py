#!/usr/bin/env python3
"""离线验证入口（cc_verify 骨架的 CI 面；计划 §8.4）。

用法::

    python scripts/trust_verify.py --bundle B.json --policy P.json [--json] [--out nf-verify.json]
    python scripts/trust_verify.py --envelope E.json --keyid ID \
        --hmac-key-hex HEX  # DSSE 信封（hmac-sha256）

退出码：0 = 达到策略；1 = 验证失败（bundle 自洽性/结构失败）；2 = 不可判定（缺锚/参数/策略）。
边界：T0 可全离线；T1 需签名、T2 需 RFC 3161、T3 需 witness、T4 需公共锚——这些核验在 G2/G4
接线，本入口如实把它们标成缺项并 exit 2，不冒充等级、不写「合规」。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import atomic_write, json_doc  # noqa: E402
from core.trust import dsse  # noqa: E402
from core.trust import keys as tk  # noqa: E402
from core.trust import verify as tv  # noqa: E402


def _load(path: str, what: str) -> dict:
    target = Path(path)
    if not target.is_file():
        raise ValueError(f"缺 {what}：{path}（修复指引：传存在的 JSON 文件路径）")
    return json_doc.load(target, dict, what=what)


def _summary(report: dict) -> str:
    lines = [
        f"subject: {report['subject']['kind']} {report['subject']['digest'][:16]}",
        f"level: required={report['level']['required']} achieved={report['level']['achieved']}",
    ]
    for check in report["checks"]:
        lines.append(f"check {check['id']}: {'ok' if check['ok'] else 'FAIL'} — {check['detail']}")
    for issue in report["issues"]:
        lines.append(f"issue {issue['code']}: {issue['message']}")
        lines.append(f"  fix: {issue['fix']}")
    return "\n".join(lines) + "\n"


def _verify_envelope(args) -> int:
    """信封模式：裸 hmac（--keyid/--hmac-key-hex）或注册表口径（--issuer-registry）。"""
    try:
        envelope = json_doc.load(Path(args.envelope), dict, what="DSSE 信封")
    except (OSError, ValueError) as exc:
        print(f"不可判定：{exc}", file=sys.stderr)
        return tv.EXIT_UNDECIDABLE
    if args.issuer_registry:
        if not args.key_material or not args.now:
            print("不可判定：注册表模式需要 --key-material 与 --now（UTC 秒级）",
                  file=sys.stderr)
            return tv.EXIT_UNDECIDABLE
        try:
            registry = tk.load_registry(args.issuer_registry)
            material = json_doc.load(Path(args.key_material), dict, what="key material")
            result = tk.verify_envelope(envelope, registry, material,
                                        dsse.load_schema(args.root), now=args.now)
        except (OSError, ValueError) as exc:
            print(f"不可判定：{exc}", file=sys.stderr)
            return tv.EXIT_UNDECIDABLE
        if result["valid"]:
            print(f"valid envelope: payloadType={result['payload_type']} "
                  f"signers={','.join(result['signers'])} "
                  f"issuers={','.join(sorted(set(result['issuers'].values())))}")
            return 0
        print(f"invalid envelope: {result['reason']}")
        return 1
    if not args.keyid or not args.hmac_key_hex:
        print("不可判定：信封模式需要 --keyid 与 --hmac-key-hex（或 --issuer-registry）",
              file=sys.stderr)
        return tv.EXIT_UNDECIDABLE
    try:
        key = bytes.fromhex(args.hmac_key_hex)
        keys = {args.keyid: {"alg": "hmac-sha256", "verify": dsse.hmac_verifier(key)}}
        result = dsse.verify_envelope(envelope, keys, dsse.load_schema(args.root))
    except (OSError, ValueError) as exc:
        print(f"不可判定：{exc}", file=sys.stderr)
        return tv.EXIT_UNDECIDABLE
    if result["valid"]:
        print(f"valid envelope: payloadType={result['payload_type']} "
              f"signers={','.join(result['signers'])}")
        return 0
    print(f"invalid envelope: {result['reason']}")
    return 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="离线验证 claim bundle / DSSE 信封")
    ap.add_argument("--bundle", default="", help="nf-claim-bundle/1 JSON")
    ap.add_argument("--policy", default="", help="nf-trust-policy/1 JSON")
    ap.add_argument("--envelope", default="", help="nf-dsse/1 信封 JSON（信封模式）")
    ap.add_argument("--keyid", default="", help="信封模式的 keyid")
    ap.add_argument("--hmac-key-hex", default="", help="信封模式的 HMAC key（hex）")
    ap.add_argument("--issuer-registry", default="", help="注册表口径：nf-issuer-registry/1 JSON")
    ap.add_argument("--key-material", default="", help="注册表口径的 key 材料（keyid → {hex}）")
    ap.add_argument("--now", default="",
                    help="注册表口径的判定时刻（UTC 秒级，必填；不隐式取墙钟）")
    ap.add_argument("--root", default=str(ROOT), help="仓库根（读冻结 schema 用）")
    ap.add_argument("--json", action="store_true", help="输出 nf-verify/1 报告 JSON")
    ap.add_argument("--out", default="", help="把报告写入文件（原子写）")
    args = ap.parse_args(argv)
    if args.envelope:
        return _verify_envelope(args)
    if not args.bundle or not args.policy:
        print("不可判定：需要 --bundle + --policy，或 --envelope 信封模式", file=sys.stderr)
        return tv.EXIT_UNDECIDABLE
    try:
        bundle = _load(args.bundle, "bundle")
        policy = _load(args.policy, "policy")
        result = tv.verify(bundle, policy, root=args.root)
    except (OSError, ValueError) as exc:
        print(f"不可判定：{exc}", file=sys.stderr)
        return tv.EXIT_UNDECIDABLE
    report = result["report"]
    text = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.out:
        atomic_write.write_text(Path(args.out), text)
    if args.json:
        sys.stdout.write(text)
    else:
        sys.stdout.write(_summary(report))
    return result["exit_code"]


if __name__ == "__main__":
    sys.exit(main())
