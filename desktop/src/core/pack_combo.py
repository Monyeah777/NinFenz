"""域包自由组合引擎（任意 n 元 × 任意组件）。

目标：100 个域包（+ 既有社区包）**任意子集**可自由组合；包内组件（协议 / 管线 / 模块 /
资产）也可自由取用；组合广度 = 2^N（不预先枚举）；深度质量 = 每条组合必须过**五条可机检
不变量**；产出 = **可复算证书**（T4：门禁重算并与在盘证书逐字段比对）。

五条不变量（任一不成立即非法，不许静默降级）：
1. **模块唯一可定位**：选中模块 id 唯一，且能定位到机读契约（缺契约即报）；
2. **依赖闭合**：模块 `inputs` 只能指向「组合内模块」∪「官方核心 13 件」，否则报 dangling；
3. **事件闭合**：任一 `subscribe` 必须在本组合内有发布方（本仓域包事件按域码命名空间，
   包内自闭合；跨包订阅须显式事件桥，否则报 unbridged）；
4. **层位堆叠确定**：同层多包默认挂载按（声明序 → 模块 id）确定性堆叠，产出 `layer_stacks`；
5. **资产可寻址**：跨包资产以 `asset_readonly` 借阅，键须能在源包 provenance 台账找到。

广度证明（`breadth`）：全部两两组合（C(N,2)）+ 定种子抽样的三元 / 四元组合跑同一套不变量，
断言「任意组合合法」——广度不靠枚举，靠**不变量在全集上成立**。
"""

# 读点：证书/协议件读取在 _pack_combo._base 里仍走 json_doc.loads（N11）。

from __future__ import annotations

# ruff: noqa: F401 — 门面按原模块面重新导出（re-export 是职责，不是未使用）
import sys as _sys
import types as _types

# 依赖面：逐字保留原模块 import 面（含函数内 core import 的边）——
# 耦合图/纯度面按模块级 import 计算，勿删（见 re-export 说明）。
from core import atomic_write, json_doc, official_core
from core import conformance_scan as csc
# 导入闭包指纹：由调用方算（持久层不再反向依赖解析层，见 2026-09-29 拆环）
from core import import_graph as _ig
from core import conformance_scan as _csc
from core import domain_pack as dpk
from core import json_schema as _js  # 只取叶子校验器：不再 import output_forms（断双向对）
from core import disk_cache

import copy
import itertools
import random
import re
from pathlib import Path
from core import atomic_write
from core import conformance_scan as csc
from core import import_graph as _ig

from ._pack_combo._const import (
    CERT_REL,
    CERT_SCHEMA,
    CORE13,
    CORE_CONTRACT_PATTERNS,
    INPUT_PATTERNS,
    MODULE_CONTRACT_PATTERNS,
    PROFILE_PATTERNS,
    SCAN_INPUTS,
    _CACHE,
    _CACHE_MAX,
    _COMBO_CACHE,
    _COMBO_CACHE_MAX,
    _CONTENT_CACHE,
    _CONTENT_CACHE_MAX,
    _CONTRACTS_CACHE,
    _CONTRACTS_CACHE_MAX,
)
from ._pack_combo._base import (
    _asset_index,
    _cache_key,
    _content_store,
    _core_contracts,
    _core_ids,
    _digest,
    _face_paths,
    _inputs_fingerprint,
    _module_contracts,
    _pack_assets,
    _pack_dirs,
    _parse_protocol,
    _read_json,
    _root_cache,
    cache_clear,
    indexes,
    profiles,
)
from ._pack_combo._cert import (
    _CERT_CACHE,
    _CERT_CACHE_MAX,
    _COMBO_DECL_KEYS,
    _canon,
    _certificate_lines,
    _combo_witness,
    _verdict_cached,
    certify,
    core_contracts_fingerprint,
    declared,
    verify_certificate,
)
from ._pack_combo._readme import (
    combo_assets_readme,
    combo_pipeline,
    combo_readme,
    combo_register,
)
from ._pack_combo._materialize import (
    _combo_borrow,
    _combo_card,
    _combo_index,
    _flatten_sources,
    combo_outputs,
    prof_get_module,
)
from ._pack_combo._base import (
    _asset_index,
    _cache_key,
    _content_store,
    _core_ids,
    _digest,
    _inputs_fingerprint,
    _module_contracts,
    _read_json,
    _root_cache,
    indexes,
    profiles,
)
from ._pack_combo._cert import (
    _certificate_lines,
    _combo_witness,
    _verdict_cached,
    declared,
)
from ._pack_combo._const import (
    CORE13,
    SCAN_INPUTS,
    _CACHE,
    _CONTENT_CACHE,
)
from ._pack_combo._materialize import (
    _flatten_sources,
    combo_outputs,
    prof_get_module,
)
from ._pack_combo._readme import (
    combo_assets_readme,
    combo_pipeline,
    combo_readme,
)



