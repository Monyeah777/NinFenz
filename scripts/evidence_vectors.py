#!/usr/bin/env python3
"""证据判定向量集：把「输入 → 期望判定」固化成**跨语言可复核**的单一产物。

为什么有它（2026-11-05）：
- ABI 的 cc_verify 是「中立第三方仲裁」的支点，但此前只有**本仓实现**能判：换一门语言写实现，
  没有任何可比的锚点（§12.7 的 Go 客户端就卡在这里，而本机没有工具链）；
- 攻击矩阵（nf evidence bench）证明的是「本实现抓得住攻击」，但它**绑定本实现的代码**；
  向量集证明的是「**任何**实现都该给出这几个判定」——两者的失效模式不同。

产物（results/ccos/evidence_verdict_vectors.json，schema nf-evidence-vectors/1）每条：
  id / desc / expected{verdict, exit_code} / bundle_b64（或 special）/ 可选 key_b64、
  revocations_b64、anchor、at —— 第三方解码即可自验，不需要读本仓代码。

纪律：**确定性**（固定密钥、固定时间戳、不压缩、成员名排序），--write 两次逐字节一致；
--check 版本比对提交件与重算；坏件一律以 issue 形式暴露，不静默跳过。
"""
from __future__ import annotations

import argparse
import base64
import contextlib
import hashlib
import io
import json
import os
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import evidence  # noqa: E402

SCHEMA = "nf-evidence-vectors/1"
OUT_REL = "results/ccos/evidence_verdict_vectors.json"
PIN = "2026-01-01T00:00:00Z"
KEY = b"vector-key-0123456789abcdef012345"          # 固定密钥：可复现，非生产用途
KEY_B64 = base64.b64encode(KEY).decode("ascii")
GUIDE = "修复指引："


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def _write_members(path: str, members: dict) -> bytes:
    """把成员字典写成确定性 zip（固定时间戳 + 不压缩 + 名排序）。"""
    items = [(name, members[name]) for name in sorted(members)]
    data = evidence._zip_bytes(items)
    Path(path).write_bytes(data)
    return data


def _members(data: bytes) -> dict:
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        return {name: zf.read(name) for name in zf.namelist()}


def _build(tmp: str, targets: list, key: bytes | None = None, anchor=None) -> bytes:
    data, _info = evidence.build(tmp, targets, issuer="vectors", created_at=PIN,
                                 key=key, anchor=anchor)
    return data


def _base_fixture(tmp: str) -> None:
    d = Path(tmp) / "d"
    d.mkdir(parents=True, exist_ok=True)
    for name, body in (("a.md", "# A\n\n甲\n"), ("b.md", "# B\n\n乙\n"),
                       ("c.md", "# C\n\n丙\n")):
        (d / name).write_text(body, encoding="utf-8")


def _case(cid: str, desc: str, verdict: str, *, bundle: bytes | None = None,
          bundle_path: str = "", key: bytes | None = None,
          revocations: dict | None = None, anchor: dict | None = None,
          at: str = "", special: str = "",
          exit_code: int | None = None) -> dict:
    row = {"id": cid, "desc": desc,
           "expected": {"verdict": verdict,
                        "exit_code": (evidence.EXIT_CODES.get(verdict, 1)
                                      if exit_code is None else exit_code)}}
    if bundle is not None:
        row["bundle_b64"] = _b64(bundle)
        row["bundle_sha256"] = hashlib.sha256(bundle).hexdigest()
    if bundle_path:
        row["bundle_path"] = bundle_path
    if special:
        row["special"] = special
    if key is not None:
        row["key_b64"] = _b64(key)
    if revocations is not None:
        row["revocations"] = revocations
    if anchor is not None:
        row["anchor"] = anchor
    if at:
        row["at"] = at
    return row


#: PIN 对应的 epoch（2026-01-01T00:00:00Z）——信封时间戳也钉死，否则 --write 两次不一致
PIN_EPOCH = "1767225600"


@contextlib.contextmanager
def _pinned_time():
    """把 SOURCE_DATE_EPOCH 钉到 PIN：信封 issued_at 取它（可复现构建惯例）。"""
    old = os.environ.get("SOURCE_DATE_EPOCH")
    os.environ["SOURCE_DATE_EPOCH"] = PIN_EPOCH
    try:
        yield
    finally:
        if old is None:
            os.environ.pop("SOURCE_DATE_EPOCH", None)
        else:
            os.environ["SOURCE_DATE_EPOCH"] = old


def build_vectors() -> dict:
    """生成全部向量（确定性；不写盘）。"""
    with _pinned_time():
        return _build_vectors()


