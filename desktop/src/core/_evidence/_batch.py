"""evidence · _batch（自 evidence.py 拆出；只移动代码，行为/文案不变）。"""
from __future__ import annotations

import os
import zipfile
from dataclasses import dataclass
from typing import Any

from core import json_doc

from ._const import (
    ATTEST_SCHEMA,
    ATTEST_SET_SCHEMA,
    BATCH_MAX_FILES,
    GUIDE,
    RECEIPTS_SCHEMA,
)
from ._reader import (
    _Reader,
)
from ._verify_forms import (
    VerifyOptions,
    _detect_container,
    _dir_read,
    _verify_attest,
    _verify_receipts,
    verify,
)


def _picked_files(target: str) -> list[str]:
    """目录下可取验的文件（*.zip / *.json，按名排序，只取常规文件）。"""
    picked = []
    for name in sorted(os.listdir(target)):
        full = os.path.join(target, name)
        if not os.path.isfile(full):
            continue
        low = name.lower()
        if low.endswith(".zip") or low.endswith(".json"):
            picked.append(full)
    return picked


def batch_paths(target: str, max_files: int = BATCH_MAX_FILES) -> list[str]:
    """批处理目标 → 待验文件列表（纯函数，便于单测）。

    目标可以是：单个证据包（.zip / 单 JSON），或一个目录（取其中 *.zip 与 *.json，按名排序）。
    目录里没有可验件就抛 ValueError（带指引），不静默返回空——空结果最容易被当成「全绿」。
    """
    target = str(target or "")
    if not target:
        raise ValueError("批处理目标为空（" + GUIDE + "给一个 .zip / 单 JSON，或包含它们的目录）")
    if os.path.isfile(target):
        return [target]
    if not os.path.isdir(target):
        raise ValueError(f"批处理目标不存在：{target}（修复指引：确认路径；目录形式只取其中的 "
                         "*.zip 与 *.json）")
    picked = _picked_files(target)
    if not picked:
        raise ValueError(f"目录里没有可验件：{target}（修复指引：只取 *.zip 与 *.json；"
                         "先 nf evidence pack 产出证据包）")
    if len(picked) > max_files:
        raise ValueError(f"目录里可验件过多（{len(picked)} > 上限 {max_files}）（修复指引：分批验，"
                         "或显式给单个文件）")
    return picked




def verify_batch(target: str, key: bytes | None = None,
                 revocations: dict[str, Any] | None = None, at: str = "",
                 root: str = "", anchor: dict[str, Any] | None = None) -> dict[str, Any]:
    """批量复验 → {total, counts{verdict: n}, ok, failures, rows}。

    判定词表与单件完全一致（复用 verify_any）；任何一件非 ok 就整体 ok=False——
    批量的意义是「这一批能不能用」，不是「平均下来还行」。
    """
    paths = batch_paths(target)
    rows: list[dict[str, Any]] = []
    counts: dict[str, int] = {}
    for path in paths:
        try:
            res = verify_any(
                path,
                opts=BatchVerifyOptions(
                    key=key,
                    revocations=revocations,
                    at=at,
                    root=root,
                    anchor=anchor,
                ),
            )
        except (OSError, ValueError) as exc:      # 用法级错误只影响这一件，不炸整批
            res = {"verdict": "invalid", "issues": [str(exc)], "level": "none", "root": ""}
        verdict = str(res.get("verdict") or "invalid")
        counts[verdict] = counts.get(verdict, 0) + 1
        rows.append({"path": os.path.basename(path), "verdict": verdict,
                     "level": res.get("level"), "root": res.get("root"),
                     "issues": list(res.get("issues") or [])[:3]})
    failures = [r for r in rows if r["verdict"] != "ok"]
    return {"schema": "nf-evidence-batch/1", "total": len(rows), "ok": not failures,
            "counts": dict(sorted(counts.items())), "failures": len(failures), "rows": rows}




@dataclass(frozen=True)
class BatchVerifyOptions:
    """参数对象（审计 C-007：把成组参数收成不可变对象）。"""
    key: bytes | None = None
    revocations: dict[str, Any] | None = None
    at: str = ''
    root: str = ''
    kind: str = ''
    anchor: dict[str, Any] | None = None
    expected_policy_digest: str = ''
    require_fresh_revocations: bool = False
    time_record: dict[str, Any] | None = None
    time_ca: str = ''
    time_untrusted: str = ''


