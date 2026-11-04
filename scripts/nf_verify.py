#!/usr/bin/env python3
"""NF 馆藏**读者侧独立验证器**（纯标准库，不 import NF 的任何模块）。

用途：读者只拿到「回执（RECEIPTS.json 里的一条）+ 条目内容」，就能自己判断
「这条属于本馆、且没被换过」——不依赖 NF 的代码、不取全馆、不需要联网。

用法：
  python nf_verify.py --entry NF-1 \\
      [--receipts library/RECEIPTS.json] [--entry-file library/NF-1.md] \\
      [--key-file <hmac 密钥>] \\
      [--ssh-allowed-signers <文件> --ssh-identity <principal>] \\
      [--json]

复现的算法（与仓库实现逐字一致，RFC 6962 域分隔）：
  规范摘要  = SHA-256( 条目文本剔除 attestation/attested_at/anchor_* 行后的字节 )
  叶        = SHA-256( 0x00 ‖ UTF-8( {"id":…,"digest":…} 的紧凑规范 JSON ) )
  内部节点  = SHA-256( 0x01 ‖ 左 ‖ 右 )
  折叠      = 按 proof 的 side 逐层合并，结果应等于回执里的 root

退出码：0 = 全部可验证项通过；1 = 有校验失败或不可验证（fail-closed）；2 = 用法错误。
"""
from __future__ import annotations

import argparse
import hashlib
import hmac as _hmac
import json
import os
import re
import shutil as _shutil
import subprocess  # nosec B404/B603/B607 —— 调用 ssh-keygen/git/hf（argv 列表、无 shell、路径经 which 解析）
import sys
import time
import zipfile

SCHEMA = "nf-receipts/1"
SSH_NS = "nf-attest"
#: 外挂验证器（ssh-keygen）调用上限（秒）——不返回时 fail-closed，绝不无限等待
TOOL_TIMEOUT_S = 60
SSH_PAYLOAD_PREFIX = "nf-attest-v1\nsubject_sha256:"
_EXCLUDE = re.compile(r"^(attestation|attested_at|anchor_[a-z_]+)\s*:")


def canonical_bytes(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":")).encode("utf-8")


def leaf_of(entry_id: str, digest: str) -> bytes:
    return hashlib.sha256(b"\x00" + canonical_bytes({"id": entry_id,
                                                     "digest": digest})).digest()


def node(left: bytes, right: bytes) -> bytes:
    return hashlib.sha256(b"\x01" + left + right).digest()


def fold(leaf: bytes, proof) -> bytes:
    cur = leaf
    for step in proof:
        sib = bytes.fromhex(step["hash"])
        cur = node(sib, cur) if step["side"] == "left" else node(cur, sib)
    return cur


def entry_digest(path: str) -> str:
    """与 `nf library entry_digest` 同规则：剔除签名/锚字段行后取 SHA-256。"""
    with open(path, "rb") as fh:
        text = fh.read().decode("utf-8").replace("\r\n", "\n")
    kept = [ln for ln in text.split("\n") if not _EXCLUDE.match(ln)]
    return hashlib.sha256("\n".join(kept).encode("utf-8")).hexdigest()


def verify_hmac(digest: str, anchor, key: bytes):
    expect = _hmac.new(key, digest.strip().lower().encode("utf-8"),
                       hashlib.sha256).hexdigest()
    return (_hmac.compare_digest(expect, str(anchor.get("mac") or "")),
            "hmac 锚匹配" if _hmac.compare_digest(expect, str(anchor.get("mac") or ""))
            else "hmac 锚不匹配（密钥不符或摘要被改）")