def _build_vectors() -> dict:
    """真实生成流程（时间已钉死；调用方走 build_vectors）。"""
    rows: list[dict] = []
    with tempfile.TemporaryDirectory(prefix="nf_vectors_") as tmp:
        _base_fixture(tmp)
        base = _build(tmp, ["d/a.md", "d/b.md"])
        hmac_bundle = _build(tmp, ["d/a.md", "d/b.md"], key=KEY)
        digest_a = hashlib.sha256((Path(tmp) / "d" / "a.md").read_bytes()).hexdigest()

        rows.append(_case("ok_digest_only", "完好包（digest_only）", "ok", bundle=base))
        rows.append(_case("ok_hmac", "完好包（hmac-sha256 级）", "ok",
                          bundle=hmac_bundle, key=KEY))
        rows.append(_case("no_key_is_invalid", "hmac 级缺密钥（不降级）", "invalid",
                          bundle=hmac_bundle))
        rows.append(_case("wrong_key_is_invalid", "hmac 级错密钥", "invalid",
                          bundle=hmac_bundle, key=b"wrong-key-wrong-key-wrong-key"))

        m = _members(base)
        m["payload/d/a.md"] = "# A\n\n甲改\n".encode()
        rows.append(_case("payload_flip", "成员字节被改", "invalid",
                          bundle=_write_members(os.path.join(tmp, "flip.zip"), m)))
        m = _members(base)
        meta = json.loads(m["bundle.json"].decode())
        meta["root"] = "0" * 64
        m["bundle.json"] = json.dumps(meta, ensure_ascii=False, sort_keys=True).encode()
        rows.append(_case("root_flip", "根被改", "invalid",
                          bundle=_write_members(os.path.join(tmp, "root.zip"), m)))
        m = _members(base)
        meta = json.loads(m["bundle.json"].decode())
        meta.pop("chain", None)
        m["bundle.json"] = json.dumps(meta, ensure_ascii=False, sort_keys=True).encode()
        rows.append(_case("chain_missing", "chain 段被删（顺序不可证）", "invalid",
                          bundle=_write_members(os.path.join(tmp, "nochain.zip"), m)))

        head2 = {"count": 2, "head": evidence.verify(
            os.path.join(tmp, "base.zip") if False else _dump(tmp, base), key=None)["head"]}
        v3 = _build(tmp, ["d/a.md", "d/b.md", "d/c.md"], anchor=head2)
        rows.append(_case("anchor_ok", "锚点对得上（正常追加）", "ok",
                          bundle=v3, anchor=head2))
        head3 = {"count": 3, "head": evidence.verify(_dump(tmp, v3))["head"]}
        rows.append(_case("anchor_truncated", "用更早的包冒充现在（整链截断）", "invalid",
                          bundle=base, anchor=head3))

        rev = {"schema": evidence.REVOCATION_SCHEMA,
               "revoked": [{"digest": digest_a, "revoked_at": PIN, "reason": "vectors"}]}
        rows.append(_case("revoked", "吊销表命中", "revoked", bundle=base, revocations=rev))
        expired, _ei = evidence.build(tmp, ["d/a.md"], issuer="vectors", created_at=PIN,
                                      expires_at="2020-01-01T00:00:00Z")
        rows.append(_case("expired", "有效期已过（expires_at 早于判定时点）", "expired",
                          bundle=expired, at="2030-01-01T00:00:00Z"))
        m = _members(base)
        m["revocations.json"] = b"{not json"
        rows.append(_case("bad_revocations", "包内吊销表坏件（不是「无吊销」）", "invalid",
                          bundle=_write_members(os.path.join(tmp, "revin.zip"), m)))
        plain = Path(tmp) / "plain.bin"
        plain.write_bytes(b"just a file")
        # 输入不是证据包 = **用法错**（rc=4），不是判定面；第三方实现也必须拒绝而不是给判定
        rows.append(_case("not_a_bundle", "不是证据包（用法错，不是判定）", "invalid",
                          bundle=plain.read_bytes(), special="not_a_bundle",
                          exit_code=4))
    return {"schema": SCHEMA, "pinned_at": PIN, "count": len(rows), "vectors": rows}


def _dump(tmp: str, data: bytes) -> str:
    """把内存里的包落到临时文件（verify 只吃路径）。"""
    path = os.path.join(tmp, "dump.zip")
    Path(path).write_bytes(data)
    return path


def render_vectors(doc: dict) -> str:
    return json.dumps(doc, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def check_vectors() -> tuple:
    """提交件 == 重算？→ (issues, live_doc)。"""
    path = ROOT / OUT_REL
    live = build_vectors()
    if not path.is_file():
        return [f"缺向量集 {OUT_REL}（{GUIDE}跑 python scripts/evidence_vectors.py --write）"], live
    try:
        recorded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return [f"{OUT_REL} 不可读：{exc}（{GUIDE}重跑 --write）"], live
    if render_vectors(recorded) != render_vectors(live):
        return [f"{OUT_REL} 与重算不一致（{GUIDE}重跑 --write 后再提交）"], live
    return [], live


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="evidence_vectors",
                                 description="证据判定向量集（跨语言可复核）")
    ap.add_argument("--write", action="store_true", help="重写向量集")
    ap.add_argument("--check", action="store_true", help="校验提交件 == 重算")
    ap.add_argument("--json", action="store_true", help="机读输出")
    args = ap.parse_args(argv)
    if args.write:
        doc = build_vectors()
        dest = ROOT / OUT_REL
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(render_vectors(doc), encoding="utf-8", newline="\n")
        if args.json:
            print(json.dumps({"written": OUT_REL, "count": doc["count"]},
                             ensure_ascii=False, indent=2, sort_keys=True))
        else:
            print(f"✓ 已写入 {OUT_REL}（{doc['count']} 条向量）")
        return 0
    issues, live = check_vectors()
    if args.json:
        print(json.dumps({"ok": not issues, "issues": issues, "count": live["count"]},
                         ensure_ascii=False, indent=2, sort_keys=True))
    else:
        for issue in issues:
            print(f"  ✗ {issue}", file=sys.stderr)
        if not issues:
            print(f"✓ 向量集与重算一致（{live['count']} 条）")
    return 0 if not issues else 1


if __name__ == "__main__":
    for _stream in (sys.stdout, sys.stderr):
        if hasattr(_stream, "reconfigure"):
            _stream.reconfigure(encoding="utf-8")
    sys.exit(main())
