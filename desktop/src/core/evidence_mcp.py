"""NF Evidence MCP（本地只读证据面）：为 AI 产物生成/校验可离线复算的证据卡。

与 `mcp_runtime`（Content Gate，12 只读检索工具）**分开**：本 server 只做「证据」，
不碰内容检索，也不实现任何网络/写盘；路径必须仓内相对，越界一律拒绝。

工具（tools/list）：
- `evidence_card`：路径 → nf-evidence-card/1（sha256/bytes/line_count/contract）
- `verify_card`：证据卡 → 重算主体摘要并比对（防篡改/防过期）
- `diff_cards`：两张卡 → 变化字段（回归/替换检测）
- `list_contracts`：按关键词列 domain pack 契约（帮助 agent 选契约）

纪律：确定性（无时间戳）、纯标准库、只读、拒绝绝对路径/`..`、单文件上限 8 MiB。
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

from core import cockpit_log, domain_rules, json_doc, machine_contract, paths
from core.meta_cockpit import cognition_event as ce

#: 关闭动作的证据引用可带「证据卡 digest」：card:<sha256 小写 hex>。
_CARD_DIGEST_RE = re.compile(r"^card:[0-9a-f]{64}$")

SCHEMA = "nf-evidence-card/1"
SERVER_NAME = "nf-evidence"
SERVER_VERSION = "0.1.0"
MAX_BYTES = 8 * 1024 * 1024
COVERAGE_MIN_NAMES = 1
COVERAGE_MIN_FIELDS = 0
COVERAGE_MIN_RULES = 0


def _root(root: str | Path) -> Path:
    return Path(root).resolve()


def _subject(path_rel: str, root: str | Path) -> Tuple[Path, bytes]:
    target = Path(paths.validate_path(str(_root(root)), str(path_rel)))
    if not target.is_file():
        raise ValueError("主体不是文件：%s" % path_rel)
    raw = target.read_bytes()
    if len(raw) > MAX_BYTES:
        raise ValueError("主体超过 %d 字节上限：%s" % (MAX_BYTES, path_rel))
    return target, raw


def artifact_checks(path_rel: str, root: str | Path = ".") -> List[Dict[str, Any]]:
    """通用产物检查（按路径分派）：存在/非空/UTF-8/JSON 可解析/模块机读契约。"""
    target, raw = _subject(path_rel, root)
    checks: List[Dict[str, Any]] = [{"rule": "exists_nonempty", "ok": bool(raw), "detail": "%d bytes" % len(raw)}]
    try:
        text = raw.decode("utf-8")
        checks.append({"rule": "utf8", "ok": True, "detail": "ok"})
    except UnicodeDecodeError:
        text = ""
        checks.append({"rule": "utf8", "ok": False, "detail": "非 UTF-8（按字节留存摘要）"})
    rel = target.relative_to(_root(root)).as_posix()
    if rel.endswith(".json"):
        try:
            parsed = json.loads(raw.decode("utf-8"))
            if not isinstance(parsed, (dict, list)):
                raise ValueError("顶层不是对象/数组（标量 JSON 不是契约件形状；"
                                 "修复指引：该文件须是对象或数组）")
            checks.append({"rule": "json_parse", "ok": True, "detail": "ok"})
        except (ValueError, UnicodeDecodeError) as exc:
            checks.append({"rule": "json_parse", "ok": False, "detail": str(exc)[:120]})
    if rel.startswith("04_模块库/") and rel.endswith(".md") and text:
        try:
            mc = machine_contract.parse_header(text)
            ok = isinstance(mc, dict) and bool(mc.get("id"))
            checks.append({"rule": "machine_contract", "ok": ok,
                           "detail": ("id=%s" % mc.get("id")) if ok else "缺 machine_contract.id"})
        except (ValueError, TypeError) as exc:
            checks.append({"rule": "machine_contract", "ok": False, "detail": str(exc)[:120]})
    return checks


def _contract_checks(pack: Dict[str, Any], root: str | Path = ".") -> List[Dict[str, Any]]:
    """契约包自检（证据卡里记录「该契约本身可解析/自洽」）。"""
    checks: List[Dict[str, Any]] = []
    pkg = str(pack.get("package") or "")
    try:
        proto_path = _root(root) / "community" / pkg / "protocol.yaml"
        from core.conformance_scan import load_yaml
        proto = load_yaml(proto_path.read_text(encoding="utf-8"))
        checks.append({"rule": "contract_yaml", "ok": isinstance(proto, dict),
                       "detail": "protocol.yaml 可解析" if isinstance(proto, dict) else "不可解析"})
    except (OSError, ValueError, RuntimeError) as exc:
        proto = {}
        checks.append({"rule": "contract_yaml", "ok": False, "detail": str(exc)[:120]})
    try:
        spec = json_doc.load(_root(root) / "community" / pkg / "outputs" / "DOMAIN_SPEC.json",
                             dict, what="DOMAIN_SPEC.json")
        subs = spec.get("subdivisions") or []
        checks.append({"rule": "contract_subdivisions", "ok": len(subs) == 12,
                       "detail": "%d 条细分" % len(subs)})
    except (OSError, ValueError) as exc:
        checks.append({"rule": "contract_subdivisions", "ok": False, "detail": str(exc)[:120]})
    # 输出索引在场（protocol.yaml 的 outputs.index 必须真实存在）
    try:
        pkgcfg = (proto.get("package") or {}) if isinstance(proto, dict) else {}
        out_idx = str((pkgcfg.get("outputs") or {}).get("index") or "")
        has_idx = bool(out_idx) and (_root(root) / "community" / pkg / out_idx).is_file()
        checks.append({"rule": "contract_outputs_index", "ok": has_idx,
                       "detail": out_idx or "protocol.yaml 未声明 outputs.index"})
    except (OSError, TypeError) as exc:
        checks.append({"rule": "contract_outputs_index", "ok": False, "detail": str(exc)[:120]})
    # 模块 id 在 registry 中登记
    try:
        reg = json_doc.load(_root(root) / "desktop" / "src" / "core" / "registry.json",
                            dict, what="registry.json")
        reg_ids = {str(m.get("id")) for m in (reg.get("modules") or []) if isinstance(m, dict)}
        for pr in reg.get("protocols") or []:
            if isinstance(pr, dict):
                reg_ids |= {str(x) for x in (pr.get("module_ids") or [])}
        mids = [str(m.get("id")) for m in ((proto.get("package") or {}).get("modules") or [])
                if isinstance(m, dict)]
        missing = [m for m in mids if m not in reg_ids]
        checks.append({"rule": "contract_modules_registered", "ok": not missing,
                       "detail": ("缺 %s" % ",".join(missing[:3])) if missing else "%d 个模块在册" % len(mids)})
    except (OSError, ValueError, TypeError) as exc:
        checks.append({"rule": "contract_modules_registered", "ok": False, "detail": str(exc)[:120]})
    return checks


def _resolve_contract(name: str, root: str | Path = ".") -> Dict[str, Any] | None:
    """契约名/域码 → {name, code, package, path, sha256}；找不到 → None。"""
    if not name:
        return None
    doc = json_doc.load(_root(root) / "protocol" / "domain_packs.json", dict,
                        what="protocol/domain_packs.json")
    q = str(name).strip()
    for p in doc.get("packs") or []:
        cands = {str(p.get("name") or ""), str(p.get("package") or ""), str(p.get("code") or "")}
        if q in cands:
            rel = "community/%s/protocol.yaml" % p.get("package")
            target = _root(root) / rel
            if not target.is_file():
                raise ValueError("契约件不存在：%s" % rel)
            return {"name": p.get("name"), "code": p.get("code"),
                    "package": p.get("package"), "path": rel,
                    "sha256": hashlib.sha256(target.read_bytes()).hexdigest()}
    raise ValueError("未找到契约：%s（可用 list_contracts 查）" % name)


def evidence_card(path_rel: str, root: str | Path = ".", contract: str = "",
                  note: str = "", min_names: int = COVERAGE_MIN_NAMES,
                  min_fields: int = COVERAGE_MIN_FIELDS,
                  min_rules: int = COVERAGE_MIN_RULES,
                  cognition: Any = None) -> Dict[str, Any]:
    target, raw = _subject(path_rel, root)
    text = raw.decode("utf-8", errors="replace")
    contract_block = _resolve_contract(contract, root) if contract else None
    if contract_block:
        contract_block.update({"checks": _contract_checks(contract_block, root)})
        rules = domain_rules.build_rules(str(contract_block.get("package")), root)
        cov = domain_rules.coverage(text, rules)
        cov["min_names"] = max(0, int(min_names))
        cov["min_fields"] = max(0, int(min_fields))
        cov["min_rules"] = max(0, int(min_rules))
        cov["ok"] = (cov["names_hit"] >= cov["min_names"] and
                     (cov["fields"] == 0 or cov["fields_hit"] >= cov["min_fields"]) and
                     cov["rules_ok"] >= cov["min_rules"])
        contract_block.update({"rules_digest": rules["rule_digest"],
                               "rules_count": len(rules["rules"]),
                               "machine_fields": rules["machine_fields"],
                               "coverage": cov})
        contract_block["checks"].append({"rule": "contract_coverage",
                                         "ok": cov["ok"],
                                         "detail": "名字 %d/%d · 字段 %d/%d · 规则 %d/%d（阈值 %d/%d/%d）"
                                                   % (cov["names_hit"], cov["rules"],
                                                      cov["fields_hit"], cov["fields"],
                                                      cov["rules_ok"], cov["rules"],
                                                      cov["min_names"], cov["min_fields"],
                                                      cov["min_rules"])})
    cog_block = None
    if cognition is not None:
        ev = cognition
        if isinstance(ev, str):
            ev = ce.load(ev)
            if ev is None:
                raise ValueError("cognition event 不在本地事件库：%s" % cognition)
        if not isinstance(ev, dict):
            raise ValueError("cognition 须为事件对象或 digest")
        bad = ce.verify(ev)
        if bad:
            raise ValueError("cognition event 非法：%s" % ",".join(bad))
        cog_block = {"schema": ev.get("schema"), "session_id": ev.get("session_id"),
                     "digest": ev["digest"], "manifest_digest": ev.get("manifest_digest"),
                     "handoff_digest": ev.get("handoff_digest"),
                     "status": ev.get("status"), "turns": ev.get("turns"),
                     "atoms": ev.get("atoms") or []}
        # 证据角色传播（event → card）：事件含 evidence_roles 才透传同值；
        # 键/值按白名单校验，非法直接 ValueError（fail-closed）。
        if isinstance(ev.get("evidence_roles"), dict):
            cog_block["evidence_roles"] = ce.validate_roles(ev["evidence_roles"])
    return {"schema": SCHEMA,
            "cognition": cog_block,
            "subject": {"path": target.relative_to(_root(root)).as_posix(),
                        "sha256": hashlib.sha256(raw).hexdigest(),
                        "bytes": len(raw),
                        "line_count": text.count("\n") + (0 if text.endswith("\n") else 1)},
            "contract": contract_block,
            "note": note or None,
            "checks": artifact_checks(path_rel, root),
            "digest_rule": "sha256(file bytes)",
            "generated_by": {"tool": SERVER_NAME, "version": SERVER_VERSION}}


def verify_card(card: Any, root: str | Path = ".") -> Dict[str, Any]:
    issues: List[str] = []
    if not isinstance(card, dict) or card.get("schema") != SCHEMA:
        return {"ok": False, "issues": ["card schema 不匹配（期望 %s）" % SCHEMA]}
    subj = card.get("subject") or {}
    rel = subj.get("path")
    if not isinstance(rel, str) or not rel:
        return {"ok": False, "issues": ["card 缺 subject.path"]}
    try:
        _t, raw = _subject(rel, root)
    except (ValueError, OSError) as exc:
        return {"ok": False, "issues": ["主体不可用：%s（%s）" % (rel, exc)]}
    live = {"sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw),
            "line_count": raw.decode("utf-8", errors="replace").count("\n")
            + (0 if raw.decode("utf-8", errors="replace").endswith("\n") else 1)}
    for field in ("sha256", "bytes", "line_count"):
        if subj.get(field) != live[field]:
            issues.append("主体漂移：%s 记录=%r 实测=%r" % (field, subj.get(field), live[field]))
    try:
        live_checks = {c["rule"]: c for c in artifact_checks(rel, root)}
    except (ValueError, OSError) as exc:
        issues.append("产物检查不可用：%s" % exc)
        live_checks = {}
    for c in card.get("checks") or []:
        if not isinstance(c, dict):
            continue
        live_c = live_checks.get(str(c.get("rule")))
        if live_c is None or bool(c.get("ok")) != bool(live_c.get("ok")):
            issues.append("检查结果变化：%s" % c.get("rule"))
    cov = (card.get("contract") or {}).get("coverage") if isinstance(card.get("contract"), dict) else None
    if isinstance(cov, dict):
        rules = domain_rules.build_rules(str(card["contract"].get("package")), root)
        live_cov = domain_rules.coverage(raw.decode("utf-8", errors="replace"), rules)
        if bool(cov.get("ok")) != (live_cov["names_hit"] >= int(cov.get("min_names", 0)) and
                                   (live_cov["fields"] == 0 or
                                    live_cov["fields_hit"] >= int(cov.get("min_fields", 0))) and
                                   live_cov["rules_ok"] >= int(cov.get("min_rules", 0))):
            issues.append("契约覆盖判定变化")
    contract = card.get("contract")
    if isinstance(contract, dict):
        live_cc = {c["rule"]: c for c in _contract_checks(contract, root)}
        cov0 = contract.get("coverage")
        if isinstance(cov0, dict):
            try:
                rules0 = domain_rules.build_rules(str(contract.get("package")), root)
                live_cov0 = domain_rules.coverage(raw.decode("utf-8", errors="replace"), rules0)
                live_cc["contract_coverage"] = {"rule": "contract_coverage",
                    "ok": (live_cov0["names_hit"] >= int(cov0.get("min_names", 0)) and
                           (live_cov0["fields"] == 0 or
                            live_cov0["fields_hit"] >= int(cov0.get("min_fields", 0))) and
                           live_cov0["rules_ok"] >= int(cov0.get("min_rules", 0)))}
            except (ValueError, OSError):  # 重算失败沿用记录值，异常由规则门禁报（AUD-0016）
                pass
        for c in contract.get("checks") or []:
            if not isinstance(c, dict):
                continue
            lc = live_cc.get(str(c.get("rule")))
            if lc is None or bool(c.get("ok")) != bool(lc.get("ok")):
                issues.append("契约检查结果变化：%s" % c.get("rule"))
        if any(isinstance(c, dict) and not c.get("ok") for c in contract.get("checks") or []):
            issues.append("契约检查未过（coverage/完整性）")
        try:
            live_contract = _resolve_contract(str(contract.get("name") or ""), root)
        except ValueError as exc:
            issues.append("契约不可用：%s" % exc)
            live_contract = None
        if live_contract and contract.get("sha256") != live_contract["sha256"]:
            issues.append("契约漂移：记录=%s 实测=%s"
                          % (str(contract.get("sha256"))[:12], live_contract["sha256"][:12]))
    elif contract is not None:
        issues.append("契约字段形状非法（须为对象或 null）")
    cog = card.get("cognition")
    if isinstance(cog, dict):
        ev = ce.load(str(cog.get("digest") or ""))
        if ev is None:
            issues.append("cognition_unverifiable：事件不在本地事件库（不冒充通过）")
        else:
            bad = ce.verify(ev)
            if bad:
                issues.append("cognition event 非法：%s" % ",".join(bad))
            if ev.get("digest") != cog.get("digest"):
                issues.append("cognition digest 不一致")
            if ev.get("handoff_digest") != cog.get("handoff_digest"):
                issues.append("cognition handoff digest 不一致")
            # 证据角色只许原样传播：先各自做白名单/值域校验（非法即 issue），
            # 再逐值比较（缺省 None==None 不误报，旧卡行为不变）。
            for label, roles in (("card", cog.get("evidence_roles")),
                                 ("event", ev.get("evidence_roles"))):
                if roles is None:
                    continue
                try:
                    ce.validate_roles(roles)
                except ValueError as exc:
                    issues.append("cognition %s evidence_roles 非法：%s"
                                  % (label, exc))
            if ev.get("evidence_roles") != cog.get("evidence_roles"):
                issues.append("cognition evidence_roles 不一致")
    elif cog is not None:
        issues.append("cognition 块形状非法")
    return {"ok": not issues, "issues": issues, "live": live}


def diff_cards(a: Any, b: Any) -> Dict[str, Any]:
    out = {"same_subject": False, "changed": []}
    sa = (a or {}).get("subject") or {}
    sb = (b or {}).get("subject") or {}
    out["same_subject"] = bool(sa.get("path") and sa.get("path") == sb.get("path") and
                              sa.get("sha256") == sb.get("sha256"))
    for field in ("path", "sha256", "bytes", "line_count"):
        if sa.get(field) != sb.get(field):
            out["changed"].append({"field": field, "a": sa.get(field), "b": sb.get(field)})
    if (a or {}).get("contract") != (b or {}).get("contract"):
        out["changed"].append({"field": "contract", "a": (a or {}).get("contract"),
                               "b": (b or {}).get("contract")})
    return out


def cockpit_summary() -> Dict[str, Any]:
    """驾驶舱视图：按 kind 计数 + 最近 decision/action/evidence。"""
    rows = cockpit_log.records(limit=500)
    by: Dict[str, int] = {}
    for r in rows:
        by[r.get("kind", "?")] = by.get(r.get("kind", "?"), 0) + 1
    latest = {k: [r for r in rows if r.get("kind") == k][-3:] for k in
              ("decision", "action", "evidence", "claim", "context")}
    return {"count": len(rows), "by_kind": by, "latest": latest,
            "log": str(cockpit_log.log_path())}


def list_contracts(root: str | Path = ".", query: str = "") -> List[Dict[str, Any]]:
    doc = json_doc.load(_root(root) / "protocol" / "domain_packs.json", dict,
                        what="protocol/domain_packs.json")
    q = str(query or "").strip().lower()
    out = []
    for p in doc.get("packs") or []:
        name = str(p.get("name") or p.get("id") or "")
        if q and q not in name.lower() and q not in str(p.get("code") or "").lower():
            continue
        out.append({"name": name, "code": p.get("code"),
                    "package": p.get("package"),
                    "content_tier": p.get("content_tier"),
                    "subdivisions": p.get("subdivisions")})
    return out


TOOLS: Dict[str, Dict[str, Any]] = {
    "evidence_card": {"description": "为仓内文件生成可离线复算的证据卡",
                      "inputSchema": {"type": "object", "required": ["path"],
                                      "properties": {"path": {"type": "string"},
                                                     "contract": {"type": "string"},
                                                     "note": {"type": "string"},
                                                     "min_names": {"type": "integer"},
                                                     "min_fields": {"type": "integer"},
                                                     "min_rules": {"type": "integer"},
                                                     "cognition": {"type": "object"}},
                                      "additionalProperties": False}},
    "verify_card": {"description": "重算主体摘要并与证据卡比对（防篡改/过期）",
                    "inputSchema": {"type": "object", "required": ["card"],
                                    "properties": {"card": {"type": "object"}},
                                    "additionalProperties": False}},
    "diff_cards": {"description": "比较两张证据卡，列出变化字段",
                   "inputSchema": {"type": "object", "required": ["a", "b"],
                                   "properties": {"a": {"type": "object"}, "b": {"type": "object"}},
                                   "additionalProperties": False}},
    "cognition_event": {"description": "把 cockpit manifest(+journal) 收敛为 nf-cognition-event/1 并写入本地事件库",
                        "inputSchema": {"type": "object", "required": ["manifest"],
                                        "properties": {"manifest": {"type": "string"},
                                                       "journal": {"type": "string"}},
                                        "additionalProperties": False}},
    "contract_rules": {"description": "把 domain pack 的 12 条细分规则编译成机读规则表（含 digest）",
                       "inputSchema": {"type": "object", "required": ["contract"],
                                       "properties": {"contract": {"type": "string"}},
                                       "additionalProperties": False}},
    "check_artifact": {"description": "对仓内产物跑通用检查（存在/UTF-8/JSON/模块契约）",
                       "inputSchema": {"type": "object", "required": ["path"],
                                       "properties": {"path": {"type": "string"}},
                                       "additionalProperties": False}},
    "attach_decision": {"description": "把决策/假设/动作写入本地驾驶舱日志（只追加、仓库外）",
                        "inputSchema": {"type": "object", "required": ["kind", "text"],
                                        "properties": {"kind": {"type": "string"},
                                                       "text": {"type": "string"},
                                                       "context": {"type": "string"},
                                                       "refs": {"type": "array", "items": {"type": "string"}},
                                                       "evidence": {"type": "array", "items": {"type": "string"}}},
                                        "additionalProperties": False}},
    "close_action": {"description": "关闭一个动作：必须带证据引用（仓内路径或决策 id）",
                     "inputSchema": {"type": "object", "required": ["action_id", "evidence"],
                                     "properties": {"action_id": {"type": "string"},
                                                    "evidence": {"type": "array", "items": {"type": "string"}},
                                                    "result": {"type": "string"}},
                                     "additionalProperties": False}},
    "cockpit_summary": {"description": "驾驶舱视图：按 kind 计数 + 最近决策/动作/证据",
                        "inputSchema": {"type": "object", "properties": {},
                                        "additionalProperties": False}},
    "list_decisions": {"description": "读本地驾驶舱日志（可按 kind 过滤）",
                       "inputSchema": {"type": "object",
                                       "properties": {"kind": {"type": "string"},
                                                      "limit": {"type": "integer"}},
                                       "additionalProperties": False}},
    "list_contracts": {"description": "按关键词列 domain pack 契约",
                       "inputSchema": {"type": "object",
                                       "properties": {"query": {"type": "string"}},
                                       "additionalProperties": False}},
}


def call_tool(name: str, arguments: Dict[str, Any], root: str | Path = ".") -> Dict[str, Any]:
    args = arguments or {}
    if name == "evidence_card":
        return {"content": [{"type": "text", "text": json.dumps(
            evidence_card(args["path"], root, args.get("contract", ""), args.get("note", ""),
                          args.get("min_names", COVERAGE_MIN_NAMES),
                          args.get("min_fields", COVERAGE_MIN_FIELDS),
                          args.get("min_rules", COVERAGE_MIN_RULES),
                          args.get("cognition")),
            ensure_ascii=False, sort_keys=True)}]}
    if name == "verify_card":
        return {"content": [{"type": "text", "text": json.dumps(
            verify_card(args["card"], root), ensure_ascii=False, sort_keys=True)}]}
    if name == "diff_cards":
        return {"content": [{"type": "text", "text": json.dumps(
            diff_cards(args["a"], args["b"]), ensure_ascii=False, sort_keys=True)}]}
    if name == "cognition_event":
        ev = ce.from_manifest_file(args["manifest"], args.get("journal"))
        return {"content": [{"type": "text", "text": json.dumps(ev, ensure_ascii=False, sort_keys=True)}]}
    if name == "contract_rules":
        pack = _resolve_contract(args["contract"], root)
        rules = domain_rules.build_rules(str(pack["package"]), root)
        return {"content": [{"type": "text", "text": json.dumps(
            rules, ensure_ascii=False, sort_keys=True)}]}
    if name == "check_artifact":
        return {"content": [{"type": "text", "text": json.dumps(
            artifact_checks(args["path"], root), ensure_ascii=False, sort_keys=True)}]}
    if name == "attach_decision":
        return {"content": [{"type": "text", "text": json.dumps(
            cockpit_log.append({k: args.get(k) for k in ("kind", "text", "context", "refs", "evidence")}),
            ensure_ascii=False, sort_keys=True)}]}
    if name == "close_action":
        aid = str(args.get("action_id") or "").strip()
        ev = [str(x) for x in (args.get("evidence") or [])]
        bad = []
        for rel in ev:
            if rel.startswith("card:"):
                # 证据卡 digest 引用：只做形态校验（语义「关闭必须带 card」
                # 由 M1 脚本与 verify.sh check45 保证）；非法即 fail-closed。
                if not _CARD_DIGEST_RE.match(rel):
                    bad.append(rel)
                continue
            if rel.startswith("cog-") or rel.startswith("cog-event:"):
                if rel.startswith("cog-event:") and ce.load(rel.split(":", 1)[1]) is None:
                    bad.append(rel)
                continue
            try:
                paths.validate_path(str(_root(root)), rel)
            except (ValueError, paths.PathEscapeError):
                bad.append(rel)
        if not aid or not ev or bad:
            raise ValueError("close_action 需 action_id + evidence；非法证据：%s" % (bad or "空"))
        rec = cockpit_log.append({"kind": "action", "text": "closed: %s" % (args.get("result") or aid),
                                  "refs": [aid], "evidence": ev})
        return {"content": [{"type": "text", "text": json.dumps(rec, ensure_ascii=False, sort_keys=True)}]}
    if name == "cockpit_summary":
        return {"content": [{"type": "text", "text": json.dumps(
            cockpit_summary(), ensure_ascii=False, sort_keys=True)}]}
    if name == "list_decisions":
        return {"content": [{"type": "text", "text": json.dumps(
            cockpit_log.records(args.get("kind", ""), args.get("limit", 50)),
            ensure_ascii=False, sort_keys=True)}]}
    if name == "list_contracts":
        return {"content": [{"type": "text", "text": json.dumps(
            list_contracts(root, args.get("query", "")), ensure_ascii=False, sort_keys=True)}]}
    raise KeyError(name)


def handle(request: Dict[str, Any], root: str | Path = ".") -> Dict[str, Any]:
    """纯函数式 JSON-RPC 分派（stdio 循环只负责收发，便于单测）。"""
    rid = request.get("id")
    method = request.get("method")
    params = request.get("params") or {}
    def ok(result): return {"jsonrpc": "2.0", "id": rid, "result": result}
    def err(code, msg): return {"jsonrpc": "2.0", "id": rid, "error": {"code": code, "message": msg}}
    if method == "initialize":
        return ok({"protocolVersion": "2026-07-28", "capabilities": {"tools": {}},
                   "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION}})
    if method == "notifications/initialized":
        return {}
    if method == "ping":
        return ok({})
    if method == "tools/list":
        return ok({"tools": [{"name": k, **v} for k, v in TOOLS.items()]})
    if method == "tools/call":
        name = params.get("name")
        if name not in TOOLS:
            return err(-32602, "未知工具：%s" % name)
        try:
            return ok(call_tool(name, params.get("arguments") or {}, root))
        except (KeyError, ValueError, OSError, TypeError, paths.PathEscapeError) as exc:
            return err(-32602, "参数/主体不合法：%s" % exc)
    return err(-32601, "未实现的方法：%s" % method)
