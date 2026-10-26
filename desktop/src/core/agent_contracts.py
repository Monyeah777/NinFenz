#!/usr/bin/env python3
# nf-io: inputs=desktop/src/core/registry.json,03_管线库/*.md,community/*/gate_profiles/*.json outputs=-
"""多 agent 协作契约（T10.3）：角色=模块、交接=事件、验收=门。

**这是什么**：把「多 agent 协作」从 prompt 工程落成**可机检契约**——每个角色（writer /
critic / fact_checker / editor）声明它消费哪些槽位、产出哪些产物、通过哪些事件交接、由哪道
既有门验收、失败怎么处置；角色链（域包维度）声明顺序与交接闭合。本模块**不新造能力**：
角色引用的模块/管线/gate profile 全部是仓库里既有的件，校验只做**静态符号存在性**断言
（不 import 角色模块——导入即执行，契约检查不执行角色）。

三条可判定性
------------
1. **闭合**：角色链相邻两跳必须由交接事件连接；每个发布事件都有订阅方（终态事件除外），
   每个订阅事件都有发布方；每个角色至少被一条域链使用（无孤立角色）。
2. **引用真实**：模块（`desktop/src/core/<m>.py` + 顶层符号）、registry 模块 id、管线
   （`03_管线库/<id>_*.md`）、gate profile（`community/<域包>/gate_profiles/<id>.json`）
   必须真实存在；域包声明的 `pipeline:` 必须与该域链声明的管线一致。
3. **失败策略明确**：`fail_closed` 或 `rewrite_with_limit`（并给退回上限），无策略即 FAIL。

与 runtime 的衔接点（**未来可直接跑**，本波不跑真实 LLM）
--------------------------------------------------------
角色链计划（`nf-agent-plan/1`）的 `steps[]` 与 `core/runtime.py` 的 `nf-runtime-trace/1`
step 形状同构：`step/layer/module/input_digest/output_digest`。把每个角色步的
`module` 换成角色引用的实现模块、`handoff` 事件落成 step 间传递的 artifact，注入一个实现
`runtime.ModelClient.respond(contract_digest, step_id)` 的 client 即可复用既有确定性
harness 与 record/replay——本模块只产出契约与计划，不执行模型。

用法：`python scripts/nf.py agent plan --domain techdoc [--json]` /
`python scripts/nf.py agent check [--json]`。
"""
from __future__ import annotations

import ast
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from core import json_doc

ROOT = Path(__file__).resolve().parents[3]

SCHEMA = "nf-agent-contracts/1"
PLAN_SCHEMA = "nf-agent-plan/1"
CHECK_SCHEMA = "nf-agent-check/1"

#: 角色封闭集（T10.3 四角色；新增角色须同时改本表与域链，check 会报孤立/未覆盖）。
ROLE_IDS = ("writer", "critic", "fact_checker", "editor")

#: 终态事件：发布后无下游订阅是**正常收口**，不算孤儿交接。
TERMINAL_EVENTS = ("final.approved", "rewrite.exhausted")

#: 外部输入（域链起点从这些槽位取），不需要发布方。
ENTRY_INPUTS = ("brief", "state")

#: 失败策略封闭集：fail_closed = 一步失败即停；rewrite_with_limit = 退回重写，有上限。
FAILURE_MODES = ("fail_closed", "rewrite_with_limit")

#: 域 → 域包目录 + gate profile + 声明管线（pipeline 必须与包 protocol.yaml 的 `pipeline:` 一致）。
DOMAINS: Dict[str, Dict[str, Any]] = {
    "techdoc": {
        "pack": "community/技术文档域包",
        "profiles": ("techdoc-strict",),
        "pipeline": "P06",
        "entry_inputs": ("brief", "state"),
        "chain": ("writer", "fact_checker", "critic", "editor"),
    },
    "regulatory": {
        "pack": "community/合规与监管域包",
        "profiles": ("regulatory-strict",),
        "pipeline": "P98",
        "entry_inputs": ("brief", "state"),
        "chain": ("writer", "critic", "fact_checker", "editor"),
    },
}