def verify_ssh(digest: str, anchor, allowed_signers: str, identity: str):
    if not allowed_signers or not os.path.isfile(allowed_signers):
        return False, "缺 allowed_signers（--ssh-allowed-signers）"
    sig = str(anchor.get("sig_file") or "")
    if not sig or not os.path.isfile(sig):
        return False, "缺签名文件：%s" % (sig or "(未记录)")
    ident = identity or str(anchor.get("identity") or "")
    payload = (SSH_PAYLOAD_PREFIX + digest.strip().lower() + "\n").encode("utf-8")
    exe = _shutil.which("ssh-keygen")
    if not exe:
        return False, ("ssh-sig 验签需要外部命令 ssh-keygen，但 PATH 中找不到"
                       "（修复指引：先安装 OpenSSH ≥8.9 后重试）")
    try:
        proc = subprocess.run([exe, "-Y", "verify", "-f", allowed_signers,  # nosec B404/B603/B607 —— 只调 ssh-keygen（argv 列表、无 shell、路径经 which 解析）
                               "-I", ident, "-n", str(anchor.get("ns") or SSH_NS),
                               "-s", sig],
                              input=payload, capture_output=True,
                              timeout=TOOL_TIMEOUT_S)      # 超时上限：外挂工具不返回时 fail-closed
    except subprocess.TimeoutExpired:
        return False, ("ssh-sig 校验超时（%d s，ssh-keygen 未返回）→ fail-closed"
                       "（修复指引：确认 ssh-keygen 可用后重试）" % TOOL_TIMEOUT_S)
    msg = (proc.stderr or proc.stdout or b"").decode("utf-8", "replace").strip()
    return (proc.returncode == 0, "ssh-sig 匹配" if proc.returncode == 0
            else f"ssh-sig 校验失败：{msg[:160]}")


# ------------------------------------------------------------------ 证据文档复验（--evidence）
#
# 与仓内 core.evidence 是**两套独立实现**：本文件不 import 任何 NF 模块，单文件拷走即可运行
# （这是「免费验证器 / 可嵌入」的形态要求）。判据必须一致——test_evidence.py 用同一批夹具跑
# 两边，结论不一致即红：两套实现不一致，说明至少一边有 bug，那时第三方复验的结论就不可信。

EVIDENCE_SCHEMA = "nf-evidence/1"
RECEIPTS_SCHEMA = "nf-receipts/1"
ATTEST_SCHEMA = "nf-attest/1"
ATTEST_SET_SCHEMA = "nf-attest-set/1"
REVOCATION_SCHEMA = "nf-revocation/1"
BUNDLE_ENTRY = "bundle.json"
PAYLOAD_DIR = "payload/"
NODE_PREFIX = b"\x01nf-node:"
EVIDENCE_EXIT = {"ok": 0, "invalid": 1, "revoked": 2, "expired": 3}
EVIDENCE_USAGE = 4
LEVELS_EV = ("digest_only", "receipts_only", "hmac-sha256", "ssh-sig", "sigstore-keyless")


def _v_members(src, entries, res):
    """成员实体 + 摘要 + 叶复算 → (payloads, leaves)；有问题即 None。"""
    payloads, leaves = {}, []
    for e in entries:
        rel = _norm(e.get("path") or e.get("id") or "")
        data = src.find(rel) if rel else None
        if data is None:
            res["issues"].append("缺 payload：%s" % (rel or "?"))
            continue
        digest = _sha_hex(data)
        payloads[rel] = data
        want = str(e.get("digest") or "")
        if digest != want:
            res["issues"].append(f"成员摘要不符：{rel}（记录={want[:16]} 实测={digest[:16]}）")
        leaf = leaf_of(rel, digest).hex()
        if leaf != str(e.get("leaf") or ""):
            res["issues"].append(f"叶复算不符：{rel}")
        leaves.append(bytes.fromhex(leaf))
    return None if res["issues"] else (payloads, leaves)


def _v_bundle_manifest(src, doc, res):
    """包清单面：成员 → 根 → 包含证明 → 链 → 夹带成员。返回 (entries, payloads)。"""
    entries = doc.get("entries") or []
    res["count"] = len(entries)
    res["root"] = str(doc.get("root") or "")
    res["head"] = str((doc.get("chain") or {}).get("head") or "")
    res["expires_at"] = str(doc.get("expires_at") or "")
    if not entries:
        res["issues"].append("证据包为空")
        return None
    got = _v_members(src, entries, res)
    if got is None:
        return None
    payloads, leaves = got
    root = (_merkle_root(leaves) or b"").hex()
    if root != res["root"]:
        res["issues"].append("根不一致：记录={} 实测={}".format(res["root"][:16], root[:16]))
        return None
    for e in entries:
        folded = fold(bytes.fromhex(str(e.get("leaf") or "")), e.get("proof") or []).hex()
        if folded != res["root"]:
            res["issues"].append("包含证明不折叠到根：{}".format(_norm(e.get("path") or "")))
    if res["issues"]:
        return None
    if res["head"] and _chain_head(entries) != res["head"]:
        res["issues"].append("透明日志链头不一致（条目顺序被插删/改序）")
        return None
    listed = {PAYLOAD_DIR + _norm(e.get("path") or e.get("id") or "") for e in entries}
    for name in src.names():
        if name.startswith(PAYLOAD_DIR) and name not in listed:
            res["issues"].append(f"包内多出未登记成员：{name}")
    if res["issues"]:
        return None
    return entries, payloads