def combine(root: str = ".", packs: Sequence[str] = (), extra_modules: Sequence[str] = (),
            extra_assets: Sequence[str] = (), _prof: Any = None,
            _contracts: Any = None) -> Dict[str, Any]:
    """组合一个（纯读、不落盘）：返回组合证书 + 五条不变量判定。"""
    prof = _prof if _prof is not None else profiles(root)
    contracts = _contracts if _contracts is not None else _module_contracts(root)
    unknown = [p for p in packs if p not in prof]
    chosen = [prof[p] for p in packs if p in prof]
    mods: Dict[str, Dict[str, Any]] = {}
    for pr in chosen:
        for rec in pr["module_recs"]:
            mods[rec["id"]] = rec
    for mid in extra_modules:                 # 组件级自由：直接点模块名（可跨包）
        rec = contracts.get(str(mid)) or contracts.get(str(mid).split(":")[-1])
        if rec:
            mods[rec["id"]] = rec
    # references 自动借入（跨包引用白名单语义）：组合包借源包模块 → 借入本组合（不改号、不复制）
    borrowed: List[Dict[str, str]] = []
    unresolved_refs: List[Dict[str, str]] = []
    by_id, pub_index, core_pub = indexes(root)

    def _add(rec: Dict[str, Any], why: str, by: str) -> bool:
        if rec["id"] in mods:
            return False
        mods[rec["id"]] = rec
        borrowed.append({"module": rec["id"], "from": str(rec.get("pack")),
                         "by": by or "<组件级>", "mode": "closure_pull", "why": why})
        return True

    for pr in chosen:
        for ref in pr.get("references") or []:
            src, mid = ref.get("source_package", ""), ref.get("module_id", "")
            rec = contracts.get(mid) or contracts.get(str(mid).split(":")[-1])
            if rec and str(rec.get("pack")) == src:
                if rec["id"] not in mods:
                    mods[rec["id"]] = rec
                    borrowed.append({"module": rec["id"], "from": src,
                                     "by": pr["package"], "mode": "module_borrow"})
            elif rec:
                if rec["id"] not in mods:
                    mods[rec["id"]] = rec
                    borrowed.append({"module": rec["id"], "from": str(rec.get("pack")),
                                     "by": pr["package"], "mode": "module_borrow"})
            else:
                unresolved_refs.append({"by": pr["package"], "source_package": src,
                                        "module_id": mid})
    # ---- 不动点闭包：依赖 inputs ∪ 事件发布方（递归），直到不再新增 ----
    core = _core_ids()
    for _round in range(12):
        grew = False
        for m, r in list(mods.items()):
            for dep in r.get("inputs", []):
                if dep in core or dep in mods or dep.split(":")[-1] in core:
                    continue
                rec = by_id.get(dep) or by_id.get(str(dep).split(":")[-1])
                if rec and _add(rec, "依赖 %s 的 inputs 需要 %s" % (m, dep), m):
                    grew = True
        published_now = ({e for x in mods.values() for e in x.get("publish", [])} | core_pub)
        for m, r in list(mods.items()):
            for ev in r.get("subscribe", []):
                if ev in published_now:
                    continue
                recs = pub_index.get(ev) or []
                if not recs:
                    continue                      # 无人发布 → 由 unpublished 面报告
                for rec in recs:
                    if _add(rec, "事件 %s 需要发布方（%s 订阅）" % (ev, m), m):
                        grew = True
        if not grew:
            break
    missing_contracts = sorted(m for m, r in mods.items() if not r.get("path"))
    core = _core_ids()
    dangling = []
    for m, r in sorted(mods.items()):
        for dep in r.get("inputs", []):
            if dep in core or dep in mods or dep.split(":")[-1] in core:
                continue
            dangling.append({"module": m, "needs": dep})
    published = {e for r in mods.values() for e in r.get("publish", [])}
    published |= core_pub
    unbridged = sorted({e for r in mods.values() for e in r.get("subscribe", [])
                        if e not in published})
    unpublished = sorted({e for r in mods.values() for e in r.get("subscribe", [])
                          if e not in published and not (pub_index.get(e) or [])})
    # 规范序（2026-09-23 修）：层栈顺序必须与证书里 **packs 的规范序**一致，
    # 否则调用者给序不同 → 复算层栈不同 → T4 复算假失败。故一律按排序后的包名定序。
    canon = sorted(set(packs))
    order = {p: i for i, p in enumerate(canon)}
    stacks: Dict[str, List[str]] = {}
    for pr in chosen:
        for lay, ms in pr["layers"].items():
            stacks.setdefault(lay, [])
            for m in ms:
                if m not in stacks[lay]:
                    stacks[lay].append(m)
    for m, r in sorted(mods.items()):
        lay = str(r.get("layer") or "")
        if lay and m not in stacks.get(lay, []):
            stacks.setdefault(lay, []).append(m)
    stacks = {k: sorted(set(v), key=lambda x: (order.get(str((mods.get(x) or {}).get("pack")),
                                                        99), x))
              for k, v in sorted(stacks.items())}
    # 对外形态：**列表**（[{layer, modules}]）而非「层名做键的字典」——JSON Schema 的
    # patternProperties 需要正则键，而仓库编码卫生按标识面判键（实测 2026-09-23 冲突）；
    # 列表形态两边都干净，且层序天然显式。
    stack_list = [{"layer": k, "modules": v} for k, v in sorted(stacks.items())]
    asset_index = _asset_index(root)
    borrow, unresolved = [], []
    for pr in chosen:
        for a in pr["assets"]:
            if a["module"] and a["module"] not in mods:
                borrow.append({"key": a["key"], "from": pr["package"],
                               "for_module": a["module"], "mode": "asset_readonly"})
    for spec in extra_assets:
        pkg, _, key = str(spec).partition(":")
        if (pkg, key) in asset_index:
            borrow.append({"key": key, "from": pkg, "for_module": "",
                           "mode": "asset_readonly"})
        else:
            unresolved.append(str(spec))
    cert: Dict[str, Any] = {
        "schema": "nf-combo/1",
        "packs": canon,
        "unknown_packs": sorted(unknown),
        "extra_modules": sorted(set(extra_modules)),
        "modules": sorted(mods),
        "module_count": len(mods),
        "layer_stacks": stack_list,
        "dependency_closure": {
            "core": sorted(_core_ids()),
            "explicit": sorted({d for r in mods.values() for d in r.get("inputs", [])
                                if d in mods}),
            "dangling": dangling},
        "event_closure": {"published": sorted(published), "unbridged": unbridged},
        "events_unpublished": unpublished,
        "assets_borrowed": sorted(borrow, key=lambda x: (x["from"], x["key"])),
        "modules_borrowed": sorted(borrowed, key=lambda x: (x["by"], x["module"])),
        "references_unresolved": sorted(unresolved_refs, key=lambda x: (x["by"], x["module_id"])),
        "assets_unresolved": sorted(unresolved),
        "module_missing_contract": missing_contracts,
    }
    cert["legal"] = not (unknown or dangling or unbridged or missing_contracts or unresolved
                         or unresolved_refs)
    cert["digest"] = _digest(cert)
    return cert


