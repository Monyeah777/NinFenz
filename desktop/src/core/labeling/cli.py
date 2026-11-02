"""nf-labelcheck 命令行：AI 生成合成内容标识合规体检器（原型）。

用法：
  nf-labelcheck check <file> [--json] [--pub <128hex>]
  nf-labelcheck sign <file> --meta meta.json --priv <hex> [--sidecar|--png-text]
  nf-labelcheck keygen [--out keys.json]
  nf-labelcheck selfcheck
  nf-labelcheck info

退出码：0 合规/仅警告；1 不合规；2 用法或环境错误。
"""

from __future__ import annotations

import argparse
import json
import os
import sys

from . import checker, metadata, security_data as sdmod, sm

VERSION = "0.1.0"


def _read_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def cmd_check(args):
    try:
        report = checker.check_file(args.file, pub_hex=args.pub,
                                    trust_store=args.trust_store)
    except FileNotFoundError:
        print(f"文件不存在：{args.file}", file=sys.stderr)
        return 2
    if args.evidence:
        os.makedirs(args.evidence, exist_ok=True)
        ev = checker.build_evidence(report, args.file)
        with open(os.path.join(args.evidence, "report.json"), "w",
                  encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        with open(os.path.join(args.evidence, "evidence.json"), "w",
                  encoding="utf-8") as f:
            json.dump(ev, f, ensure_ascii=False, indent=2)
        with open(os.path.join(args.evidence, "证据包.md"), "w",
                  encoding="utf-8") as f:
            f.write(checker.render_evidence_md(ev))
        print(f"证据包已写入 {args.evidence}/（report.json / "
              f"evidence.json / 证据包.md）")
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(checker.render_text(report))
    return report["exit_code"]


def cmd_keygen(args):
    keys = sm.sm2_keygen()
    out = {"alg": "SM2", "user_id": sm.DEFAULT_UID.decode(), **keys}
    text = json.dumps(out, ensure_ascii=False, indent=2)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(text + "\n")
        print(f"已写入 {args.out}（私钥请离线保管，勿提交）")
    else:
        print(text)
    return 0


def _dumps(obj, compact=False):
    """与 sidecar/文本块一致的序列化（稳定、可复算）。

    Markdown 的内嵌 JSON 走 compact：写入器会把多行压成单行，
    签名/验签必须用同一份字面串（TBS 切片按原始文本）。
    """
    if compact:
        return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
    return json.dumps(obj, ensure_ascii=False, indent=2)


def cmd_sign(args):
    meta = _read_json(args.meta)
    fields = {k: meta[k] for k in sdmod.FIELDS if k in meta}
    for key in ("Label", "ContentProducer", "ProduceID"):
        if key not in fields:
            print(f"meta 缺必需字段：{key}", file=sys.stderr)
            return 2
    container = metadata.sniff(args.file)
    try:
        cntsel, content = checker.select_content(args.file, container)
    except ValueError as exc:
        print(f"取内容字节失败：{exc}", file=sys.stderr)
        return 2
    # 先按「不含 ReservedCode1」的原文算 TBS（切片在 ProduceID 之后结束）
    compact = container == "markdown"
    raw = _dumps({"AIGC": fields}, compact)
    bindings = sdmod.build_bindings(content, cntsel)
    tsa_sign = None
    cert_der = None
    if args.tsa_key:
        if not args.tsa_cert:
            print("--tsa-key 需要同时给 --tsa-cert", file=sys.stderr)
            return 2
        from . import tsa, x509
        cert_der = x509.pem_to_der(open(args.tsa_cert, "rb").read())
        tsa_sign = lambda m: tsa.make_token(m, cert_der, args.tsa_key)  # noqa: E731
    sec = sdmod.build_security_data(raw, bindings, args.priv,
                                    tsa_sign=tsa_sign, cert_der=cert_der)
    fields["ReservedCode1"] = sec
    payload = {"AIGC": fields}
    text = _dumps(payload, compact)
    written = _write_into_container(args.file, container, text, args)
    if not written:
        path = metadata.write_sidecar(args.file, payload)
        print(f"已写入 sidecar：{path}")
        if container not in ("text",):
            print("注意：sidecar 是原型阶段的演示载体；正式发布应写入容器元数据",
                  file=sys.stderr)
    return 0


def _write_into_container(path, container, text, args):
    """按容器写入标识；成功返回 True，需要回退 sidecar 返回 False。"""
    if container == "png":
        metadata.inject_png_text(path, "AIGC", text)
        print(f"已写入 PNG 文本块（tEXt/iTXt）：{path}")
        return True
    try:
        if container == "jpeg":
            from . import writers_image_pdf as w
            w.inject_jpeg_xmp(path, text)
            print(f"已写入 JPEG APP1 XMP：{path}")
            return True
        if container == "pdf":
            from . import writers_image_pdf as w
            w.inject_pdf_info(path, text)
            print(f"已写入 PDF Info /AIGC（增量更新）：{path}")
            return True
        if container in ("xmind", "posm", "posf", "uof"):
            from . import writers_zipformats as w
            fn = {"xmind": w.inject_xmind, "posm": w.inject_posm,
                  "posf": w.inject_posf, "uof": w.inject_uof}[container]
            fn(path, text)
            print(f"已写入 {container} 标识载体：{path}")
            return True
        if container == "docx":
            from . import writers_docx_md as w
            w.inject_docx(path, text)
            print(f"已写入 DOCX docProps/custom.xml（name=AIGC）：{path}")
            return True
        if container == "ofd":
            from . import writers_ofd as w
            w.inject_ofd(path, text)
            print(f"已写入 OFD CustomDatas/AIGC.xml：{path}")
            return True
        if container == "markdown":
            from . import writers_docx_md as w
            w.inject_markdown(path, text)
            print(f"已写入 Markdown 头注释块：{path}")
            return True
        if container == "mp4":
            from . import writers_mp4 as w
            if hasattr(w, "inject_mp4_meta"):
                try:
                    w.inject_mp4_meta(path, text)
                    print(f"已写入 MP4 moov.udta.meta keys/ilst：{path}")
                    return True
                except Exception as exc:
                    print(f"标准位置写入不可用（{exc}），回退 XMP uuid",
                          file=sys.stderr)
            w.inject_mp4_xmp(path, text)
            print(f"已写入 MP4 XMP uuid（兼容载体）：{path}")
            return True
    except Exception as exc:  # 写入器未就绪/格式不支持 → 回退 sidecar
        print(f"容器写入不可用（{exc}），回退 sidecar", file=sys.stderr)
        return False
    return False


def cmd_verify(args):
    args.json = getattr(args, "json", False)
    report = checker.check_file(args.file, pub_hex=args.pub,
                                trust_store=args.trust_store)
    sec = report["sections"]["C"]
    ok = sec["status"] == "PASS"
    if args.json:
        print(json.dumps({"file": report["file"], "signature": sec},
                         ensure_ascii=False, indent=2))
    else:
        print(f"签名校验：{'PASS' if ok else 'FAIL'}")
        for it in sec["items"]:
            print(f"  - {it['id']} {it['status']}  {it['detail']}")
    return 0 if ok else 1


def cmd_selfcheck(args):
    ok = True
    print("== SM3 / SM2 自检 ==")
    for name, good, detail in sm.selfcheck():
        print(f"  {'PASS' if good else 'FAIL'}  {name} {detail}")
        ok &= good
    print("== 证书链 / 可信时间戳自检 ==")
    try:
        from . import tsa as _tsa
        from . import x509 as _x509
        ca_k = sm.sm2_keygen()
        ca = _x509.make_cert("SelfCheck CA", "SelfCheck CA", ca_k["public"],
                             ca_k["private"], serial=1, is_ca=True)
        leaf_k = sm.sm2_keygen()
        leaf = _x509.make_cert("SelfCheck Leaf", "SelfCheck CA",
                               leaf_k["public"], ca_k["private"], serial=2)
        ok_chain = _x509.build_chain(_x509.parse_cert(leaf),
                                     [_x509.parse_cert(leaf)],
                                     [_x509.parse_cert(ca)])[0]
        tok = _tsa.make_token(b"selfcheck", leaf, leaf_k["private"])
        ok_ts = _tsa.verify_token(tok, b"selfcheck",
                                  [_x509.parse_cert(ca)])[0]
        print(f"  {'PASS' if ok_chain else 'FAIL'}  证书链（CA→叶子）")
        print(f"  {'PASS' if ok_ts else 'FAIL'}  可信时间戳（v2）")
        ok &= ok_chain and ok_ts
    except Exception as exc:  # pragma: no cover
        print(f"  FAIL  {exc}")
        ok = False
    print("== 元数据模块自检 ==")
    try:
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            png = os.path.join(td, "a.png")
            metadata.make_png(png, {"Author": "nf"})
            print("  PASS  PNG 夹具/提取：" + str(metadata.sniff(png)))
            txt = os.path.join(td, "b.txt")
            with open(txt, "w", encoding="utf-8") as f:
                f.write("标题\n本内容由 AI 生成。\n结尾\n")
            print("  PASS  文本嗅探：" + metadata.sniff(txt))
    except Exception as exc:  # pragma: no cover
        print(f"  FAIL  {exc}")
        ok = False
    print("自检结果：" + ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


def cmd_info(args):
    print(f"nf-labelcheck {VERSION}（原型）")
    print("依据：GB 45438—2025；TC260-PG-202511A；《人工智能生成合成内容标识办法》")
    print("七字段（GB 45438 附录 E）：")
    for i, key in enumerate(sdmod.FIELDS, 1):
        print(f"  value{i} {key:18s} {sdmod.describe_field(key)}")
    print("算法：SM3 1.2.156.10197.1.401；SM3withSM2 1.2.156.10197.1.501")
    print("判定：A 显式 / B 隐式字段 / C 安全防护 / D 内容绑定 / E 备案材料")
    return 0


def build_parser():
    p = argparse.ArgumentParser(
        prog="nf-labelcheck",
        description="AI 生成合成内容标识合规体检器（本地、可复算）")
    p.add_argument("--version", action="version", version=f"nf-labelcheck {VERSION}")
    sub = p.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("check", help="体检一个文件")
    c.add_argument("file")
    c.add_argument("--json", action="store_true")
    c.add_argument("--pub", help="SM2 公钥（128 位十六进制）")
    c.add_argument("--trust-store", help="信任根 PEM/DER（验证书链与时间戳）")
    c.add_argument("--evidence", help="同时输出证据包到目录")
    c.set_defaults(func=cmd_check)

    s = sub.add_parser("sign", help="生成并写入安全防护信息（原型）")
    s.add_argument("file")
    s.add_argument("--meta", required=True, help="七字段 JSON 文件")
    s.add_argument("--priv", required=True, help="SM2 私钥（64 位十六进制）")
    s.add_argument("--cntsel", choices=["PNG", "JPEG", "OTHER"])
    s.add_argument("--sidecar", action="store_true", default=True)
    s.add_argument("--png-text", action="store_true", help="写入 PNG tEXt 块")
    s.add_argument("--tsa-cert", help="TSA 签名证书（PEM/DER），附时间戳用")
    s.add_argument("--tsa-key", help="TSA 签名私钥（64 hex），附时间戳用")
    s.set_defaults(func=cmd_sign)

    v = sub.add_parser("verify", help="只验签名")
    v.add_argument("file")
    v.add_argument("--pub")
    v.add_argument("--trust-store")
    v.add_argument("--json", action="store_true")
    v.set_defaults(func=cmd_verify)

    k = sub.add_parser("keygen", help="生成 SM2 密钥对")
    k.add_argument("--out")
    k.set_defaults(func=cmd_keygen)

    sub.add_parser("selfcheck", help="SM3/SM2 与模块自检").set_defaults(func=cmd_selfcheck)
    sub.add_parser("info", help="规格说明").set_defaults(func=cmd_info)
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