def _v_bundle_envelopes(src, doc, payloads, key, res):
    """信封面：清单内每一份都必须通过，且每个成员都被覆盖。"""
    names = [str(n) for n in (doc.get("attestations") or [])]
    if not names:
        res["issues"].append("包内无 attestation")
        return
    levels, covered, bad = [], set(), []
    for name in names:
        raw = src.read(name)
        if raw is None:
            bad.append(f"{name}：缺该信封")
            continue
        _schema, env = _parse_doc(raw)
        if env is None:
            bad.append(f"{name}：不是合法 JSON")
            continue
        level, why = _envelope_ok(env, payloads, key)
        if level:
            levels.append(level)
            covered.add(_norm((env.get("subject") or {}).get("path") or ""))
        else:
            bad.append(f"{name}：{why}")
    if bad:
        res["issues"].append("信封未全部通过校验：{}".format("；".join(bad[:3])))
        return
    want = {_norm(e.get("path") or e.get("id") or "") for e in (doc.get("entries") or [])}
    missing = sorted(want - covered)
    if missing:
        res["issues"].append("成员缺信封：{}".format(", ".join(missing[:3])))
        return
    res["level"] = max(levels, key=lambda lv: LEVELS_EV.index(lv) if lv in LEVELS_EV else -1)


def _rev_hit(rev, entries):
    """吊销表命中（按摘要或仓相对路径）；表形状不对一律不认。"""
    if not rev or str(rev.get("schema") or "") != REVOCATION_SCHEMA:
        return None
    items = rev.get("revoked") or []
    if not isinstance(items, list):
        return None
    digests = {str(e.get("digest") or "") for e in entries}
    paths = {_norm(e.get("path") or e.get("id") or "") for e in entries}
    for it in items:
        if not isinstance(it, dict):
            continue
        dig = str(it.get("digest") or "")
        pat = _norm(it.get("path") or "")
        if (dig and dig in digests) or (pat and pat in paths):
            return it
    return None


def _judge(res, entries, revocations, at):
    """判定面：证据本身成立后，再判吊销（压过 ok）与时效。"""
    hit = _rev_hit(revocations, entries)
    if hit is not None:
        res["verdict"] = "revoked"
        res["revoked_by"] = hit
        res["issues"].append("证据已被吊销：%s"
                             % (hit.get("reason") or hit.get("path") or hit.get("digest")
                                or "未给理由"))
        return res
    exp = res.get("expires_at") or ""
    if exp:
        now = at or _now()
        if now > exp:
            res["verdict"] = "expired"
            res["issues"].append(f"证据已过期：有效期至 {exp}，判定时点 {now}")
            return res
    res["verdict"] = "ok"
    return res


def _v_receipts(src, doc, revocations):
    """回执形态：成员摘要 → 叶 → 根 → 每条包含证明。"""
    res = _res("receipts")
    if str(doc.get("schema") or "") != RECEIPTS_SCHEMA:
        res["issues"].append("回执 schema 不匹配")
        return res
    entries = doc.get("entries") or []
    res["count"] = len(entries)
    res["root"] = str(doc.get("root") or "")
    if not entries:
        res["issues"].append("回执为空")
        return res
    got = _v_members(src, entries, res)
    if got is None:
        return res
    _payloads, leaves = got
    if (_merkle_root(leaves) or b"").hex() != res["root"]:
        res["issues"].append("根不一致")
        return res
    for e in entries:
        folded = fold(bytes.fromhex(str(e.get("leaf") or "")), e.get("proof") or []).hex()
        if folded != res["root"]:
            res["issues"].append("包含证明不折叠到根：{}".format(_norm(e.get("id") or "")))
    if res["issues"]:
        return res
    res["level"] = "receipts_only"
    return _judge(res, entries, revocations, "")


