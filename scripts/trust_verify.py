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
import hmac
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import atomic_write, json_doc  # noqa: E402
from core.trust import anchor as ta  # noqa: E402
from core.trust import context_lineage as tcl  # noqa: E402
from core.trust import dsse  # noqa: E402
from core.trust import entity as te  # noqa: E402
from core.trust import human_review as hrev  # noqa: E402
from core.trust import keys as tk  # noqa: E402
from core.trust import model_card as tmc  # noqa: E402
from core.trust import trust_store as tstore  # noqa: E402
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


def _hmac_map(path: str) -> dict:
    """{id: hex} → {id: callable(message_digest_str, sig_bytes)}（stdlib hmac）。"""
    raw = json_doc.load(Path(path), dict, what="hmac material")
    out = {}
    for keyid, hex_text in raw.items():
        key = bytes.fromhex(str(hex_text))

        def check(message, signature, _key=key):
            return hmac.compare_digest(dsse.hmac_sign(_key, message.encode()), signature)

        out[str(keyid)] = check
    return out


def _anchor_verifiers(args) -> dict:
    """按 CLI 提供的材料构造锚 verifier（没给的材料就没有对应 verifier=记 none）。"""
    verifiers = {}
    if args.tsa_query and args.tsa_ca:
        verifiers["rfc3161"] = ta.make_timestamp_verifier(
            args.tsa_query, args.tsa_ca, subject_path=args.tsa_subject)
    if args.git_repo:
        verifiers["git-commit"] = ta.make_git_commit_verifier(args.git_repo)
    if args.witness_material:
        verifiers["witness"] = ta.make_witness_verifier(_hmac_map(args.witness_material))
    if args.sth_material:
        verifiers["transparency-sth"] = ta.make_sth_verifier(_hmac_map(args.sth_material))
    return verifiers


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
    ap.add_argument("--entities", default="", help="类型化实体 JSON 数组（组合/准入模式）")
    ap.add_argument("--type-registry", default="", help="nf-type-registry/1 类型注册表")
    ap.add_argument("--model-card", default="", help="nf-model-card/1 模型卡（可选）")
    ap.add_argument("--current-card", default="", help="当前模型卡（用于检测模型替换/评测变更）")
    ap.add_argument("--ai-evidence", default="", help="AI 证据实体 JSON（绑定模式）")
    ap.add_argument("--context-lineage", default="",
                    help="nf-context-lineage/1 上下文血缘（与 --ai-evidence 合用）")
    ap.add_argument("--lineage", default="",
                    help="只校验 context lineage（可配 --model-card 绑定）")
    ap.add_argument("--lineage-build", default="", help="构建模式：输出 lineage 文件路径")
    ap.add_argument("--contexts", default="", help="构建模式输入：[{role, content_b64}] JSON")
    ap.add_argument("--human-review", default="", help="人类复核记录信封（nf-dsse/1）")
    ap.add_argument("--review-gate", action="store_true",
                    help="复核闸门：无记录时显式 PENDING exit2")
    ap.add_argument("--subject-kind", default="bundle",
                    help="复核绑定的对象类别")
    ap.add_argument("--subject-digest", default="", help="复核绑定的对象摘要")
    ap.add_argument("--trust-store", action="store_true",
                    help="校验 policy × issuer registry × type registry 一致性")
    ap.add_argument("--root", default=str(ROOT), help="仓库根（读冻结 schema 用）")
    ap.add_argument("--json", action="store_true", help="输出 nf-verify/1 报告 JSON")
    ap.add_argument("--out", default="", help="把报告写入文件（原子写）")
    ap.add_argument("--anchor", default="", help="nf-anchor/1 锚件（可选；给了才核 T2 事实）")
    ap.add_argument("--head-signature", default="", help="链头签名信封（nf-dsse/1，可选）")
    ap.add_argument("--anchor-build", default="", help="构建模式：输出 nf-anchor/1 文件路径")
    ap.add_argument("--anchor-target", default="", help="构建模式的 target_digest")
    ap.add_argument("--anchor-anchors", default="", help="构建模式的 anchors JSON 数组文件")
    ap.add_argument("--auto-anchor", default="",
                    help="一键编排：输出锚件路径（可先验链头）+ 组件文件")
    ap.add_argument("--anchor-components", default="",
                    help="一键编排的组件（nf-anchor/1 的 anchors 列表或对象）")
    ap.add_argument("--tsa-query", default="", help="RFC3161 verifier 的查询文件")
    ap.add_argument("--tsa-ca", default="", help="RFC3161 verifier 的 TSA 根/中间证书 PEM")
    ap.add_argument("--tsa-subject", default="", help="被时间戳盖章的数据文件（可选绑定校验）")
    ap.add_argument("--git-repo", default="", help="git-commit 锚 verifier 的仓库路径")
    ap.add_argument("--witness-material", default="", help="witness hmac 材料 {id: hex}")
    ap.add_argument("--sth-material", default="", help="STH hmac 材料 {log_id: hex}")
    args = ap.parse_args(argv)
    if args.trust_store:
        if not args.policy or not args.issuer_registry or not args.type_registry:
            print("不可判定：--trust-store 需要 --policy/--issuer-registry/--type-registry",
                  file=sys.stderr)
            return tv.EXIT_UNDECIDABLE
        try:
            policy_doc = _load(args.policy, "policy")
            issuer_registry = tk.load_registry(args.issuer_registry)
            type_registry = te.load_type_registry(args.type_registry)
            store = tstore.build_store(policy_doc, issuer_registry, type_registry)
        except (OSError, ValueError) as exc:
            print(f"invalid trust store: {exc}")
            return tv.EXIT_INVALID
        print(f"valid trust store: issuers={len(store['issuers'])} "
              f"keyids={len(store['keyids'])} types={len(store['types'])}")
        return 0
    if args.review_gate or args.human_review:
        if not args.human_review:
            print("human review state: PENDING（未提供记录；PENDING 不等于通过）")
            return tv.EXIT_UNDECIDABLE
        if not args.subject_digest:
            print("不可判定：复核模式需要 --subject-digest", file=sys.stderr)
            return tv.EXIT_UNDECIDABLE
        if not args.issuer_registry or not args.key_material or not args.now:
            print("不可判定：复核模式需要 --issuer-registry/--key-material/--now",
                  file=sys.stderr)
            return tv.EXIT_UNDECIDABLE
        try:
            envelope = _load(args.human_review, "human review")
            registry_doc = tk.load_registry(args.issuer_registry)
            material_doc = json_doc.load(Path(args.key_material), dict, what="key material")
        except (OSError, ValueError) as exc:
            print(f"不可判定：{exc}", file=sys.stderr)
            return tv.EXIT_UNDECIDABLE
        result = hrev.verify_review(envelope, args.subject_kind, args.subject_digest,
                                    registry_doc, material_doc, now=args.now,
                                    root=args.root)
        state = hrev.review_state(result)
        print(f"human review state: {state}"
              + (f"（{result.get('reason')}）" if result.get("reason") else ""))
        if state == hrev.STATE_APPROVED:
            return 0
        return 1
    if args.lineage_build:
        if not args.model_card or not args.contexts:
            print("不可判定：--lineage-build 需要 --model-card 与 --contexts", file=sys.stderr)
            return tv.EXIT_UNDECIDABLE
        try:
            card = tmc.load_card(args.model_card)
            raw = json_doc.load(Path(args.contexts), list, what="contexts")
            import base64
            contents = [(str(item["role"]), base64.b64decode(str(item["content_b64"])))
                        for item in raw]
            doc = tcl.build_lineage(tmc.identity_digest(card), contents)
            atomic_write.write_text(Path(args.lineage_build),
                                    json.dumps(doc, ensure_ascii=False, indent=2) + "\n")
        except (KeyError, OSError, ValueError) as exc:
            print(f"不可判定：{exc}", file=sys.stderr)
            return tv.EXIT_UNDECIDABLE
        print(f"lineage built: head={doc['head'][:16]} segments={len(doc['segments'])}")
        return 0
    if args.lineage:
        try:
            lineage = tcl.load_lineage(args.lineage)
            card = tmc.load_card(args.model_card) if args.model_card else None
            result = tcl.verify_lineage(lineage, card, root=args.root)
        except (OSError, ValueError) as exc:
            print(f"不可判定：{exc}", file=sys.stderr)
            return tv.EXIT_UNDECIDABLE
        if result.get("ok"):
            print(f"valid context lineage: head={result['head']}")
            return 0
        print(f"invalid context lineage: {result['issues'][0]['code']}")
        return 1
    if args.ai_evidence:
        if not args.model_card:
            print("不可判定：--ai-evidence 模式需要 --model-card", file=sys.stderr)
            return tv.EXIT_UNDECIDABLE
        try:
            evidence = _load(args.ai_evidence, "ai evidence")
            bound = tmc.load_card(args.model_card)
            current = tmc.load_card(args.current_card) if args.current_card else None
            schema = tmc.load_schema(args.root)
        except (OSError, ValueError) as exc:
            print(f"不可判定：{exc}", file=sys.stderr)
            return tv.EXIT_UNDECIDABLE
        if args.context_lineage:
            lineage = tcl.load_lineage(args.context_lineage)
            result = tcl.check_context_binding(evidence, bound, lineage, root=args.root)
            label = "model-card + context-lineage"
        else:
            result = tmc.check_binding(evidence, bound, current, schema)
            label = "model-card"
        if result.get("ok"):
            extra = f" lineage={result.get('lineage_digest', '')[:16]}"
            primary = result.get("bound_digest") or result.get("card_digest")
            warning = f"（warning: {result['warning']}）" if result.get("warning") else ""
            print(f"valid {label} binding: {primary}" + extra + warning)
            return 0
        print(f"invalid {label} binding: {result.get('reason')}")
        return 1
    if args.entities:
        if not args.type_registry or not args.policy or not args.issuer_registry:
            print("不可判定：--entities 模式需要 --type-registry/--policy/--issuer-registry",
                  file=sys.stderr)
            return tv.EXIT_UNDECIDABLE
        try:
            entities = json_doc.load(Path(args.entities), list, what="entities")
            type_registry = te.load_type_registry(args.type_registry)
            policy_doc = _load(args.policy, "policy")
            issuer_registry = tk.load_registry(args.issuer_registry)
            entity_schema = te.load_schema(args.root)
            type_schema = te.load_type_schema(args.root)
            issues = []
            for index, entity in enumerate(entities):
                result = te.typed_admissibility(entity, type_registry, policy_doc,
                                                issuer_registry, entity_schema,
                                                type_schema)
                if not result.get("admissible"):
                    issues.append(f"entities[{index}]: {result.get('reason')}")
            composed = te.composition_check(entities, type_registry, type_schema,
                                            root=args.root)
            issues.extend(f"{i['code']}: {i['message']}" for i in composed["issues"])
        except (OSError, ValueError) as exc:
            print(f"不可判定：{exc}", file=sys.stderr)
            return tv.EXIT_UNDECIDABLE
        for issue in issues:
            print(f"invalid: {issue}")
        if not issues:
            print(f"valid typed entities: {len(entities)}（准入 + 组合均通过）")
        return 0 if not issues else 1
    if args.auto_anchor:
        if not args.subject_digest or not args.anchor_components:
            print("不可判定：--auto-anchor 需要 --subject-digest 与 --anchor-components",
                  file=sys.stderr)
            return tv.EXIT_UNDECIDABLE
        try:
            raw = json_doc.load(Path(args.anchor_components),
                                (dict, list), what="anchor components")
            head = _load(args.head_signature, "head signature") if args.head_signature else None
            registry_doc = tk.load_registry(args.issuer_registry) if args.issuer_registry else None
            material_doc = (json_doc.load(Path(args.key_material), dict, what="key material")
                            if args.key_material else None)
            doc = ta.auto_anchor(args.subject_digest, raw, root=args.root, head=head,
                                 registry=registry_doc, material=material_doc,
                                 now=args.now or None)
            atomic_write.write_text(Path(args.auto_anchor),
                                    json.dumps(doc, ensure_ascii=False, indent=2) + "\n")
        except (OSError, ValueError) as exc:
            print(f"不可判定：{exc}", file=sys.stderr)
            return tv.EXIT_UNDECIDABLE
        print(f"auto anchor built: target={args.subject_digest} anchors={len(doc['anchors'])}")
        return 0
    if args.anchor_build:
        anchors = json_doc.load(Path(args.anchor_anchors), list, what="anchors") \
            if args.anchor_anchors else []
        try:
            doc = ta.build_anchor_set(args.anchor_target, anchors)
            atomic_write.write_text(Path(args.anchor_build),
                                    json.dumps(doc, ensure_ascii=False, indent=2) + "\n")
        except (OSError, ValueError) as exc:
            print(f"不可判定：{exc}", file=sys.stderr)
            return tv.EXIT_UNDECIDABLE
        print(f"anchor built: target={args.anchor_target} anchors={len(anchors)}")
        return 0
    if args.envelope:
        return _verify_envelope(args)
    if not args.bundle or not args.policy:
        print("不可判定：需要 --bundle + --policy，或 --envelope 信封模式", file=sys.stderr)
        return tv.EXIT_UNDECIDABLE
    try:
        bundle = _load(args.bundle, "bundle")
        policy = _load(args.policy, "policy")
        anchor_doc = _load(args.anchor, "anchor") if args.anchor else None
        head = _load(args.head_signature, "head signature") if args.head_signature else None
        registry_doc = tk.load_registry(args.issuer_registry) if args.issuer_registry else None
        material_doc = (json_doc.load(Path(args.key_material), dict, what="key material")
                        if args.key_material else None)
        result = tv.verify(bundle, policy, root=args.root, anchor=anchor_doc,
                           anchor_verifiers=_anchor_verifiers(args) if anchor_doc else None,
                           head_signature=head, registry=registry_doc,
                           material=material_doc, now=args.now or None)
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