#: 角色契约（**全部引用既有件**；映射表见报告「角色→模块→门」）。
ROLES: Dict[str, Dict[str, Any]] = {
    "writer": {
        "role_id": "writer",
        "purpose": "把 brief/state 写成域包可验收的草稿（结构装配 M90 + 内容 IR）",
        "inputs": ("brief", "state"),
        "outputs": ("draft",),
        "handoff": {"publish": ("draft.ready",), "subscribe": ("brief", "state")},
        "modules": ("content_ir", "composer"),          # desktop/src/core/<m>.py 在场 + 符号
        "symbols": {"content_ir": "render", "composer": "build_assembly"},
        "registry_modules": ("M90",),                    # 结构装配（既有官方核心模块）
        "pipeline": "P01",
        "gate": {"kind": "module_function", "ref": "quality_gate.run_gate"},
        "failure_policy": {"mode": "rewrite_with_limit", "max_retries": 2},
    },
    "fact_checker": {
        "role_id": "fact_checker",
        "purpose": "核对草稿里的断言/数字是否有证据锚点（知识条目库 M20 + grounding）",
        "inputs": ("draft",),
        "outputs": ("checked_claims",),
        "handoff": {"publish": ("claims.verified",),
                    "subscribe": ("draft.ready", "critique.issued")},
        "modules": ("knowledge", "grounding", "numeric_grounding"),
        "symbols": {"knowledge": "scan", "grounding": "verify_anchors",
                    "numeric_grounding": "check"},
        "registry_modules": ("M20",),
        "pipeline": "P90",
        "gate": {"kind": "module_function", "ref": "numeric_grounding.check"},
        "failure_policy": {"mode": "rewrite_with_limit", "max_retries": 1},
    },
    "critic": {
        "role_id": "critic",
        "purpose": "按域包 gate profile 出逐条质检意见（M80 输出质检门）",
        "inputs": ("draft",),
        "outputs": ("critique",),
        "handoff": {"publish": ("critique.issued",), "subscribe": ("draft.ready", "claims.verified")},
        "modules": ("quality_gate", "gate_profile", "prose_lint"),
        "symbols": {"quality_gate": "run_gate", "gate_profile": "report", "prose_lint": "lint_text"},
        "registry_modules": ("M80",),
        "pipeline": "P01",
        "gate": {"kind": "profile", "by_domain": {"techdoc": "techdoc-strict",
                                                  "regulatory": "regulatory-strict"}},
        "failure_policy": {"mode": "rewrite_with_limit", "max_retries": 2},
    },
    "editor": {
        "role_id": "editor",
        "purpose": "按 critique 收敛终稿并过最终门（M24 规则组合 + gate profile 复检）",
        "inputs": ("critique",),
        "outputs": ("final",),
        "handoff": {"publish": ("final.approved",),
                    "subscribe": ("critique.issued", "claims.verified")},
        "modules": ("content_ir", "prose_lint", "gate_profile"),
        "symbols": {"content_ir": "check_file", "prose_lint": "lint_text",
                    "gate_profile": "report"},
        "registry_modules": ("M24",),
        "pipeline": "P90",
        "gate": {"kind": "module_function", "ref": "gate_profile.report"},
        "failure_policy": {"mode": "fail_closed", "max_retries": 0},
    },
}

#: 与 runtime 的衔接点（契约引用；check 断言这些符号在 runtime.py 里真实在场）。
RUNTIME_HOOK = {
    "module": "runtime",
    "entry": "execute",
    "client_interface": "ModelClient.respond",
    "trace_schema": "nf-runtime-trace/1",
    "fixture_schema": "nf-runtime-fixture/1",
}

_ROLE_KEYS = ("role_id", "purpose", "inputs", "outputs", "handoff", "modules", "symbols",
              "registry_modules", "pipeline", "gate", "failure_policy")


# ---------------------------------------------------------------- 静态能力解析（不 import 角色模块）

