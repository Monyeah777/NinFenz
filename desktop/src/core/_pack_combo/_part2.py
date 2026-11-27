"""core.pack_combo 私有实现分片 2/2（对外只经 core.pack_combo 门面导入）：breadth 等"""

from __future__ import annotations

import copy
import itertools
import random

from core import conformance_scan as csc
from core import import_graph as _ig
from core._pack_combo._base import (
    _cache_key,
    _content_store,
    _inputs_fingerprint,
    _module_contracts,
    _root_cache,
    profiles,
)
from core._pack_combo._cert import _certificate_lines, _combo_witness, _verdict_cached, declared
from core._pack_combo._const import _CACHE, _CONTENT_CACHE, SCAN_INPUTS

from ._part1 import BreadthOptions


def breadth(root: str = '.', opts: BreadthOptions | None = None) -> Dict[str, Any]:
    """广度证明：全部两两 + 定种子抽样三元 / 四元 / 五元 / 六元，跑同一套不变量。

    参与面 = `community/` 下全部已登记协议包（域包 + 组合包 + 既有社区包）——
    组合包带 `references`（借阅源包模块），本轮起一并进入广度抽样，验证
    「组合包本身也能当组合成员」（摊平后不变量仍成立）。

    结果按**输入内容指纹 + 抽样参数**缓存（`_CONTENT_CACHE`）：广度证明是诸输入的纯函数，
    输入没变就不必重跑 6910 次组合（实测 ~0.92 s）；输入一变指纹就变，无陈旧风险。
    """

    opts = opts if opts is not None else BreadthOptions()
    triple_sample = opts.triple_sample
    quad_sample = opts.quad_sample
    quint_sample = opts.quint_sample
    sext_sample = opts.sext_sample
    seed = opts.seed
    _witness = opts._witness
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


def _scan_impl(root: str = ".") -> Tuple[List[str], Dict[str, Any]]:
    """真算（未命中缓存时走这里）。"""
    issues: List[str] = []
    doc = declared(root)
    certs = doc.get("certificates") or []
    witness = _combo_witness(root, profiles(root), _module_contracts(root))
    for cert in certs:
        issues += _certificate_lines(root, cert, witness)
    br = breadth(root, opts=BreadthOptions(_witness=witness))
    if not br["all_legal"]:
        issues.append("广度证明不成立：两两 %d/%d · 三元 %d/%d · 四元 %d/%d · 五元 %d/%d · "
                      "六元 %d/%d（样本 %s）"
                      % (br["pairs_legal"], br["pairs"], br["triples_legal"], br["triples"],
                         br["quads_legal"], br["quads"], br["quints_legal"], br["quints"],
                         br["sexts_legal"], br["sexts"], br["failures"][:2]))
    return issues, {"declared_certificates": len(certs), "breadth": br}


def scan(root: str = ".") -> Tuple[List[str], Dict[str, Any]]:
    """check32 子扫描入口：在盘组合证书复算（T4）+ 广度证明。

    派生结果按**输入内容指纹**缓存（输入面见 `SCAN_INPUTS`：各包实况 + 模块契约 + 协议声明 +
    registry）。**冷进程也走这层**（2026-09-29 实测：宽面指纹在同一只读作用域内近乎白拿，而重算
    这条派生账贵得多；见 `quality_depth_scan.scan` 的实测数字）。
    """
    return csc.memo_pair("pack-combo-scan", SCAN_INPUTS, _scan_impl, root,
                         code_modules=("core.pack_combo",))
