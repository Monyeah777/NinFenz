"""nf-anchor/1 外部锚（FR-A3-03 / 计划 §7.3 T2-T3）：构建 + 核验 + 事实投影。

为什么需要它：链头/bundle 根自己算得再对，也只能证明「我没算错」；要证明「这个摘要在某个
时刻/某个公共日志上真的存在过」，必须有**外部锚**。本模块把 nf-anchor/1 的四类锚
（rfc3161 / transparency-sth / witness / git-commit）接成可判定的证据面：

- 结构：冻结 schema 判定（未知 kind / 未知字段一律拒）；
- 绑定：anchor.target_digest 必须等于被证摘要，否则 ANCHOR-TARGET-MISMATCH（invalid）；
- 核验：每类锚由**可插拔 verifier** 验（本仓零第三方加密库；rfc3161 用 openssl 的既有
  timestamp.verify，witness/STH 用调用方给的 verifier 回调）；
- 事实：time_token / transparency_sth / public_anchor ∈ ok/none/invalid，供 verify.decide 用；
- 缺信任根/缺 verifier 一律记 none（不可判定），绝不写 ok。

边界：T4 公共锚（Sigstore/Rekor/公共 TSA）不在本模块内（G4）；witness 语句格式是本仓约定
（nf-anchor-witness/1），外部 witness 需按此签名，未实现（G4 前如实标 none）。
"""
from __future__ import annotations

import base64
import binascii
import hashlib
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

from core import json_doc, json_schema
from core.trust import canonical as tc

GUIDE = "修复指引："
SCHEMA = "nf-anchor/1"
SCHEMA_REL = "protocol/trust/anchor.schema.json"
KINDS = ("rfc3161", "transparency-sth", "witness", "git-commit")
MAX_ANCHORS = 1024
WITNESS_STATEMENT = "nf-anchor-witness/1"


def load_schema(root: str = ".", rel: str = SCHEMA_REL) -> dict:
    path = Path(root) / rel
    if not path.is_file():
        raise ValueError(f"缺 anchor schema：{rel}（{GUIDE}先落 protocol/trust 定义）")
    doc = json_doc.load(path, dict, what=rel)
    const = str((doc.get("properties") or {}).get("schema", {}).get("const"))
    if const != SCHEMA:
        raise ValueError(f"{rel} 不是 {SCHEMA} 定义（{GUIDE}核对 properties.schema.const）")
    return doc


def build_anchor_set(target_digest: str, anchors: list, schema: dict | None = None,
                     root: str = ".") -> dict:
    """组装并自检 nf-anchor/1；结构不过即抛（不产出半截锚件）。"""
    if not tc.is_digest(target_digest):
        raise ValueError(f"target_digest 必须是 64 位小写 hex（{GUIDE}用 sha256 摘要）")
    if not isinstance(anchors, list) or not anchors:
        raise ValueError(f"anchors 至少 1 条（{GUIDE}无锚件没有外部证据）")
    if len(anchors) > MAX_ANCHORS:
        raise ValueError(f"anchors 超过上限 {MAX_ANCHORS}（{GUIDE}拆多份锚件）")
    doc = {"schema": SCHEMA, "target_digest": target_digest, "anchors": anchors}
    check_schema = schema if schema is not None else load_schema(root)
    problems = json_schema.json_schema_check(doc, check_schema)
    if problems:
        raise ValueError(f"锚件结构不合 {SCHEMA}：{problems[0]}（{GUIDE}按冻结 schema 修）")
    return doc


