"""evidence · _selfcheck（自 evidence.py 拆出；只移动代码，行为/文案不变）。"""
from __future__ import annotations

import hashlib
import io
import os
import tempfile
import zipfile
from typing import Any

from ._build import (
    _zip_bytes,
    build,
)
from ._const import (
    GUIDE,
    PAYLOAD_DIR,
    REVOCATION_SCHEMA,
)
from ._verify_forms import (
    verify,
)

# ------------------------------------------------------------------ 机制自检

def _selfcheck_bundle(tmp: str, pin: str, **kw: Any) -> bytes:
    data, _info = build(tmp, ["d/subject.md"], issuer="selfcheck", created_at=pin, **kw)
    return data




def _selfcheck_tamper(tmp: str, data: bytes) -> tuple[str, str]:
    """改成员一字节 → 必红；返回 (verdict, 该成员摘要)。"""
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        members = {n: zf.read(n) for n in zf.namelist()}
    payload = PAYLOAD_DIR + "d/subject.md"
    digest = hashlib.sha256(members[payload]).hexdigest()
    members[payload] = b"# subject\n\n-body-X\n"
    path = os.path.join(tmp, "tampered.zip")
    with open(path, "wb") as fh:
        fh.write(_zip_bytes(list(members.items())))
    return verify(path)["verdict"], digest




def _selfcheck_revoked(tmp: str, digest: str) -> str:
    """吊销表命中 → 必判 revoked。"""
    rev = {"schema": REVOCATION_SCHEMA,
           "revoked": [{"digest": digest, "revoked_at": "2026-01-01T00:00:00Z",
                        "reason": "selfcheck"}]}
    return verify(os.path.join(tmp, "b.zip"), revocations=rev)["verdict"]




def selfcheck() -> tuple[bool, list[str], dict[str, Any]]:
    """机制体检：PASS 必过、改一字节必红、吊销必判 revoked、过期必判 expired。

    抓不到篡改的校验器就是摆设——这里用**自造夹具**跑四种判定，不依赖仓库内容。
    """
    issues: list[str] = []
    stats: dict[str, Any] = {}
    with tempfile.TemporaryDirectory(prefix="nf_evself_") as tmp:
        os.makedirs(os.path.join(tmp, "d"), exist_ok=True)
        with open(os.path.join(tmp, "d", "subject.md"), "wb") as fh:
            fh.write(b"# subject\n\n-body-\n")
        pin = "2026-01-01T00:00:00Z"      # 固定签发时刻：测的是**打包确定性**，不是墙钟
        data = _selfcheck_bundle(tmp, pin)
        bundle = os.path.join(tmp, "b.zip")
        with open(bundle, "wb") as fh:
            fh.write(data)
        res = verify(bundle)
        stats["pack"] = {"root": res["root"], "head": res["head"], "count": res["count"],
                         "level": res["level"], "created_at": res["created_at"]}
        if res["verdict"] != "ok":
            issues.append(f"自造证据包未通过校验：{'；'.join(res['issues'])}"
                          f"（{GUIDE}请先修 pack/verify 一侧）")
        stats["ok"] = {"verdict": res["verdict"], "level": res["level"],
                       "count": res["count"]}
        if _selfcheck_bundle(tmp, pin) != data:
            issues.append("两次打包不逐字节一致（" + GUIDE + "打包须确定性——请固定时间戳与"
                          "成员序，否则证据不可复算）")
        tam, digest = _selfcheck_tamper(tmp, data)
        if tam != "invalid":
            issues.append(f"篡改未被判否（实得 {tam}）（{GUIDE}摘要/根校验失效——证据是摆设，"
                          "请先修校验路径）")
        stats["tamper"] = tam
        rev = _selfcheck_revoked(tmp, digest)
        if rev != "revoked":
            issues.append(f"吊销未判 revoked（实得 {rev}）（{GUIDE}吊销表命中必须压过 ok，"
                          "请先修判定顺序）")
        stats["revoked"] = rev
        exp = _selfcheck_bundle(tmp, pin, expires_at="2020-01-01T00:00:00Z")
        exp_path = os.path.join(tmp, "expired.zip")
        with open(exp_path, "wb") as fh:
            fh.write(exp)
        ex = verify(exp_path)["verdict"]
        if ex != "expired":
            issues.append(f"过期未判 expired（实得 {ex}）（{GUIDE}时效判定须在证据有效之后"
                          "执行，请先修判定顺序）")
        stats["expired"] = ex
    return not issues, issues, stats
