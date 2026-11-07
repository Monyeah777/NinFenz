"""RFC 3161 timestamp records with offline token verification and fail-closed trust."""
from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import shutil
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from core import atomic_write, json_doc, json_schema

SCHEMA = "nf-time-token/1"
ROOT = Path(__file__).resolve().parents[3]
SCHEMA_REL = "protocol/schema/time_token.schema.json"
MAX_TOKEN_BYTES = 1 << 20
STAMP_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
GUIDE = "修复指引："


@dataclass
class CheckResult:
    ok: bool
    verdict: str
    issues: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    subject_sha256: str = ""
    query_sha256: str = ""
    token_sha256: str = ""
    ca_sha256: str = ""
    gen_time: str = ""
    serial: str = ""
    tsa: str = ""
    status: str = ""
    policy_oid: str = ""
    hash_algorithm: str = ""
    nonce: str = ""

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _failure(message: str) -> CheckResult:
    return CheckResult(False, "invalid", [message])


def openssl_path() -> str:
    explicit = os.environ.get("NF_OPENSSL", "").strip()
    if explicit:
        return explicit if Path(explicit).is_file() else ""
    return shutil.which("openssl") or ""


def _run(argv: list[str], timeout: float = 120.0) -> dict[str, Any]:
    from core.atoms import proc

    return proc.run_capture(argv, timeout=timeout)


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def schema_issues(doc: dict[str, Any]) -> list[str]:
    schema = json_doc.loads(
        atomic_write.read_text(ROOT / SCHEMA_REL), dict, what=SCHEMA_REL
    )
    return json_schema.json_schema_check(doc, schema)


def _read(path: str, label: str) -> tuple[bytes, str]:
    p = Path(path)
    if not p.is_file():
        raise ValueError(f"{label} 不存在：{path}（修复指引：提供实际文件路径）")
    data = atomic_write.read_bytes(p)
    if len(data) > MAX_TOKEN_BYTES and label in {"RFC3161 token", "RFC3161 query"}:
        raise ValueError(
            f"{label} 过大：{len(data)} 字节（修复指引：拒绝可疑输入）"
        )
    return data, _digest(data)


def _subject_digest(path: str) -> str:
    p = Path(path)
    if not p.is_file():
        raise ValueError(
            f"timestamp subject 不存在：{path}（修复指引：提供实际文件路径）"
        )
    digest = hashlib.sha256()
    try:
        with open(path, "rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as exc:
        raise ValueError(f"subject 读取失败：{exc}（{GUIDE}检查权限与文件状态）") from exc
    return digest.hexdigest()


def _write_external(out: str, argv: list[str]) -> None:
    target = Path(out)
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="nf_time_external_",
                                     dir=str(target.parent)) as tmpdir:
        tmp = Path(tmpdir) / target.name
        proc = _run([*argv, "-out", str(tmp)])
        if proc.get("code") != 0:
            detail = str(proc.get("err") or proc.get("out") or "未知错误").strip()
            raise ValueError(f"openssl 写盘失败：{detail}（{GUIDE}确认 OpenSSL 与输入可用）")
        atomic_write.write_bytes(target, tmp.read_bytes())


def make_query(subject: str, out: str = "") -> CheckResult:
    tool = openssl_path()
    if not tool:
        return _failure(
            "环境没有 openssl（修复指引：安装 OpenSSL 3.x 或设置 NF_OPENSSL）"
        )
    try:
        subject_sha = _subject_digest(subject)
    except ValueError as exc:
        return _failure(str(exc))
    destination = out or subject + ".tsq"
    argv = [tool, "ts", "-query", "-data", subject, "-sha256", "-cert"]
    try:
        _write_external(destination, argv)
        query, query_sha = _read(destination, "RFC3161 query")
    except (OSError, ValueError) as exc:
        return _failure(str(exc))
    result = CheckResult(True, "query", subject_sha256=subject_sha,
                         query_sha256=query_sha)
    result.warnings.append(f"query: {len(query)} bytes")
    return result