def breadth(root: str = ".", triple_sample: int = 400, quad_sample: int = 200,
            quint_sample: int = 120, sext_sample: int = 60,
            seed: int = 20260923, _witness: Optional[str] = None) -> Dict[str, Any]:
    """广度证明：全部两两 + 定种子抽样三元 / 四元 / 五元 / 六元，跑同一套不变量。

    参与面 = `community/` 下全部已登记协议包（域包 + 组合包 + 既有社区包）——
    组合包带 `references`（借阅源包模块），本轮起一并进入广度抽样，验证
    「组合包本身也能当组合成员」（摊平后不变量仍成立）。

    结果按**输入内容指纹 + 抽样参数**缓存（`_CONTENT_CACHE`）：广度证明是诸输入的纯函数，
    输入没变就不必重跑 6910 次组合（实测 ~0.92 s）；输入一变指纹就变，无陈旧风险。
    """
    fp = _inputs_fingerprint(root)          # 只算一遍：进程内键与落盘键共用（过去算两遍，白花 57 ms）
    content_key = ("breadth", fp, triple_sample, quad_sample,
                   quint_sample, sext_sample, seed)
    hit = _CONTENT_CACHE.get(content_key)
    dkey = None
    if hit is None:                        # 进程内没命中 → 再看持久层（广度证明 ~0.9 s 一笔）
        from core import disk_cache
        dkey = disk_cache.key("pack-breadth", str(fp),
                              str(triple_sample), str(quad_sample), str(quint_sample),
                              str(sext_sample), str(seed), root=root,
                              code_scope=_ig.code_scope_fingerprint(root, ("core.pack_combo",)))
        hit = disk_cache.load("pack-breadth", dkey,
                             validate=lambda v: isinstance(v, dict) and bool(v))
        if hit is not None:
            _content_store(content_key, hit)
    if hit is not None:
        return copy.deepcopy(hit)
    key = _cache_key(root)
    prof = profiles(root)
    contracts = _module_contracts(root)
    # 逐组合判决缓存的全局见证（本轮算一遍；`scan()` 已算过就直接复用）
    witness = _witness or _combo_witness(root, prof, contracts)
    cached = _root_cache(key)
    cached.update({"prof": prof, "contracts": contracts})
    _CACHE[key] = cached
    names = sorted(prof)
    stats: Dict[str, Any] = {"packs": len(names), "pairs": 0, "pairs_legal": 0,
                             "triples": 0, "triples_legal": 0, "quads": 0, "quads_legal": 0,
                             "quints": 0, "quints_legal": 0,
                             "sexts": 0, "sexts_legal": 0,
                             "failures": []}
    for a, b in itertools.combinations(names, 2):
        legal, dangling, unbridged = _verdict_cached(root, (a, b), prof, contracts, witness)
        stats["pairs"] += 1
        stats["pairs_legal"] += 1 if legal else 0
        if not legal and len(stats["failures"]) < 10:
            stats["failures"].append({"combo": [a, b], "dangling": dangling,
                                      "unbridged": unbridged})
    rnd = random.Random(seed)
    triples: Set[Tuple[str, ...]] = set()
    if len(names) >= 3:
        while len(triples) < min(triple_sample, 5000):
            triples.add(tuple(sorted(rnd.sample(names, 3))))
    for t in sorted(triples):
        legal, _dg, _ub = _verdict_cached(root, t, prof, contracts, witness)
        stats["triples"] += 1
        stats["triples_legal"] += 1 if legal else 0
    quads: Set[Tuple[str, ...]] = set()
    if len(names) >= 4:
        while len(quads) < min(quad_sample, 5000):
            quads.add(tuple(sorted(rnd.sample(names, 4))))
    for q in sorted(quads):
        legal, _dg, _ub = _verdict_cached(root, q, prof, contracts, witness)
        stats["quads"] += 1
        stats["quads_legal"] += 1 if legal else 0
    for size, tag in ((5, "quints"), (6, "sexts")):
        want = min(quint_sample if size == 5 else sext_sample, 5000)
        picks: Set[Tuple[str, ...]] = set()
        if len(names) >= size:
            while len(picks) < want:
                picks.add(tuple(sorted(rnd.sample(names, size))))
        for p in sorted(picks):
            legal, dangling, unbridged = _verdict_cached(root, p, prof, contracts, witness)
            stats[tag] += 1
            stats[tag + "_legal"] += 1 if legal else 0
            if not legal and len(stats["failures"]) < 10:
                stats["failures"].append({"combo": list(p), "dangling": dangling,
                                          "unbridged": unbridged})
    stats["all_legal"] = bool(
        stats["pairs"] == stats["pairs_legal"]
        and stats["triples"] == stats["triples_legal"]
        and stats["quads"] == stats["quads_legal"]
        and stats["quints"] == stats["quints_legal"]
        and stats["sexts"] == stats["sexts_legal"])
    _content_store(content_key, stats)
    if dkey is not None:
        disk_cache.store("pack-breadth", dkey, stats)
    return stats


