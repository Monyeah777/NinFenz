"""证据包（evidence bundle）——cc_verify 的自包含证据容器。

内部差距（2026-11-04 实证）：三件证据件其实都在——attest 给可验证信封（三级信任）、
receipts 给单根 + inclusion proof、transparency 给哈希链——但**没有一件是「给外部人
一个文件就能验」的形态**：对方要拿到整个仓库、要知道仓库相对路径、要复现 nf 的算法。
「第三方复验」于是不成立，只剩「你自己跑一遍」。（nf verify 是门禁，不是证据校验。）

本模块只做**容器与判定顺序**，密码学一律复用既有实现，不自造：
- 叶 / 内部节点 / 梅克尔根：core.receipts（RFC 6962 域分隔，见该文件 leaf_hash / node_hash）
- 信封与签名：core.attest（digest_only / hmac-sha256 / sigstore-keyless，缺锚拒绝）
- 透明日志链：域分隔前缀取自 core.transparency_log（单一真源，不在本文件复写常量）

判定词表固定为 ok / revoked / expired / invalid——这是 ABI 的稳定面
（docs/ccos/abi-v0.md §4），新增形容词等于改所有验证方。

纪律（对齐 core 零第三方依赖红线）：stdlib-only；**纯读**（校验路径不落盘、不改仓库；
唯一例外是校验期把 payload 解到进程私有临时目录，出作用域即销毁）。
"""

# ruff: noqa: F401 — 门面按原模块面重新导出（re-export 是职责，不是未使用），实现在私有子包。
from __future__ import annotations

# ruff: noqa: F401 — 门面按原模块面重新导出（re-export 是职责，不是未使用）
import io
import os
import tempfile
import warnings
import zipfile
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

# 依赖面：实现在 _evidence 子包；本行履约原模块对 core 的 import 边（勿删）。
from core import atomic_write, attest, json_doc, receipts, timestamp
from core import revocations as revoc

# 实现分片：原模块逻辑在私有子包 _evidence/，本门面按原模块面显式再导出（API 不变）。
from core._evidence._part1 import (
    _bench_run,
    _bench_write,
    _BenchOptions,
    _bump_mac,
    _bump_subject,
    _drop_entry,
    _empty_head,
    _flip_proof,
    _members,
    _mut_attest,
    _mut_meta,
    _rebuild,
    _swap_entries,
    _truncate_proof,
    _zip_unsorted,
    write,
)
from core._evidence._part2 import bench_markdown
from core.transparency_log import NODE_PREFIX

from ._evidence._batch import (
    BatchVerifyOptions,
    _verify_single_json,
    batch_paths,
    verify_any,
    verify_batch,
)
from ._evidence._build import (
    BuildOptions,
    _decision_target,
    _envelope,
    _manifest,
    _read_text,
    _targets,
    _zip_bytes,
    build,
    default_out,
)
from ._evidence._const import (
    _ZIP_EPOCH,
    ATTEST_DIR,
    ATTEST_SCHEMA,
    ATTEST_SET_SCHEMA,
    BATCH_MAX_FILES,
    BENCH_KEY,
    BENCH_PIN,
    BENCH_SCHEMA,
    BUNDLE_ENTRY,
    EXIT_CODES,
    GUIDE,
    KINDS,
    LEVELS,
    MAX_MEMBER_BYTES,
    MAX_TOTAL_BYTES,
    PAYLOAD_DIR,
    RECEIPTS_SCHEMA,
    REPLAY_SCHEMA,
    REVOCATION_SCHEMA,
    REVOCATIONS_ENTRY,
    SCHEMA,
)
from ._evidence._freshness import (
    _apply_expiry,
    _apply_freshness,
    _apply_time_token,
)
from ._evidence._primitives import (
    UnsafeBundleError,
    _chain_head,
    _chain_prefix_head,
    _json_bytes,
    _leaf,
    _norm,
    _safe_rel,
    _sha256,
    canonical,
    check_anchor,
)
from ._evidence._reader import (
    _empty_result,
    _fill_header,
    _load_meta,
    _Reader,
)
from ._evidence._replay import (
    _open_source,
    _replay_attest,
    _replay_bundle,
    _replay_receipts,
    _trace_member,
    replay,
)
from ._evidence._revocation import (
    _BAD_REVOCATIONS,
    _apply_revocation,
    _apply_revocation_doc,
    _embedded_revocations,
    _revocation_hit,
    _revocation_source,
)
from ._evidence._selfcheck import (
    _selfcheck_bundle,
    _selfcheck_revoked,
    _selfcheck_tamper,
    selfcheck,
)
from ._evidence._verify_core import (
    _check_attestations,
    _check_chain,
    _check_decision,
    _check_members,
    _check_proofs,
    _check_root,
    _extract,
    _one_envelope,
)
from ._evidence._verify_forms import (
    VerifyOptions,
    _check_extras,
    _detect_container,
    _dir_read,
    _payload_find,
    _schema_of,
    _verify_attest,
    _verify_receipts,
    _verify_uncosted,
    verify,
)