def _v_attest(src, doc, key, revocations, at):
    """信封形态：每份信封自洽 + 指向真实成员。"""
    res = _res("attest")
    is_set = str(doc.get("schema") or "") == ATTEST_SET_SCHEMA
    envs = doc.get("attestations") if is_set else [doc]
    if not isinstance(envs, list) or not envs:
        res["issues"].append("信封集为空")
        return res
    res["count"] = len(envs)
    payloads = {}
    for env in envs:
        if not isinstance(env, dict):
            res["issues"].append("信封不是对象")
            continue
        rel = _norm((env.get("subject") or {}).get("path") or "")
        data = src.find(rel) if rel else None
        if data is None:
            res["issues"].append("缺成员实体：%s" % (rel or "?"))
            continue
        payloads[rel] = data
    if res["issues"]:
        return res
    levels, bad = [], []
    for env in envs:
        level, why = _envelope_ok(env, payloads, key)
        if level:
            levels.append(level)
        else:
            bad.append(why)
    if bad:
        res["issues"].append("信封未全部通过校验：{}".format("；".join(bad[:3])))
        return res
    res["level"] = max(levels, key=lambda lv: LEVELS_EV.index(lv) if lv in LEVELS_EV else -1)
    entries = [{"path": k, "digest": _sha_hex(v)} for k, v in payloads.items()]
    return _judge(res, entries, revocations, at)


def _embedded_rev(src):
    raw = src.read("revocations.json")
    if raw is None:
        return None
    _schema, doc = _parse_doc(raw)
    return doc