def materialize(root: str = ".", packs: Sequence[str] = (), combo_id: str = "",
                category: str = "", write: bool = False) -> Dict[str, Any]:
    """把一次组合落成**可装载的组合包**（派生协议 + 派生管线 + 借阅索引 + 机验产出面）。

    设计（守既有关禁）：
    - 组合包**不新增模块**（module_id_range/modules 均空）；全部模块经 `references` 只读借阅
      → check15 ①②④⑤ 可过，且避免多层组合（组合包自身的引用被**摊平**成源包直引）；
    - 层位堆叠写进 `available`（**default 留空**）→ 规避 check15 ③「同层 default 冲突」；
    - 派生管线沿用 P00 九层骨架，`allowed_modules` = 官方核心 ∪ 借阅模块；
    - 产出面含 **T4 证书**（由 pack_combo 重算）与图表/图结构，全部 ≥T2。
    """
    cert = combine(root, packs=packs)
    if not cert["legal"]:
        return {"ok": False, "reason": "组合非法（先修五不变量）", "certificate": cert}
    src_map, combo_packs = _flatten_sources(root, packs)
    own = sorted({m for ms in src_map.values() for m in ms})
    if not own:
        return {"ok": False, "reason": "空组合（无借阅模块）", "certificate": cert}
    name = combo_id or ("组合包-" + "-".join(packs[:2]))
    if not re.fullmatch(r"[\u4e00-\u9fffA-Za-z0-9_\-]{2,40}", name):
        return {"ok": False, "reason": "组合包名不合形：%r" % name}
    cat = category or ("组合域-%s" % name.replace("组合包-", ""))
    # 管线 id：三级池里取未占用
    used = set()
    reg = _read_json(Path(root) / "desktop/src/core/registry.json") or {}
    used |= {str(p.get("pipeline")) for p in reg.get("protocols") or []}
    # 幂等：本组合包若已存在（protocol.yaml 有合形管线号）→ 复用，不再重新分配
    # （实测 2026-09-23：重复 materialize 会把 P108 换成 P109，产生无谓 churn 与陈旧管线文件）
    pid = ""
    existing = Path(root) / "community" / name / "protocol.yaml"
    if existing.is_file():
        m = re.search(r"(?m)^\s*pipeline:\s*(P\d{2,3})\s*$", existing.read_text(encoding="utf-8"))
        if m:
            pid = m.group(1)
    if not pid:
        pid = next((x for x in ["P%03d" % i for i in range(100, 200)] if x not in used), "")
    if not pid:
        return {"ok": False, "reason": "管线 id 池已用尽", "certificate": cert}
    layers: Dict[str, List[str]] = {}
    for m in cert["modules"]:
        rec = prof_get_module(root, m)
        lay = str(rec.get("layer") or "P40")
        layers.setdefault(lay, [])
        if m not in layers[lay]:
            layers[lay].append(m)
    pkg_dir = Path(root) / "community" / name
    files: Dict[str, str] = {}
    refs = [(sp, ms) for sp, ms in sorted(src_map.items()) if ms]
    proto = [
        "# protocol.yaml — 组合包协议声明（组合引擎产物化：%s）" % name,
        "# 由 `nf combine materialize` 生成；机读真相 = 本文件，人读速览 = README.md（双源一致）",
        "protocol:",
        '  schema_version: "2"',
        "package:",
        '  conformance: "L2"',
        "  id: %s" % name,
        "  name: %s" % name,
        '  version: "1.0.0"',
        "  pipeline: %s" % pid,
        "  module_id_range: []          # 组合包不新增模块（全部经 references 只读借阅）",
        "  categories:",
        "    - %s" % cat,
        "  dependencies:",
        "    core_only: true",
        "    core_modules: [%s]" % ", ".join(CORE13),
        "    cross_package: []",
        "  references:",
    ]
    for sp, ms in refs:
        for mid in ms:
            proto += ["    - source_package: %s" % sp,
                      "      module_id: %s" % mid,
                      '      source_schema_version: "2"',
                      "      asset_readonly: true"]
    proto += ["  modules: []", "  assets:",
              "    count: 0",
              "    readme: README.md",
              "  mount_layers:          # 堆叠写入 available（default 留空，规避同层 default 冲突）"
                  ""]
    for lay, ms in sorted(layers.items()):
        proto.append("    %s: {default: [], available: [%s]}" % (lay, ", ".join(ms)))
    files["community/%s/protocol.yaml" % name] = "\n".join(proto) + "\n"
    files["community/%s/README.md" % name] = combo_readme(name, packs, cert, refs, layers, pid)
    files["community/%s/assets/README.md" % name] = combo_assets_readme(refs, layers)
    files["community/%s/pipelines/%s_%s装配流管线.md" % (name, pid, name)] = combo_pipeline(
        name, pid, layers, cert)
    files.update(combo_outputs(root, name, cert, layers))
    written, changed = [], []
    for f in sorted((pkg_dir / "pipelines").glob("*.md")) if (pkg_dir / "pipelines").is_dir() else []:
        tok = f.name.split("_")[0]
        if re.fullmatch(r"P\d{2,3}", tok) and tok != pid:
            f.unlink()                        # 陈旧管线（改号残留）
    for rel, text in sorted(files.items()):
        p = Path(root) / rel
        if p.is_file() and p.read_bytes() == text.encode("utf-8"):
            continue
        changed.append(rel)
        if write:
            p.parent.mkdir(parents=True, exist_ok=True)
            # 原子写（2026-09-30 收口）：组合包产物落在 `community/<组合包>/…`，
            # 写入期间有人跑 check14/15/32 会读到半截正文。
            atomic_write.write_text(p, text)
            written.append(rel)
    return {"ok": True, "package": name, "pipeline": pid, "category": cat,
            "references": sum(len(ms) for _, ms in refs), "modules": len(own),
            "layers": {k: len(v) for k, v in sorted(layers.items())},
            "files": len(files), "changed": len(changed), "written": len(written),
            "combo_packs_flattened": combo_packs, "certificate": cert}


