"""core.attest 私有实现分片 1/2（对外只经 core.attest 门面导入）：SCHEMA、SCHEME_HMAC 等"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import shutil
import subprocess
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

SCHEMA = "nf-attest/1"


#: 支持的签名方案（外挂锚 = 外部验证器；未知方案一律 fail-closed）
SCHEME_HMAC = "hmac-sha256"


SCHEME_SIGSTORE = "sigstore-keyless"


SCHEME_SSH = "ssh-sig"


#: 决策证据（Q0）：绑定「这次判定过了哪条策略」的四字段；可选，旧信封无此键时摘要不变
DECISION_FIELDS = ("syscall", "policy_digest", "verdict", "object_sha256")


#: ssh-sig 的签名命名空间（ssh-keygen -Y sign -n）——与密钥其他用途隔离
SSH_NAMESPACE = "nf-attest"


#: ssh-sig 的签名载荷格式（读者侧按同一格式重建，必须逐字一致）
SSH_PAYLOAD_PREFIX = "nf-attest-v1\nsubject_sha256:"


#: 外部验证器（ssh-keygen / cosign）的**调用上限**（秒）。
#: 为什么要设（2026-10-01 只读扫描）：这些调用原本只见处理了 stdin（`stdin=DEVNULL` 防口令
#: 提问挂住），但**没有任何超时**——工具因别的理由卡住（agent socket / 网络 HSM / 版本怪异）
#: 时会把调用方（agent 会话、CI）**无限期挂住**，且没有诊断。超时一律 fail-closed。
TOOL_TIMEOUT_S = 60


#: 默认锚定的内容面 = 与 `nf sig` 同源的根级编号文档
DEFAULT_SUBJECTS = ("01_核心协议.md", "02_联动注册表.md",
                    "06_Agent执行协议.md", "07_官方核心出厂与社区预设导航.md")


def canonical(obj: Any) -> bytes:
    """规范化 JSON 编码（键排序 + 紧凑分隔符）——摘要稳定的前提。"""
    return json.dumps(obj, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":")).encode("utf-8")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def subject_of(path: str, root: str = ".") -> Dict[str, Any]:
    """内容主体摘要：相对路径 + sha256 + 字节数 + 行数（全部可复现）。"""
    abs_path = os.path.join(root, path)
    with open(abs_path, "rb") as fh:
        raw = fh.read()
    text = raw.decode("utf-8")
    rel = path.replace("\\", "/")
    return {
        "path": rel,
        "sha256": _sha256(raw),
        "bytes": len(raw),
        "line_count": len(text.replace("\r\n", "\n").splitlines()),
    }


def envelope_digest(att: Dict[str, Any]) -> str:
    """信封摘要 = subject + producer + issued_at（+ 可选 decision）的规范化摘要。

    decision 存在时纳入摘要：否则改 64 个 hex 就能「换策略」，签名面覆盖不到。
    旧信封没有 decision 键 → base 仍是 4 键，摘要逐字节不变（向后兼容）。
    """
    base = {k: att.get(k) for k in ("schema", "subject", "producer", "issued_at")}
    decision = att.get("decision")
    if isinstance(decision, dict) and decision:
        base["decision"] = decision
    return _sha256(canonical(base))


def issue_stamp(now: Optional[datetime] = None) -> str:
    """签发时间戳（UTC，秒级）。**可复现**：设 `SOURCE_DATE_EPOCH` 就用它，否则用墙钟。

    为什么（2026-10-01 取证）：机器面「同一输入两次运行逐字节一致」在 `nf attest --json` 上
    此前是假真——`issued_at` 取墙钟，跨秒的两次运行必然不同（信封摘要也随之变），
    agent 侧无法稳定 diff，判据也没法把这条口径钉住。`SOURCE_DATE_EPOCH` 是**可复现构建**
    的通用惯例（reproducible-builds.org）：设了就固定，不设仍是真实签发时间。
    """
    if now is not None:
        return now.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    epoch = (os.environ.get("SOURCE_DATE_EPOCH") or "").strip()
    if epoch.isdigit():
        return datetime.fromtimestamp(int(epoch), timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def build(path: str, root: str = ".", issuer: str = "",
          subject: Optional[Dict[str, Any]] = None,
          decision: dict[str, Any] | None = None) -> Dict[str, Any]:
    """构造未签名 attestation（digest_only 级）；decision 可选（进信封摘要）。"""
    subj = subject if subject is not None else subject_of(path, root)
    att = {
        "schema": SCHEMA,
        "subject": subj,
        "producer": {"tool": "nf", "issuer": issuer or ""},
        "issued_at": issue_stamp(),
    }
    if decision is not None:
        att["decision"] = dict(decision)
    att["envelope_digest"] = envelope_digest(att)
    return att


def _policy_digest_issues(decision: dict) -> list[str]:
    """policy_digest 须为 64 位小写十六进制。"""
    if re.fullmatch(r"[0-9a-f]{64}", str(decision.get("policy_digest") or "")):
        return []
    return ["decision.policy_digest 须为 64 位小写十六进制（修复指引：用 "
            "nf check --json 的 policy_digest）"]


def _object_digest_issues(decision: dict, member_digests) -> list[str]:
    """object_sha256 形状 +（给了成员摘要时）是否绑定到包内实体。"""
    obj = str(decision.get("object_sha256") or "")
    if not re.fullmatch(r"[0-9a-f]{64}", obj):
        return ["decision.object_sha256 须为 64 位小写十六进制"
                "（修复指引：用成员实体的 sha256）"]
    if member_digests is not None and obj not in set(member_digests):
        return ["decision.object_sha256 不在成员摘要里（决策未绑定到包内实体）"]
    return []


def decision_issues(decision: Any, member_digests: Any = None) -> list[str]:
    """决策证据块形状校验（fail-closed）；给 member_digests 时校验 object 在成员里。"""
    if not isinstance(decision, dict) or not decision:
        return ["decision 必须是非空对象（修复指引：见 docs/ccos/evidence-bundle-v0.md）"]
    issues: list[str] = []
    unknown = sorted(set(decision) - set(DECISION_FIELDS))
    if unknown:
        issues.append(f"decision 含未知字段：{', '.join(unknown)}"
                      f"（修复指引：只允许 {'/'.join(DECISION_FIELDS)}）")
    if decision.get("syscall") != "cc_check":
        issues.append("decision.syscall 只支持 cc_check（v0）（修复指引：换支持的调用）")
    issues += _policy_digest_issues(decision)
    if decision.get("verdict") not in ("ok",):
        issues.append("decision.verdict 只允许 ok（v0 只记录通过的判定）")
    issues += _object_digest_issues(decision, member_digests)
    return issues


def sign_hmac(att: Dict[str, Any], key: bytes) -> Dict[str, Any]:
    """本地密钥签发（stdlib hmac-sha256）——签名绑定信封摘要。"""
    if not key:
        raise ValueError("HMAC 签发需要非空密钥（修复指引：--key-file 指向密钥文件）")
    out = dict(att)
    mac = hmac.new(key, att["envelope_digest"].encode("utf-8"),
                   hashlib.sha256).hexdigest()
    out["signature"] = {"scheme": SCHEME_HMAC, "mac": mac,
                        "key_id": _sha256(key)[:16]}
    return out


def have_external_verifier(tool: str = "cosign") -> bool:
    """外挂锚验证器是否在场（Sigstore 锚 = 外部 CLI，不随 core 分发）。"""
    return shutil.which(tool) is not None


def _which(tool: str, purpose: str) -> str:
    """把外部 CLI 解析成**绝对路径**（逐行审查修正：裸名走 PATH 有 cwd 劫持面）。

    缺失 → ValueError（fail-closed，带可执行修复指引）。
    """
    exe = shutil.which(tool)
    if not exe:
        raise ValueError("%s 需要外部命令 %s，但 PATH 中找不到（修复指引：先安装 %s 后重试，"
                         "或改用 --key-file 的 hmac 级）" % (purpose, tool, tool))
    return exe


def verify_external(att: Dict[str, Any], tool: str = "cosign") -> Tuple[bool, List[str]]:
    """调用外部验证器校验 sigstore 锚；验证器缺失 → **拒绝**（不降级）。"""
    if not have_external_verifier(tool):
        return False, ["外挂锚验证器缺失（%s 未安装）→ fail-closed 拒绝，"
                       "不降级为 digest_only（修复指引：装 cosign 后重验，"
                       "或改用 --key-file 的 hmac 级）" % tool]
    sig = (att.get("signature") or {})
    bundle = sig.get("bundle")
    if not bundle or not os.path.exists(bundle):
        return False, ["外挂锚缺 bundle 实体（signature.bundle 指向不存在）"
                       "（修复指引：随 attestation 一并分发签名 bundle）"]
    try:
        proc = subprocess.run([shutil.which(tool) or tool, "verify-blob", "--bundle", bundle, bundle],  # nosec B404/B603/B607 —— 调用 ssh-keygen/git/hf（argv 列表、无 shell、路径经 which 解析）
                              capture_output=True, text=True, timeout=TOOL_TIMEOUT_S)
    except subprocess.TimeoutExpired:
        return False, ["外挂锚校验超时（%d s，%s 未返回）→ fail-closed 拒绝"
                       "（修复指引：确认验证器可用后重试；超时上限见 attest.TOOL_TIMEOUT_S）"
                       % (TOOL_TIMEOUT_S, tool)]
    if proc.returncode != 0:
        return False, ["外挂锚校验失败：%s" % (proc.stderr or proc.stdout).strip()[:300]]
    return True, []


def _subject_issues(subj: dict, root: str) -> Tuple[list, str]:
    """主体面校验 → (issues, level)；issues 为空表示无漂移。"""
    path = subj.get("path")
    if not path:
        return ["attestation 缺 subject.path"], "invalid"
    try:
        live = subject_of(path, root)
    except OSError as exc:
        return ["主体不可读：%s（%s）" % (path, exc)], "invalid"
    issues: List[str] = []
    for field in ("sha256", "bytes", "line_count"):
        if live.get(field) != subj.get(field):
            issues.append("主体漂移：%s 记录=%s 实测=%s"
                          % (field, subj.get(field), live.get(field)))
    return issues, "digest_only"


def _signature_issues(att: Dict[str, Any], key) -> Tuple[bool, List[str], str]:
    """签名面校验 → (ok, issues, level)。"""
    sig = att.get("signature")
    if not sig:
        return True, [], "digest_only"
    scheme = sig.get("scheme")
    if scheme == SCHEME_HMAC:
        if key is None:
            return False, ["缺密钥，无法校验 hmac 签名（修复指引：--key-file）"], "hmac-sha256"
        expect = hmac.new(key, att["envelope_digest"].encode("utf-8"),
                          hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expect, str(sig.get("mac") or "")):
            return False, ["hmac 签名不匹配（密钥不符或信封被改）"], "hmac-sha256"
        return True, [], "hmac-sha256"
    if scheme == SCHEME_SIGSTORE:
        ok, ext_issues = verify_external(att)
        return ok, ext_issues, "sigstore-keyless"
    return False, ["未知签名方案：%s（支持：%s / %s）"
                   % (scheme, SCHEME_HMAC, SCHEME_SIGSTORE)], "unsupported"


def verify(att: Dict[str, Any], root: str = ".",
           key: Optional[bytes] = None) -> Tuple[bool, List[str], str]:
    """校验 attestation → (ok, issues, level)。

    ok=False 一律表示「不可信」，绝不因缺证据而放行——本函数判的是**证据强度**，
    不是内容质量：「可复现」不等于「诚实」。
    """
    issues: List[str] = []
    if not isinstance(att, dict) or att.get("schema") != SCHEMA:
        return False, ["attestation schema 不匹配（期望 %s）" % SCHEMA], "invalid"
    subj = att.get("subject") or {}
    drift, level = _subject_issues(subj, root)
    if drift:
        return False, drift, level
    if att.get("envelope_digest") != envelope_digest(att):
        return False, ["信封摘要不一致（attestation 自身被改动）"], "digest_only"
    return _signature_issues(att, key)


def sign_digest_hmac(subject_digest: str, key: bytes, issuer: str = "") -> Dict[str, Any]:
    """对**已算好的内容摘要**签发 HMAC 锚（供馆藏条目等"摘要已在 frontmatter"的场景）。

    与 `sign_hmac`（签信封）区分：这里签的是条目规范摘要，锚可独立于信封存在。
    """
    if not key:
        raise ValueError("HMAC 签锚需要非空密钥（修复指引：--key-file <密钥文件>）")
    if not re.fullmatch(r"[0-9a-fA-F]{64}", (subject_digest or "").strip()):
        raise ValueError("待签摘要非法（修复指引：先算条目规范摘要，64 位十六进制）")
    mac = hmac.new(key, subject_digest.strip().lower().encode("utf-8"),
                   hashlib.sha256).hexdigest()
    return {"scheme": SCHEME_HMAC, "mac": mac, "key_id": _sha256(key)[:16],
            "issuer": issuer or ""}


def ssh_payload(subject_digest: str) -> bytes:
    """ssh-sig 的签名载荷（读者侧必须逐字重建同一字节序列）。"""
    return (SSH_PAYLOAD_PREFIX + (subject_digest or "").strip().lower() + "\n").encode("utf-8")
