"""外部验签的 provenance 检查（SLSA L3 —— Non-falsifiable provenance）。

为什么补（设计文档 §3.2 能力空洞 P0）：本仓有 `nf attest` 与 `protocol/RECEIPTS.json`，但
**同进程自签自验**按 SLSA 口径不构成「不可伪造」——签名方就是验签方，篡改者只需要改同一个
进程里的代码。本检查证明两件可证的事实，缺一即红：

1. **验签能在生成进程之外执行**：把 attestation 交给**独立子进程**验（只读 JSON + 密钥）；
2. **验签对篡改敏感**：把主体摘要改一位后，同一子进程必须**拒绝**——否则这条对账是空转。

诚实边界（写进成功文案而不是藏起来）：仓库自身 RECEIPTS 目前**没有签名外锚**（cosign 不在场），
本检查证明的是「外部验签机制可用且能红」，不是「本仓 provenance 已经不可伪造」。
外锚一旦就位，同一检查会自动把它纳入（`attest.verify` 支持 sigstore-keyless）。
"""
from __future__ import annotations

import copy
import json
import os
import secrets
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

from core import attest

RECEIPTS_REL = "protocol/RECEIPTS.json"
RECEIPTS_SCHEMA = "nf-receipts/1"
#: 子进程验签脚本：只依赖 sys.path 上的 core.attest，输入走 stdin（密钥不进 argv）。
_VERIFIER_SRC = r"""
import json
import sys
from core import attest
payload = json.load(sys.stdin)
ok, issues, level = attest.verify(payload["att"], payload["root"],
                                  key=bytes.fromhex(payload["key_hex"]))
print(json.dumps({"ok": bool(ok), "issues": issues, "level": level}, ensure_ascii=False))
sys.exit(0 if ok else 1)
"""

Verifier = Callable[[dict[str, object]], bool]


def receipts_issues(root: Path) -> list[str]:
    """回执单根自身的形状（机制在场的前提）。"""
    path = root / RECEIPTS_REL
    if not path.is_file():
        return ["缺 %s（修复指引：跑 nf receipts --scope protocol --write 生成回执单根）"
                % RECEIPTS_REL]
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return ["%s 不可解析：%s（修复指引：重新生成回执单根）" % (RECEIPTS_REL, exc)]
    issues: list[str] = []
    if not isinstance(doc, dict) or doc.get("schema") != RECEIPTS_SCHEMA:
        issues.append("%s schema 不是 %s（修复指引：重新生成回执单根，别手改）"
                      % (RECEIPTS_REL, RECEIPTS_SCHEMA))
        return issues
    entries = doc.get("entries") or []
    root_hex = str(doc.get("root") or "")
    if not isinstance(entries, list) or not entries:
        issues.append("%s 没有任何回执条目（修复指引：确认 protocol 面有可回执的机读产物）"
                      % RECEIPTS_REL)
    if len(root_hex) != 64 or any(ch not in "0123456789abcdef" for ch in root_hex):
        issues.append("%s 的 root 不是 64 位十六进制（修复指引：重新生成回执单根）"
                      % RECEIPTS_REL)
    if isinstance(entries, list) and doc.get("count") != len(entries):
        issues.append("%s 的 count 与 entries 条数不一致（修复指引：重新生成回执单根）"
                      % RECEIPTS_REL)
    return issues


def _payload(att: dict[str, object], root: str, key: bytes) -> dict[str, object]:
    return {"att": att, "root": root, "key_hex": key.hex()}


def run_verifier(payload: dict[str, object]) -> bool:
    """默认验签器：**独立子进程**跑 core.attest.verify（本检查的全部意义所在）。"""
    src_dir = str(Path(__file__).resolve().parents[1])
    env = dict(os.environ)
    env["PYTHONPATH"] = src_dir + (os.pathsep + env["PYTHONPATH"]
                                   if env.get("PYTHONPATH") else "")
    try:
        proc = subprocess.run(  # nosec B603 - argv 列表、无 shell
            [sys.executable, "-c", _VERIFIER_SRC],
            input=json.dumps(payload, ensure_ascii=False),
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            env=env, cwd=str(payload.get("root") or "."), timeout=120,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return proc.returncode == 0


def scan(root: str = ".", verifier: Verifier | None = None
         ) -> tuple[list[str], dict[str, object]]:
    """→ (issues, stats)。

    verifier 可注入（单测用来证明「篡改没被检出」也会红）；缺省走独立子进程。
    """
    r = Path(root)
    issues: list[str] = receipts_issues(r)
    if issues:
        return issues, {"verified": False}
    check = verifier or run_verifier
    key = secrets.token_bytes(32)
    signed = attest.sign_hmac(attest.build(RECEIPTS_REL, str(r), issuer="check42"), key)
    tampered = copy.deepcopy(signed)
    subject = tampered.get("subject") or {}
    sealed = str(subject.get("sha256") or "")
    subject["sha256"] = ("0" * 64) if sealed != "0" * 64 else ("1" * 64)
    ok_real = check(_payload(signed, str(r), key))
    ok_tampered = check(_payload(tampered, str(r), key))
    if not ok_real:
        issues.append("独立进程验签失败：真件的 hmac 级 attestation 在子进程里验不过"
                      "（修复指引：确认 nf attest 的 --key-file 口径与 core.attest.verify 一致）")
    if ok_tampered:
        issues.append("篡改未被检出：改掉主体摘要后子进程仍判通过——这条对账是空转"
                      "（修复指引：确认验签真的比对 subject 摘要，不是只看信封）")
    stats: dict[str, object] = {"verified": True, "tamper_detected": not ok_tampered,
                                "external_anchor": attest.have_external_verifier(),
                                "level": "hmac-sha256"}
    return issues, stats