def _core_source(root: Path, module: str) -> Optional[str]:
    """读 `desktop/src/core/<module>.py` 源码；不存在返回 None（**不导入**）。"""
    if not re.match(r"^[a-z][a-z0-9_]*$", str(module or "")):
        return None
    p = root / "desktop" / "src" / "core" / ("%s.py" % module)
    if not p.is_file():
        return None
    try:
        return p.read_text(encoding="utf-8")
    except OSError:
        return None


def _source_symbols(source: str) -> set:
    """模块源码的顶层符号集合（函数/类/常量赋值）。"""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return set()
    out = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            out.add(node.name)
        elif isinstance(node, ast.Assign):
            for tgt in node.targets:
                if isinstance(tgt, ast.Name):
                    out.add(tgt.id)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            out.add(node.target.id)
    return out


def _all_modules() -> set:
    mods: set = set()
    for role in ROLES.values():
        mods.update(role.get("modules") or ())
    return mods


def _registry_module_ids(root: Path) -> set:
    path = root / "desktop" / "src" / "core" / "registry.json"
    try:
        doc = json_doc.load(path, dict, what="registry.json")
    except (OSError, ValueError):
        return set()
    return {str(m.get("id") or "") for m in (doc.get("modules") or [])
            if isinstance(m, dict) and str(m.get("id") or "")}


def _pipeline_ids(root: Path) -> set:
    """`03_管线库/Pxx_*.md` 文件名 → 管线 id 集合（不解析 YAML，只认目录真源）。"""
    d = root / "03_管线库"
    if not d.is_dir():
        return set()
    return {str(m.group(1)) for p in d.glob("P*.md")
            for m in [re.match(r"^([A-Z]\d+)_", p.name)] if m}


def _gate_profile(root: Path, domain: str, profile: str) -> Optional[dict]:
    """读域包 gate profile（json_doc；不存在/坏件返回 None，由调用方报 issue）。"""
    pack = str(DOMAINS.get(domain, {}).get("pack") or "")
    if not pack:
        return None
    p = root / pack / "gate_profiles" / ("%s.json" % profile)
    if not p.is_file():
        return None
    try:
        doc = json_doc.load(p, dict, what="%s/gate_profiles/%s.json" % (pack, profile))
    except (OSError, ValueError):
        return None
    return doc


def _domain_pipeline(root: Path, domain: str) -> str:
    """域包 protocol.yaml 里声明的 `pipeline:`（文本扫描；缺件返回空串）。"""
    pack = str(DOMAINS.get(domain, {}).get("pack") or "")
    p = root / pack / "protocol.yaml"
    if not p.is_file():
        return ""
    try:
        text = p.read_text(encoding="utf-8")
    except OSError:
        return ""
    m = re.search(r"^\s*pipeline:\s*([A-Z]\d+)\b", text, re.M)
    return m.group(1) if m else ""


def _runtime_present(root: Path) -> bool:
    src = _core_source(root, str(RUNTIME_HOOK["module"]))
    if not src:
        return False
    syms = _source_symbols(src)
    return ("class ModelClient" in src and str(RUNTIME_HOOK["entry"]) in syms)


# ---------------------------------------------------------------- 闭合校验

def _bad(issues: List[str], fmt: str, *args: Any) -> None:
    issues.append(fmt % args)


def _check_handoff(role: Dict[str, Any], issues: List[str]) -> Tuple[set, set]:
    handoff = role.get("handoff")
    name = str(role.get("role_id") or "?")
    if not isinstance(handoff, dict):
        _bad(issues, "角色 %s 缺 handoff（修复指引：写 publish/subscribe 事件表）", name)
        return set(), set()
    pub = handoff.get("publish") or []
    sub = handoff.get("subscribe") or []
    for key, vals in (("publish", pub), ("subscribe", sub)):
        if not isinstance(vals, (list, tuple)) or not vals:
            _bad(issues, "角色 %s 的 handoff.%s 为空（修复指引：至少一个事件）", name, key)
    if not pub:
        _bad(issues, "角色 %s 无产出交接事件（修复指引：publish 至少一个事件）", name)
    return {str(x) for x in pub if str(x).strip()}, {str(x) for x in sub if str(x).strip()}


