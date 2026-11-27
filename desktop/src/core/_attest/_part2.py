"""core.attest 私有实现分片 2/2（对外只经 core.attest 门面导入）：sign_digest_ssh 等"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import subprocess
from typing import Any, Dict, List, Optional, Tuple

from ._part1 import (
    SCHEME_HMAC,
    SCHEME_SIGSTORE,
    SCHEME_SSH,
    SSH_NAMESPACE,
    TOOL_TIMEOUT_S,
    _sha256,
    _which,
    have_external_verifier,
    ssh_payload,
)


def sign_digest_ssh(subject_digest: str, key_path: str, identity: str,
                    ns: str = SSH_NAMESPACE, workdir: str = "") -> Dict[str, Any]:
    """用 `ssh-keygen -Y sign` 对摘要载荷签名（真实非对称签名，读者侧只需 ssh-keygen）。"""
    if not have_external_verifier("ssh-keygen"):
        raise ValueError("缺 ssh-keygen → 无法签发 ssh-sig 锚（fail-closed，不做假锚）"
                         "（修复指引：安装 OpenSSH 或改用 --key-file 的 hmac 级）")
    # `~` 展开：文档示例写的是 `--ssh-key ~/.ssh/id_ed25519`，而 Python 不会自动展开 `~`
    # （实测：私有键就在家目录也被判「不存在」）。此处按 shell 语义补上。
    key_path = os.path.expanduser(str(key_path))
    if not os.path.isfile(key_path):
        raise ValueError("签名私钥不存在：%s（修复指引：--ssh-key <私钥路径>；"
                         "`~` 会被展开到家目录，也可给绝对/相对路径）" % key_path)
    if not identity.strip():
        raise ValueError("ssh-sig 需要身份标识（修复指引：--ssh-identity <principal>）")
    import tempfile

    base = workdir or tempfile.mkdtemp(prefix="nf_ssh_")
    os.makedirs(base, exist_ok=True)
    payload_path = os.path.join(base, "payload.txt")
    with open(payload_path, "wb") as fh:
        fh.write(ssh_payload(subject_digest))
    # stdin=DEVNULL：密钥若带口令，ssh-keygen 会等输入（实测会挂住）——
    # 这里让它**快速失败**而不是阻塞调用方。
    try:
        proc = subprocess.run([_which("ssh-keygen", "ssh-sig 签名"),  # nosec B404/B603/B607 —— 调用 ssh-keygen/git/hf（argv 列表、无 shell、路径经 which 解析）
                               "-Y", "sign", "-f", key_path, "-n", ns,
                               payload_path], capture_output=True, text=True,
                              stdin=subprocess.DEVNULL, timeout=TOOL_TIMEOUT_S)
    except subprocess.TimeoutExpired as exc:
        raise ValueError("ssh-keygen 签名超时（%d s 未返回；修复指引：确认私钥可用、不带交互口令，"
                         "或改用 --key-file 的 hmac 级）" % TOOL_TIMEOUT_S) from exc
    if proc.returncode != 0:
        raise ValueError("ssh-keygen 签名失败：%s"
                         % (proc.stderr or proc.stdout).strip()[:200])
    sig = payload_path + ".sig"
    if not os.path.isfile(sig):
        raise ValueError("ssh-keygen 未产出签名文件（修复指引：检查 ssh-keygen 版本 ≥8.9）")
    pub = key_path + ".pub"
    fingerprint = ""
    if os.path.isfile(pub):
        fp = None
        try:
            fp = subprocess.run([_which("ssh-keygen", "ssh-sig 指纹"), "-lf", pub],  # nosec B404/B603/B607 —— 调用 ssh-keygen/git/hf（argv 列表、无 shell、路径经 which 解析）
                                capture_output=True, text=True, timeout=TOOL_TIMEOUT_S)
        except subprocess.TimeoutExpired:
            # 指纹是**信息字段**（签名本体已产出并可分发）：超时即留空，不因它拖挂整条签名
            # 流程——但也不假装取到了（字段留空本身即如实表达「未取到」）。
            fp = None
        if fp is not None and fp.returncode == 0 and fp.stdout.split():
            fingerprint = fp.stdout.split()[1]
    return {"scheme": SCHEME_SSH, "ns": ns, "identity": identity.strip(),
            "sig_file": sig, "fingerprint": fingerprint,
            "payload_sha256": _sha256(ssh_payload(subject_digest))}


def verify_ssh_anchor(subject_digest: str, anchor: Dict[str, Any],
                      allowed_signers: str, identity: str) -> Tuple[bool, List[str]]:
    """`ssh-keygen -Y verify` 校验 ssh-sig 锚；缺验证器/缺 allowed_signers 一律拒绝。"""
    if not have_external_verifier("ssh-keygen"):
        return False, ["缺 ssh-keygen → ssh-sig 锚不可校验（fail-closed）"]
    if not allowed_signers or not os.path.isfile(allowed_signers):
        return False, ["缺 allowed_signers（修复指引：--ssh-allowed-signers <文件>；"
                       "格式 `<身份> <公钥>`）"]
    sig_file = anchor.get("sig_file") or ""
    if not sig_file or not os.path.isfile(sig_file):
        return False, ["缺签名文件实体：%s（修复指引：随锚一并分发 .sig 文件）" % sig_file]
    ns = str(anchor.get("ns") or SSH_NAMESPACE)
    ident = identity or str(anchor.get("identity") or "")
    if not ident:
        return False, ["缺验签身份（修复指引：--ssh-identity <principal>）"]
    # 注意：必须按**字节**喂 stdin——Windows 文本模式会把 \n 翻成 \r\n，
    # 导致验签载荷与签名时不一致（实测踩过：incorrect signature）。
    try:
        exe = _which("ssh-keygen", "ssh-sig 验签")
    except ValueError as exc:
        return False, [str(exc)]
    try:
        proc = subprocess.run([exe, "-Y", "verify", "-f", allowed_signers,  # nosec B404/B603/B607 —— 调用 ssh-keygen/git/hf（argv 列表、无 shell、路径经 which 解析）
                               "-I", ident, "-n", ns, "-s", sig_file],
                              input=ssh_payload(subject_digest),
                              capture_output=True, timeout=TOOL_TIMEOUT_S)
    except subprocess.TimeoutExpired:
        return False, ["ssh-sig 校验超时（%d s，ssh-keygen 未返回）→ fail-closed 拒绝"
                       "（修复指引：确认 ssh-keygen 可用后重试）" % TOOL_TIMEOUT_S]
    out = (proc.stderr or proc.stdout or b"").decode("utf-8", "replace").strip()[:200]
    if proc.returncode != 0:
        return False, ["ssh-sig 校验失败：%s" % out]
    return True, []


def verify_digest_anchor(subject_digest: str, anchor: Dict[str, Any],
                         key: Optional[bytes] = None,
                         ssh_ctx: Optional[Dict[str, str]] = None
                         ) -> Tuple[bool, List[str], str]:
    """校验摘要锚 → (ok, issues, level)；缺验证器一律 fail-closed（不静默放行）。

    ssh_ctx = {"allowed_signers": <path>, "identity": <principal>}
    """
    scheme = (anchor or {}).get("scheme")
    if not scheme:
        return False, ["锚缺 scheme（修复指引：nf library attest <编号> --key-file <密钥>）"], "none"
    if scheme == SCHEME_HMAC:
        if key is None:
            return False, ["锚为 hmac 级但未提供密钥 → 无法校验"
                           "（修复指引：--key-file <同一密钥>）"], "hmac-sha256"
        expect = hmac.new(key, (subject_digest or "").strip().lower().encode("utf-8"),
                          hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expect, str(anchor.get("mac") or "")):
            return False, ["hmac 锚不匹配（密钥不符，或内容/摘要已改）"], "hmac-sha256"
        return True, [], "hmac-sha256"
    if scheme == SCHEME_SSH:
        ctx = ssh_ctx or {}
        ok, issues = verify_ssh_anchor(subject_digest, anchor,
                                      ctx.get("allowed_signers", ""),
                                      ctx.get("identity", ""))
        return ok, issues, "ssh-sig"
    if scheme == SCHEME_SIGSTORE:
        return False, ["sigstore 锚需外部验证器，当前不可校验"
                       "（修复指引：装 cosign 后重验，或改用 hmac / ssh-sig 锚）"
                           ""], "sigstore-keyless"
    return False, ["未知锚方案：%s（支持：%s / %s / %s）"
                   % (scheme, SCHEME_HMAC, SCHEME_SSH, SCHEME_SIGSTORE)], "unsupported"


def read_key_file(path: str) -> bytes:
    """读本地签名密钥（调用方负责权限；空文件视为无效）。"""
    with open(path, "rb") as fh:
        key = fh.read().strip()
    if not key:
        raise ValueError("密钥文件为空：%s（修复指引：写入 ≥16 字节随机密钥）" % path)
    return key


def dumps(att: Dict[str, Any]) -> str:
    """稳定序列化（便于入仓/分发对照）。"""
    return json.dumps(att, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