def run_evidence(args) -> int:
    """`--evidence` 模式：零依赖复验（三形态同一套四词判定）。"""
    try:
        key = None
        if args.key_file:
            with open(args.key_file, "rb") as fh:
                key = fh.read().strip() or None
        rev = None
        if args.revocations:
            with open(args.revocations, encoding="utf-8") as fh:
                rev = json.load(fh)
            if not isinstance(rev, dict):     # 形状就地校验（零依赖：不走 core.json_doc）
                print("✗ 吊销表顶层应为对象（修复指引：请给 nf-revocation/1 的 JSON 对象）",
                      file=sys.stderr)
                return EVIDENCE_USAGE
        src = _Src(args.evidence, root=args.root)
        try:
            form, doc = _form(src, args.kind)
            if form == "bundle":
                res = _res("bundle")
                got = _v_bundle_manifest(src, doc, res)
                if got is not None:
                    _v_bundle_envelopes(src, doc, got[1], key, res)
                    if not res["issues"]:
                        _judge(res, got[0], rev if rev is not None else _embedded_rev(src),
                               args.at)
            elif form == "receipts":
                res = _v_receipts(src, doc, rev)
            else:
                res = _v_attest(src, doc, key, rev, args.at)
        finally:
            src.close()
    except (OSError, ValueError) as exc:
        print(f"✗ {exc}", file=sys.stderr)
        return EVIDENCE_USAGE
    if args.json:
        print(json.dumps(res, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(f"== nf_verify --evidence（零依赖复验）{args.evidence} ==")
        print("  形态：%s · 判定：%s · 强度：%s · 成员 %d 件"
              % (res["kind"], res["verdict"], res["level"], res["count"]))
        if res["root"]:
            print("  根：{}".format(res["root"][:32]))
        for i in res["issues"]:
            print(f"  [FAIL] {i}", file=sys.stderr)
        if res["verdict"] == "ok":
            print("  => 证据成立（口径：成员未改 + 证明到根 + 信封自洽；不等于内容质量或真实性）")
    return EVIDENCE_EXIT.get(res["verdict"], 1)

def _build_parser():
    ap = argparse.ArgumentParser(
        prog="nf_verify",
        description="NF 读者侧独立验证器（纯标准库，不依赖 NF 代码）：馆藏单条 / 证据文档复验")
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--entry", help="馆藏编号（如 NF-1）")
    mode.add_argument("--evidence",
                      help="证据文档：证据包 .zip / 解包目录 / nf-receipts · nf-attest JSON")
    ap.add_argument("--receipts", default="library/RECEIPTS.json",
                    help="回执文件（缺省 library/RECEIPTS.json）")
    ap.add_argument("--entry-file", default="",
                    help="条目内容文件（缺省 library/<编号>.md；无则只验包含关系）")
    ap.add_argument("--root", default="",
                    help="证据文档形态：成员根目录（缺省 = 该 JSON 所在目录）")
    ap.add_argument("--kind", default="", choices=("", "bundle", "receipts", "attest"),
                    help="证据文档形态（缺省 = 按文档 schema 自动判）")
    ap.add_argument("--revocations", default="", help="吊销表 JSON（nf-revocation/1）")
    ap.add_argument("--at", default="", help="判定时点（UTC 秒级；缺省 = 现在）")
    ap.add_argument("--key-file", default="", help="hmac 锚 / hmac 信封校验用密钥文件")
    ap.add_argument("--ssh-allowed-signers", default="",
                    help="ssh-sig 锚校验用 allowed_signers 文件")
    ap.add_argument("--ssh-identity", default="", help="ssh-sig 锚的 principal")
    ap.add_argument("--json", action="store_true", help="输出结构化 JSON")
    return ap


def _sha_hex(data) -> str:
    return hashlib.sha256(data).hexdigest()


def _merkle_root(leaves):
    """RFC 6962 风格：空集 → None；单叶 → 该叶；否则切到最大的 2 的幂。"""
    if not leaves:
        return None
    if len(leaves) == 1:
        return leaves[0]
    mid = 1
    while mid * 2 < len(leaves):
        mid *= 2
    return node(_merkle_root(leaves[:mid]), _merkle_root(leaves[mid:]))


def _chain_head(entries) -> str:
    """透明日志链头：H(NODE_PREFIX | prev | leaf) 逐节折叠（与仓内同源）。"""
    prev = "0" * 64
    for e in entries:
        h = hashlib.sha256()
        h.update(NODE_PREFIX)
        for part in (prev.encode("ascii"), str(e.get("leaf") or "").encode("ascii")):
            h.update(b"|")
            h.update(part)
        prev = h.hexdigest()
    return prev


def _norm(rel: str) -> str:
    return str(rel).replace("\\", "/").lstrip("/")


def _now() -> str:
    epoch = (os.environ.get("SOURCE_DATE_EPOCH") or "").strip()
    if epoch.isdigit():
        return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(int(epoch)))
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


class _Src:
    """证据源读面：zip / 目录 / 单 JSON + 根目录（三形态共用）。"""

    def __init__(self, path: str, root: str = ""):
        self.path = path
        self._zf = None
        self._dir = ""
        self._doc_path = ""
        if os.path.isdir(path):
            self._dir = path
        elif os.path.isfile(path) and zipfile.is_zipfile(path):
            self._zf = zipfile.ZipFile(path)
        elif os.path.isfile(path):
            self._doc_path = path
            self._dir = root or os.path.dirname(os.path.abspath(path)) or "."
        else:
            raise ValueError(f"证据源不存在：{path}"
                             "（修复指引：请给证据包 .zip、解包目录或证据 JSON）")

    def names(self):
        if self._zf is not None:
            return sorted(self._zf.namelist())
        out = []
        for base, _dirs, files in os.walk(self._dir):
            for n in files:
                out.append(_norm(os.path.relpath(os.path.join(base, n), self._dir)))
        return sorted(out)

    def read(self, name):
        name = _norm(name)
        if self._zf is not None:
            try:
                return self._zf.read(name)
            except KeyError:        # 成员不在包里：按「缺件」返回 None，由调用方判 invalid
                return None
        full = os.path.join(self._dir, *name.split("/"))
        if not os.path.isfile(full):
            return None
        with open(full, "rb") as fh:
            return fh.read()

    def find(self, rel):
        for name in (rel, PAYLOAD_DIR + rel):
            data = self.read(name)
            if data is not None:
                return data
        return None

    def doc_bytes(self):
        if not self._doc_path:
            return None
        with open(self._doc_path, "rb") as fh:
            return fh.read()

    def close(self):
        if self._zf is not None:
            self._zf.close()
            self._zf = None


def _parse_doc(raw):
    """容错解析：坏 JSON / 非对象一律返回 ("", None)。

    本文件刻意**不 import 任何 NF 模块**（零依赖单文件可分发），故不能走 core.json_doc；
    形状判据就在解析点旁边显式写出来，不散落到调用方。
    """
    try:
        doc = json.loads(raw.decode())
    except (ValueError, UnicodeDecodeError):
        return "", None
    if not isinstance(doc, dict):
        return "", None
    return str(doc.get("schema") or ""), doc


def _form(src, kind: str = ""):
    """判形态：只认文档 schema，不认扩展名。"""
    mapping = {RECEIPTS_SCHEMA: "receipts", ATTEST_SCHEMA: "attest", ATTEST_SET_SCHEMA: "attest"}
    raw = src.doc_bytes()
    if raw is not None:
        schema, doc = _parse_doc(raw)
        form = mapping.get(schema, "")
        if schema == EVIDENCE_SCHEMA:
            raise ValueError("bundle 形态须给 .zip 或解包目录（修复指引：单 JSON 不会是自包含包）")
        if not form or (kind and kind != form):
            raise ValueError(f"认不出证据形态：{src.path}（schema={schema or '缺失'}）"
                             "（修复指引：请给 nf-receipts/1、nf-attest/1、"
                             "nf-attest-set/1 的 JSON）")
        return form, doc
    raw = src.read(BUNDLE_ENTRY)
    if raw is not None:
        schema, doc = _parse_doc(raw)
        if schema == EVIDENCE_SCHEMA:
            return "bundle", doc
    for name in [n for n in src.names() if n.endswith(".json")]:
        schema, doc = _parse_doc(src.read(name) or b"")
        form = mapping.get(schema, "")
        if form and (not kind or kind == form):
            return form, doc
    raise ValueError(f"认不出证据形态：{src.path}（修复指引：请给 nf evidence pack 的 .zip、或含 "
                     "nf-receipts/1 · nf-attest/1 · nf-attest-set/1 的目录）")


def _res(kind: str):
    return {"kind": kind, "verdict": "invalid", "level": "none", "root": "",
            "head": "", "count": 0, "issues": [], "expires_at": "", "revoked_by": None}


def _envelope_ok(env, payloads, key):
    """单份信封 → (level 或空串, 原因)。缺锚/未知方案一律 fail-closed，不降级。"""
    if not isinstance(env, dict) or env.get("schema") != ATTEST_SCHEMA:
        return "", "信封 schema 不匹配"
    base = {k: env.get(k) for k in ("schema", "subject", "producer", "issued_at")}
    if env.get("envelope_digest") != _sha_hex(canonical_bytes(base)):
        return "", "信封摘要不一致（信封被改）"
    subj = env.get("subject") or {}
    rel = _norm(subj.get("path") or "")
    data = payloads.get(rel)
    if data is None:
        return "", "信封指向的成员不在证据里：%s" % (rel or "?")
    if _sha_hex(data) != str(subj.get("sha256") or ""):
        return "", f"信封主体与成员不同源：{rel}"
    sig = env.get("signature")
    if not sig:
        return "digest_only", ""
    scheme = str(sig.get("scheme") or "")
    if scheme == "hmac-sha256":
        if key is None:
            return "", "hmac 级缺密钥（fail-closed，不降级）"
        mac = _hmac.new(key, str(env.get("envelope_digest") or "").encode("utf-8"),
                        hashlib.sha256).hexdigest()
        if not _hmac.compare_digest(mac, str(sig.get("mac") or "")):
            return "", "hmac 签名不匹配（密钥不符或信封被改）"
        return "hmac-sha256", ""
    return "", "信封签名方案 %s 需外部验证器（本零依赖验证器 fail-closed）" % (scheme or "缺失")


def main(argv=None) -> int:
    args = _build_parser().parse_args(argv)
    if args.evidence:
        return run_evidence(args)
    return run_entry(args)


def run_entry(args) -> int:
    try:
        with open(args.receipts, encoding="utf-8") as fh:
            doc = json.load(fh)
        # 独立验证器**零 NF 依赖**（本判据不改）：顶层形状在这一层就地校验，
            # 与 core.json_doc 同一口径（对象才继续，否则给指引）。
        if not isinstance(doc, dict):
            raise ValueError(f"{args.receipts} 顶层应为对象，实为 {type(doc).__name__}"
                             "（修复指引：回执件不是数组/标量）")
    except (OSError, ValueError) as exc:
        print(f"✗ 回执不可读：{exc}", file=sys.stderr)
        return 2
    if doc.get("schema") != SCHEMA:
        print(f"✗ 回执 schema 不匹配（期望 {SCHEMA}）", file=sys.stderr)
        return 2
    want = args.entry.strip().lower()
    hit = next((e for e in doc.get("entries") or []
                if str(e.get("id", "")).lower() == want), None)
    if hit is None:
        print(f"✗ 回执中没有该条目：{args.entry}", file=sys.stderr)
        return 2

    checks = []
    digest = str(hit.get("digest") or "")
    root = str(doc.get("root") or "")

    # 1) 包含关系：叶 → 折叠 → 根
    folded = fold(leaf_of(hit["id"], digest), hit.get("proof") or []).hex()
    checks.append(("inclusion", folded == root,
                   "包含证明折叠到根" if folded == root
                   else f"折叠结果 {folded[:16]} ≠ 根 {root[:16]}"))

    # 2)（可选）内容绑定：重算规范摘要 == 回执摘要
    path = args.entry_file or os.path.join("library", "{}.md".format(hit["id"]))
    if os.path.isfile(path):
        live = entry_digest(path)
        checks.append(("content", live == digest,
                       "内容摘要与回执一致" if live == digest
                       else f"内容摘要 {live[:16]} ≠ 回执 {digest[:16]}（内容被改）"))
    else:
        checks.append(("content", False,
                       "未提供条目内容（--entry-file），无法校验内容绑定"))

    # 3)（可选）签名锚
    anchor = hit.get("anchor")
    if anchor:
        scheme = anchor.get("scheme")
        if scheme == "hmac-sha256":
            if args.key_file and os.path.isfile(args.key_file):
                with open(args.key_file, "rb") as fh:
                    ok, msg = verify_hmac(digest, anchor, fh.read().strip())
            else:
                ok, msg = False, "缺 --key-file，hmac 锚不可校验（fail-closed）"
            checks.append(("anchor", ok, msg))
        elif scheme == "ssh-sig":
            ok, msg = verify_ssh(digest, anchor, args.ssh_allowed_signers,
                                 args.ssh_identity)
            checks.append(("anchor", ok, msg))
        elif scheme == "sigstore-keyless":
            checks.append(("anchor", False,
                           "sigstore 锚需 cosign，未安装 → fail-closed"))
        else:
            checks.append(("anchor", False, f"未知锚方案：{scheme}"))
    else:
        checks.append(("anchor", True, "该条未挂签名锚（仅包含关系可验）"))

    ok_all = all(ok for _n, ok, _m in checks)
    # 结论行的**诚实度**（2026-09-30 补）：无签名锚时只验了「包含关系 + 内容绑定」，**真实性
    # 一字未验**——此前结论行照样只说「可验证通过」，读者容易把它读成「签名已验」。退出码与
    # JSON 形状不变（读者侧契约不动），只把结论行写清。
    anchored = bool(hit.get("anchor"))
    if args.json:
        print(json.dumps({"entry": hit["id"], "root": root, "digest": digest,
                          "ok": ok_all,
                          "checks": [{"name": n, "ok": o, "detail": m}
                                     for n, o, m in checks]},
                         ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print("== nf_verify（读者侧独立验证）{} ==".format(hit["id"]))
        print(f"  全馆根：{root[:32]}")
        for n, o, m in checks:
            print("  %s %-10s %s" % ("✓" if o else "✗", n, m))
        print("  => %s" % ("可验证通过" if ok_all else "未通过（详上）"))
        if ok_all and not anchored:
            print("     （口径：真实性**未验**——该条未挂签名锚；上表只证包含关系与内容绑定）")
    return 0 if ok_all else 1


if __name__ == "__main__":
    # stdio 钉 UTF-8：Windows 控制台 GBK 下 ✓/✗ 即 UnicodeEncodeError（同 nf.py）
    for _stream in (sys.stdout, sys.stderr):
        if hasattr(_stream, "reconfigure"):
            _stream.reconfigure(encoding="utf-8")
    sys.exit(main())