def _check_failure(role: Dict[str, Any], issues: List[str]) -> None:
    name = str(role.get("role_id") or "?")
    fp = role.get("failure_policy")
    if not isinstance(fp, dict):
        _bad(issues, "角色 %s 缺失败策略（修复指引：fail_closed 或 rewrite_with_limit）", name)
        return
    mode = str(fp.get("mode") or "")
    retries = fp.get("max_retries", -1)
    if mode not in FAILURE_MODES:
        _bad(issues, "角色 %s 失败策略 mode=%r 不在封闭集 %s（修复指引：改用合法策略）",
             name, mode, FAILURE_MODES)
    if not isinstance(retries, int) or isinstance(retries, bool) or retries < 0:
        _bad(issues, "角色 %s 失败策略 max_retries 须为 ≥0 整数（修复指引：填退回上限）", name)
    elif mode == "fail_closed" and retries != 0:
        _bad(issues, "角色 %s fail_closed 却给 max_retries=%d（修复指引：fail_closed 即 0）",
             name, retries)
    elif mode == "rewrite_with_limit" and retries < 1:
        _bad(issues, "角色 %s rewrite_with_limit 须给 ≥1 的退回上限（修复指引：填 max_retries）",
             name)


def _check_gate(role: Dict[str, Any], root: Path, domain: str,
                issues: List[str]) -> Optional[str]:
    """校验角色门可达 → 返回该域下解析后的门标识（profile id 或 module.func）。"""
    name = str(role.get("role_id") or "?")
    gate = role.get("gate")
    if not isinstance(gate, dict):
        _bad(issues, "角色 %s 缺 gate（修复指引：声明 gate.kind/ref 或 profile.by_domain）", name)
        return None
    kind = str(gate.get("kind") or "")
    if kind == "module_function":
        ref = str(gate.get("ref") or "")
        mod, _, fn = ref.partition(".")
        src = _core_source(root, mod)
        if not src:
            _bad(issues, "角色 %s 的门引用不存在模块：%s（修复指引：改成在场 core 模块）",
                 name, mod)
            return None
        if fn not in _source_symbols(src):
            _bad(issues, "角色 %s 的门引用不存在符号：%s（修复指引：核对函数名）", name, ref)
            return None
        return ref
    if kind == "profile":
        by_domain = gate.get("by_domain") or {}
        profile = str(by_domain.get(domain) or "")
        if not profile:
            _bad(issues, "角色 %s 的 profile 门缺 domain=%s 的映射（修复指引：补 by_domain）",
                 name, domain)
            return None
        doc = _gate_profile(root, domain, profile)
        if doc is None:
            _bad(issues, "角色 %s 引用的 gate profile 不存在：%s/%s（修复指引：核对域包）",
                 name, DOMAINS.get(domain, {}).get("pack", "?"), profile)
            return None
        if str(doc.get("profile_id") or "") != profile:
            _bad(issues, "gate profile %s 的 profile_id 不一致：%r（修复指引：核对文件）",
                 profile, doc.get("profile_id"))
            return None
        return profile
    _bad(issues, "角色 %s 的 gate.kind=%r 非法（修复指引：module_function 或 profile）",
         name, kind)
    return None


def _check_role(role: Dict[str, Any], root: Path, domain: str,
                issues: List[str]) -> Tuple[set, set, Optional[str]]:
    name = str(role.get("role_id") or "?")
    missing = [k for k in _ROLE_KEYS if k not in role]
    if missing:
        _bad(issues, "角色 %s 缺字段 %s（修复指引：按契约模板补齐）", name, ",".join(missing))
    if name not in ROLE_IDS:
        _bad(issues, "未知角色 id：%r（修复指引：角色封闭集 %s）", name, ROLE_IDS)
    for key in ("inputs", "outputs"):
        vals = role.get(key)
        if not isinstance(vals, (list, tuple)) or not vals:
            _bad(issues, "角色 %s 的 %s 为空（修复指引：声明槽位/产物）", name, key)
    for mod in role.get("modules") or ():
        src = _core_source(root, str(mod))
        if not src:
            _bad(issues, "角色 %s 引用不存在模块：%s（修复指引：desktop/src/core 下须在场）",
                 name, mod)
    pipe = str(role.get("pipeline") or "")
    if not pipe or pipe not in _pipeline_ids(root):
        _bad(issues, "角色 %s 引用不存在管线：%r（修复指引：03_管线库 下须有该管线 md）",
             name, pipe)
    known_reg = _registry_module_ids(root)
    for rid in role.get("registry_modules") or ():
        if str(rid) not in known_reg:
            _bad(issues, "角色 %s 引用不存在 registry 模块：%s（修复指引：核对 registry.json）",
                 name, rid)
    for mod, sym in (role.get("symbols") or {}).items():
        src = _core_source(root, str(mod))
        if src and str(sym) not in _source_symbols(src):
            _bad(issues, "角色 %s 引用 %s.%s 不存在（修复指引：核对符号名）", name, mod, sym)
    pub, sub = _check_handoff(role, issues)
    _check_failure(role, issues)
    resolved = _check_gate(role, root, domain, issues)
    return pub, sub, resolved