def _b64d(text: Any) -> bytes:
    if not isinstance(text, str):
        raise ValueError(f"base64 字段必须是字符串（{GUIDE}检查锚件结构）")
    try:
        return base64.b64decode(text, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError(f"base64 解码失败：{exc}（{GUIDE}用严格 base64 重编）") from exc


def witness_statement(target_digest: str, witness_id: str, keyid: str) -> str:
    """本仓 witness 签名语句（域分隔摘要）：witness 对「目标摘要 + 自己身份」签名。"""
    body = tc.canonical_bytes({"schema": WITNESS_STATEMENT, "target_digest": target_digest,
                               "witness_id": str(witness_id), "keyid": str(keyid)})
    return tc.domain_digest("nf:anchor:v1:witness", body)


def sth_statement(sth: dict) -> str:
    """STH 签名语句：log_id/tree_size/root 三者绑定。"""
    return tc.domain_digest("nf:anchor:v1:sth", tc.canonical_bytes(
        {"log_id": str(sth.get("log_id")), "tree_size": int(sth.get("tree_size") or 0),
         "root": str(sth.get("root"))}))


def make_timestamp_verifier(query_path: str, ca_file: str, subject_path: str = "",
                            policy_root_digest: str = "") -> Callable[[dict, str], dict]:
    """返回 RFC3161 verifier：token 必须与 query 成对，且 subject 摘要=target_digest。

    policy_root_digest（可选）：policy.tsa_roots[].digest 应是 CA 文件的摘要；给了就必须匹配
    （信任根不是「随便换个 CA 文件」就能换的）。
    """
    def verify(item: dict, target_digest: str) -> dict:
        from core import timestamp
        try:
            token_bytes = _b64d(item.get("token"))
        except ValueError as exc:
            return {"ok": False, "reason": "ANCHOR-TOKEN-B64-INVALID", "detail": str(exc)}
        ca_path = Path(ca_file)
        if not ca_path.is_file():
            return {"ok": False, "reason": "TSA-CA-MISSING",
                    "detail": "缺 CA 文件（" + GUIDE + "给 TSA 根/中间证书 PEM）"}
        if policy_root_digest:
            actual = hashlib.sha256(ca_path.read_bytes()).hexdigest()
            if actual != policy_root_digest:
                return {"ok": False, "reason": "TSA-ROOT-MISMATCH",
                        "detail": "CA 摘要与 policy.tsa_roots.digest 不符"}
        if subject_path:
            subject_digest = hashlib.sha256(Path(subject_path).read_bytes()).hexdigest()
            if subject_digest != target_digest:
                return {"ok": False, "reason": "SUBJECT-DIGEST-MISMATCH",
                        "detail": "被证文件摘要与 anchor.target_digest 不符"}
        with tempfile.TemporaryDirectory() as tmp:
            token_path = Path(tmp) / "token.tsr"
            token_path.write_bytes(token_bytes)
            res = timestamp.verify(str(token_path), query_path, ca_file=str(ca_path))
        if not res.get("ok"):
            return {"ok": False, "reason": "TIMESTAMP-INVALID",
                    "detail": "；".join(res.get("issues") or [])[:200]}
        return {"ok": True, "gen_time": res.get("gen_time", ""),
                "tsa": res.get("tsa", ""), "warnings": res.get("warnings") or []}
    return verify


def make_witness_verifier(material: dict) -> Callable[[dict, str], dict]:
    """返回 witness verifier：material[keyid] = callable(data_digest, sig_bytes)->bool。"""
    def verify(item: dict, target_digest: str) -> dict:
        keyid = str(item.get("keyid") or "")
        checker = (material or {}).get(keyid)
        if not callable(checker):
            return {"ok": False, "reason": "WITNESS-KEY-MISSING", "detail": keyid}
        try:
            signature = _b64d(item.get("sig"))
        except ValueError as exc:
            return {"ok": False, "reason": "WITNESS-SIG-B64-INVALID", "detail": str(exc)}
        message = witness_statement(target_digest, str(item.get("witness_id") or ""), keyid)
        try:
            ok = bool(checker(message, signature))
        except Exception:
            # 静默跳过理由：witness 回调异常 = 验签失败（fail-closed），不把异常当通过。
            ok = False
        if not ok:
            return {"ok": False, "reason": "WITNESS-SIG-INVALID"}
        return {"ok": True, "witness_id": str(item.get("witness_id") or ""), "keyid": keyid}
    return verify


def make_sth_verifier(material: dict) -> Callable[[dict, str], dict]:
    """返回 STH verifier：material[log_id] = callable(statement_digest, sig_bytes)->bool。"""
    def verify(item: dict, target_digest: str) -> dict:
        del target_digest                                     # STH 只绑 root/tree_size
        log_id = str(item.get("log_id") or "")
        checker = (material or {}).get(log_id)
        if not callable(checker):
            return {"ok": False, "reason": "STH-LOG-KEY-MISSING", "detail": log_id}
        try:
            signature = _b64d(item.get("signature"))
        except ValueError as exc:
            return {"ok": False, "reason": "STH-SIG-B64-INVALID", "detail": str(exc)}
        try:
            ok = bool(checker(sth_statement(item), signature))
        except Exception:
            # 静默跳过理由：STH 回调异常 = 验签失败（fail-closed），不把异常当通过。
            ok = False
        if not ok:
            return {"ok": False, "reason": "STH-SIG-INVALID"}
        return {"ok": True, "log_id": log_id}
    return verify


def make_git_commit_verifier(repo_path: str = "") -> Callable[[dict, str], dict]:
    """返回 git-commit verifier：只证 commit 在给定仓库里可达（不证公共可见）。"""
    def verify(item: dict, target_digest: str) -> dict:
        del target_digest
        commit = str(item.get("commit") or "")
        repo = repo_path or str(item.get("repo") or "")
        if not repo:
            return {"ok": False, "reason": "GIT-REPO-MISSING"}
        import subprocess
        try:
            proc = subprocess.run(["git", "-C", repo, "cat-file", "-e", commit + "^{commit}"],
                                  capture_output=True, text=True, encoding="utf-8",
                                  timeout=30)
        except (OSError, subprocess.SubprocessError):
            return {"ok": False, "reason": "GIT-UNAVAILABLE"}
        if proc.returncode != 0:
            return {"ok": False, "reason": "GIT-COMMIT-NOT-FOUND", "detail": commit}
        return {"ok": True, "commit": commit,
                "warnings": ["git-commit 只证本地可达；公共可见性需公共锚（T4/G4）"]}
    return verify


def _tsa_root(policy: dict, tsa_id: str) -> dict | None:
    for item in (policy or {}).get("tsa_roots") or []:
        if isinstance(item, dict) and str(item.get("id")) == tsa_id:
            return item
    return None


def verify_anchor_set(doc: Any, target_digest: str, policy: dict,
                      verifiers: dict | None = None,
                      schema: dict | None = None,
                      root: str = ".") -> dict:
    """核验锚件 → {facts, details, issues}。facts 供 verify.decide 使用。"""
    check_schema = schema if schema is not None else load_schema(root)
    problems = json_schema.json_schema_check(doc, check_schema)
    if problems:
        return {"facts": {"time_token": "invalid", "transparency_sth": "invalid",
                          "public_anchor": "none"},
                "details": [], "issues": [{"code": "ANCHOR-SCHEMA-INVALID",
                                           "message": problems[0],
                                           "fix": "按 nf-anchor/1 修锚件后重验"}]}
    if doc.get("target_digest") != target_digest:
        return {"facts": {"time_token": "invalid", "transparency_sth": "invalid",
                          "public_anchor": "none"},
                "details": [], "issues": [{"code": "ANCHOR-TARGET-MISMATCH",
                                           "message": "锚件 target_digest 与被证摘要不符",
                                           "fix": "重新对正确摘要做锚，别把旧锚挂到新对象上"}]}
    checks = verifiers or {}
    details, issues = [], []
    facts = {"time_token": "none", "transparency_sth": "none", "public_anchor": "none"}
    status_by_kind: dict = {}
    for item in doc.get("anchors") or []:
        kind = str(item.get("kind"))
        detail = {"kind": kind, "status": "none"}
        if kind == "rfc3161":
            tsa_id = str(item.get("tsa") or "")
            root_item = _tsa_root(policy, tsa_id)
            if root_item is None:
                detail.update(status="none", reason="TSA-ROOT-MISSING")
            elif not callable(checks.get("rfc3161")):
                detail.update(status="none", reason="VERIFIER-MISSING")
            else:
                got = checks["rfc3161"](item, target_digest)
                detail.update(status="ok" if got.get("ok") else "invalid",
                              reason=got.get("reason", ""), gen_time=got.get("gen_time", ""))
        elif kind == "transparency-sth":
            if not callable(checks.get("transparency-sth")):
                detail.update(status="none", reason="VERIFIER-MISSING")
            else:
                got = checks["transparency-sth"](item, target_digest)
                detail.update(status="ok" if got.get("ok") else "invalid",
                              reason=got.get("reason", ""))
        elif kind == "witness":
            if not callable(checks.get("witness")):
                detail.update(status="none", reason="VERIFIER-MISSING")
            else:
                got = checks["witness"](item, target_digest)
                detail.update(status="ok" if got.get("ok") else "invalid",
                              reason=got.get("reason", ""))
        elif kind == "git-commit":
            if not callable(checks.get("git-commit")):
                detail.update(status="none", reason="VERIFIER-MISSING")
            else:
                got = checks["git-commit"](item, target_digest)
                detail.update(status="ok" if got.get("ok") else "invalid",
                              reason=got.get("reason", ""),
                              warnings=got.get("warnings") or [])
        details.append(detail)
        status_by_kind.setdefault(kind, []).append(detail["status"])
    for kind, statuses in status_by_kind.items():
        if kind == "rfc3161":
            facts["time_token"] = ("invalid" if "invalid" in statuses
                                   else "ok" if "ok" in statuses else "none")
        elif kind == "transparency-sth":
            facts["transparency_sth"] = ("invalid" if "invalid" in statuses
                                         else "ok" if "ok" in statuses else "none")
        elif kind == "witness":
            witnesses = statuses
            if "invalid" in witnesses:
                facts["transparency_sth"] = "invalid"
            threshold = int(((policy or {}).get("anchors") or {}).get(
                "witness_threshold") or 0)
            if (threshold > 0 and facts["transparency_sth"] == "ok"
                    and witnesses.count("ok") < threshold):
                facts["transparency_sth"] = "none"
                issues.append({"code": "WITNESS-THRESHOLD-NOT-MET",
                               "message": f"witness 有效 {witnesses.count('ok')} "
                                          f"< 策略阈值 {threshold}",
                               "fix": "收集足够 witness 签名后重验"})
    for detail in details:
        if detail["status"] == "invalid":
            code = str(detail.get("reason") or "ANCHOR-INVALID")
            issues.append({"code": code,
                           "message": f"{detail['kind']} 锚核验失败",
                           "fix": "修锚件/换正确信任根后重验；被篡改的锚必须拒"})
    return {"facts": facts, "details": details, "issues": issues}
