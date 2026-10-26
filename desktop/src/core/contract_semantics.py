"""T7.1 · 契约语义可判定核心（nf-contract-semantics/1）。

把「内容契约」落成可判定的最小形式核心：**五概念模型 + 三条良构规则 + 规范形**。

五概念（从真源构建，不猜测）：
  Slot   = (path, kind, owner)          真源 protocol/world_slots.json + 模块 io_types/world_model
  Event  = (name, publishers, subscribers) 真源 模块头 machine_contract.events + registry.subscriptions
  Layer  = (id, rank, defaults, alloweds)  真源 03_管线库/*.md + community/*/pipelines/*.md
  Module = (id, layer, inputs, events, domain) 真源 registry.modules + 包 protocol 投影 + 04_模块库 机读块
  Gate   = (pipeline, module, verdicts, on_undefined) 真源 各管线 P80 层 + M80 §3 判据

三规则：
  W1 层序闭包：consumer ← producer 的 rank(producer) ≤ rank(consumer)；
                倒挂且未登记 protocol/layer_exceptions.json → FAIL，已登记 → WARN。
  W2 域隔离  ：包 module_ids 的模块须属本包（或官方核心 / references 白名单）；
                跨包归属且不在 references → FAIL。域字段缺省/资产域缺失 → WARN（不可判定）。
  W3 门全性  ：每条管线 P80 层须在场且绑定输出门；M80 在场时 gate 判定域须 = {pass,warn,fail}
                且 on_undefined = "fail"（异常 fail-closed）→ 否则 FAIL；P80 无 M80 → WARN（不可判定）。

canonicalize：对 registry 子集做规范形（键排序 / 集合排序 / 数字规范化 / 路径 POSIX / 紧凑分隔符）
→ UTF-8 字节 → SHA-256；带版本域名 `nf-sem-canon/1`，两次/乱序输入结果一致（幂等 + 稳定）。

CLI：`nf spec check --core [--json]` / `nf spec canonical [--json]`（scripts/nf.py）。
退出码：0 = 无 FAIL（WARN 可接受）；1 = 有 FAIL；2 = 无法判定/输入不可读（fail-closed）。
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Literal, NamedTuple, Optional, Sequence, Tuple

from core import json_doc, pipeline_loader

SCHEMA = "nf-contract-semantics/1"
CANON_VERSION = "nf-sem-canon/1"
CANON_SCHEMA = "nf-sem-canon-payload/1"

REGISTRY_REL = "desktop/src/core/registry.json"
SLOTS_REL = "protocol/world_slots.json"
EXTERNAL_EVENTS_REL = "protocol/external_events.json"
PROVENANCE_REL = "05_资产库/provenance.json"
EXCEPTIONS_REL = "protocol/layer_exceptions.json"

_CORE_MODULE_DIR = "04_模块库"
_REQ_VERDICTS = ("pass", "warn", "fail")
Verdict = Literal["pass", "warn", "fail"]


class GateSpec(NamedTuple):
    """门类型：判定域 + 未定义/异常时的落点（fail-closed）。

    类型层表达：`verdicts` 恰为 {pass,warn,fail}；`on_undefined` 必须是 fail。
    """

    verdicts: Tuple[Verdict, ...]
    on_undefined: Verdict


#: 门全性策略（真源：04_模块库/通用类/M80_输出质检门.md:46-62「gate / gate_action / 判定」）。
GATE_POLICY = GateSpec(("pass", "warn", "fail"), "fail")

#: 规则证据（file:line；WARN/FAIL 都带，保证可追溯）。
EVIDENCE = {
    "W1": ("01_核心协议.md:160-171", "protocol/layer_exceptions.json:1-50",
           "04_模块库/事件类/M06_流程状态机.md:12-13"),
    "W2": ("01_核心协议.md:176-182", "02_联动注册表.md:1114-1133",
           "desktop/src/core/registry.json:288"),
    "W3": ("04_模块库/通用类/M80_输出质检门.md:46-62",
           "06_Agent执行协议.md:122-136", "03_管线库/P01_标准管线.md:10-30"),
    "SLOT": ("protocol/world_slots.json:4-46", "01_核心协议.md:48-51,65-85"),
    "EVENT": ("01_核心协议.md:57", "02_联动注册表.md:28-48"),
}

_BASE = re.compile(r"^([^:]*:)?(?P<base>M[0-9]{2,3})$")


def _base(mid: Any) -> str:
    m = _BASE.match(str(mid or "").strip())
    return m.group("base") if m else str(mid or "").strip()


def _pipe(base: str) -> str:
    return str(base).split(":")[-1]


def _issue(rule: str, code: str, severity: str, subject: str, message: str,
           evidence: Sequence[str] = (), fix: str = "") -> Dict[str, Any]:
    return {"rule": rule, "code": code, "severity": severity,
            "subject": str(subject), "message": message,
            "evidence": list(evidence or EVIDENCE.get(rule, ())), "fix": fix}


# ---------------------------------------------------------------- 载入（真源）
def _root(root: Any) -> Path:
    return Path(root)


def _read_slots(root: Path) -> Dict[str, Any]:
    data = json_doc.load(root / SLOTS_REL, dict, what=SLOTS_REL)
    return {str(k): v for k, v in (data.get("slots") or {}).items()}


def _read_registry(root: Path) -> Dict[str, Any]:
    return json_doc.load(root / REGISTRY_REL, dict, what=REGISTRY_REL)


def _read_exceptions(root: Path) -> Dict[Tuple[str, str], Dict[str, Any]]:
    from core import layer_closure as lc
    try:
        return lc.load_exceptions(str(root))
    except ValueError as exc:
        raise ValueError("层序例外表不可用：%s（修复指引：核对 %s）"
                         % (exc, EXCEPTIONS_REL))


def _read_pipelines(root: Path) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    files = sorted((root / "03_管线库").glob("*.md")) + \
        sorted((root / "community").glob("*/pipelines/*.md"))
    for f in files:
        try:
            pipe = pipeline_loader.load_pipeline_file(f)
        except (OSError, ValueError):
            pipe = None
        if pipe is None:
            continue
        rel = f.relative_to(root).as_posix()
        layers = [{"id": str(l.id), "default": [_pipe(x) for x in l.default_modules],
                   "allowed": [_pipe(x) for x in l.allowed_modules],
                   "optional": bool(l.optional), "name": str(l.name)}
                  for l in pipe.layers]
        out[str(pipe.id)] = {"id": str(pipe.id), "source": rel, "layers": layers,
                             "types": [t.get("from") for t in getattr(pipe, "dependencies", [])
                                       if isinstance(t, dict)]}
    return out


def _read_contracts(root: Path) -> Tuple[Dict[str, Any], Dict[str, List[str]],
                                         Dict[str, List[str]], List[str]]:
    """模块头机读块 → (core 契约, publishers, subscribers, 解析缺口)。"""
    from core import conformance_scan as csc

    core: Dict[str, Any] = {}
    publishers: Dict[str, List[str]] = {}
    subscribers: Dict[str, List[str]] = {}
    gaps: List[str] = []
    for doc in csc._module_docs(str(root)):
        rel = Path(doc).relative_to(root).as_posix()
        try:
            text = Path(doc).read_text(encoding="utf-8")
        except OSError:
            gaps.append(rel)
            continue
        mc = csc._fence_yaml(text, "machine_contract").get("machine_contract")
        if not isinstance(mc, dict) or not mc.get("id"):
            gaps.append(rel)
            continue
        mid = _base(mc.get("id"))
        ev = mc.get("events") if isinstance(mc.get("events"), dict) else {}
        for name in ev.get("publish") or []:
            publishers.setdefault(str(name), []).append(mid)
        for name in ev.get("subscribe") or []:
            subscribers.setdefault(str(name), []).append(mid)
        if rel.startswith(_CORE_MODULE_DIR + "/"):
            core[mid] = {"id": mid, "raw_id": str(mc.get("id")), "layer": str(mc.get("layer") or ""),
                         "inputs": [_base(x) for x in (mc.get("inputs") or [])],
                         "outputs": [str(x) for x in (mc.get("outputs") or [])],
                         "events": {"publish": [str(x) for x in ev.get("publish") or []],
                                    "subscribe": [str(x) for x in ev.get("subscribe") or []]},
                         "io_types": mc.get("io_types") if isinstance(mc.get("io_types"), dict) else {},
                         "world_model": mc.get("world_model") if isinstance(mc.get("world_model"), dict) else {},
                         "conformance": str(mc.get("conformance") or ""), "source": rel}
    return core, publishers, subscribers, gaps


def _read_package_domains(root: Path) -> Dict[str, str]:
    """包 domain：protocol.yaml `package.domain` → categories[0] → 包 id（逐级代偿）。"""
    out: Dict[str, str] = {}
    from core import lazy_yaml
    yaml = lazy_yaml.module()
    if yaml is None:
        return out
    for proto in sorted((root / "community").glob("*/protocol.yaml")):
        try:
            data = yaml.safe_load(proto.read_text(encoding="utf-8")) or {}
        except (OSError, ValueError, TypeError):
            continue
        pkg = data.get("package") if isinstance(data.get("package"), dict) else {}
        pid = str(pkg.get("id") or "").strip()
        cats = [str(c) for c in (pkg.get("categories") or [])]
        dom = str(pkg.get("domain") or "").strip() or (cats[0] if cats else "")
        if pid:
            out[pid] = dom
    return out


def load_model(root: Any = ".") -> Dict[str, Any]:
    """从真源构建五概念模型（不可读 → ValueError，CLI rc=2，不静默降级）。"""
    root_p = _root(root)
    reg = _read_registry(root_p)
    slots = _read_slots(root_p)
    exceptions = _read_exceptions(root_p)
    pipelines = _read_pipelines(root_p)
    core, publishers, subscribers, gaps = _read_contracts(root_p)
    domains = _read_package_domains(root_p)
    try:
        external = json_doc.load(root_p / EXTERNAL_EVENTS_REL, dict, what=EXTERNAL_EVENTS_REL)
    except ValueError:
        external = {}
    external_events = set((external.get("events") or {}).keys()) if isinstance(
        external.get("events"), dict) else set()

    modules: Dict[str, Any] = {}
    for m in reg.get("modules") or []:
        mid = str(m.get("id") or "")
        if mid:
            modules[mid] = {"id": mid, "name": str(m.get("name") or ""),
                            "category": str(m.get("category") or ""),
                            "source": str(m.get("source") or ""),
                            "mounts": [{k: str(v) for k, v in (mt or {}).items()}
                                       for mt in (m.get("mounts") or []) if isinstance(mt, dict)],
                            "package": "", "domain": ""}
    packages: Dict[str, Any] = {}
    claims: Dict[str, List[str]] = {}
    for p in reg.get("protocols") or []:
        pid = str(p.get("id") or "")
        if not pid:
            continue
        mids = [str(x) for x in (p.get("module_ids") or [])]
        refs = [str(r.get("module_id")) for r in (p.get("references") or [])
                if isinstance(r, dict) and r.get("module_id")]
        packages[pid] = {
            "id": pid, "pipeline": str(p.get("pipeline") or ""),
            "categories": [str(c) for c in (p.get("categories") or [])],
            "domain": str(p.get("domain") or "").strip() or domains.get(pid, "")
                      or (str((p.get("categories") or [""])[0]) if p.get("categories") else ""),
            "module_ids": mids, "references": refs,
            "mount_layers": p.get("mount_layers") or {}, "schema_version": p.get("schema_version"),
        }
        for mid in mids:
            claims.setdefault(mid, []).append(pid)
            modules.setdefault(mid, {"id": mid, "name": "", "category": "",
                                     "source": "社区包", "mounts": [],
                                     "package": pid, "domain": packages[pid]["domain"]})
            if not modules[mid].get("package"):
                modules[mid]["package"] = pid
                modules[mid]["domain"] = packages[pid]["domain"]

    # 管线 → 包映射 + P80 门候选
    pipe_pkgs: Dict[str, List[str]] = {}
    for pid, pk in packages.items():
        if pk["pipeline"]:
            pipe_pkgs.setdefault(pk["pipeline"], []).append(pid)
    for pipe in pipelines.values():
        p80 = next((l for l in pipe["layers"] if l["id"] == "P80"), None)
        pipe["p80"] = p80
        gate_mods = sorted({m for m in ((p80["default"] if p80 else [])
                                        + (p80["allowed"] if p80 else [])) if _pipe(m) == "M80"})
        pipe["gate_modules"] = gate_mods
        pipe["packages"] = sorted(pipe_pkgs.get(pipe["id"], []))

    # 资产域（不可判定项：05 provenance 无 domain 字段）
    asset_domain_unknown = []
    try:
        prov = json_doc.load(root_p / PROVENANCE_REL, dict, what=PROVENANCE_REL)
        for a in prov.get("assets") or []:
            if isinstance(a, dict) and not str(a.get("domain") or "").strip():
                asset_domain_unknown.append(str(a.get("key") or a.get("file") or "?"))
    except ValueError:
        asset_domain_unknown = ["（provenance 不可读）"]

    return {
        "schema": SCHEMA, "root": str(root_p),
        "registry_schema_version": str(reg.get("registry_schema_version") or ""),
        "modules": modules,
        "module_bases": sorted({_base(m) for m in modules} | set(core)),
        "core_modules": sorted(core), "core_contracts": core,
        "packages": packages, "module_claims": claims,
        "pipelines": pipelines, "slots": slots,
        "publishers": publishers, "subscribers": subscribers,
        "external_events": sorted(external_events),
        "layer_exceptions": {"%s←%s" % k: v for k, v in exceptions.items()},
        "contract_gaps": sorted(gaps), "asset_domain_unknown": asset_domain_unknown,
        "gate_policy": {"verdicts": list(GATE_POLICY.verdicts),
                        "on_undefined": GATE_POLICY.on_undefined},
        "package_domain_declared": sum(1 for p in packages.values() if p["domain"]),
    }


# ---------------------------------------------------------------- 三规则
def _w1_layer_closure(model: Dict[str, Any]) -> List[Dict[str, Any]]:
    issues: List[Dict[str, Any]] = []
    p01 = model["pipelines"].get("P01")
    if not p01:
        return [_issue("W1", "layer_pipeline_missing", "FAIL", "P01",
                       "缺 P01 标准管线，层序闭包不可判定",
                       fix="恢复 03_管线库/P01_标准管线.md 或改判据入口")]
    rank = {l["id"]: i for i, l in enumerate(p01["layers"])}
    if len(rank) != len(p01["layers"]):
        issues.append(_issue("W1", "layer_duplicate", "FAIL", "P01",
                             "P01 layers[].id 有重复", fix="管线层 id 须唯一"))
    exceptions = model["layer_exceptions"]
    used = set()
    for mid, mc in sorted(model["core_contracts"].items()):
        layer = mc.get("layer")
        if layer not in rank:
            continue                      # 调度器 / P90 专线：不在 P01 层序内
        for dep in mc.get("inputs") or []:
            prod = _base(dep)
            pmc = model["core_contracts"].get(prod)
            if not pmc or pmc.get("layer") not in rank:
                continue
            if rank[pmc["layer"]] <= rank[layer]:
                continue
            key = "%s←%s" % (mid, prod)
            if key in exceptions:
                used.add(key)
                issues.append(_issue(
                    "W1", "layer_inversion_registered", "WARN", key,
                    "%s(%s) ← %s(%s) 层序倒挂，已在例外表登记（不计 FAIL）"
                    % (mid, layer, prod, pmc["layer"]),
                    evidence=[str(exceptions[key].get("evidence") or "")]))
            else:
                issues.append(_issue(
                    "W1", "layer_inversion", "FAIL", key,
                    "%s(%s) ← %s(%s)：生产者位于更后的层（rank %d > %d）"
                    % (mid, layer, prod, pmc["layer"], rank[pmc["layer"]], rank[layer]),
                    fix="调整层位/挂载，或在 %s 登记例外并写明 reason" % EXCEPTIONS_REL))
    unused = sorted(set(exceptions) - used)
    if unused:
        issues.append(_issue("W1", "layer_exception_unused", "WARN", "、".join(unused),
                             "例外表条目未被消费（双向耦合另一向或已修复）；清账时必须可见",
                             evidence=[EXCEPTIONS_REL + ":1-50"]))
    unknown = [l for l in rank if l not in {str(x["id"]) for x in p01["layers"]}]
    if unknown:
        issues.append(_issue("W1", "layer_unknown", "FAIL", "、".join(unknown),
                             "层 id 不在 P01 层表内"))
    return issues


def _w2_domain_isolation(model: Dict[str, Any]) -> List[Dict[str, Any]]:
    issues: List[Dict[str, Any]] = []
    core = set(model["core_modules"])
    for pid, pk in sorted(model["packages"].items()):
        refs = {_base(x) for x in pk["references"]}
        own_dom = pk["domain"]
        if not own_dom:
            issues.append(_issue("W2", "domain_undeclared", "WARN", pid,
                                 "包 %s 未声明 domain（protocol.yaml package.domain / categories 均缺）"
                                 "→ 域一致性不可判定" % pid,
                                 evidence=["protocol/schema/protocol.schema.json:27-31"],
                                 fix="在 protocol.yaml 写 package.domain（可选字段，01 §6.1）"))
        for mid in pk["module_ids"]:
            if mid in set(model["core_modules"]) or _base(mid) in refs:
                continue
            holders = [p for p in model["module_claims"].get(mid, []) if p != pid]
            if holders:
                issues.append(_issue(
                    "W2", "cross_domain_module", "FAIL", "%s←%s" % (pid, mid),
                    "包 %s 声明了 %s 的模块 %s，且不在 references 白名单"
                    % (pid, "、".join(holders), mid),
                    fix="移除该模块，或经 package.references 受控引用（01 §6 R1）"))
        # module.domain 若显式声明，须与包 domain 一致
        for mid in pk["module_ids"]:
            m = model["modules"].get(mid) or {}
            mdom = str(m.get("domain") or "").strip()
            if mdom and own_dom and mdom != own_dom:
                issues.append(_issue("W2", "module_domain_mismatch", "FAIL", mid,
                                     "模块 %s 声明 domain=%r ≠ 包域 %r" % (mid, mdom, own_dom),
                                     fix="对齐模块 domain 与包 domain"))
    if model["asset_domain_unknown"]:
        issues.append(_issue(
            "W2", "asset_domain_unverifiable", "WARN", "05_资产库/provenance.json",
            "资产台账 %d 条缺 domain 字段（schema 可选）→ 资产域一致性**不可判定**，"
            "本轮不判 PASS；修复指引：回填 domain 后本规则方可判定"
            % len(model["asset_domain_unknown"]),
            evidence=["protocol/schema/asset.schema.json:8-17", "05_资产库/provenance.json:1-30"],
            fix="为 provenance assets[] 补 domain（T2.1 已留可选字段）"))
    pipe_unbound = []  # 门绑定缺失归 W3（避免同码 WARN 双报）
    # 管线 domain 一致性（若显式声明）
    for pipe_id, pipe in sorted(model["pipelines"].items()):
        pkg_doms = sorted({model["packages"][p]["domain"] for p in pipe.get("packages") or []
                           if model["packages"][p]["domain"]})
        if len(pkg_doms) > 1:
            issues.append(_issue("W2", "pipeline_domain_conflict", "FAIL", pipe_id,
                                 "同一管线被多个不同域的包声明：%s" % "、".join(pkg_doms),
                                 fix="管线归属须唯一域；组合需求走组合包 references"))
    return issues


def _w3_gate_totality(model: Dict[str, Any]) -> List[Dict[str, Any]]:
    issues: List[Dict[str, Any]] = []
    policy = model["gate_policy"]
    verdicts = tuple(policy.get("verdicts") or ())
    on_undef = str(policy.get("on_undefined") or "")
    if set(verdicts) != set(_REQ_VERDICTS):
        issues.append(_issue("W3", "gate_not_total", "FAIL", "gate_policy",
                             "门判定域不完整：%r（须恰为 pass/warn/fail）" % (verdicts,),
                             fix="恢复 GATE_POLICY.verdicts"))
    if on_undef != "fail":
        issues.append(_issue("W3", "gate_not_total", "FAIL", "gate_policy",
                             "门异常/未定义落点=%r ≠ fail（违 fail-closed）" % on_undef,
                             fix="on_undefined 必须为 fail（异常=FAIL）"))
    m80 = model["core_contracts"].get("M80")
    if m80 and m80.get("layer") != "P80":
        issues.append(_issue("W3", "gate_misplaced", "FAIL", "M80",
                             "输出门 M80 挂载层=%r ≠ P80" % m80.get("layer"),
                             fix="M80 必须在 P80 层"))
    if m80 and str(m80.get("conformance") or "") not in ("L1", "L2", "L3"):
        issues.append(_issue("W3", "gate_undeclared", "FAIL", "M80",
                             "输出门 M80 机读契约缺 conformance 声明（门声明不完整）",
                             fix="按 01 §1.2 声明 conformance ≥L1"))
    for pipe_id, pipe in sorted(model["pipelines"].items()):
        if pipe_id == "P00":
            continue
        p80 = pipe.get("p80")
        if p80 is None:
            issues.append(_issue("W3", "gate_missing", "FAIL", pipe_id,
                                 "管线缺 P80 输出层 → 无输出门，门全性不成立",
                                 fix="补 P80 层并绑定 M80（唯一输出闸）"))
            continue
        gate = [m for m in (p80.get("default") or []) + (p80.get("allowed") or [])
                if _pipe(m) == "M80"]
        if not gate:
            issues.append(_issue("W3", "gate_unbound", "WARN", pipe_id,
                                 "P80 层未绑定 M80（门全性不可判定，不假装通过；修复指引："
                                 "在 P80 default/allowed 绑定 M80 或登记门声明）",
                                 evidence=[pipe.get("source", "")]))
    return issues


def _slot_and_event_rules(model: Dict[str, Any]) -> List[Dict[str, Any]]:
    issues: List[Dict[str, Any]] = []
    slots = model["slots"]
    for path, spec in sorted(slots.items()):
        owner = _base((spec or {}).get("owner"))
        if owner and owner not in set(model["module_bases"]):
            issues.append(_issue("SLOT", "slot_owner_missing", "FAIL", path,
                                 "槽 %s 的 owner=%s 不在模块表" % (path, (spec or {}).get("owner")),
                                 fix="在 registry.json modules[] 登记 owner 模块"))
    # 世界模型变量 → 槽绑定
    m50 = model["core_contracts"].get("M50") or {}
    wm = m50.get("world_model") if isinstance(m50.get("world_model"), dict) else {}
    for var in ((wm.get("abstract_state") or {}).get("variables") or []):
        if not isinstance(var, dict) or not var.get("slot"):
            continue
        slot = str(var["slot"])
        if slot not in slots:
            issues.append(_issue("SLOT", "slot_unbound", "FAIL", slot,
                                 "world_model 变量 %r 绑定未注册槽 %s" % (var.get("name"), slot),
                                 fix="在 protocol/world_slots.json 注册该槽"))
            continue
        want = str(var.get("kind") or "")
        have = str((slots[slot] or {}).get("kind") or "")
        if want and have and want != have:
            issues.append(_issue("SLOT", "slot_kind_mismatch", "FAIL", slot,
                                 "槽 %s 类型 %r ≠ world_model 变量类型 %r" % (slot, have, want),
                                 fix="对齐 world_slots.kind 与模块变量 kind"))
    # io_types.inputs → 前置模块须在模块表
    for mid, mc in sorted(model["core_contracts"].items()):
        inputs = ((mc.get("io_types") or {}).get("inputs") or {})
        for dep in inputs:
            base = _base(dep)
            if base not in set(model["module_bases"]):
                issues.append(_issue("SLOT", "io_input_unbound", "FAIL", "%s←%s" % (mid, dep),
                                     "io_types.inputs 指向不存在的前置模块 %s" % dep,
                                     fix="登记该模块或修正 io_types"))
    # 事件：订阅方须有发布方（核心契约 + 全量模块头 + external_events + registry 订阅）
    publishers = {k: set(v) for k, v in model["publishers"].items()}
    for name in model["external_events"]:
        publishers.setdefault(name, set()).add("external")
    try:
        reg = _read_registry(_root(model["root"]))
        for name, sub in (reg.get("subscriptions") or {}).items():
            pub = _base((sub or {}).get("publisher"))
            if pub:
                publishers.setdefault(str(name), set()).add(pub)
    except ValueError:
        pass
    for name, subs in sorted(model["subscribers"].items()):
        if name not in publishers and not publishers.get(name):
            issues.append(_issue("EVENT", "orphan_event", "FAIL", name,
                                 "事件 %s 有订阅方（%s）但全库无发布方"
                                 % (name, "、".join(sorted(set(subs))[:4])),
                                 fix="补发布方（唯一）或从订阅面移除；跨包经事件桥（01 §6 R1）"))
    return issues


def _duplicate_rules(model: Dict[str, Any]) -> List[Dict[str, Any]]:
    issues: List[Dict[str, Any]] = []
    seen: Dict[str, int] = {}
    for mid in model["modules"]:
        seen[mid] = seen.get(mid, 0) + 1
    # modules 是 dict（天然唯一）；重复由原始 claims 面暴露
    for mid, holders in sorted(model["module_claims"].items()):
        uniq = sorted(set(holders))
        if len(uniq) > 1:
            issues.append(_issue("W2", "duplicate_module_claim", "FAIL", mid,
                                 "模块 %s 同时被多包声明：%s" % (mid, "、".join(uniq)),
                                 fix="module id 全局唯一（02 §8.3）；跨包走 references 而非重复声明"))
    if model["registry_schema_version"] not in ("2",):
        issues.append(_issue("S0", "registry_schema_unknown", "WARN",
                             "registry_schema_version",
                             "registry_schema_version=%r（期望 \"2\"）"
                             % model["registry_schema_version"],
                             fix="核对 registry.json 头部版本"))
    return issues


def check_model(model: Dict[str, Any]) -> Dict[str, Any]:
    """对已构建模型跑三规则 + 槽/事件/重复 id → 结构化报告。"""
    issues: List[Dict[str, Any]] = []
    issues += _w1_layer_closure(model)
    issues += _w2_domain_isolation(model)
    issues += _w3_gate_totality(model)
    issues += _slot_and_event_rules(model)
    issues += _duplicate_rules(model)
    fails = [i for i in issues if i["severity"] == "FAIL"]
    warns = [i for i in issues if i["severity"] == "WARN"]
    verdict: Verdict = "fail" if fails else ("warn" if warns else "pass")
    return {
        "schema": SCHEMA, "verdict": verdict,
        "issues": issues, "fails": fails, "warns": warns,
        "stats": {"modules": len(model["modules"]),
                  "core_modules": len(model["core_modules"]),
                  "packages": len(model["packages"]),
                  "pipelines": len(model["pipelines"]),
                  "slots": len(model["slots"]),
                  "events": len(set(model["publishers"]) | set(model["subscribers"])),
                  "contract_gaps": len(model["contract_gaps"]),
                  "fail": len(fails), "warn": len(warns)},
    }


# ---------------------------------------------------------------- 规范形
def _canon_path(value: str) -> str:
    return value.replace("\\", "/")


def _canon_number(value: Any) -> Any:
    if isinstance(value, bool):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return value


def canonicalize(value: Any, *, _sets: bool = True) -> Any:
    """规范形：dict 键排序 / 集合型 list 排序去重 / 数字规范化 / 路径 POSIX。"""
    if isinstance(value, dict):
        return {str(k): canonicalize(v, _sets=_sets) for k, v in sorted(value.items(),
                                                                       key=lambda kv: str(kv[0]))}
    if isinstance(value, list):
        items = [canonicalize(v, _sets=_sets) for v in value]
        if _sets:
            if all(not isinstance(v, (dict, list)) for v in items):
                try:
                    return sorted(set(items), key=lambda v: (str(type(v)), str(v)))
                except TypeError:
                    return items
            # 对象列表按规范 JSON 文本定序（registry modules/protocols 无顺序语义）
            return sorted(items, key=lambda v: json.dumps(v, ensure_ascii=False,
                                                          sort_keys=True))
        return items
    if isinstance(value, float):
        return _canon_number(value)
    if isinstance(value, str):
        return _canon_path(value)
    return value


def canonical_payload(model: Dict[str, Any], subset: Optional[Sequence[str]] = None) -> Dict[str, Any]:
    """registry 子集规范形载荷：modules + protocols + mount_points + subscriptions。"""
    reg = _read_registry(_root(model["root"]))
    modules = [dict(m) for m in (reg.get("modules") or []) if isinstance(m, dict)]
    protocols = [dict(p) for p in (reg.get("protocols") or []) if isinstance(p, dict)]
    if subset is not None:
        wanted = set(subset)
        modules.sort(key=lambda m: str(m.get("id") or ""))
        modules = modules[: max(1, wanted.__len__())]
        protocols.sort(key=lambda p: str(p.get("id") or ""))
        protocols = protocols[: max(1, len(wanted) // 4 + 1)]
    return canonicalize({
        "schema": CANON_SCHEMA,
        "registry_schema_version": str(reg.get("registry_schema_version") or ""),
        "modules": modules,
        "protocols": protocols,
        "mount_points": reg.get("mount_points") or {},
        "subscriptions": reg.get("subscriptions") or {},
    })


def canonical_bytes(payload: Dict[str, Any]) -> bytes:
    body = json.dumps(payload, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False) + "\n"
    return (CANON_VERSION + "\n").encode("utf-8") + body.encode("utf-8")


def canonical_digest(payload: Dict[str, Any]) -> str:
    return hashlib.sha256(canonical_bytes(payload)).hexdigest()


# ---------------------------------------------------------------- CLI 内核
def run_check(root: Any = ".", core_only: bool = True, as_json: bool = False) -> int:
    """`nf spec check --core [--json]` → 0 无 FAIL / 1 有 FAIL / 2 不可判定。"""
    if not core_only:
        print("  ✗ 目前仅支持 `--core`：契约语义核心面向官方核心 + 包登记面（修复指引："
              "加 --core；扩展面待后续按同一模型接入）", file=sys.stderr)
        return 2
    try:
        model = load_model(root)
    except (OSError, ValueError) as exc:
        print("  ✗ 契约语义模型不可判定：%s（修复指引：运行 `nf doctor` 核对真源件；"
              "本命令不做「读不到 = 通过」的假绿）" % exc, file=sys.stderr)
        return 2
    report = check_model(model)
    if as_json:
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print("== nf spec check --core（契约语义：W1 层序 / W2 域隔离 / W3 门全性）==")
        print("  判定：%s（FAIL %d · WARN %d · 模块 %d · 包 %d · 管线 %d）"
              % (report["verdict"].upper(), report["stats"]["fail"],
                 report["stats"]["warn"], report["stats"]["modules"],
                 report["stats"]["packages"], report["stats"]["pipelines"]))
        for i in report["fails"]:
            print("  [FAIL] %s/%s %s：%s" % (i["rule"], i["code"], i["subject"], i["message"]))
            if i["fix"]:
                print("         修复指引：%s" % i["fix"])
        for i in report["warns"]:
            print("  [WARN] %s/%s %s：%s" % (i["rule"], i["code"], i["subject"], i["message"]))
        if not report["issues"]:
            print("  ✓ 三规则零 issue（当前模型可判定为良构）")
        print("  证据：W1 %s ｜ W2 %s ｜ W3 %s"
              % (EVIDENCE["W1"][0], EVIDENCE["W2"][0], EVIDENCE["W3"][0]))
    return 1 if report["fails"] else 0


def run_canonical(root: Any = ".", as_json: bool = False) -> int:
    """`nf spec canonical [--json]` → 规范形摘要（两次一致为幂等）。"""
    try:
        model = load_model(root)
        payload = canonical_payload(model)
        first, second = canonical_bytes(payload), canonical_bytes(canonicalize(payload))
        digest = hashlib.sha256(first).hexdigest()
    except (OSError, ValueError) as exc:
        print("  ✗ 规范形不可计算：%s（修复指引：核对 registry.json 可读）" % exc,
              file=sys.stderr)
        return 2
    doc = {"kind": "spec-canonical", "schema": CANON_SCHEMA, "canon_version": CANON_VERSION,
           "digest": digest, "idempotent": first == second,
           "bytes": len(first), "modules": len(payload.get("modules") or []),
           "protocols": len(payload.get("protocols") or [])}
    if as_json:
        print(json.dumps(doc, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print("== nf spec canonical（registry 子集规范形）==")
        print("  canon_version：%s" % CANON_VERSION)
        print("  digest：sha256:%s" % digest)
        print("  幂等：%s（两次规范化逐字节一致）" % ("是" if first == second else "否"))
        print("  范围：modules %d · protocols %d · bytes %d"
              % (doc["modules"], doc["protocols"], doc["bytes"]))
    return 0 if first == second else 1