def _check_domain(domain: str, spec: Dict[str, Any], root: Path, roles: Dict[str, Dict[str, Any]],
                  issues: List[str]) -> Dict[str, Any]:
    chain = tuple(spec.get("chain") or ())
    if len(chain) < 2:
        _bad(issues, "域 %s 角色链过短（修复指引：至少两跳才有交接）", domain)
        return {"chain": list(chain), "edges": [], "gates": {}}
    for rid in chain:
        if rid not in roles:
            _bad(issues, "域 %s 角色链引用未知角色：%s（修复指引：核对 ROLE_IDS）", domain, rid)
    if len(set(chain)) != len(chain):
        _bad(issues, "域 %s 角色链重复角色（修复指引：链上角色唯一）", domain)
    pack = str(spec.get("pack") or "")
    if not pack or not (root / pack).is_dir():
        _bad(issues, "域 %s 的域包不在场：%s（修复指引：核对目录）", domain, pack)
    declared = str(spec.get("pipeline") or "")
    core_ids = _pipeline_ids(root)
    pack_pipeline = _domain_pipeline(root, domain)
    if not declared:
        _bad(issues, "域 %s 缺声明管线（修复指引：填管线 id）", domain)
    elif declared not in core_ids and declared != pack_pipeline:
        _bad(issues, "域 %s 引用不存在管线：%s（修复指引：须命中 03_管线库 既有管线，"
                     "或与域包 protocol.yaml 的 pipeline 一致）", domain, declared)
    if not pack_pipeline:
        _bad(issues, "域 %s 的域包未声明 pipeline（修复指引：核对 %s/protocol.yaml）",
             domain, pack or "?")
    for prof in spec.get("profiles") or ():
        if _gate_profile(root, domain, str(prof)) is None:
            _bad(issues, "域 %s 缺 gate profile 文件：%s（修复指引：补 gate_profiles/*.json）",
                 domain, prof)
    entry = {str(x) for x in spec.get("entry_inputs") or ()}
    if not entry:
        _bad(issues, "域 %s 缺 entry_inputs（修复指引：声明入口槽位）", domain)
    bad_entry = sorted(entry - set(ENTRY_INPUTS))
    if bad_entry:
        _bad(issues, "域 %s 的 entry_inputs 非法：%s（修复指引：入口只许 %s）",
             domain, bad_entry, ENTRY_INPUTS)
    # 相邻交接闭合：publish(i) ∩ subscribe(i+1) 非空
    edges = []
    for i in range(len(chain) - 1):
        a, b = chain[i], chain[i + 1]
        if a not in roles or b not in roles:
            continue
        pub = {str(x) for x in (roles[a].get("handoff") or {}).get("publish") or ()}
        sub = {str(x) for x in (roles[b].get("handoff") or {}).get("subscribe") or ()}
        shared = sorted(pub & sub)
        if not shared:
            _bad(issues, "域 %s 交接断裂：%s → %s 无共同事件（%s 发布 %s；%s 订阅 %s）"
                         "（修复指引：让下游订阅上游发布事件）",
                 domain, a, b, a, sorted(pub), b, sorted(sub))
            edges.append({"from": a, "to": b, "event": "", "ok": False})
        else:
            edges.append({"from": a, "to": b, "event": shared[0], "ok": True})
    first = roles.get(chain[0]) if chain else None
    if first:
        sub0 = {str(x) for x in (first.get("handoff") or {}).get("subscribe") or ()}
        if not (sub0 & entry):
            _bad(issues, "域 %s 首角色 %s 未订阅入口槽位（订阅 %s；入口 %s）"
                         "（修复指引：首角色 subscribe 须含 entry_inputs）",
                 domain, chain[0], sorted(sub0), sorted(entry))
    last = roles.get(chain[-1]) if chain else None
    if last:
        pub_last = {str(x) for x in (last.get("handoff") or {}).get("publish") or ()}
        if not (pub_last & set(TERMINAL_EVENTS)):
            _bad(issues, "域 %s 末角色 %s 未发布终态事件（发布 %s；终态 %s）"
                         "（修复指引：末角色 publish 含 final.approved）",
                 domain, chain[-1], sorted(pub_last), TERMINAL_EVENTS)
    for rid in chain:
        role = roles.get(rid)
        if role:
            _check_gate(role, root, domain, issues)      # 每域解析后的门必须真实可达
    return {"chain": list(chain), "edges": edges,
            "gates": {rid: _role_gate(roles.get(rid), domain) for rid in chain}}


