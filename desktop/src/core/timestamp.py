"""RFC 3161 可信时间戳（G3 的可落地半边）：向 TSA 申请 token，并离线校验它。

为什么（2026-11-07）：时效判据此前只吃本机时钟——回拨就能把「已过期」变「未过期」，我们只能
如实标注 time_proof=none。现在接外部时间权威：token 由 TSA 签发、绑定被证数据的摘要，
校验的时候不需要联网、不需要 TSA 在线，只需要 TSA 的证书链（信任锚）。

依赖与边界（诚实写清）：
- 只用 openssl 命令行（ts -query / ts -verify），不自己实现 DER/ASN.1；openssl 不在时
  相关命令 fail-closed 并给出指引（不降级成「本机时钟也算」）。
- 信任锚是调用方给的 CA 文件（本仓在文档里给用法，不预置根证书——预置等于替用户做信任决定）。
- 本模块只证「这份字节在 gen_time 那一刻已经存在」；不证内容质量、不证签发方身份。
- 时间戳绑定的是数据字节的 sha256：调用方要自己保证 subject_sha256 与实际数据一致。
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import json
import os
import re
import shutil
import sys
from pathlib import Path
from typing import Any

SCHEMA = "nf-time-token/1"
GUIDE = "修复指引："
TSA_DEFAULT = "http://timestamp.digicert.com"
STAMP_RE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$")
MAX_TOKEN_BYTES = 1 << 20


def openssl_path() -> str:
    """openssl 可执行文件路径；不在场返回空串（调用方 fail-closed）。"""
    return shutil.which("openssl") or ""


def _run(argv: list[str], timeout: float = 120.0) -> dict:
    """跑一条固定 argv 的外部命令（受控进程原子；无 shell）。"""
    here = str(Path(__file__).resolve().parents[1])
    if here not in sys.path:
        sys.path.insert(0, here)
    from core.atoms import proc as proc_atom
    return proc_atom.run_capture(argv, timeout=timeout)


def subject_digest(data: bytes) -> str:
    """被证数据的 sha256（时间戳绑定的是它）。"""
    return hashlib.sha256(data).hexdigest()


def make_query(path: str, out: str = "") -> tuple[str, str]:
    """为文件生成 RFC 3161 时间戳请求（DER）→ (tsq 路径, 空串或错误)。"""
    tool = openssl_path()
    if not tool:
        return "", ("环境没有 openssl（" + GUIDE + "装 openssl 后再用时间戳；本仓不提供纯 Python "
                    "的 DER/ASN.1 实现，也不把本机时钟当可信时间）")
    dest = out or str(path) + ".tsq"
    proc = _run([tool, "ts", "-query", "-data", str(path), "-sha256", "-cert", "-out", dest])
    if proc.get("code") != 0:
        return "", (f"生成时间戳请求失败（{proc.get('err') or proc.get('out') or '未知错误'}）"
                    f"（{GUIDE}确认文件可读、openssl 版本不低于 1.1）")
    return dest, ""


def submit(query_path: str, url: str = "", out: str = "", timeout: int = 30) -> tuple[str, str]:
    """把请求发给 TSA，收下响应（DER）→ (tsr 路径, 空串或错误)。

    用 curl 发 POST（Content-Type: application/timestamp-query）；不引入 HTTP 客户端依赖，
    也不接受非 http(s) 的地址——避免「时间戳」变成随便一个内网服务的自说自话。
    """
    target = (url or TSA_DEFAULT).strip()
    if not (target.startswith("http://") or target.startswith("https://")):
        return "", ("TSA 地址必须是 http(s)（" + GUIDE + "如 http://timestamp.digicert.com）")
    curl = shutil.which("curl")
    if not curl:
        return "", ("环境没有 curl（" + GUIDE + "装 curl，或用其它工具把 .tsq 提交给 TSA，"
                    "再把响应存成 .tsr）")
    dest = out or str(query_path) + ".tsr"
    proc = _run([curl, "-sS", "-m", str(max(5, int(timeout))),
                 "-H", "Content-Type: application/timestamp-query",
                 "--data-binary", "@" + str(query_path), target, "-o", dest], timeout + 30)
    if proc.get("code") != 0:
        return "", (f"TSA 请求失败（{proc.get('err') or proc.get('out') or '未知错误'}）"
                    f"（{GUIDE}确认网络可到 {target}；离线环境请把请求交给有网的机器）")
    try:
        size = os.path.getsize(dest)
    except OSError:
        return "", ("TSA 没落盘响应（" + GUIDE + "重试或换一个 TSA）")
    if size == 0:
        return "", ("TSA 返回空响应（" + GUIDE + "换一个 TSA 或稍后重试）")
    if size > MAX_TOKEN_BYTES:
        return "", (f"TSA 响应过大（{size} 字节）（{GUIDE}拒绝可疑响应）")
    return dest, ""


def _normalize_stamp(raw: str) -> str:
    """openssl 打印的是 RFC 822 风格（Nov  7 10:01:50 2026 GMT）→ ISO 秒级 UTC。

    统一成 ISO 是为了能和证据包的 expires_at / --at 直接做字符串比较（同一口径、不引时区库）。
    """
    text = (raw or "").strip()
    if STAMP_RE.match(text):
        return text
    for fmt in ("%b %d %H:%M:%S %Y GMT", "%b  %d %H:%M:%S %Y GMT"):
        try:
            return _dt.datetime.strptime(text, fmt).strftime("%Y-%m-%dT%H:%M:%SZ")
        except ValueError:  # 为什么可以吞：两种空格宽度是多来源格式差异（单/双空格），
            continue        # 都不匹配就返回空串由调用方判 invalid——不是丢证据
    return ""


def _parse_text(text: str) -> dict[str, Any]:
    """从 ts -reply -text 里抽关键字段（genTime / serial / TSA / status）。"""
    out: dict[str, Any] = {"gen_time": "", "serial": "", "tsa": "", "status": ""}
    for line in text.splitlines():
        low = line.lower()
        if "time stamp:" in low and not out["gen_time"]:
            out["gen_time"] = _normalize_stamp(line.split(":", 1)[1])
        elif "serial number:" in low and not out["serial"]:
            out["serial"] = line.split(":", 1)[1].strip()
        elif low.startswith("tsa:") and not out["tsa"]:
            out["tsa"] = line.split(":", 1)[1].strip()
        elif low.startswith("status:") and not out["status"]:
            out["status"] = line.split(":", 1)[1].strip()
    return out


def verify(token_path: str, query_path: str, ca_file: str = "",
           untrusted: str = "") -> dict[str, Any]:
    """离线校验时间戳响应 → {ok, verdict, gen_time, serial, tsa, issues, warnings}。

    ca_file 是信任锚（TSA 根/中间证书）；不给就 fail-closed（不猜）。
    """
    res: dict[str, Any] = {"ok": False, "verdict": "invalid", "gen_time": "", "serial": "",
                           "tsa": "", "issues": [], "warnings": []}
    tool = openssl_path()
    if not tool:
        res["issues"].append("环境没有 openssl（" + GUIDE + "装 openssl 后再校验时间戳；"
                             "没有它就无法验证 TSA 签名，本仓不会假装验过）")
        return res
    if not ca_file or not os.path.isfile(ca_file):
        res["issues"].append("缺信任锚 --ca-file（" + GUIDE + "给 TSA 的根/中间证书 PEM；"
                             "不给信任锚就没法判断这个 token 是谁签的）")
        return res
    if not os.path.isfile(token_path) or not os.path.isfile(query_path):
        res["issues"].append("缺 token 或请求文件（" + GUIDE + "两者都要：token 由 TSA 返回、"
                             "请求是文件原始摘要的来源）")
        return res
    argv = [tool, "ts", "-verify", "-in", str(token_path), "-queryfile", str(query_path),
            "-CAfile", str(ca_file)]
    if untrusted:
        argv += ["-untrusted", str(untrusted)]
    proc = _run(argv)
    detail = ((proc.get("err") or "") + "\n" + (proc.get("out") or "")).strip()
    if proc.get("code") != 0:
        last = detail.splitlines()[-1][:160] if detail else "无输出"
        res["issues"].append("时间戳校验不过（" + GUIDE + "换正确的 CA 文件、确认 token 与请求"
                             f"是同一对；被改过的 token 也会这样）（{last}）")
        return res
    reply = _run([tool, "ts", "-reply", "-in", str(token_path), "-text"])
    parsed = _parse_text((reply.get("out") or "") + (reply.get("err") or ""))
    res["gen_time"] = parsed["gen_time"]
    res["serial"] = parsed["serial"]
    res["tsa"] = parsed["tsa"]
    if not STAMP_RE.match(res["gen_time"]):
        res["issues"].append("token 里没有可用的 genTime（" + GUIDE + "换一个 TSA 或重签）")
        return res
    if "granted" not in parsed["status"].lower():
        res["issues"].append(f"TSA 未批准该请求（status={parsed['status'] or '缺失'}）"
                             f"（{GUIDE}换 TSA 或检查请求 digest 算法）")
        return res
    res["ok"] = True
    res["verdict"] = "ok"
    res["anchored_at"] = res["gen_time"]
    res["warnings"].append("时间戳只证「该摘要在该时刻已存在」；不证内容质量、不证签发方身份")
    return res


def record(subject_path: str, token_path: str, query_path: str, subject_sha: str,
           ca_file: str, out: str = "") -> tuple[dict[str, Any], str]:
    """把 token + 请求 + 被证摘要 + 信任锚摘要收成一份可分发记录（nf-time-token/1）。"""
    doc: dict[str, Any] = {
        "schema": SCHEMA,
        "subject": {"path": os.path.basename(subject_path), "sha256": subject_sha},
        "token": {"path": os.path.basename(token_path),
                  "sha256": hashlib.sha256(Path(token_path).read_bytes()).hexdigest()},
        "query": {"path": os.path.basename(query_path),
                  "sha256": hashlib.sha256(Path(query_path).read_bytes()).hexdigest()},
        "ca": {"path": os.path.basename(ca_file),
               "sha256": hashlib.sha256(Path(ca_file).read_bytes()).hexdigest()},
        "note": "token 与请求必须成对分发；信任锚另走可信渠道，不要随手换 CA 文件",
    }
    if out:
        from core import atomic_write
        atomic_write.write_text(out, json.dumps(doc, ensure_ascii=False, indent=2,
                                                sort_keys=True) + "\n")
    return doc, ""