def scan(root: str = ".") -> Tuple[List[str], Dict[str, Any]]:
    """check32 子扫描入口：在盘组合证书复算（T4）+ 广度证明。

    派生结果按**输入内容指纹**缓存（输入面见 `SCAN_INPUTS`：各包实况 + 模块契约 + 协议声明 +
    registry）。**冷进程也走这层**（2026-09-29 实测：宽面指纹在同一只读作用域内近乎白拿，而重算
    这条派生账贵得多；见 `quality_depth_scan.scan` 的实测数字）。
    """
    return csc.memo_pair("pack-combo-scan", SCAN_INPUTS, _scan_impl, root,
                         code_modules=("core.pack_combo",))


def _scan_impl(root: str = ".") -> Tuple[List[str], Dict[str, Any]]:
    """真算（未命中缓存时走这里）。"""
    issues: List[str] = []
    doc = declared(root)
    certs = doc.get("certificates") or []
    witness = _combo_witness(root, profiles(root), _module_contracts(root))
    for cert in certs:
        issues += _certificate_lines(root, cert, witness)
    br = breadth(root, _witness=witness)
    if not br["all_legal"]:
        issues.append("广度证明不成立：两两 %d/%d · 三元 %d/%d · 四元 %d/%d · 五元 %d/%d · "
                      "六元 %d/%d（样本 %s）"
                      % (br["pairs_legal"], br["pairs"], br["triples_legal"], br["triples"],
                         br["quads_legal"], br["quads"], br["quints_legal"], br["quints"],
                         br["sexts_legal"], br["sexts"], br["failures"][:2]))
    return issues, {"declared_certificates": len(certs), "breadth": br}