def _role_gate(role: Optional[Dict[str, Any]], domain: str) -> str:
    gate = (role or {}).get("gate") or {}
    if str(gate.get("kind")) == "profile":
        return str((gate.get("by_domain") or {}).get(domain) or "")
    return str(gate.get("ref") or "")


def validate(roles: Optional[Dict[str, Dict[str, Any]]] = None,
             domains: Optional[Dict[str, Dict[str, Any]]] = None,
             root: Optional[Any] = None) -> Tuple[List[str], Dict[str, Any]]:
    """→ (issues, stats)。roles/domains 可注入（负例用；缺省 = 本模块契约）。"""
    r = Path(root).resolve() if root is not None else ROOT
    roles = roles if roles is not None else ROLES
    domains = domains if domains is not None else DOMAINS
    issues: List[str] = []
    stats: Dict[str, Any] = {"schema": SCHEMA, "roles": 0, "domains": 0,
                             "modules": 0, "events": 0, "profiles": 0}
    if set(domains) != set(DOMAINS):
        extra = sorted(set(domains) - set(DOMAINS))
        if extra:
            _bad(issues, "未知域：%s（修复指引：域封闭集 techdoc/regulatory）", extra)
    if set(roles) != set(ROLE_IDS):
        _bad(issues, "角色集合须恰为 %s（实为 %s）（修复指引：补齐/删除多余角色）",
             ROLE_IDS, sorted(roles))
    used: set = set()
    pubs: set = set()
    subs: set = set()
    resolved_gates: Dict[str, str] = {}
    for domain, spec in domains.items():
        dom = _check_domain(domain, spec, r, roles, issues)
        used.update(dom.get("chain") or [])
        for rid, gate in (dom.get("gates") or {}).items():
            if gate:
                resolved_gates[rid] = gate
        for rid in dom.get("chain") or ():
            role = roles.get(rid)
            if role:
                pubs.update((role.get("handoff") or {}).get("publish") or ())
                subs.update((role.get("handoff") or {}).get("subscribe") or ())
    for rid, role in roles.items():
        _check_role(role, r, "techdoc", issues)          # 角色自洽用默认域检查 profile 门
    for ev in sorted(pubs - subs - set(TERMINAL_EVENTS)):
        _bad(issues, "孤儿交接事件：%s 有发布方无订阅方（修复指引：补下游 subscribe，"
                     "或登记为终态事件）", ev)
    for ev in sorted(subs - pubs - set(ENTRY_INPUTS)):
        _bad(issues, "交接事件无发布方：%s（修复指引：补上游 publish，或改为入口槽位）", ev)
    for rid in sorted(set(roles) - used):
        _bad(issues, "孤立角色：%s 未被任何域链使用（修复指引：接进域链或删除）", rid)
    if not _runtime_present(r):
        _bad(issues, "runtime 衔接点不在场：core/runtime.py 缺 ModelClient/execute"
                     "（修复指引：本波依赖既有 runtime，勿新造运行时）")
    stats.update(roles=len(roles), domains=len(domains),
                 modules=len(_all_modules()), events=len(pubs | subs),
                 profiles=len(resolved_gates),
                 registry_modules=len(_registry_module_ids(r)),
                 pipelines=len(_pipeline_ids(r)), ok=not issues)
    return issues, stats