def submit(query_path: str, tsa_url: str, out: str = "",
           timeout: float = 30.0) -> CheckResult:
    parsed = urllib.parse.urlparse(tsa_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return _failure("TSA 地址必须是显式 http(s) URL（修复指引：提供 --tsa-url）")
    if parsed.scheme == "http" and parsed.hostname not in {"127.0.0.1", "::1", "localhost"}:
        return _failure(
            "公网 TSA 必须使用 HTTPS（修复指引：HTTP 只允许本机回环测试）"
        )
    try:
        query, query_sha = _read(query_path, "RFC3161 query")
    except ValueError as exc:
        return _failure(str(exc))
    request = urllib.request.Request(
        tsa_url,
        data=query,
        method="POST",
        headers={
            "Content-Type": "application/timestamp-query",
            "Accept": "application/timestamp-reply",
            "User-Agent": "NinFenz-RFC3161/1",
        },
    )
    try:
        with urllib.request.urlopen(  # nosec B310 - explicit HTTPS / loopback HTTP gate above
            request, timeout=max(1.0, float(timeout))
        ) as response:
            status = int(getattr(response, "status", 200))
            if status != 200:
                return _failure(f"TSA HTTP {status}（{GUIDE}检查上游状态后重试）")
            token = response.read(MAX_TOKEN_BYTES + 1)
    except (OSError, urllib.error.URLError) as exc:
        return _failure(f"TSA 请求失败：{exc}（{GUIDE}检查网络与 --tsa-url）")
    if not token:
        return _failure(f"TSA 返回空响应（{GUIDE}换 TSA 或稍后重试）")
    if len(token) > MAX_TOKEN_BYTES:
        return _failure(f"TSA 响应过大（{GUIDE}拒绝超过 {MAX_TOKEN_BYTES} 字节的 token）")
    destination = out or query_path + ".tsr"
    try:
        atomic_write.write_bytes(destination, token)
    except OSError as exc:
        return _failure(f"token 写盘失败：{exc}（{GUIDE}检查目标目录权限）")
    return CheckResult(True, "submitted", query_sha256=query_sha,
                       token_sha256=_digest(token))


def _normalize_stamp(raw: str) -> str:
    text = raw.strip()
    if STAMP_RE.match(text):
        return text
    for fmt in ("%b %d %H:%M:%S %Y GMT", "%b  %d %H:%M:%S %Y GMT"):
        try:
            from datetime import datetime

            return datetime.strptime(text, fmt).strftime("%Y-%m-%dT%H:%M:%SZ")
        except ValueError:
            continue  # 依次尝试 OpenSSL 的空格宽度变体；都不中返回空并由调用方 fail-closed
    return ""


def _parse_reply(text: str) -> dict[str, str]:
    parsed = {
        "gen_time": "", "serial": "", "tsa": "", "status": "",
        "policy_oid": "", "hash_algorithm": "", "nonce": "",
    }
    for line in text.splitlines():
        low = line.lower()
        if "time stamp:" in low and not parsed["gen_time"]:
            parsed["gen_time"] = _normalize_stamp(line.split(":", 1)[1])
        elif "serial number:" in low and not parsed["serial"]:
            parsed["serial"] = line.split(":", 1)[1].strip()
        elif low.startswith("tsa:") and not parsed["tsa"]:
            parsed["tsa"] = line.split(":", 1)[1].strip()
        elif low.startswith("status:") and not parsed["status"]:
            parsed["status"] = line.split(":", 1)[1].strip()
        elif low.startswith("policy oid:") and not parsed["policy_oid"]:
            parsed["policy_oid"] = line.split(":", 1)[1].strip()
        elif low.startswith("hash algorithm:") and not parsed["hash_algorithm"]:
            parsed["hash_algorithm"] = line.split(":", 1)[1].strip()
        elif low.startswith("nonce:") and not parsed["nonce"]:
            parsed["nonce"] = line.split(":", 1)[1].strip()
    return parsed


def _verify_command(argv: list[str]) -> tuple[bool, str]:
    proc = _run(argv)
    detail = ((proc.get("err") or "") + "\n" + (proc.get("out") or "")).strip()
    if proc.get("code") != 0:
        last = detail.splitlines()[-1][:180] if detail else "无输出"
        return False, last
    return True, detail


def verify(subject: str, query: str, token: str, ca_file: str,
           untrusted: str = "") -> CheckResult:
    tool = openssl_path()
    if not tool:
        return _failure(
            "环境没有 openssl（修复指引：安装 OpenSSL 3.x 或设置 NF_OPENSSL）"
        )
    if not ca_file or not Path(ca_file).is_file():
        return _failure(f"缺信任锚 --ca-file（{GUIDE}显式提供 TSA 根/中间证书）")
    try:
        subject_sha = _subject_digest(subject)
        _query, query_sha = _read(query, "RFC3161 query")
        token_bytes, token_sha = _read(token, "RFC3161 token")
        ca_bytes, ca_sha = _read(ca_file, "trust anchor")
    except ValueError as exc:
        return _failure(str(exc))
    del _query, token_bytes, ca_bytes
    common = [tool, "ts", "-verify", "-in", token, "-CAfile", ca_file]
    if untrusted:
        common += ["-untrusted", untrusted]
    ok_query, detail_query = _verify_command([*common, "-queryfile", query])
    ok_data, _detail_data = _verify_command([*common, "-data", subject])
    if not ok_query or not ok_data:
        return _failure(
            "时间戳绑定或签名校验不过"
            f"（{GUIDE}确认 subject/query/token 同源并换正确 CA；{detail_query}）"
        )
    reply = _run([tool, "ts", "-reply", "-in", token, "-text"])
    parsed = _parse_reply(str(reply.get("out") or "") + str(reply.get("err") or ""))
    if not STAMP_RE.match(parsed["gen_time"]):
        return _failure(f"token 缺可用 genTime（{GUIDE}换 TSA 或重签）")
    if "granted" not in parsed["status"].lower():
        return _failure(
            f"TSA 未批准该请求：{parsed['status'] or '缺失'}"
            f"（{GUIDE}换 TSA 或检查摘要算法）"
        )
    if parsed["hash_algorithm"].lower() != "sha256":
        return _failure(
            f"token 摘要算法不是 sha256：{parsed['hash_algorithm'] or '缺失'}"
            f"（{GUIDE}重新生成 SHA-256 请求）"
        )
    if not parsed["policy_oid"] or not parsed["nonce"]:
        return _failure(
            f"token 缺 policy OID 或 nonce（{GUIDE}检查 TSA 是否返回完整 TSTInfo）"
        )
    return CheckResult(
        True,
        "tsa",
        warnings=[
            "时间戳只证明该摘要在 genTime 已存在；不证明内容质量或签发方身份",
        ],
        subject_sha256=subject_sha,
        query_sha256=query_sha,
        token_sha256=token_sha,
        ca_sha256=ca_sha,
        gen_time=parsed["gen_time"],
        serial=parsed["serial"],
        tsa=parsed["tsa"],
        status=parsed["status"],
        policy_oid=parsed["policy_oid"],
        hash_algorithm=parsed["hash_algorithm"],
        nonce=parsed["nonce"],
    )


def record_doc(subject: str, query: str, token: str, ca_file: str,
               untrusted: str = "") -> dict[str, Any]:
    checked = verify(subject, query, token, ca_file, untrusted)
    if not checked.ok:
        raise ValueError("不能记录未验证 token：" + "；".join(checked.issues))
    query_bytes, _query_sha = _read(query, "RFC3161 query")
    token_bytes, _token_sha = _read(token, "RFC3161 token")
    doc = {
        "schema": SCHEMA,
        "subject": {"name": Path(subject).name, "sha256": checked.subject_sha256},
        "query": {
            "name": Path(query).name,
            "sha256": checked.query_sha256,
            "der_base64": base64.b64encode(query_bytes).decode("ascii"),
        },
        "token": {
            "name": Path(token).name,
            "sha256": checked.token_sha256,
            "der_base64": base64.b64encode(token_bytes).decode("ascii"),
        },
        "trust_anchor": {"name": Path(ca_file).name, "sha256": checked.ca_sha256},
        "tsa_result": {
            "gen_time": checked.gen_time,
            "serial": checked.serial,
            "tsa": checked.tsa,
            "status": checked.status,
            "policy_oid": checked.policy_oid,
            "hash_algorithm": checked.hash_algorithm,
            "nonce": checked.nonce,
        },
        "note": "token/query 随记录分发；信任锚必须由消费方独立提供",
    }
    issues = schema_issues(doc)
    if issues:
        raise ValueError("时间记录 schema 校验失败：" + "；".join(issues))
    return doc


def write_record(subject: str, query: str, token: str, ca_file: str,
                 untrusted: str = "", out: str = "") -> dict[str, Any]:
    doc = record_doc(subject, query, token, ca_file, untrusted)
    if out:
        atomic_write.write_text(
            out, json.dumps(doc, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        )
    return doc


def verify_record(subject: str, record: dict[str, Any], ca_file: str,
                  untrusted: str = "") -> CheckResult:
    if not isinstance(record, dict) or record.get("schema") != SCHEMA:
        return _failure(f"时间记录 schema 不匹配（{GUIDE}使用 {SCHEMA}）")
    issues = schema_issues(record)
    if issues:
        return CheckResult(False, "invalid", issues=issues)
    try:
        for key in ("query", "token"):
            encoded = record.get(key, {}).get("der_base64")
            if not isinstance(encoded, str) or len(encoded) > 1398104:
                raise ValueError(f"{key}.der_base64 缺失或过大")
        subject_sha = _subject_digest(subject)
        ca_bytes, ca_sha = _read(ca_file, "trust anchor")
        query = base64.b64decode(str(record["query"]["der_base64"]), validate=True)
        token = base64.b64decode(str(record["token"]["der_base64"]), validate=True)
    except (KeyError, TypeError, ValueError) as exc:
        return _failure(f"时间记录字段缺失或编码非法：{exc}（{GUIDE}重建记录）")
    issues: list[str] = []
    if record.get("subject", {}).get("sha256") != subject_sha:
        issues.append(f"subject 摘要不符（{GUIDE}换正确 subject 或重建记录）")
    if record.get("query", {}).get("sha256") != _digest(query):
        issues.append(f"query 摘要不符（{GUIDE}重建记录，禁止手改 DER）")
    if record.get("token", {}).get("sha256") != _digest(token):
        issues.append(f"token 摘要不符（{GUIDE}重建记录，禁止手改 DER）")
    if record.get("trust_anchor", {}).get("sha256") != ca_sha:
        issues.append(f"trust_anchor 摘要不符（{GUIDE}提供签发该 token 的 CA）")
    if issues:
        return CheckResult(False, "invalid", issues=issues, subject_sha256=subject_sha)
    del ca_bytes
    with tempfile.TemporaryDirectory(prefix="nf_time_record_") as tmp:
        query_path = Path(tmp) / "query.tsq"
        token_path = Path(tmp) / "token.tsr"
        query_path.write_bytes(query)
        token_path.write_bytes(token)
        checked = verify(subject, str(query_path), str(token_path), ca_file, untrusted)
    expected = record.get("tsa_result") or {}
    for key, actual in (
        ("gen_time", checked.gen_time),
        ("serial", checked.serial),
        ("policy_oid", checked.policy_oid),
        ("hash_algorithm", checked.hash_algorithm),
        ("nonce", checked.nonce),
    ):
        if checked.ok and str(expected.get(key) or "") != actual:
            checked.ok = False
            checked.verdict = "invalid"
            checked.issues.append(f"{key} 与记录不符（{GUIDE}重建记录）")
    return checked
