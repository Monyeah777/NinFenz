"""core.pack_combo 私有实现分片 2/2（对外只经 core.pack_combo 门面导入）：breadth 等"""

from __future__ import annotations
from typing import Any, Dict, List, Set, Tuple

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
    fp = _inputs_fingerprint(root)          # 只算一遍：进程内键与落盘键共用（过去算两遍，白花 57 ms）
    content_key = ("breadth", fp, opts.triple_sample, opts.quad_sample,
                   opts.quint_sample, opts.sext_sample, opts.seed)
    hit, dkey = _cached_breadth(root, content_key, fp)
    if hit is not None:
        return copy.deepcopy(hit)
    env = _breadth_env(root, opts)
    _judge_pairs(env)
    rnd = random.Random(opts.seed)
    _judge_sample(env, rnd, 3, opts.triple_sample, "triples", False)
    _judge_sample(env, rnd, 4, opts.quad_sample, "quads", False)
    for size, tag in ((5, "quints"), (6, "sexts")):
        want = min(opts.quint_sample if size == 5 else opts.sext_sample, 5000)
        _judge_sample(env, rnd, size, want, tag, True)
    env["stats"]["all_legal"] = _all_legal(env["stats"])
    _store_breadth(content_key, env["stats"], dkey)
    return env["stats"]


def _cached_breadth(root: str, content_key: tuple, fp):
    """进程内缓存 → 持久层缓存 → (命中值或 None, 落盘键)。"""
    hit = _CONTENT_CACHE.get(content_key)
    if hit is not None:
        return hit, None
    from core import disk_cache
    triple_sample, quad_sample, quint_sample, sext_sample, seed = content_key[2:]
    dkey = disk_cache.key("pack-breadth", str(fp),
                          str(triple_sample), str(quad_sample), str(quint_sample),
                          str(sext_sample), str(seed), root=root,
                          code_scope=_ig.code_scope_fingerprint(root, ("core.pack_combo",)))
    hit = disk_cache.load("pack-breadth", dkey,
                          validate=lambda v: isinstance(v, dict) and bool(v))
    if hit is not None:
        _content_store(content_key, hit)
    return hit, dkey


def _breadth_env(root: str, opts: BreadthOptions) -> Dict[str, Any]:
    """广度证明上下文（输入面 + 见证 + 统计骨架）。"""
    key = _cache_key(root)
    prof = profiles(root)
    contracts = _module_contracts(root)
    # 逐组合判决缓存的全局见证（本轮算一遍；`scan()` 已算过就直接复用）
    witness = opts._witness or _combo_witness(root, prof, contracts)
    cached = _root_cache(key)
    cached.update({"prof": prof, "contracts": contracts})
    _CACHE[key] = cached
    names = sorted(prof)
    stats: Dict[str, Any] = {"packs": len(names), "pairs": 0, "pairs_legal": 0,
                             "triples": 0, "triples_legal": 0, "quads": 0, "quads_legal": 0,
                             "quints": 0, "quints_legal": 0,
                             "sexts": 0, "sexts_legal": 0,
                             "failures": []}
    return {"root": root, "prof": prof, "contracts": contracts, "witness": witness,
            "names": names, "stats": stats}


def _judge_pairs(env: Dict[str, Any]) -> None:
    """全部两两组合判决。"""
    stats = env["stats"]
    for a, b in itertools.combinations(env["names"], 2):
        legal, dangling, unbridged = _verdict_cached(
            env["root"], (a, b), env["prof"], env["contracts"], env["witness"])
        stats["pairs"] += 1
        stats["pairs_legal"] += 1 if legal else 0
        _maybe_failure(env, [a, b], legal, dangling, unbridged)


def _maybe_failure(env: Dict[str, Any], combo: list, legal: bool, dangling,
                   unbridged) -> None:
    """不合法组合记入 failures（最多 10 条）。"""
    stats = env["stats"]
    if not legal and len(stats["failures"]) < 10:
        stats["failures"].append({"combo": combo, "dangling": dangling,
                                  "unbridged": unbridged})


def _sample_combos(env: Dict[str, Any], rnd, size: int, want: int) -> Set[Tuple[str, ...]]:
    """定种子抽 size 元组合（去重、稳定）。"""
    names = env["names"]
    picks: Set[Tuple[str, ...]] = set()
    if len(names) < size:
        return picks
    while len(picks) < min(want, 5000):
        picks.add(tuple(sorted(rnd.sample(names, size))))
    return picks


def _judge_sample(env: Dict[str, Any], rnd, size: int, want: int, tag: str,
                  collect: bool) -> None:
    """抽 size 元组合并逐组合判决。"""
    stats = env["stats"]
    for p in sorted(_sample_combos(env, rnd, size, want)):
        legal, dangling, unbridged = _verdict_cached(
            env["root"], p, env["prof"], env["contracts"], env["witness"])
        stats[tag] += 1
        stats[tag + "_legal"] += 1 if legal else 0
        if collect:
            _maybe_failure(env, list(p), legal, dangling, unbridged)


def _all_legal(stats: Dict[str, Any]) -> bool:
    """各元数「合法数 == 总数」的不变量。"""
    return bool(
        stats["pairs"] == stats["pairs_legal"]
        and stats["triples"] == stats["triples_legal"]
        and stats["quads"] == stats["quads_legal"]
        and stats["quints"] == stats["quints_legal"]
        and stats["sexts"] == stats["sexts_legal"])


def _store_breadth(content_key: tuple, stats: Dict[str, Any], dkey) -> None:
    """结果写回进程内缓存与持久层。"""
    _content_store(content_key, stats)
    if dkey is not None:
        from core import disk_cache
        disk_cache.store("pack-breadth", dkey, stats)


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