# ---------------------------------------------------------------- 计划（供 runtime 衔接）

def plan(root: Optional[Any] = None, domain: str = "techdoc") -> Dict[str, Any]:
    """→ `nf-agent-plan/1`：角色链 + 每步门 + 交接边（纯函数，不执行角色）。"""
    if domain not in DOMAINS:
        raise ValueError("未知域 %r（修复指引：--domain 取 %s）" % (domain, "/".join(DOMAINS)))
    spec = DOMAINS[domain]
    chain = list(spec.get("chain") or ())
    steps = []
    for i, rid in enumerate(chain):
        role = ROLES.get(rid) or {}
        steps.append({
            "step": i + 1,
            "layer": rid,
            "module": list(role.get("modules") or ()),
            "registry_module": list(role.get("registry_modules") or ()),
            "gate": _role_gate(role, domain),
            "inputs": list(role.get("inputs") or ()),
            "outputs": list(role.get("outputs") or ()),
            "handoff": dict(role.get("handoff") or {}),
            "failure_policy": dict(role.get("failure_policy") or {}),
        })
    edges = []
    for i in range(len(chain) - 1):
        a, b = chain[i], chain[i + 1]
        pub = set((ROLES.get(a) or {}).get("handoff", {}).get("publish") or ())
        sub = set((ROLES.get(b) or {}).get("handoff", {}).get("subscribe") or ())
        shared = sorted(pub & sub)
        edges.append({"from": a, "to": b, "event": shared[0] if shared else ""})
    doc = {
        "kind": "agent-plan",
        "schema": PLAN_SCHEMA,
        "domain": domain,
        "pack": spec.get("pack") or "",
        "pipeline": spec.get("pipeline") or "",
        "chain": steps,
        "edges": edges,
        "runtime_hook": dict(RUNTIME_HOOK),
        "gates": {rid: _role_gate(ROLES.get(rid), domain) for rid in chain},
    }
    return doc


def main(argv: Optional[Sequence[str]] = None) -> int:
    """独立入口（`python desktop/src/core/agent_contracts.py plan --domain ...`）。"""
    import sys

    args = list(argv if argv is not None else sys.argv[1:])
    if not args or args[0] not in ("plan", "check"):
        print("用法：agent_contracts.py plan --domain techdoc|regulatory [--json] "
              "| agent_contracts.py check [--json]", file=sys.stderr)
        return 2
    as_json = "--json" in args
    if args[0] == "plan":
        domain = "techdoc"
        if "--domain" in args:
            try:
                domain = args[args.index("--domain") + 1]
            except IndexError:
                print("--domain 缺值（修复指引：给 techdoc|regulatory）", file=sys.stderr)
                return 2
        try:
            doc = plan(domain=domain)
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 2
        print(json.dumps(doc, ensure_ascii=False, indent=2) if as_json else str(doc))
        return 0
    issues, stats = validate()
    if as_json:
        print(json.dumps({"kind": "agent-check", "schema": CHECK_SCHEMA,
                          "ok": not issues, "issues": issues, "stats": stats},
                         ensure_ascii=False, indent=2))
    else:
        print("== agent 契约闭合检查 ==")
        for i in issues:
            print("  [FAIL] %s" % i)
        print("  角色 %d · 域 %d · 模块 %d · 事件 %d · 门 %d → %s"
              % (stats["roles"], stats["domains"], stats["modules"], stats["events"],
                 stats["profiles"], "PASS" if not issues else "FAIL"))
    return 0 if not issues else 1


if __name__ == "__main__":
    raise SystemExit(main())
