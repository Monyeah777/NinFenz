"""evidence · _replay（自 evidence.py 拆出；只移动代码，行为/文案不变）。"""
from __future__ import annotations

import hashlib
import hmac
import os
import zipfile
from typing import Any

from core import json_doc, receipts
from core.transparency_log import NODE_PREFIX

from ._const import (
    ATTEST_SCHEMA,
    ATTEST_SET_SCHEMA,
    GUIDE,
    RECEIPTS_SCHEMA,
    REPLAY_SCHEMA,
)
from ._primitives import (
    _leaf,
    _norm,
    _sha256,
    canonical,
)
from ._reader import (
    _Reader,
)
from ._verify_forms import (
    _detect_container,
    _dir_read,
    _payload_find,
)


def _open_source(path: str, root: str = "",
                 kind: str = "") -> tuple[str, dict[str, Any], Any, Any]:
    """→ (形态, 文档, read(rel), close())。容器与单 JSON 统一读面。"""
    if os.path.isfile(path) and not zipfile.is_zipfile(path):
        with open(path, "rb") as fh:
            raw = fh.read()
        try:
            doc = json_doc.loads(raw.decode(), dict, what="证据文档")
        except (ValueError, UnicodeDecodeError) as exc:
            raise ValueError(f"不是合法 UTF-8 JSON：{path}（{exc}）"
                             f"（{GUIDE}请给证据 JSON 或证据包 .zip）") from exc
        schema = str(doc.get("schema") or "") if isinstance(doc, dict) else ""
        form = {RECEIPTS_SCHEMA: "receipts", ATTEST_SCHEMA: "attest",
                ATTEST_SET_SCHEMA: "attest"}.get(schema, "")
        if not form:
            raise ValueError(f"认不出证据形态：{path}（schema={schema or '缺失'}）"
                             f"（{GUIDE}请给 nf-receipts/1 · nf-attest/1 · nf-attest-set/1）")
        base = root or os.path.dirname(os.path.abspath(path)) or "."
        return form, doc, _dir_read(base), (lambda: None)
    rd = _Reader(path)
    form, doc = _detect_container(rd, kind)
    return form, doc, rd.read, rd.close




def _trace_member(e: dict[str, Any], read: Any, issues: list[str],
                  seen: set[str]) -> dict[str, Any] | None:
    """单个成员的推导链：字节 → 摘要 → 叶 → 证明折叠。返回 trace 段或 None。"""
    rel = _norm(str(e.get("path") or e.get("id") or ""))
    if not rel:
        issues.append("回执条目缺 path/id（" + GUIDE + "请重新生成回执）")
        return None
    if rel in seen:
        issues.append(f"成员重复出现：{rel}（{GUIDE}同一成员不许在证据里出现两次）")
        return None
    seen.add(rel)
    data = _payload_find(read, rel)
    if data is None:
        issues.append(f"缺成员实体：{rel}（{GUIDE}请把成员实体放进证据包/成员根）")
        return None
    digest = _sha256(data)
    leaf = _leaf(rel, digest)
    steps: list[dict[str, Any]] = [
        {"step": 1, "rule": "sha256-bytes", "subject": rel,
         "input": f"{len(data)} bytes", "output": digest},
        {"step": 2, "rule": "rfc6962-leaf", "subject": rel,
         "input": canonical({"id": rel, "digest": digest}).hex()[:32] + "…",
         "output": leaf},
    ]
    cur = leaf
    for i, step in enumerate(e.get("proof") or [], 1):
        side = str(step.get("side") or "")
        sibling = str(step.get("hash") or "")
        nxt = receipts.fold_proof(cur, [{"side": side, "hash": sibling}])
        steps.append({"step": 2 + i, "rule": "rfc6962-fold", "subject": rel,
                      "input": f"{side}:{sibling[:16]}… 折叠自 {cur[:16]}…",
                      "output": nxt})
        cur = nxt
    recorded = str(e.get("leaf") or "")
    if recorded and recorded != leaf:
        issues.append(f"叶复算不符：{rel}（记录={recorded[:16]} 实测={leaf[:16]}）"
                      f"（{GUIDE}叶定义须与 receipts 同源；证据被改过就重打）")
    return {"path": rel, "digest": digest, "leaf": leaf, "folded": cur,
            "steps": steps}




def _replay_bundle(doc: dict[str, Any], read: Any, entry: str,
                   key: bytes | None) -> dict[str, Any]:
    """包形态：成员链 + 链头 + 信封面。"""
    issues: list[str] = []
    entries = doc.get("entries") or []
    res: dict[str, Any] = {"root": str(doc.get("root") or ""),
                           "head": str((doc.get("chain") or {}).get("head") or ""),
                           "count": len(entries), "entries": [], "issues": issues}
    want = _norm(entry) if entry else ""
    leaves: list[bytes] = []
    prev = "0" * 64
    seen: set[str] = set()
    for e in entries:
        trace = _trace_member(e, read, issues, seen)
        if trace is None:
            return res
        leaves.append(bytes.fromhex(str(trace["leaf"])))
        node = hashlib.sha256(NODE_PREFIX + b"|" + prev.encode("ascii") + b"|"
                              + str(trace["leaf"]).encode("ascii")).hexdigest()
        trace["steps"].append({"step": len(trace["steps"]) + 1,
                               "rule": "nf-hashchain",
                               "subject": trace["path"],
                               "input": prev[:16] + "…", "output": node})
        prev = node
        if not want or trace["path"] == want:
            res["entries"].append(trace)
    res["recomputed_root"] = (receipts.merkle_root(leaves) or b"").hex()
    res["recomputed_head"] = prev
    if res["recomputed_root"] != res["root"]:
        issues.append(f"根不一致：记录={res['root'][:16]} 实测="
                      f"{res['recomputed_root'][:16]}（{GUIDE}成员集被增删或改序）")
    if not res["head"]:
        issues.append("缺 chain 段（" + GUIDE + "轨迹无法证明条目顺序——"
                      "请用 nf evidence pack 重新打包，缺证据不等于没问题）")
    elif res["recomputed_head"] != res["head"]:
        issues.append("链头不一致（" + GUIDE + "条目顺序被插删/改序）")
    if want and not res["entries"]:
        issues.append(f"证据里没有该成员：{entry}（{GUIDE}请核对相对路径写法）")
    return res




