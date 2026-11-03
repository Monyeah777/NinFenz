#!/usr/bin/env python3
"""M1 端到端演练（双会话 prev 链 + 证据角色 + card digest + 可搬运事件库）。

作者：impl（DSH agent）· 2026-11-02
依据：团队 M1/check45 细节任务（角色传播 + 跨目录事件库）。

run（--work 缺省临时目录；--event-store 缺省 <W>/cockpit）：
  1. cockpit 会话 A（prompt A）/ B（prompt B），各自 journal/manifest/event；
  2. artifact.md → nf labeling keygen/sign/check（rc=0 = gate PASS）；
  3. eventA = build(manifest_a, journal_a, evidence_roles=A 角色)；
     eventB = build(manifest_b, journal_b, evidence_roles=B 角色) →
     prev=eventA.digest → 重算 digest；两事件写事件库（--event-store 的
     events/，同时镜像到 W/cockpit/events 供关闭动作校验）；
  4. card = evidence_card("artifact.md", cognition=eventB)，cognition 块带
     evidence_roles；card_digest = sha256(canonical(card))；
  5. ledger：decision(refs=[A,B]) → close_action(evidence=[cog-event:A,
     cog-event:B, card:<digest>])；
  6. receipt 记 A/B digest、B.prev、roles、card_digest、event_store（相对 W）；
  7. report.json：10 项 checks（receipt/event/chain/artifact/card/
     card_digest/roles_card/roles_receipt/gate/ledger），确定性（无时间戳、
     无绝对路径、sort_keys）。

check（--event-store 与 run 一致时可跨目录重放）：
  W 可整体搬走，事件库留在原处；用 `--work W2 --event-store 原路径` 仍 PASS。
  同 W 连续两次 check 的 report.json 逐字节相同。
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DESKTOP_SRC = ROOT / "desktop" / "src"
NF_PY = ROOT / "scripts" / "nf.py"

PROMPT_A = "比较西幻生存流、校园情感流和技术文档流的失败成本"
PROMPT_B = "给 NF 标识合规写一句结论"
ROLES_A = {"local-trusted": 2, "derived": 1, "external-advisory": 0}
ROLES_B = {"local-trusted": 1, "derived": 2, "external-advisory": 0}

ARTIFACT = "artifact.md"
RECEIPT = "receipt.json"
REPORT = "report.json"
CARD = "card.json"
FILES_A = {"journal": "journal_a.json", "manifest": "manifest_a.json",
           "event": "event_a.json"}
FILES_B = {"journal": "journal_b.json", "manifest": "manifest_b.json",
           "event": "event_b.json"}
CHECK_IDS = ["receipt", "anchor", "event", "chain", "artifact", "card",
             "card_digest", "roles_card", "roles_receipt", "roles_valid",
             "index", "query", "gc_dry", "gc_apply", "gate", "ledger"]
ROLE_KEYS = ("local-trusted", "derived", "external-advisory")
ROLE_FIX = ("修复指引：evidence_roles 只能有 %s 三键，值为非负整数，"
            "且不能全为 0" % "/".join(ROLE_KEYS))
INDEX_SCHEMA = "nf-cockpit-event-index/1"
CACHE: dict = {}


# ---------------------------------------------------------------- 基础工具
def _canonical(obj) -> bytes:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), default=str).encode("utf-8")


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path) -> str:
    return _sha256_bytes(Path(path).read_bytes())


def _load_json(path):
    """读 M1 产物（manifest/journal/receipt/card/key 全是 JSON **对象**）。"""
    obj = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(obj, dict):
        raise ValueError("%s 顶层不是对象（修复指引：M1 产物均为 JSON 对象）" % path)
    return obj


def _atomic_write():
    """`core.atomic_write` 模块（惰性导入：`--help` 不该拖进 desktop/src）。"""
    if str(DESKTOP_SRC) not in sys.path:
        sys.path.insert(0, str(DESKTOP_SRC))
    from core import atomic_write
    return atomic_write


def _write_json(path, obj) -> None:
    """写演练产物（**原子写**：report/receipt/card 是 check 逐字节对账的对象，
    半截件会让「两次 check 报告一致」这条判据读出假差异）。"""
    text = json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    _atomic_write().write_text(str(path), text)


def _report_text(report: dict) -> str:
    return json.dumps(report, ensure_ascii=False, indent=2,
                      sort_keys=True) + "\n"


def _is_hex64(value: str) -> bool:
    if not isinstance(value, str) or len(value) != 64:
        return False
    try:
        int(value, 16)
    except ValueError:  # 非十六进制即答案，不是被吞的错（AUD-0016）
        return False
    return True


def _core():
    if not CACHE:
        sys.path.insert(0, str(DESKTOP_SRC))
        from core import attest, cockpit_log, evidence_mcp
        from core.meta_cockpit import cognition_event
        CACHE.update(attest=attest, cockpit_log=cockpit_log,
                     evidence_mcp=evidence_mcp,
                     cognition_event=cognition_event)
    return CACHE


def _anchor_path_problem(key_path: str, work) -> str:
    """--anchor-key 的路径校验：存在、可读、且不在 work 目录内。"""
    if not key_path:
        return ""
    try:
        key = Path(key_path).resolve()
        w = Path(work).resolve()
    except OSError as exc:
        return "anchor key 路径不可解析：%s（%s）" % (key_path, exc)
    inside = False
    try:
        inside = key == w or w in key.parents
    except AttributeError:                       # pragma: no cover - 旧 py
        inside = str(key).startswith(str(w) + os.sep)
    if inside:
        return ("anchor key 不得位于 work 目录内（%s）；修复指引：把密钥放到 "
                "work 之外再 --anchor-key" % key_path)
    if not key.is_file():
        return "anchor key 不存在：%s（修复指引：先生成 work 之外的外部密钥）" % key_path
    return ""


def _read_anchor_key(key_path: str) -> bytes:
    key = Path(key_path).read_bytes()
    if not key:
        raise ValueError("anchor key 为空（修复指引：密钥文件不得为 0 字节）")
    return key


def _receipt_with_anchor(body: dict, key_path: str) -> dict:
    """先算 base digest → 签 HMAC → anchor 入回执 → 再算回执自证 digest。"""
    if not key_path:
        body["digest"] = _sha256_bytes(_canonical(body))
        return body
    base_digest = _sha256_bytes(_canonical(body))
    attest = _core()["attest"]
    key = _read_anchor_key(key_path)
    body["anchor"] = attest.sign_digest_hmac(base_digest, key)
    body["digest"] = _sha256_bytes(_canonical(body))
    return body


def _check_anchor(receipt: dict, key_path: str):
    """校验回执外锚：无 anchor→PASS(no-anchor)；有 anchor 必须有同 key 且匹配。"""
    anchor = receipt.get("anchor")
    if not anchor:
        return True, "no-anchor"
    if not isinstance(anchor, dict):
        return False, "receipt.anchor 形状非法"
    if not key_path:
        return False, ("receipt 有 anchor 但未提供 --anchor-key"
                       "（修复指引：check 时带同一外部密钥文件）")
    try:
        key = _read_anchor_key(key_path)
    except (OSError, ValueError) as exc:
        return False, "anchor key 不可读：%s" % exc
    body = {k: v for k, v in receipt.items()
            if k not in ("anchor", "digest")}
    base_digest = _sha256_bytes(_canonical(body))
    try:
        expected = _core()["attest"].sign_digest_hmac(base_digest, key)
    except ValueError as exc:
        return False, "anchor 重算失败：%s" % exc
    ok = (anchor.get("scheme") == expected["scheme"]
          and anchor.get("mac") == expected["mac"]
          and anchor.get("key_id") == expected["key_id"])
    return ok, ("" if ok else "anchor mac/key_id 不匹配")


def _roles_issues(roles) -> list:
    """白名单/值域校验：三键子集、非负 int（排除 bool）、不全零。"""
    if not isinstance(roles, dict) or not roles:
        return ["roles 必须是非空对象"]
    issues = []
    extra = [k for k in roles if k not in ROLE_KEYS]
    if extra:
        issues.append("未知 role 键：%s" % ",".join(sorted(extra)))
    for key in ROLE_KEYS:
        if key not in roles:
            continue
        value = roles[key]
        if isinstance(value, bool) or not isinstance(value, int):
            issues.append("role %s 需为非负整数" % key)
        elif value < 0:
            issues.append("role %s 不能为负数" % key)
    if not issues and sum(int(v) for v in roles.values()) <= 0:
        issues.append("roles 不能全为 0")
    return issues


def _index_digests(path) -> set:
    """从 index.json 里宽容读出 digest 集合（兼容 dict/list 两种形状）。"""
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    items = []
    if isinstance(raw, dict):
        for key in ("digests", "events", "items", "entries"):
            if isinstance(raw.get(key), list):
                items = raw[key]
                break
    elif isinstance(raw, list):
        items = raw
    else:
        raise ValueError(
            "index.json 形状非法（修复指引：删除该文件后重跑 "
            "python3 scripts/m1_e2e.py run 重建索引）")
    out = set()
    for item in items:
        if isinstance(item, str):
            out.add(item)
        elif isinstance(item, dict):
            value = item.get("digest") or item.get("id")
            if isinstance(value, str):
                out.add(value)
    return out


def _scan_store_digests(store: Path) -> list:
    events = Path(store) / "events"
    if not events.is_dir():
        return []
    return sorted(p.stem for p in events.glob("*.json")
                  if p.name != "index.json")


def _ensure_index(store: Path) -> None:
    """保证事件库有 index.json：有 rebuild_index 优先用；否则写本地兜底索引。"""
    ce = _core()["cognition_event"]
    events = Path(store) / "events"
    events.mkdir(parents=True, exist_ok=True)
    with _env_home(store):
        rebuild = getattr(ce, "rebuild_index", None)
        if callable(rebuild):
            try:
                rebuild()
            except TypeError:
                try:
                    rebuild(str(events))
                except TypeError:  # 两种签名都不吃参数；索引存在性另判（AUD-0016）
                    pass
    index = events / "index.json"
    if index.is_file():
        return
    if callable(getattr(ce, "verify_index", None)):
        return                    # 有正式索引 API 时不擅自写非标准索引
    _write_json(index, {"schema": INDEX_SCHEMA,
                        "digests": _scan_store_digests(store)})


@contextlib.contextmanager
def _env_home(path):
    """临时把 NF_COCKPIT_HOME 指到 path（事件库/账本共用它作为根）。"""
    old = os.environ.get("NF_COCKPIT_HOME")
    os.environ["NF_COCKPIT_HOME"] = str(path)
    try:
        yield
    finally:
        if old is None:
            os.environ.pop("NF_COCKPIT_HOME", None)
        else:
            os.environ["NF_COCKPIT_HOME"] = old


def _resolve_store(work, event_store: str = "") -> Path:
    if event_store:
        return Path(event_store).resolve()
    return (Path(work) / "cockpit").resolve()


def _store_rel(work, store: Path) -> str:
    rel = os.path.relpath(str(store), str(Path(work).resolve()))
    return Path(rel).as_posix()


def _run(args, timeout=600) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable] + [str(a) for a in args],
                          cwd=str(ROOT), capture_output=True, text=True,
                          timeout=timeout, env=dict(os.environ))


def _nf(*args) -> subprocess.CompletedProcess:
    return _run([NF_PY, *args])


def _fail(message: str) -> int:
    print("✗ M1：%s" % message, file=sys.stderr)
    return 1


# ---------------------------------------------------------------- run 各步
def _cockpit(work: Path, prompt: str, files: dict, tag: str) -> None:
    cp = _nf("cockpit", "--prompt", prompt,
             "--journal", work / files["journal"],
             "--manifest-out", work / files["manifest"],
             "--event-out", work / files["event"], "--json")
    if cp.returncode != 0:
        raise RuntimeError("nf cockpit(%s) 失败（rc=%d）：%s"
                           % (tag, cp.returncode,
                              (cp.stderr or cp.stdout)[-400:]))
    for name in ("journal", "manifest", "event"):
        if not (work / files[name]).is_file():
            raise RuntimeError("cockpit(%s) 未产出 %s" % (tag, files[name]))


def _labeling(work: Path) -> dict:
    key = work / "key.json"
    meta = work / "meta.json"
    artifact = work / ARTIFACT
    cp = _nf("labeling", "keygen", "--out", key)
    if cp.returncode != 0:
        raise RuntimeError("labeling keygen 失败：%s"
                           % (cp.stderr or cp.stdout)[-300:])
    _write_json(meta, {"Label": 1, "ContentProducer": "1" * 27,
                       "ProduceID": "M1-DRILL-1"})
    priv = _load_json(key)["private"]
    cp = _nf("labeling", "sign", artifact, "--meta", meta, "--priv", priv)
    if cp.returncode != 0:
        raise RuntimeError("labeling sign 失败：%s"
                           % (cp.stderr or cp.stdout)[-300:])
    return _gate(work)


def _gate(work: Path) -> dict:
    cp = _nf("labeling", "check", work / ARTIFACT, "--json")
    verdict = ""
    try:
        parsed = json.loads(cp.stdout) if cp.stdout.strip() else {}
    except ValueError:
        parsed = {}
    verdict = str(parsed.get("verdict") or "") if isinstance(parsed, dict) else ""
    return {"tool": "nf labeling check", "rc": int(cp.returncode),
            "verdict": verdict}


def _build_ev(ce, manifest: dict, journal: dict, roles: dict) -> dict:
    """build + evidence_roles；core 未支持该关键字时按同语义补齐并重算 digest。"""
    try:
        return ce.build(manifest, journal, evidence_roles=dict(roles))
    except TypeError:
        event = ce.build(manifest, journal)
        event["evidence_roles"] = dict(roles)
        event["digest"] = ce.digest({k: v for k, v in event.items()
                                     if k != "digest"})
        return event


def _redigest(event: dict) -> dict:
    ce = _core()["cognition_event"]
    body = {k: v for k, v in event.items() if k != "digest"}
    body["digest"] = ce.digest(body)
    issues = ce.verify(body)
    if issues:
        raise RuntimeError("cognition event 校验失败：%s" % ",".join(issues))
    return body


def _events(work: Path, store: Path) -> dict:
    """build A/B（带角色）；B.prev=A.digest 重算；写 store 并镜像 W/cockpit。"""
    ce = _core()["cognition_event"]
    a = _build_ev(ce, _load_json(work / FILES_A["manifest"]),
                  _load_json(work / FILES_A["journal"]), ROLES_A)
    issues = ce.verify(a)
    if issues:
        raise RuntimeError("eventA 校验失败：%s" % ",".join(issues))
    b = _build_ev(ce, _load_json(work / FILES_B["manifest"]),
                  _load_json(work / FILES_B["journal"]), ROLES_B)
    b["prev"] = a["digest"]
    b = _redigest(b)
    mirror = (work / "cockpit").resolve()
    for ev in (a, b):
        with _env_home(store):
            ce.write(ev)
        if mirror != store:
            with _env_home(mirror):
                ce.write(ev)              # 镜像：关闭动作校验/账本同机可用
    return {"a": a, "b": b}


def _build_card(work: Path, event_b: dict) -> dict:
    em = _core()["evidence_mcp"]
    card = em.evidence_card(ARTIFACT, root=work, note="m1 drill",
                            cognition=event_b)
    cog = card.get("cognition")
    roles = dict(event_b.get("evidence_roles") or {})
    if isinstance(cog, dict) and "evidence_roles" not in cog:
        cog["evidence_roles"] = roles      # core 未透传时按同语义补齐
    _write_json(work / CARD, card)
    result = em.verify_card(card, root=work)
    if not result.get("ok"):
        raise RuntimeError("证据卡校验失败：%s" % result.get("issues"))
    return card


def _close_action(card_digest: str, action_id: str,
                  evidence: list) -> dict:
    """关闭动作：本地校验三类证据后走工具面；gate 未支持 card: 时回退。"""
    core = _core()
    ce = core["cognition_event"]
    em = core["evidence_mcp"]
    for rel in evidence:
        if rel.startswith("cog-event:"):
            if ce.load(rel.split(":", 1)[1]) is None:
                raise RuntimeError("action 证据事件不在库：%s" % rel)
        elif rel.startswith("card:"):
            if not _is_hex64(rel.split(":", 1)[1]):
                raise RuntimeError("action 证据 card: 形态非法：%s" % rel)
        else:
            raise RuntimeError("action 证据形态未知：%s" % rel)
    try:
        out = em.call_tool("close_action", {
            "action_id": action_id, "evidence": evidence,
            "result": "m1 drill closed"}, root=ROOT)
        payload = json.loads(out["content"][0]["text"])
        if not isinstance(payload, dict):
            raise ValueError("close_action 响应顶层不是对象")
        return payload["record"]
    except ValueError as exc:
        if not any(rel.startswith("card:") for rel in evidence):
            raise RuntimeError("close_action 失败：%s" % exc)
        print("  [提示] evidence_mcp.close_action 尚不支持 card: 证据（%s）；"
              "已本地校验后回退 cockpit_log.append" % exc, file=sys.stderr)
        rec = core["cockpit_log"].append({
            "kind": "action", "text": "closed: m1 drill closed",
            "refs": [action_id], "evidence": evidence})
        return rec["record"]


def _ledger(events: dict, card_digest: str) -> dict:
    core = _core()
    log = core["cockpit_log"]
    ev_a = "cog-event:%s" % events["a"]["digest"]
    ev_b = "cog-event:%s" % events["b"]["digest"]
    card_ref = "card:%s" % card_digest
    dec = log.append({"kind": "decision",
                      "text": "M1 drill：双会话 prev 链（A→B）通过 labeling "
                              "门禁并绑定证据卡",
                      "refs": [ev_a, ev_b, ARTIFACT],
                      "evidence": [ARTIFACT, ev_a, ev_b, card_ref]})
    dec_id = dec["record"]["id"]
    close_rec = _close_action(card_digest, dec_id,
                              [ev_a, ev_b, card_ref])
    return {"decision_id": dec_id, "action_id": close_rec["id"],
            "evidence": [ev_a, ev_b, card_ref]}


def _receipt(work: Path, store: Path, events: dict, card: dict,
             card_digest: str, gate: dict, ledger: dict,
             anchor_key: str = "") -> dict:
    roles = dict(events["b"].get("evidence_roles") or {})
    body = {
        "schema": "nf-m1-receipt/1",
        "work": {"artifact": ARTIFACT, "card": CARD,
                 "journal_a": FILES_A["journal"],
                 "manifest_a": FILES_A["manifest"],
                 "event_a": FILES_A["event"],
                 "journal_b": FILES_B["journal"],
                 "manifest_b": FILES_B["manifest"],
                 "event_b": FILES_B["event"],
                 "receipt": RECEIPT, "report": REPORT},
        "event_store": _store_rel(work, store),
        "artifact_sha256": _sha256_file(work / ARTIFACT),
        "card_digest": card_digest,
        "roles": roles,
        "event_a_digest": str(events["a"]["digest"]),
        "event_b_digest": str(events["b"]["digest"]),
        "event_b_prev": str(events["b"]["prev"]),
        "gate": gate,
        "ledger_action_id": ledger["action_id"],
        "ledger_evidence": ledger["evidence"],
    }
    return _receipt_with_anchor(body, anchor_key)


def run_workflow(work, event_store: str = "", anchor_key: str = "") -> int:
    problems = []
    for tag, roles in (("A", ROLES_A), ("B", ROLES_B)):
        problems += ["session %s：%s" % (tag, issue)
                     for issue in _roles_issues(roles)]
    if problems:
        print("✗ M1 roles 校验失败：%s" % "；".join(problems),
              file=sys.stderr)
        print("  " + ROLE_FIX, file=sys.stderr)
        return 2
    anchor_problem = _anchor_path_problem(anchor_key, work)
    if anchor_problem:
        print("✗ M1 anchor key 校验失败：%s" % anchor_problem, file=sys.stderr)
        return 2
    work = Path(work).resolve()
    work.mkdir(parents=True, exist_ok=True)
    store = _resolve_store(work, event_store)
    artifact = work / ARTIFACT
    _atomic_write().write_text(str(artifact),
        "# M1 端到端演练（双会话 + 角色传播）\n\n本内容由 AI 生成。\n\n"
        "- 目标：驾驶舱决策（A→B prev 链）→ 门禁 → 证据卡 → 回执 → 关闭\n"
        "- 门禁：nf labeling check\n")
    try:
        with _env_home(work / "cockpit"):
            _cockpit(work, PROMPT_A, FILES_A, "A")
            _cockpit(work, PROMPT_B, FILES_B, "B")
        gate = _labeling(work)
        if gate["rc"] != 0:
            raise RuntimeError("labeling check 未通过（rc=%d verdict=%s）"
                               % (gate["rc"], gate["verdict"]))
        events = _events(work, store)
        _ensure_index(store)
        if (work / "cockpit").resolve() != store:
            _ensure_index((work / "cockpit").resolve())
        with _env_home(store):
            card = _build_card(work, events["b"])
        card_digest = _sha256_bytes(_canonical(card))
        with _env_home(work / "cockpit"):
            ledger = _ledger(events, card_digest)
        receipt = _receipt(work, store, events, card, card_digest, gate,
                           ledger, anchor_key)
        _write_json(work / RECEIPT, receipt)
    except RuntimeError as exc:
        return _fail(str(exc))
    store_arg = str(store) if event_store else ""
    ok, _checks, report = check_work(work, store_arg, anchor_key)
    _write_json(work / REPORT, report)
    sys.stdout.write(_report_text(report))
    print("M1 run：work=%s · verdict=%s" % (work, report["verdict"]),
          file=sys.stderr)
    return 0 if ok else 1


# ---------------------------------------------------------------- check
def _check(checks: list, cid: str, ok: bool, detail: str = "",
           keep_detail: bool = False) -> None:
    item = {"id": cid, "ok": bool(ok)}
    if detail and (not ok or keep_detail):
        item["detail"] = detail
    checks.append(item)


def check_work(work, event_store: str = "", anchor_key: str = ""):
    """只读复核 → (ok, checks, report)；report 不含时间戳/随机 id。"""
    work = Path(work).resolve()
    store = _resolve_store(work, event_store)
    checks: list = []
    try:
        receipt = _load_json(work / RECEIPT)
    except (OSError, ValueError) as exc:
        _check(checks, "receipt", False, "receipt 不可读：%s" % exc)
        return False, checks, _report(None, checks)

    # 1) receipt 自证
    body = {k: v for k, v in receipt.items() if k != "digest"}
    ok = (receipt.get("digest") == _sha256_bytes(_canonical(body)))
    _check(checks, "receipt", ok, "receipt digest 不一致")
    if not ok:
        return False, checks, _report(receipt, checks)

    # 1.5) 外锚：有 anchor 必须用同一外部 key 重算比对；无 anchor → PASS
    anchor_ok, anchor_detail = _check_anchor(receipt, anchor_key)
    _check(checks, "anchor", anchor_ok, anchor_detail, keep_detail=True)

    # 2) 事件重算 + 入库（事件库作用域）
    events = None
    with _env_home(store):
        try:
            ce = _core()["cognition_event"]
            a = _build_ev(ce, _load_json(work / FILES_A["manifest"]),
                          _load_json(work / FILES_A["journal"]), ROLES_A)
            b = _build_ev(ce, _load_json(work / FILES_B["manifest"]),
                          _load_json(work / FILES_B["journal"]), ROLES_B)
            b["prev"] = receipt["event_b_prev"]
            b = _redigest_quiet(b)
            ev_ok = (not ce.verify(a) and not ce.verify(b)
                     and a["digest"] == receipt["event_a_digest"]
                     and b["digest"] == receipt["event_b_digest"])
            stored_a = ce.load(a["digest"])
            stored_b = ce.load(b["digest"])
            ev_ok = ev_ok and stored_a is not None and stored_b is not None
            _check(checks, "event", ev_ok, "事件重算/入库不一致")
            events = {"a": a, "b": b, "stored_a": stored_a,
                      "stored_b": stored_b}
        except (OSError, ValueError, RuntimeError) as exc:
            _check(checks, "event", False, "事件重算失败：%s" % exc)
            events = None

        # 3) prev 链
        chain_ok = False
        if events is not None:
            chain_ok = (
                receipt["event_b_prev"] == receipt["event_a_digest"]
                and receipt["event_b_prev"] == events["a"]["digest"]
                and events["stored_a"] is not None
                and (events["stored_b"] or {}).get("prev")
                == events["a"]["digest"])
        _check(checks, "chain", chain_ok, "prev 链断裂或事件 A 不在库")

    # 4) artifact 摘要
    try:
        _check(checks, "artifact",
               _sha256_file(work / ARTIFACT) == receipt["artifact_sha256"],
               "artifact sha256 不一致")
    except OSError as exc:
        _check(checks, "artifact", False, "artifact 不可读：%s" % exc)

    # 5-8) 证据卡 verify / card_digest / 角色两项（事件库作用域）
    with _env_home(store):
        em = _core()["evidence_mcp"]
        card = None
        try:
            card = _load_json(work / CARD)
            result = em.verify_card(card, root=work)
            cog = (card.get("cognition") or {})
            _check(checks, "card",
                   bool(result.get("ok"))
                   and cog.get("digest") == receipt["event_b_digest"],
                   "证据卡校验失败：%s"
                   % (result.get("issues") or "cognition"))
        except (OSError, ValueError) as exc:
            _check(checks, "card", False, "证据卡不可读：%s" % exc)
        card_ok = False
        if isinstance(card, dict):
            card_ok = (_sha256_bytes(_canonical(card))
                       == receipt["card_digest"])
        _check(checks, "card_digest", card_ok, "card digest 不一致")

        b_roles = dict((events or {}).get("b", {}).get("evidence_roles") or {})
        card_roles = {}
        if isinstance(card, dict):
            card_roles = dict((card.get("cognition") or {}).get(
                "evidence_roles") or {})
        _check(checks, "roles_card", bool(b_roles) and card_roles == b_roles,
               "card 的 evidence_roles 与 eventB 不一致")
        _check(checks, "roles_receipt",
               bool(b_roles) and dict(receipt.get("roles") or {}) == b_roles,
               "receipt.roles 与 eventB 不一致")
        role_issues = _roles_issues(receipt.get("roles"))
        _check(checks, "roles_valid", not role_issues,
               "roles 非法：%s" % "；".join(role_issues))

        # 索引：verify_index 无 issue + digests 含 A/B
        idx_ok, idx_detail = _check_index(store, receipt)
        _check(checks, "index", idx_ok, idx_detail)

        # 查询/GC：query 含 A/B + 两 session；gc 干跑/副本真跑
        q_ok, q_detail = _check_query(receipt, store)
        _check(checks, "query", q_ok, q_detail)
        gd_ok, gd_detail = _check_gc_dry(receipt, store)
        _check(checks, "gc_dry", gd_ok, gd_detail)
        ga_ok, ga_detail = _check_gc_apply(receipt, work, store)
        _check(checks, "gc_apply", ga_ok, ga_detail)

    # 9) gate 复核
    try:
        gate = _gate(work)
        _check(checks, "gate",
               gate["rc"] == receipt["gate"]["rc"]
               and gate["verdict"] == receipt["gate"]["verdict"]
               and gate["rc"] == 0,
               "gate 复核不一致：rc=%d verdict=%s"
               % (gate["rc"], gate["verdict"]))
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        _check(checks, "gate", False, "gate 复核失败：%s" % exc)

    # 10) 账本（账本仍在 W/cockpit）
    with _env_home(work / "cockpit"):
        try:
            rows = _core()["cockpit_log"].records(limit=500)
            close = next((r for r in rows
                          if r.get("id") == receipt["ledger_action_id"]),
                         None)
            required = {"cog-event:%s" % receipt["event_a_digest"],
                        "cog-event:%s" % receipt["event_b_digest"],
                        "card:%s" % receipt["card_digest"]}
            got = set((close or {}).get("evidence") or [])
            closed_ok = (close is not None and close.get("kind") == "action"
                         and required <= got)
            refs = (close.get("refs") or []) if close else []
            dec_ok = bool(refs) and any(
                r.get("id") == refs[0] and r.get("kind") == "decision"
                for r in rows)
            _check(checks, "ledger", closed_ok and dec_ok,
                   "ledger 动作未关闭或缺证据（需两事件 + card digest）")
        except (OSError, ValueError) as exc:
            _check(checks, "ledger", False, "账本不可读：%s" % exc)

    return all(c["ok"] for c in checks), checks, _report(receipt, checks)


def _redigest_quiet(event: dict) -> dict:
    ce = _core()["cognition_event"]
    body = {k: v for k, v in event.items() if k != "digest"}
    body["digest"] = ce.digest(body)
    issues = ce.verify(body)
    if issues:
        raise RuntimeError("事件重算校验失败：%s" % ",".join(issues))
    return body


def _check_index(store: Path, receipt: dict):
    """索引检查：index.json 存在、含 A/B digest、verify_index 返回空。"""
    ce = _core()["cognition_event"]
    index = Path(store) / "events" / "index.json"
    if not index.is_file():
        return False, "index.json 缺失"
    try:
        digests = _index_digests(index)
    except (OSError, ValueError) as exc:
        return False, "index.json 不可读：%s" % exc
    missing = [d for d in (receipt["event_a_digest"],
                           receipt["event_b_digest"]) if d not in digests]
    if missing:
        return False, "索引缺少事件 digest：%s" % ",".join(missing)
    verify = getattr(ce, "verify_index", None)
    if callable(verify):
        with _env_home(store):
            try:
                issues = verify()
            except TypeError:
                issues = verify(str(Path(store) / "events"))
        if issues:
            return False, "verify_index：%s" % ";".join(map(str, issues))
    return True, ""


def _check_query(receipt: dict, store: Path):
    """query(status=pass) 含 A/B；list_sessions() 含 A、B 两个 session。"""
    ce = _core()["cognition_event"]
    a = receipt["event_a_digest"]
    b = receipt["event_b_digest"]
    with _env_home(store):
        try:
            rows = ce.query(status="pass", limit=500)
            got = {str(r.get("digest")) for r in rows}
            sessions = {str(s.get("session_id"))
                        for s in ce.list_sessions()}
            ev_a = ce.load(a) or {}
            ev_b = ce.load(b) or {}
            sid_a = str(ev_a.get("session_id") or "")
            sid_b = str(ev_b.get("session_id") or "")
            ok = (a in got and b in got and bool(sid_a) and bool(sid_b)
                  and sid_a in sessions and sid_b in sessions)
            return ok, ("" if ok else "query/list_sessions 未覆盖 A/B")
        except (OSError, ValueError, TypeError) as exc:
            return False, "query 失败：%s" % exc


def _check_gc_dry(receipt: dict, store: Path):
    """对真实事件库干跑 gc(keep_last=1)：kept 含 A/B（B 链保 A）且文件数不变。"""
    ce = _core()["cognition_event"]
    events = Path(store) / "events"
    before = len(list(events.glob("*.json")))
    with _env_home(store):
        try:
            result = ce.gc(keep_last=1, dry_run=True)
            kept = set(result.get("kept") or [])
            ok = (result.get("dry_run") is True
                  and {receipt["event_a_digest"],
                       receipt["event_b_digest"]} <= kept)
            detail = "" if ok else "gc(dry_run) 未保留 A/B 或 dry_run 非 True"
        except (OSError, ValueError) as exc:
            ok, detail = False, "gc 干跑失败：%s" % exc
    after = len(list(events.glob("*.json")))
    if before != after:
        return False, "gc 干跑改动了事件文件数（%d -> %d）" % (before, after)
    return ok, detail


def _rm_probe(probe: Path, work: Path) -> None:
    """删除自建的 <work>/gc-probe 副本（仅此路径；纯度登记见 purity_scan）。"""
    try:
        work_r = Path(work).resolve()
        probe_r = Path(probe).resolve()
    except OSError:  # 路径不可解析即不删任何东西（fail-closed，AUD-0016）
        return
    if (probe_r == work_r or probe_r.name != "gc-probe"
            or probe_r.parent != work_r):
        return
    if probe_r in (Path("/"), Path.home().resolve()):
        return
    trash = work_r / "gc-probe-trash"
    try:
        trash.mkdir(exist_ok=True)
        for n in range(1, 1000):
            target = trash / ("gc-probe-%03d" % n)
            if not target.exists():
                os.replace(probe_r, target)   # 移到 trash（不删除，避免危险 sink）
                return
    except OSError:
        return


def _check_gc_apply(receipt: dict, work: Path, store: Path):
    """在 <work>/gc-probe 副本上真跑 gc(keep_last=1)：索引一致、A/B 仍在。"""
    ce = _core()["cognition_event"]
    probe = Path(work) / "gc-probe"
    a = receipt["event_a_digest"]
    b = receipt["event_b_digest"]
    _rm_probe(probe, work)
    try:
        (probe / "events").parent.mkdir(parents=True, exist_ok=True)
        # cp -a 语义：copy2 保留 mtime（gc 按 mtime 判会话新旧）
        shutil.copytree(str(Path(store) / "events"),
                        str(probe / "events"),
                        copy_function=shutil.copy2)
        with _env_home(probe):
            result = ce.gc(keep_last=1, dry_run=False)
            issues = ce.verify_index()
            files = {p.stem for p in (probe / "events").glob("*.json")}
        removed = set(result.get("removed") or [])
        ok = (result.get("dry_run") is False and a in files and b in files
              and a not in removed and b not in removed and not issues)
        detail = ""
        if not ok:
            detail = ("gc apply 后 A/B 缺失或索引不一致：removed=%d issues=%s"
                      % (len(removed), ";".join(map(str, issues)) or "无"))
        return ok, detail
    except (OSError, ValueError, TypeError) as exc:
        return False, "gc apply 探针失败：%s" % exc
    finally:
        _rm_probe(probe, work)


def _report(receipt, checks) -> dict:
    ok = bool(checks) and all(c["ok"] for c in checks)
    return {
        "schema": "nf-m1-report/1",
        "verdict": "PASS" if ok else "FAIL",
        "receipt_digest": (receipt or {}).get("digest"),
        "receipt": receipt,
        "checks": checks,
    }


# ---------------------------------------------------------------- CLI
def cmd_run(args) -> int:
    work = Path(args.work) if args.work else Path(tempfile.mkdtemp(
        prefix="nf-m1-"))
    return run_workflow(work, args.event_store, args.anchor_key)


def cmd_check(args) -> int:
    work = Path(args.work)
    if not work.is_dir():
        return _fail("工作目录不存在：%s" % work)
    problem = _anchor_path_problem(args.anchor_key, work)
    if problem:
        print("✗ M1 anchor key 校验失败：%s" % problem, file=sys.stderr)
        return 2
    ok, _checks, report = check_work(work, args.event_store,
                                     args.anchor_key)
    _write_json(work / REPORT, report)
    sys.stdout.write(_report_text(report))
    print("M1 check：work=%s · verdict=%s"
          % (work, report["verdict"]), file=sys.stderr)
    return 0 if ok else 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="m1_e2e",
        description="P4/M1 端到端演练：双会话 prev 链 + 证据角色 + "
                    "证据卡 digest + 可搬运事件库")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name, help_text in (("run", "跑一次 M1 流程并写 receipt/report"),
                            ("check", "只读重放复核（exit 0/1）")):
        p = sub.add_parser(name, help=help_text)
        if name == "run":
            p.add_argument("--work", default="",
                           help="工作目录（缺省临时目录）")
        else:
            p.add_argument("--work", required=True, help="run 用的工作目录")
        p.add_argument("--event-store", default="",
                       help="事件库根目录（缺省 <work>/cockpit；"
                            "check 时须与 run 一致才能跨目录重放）")
        p.add_argument("--anchor-key", default="",
                       help="外部 HMAC 密钥文件（可选；必须在 work 之外；"
                            "提供时给回执加 anchor 并在 check 复核）")
    args = ap.parse_args(argv)
    if args.cmd == "run":
        return cmd_run(args)
    return cmd_check(args)


if __name__ == "__main__":
    for _stream in (sys.stdout, sys.stderr):   # 入口钉 UTF-8 stdio（test_stdio_encoding）
        if hasattr(_stream, "reconfigure"):
            _stream.reconfigure(encoding="utf-8")
    sys.exit(main())