def bench() -> dict[str, Any]:
    """跑攻击矩阵 → {schema, cases, passed, failed, total, ok}。"""
    rows: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="nf_bench_") as tmp:
        os.makedirs(os.path.join(tmp, "d"), exist_ok=True)
        for name, body in (("a.md", "# A\n\n甲\n"), ("b.md", "# B\n\n乙\n"),
                           ("c.md", "# C\n\n丙\n")):
            with open(os.path.join(tmp, "d", name), "wb") as fh:
                fh.write(body.encode())
        base, _info = build(
            tmp,
            ['d/a.md', 'd/b.md'],
            opts=BuildOptions(issuer='bench', key=BENCH_KEY, created_at=BENCH_PIN),
        )
        members = _members(base)
        digest_a = _sha256(members[PAYLOAD_DIR + "d/a.md"])
        base_path = _bench_write(tmp, "base.zip", base)
        # 正例与良性变化
        _bench_run(rows, "pass", "完好证据包必过", "ok", base_path)
        ddir = os.path.join(tmp, "unpacked")
        os.makedirs(ddir, exist_ok=True)
        with zipfile.ZipFile(base_path) as zf:
            zf.extractall(ddir)
        _bench_run(rows, "pass_dir", "解包目录形态等价", "ok", ddir)
        _bench_run(rows, "benign_reorder", "成员重排/时间戳变化不影响判定", "ok",
                   _bench_write(tmp, "reorder.zip", _zip_unsorted(members)))
        # 成员面
        m = dict(members)
        payload = members[PAYLOAD_DIR + "d/a.md"]
        m[PAYLOAD_DIR + "d/a.md"] = "# A\n\n甲改\n".encode()
        _bench_run(rows, "payload_flip", "成员字节被改", "invalid",
                   _bench_write(tmp, "flip.zip", _rebuild(m)))
        m = dict(members)
        m[PAYLOAD_DIR + "d/a.md"] = payload[:4]
        _bench_run(rows, "payload_truncate", "成员被截断", "invalid",
                   _bench_write(tmp, "trunc.zip", _rebuild(m)))
        m = dict(members)
        m[PAYLOAD_DIR + "d/a.md"] = b"X" * len(payload)
        _bench_run(rows, "payload_same_size", "等长替换（摘要必须变）", "invalid",
                   _bench_write(tmp, "samesize.zip", _rebuild(m)))
        m = dict(members)
        m.pop(PAYLOAD_DIR + "d/b.md")
        _bench_run(rows, "payload_removed", "成员实体缺失", "invalid",
                   _bench_write(tmp, "pop.zip", _rebuild(m)))
        m = dict(members)
        m[PAYLOAD_DIR + "d/sneak.md"] = b"# sneak\n"
        _bench_run(rows, "payload_extra", "夹带未登记成员", "invalid",
                   _bench_write(tmp, "extra.zip", _rebuild(m)))
        # 清单面
        _bench_run(rows, "manifest_digest", "清单里的摘要被改", "invalid",
                   _bench_write(tmp, "mdig.zip", _mut_meta(
                       base, lambda meta: meta["entries"][0].__setitem__("digest", "0" * 64))))
        _bench_run(rows, "manifest_root", "清单里的根被改", "invalid",
                   _bench_write(tmp, "mroot.zip", _mut_meta(
                       base, lambda meta: meta.__setitem__("root", "0" * 64))))
        _bench_run(rows, "manifest_leaf", "清单里的叶被改", "invalid",
                   _bench_write(tmp, "mleaf.zip", _mut_meta(
                       base, lambda meta: meta["entries"][0].__setitem__("leaf", "0" * 64))))
        _bench_run(rows, "manifest_drop_entry", "清单删条但实体仍在", "invalid",
                   _bench_write(tmp, "mdrop.zip", _mut_meta(base, _drop_entry)))
        # 证明 / 链
        _bench_run(rows, "proof_flip", "包含证明被翻面", "invalid",
                   _bench_write(tmp, "pflip.zip", _mut_meta(base, _flip_proof)))
        _bench_run(rows, "proof_truncate", "包含证明被截断", "invalid",
                   _bench_write(tmp, "ptrunc.zip", _mut_meta(base, _truncate_proof)))
        _bench_run(rows, "chain_head", "链头被改", "invalid",
                   _bench_write(tmp, "chead.zip", _mut_meta(
                       base, lambda meta: meta["chain"].__setitem__("head", "0" * 64))))
        _bench_run(rows, "chain_order", "条目顺序被换（链可证顺序）", "invalid",
                   _bench_write(tmp, "corder.zip", _mut_meta(base, _swap_entries)))
        _bench_run(rows, "chain_missing", "chain 段被整体删除（缺证据≠证据成立）", "invalid",
                   _bench_write(tmp, "chnone.zip",
                                _mut_meta(base, lambda meta: meta.pop("chain", None))))
        _bench_run(rows, "chain_head_empty", "链头被置空", "invalid",
                   _bench_write(tmp, "chzero.zip",
                                _mut_meta(base, _empty_head)))
        _bench_run(rows, "chain_count_wrong", "链条数与成员数不符", "invalid",
                   _bench_write(tmp, "chcnt.zip",
                                _mut_meta(base, lambda meta: meta["chain"]
                                          .__setitem__("count", 99))))
        # 决策证据（Q0）：正例 + 两条攻击（换策略摘要 / 删声明面）
        dec = {"syscall": "cc_check",
               "policy_digest": _sha256(b"nf-check-policy/1:bench"),
               "verdict": "ok", "object_sha256": digest_a}
        dec_bundle, _dec_info = build(
            tmp,
            ['d/a.md', 'd/b.md'],
            opts=BuildOptions(issuer='bench', created_at=BENCH_PIN, decision=dec),
        )
        _bench_run(rows, "decision_ok", "决策证据自洽（digest_only → declared）", "ok",
                   _bench_write(tmp, "decbase.zip", dec_bundle))
        _bench_run(rows, "decision_policy_swap", "换策略摘要（声明面与绑定面不一致）", "invalid",
                   _bench_write(tmp, "decswap.zip", _mut_meta(
                       dec_bundle,
                       lambda meta: meta["decision"].__setitem__("policy_digest", "1" * 64))))
        _bench_run(rows, "decision_strip", "删声明面（绑定面仍在）", "invalid",
                   _bench_write(tmp, "decstrip.zip",
                                _mut_meta(dec_bundle, lambda meta: meta.pop("decision", None))))
        m = dict(members)
        m[REVOCATIONS_ENTRY] = b"{not json"
        _bench_run(rows, "traversal_path", "成员路径含双点段（验证即任意写的入口）", "invalid",
                   _bench_write(tmp, "trav.zip", _mut_meta(
                       base, lambda meta: meta["entries"][0].update(
                           {"path": "../escape.md", "id": "../escape.md"}))))
        dup_zip = os.path.join(tmp, "dupym.zip")
        # 造重名 zip 时 zipfile 会发 UserWarning（"Duplicate name"）到 stderr；机器面比对要求
        # 直跑与守护逐字节一致，这条噪声必须在这里消掉（不是屏蔽判据，是屏蔽构造期提示）。
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            with zipfile.ZipFile(dup_zip, "w", zipfile.ZIP_STORED) as zf:
                for name, raw in sorted(_members(base).items()):
                    zi = zipfile.ZipInfo(name, date_time=_ZIP_EPOCH)
                    zf.writestr(zi, raw)
                zi = zipfile.ZipInfo(PAYLOAD_DIR + "d/a.md", date_time=_ZIP_EPOCH)
                zf.writestr(zi, b"shadow")
        _bench_run(rows, "dup_members", "重名成员（zip 歧义：判定不可复算）", "invalid", dup_zip)
        _bench_run(rows, "revocations_bad", "包内吊销表写坏（坏件不能当「无吊销」）", "invalid",
                   _bench_write(tmp, "revbad.zip", _rebuild(m)))
        # 信封 / 密钥 / 结构
        m = dict(members)
        m.pop(ATTEST_DIR + "0001.json")
        _bench_run(rows, "attest_removed", "信封实体缺失", "invalid",
                   _bench_write(tmp, "natt.zip", _rebuild(m)))
        _bench_run(rows, "attest_subject_sha", "信封主体摘要被改", "invalid",
                   _bench_write(tmp, "asub.zip", _mut_attest(base, _bump_subject)))
        _bench_run(rows, "attest_mac", "hmac 签名被改", "invalid",
                   _bench_write(tmp, "amac.zip", _mut_attest(base, _bump_mac)))
        _bench_run(rows, 'no_key', 'hmac 级缺密钥（不降级）', 'invalid',
                   base_path, opts=_BenchOptions(key=None))
        _bench_run(rows, 'wrong_key', 'hmac 级错密钥', 'invalid', base_path,
                   opts=_BenchOptions(key=b'wrong-key-wrong-key-wrong-key'))
        _bench_run(rows, "schema_bumped", "包版本被改", "invalid",
                   _bench_write(tmp, "schema.zip", _mut_meta(
                       base, lambda meta: meta.__setitem__("schema", "nf-evidence/99"))))
        notzip = os.path.join(tmp, "notzip.bin")
        with open(notzip, "wb") as fh:
            fh.write(b"just a file")
        _bench_run(rows, "not_a_bundle", "不是证据包", "invalid", notzip)
        # 判定面（吊销 / 时效）
        rev = {"schema": REVOCATION_SCHEMA,
               "revoked": [{"digest": digest_a, "revoked_at": BENCH_PIN,
                             "reason": "bench"}]}
        _bench_run(rows, 'revoked', '吊销表命中必须压过 ok', 'revoked',
                   base_path, opts=_BenchOptions(revocations=rev))
        expired, _x = build(
            tmp,
            ['d/a.md', 'd/b.md'],
            opts=BuildOptions(
                issuer='bench',
                key=BENCH_KEY,
                expires_at='2020-01-01T00:00:00Z',
                created_at=BENCH_PIN,
            ),
        )
        _bench_run(rows, "expired", "有效期已过", "expired",
                   _bench_write(tmp, "expired.zip", expired))
        # 外部锚点（G1：防整链截断）
        head2 = {"count": 2, "head": verify(base_path, opts=VerifyOptions(key=BENCH_KEY))["head"]}
        v3, _i3 = build(
            tmp,
            ['d/a.md', 'd/b.md', 'd/c.md'],
            opts=BuildOptions(issuer='bench', key=BENCH_KEY, created_at=BENCH_PIN, anchor=head2),
        )
        v3_path = _bench_write(tmp, "v3.zip", v3)
        _bench_run(rows, 'anchor_ok', '锚点对得上（正常追加，不得误杀）', 'ok',
                   v3_path, opts=_BenchOptions(anchor=head2))
        head3 = {"count": 3, "head": verify(v3_path, opts=VerifyOptions(key=BENCH_KEY))["head"]}
        _bench_run(rows, 'anchor_truncated', '用更早的包冒充现在（整链截断）', 'invalid',
                   base_path, opts=_BenchOptions(anchor=head3))
        _bench_run(rows, 'anchor_forked', '锚点来自另一条链（历史被改写）', 'invalid',
                   v3_path, opts=_BenchOptions(anchor={'count': 2, 'head': '0' * 64}))
        _bench_run(rows, 'anchor_bad_shape', '锚点材料形状不对', 'invalid',
                   v3_path, opts=_BenchOptions(anchor={'count': 'two', 'head': ''}))
    passed = sum(1 for r in rows if r["ok"])
    return {"schema": BENCH_SCHEMA, "cases": rows, "passed": passed,
            "failed": len(rows) - passed, "total": len(rows),
            "ok": passed == len(rows)}