def _replay_receipts(doc: dict[str, Any], read: Any, entry: str) -> dict[str, Any]:
    """回执形态：成员链 → 根（无信封、无链头）。"""
    issues: list[str] = []
    entries = doc.get("entries") or []
    res: dict[str, Any] = {"root": str(doc.get("root") or ""), "head": "",
                           "count": len(entries), "entries": [], "issues": issues}
    want = _norm(entry) if entry else ""
    leaves: list[bytes] = []
    seen: set[str] = set()
    for e in entries:
        item = ({"path": e.get("id"), "digest": e.get("digest"),
                 "leaf": e.get("leaf"), "proof": e.get("proof")})
        trace = _trace_member(item, read, issues, seen)
        if trace is None:
            return res
        leaves.append(bytes.fromhex(str(trace["leaf"])))
        if not want or trace["path"] == want:
            res["entries"].append(trace)
    res["recomputed_root"] = (receipts.merkle_root(leaves) or b"").hex()
    res["recomputed_head"] = ""
    if res["recomputed_root"] != res["root"]:
        issues.append(f"根不一致：记录={res['root'][:16]} 实测="
                      f"{res['recomputed_root'][:16]}（{GUIDE}成员集被增删或改序）")
    if want and not res["entries"]:
        issues.append(f"回执里没有该成员：{entry}（{GUIDE}请核对编号写法）")
    return res




def _replay_attest(doc: dict[str, Any], read: Any, entry: str,
                   key: bytes | None) -> dict[str, Any]:
    """信封形态：主体摘要 → 信封摘要 → （可选）hmac。"""
    issues: list[str] = []
    if str(doc.get("schema") or "") == ATTEST_SET_SCHEMA:
        envs = doc.get("attestations") or []
    else:
        envs = [doc]
    res: dict[str, Any] = {"root": "", "head": "", "count": len(envs),
                           "entries": [], "issues": issues}
    want = _norm(entry) if entry else ""
    for env in envs:
        if not isinstance(env, dict):
            issues.append("信封不是对象（" + GUIDE + "请重新 nf attest --out）")
            continue
        subj = env.get("subject") or {}
        rel = _norm(str(subj.get("path") or ""))
        data = _payload_find(read, rel) if rel else None
        if data is None:
            issues.append(f"缺成员实体：{rel or '?'}（{GUIDE}请把成员放进成员根）")
            continue
        steps = [{"step": 1, "rule": "sha256-bytes", "subject": rel,
                  "input": f"{len(data)} bytes", "output": _sha256(data)}]
        base = {k: env.get(k) for k in ("schema", "subject", "producer", "issued_at")}
        digest_env = _sha256(canonical(base))
        steps.append({"step": 2, "rule": "nf-attest-envelope", "subject": rel,
                      "input": canonical(base).hex()[:32] + "…",
                      "output": digest_env})
        sig = env.get("signature") or {}
        if sig.get("scheme") == "hmac-sha256" and key:
            mac = hmac.new(key, digest_env.encode("utf-8"), hashlib.sha256).hexdigest()
            steps.append({"step": 3, "rule": "hmac-sha256", "subject": rel,
                          "input": digest_env[:16] + "…", "output": mac})
            if mac != str(sig.get("mac") or ""):
                issues.append(f"hmac 不匹配：{rel}（{GUIDE}密钥不符或信封被改）")
        if digest_env != str(env.get("envelope_digest") or ""):
            issues.append(f"信封摘要不一致：{rel}（{GUIDE}信封被改动）")
        if not want or rel == want:
            res["entries"].append({"path": rel, "digest": _sha256(data),
                                   "leaf": digest_env, "steps": steps})
    if want and not res["entries"]:
        issues.append(f"信封里没有该主体：{entry}（{GUIDE}请核对相对路径写法）")
    return res




def replay(target: str, entry: str = "", key: bytes | None = None,
           root: str = "", kind: str = "") -> dict[str, Any]:
    """把证据的推导过程摊成确定性 trace；`ok` = 每一步都复算得出且与记录一致。"""
    form, doc, read, close = _open_source(target, root, kind)
    try:
        if form == "bundle":
            res = _replay_bundle(doc, read, entry, key)
        elif form == "receipts":
            res = _replay_receipts(doc, read, entry)
        else:
            res = _replay_attest(doc, read, entry, key)
    finally:
        close()
    res["schema"] = REPLAY_SCHEMA
    res["kind"] = form
    res["target"] = target.replace("\\", "/")
    res["ok"] = not res["issues"]
    return res