def verify_any(path: str, opts: BatchVerifyOptions | None = None) -> dict[str, Any]:
    """cc_verify 的统一入口：自动判三种形态并给出同一套四词判定。

    - 容器（.zip / 目录）按内容判形态；单 JSON 按 schema 判形态，成员从 `root` 找
      （缺省 = 该 JSON 所在目录）。
    - 判定词表与退出码对所有形态一致：ok / revoked / expired / invalid。
    """

    opts = opts if opts is not None else BatchVerifyOptions()
    key = opts.key
    revocations = opts.revocations
    at = opts.at
    root = opts.root
    kind = opts.kind
    anchor = opts.anchor
    expected_policy_digest = opts.expected_policy_digest
    require_fresh_revocations = opts.require_fresh_revocations
    time_record = opts.time_record
    time_ca = opts.time_ca
    time_untrusted = opts.time_untrusted
    if os.path.isfile(path) and not zipfile.is_zipfile(path):
        res = _verify_single_json(
            path,
            opts=BatchVerifyOptions(
                key=key,
                revocations=revocations,
                at=at,
                root=root,
                kind=kind,
                require_fresh_revocations=require_fresh_revocations,
            ),
        )
        form = "bundle" if str(res.get("kind") or "") == "bundle" else "other"
    else:
        rd = _Reader(path)
        try:
            form, doc = _detect_container(rd, kind)
            if form == "bundle":
                return verify(
                    path,
                    opts=VerifyOptions(
                        key=key,
                        revocations=revocations,
                        at=at,
                        anchor=anchor,
                        expected_policy_digest=expected_policy_digest,
                        require_fresh_revocations=require_fresh_revocations,
                        time_record=time_record,
                        time_ca=time_ca,
                        time_untrusted=time_untrusted,
                    ),
                )
            if form == "receipts":
                res = _verify_receipts(doc, rd.read, revocations,
                                       require_fresh_revocations, at)
            else:
                res = _verify_attest(doc, rd.read, key, revocations, at,
                                     require_fresh_revocations)
        finally:
            rd.close()
    if expected_policy_digest and form != "bundle":
        res["warnings"].append("该证据形态不含 decision，无法比对策略（只证字节与信封）")
    return res




def _base_dir(root, path: str) -> str:
    """显式 root 优先；否则用文件所在目录（再退当前目录）。"""
    return root or os.path.dirname(os.path.abspath(path)) or "."


def _is_receipts(schema: str, kind) -> bool:
    """schema 与显式 kind 都指向 receipts 形态。"""
    return schema == RECEIPTS_SCHEMA and (not kind or kind == "receipts")


def _is_attest(schema: str, kind) -> bool:
    """schema 与显式 kind 都指向 attest 形态。"""
    return schema in (ATTEST_SCHEMA, ATTEST_SET_SCHEMA) and (not kind or kind == "attest")


def _verify_single_json(path: str, opts: BatchVerifyOptions) -> dict[str, Any]:
    key = opts.key
    revocations = opts.revocations
    at = opts.at
    root = opts.root
    kind = opts.kind
    require_fresh_revocations = opts.require_fresh_revocations
    with open(path, "rb") as fh:
        raw = fh.read()
    try:
        doc = json_doc.loads(raw.decode(), dict, what="证据文档")
    except (ValueError, UnicodeDecodeError) as exc:
        raise ValueError(f"不是合法 UTF-8 JSON：{path}（{exc}）（{GUIDE}请给 nf receipts / "
                         "nf attest 产出的 JSON，或 nf evidence pack 的 .zip）") from exc
    if not isinstance(doc, dict):
        raise ValueError(f"证据文档不是对象：{path}（{GUIDE}请给带 schema 字段的证据 JSON）")
    schema = str(doc.get("schema") or "")
    read = _dir_read(_base_dir(root, path))
    if _is_receipts(schema, kind):
        return _verify_receipts(doc, read, revocations, require_fresh_revocations, at)
    if _is_attest(schema, kind):
        return _verify_attest(doc, read, key, revocations, at, require_fresh_revocations)
    raise ValueError(f"认不出证据形态：{path}（schema={schema or '缺失'}）"
                     "（修复指引：请对照支持的四种——nf-evidence/1 容器、nf-receipts/1、"
                     "nf-attest/1、nf-attest-set/1；形态以文档 schema 字段判定）")
