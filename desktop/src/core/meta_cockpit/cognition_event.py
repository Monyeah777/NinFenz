"""Cognition Event：把驾驶舱一次运行收敛成可复算、可引用的证据事件。

纪律：
- 不含质量评分（作者设计：内部无 score/grade）；
- 字段只来自 cockpit manifest + journal（原子轨迹），digest 确定性；
- 事件可写入本地事件库（NF_COCKPIT_HOME/events/<digest>.json），供 ledger/证据卡引用。
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import tempfile
from pathlib import Path

from . import atomic_io, json_asset

SCHEMA = "nf-cognition-event/1"
SERVER_VERSION = "1.0"
#: 证据角色白名单（只能原样传播，不得升级）。
ROLE_KEYS = ("local-trusted", "derived", "external-advisory")
#: 事件库索引文件（确定性 JSON；写事件后由 write() 原子重建）。
INDEX_NAME = "index.json"
INDEX_SCHEMA = "nf-cognition-event-index/1"
_ROLE_FIX = ("修复指引：evidence_roles 是「来源名 → 角色」映射；角色只用白名单 "
             "ROLE_KEYS（local-trusted / derived / external-advisory），值给非负"
             "整数计数（bool/浮点/字符串都不行），且角色只许原样传播、不得升级。")


def validate_roles(roles) -> dict:
    """校验 evidence_roles：键 ⊆ ROLE_KEYS 且值为非负 int（bool 拒绝）。"""
    if not isinstance(roles, dict):
        raise ValueError("evidence_roles 必须是 dict（收到 %r）。%s"
                         % (type(roles), _ROLE_FIX))
    bad = []
    for key, value in roles.items():
        if not isinstance(key, str) or key not in ROLE_KEYS:
            bad.append("未知键 %r" % (key,))
            continue
        if isinstance(value, bool) or not isinstance(value, int):
            bad.append("%s 的值须为非负整数（收到 %r）" % (key, value))
        elif value < 0:
            bad.append("%s 的值不能为负（收到 %d）" % (key, value))
    if bad:
        raise ValueError("evidence_roles 非法：%s。%s"
                         % ("；".join(bad), _ROLE_FIX))
    return dict(roles)


# 与规格命名对齐（内部/外部都可用）。
_validate_roles = validate_roles


def _canonical(value) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), default=str).encode("utf-8")


def digest(value) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _home() -> Path:
    base = os.environ.get("NF_COCKPIT_HOME") or str(Path.home() / ".NinFenz" / "cockpit")
    p = Path(base) / "events"
    p.mkdir(parents=True, exist_ok=True)
    return p


def build(manifest: dict, journal: dict | None = None, session_id: str = "",
          evidence_roles: dict | None = None) -> dict:
    if not isinstance(manifest, dict) or manifest.get("schema") != "nf-cockpit-manifest/1":
        raise ValueError("manifest schema 须为 nf-cockpit-manifest/1")
    rounds = []
    atoms = []
    if isinstance(journal, dict):
        for ev in journal.get("events") or []:
            ids = [str(x.get("atom_id")) for x in (ev.get("atom_trace") or [])
                   if isinstance(x, dict) and x.get("atom_id")]
            rounds.append({"seq": ev.get("seq"), "atoms": ids,
                           "status": ev.get("status"),
                           "event_digest": ev.get("event_digest")})
            for a in ids:
                if a not in atoms:
                    atoms.append(a)
    sid = session_id or str(manifest.get("journal_digest") or manifest.get("handoff_digest") or "")
    event = {
        "schema": SCHEMA,
        "session_id": sid,
        "manifest_digest": str(manifest.get("digest") or digest(manifest)),
        "machine_digest": str(manifest.get("machine_digest") or ""),
        "runtime_digest": str(manifest.get("runtime_digest") or ""),
        "journal_digest": manifest.get("journal_digest"),
        "handoff_digest": str(manifest.get("handoff_digest") or ""),
        "context_digest": str(manifest.get("context_digest") or ""),
        "prompt_digest": str(manifest.get("prompt_digest") or ""),
        "status": manifest.get("status"),
        "termination": manifest.get("termination"),
        "complete": bool(manifest.get("complete")),
        "turns": int(manifest.get("turns") or 0),
        "context_units_spent": int(manifest.get("context_units_spent") or 0),
        "abstention_status": manifest.get("abstention_status"),
        "human_action_required": bool(manifest.get("human_action_required")),
        "atoms": atoms,
        "rounds": rounds,
        "no_scoring": True,
        "prev": None,
    }
    # 证据角色传播（可选）：只有显式给非空 dict 才落键——缺省不加键，
    # 保证旧事件 digest 稳定；键序由 digest 的 sort_keys 规范化。
    # 白名单/值域在落键前校验（非法直接 ValueError，fail-closed）。
    if isinstance(evidence_roles, dict) and evidence_roles:
        event["evidence_roles"] = validate_roles(evidence_roles)
    event["digest"] = digest(event)
    return event


def verify(event: dict) -> list:
    issues = []
    if not isinstance(event, dict) or event.get("schema") != SCHEMA:
        return ["schema"]
    want = event.get("digest")
    clone = {k: v for k, v in event.items() if k != "digest"}
    if want != digest(clone):
        issues.append("digest")
    if event.get("no_scoring") is not True:
        issues.append("no_scoring")
    return issues


def _index_path() -> Path:
    return _home() / INDEX_NAME


def _retention_path() -> Path:
    """保留策略文件位于事件库 store 根（NF_COCKPIT_HOME/retention.json）。"""
    return _home().parent / RETENTION_FILE


def _scan_events() -> list:
    """扫描事件库里的 *.json（忽略 index.json）；坏件/名不符 ValueError。"""
    home = _home()
    events = []
    for path in sorted(home.glob("*.json"), key=lambda p: p.name):
        if path.name in (INDEX_NAME, RETENTION_FILE):
            continue
        try:
            event = json_asset.load(path)
        except Exception as exc:  # noqa: BLE001 - 统一转 ValueError 便于门禁
            raise ValueError("事件文件不是合法 JSON：%s（%s）"
                             % (path.name, exc))
        if not isinstance(event, dict):
            raise ValueError("事件文件不是对象：%s" % path.name)
        digest_ = str(event.get("digest") or "")
        if digest_ != path.stem:
            raise ValueError("事件文件名与 digest 不一致：%s（%s）"
                             % (path.name, digest_))
        events.append(event)
    return events


def _chain_for(session_id: str, by_digest: dict) -> list:
    """单会话的确定性 prev 链（含跨会话前景祖先；成员按 digest 排序）。"""
    members = sorted(d for d, ev in by_digest.items()
                     if str(ev.get("session_id") or "") == session_id)
    seen, chain = set(), []

    def add_path(digest_: str) -> None:
        stack, local, cur = [], set(), digest_
        # local 防纯环（A.prev=B / B.prev=A）无限回溯；seen 跨成员去重。
        while (cur and cur not in seen and cur not in local
               and cur in by_digest):
            local.add(cur)
            stack.append(cur)
            cur = str(by_digest[cur].get("prev") or "")
        for item in reversed(stack):
            if item not in seen:
                seen.add(item)
                chain.append(item)

    for member in members:
        add_path(member)
    return chain


def build_index(events=None) -> dict:
    """由事件库（或给定事件列表）构造确定性索引对象。"""
    events = _scan_events() if events is None else list(events)
    by_digest = {str(ev.get("digest")): ev for ev in events}
    digests = sorted(by_digest)
    sessions = {}
    for sid in sorted({str(ev.get("session_id") or "") for ev in events}):
        members = [d for d in digests
                   if str(by_digest[d].get("session_id") or "") == sid]
        sessions[sid] = {"events": members,
                         "prev_chain": _chain_for(sid, by_digest)}
    return {"schema": INDEX_SCHEMA, "digests": digests, "sessions": sessions}


def _write_index(index: dict) -> None:
    """同目录临时件 + os.replace 原子写索引。"""
    home = _home()
    atomic_io.write_text(home / INDEX_NAME,
                         json.dumps(index, ensure_ascii=False,
                                    sort_keys=True, indent=2) + "\n")


def rebuild_index() -> dict:
    """扫描事件库并原子重建 index.json；返回索引对象。"""
    index = build_index()
    _write_index(index)
    return index


def verify_index() -> list:
    """索引与事件库目录比对；返回 issues（空 = 一致）。fail-closed。"""
    path = _index_path()
    issues = []
    if not path.is_file():
        return ["index.json 缺失（修复指引：重建事件库索引 rebuild_index）"]
    try:
        raw = json_asset.load(path)
    except Exception as exc:  # noqa: BLE001
        return ["index.json 不是合法 JSON：%s" % exc]
    if not isinstance(raw, dict):
        return ["index.json 不是对象"]
    if raw.get("schema") != INDEX_SCHEMA:
        issues.append("index schema 不匹配：%r（期望 %s）"
                      % (raw.get("schema"), INDEX_SCHEMA))
    try:
        expected = build_index()
    except ValueError as exc:
        return issues + [str(exc)]
    if raw.get("digests") != expected["digests"]:
        issues.append("index digests 与目录扫描不一致（缺失/多余/顺序不符）")
    if raw.get("sessions") != expected["sessions"]:
        issues.append("index sessions 与目录扫描不一致（session/成员/prev 链）")
    return issues


def list_sessions() -> list:
    """按 session_id 排序返回 [{session_id, events, prev_chain}]。

    优先从 events/index.json 的 sessions 读取；索引缺失/损坏时只扫描事件库
    现算（不写盘，保持查询面只读）。
    """
    index = None
    path = _index_path()
    if path.is_file():
        try:
            raw = json_asset.load(path)
            if (isinstance(raw, dict)
                    and raw.get("schema") == INDEX_SCHEMA
                    and isinstance(raw.get("sessions"), dict)):
                index = raw
        except Exception:  # noqa: BLE001 - 坏索引回退到扫描
            index = None
    if index is None:
        index = build_index()
    return [{"session_id": sid,
             "events": list((index["sessions"][sid] or {}).get("events") or []),
             "prev_chain": list((index["sessions"][sid] or {}).get("prev_chain") or [])}
            for sid in sorted(index.get("sessions") or {})]


_DIGEST_FORM = re.compile(r"^[0-9a-f]{64}$")


def _digest_form(value) -> str:
    if not isinstance(value, str) or not _DIGEST_FORM.match(value):
        raise ValueError("digest 须为 64 位小写 hex（收到 %r）。"
                         "修复指引：事件 digest 取 receipt/事件文件里的 64 位 "
                         "sha256（小写、无前缀）" % (value,))
    return value


def query(session_id=None, status=None, digest=None, limit=50) -> list:
    """按会话/状态/digest 过滤事件，按 digest 排序后取前 limit 条。"""
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 500:
        raise ValueError("limit 须为 1..500 的整数（收到 %r）。"
                         "修复指引：查询上限用 --limit 1..500" % (limit,))
    if digest is not None:
        digest = _digest_form(digest)
    events = _scan_events()
    out = [ev for ev in events
           if (session_id is None
               or str(ev.get("session_id") or "") == str(session_id))
           and (status is None or str(ev.get("status") or "") == str(status))
           and (digest is None or str(ev.get("digest") or "") == digest)]
    out.sort(key=lambda ev: str(ev.get("digest") or ""))
    return out[:limit]


POLICY_SCHEMA = "nf-cognition-retention/1"
RETENTION_ENV = "NF_COCKPIT_RETENTION"
RETENTION_FILE = "retention.json"
_POLICY_FIELDS = ("schema", "keep_last", "keep_status", "max_events", "dry_run")
DEFAULT_POLICY = {"keep_last": 20, "keep_status": [], "max_events": None,
                  "dry_run": True}
_RETENTION_FIX = (
    "修复指引：保留策略用 nf-cognition-retention/1 —— keep_last 为 >=1 整数；"
    "keep_status 为状态字符串数组；max_events 可选、>=1 整数；dry_run 为布尔；"
    "未知字段一律拒绝。优先级：显式参数 > NF_COCKPIT_RETENTION(JSON) > "
    "<store>/retention.json > 内置默认。")


def _policy_error(source: str, detail: str) -> None:
    raise ValueError("%s 保留策略非法：%s。%s"
                     % (source, detail, _RETENTION_FIX))


def validate_policy(raw, source: str = "policy") -> dict:
    """校验保留策略片段；返回归一化后的字段子集（未知字段/类型错即 ValueError）。"""
    if not isinstance(raw, dict):
        _policy_error(source, "必须是对象（收到 %s）" % type(raw).__name__)
    unknown = sorted(set(raw) - set(_POLICY_FIELDS))
    if unknown:
        _policy_error(source, "未知字段 %s" % ",".join(unknown))
    if "schema" in raw and raw["schema"] != POLICY_SCHEMA:
        _policy_error(source, "schema 不符（%r，期望 %s）"
                      % (raw["schema"], POLICY_SCHEMA))
    out = {}
    if "keep_last" in raw:
        value = raw["keep_last"]
        if isinstance(value, bool) or not isinstance(value, int) or value < 1:
            _policy_error(source, "keep_last 须为 >=1 整数（收到 %r）" % (value,))
        out["keep_last"] = value
    if "keep_status" in raw:
        value = raw["keep_status"]
        if (not isinstance(value, list)
                or any(not isinstance(x, str) or not x for x in value)):
            _policy_error(source, "keep_status 须为非空字符串数组（收到 %r）"
                          % (value,))
        out["keep_status"] = sorted(set(value))
    if raw.get("max_events") is None:
        pass                      # None = 未设置（可选字段）
    elif "max_events" in raw:
        value = raw["max_events"]
        if isinstance(value, bool) or not isinstance(value, int) or value < 1:
            _policy_error(source, "max_events 须为 >=1 整数（收到 %r）" % (value,))
        out["max_events"] = value
    if "dry_run" in raw:
        if not isinstance(raw["dry_run"], bool):
            _policy_error(source, "dry_run 须为布尔（收到 %r）"
                          % (raw["dry_run"],))
        out["dry_run"] = raw["dry_run"]
    return out


def _load_policy_file(path: Path, source: str) -> dict:
    if not path.is_file():
        return {}
    try:
        raw = json_asset.load(path)
    except Exception as exc:  # noqa: BLE001 - 统一转 ValueError 便于门禁
        raise ValueError("%s 不是合法 JSON：%s。%s"
                         % (source, exc, _RETENTION_FIX))
    return validate_policy(raw, source)


def _effective_policy(keep_last=None, keep_status=None, max_events=None,
                      dry_run=None, config=None) -> dict:
    """按「显式参数 > 环境变量 > config/文件 > 默认」合并生效策略。"""
    policy = {"keep_last": DEFAULT_POLICY["keep_last"],
              "keep_status": list(DEFAULT_POLICY["keep_status"]),
              "max_events": DEFAULT_POLICY["max_events"],
              "dry_run": DEFAULT_POLICY["dry_run"]}
    if config is not None:
        if isinstance(config, dict):
            policy.update(validate_policy(config, "config"))
        elif isinstance(config, (str, Path)):
            policy.update(_load_policy_file(Path(config),
                                            "config 文件 %s" % config))
        else:
            raise ValueError("config 须为策略 dict 或 JSON 路径（收到 %s）。%s"
                             % (type(config).__name__, _RETENTION_FIX))
    else:
        policy.update(_load_policy_file(_retention_path(),
                                        "事件库保留策略 %s" % RETENTION_FILE))
    env = os.environ.get(RETENTION_ENV)
    if env:
        try:
            raw = json.loads(env)
        except ValueError as exc:
            raise ValueError("%s 环境变量不是合法 JSON：%s。%s"
                             % (RETENTION_ENV, exc, _RETENTION_FIX))
        if not isinstance(raw, dict):
            raise ValueError("%s 环境变量须是 JSON 对象（收到 %s）。%s"
                             % (RETENTION_ENV, type(raw).__name__, _RETENTION_FIX))
        policy.update(validate_policy(raw, "%s 环境变量" % RETENTION_ENV))
    explicit = {"keep_last": keep_last, "keep_status": keep_status,
                "max_events": max_events, "dry_run": dry_run}
    explicit = {k: v for k, v in explicit.items() if v is not None}
    if explicit:
        policy.update(validate_policy(explicit, "显式参数"))
    return policy


def gc(keep_last=None, keep_digests=(), dry_run=None, config=None,
       keep_status=None, max_events=None) -> dict:
    """按保留策略清理事件库（按会话整组保留 + 保留 prev 祖先）。

    - 策略字段见 `nf-cognition-retention/1`；优先级 显式参数 > 环境变量
      `NF_COCKPIT_RETENTION`(JSON) > `config`（dict/路径，缺省读
      `<store>/retention.json`）> 内置默认（keep_last=20, keep_status=[],
      max_events=None, dry_run=True）；
    - `keep_status` 命中的会话**整组保留**，不参与 max_events 截断；
    - `max_events` 只截断「按最近保留」部分（命中 keep_status/keep_digests
      的项与其 prev 祖先仍保留）；
    - `dry_run` 默认 True（只算不删）；apply 后删事件文件并重建索引；
    - 返回 kept/removed/sessions_kept/sessions_removed/dry_run/policy。
    """
    policy = _effective_policy(keep_last, keep_status, max_events, dry_run,
                               config)
    if isinstance(keep_digests, str):
        raise ValueError("keep_digests 须为 digest 序列（不要传单个字符串）。"
                         "修复指引：gc(keep_digests=('...',)) 或 CLI 重复 "
                         "--keep-digest")
    try:
        forced = [_digest_form(d) for d in keep_digests]
    except TypeError as exc:
        raise ValueError("keep_digests 不可迭代（%s）。修复指引：传 digest 序列"
                         % exc)
    events = {str(ev.get("digest")): ev for ev in _scan_events()}
    files = {path.stem: path for path in sorted(_home().glob("*.json"))
             if path.name != INDEX_NAME}
    groups: dict = {}
    for digest_, ev in events.items():
        groups.setdefault(str(ev.get("session_id") or ""), []).append(digest_)

    def mtime_of(digest_: str) -> float:
        return files[digest_].stat().st_mtime

    def session_mtime(sid: str) -> float:
        return max(mtime_of(d) for d in groups[sid])

    order = sorted(groups, key=lambda sid: (-session_mtime(sid), sid))
    keep_last = policy["keep_last"]
    recent = order if keep_last >= len(order) else order[:keep_last]
    hit_status = set(policy["keep_status"])
    protected = [sid for sid in order
                 if any(str(events[d].get("status") or "") in hit_status
                        for d in groups[sid])]
    base = {d for sid in recent for d in groups[sid]}
    if policy["max_events"] is not None and len(base) > policy["max_events"]:
        newest = sorted(base, key=lambda d: (mtime_of(d), d), reverse=True)
        base = set(newest[:policy["max_events"]])
    keep = set(base)
    keep |= {d for sid in protected for d in groups[sid]}
    keep |= {d for d in forced if d in events}
    pending = list(keep)
    while pending:                      # 自动保留 prev 链祖先（可跨会话）
        cur = pending.pop()
        prev = str(events[cur].get("prev") or "")
        if prev and prev in events and prev not in keep:
            keep.add(prev)
            pending.append(prev)
    kept = sorted(keep)
    removed = sorted(d for d in events if d not in keep)
    result = {
        "kept": kept,
        "removed": removed,
        "sessions_kept": sum(1 for sid in groups
                             if all(d in keep for d in groups[sid])),
        "sessions_removed": sum(1 for sid in groups
                                if any(d not in keep for d in groups[sid])),
        "dry_run": bool(policy["dry_run"]),
        "policy": policy,
    }
    if not policy["dry_run"]:
        trash = _store_root() / "trash"
        trash.mkdir(parents=True, exist_ok=True)
        for digest_ in removed:
            try:
                os.replace(files[digest_], trash / files[digest_].name)
            except (KeyError, FileNotFoundError, OSError):
                pass
        rebuild_index()
    return result




AUDIT_SCHEMA = "nf-cognition-gc-audit/1"
AUDIT_DIR = "audit"


def _store_root() -> Path:
    """事件库 store 根（NF_COCKPIT_HOME；events/ 与 audit/ 都在其下）。"""
    return _home().parent


def _write_audit(audit: dict) -> str:
    """原子写 `<store>/audit/<digest>.json`；同 digest 已存在则不重复写。"""
    audit_dir = _store_root() / AUDIT_DIR
    audit_dir.mkdir(parents=True, exist_ok=True)
    path = audit_dir / (audit["digest"] + ".json")
    if path.is_file():
        return str(path)
    atomic_io.write_text(path, json.dumps(audit, ensure_ascii=False,
                                          sort_keys=True, indent=2) + "\n")
    return str(path)


def _canary_apply(policy: dict) -> dict:
    """把 store 拷到 <store>/canary/ 并在影子库上真跑 GC（真实库不动）。"""
    store = _store_root()
    # 每次灰度用独立影子目录（tempfile.mkdtemp 自建、无需删除 ⇒ 不新增危险 sink）
    canary = Path(tempfile.mkdtemp(prefix="canary-", dir=str(store)))
    shutil.copytree(_home(), canary / "events",
                    copy_function=shutil.copy2)
    retention = store / RETENTION_FILE
    if retention.is_file():
        shutil.copy2(retention, canary / RETENTION_FILE)
    saved_home = os.environ.get("NF_COCKPIT_HOME")
    saved_env = os.environ.pop(RETENTION_ENV, None)
    os.environ["NF_COCKPIT_HOME"] = str(canary)
    try:
        result = gc(config=dict(policy), dry_run=False)
        issues = verify_index()
    finally:
        if saved_home is None:
            os.environ.pop("NF_COCKPIT_HOME", None)
        else:
            os.environ["NF_COCKPIT_HOME"] = saved_home
        if saved_env is not None:
            os.environ[RETENTION_ENV] = saved_env
    return {"applied": True, "kept": result["kept"],
            "removed": result["removed"], "index_ok": not issues}


def gc_audit(config=None, canary: bool = False) -> dict:
    """保留策略的审计试运行：生成确定性审计记录（不删真实库）。

    - 按现行策略链（显式 config/环境/文件/默认）算出 kept/removed；
    - 审计记录 schema `nf-cognition-gc-audit/1`（无时间戳，digest=sha256 canonical）；
      写 `<store>/audit/<digest>.json`（原子写；同输入重复调用同 digest 不重写）；
    - `canary=True`：在 `<store>/canary/` 影子副本上真跑 apply 并校验影子索引，
      返回含 canary 块（applied/kept/removed/index_ok），真实库不动；
    - 非法配置/参数 → ValueError（带修复指引）。
    """
    if not isinstance(canary, bool):
        raise ValueError("canary 须为布尔（收到 %s）。修复指引：gc_audit(canary="
                         "True/False)" % type(canary).__name__)
    result = gc(config=config, dry_run=True)
    policy = result["policy"]
    events = _scan_events()
    audit = {
        "schema": AUDIT_SCHEMA,
        "policy": policy,
        "policy_digest": digest(policy),
        "kept": sorted(result["kept"]),
        "removed": sorted(result["removed"]),
        "sessions_kept": result["sessions_kept"],
        "sessions_removed": result["sessions_removed"],
        "store_digests": sorted(str(ev.get("digest")) for ev in events),
        "dry_run": True,
    }
    audit["digest"] = digest(audit)
    _write_audit(audit)
    if canary:
        audit["canary"] = _canary_apply(policy)
    return audit


AUDIT_SUMMARY_SCHEMA = "nf-cognition-audit-summary/1"


def _audit_dir() -> Path:
    return _store_root() / AUDIT_DIR


def list_audits() -> list:
    """读 <store>/audit/*.json（按 digest 排序）；坏件/schema 不符 → ValueError。"""
    audit_dir = _audit_dir()
    if not audit_dir.is_dir():
        return []
    audits = []
    for path in sorted(audit_dir.glob("*.json"), key=lambda p: p.name):
        try:
            raw = json_asset.load(path)
        except Exception as exc:  # noqa: BLE001 - 统一转 ValueError 便于门禁
            raise ValueError("审计文件不是合法 JSON：%s（%s）。修复指引：删除或"
                             "修复 <store>/audit 下的坏审计件，再用 gc_audit 重新"
                             "生成" % (path.name, exc))
        if not isinstance(raw, dict) or raw.get("schema") != AUDIT_SCHEMA:
            raise ValueError("审计文件 schema 不符：%s（修复指引：只保留 gc_audit "
                             "生成的 nf-cognition-gc-audit/1 文件）" % path.name)
        if str(raw.get("digest") or "") != path.stem:
            raise ValueError("审计文件名与 digest 不一致：%s（修复指引：删除该坏件"
                             "后重跑 gc_audit）" % path.name)
        audits.append(raw)
    return audits


def query_audits(policy_digest=None, has_removed=None, limit=50) -> list:
    """过滤审计记录（policy_digest / 是否有删除项），按 digest 排序后取 limit。"""
    if (isinstance(limit, bool) or not isinstance(limit, int)
            or not 1 <= limit <= 500):
        raise ValueError("limit 须为 1..500 的整数（收到 %r）。修复指引：查询上限"
                         "用 --limit 1..500" % (limit,))
    if has_removed is not None and not isinstance(has_removed, bool):
        raise ValueError("has_removed 须为布尔或 None（收到 %r）。修复指引："
                         "CLI 用 --has-removed 开关" % (has_removed,))
    if policy_digest is not None:
        policy_digest = _digest_form(policy_digest)
    out = [audit for audit in list_audits()
           if (policy_digest is None
               or str(audit.get("policy_digest") or "") == policy_digest)
           and (has_removed is None
                or bool(audit.get("removed")) is has_removed)]
    out.sort(key=lambda audit: str(audit.get("digest") or ""))
    return out[:limit]


def audit_summary() -> dict:
    """审计汇总（确定性：无时间戳；字段见 nf-cognition-audit-summary/1）。"""
    audits = list_audits()
    by_policy: dict = {}
    total_removed = 0
    total_kept = 0
    max_removed = None
    for audit in audits:
        policy_digest = str(audit.get("policy_digest") or "")
        by_policy[policy_digest] = by_policy.get(policy_digest, 0) + 1
        removed = len(audit.get("removed") or [])
        total_removed += removed
        total_kept += len(audit.get("kept") or [])
        digest_ = str(audit.get("digest") or "")
        if removed <= 0:
            continue
        if (max_removed is None or removed > max_removed["removed"]
                or (removed == max_removed["removed"]
                    and digest_ < max_removed["digest"])):
            max_removed = {"digest": digest_, "removed": removed}
    return {"schema": AUDIT_SUMMARY_SCHEMA, "total": len(audits),
            "by_policy_digest": by_policy, "total_removed": total_removed,
            "total_kept": total_kept, "max_removed": max_removed}


ALERT_SCHEMA = "nf-cognition-audit-alerts/1"
ALERT_REPORT_SCHEMA = "nf-cognition-audit-alert/1"
ALERT_RULES_FILE = "alert_rules.json"
_ALERT_FIELDS = ("schema", "max_removed", "max_removed_ratio",
                 "max_policy_churn", "min_audits_for_ratio")
DEFAULT_ALERT_RULES = {"max_removed": 10, "max_removed_ratio": 0.5,
                       "max_policy_churn": 5, "min_audits_for_ratio": 1}
_ALERT_FIX = (
    "修复指引：告警规则用 nf-cognition-audit-alerts/1 —— max_removed / "
    "max_policy_churn / min_audits_for_ratio 为 >=0 整数，max_removed_ratio 为 "
    "0..1 的数值；未知字段一律拒绝。")


def _alert_error(source: str, detail: str) -> None:
    raise ValueError("%s 告警规则非法：%s。%s"
                     % (source, detail, _ALERT_FIX))


def validate_alert_rules(raw, source: str = "alert_rules") -> dict:
    """校验告警规则片段；返回归一化字段子集（非法即 ValueError）。"""
    if not isinstance(raw, dict):
        _alert_error(source, "必须是对象（收到 %s）" % type(raw).__name__)
    unknown = sorted(set(raw) - set(_ALERT_FIELDS))
    if unknown:
        _alert_error(source, "未知字段 %s" % ",".join(unknown))
    if "schema" in raw and raw["schema"] != ALERT_SCHEMA:
        _alert_error(source, "schema 不符（%r，期望 %s）"
                      % (raw["schema"], ALERT_SCHEMA))
    out = {}
    for key in ("max_removed", "max_policy_churn", "min_audits_for_ratio"):
        if key not in raw:
            continue
        value = raw[key]
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            _alert_error(source, "%s 须为 >=0 整数（收到 %r）" % (key, value))
        out[key] = value
    if "max_removed_ratio" in raw:
        value = raw["max_removed_ratio"]
        if (isinstance(value, bool) or not isinstance(value, (int, float))
                or not 0 <= value <= 1):
            _alert_error(source, "max_removed_ratio 须为 0..1 数值（收到 %r）"
                          % (value,))
        out["max_removed_ratio"] = float(value)
    return out


def _load_alert_rules(config=None) -> dict:
    if config is not None:
        if isinstance(config, dict):
            return validate_alert_rules(config, "config")
        if isinstance(config, (str, Path)):
            path = Path(config)
            if not path.is_file():
                raise ValueError("告警规则文件不存在：%s。修复指引：检查 --config "
                                 "路径，或省略以用默认规则" % path)
            try:
                raw = json_asset.load(path)
            except Exception as exc:  # noqa: BLE001
                raise ValueError("告警规则文件不是合法 JSON：%s（%s）。%s"
                                 % (path, exc, _ALERT_FIX))
            return validate_alert_rules(raw, "config 文件 %s" % path)
        raise ValueError("config 须为规则 dict 或 JSON 路径（收到 %s）。%s"
                         % (type(config).__name__, _ALERT_FIX))
    path = _store_root() / ALERT_RULES_FILE
    if not path.is_file():
        return {}
    try:
        raw = json_asset.load(path)
    except Exception as exc:  # noqa: BLE001
        raise ValueError("告警规则文件不是合法 JSON：%s（%s）。%s"
                         % (path, exc, _ALERT_FIX))
    return validate_alert_rules(raw, "告警规则文件 %s" % ALERT_RULES_FILE)


def audit_anomalies(config=None) -> dict:
    """按阈值规则检查审计记录异常；输出确定性告警报告（无时间戳）。

    - 默认规则：max_removed=10 / max_removed_ratio=0.5 / max_policy_churn=5 /
      min_audits_for_ratio=1；config 可为 dict 或 JSON 路径（缺省读
      `<store>/alert_rules.json`）；
    - findings：单条 audit removed 超限（fail）、整体 removed 占比超限（warn，
      且审计数 >= min_audits_for_ratio）、策略种类数超限（warn）；
    - findings 按 (kind, audit) 排序；空库 clean=true；坏规则 ValueError。
    """
    rules = dict(DEFAULT_ALERT_RULES)
    rules.update(_load_alert_rules(config))
    summary = audit_summary()
    audits = list_audits()
    findings = []
    for audit in audits:
        removed = len(audit.get("removed") or [])
        if removed > rules["max_removed"]:
            findings.append({
                "severity": "fail", "kind": "max_removed",
                "detail": "audit removed=%d > max_removed=%d"
                          % (removed, rules["max_removed"]),
                "audit": str(audit.get("digest") or ""),
            })
    total = int(summary.get("total") or 0)
    kept = int(summary.get("total_kept") or 0)
    removed_total = int(summary.get("total_removed") or 0)
    denominator = kept + removed_total
    if (total >= rules["min_audits_for_ratio"] and denominator > 0):
        ratio = removed_total / denominator
        if ratio > rules["max_removed_ratio"]:
            findings.append({
                "severity": "warn", "kind": "removed_ratio",
                "detail": "removed_ratio=%.3f > max_removed_ratio=%.3f"
                          % (ratio, rules["max_removed_ratio"]),
                "audit": None,
            })
    churn = len(summary.get("by_policy_digest") or {})
    if churn > rules["max_policy_churn"]:
        findings.append({
            "severity": "warn", "kind": "policy_churn",
            "detail": "policy 种类=%d > max_policy_churn=%d"
                      % (churn, rules["max_policy_churn"]),
            "audit": None,
        })
    findings.sort(key=lambda item: (str(item["kind"]),
                                    str(item.get("audit") or "")))
    report = {"schema": ALERT_REPORT_SCHEMA, "findings": findings,
              "clean": not findings}
    report["digest"] = digest(report)
    return report


ALERTS_DIR = "alerts"
ALERT_TREND_SCHEMA = "nf-cognition-alert-trend/1"


def _alerts_path() -> Path:
    return _store_root() / ALERTS_DIR


def _write_alert_report(report: dict) -> str:
    """原子写 `<store>/alerts/<digest>.json`；同 digest 已存在则不重写。"""
    alerts_dir = _alerts_path()
    alerts_dir.mkdir(parents=True, exist_ok=True)
    path = alerts_dir / (report["digest"] + ".json")
    if path.is_file():
        return str(path)
    atomic_io.write_text(path, json.dumps(report, ensure_ascii=False,
                                          sort_keys=True, indent=2) + "\n")
    return str(path)


def record_alert_report(config=None) -> dict:
    """生成告警报告并落盘 `<store>/alerts/<digest>.json`（同 digest 不重写）。"""
    report = audit_anomalies(config=config)
    _write_alert_report(report)
    return report


def audit_alert_history() -> list:
    """读 `<store>/alerts/*.json`，按 digest 排序；坏件/schema 不符 → ValueError。"""
    alerts_dir = _alerts_path()
    if not alerts_dir.is_dir():
        return []
    reports = []
    for path in sorted(alerts_dir.glob("*.json"), key=lambda p: p.name):
        try:
            raw = json_asset.load(path)
        except Exception as exc:  # noqa: BLE001 - 统一转 ValueError 便于门禁
            raise ValueError("告警历史文件不是合法 JSON：%s（%s）。修复指引：删除"
                             "或修复 <store>/alerts 下的坏件后重跑 --record"
                             % (path.name, exc))
        if not isinstance(raw, dict) or raw.get("schema") != ALERT_REPORT_SCHEMA:
            raise ValueError("告警历史文件 schema 不符：%s（修复指引：只保留 "
                             "record_alert_report 生成的 nf-cognition-audit-alert/1 "
                             "文件）" % path.name)
        if str(raw.get("digest") or "") != path.stem:
            raise ValueError("告警历史文件名与 digest 不一致：%s（修复指引：删除该"
                             "坏件后重跑 --record）" % path.name)
        reports.append(raw)
    return reports


def audit_alert_trend() -> dict:
    """告警历史趋势（确定性：无时间戳；按已记录报告聚合）。"""
    history = audit_alert_history()
    by_kind: dict = {}
    by_severity: dict = {}
    clean = 0
    dirty = 0
    for report in history:
        if report.get("clean"):
            clean += 1
        else:
            dirty += 1
        for finding in report.get("findings") or []:
            kind = str(finding.get("kind") or "")
            by_kind[kind] = by_kind.get(kind, 0) + 1
            severity = str(finding.get("severity") or "")
            by_severity[severity] = by_severity.get(severity, 0) + 1
    latest = history[-1]["digest"] if history else None
    return {"schema": ALERT_TREND_SCHEMA, "reports": len(history),
            "clean": clean, "dirty": dirty, "by_kind": by_kind,
            "by_severity": by_severity, "latest": latest}


def write(event: dict) -> str:
    issues = verify(event)
    if issues:
        raise ValueError("invalid cognition event: %s" % ",".join(issues))
    path = _home() / (event["digest"] + ".json")
    path.write_text(json.dumps(event, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8")
    rebuild_index()                  # 写完事件即原子重建索引（确定性）
    return str(path)


def load(event_digest: str) -> dict | None:
    p = _home() / (str(event_digest) + ".json")
    if not p.is_file():
        return None
    return json_asset.load(p)


def from_manifest_file(manifest_path: str | Path, journal_path: str | Path | None = None) -> dict:
    manifest = json_asset.load(Path(manifest_path))
    journal = None
    if journal_path is not None:
        journal = json_asset.load(Path(journal_path))
    event = build(manifest, journal)
    write(event)
    return event
