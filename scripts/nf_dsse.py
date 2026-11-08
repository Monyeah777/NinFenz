#!/usr/bin/env python3
"""CLI adapter for DSSE v1 envelopes; cryptographic rules live in core.dsse."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path


def add_parser(sub):
    """Register `nf dsse sign|verify` on the shared parser."""
    dss = sub.add_parser(
        "dsse",
        help="DSSE v1 签名信封：签名 / 验签",
        description="DSSE v1.0.2 JSON Envelope：严格 PAE、标准/URL-safe Base64、"
                    "HMAC-SHA256 多签名与唯一密钥阈值验证。",
    )
    dsub = dss.add_subparsers(dest="dsse_cmd", required=True)
    sign = dsub.add_parser(
        "sign",
        help="为任意 payload 生成 DSSE 信封",
        description="读取原始 payload bytes 后，对 PAE(payloadType,payload) 签名。",
    )
    sign.add_argument("--payload", required=True, help="原始 payload 文件")
    sign.add_argument("--payload-type", required=True,
                      help="MIME type 或 URI（如 application/vnd.in-toto+json）")
    sign.add_argument("--key-file", required=True, help="HMAC-SHA256 密钥文件")
    sign.add_argument("--keyid", default="",
                      help="可选 keyid（缺省取密钥 SHA-256 前 16 位）")
    sign.add_argument("--out", default="", help="信封输出文件（缺省打印到 stdout）")
    verify = dsub.add_parser(
        "verify",
        help="验签并取回原始 payload bytes",
        description="先验 DSSE 签名，再按 payloadType 白名单放行。",
    )
    verify.add_argument("--envelope", required=True, help="DSSE JSON Envelope")
    verify.add_argument("--key-file", required=True, help="受信 HMAC-SHA256 密钥文件")
    verify.add_argument("--keyid", default="", help="密钥标识（缺省由密钥内容派生）")
    verify.add_argument("--payload-type", default="", help="要求精确匹配的 payloadType")
    verify.add_argument("--threshold", type=int, default=1,
                        help="需要通过的唯一受信密钥数（缺省 1）")
    verify.add_argument("--out", default="", help="把验签后的原始 payload 写入该文件")
    verify.add_argument("--json", action="store_true", help="输出结构化结果")


def _read_bytes(path: str, label: str) -> bytes:
    from core import trust_boundary

    p = Path(path)
    if not p.is_file():
        raise ValueError(f"{label}不存在：{p}（修复指引：给出在场文件路径）")
    size = p.stat().st_size
    if size > trust_boundary.MAX_IMPORT_BYTES:
        raise ValueError(
            f"{label}过大：{size} > {trust_boundary.MAX_IMPORT_BYTES} bytes"
            "（修复指引：先裁剪或分片）")
    return p.read_bytes()


def run(args) -> int:
    """Execute a parsed DSSE command."""
    from core import atomic_write, attest, dsse

    try:
        key = attest.read_key_file(args.key_file)
        keyid = args.keyid or hashlib.sha256(key).hexdigest()[:16]
        if args.dsse_cmd == "sign":
            payload = _read_bytes(args.payload, "payload")
            envelope = dsse.sign(args.payload_type, payload, key, keyid)
            blob = dsse.dumps(envelope).encode("utf-8")
            if args.out:
                atomic_write.write_bytes(args.out, blob)
                print(f"  ✓ DSSE 信封已写入：{args.out}（{len(blob)} bytes，keyid={keyid}）")
            else:
                sys.stdout.buffer.write(blob)
                sys.stdout.buffer.flush()
            return 0
        raw = _read_bytes(args.envelope, "DSSE envelope")
        verified = dsse.verify_json(
            raw, {keyid: key}, threshold=args.threshold,
            accepted_payload_types={args.payload_type} if args.payload_type else None)
        if args.out:
            atomic_write.write_bytes(args.out, verified.payload)
        result = {
            "kind": "dsse-verify", "schema": "dsse-envelope/1", "ok": True,
            "algorithm": dsse.HMAC_SHA256,
            "payloadType": verified.payload_type,
            "accepted_keyids": list(verified.accepted_keyids),
            "threshold": args.threshold,
            "payload_sha256": hashlib.sha256(verified.payload).hexdigest(),
            "payload_bytes": len(verified.payload),
            "out": args.out or None,
        }
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
        else:
            print(f"  ✓ DSSE 验签通过：{verified.payload_type} · "
                  f"keyid={','.join(verified.accepted_keyids)} · "
                  f"payload={len(verified.payload)} bytes · sha256={result['payload_sha256']}")
            if args.out:
                print(f"  ✓ 已原样写出被认证 payload：{args.out}")
        return 0
    except (OSError, ValueError) as exc:
        message = f"DSSE 失败：{exc}"
        if getattr(args, "json", False):
            print(json.dumps(
                {"kind": "dsse-verify", "schema": "dsse-envelope/1",
                 "ok": False, "error": message},
                ensure_ascii=False, indent=2, sort_keys=True), file=sys.stderr)
        else:
            print(f"  ✗ {message}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")
