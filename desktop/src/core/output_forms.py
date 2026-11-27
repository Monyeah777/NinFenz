"""产出形态面（output forms）——把「产出一律是散文」的缺口机制化。

背景（内部差距）：两个非叙事域包（AI系统域包 / 量化金融域包）的产出**全是散文**——
连数据契约、指标表、策略规格都是 Markdown 表格：人能读，机器只能当文本，判不了形状、
判不了单位、判不了引用完整，更复算不了数。本模块把产出**形态**本身当成一等对象：

1. **形态清单**（`protocol/output_forms.json`）：主域全量形态类别（结构化数据 / 表格 /
   图表 / 图结构 / 契约 / 接口 / 时序 / 打包 / 文档 / 金融专业面 / AI 专业面）逐条登记，
   每条带外部规范入口与**可达性实证**（本机 GET 结果），并标注本仓的机验能力档位。
2. **机检档位**（tier）：T0 散文 → T1 良构 → T2 形状（schema/结构）→ T3 语义
   （引用 / 单位 / 口径 / 双源一致）→ T4 **可复算**（本仓引擎重算并与在盘产物逐字段比对）。
3. **自家校验器**：本仓零第三方硬依赖（purity R5），故自带 JSON Schema 2020-12
   **子集**校验器（不支持的官方关键字**显式列出**，绝不静默通过）+ 形态结构校验器
   （Vega-Lite / Mermaid / GraphML / CSV / XML…）。
4. **包级清单**（`community/<包>/outputs/INDEX.json`）：每个包声明自己的机验产出面
   （路径 / 形态 / 档位 / 角色 / schema / 双源 / 复算），check14/check32 据此判定。
5. **机验率与功能面计量**：`machine_verifiable_ratio` = 机验面 /（机验面 + 散文资产），
   `functional_faces` = T4 面数；基线落 `protocol/output_forms_baseline.json`（可重签），
   机验率**回退即 FAIL**（口径同 check8 资产行基线，不把数字写死进 verify.sh）。

纪律：不伪造——形态可达性实证失败如实记档；不支持的关键字显式上报；复算不一致即 FAIL。
"""

# 读点：产出清单/形态清单读取在 _output_forms._registry 里仍走 json_doc.loads（N11）。

from __future__ import annotations

# ruff: noqa: F401 — 门面按原模块面重新导出（re-export 是职责，不是未使用）
import sys as _sys
import types as _types

# 依赖面：逐字保留原模块 import 面（含函数内 core import 的边）——
# 耦合图/纯度面按模块级 import 计算，勿删（见 re-export 说明）。
from core import json_doc
from core import atomic_write
from core import conformance_scan as _csc   # 共享语料（读缓存 / 列目录缓存 / 内容指纹）
# 导入闭包指纹：由调用方算（持久层不再反向依赖解析层，见 2026-09-29 拆环）
from core import import_graph as _ig
from core import paths as _paths            # 仓库内包含性判据（单一真相源）
# ---------------------------------------------------------------- JSON Schema 子集

# JSON Schema 校验器已迁到**叶子件** `core/json_schema.py`（2026-09-29）：原先
# `output_forms ↔ pack_combo` 是模块级双向对（pack_combo 只用这一个纯函数），迁出后
# 两边都单向依赖叶子，零环由 `coupling_metrics` 机检。
from core.json_schema import json_schema_check as _js_check
from core.json_schema import pattern_issue as _pattern_issue
from core import conformance_scan as _csc
from core import quant_metrics as qm
from core import domain_metrics as dm
from core import pack_combo as pc            # 惰性导入：避免模块级环
from core import disk_cache
from core import concept_graph as cg
from core import pack_combo as pc

import copy
from typing import Any, Dict
from core import conformance_scan as _csc
from core import import_graph as _ig

from ._output_forms._const import (
    BASELINE_REL,
    INDEX_REL,
    REGISTRY_INPUT,
    REGISTRY_REL,
    STATUSES,
    TIERS,
    _DTD_RE,
    _EXT_FORM,
    _FORM_MAX_TIER,
    _MERMAID_KINDS,
)
from ._output_forms._registry import (
    _pack_dirs,
    _read_bytes_cached,
    _read_json,
    _read_text_cached,
    _rel,
    detect,
    load_registry,
    registry_verify,
)
from ._output_forms._checkers import (
    _check_csv,
    _check_domain_report,
    _check_domain_spec,
    _check_dot,
    _check_graphml,
    _check_json,
    _check_jsonl,
    _check_markdown,
    _check_mermaid,
    _check_quant_metrics,
    _check_toml,
    _check_vega_lite,
    _check_xml,
    _check_yaml,
    _xml_guard,
    json_schema_check,
)
from ._output_forms._pack import (
    _PACK_FACE_PARSED,
    _PACK_FACE_SHARED,
    _PACK_FACE_SLICE,
    _PACK_KEY_MEMO,
    _PACK_KEY_MEMO_MAX,
    _PACK_VERIFY_CACHE,
    _PACK_VERIFY_MAX,
    _matches_any,
    _pack_key_reusable,
    _pack_slice_patterns,
    _pack_verify_ok,
    _verify_pack_cached,
    _verify_pack_io,
    pack_content_key,
    pack_slice_index,
    shared_face_key,
)
from ._output_forms._gen_a import (
    _combo_doc,
    _gen_combo_cert,
    _gen_concept_closure,
    _gen_domain_report,
    _gen_mermaid,
    _gen_performance_report,
    _gen_vega,
    _gen_vega_metrics,
)
from ._output_forms._gen_b import (
    GENERATORS,
    _check_combo_cert,
    _combo_module_inputs,
    _gen_graphml_concept_dag,
    _gen_graphml_module_deps,
    _gen_mermaid_concept_dag,
    _gen_mermaid_layer_load,
    _gen_vega_layer_stack,
    _stack_pairs,
    m_prov,
)
from ._output_forms._index import (
    _FORM_CHECK,
    _deep_diff,
    _dual_source_check,
    _recompute_entry,
    render_outputs,
)
from ._output_forms._meter import (
    _count,
    baseline_verify,
    meter,
    write_baseline,
)
from ._output_forms._util import (
    _declared_out_rel,
    _dump,
    _gen_id,
    _pkg_rel,
    _reject_escape_forms,
)
from ._output_forms._meter import (
    _count,
    baseline_verify,
)
from ._output_forms._pack import (
    _verify_pack_cached,
    pack_slice_index,
    shared_face_key,
)
from ._output_forms._registry import (
    _pack_dirs,
    registry_verify,
)



#: 一次**只读**校验内共享「同文件读一次」。**真源是 conformance_scan 的共享语料缓存**——
#: 这样 `index_verify` 的读盘能与外层聚合（evaluate / qds.scan / conformance_report.run）
#: 的其它扫描器**共用同一份**（同一份包资产过去被四个模块各读一遍）。
#: 作用域仍严格等于一次 `index_verify` 调用（出口即清），所以不会读到陈旧内容；
#: 写路径（`render_outputs(write=True)`）从不进入该作用域。
def _memo_reads():
    from core import conformance_scan as _csc
    return _csc.read_memo()


#: `index_verify` 的**输入面**（穷举；内容键结果缓存的键就取自它）。
#: 有「读到的文件必须全部落在输入面内」的判据守着（test_conformance_scan.DerivedResultCacheTest），
#: 所以将来给本函数加新读取，判据会先红、逼着把新输入补进来——不会悄悄读到陈旧结果。
INDEX_INPUTS = ("community/*/outputs/**/*",
                "community/*/assets/*",
                "community/*/protocol.yaml",
                "community/*/modules/*.md",
                "04_模块库/*/*.md",
                "desktop/src/core/registry.json",
                # 2026-09-29 补齐（**陈旧洞**）：本模块真读这两件（形态清单 registry + 机验率基线）
                # ，
                # 原先一条都没申报 ⇒ 重签基线/改形态清单时 `output-forms-scan` 会**命中旧结果**。
                # 抓它的是「**逻辑读**」审计（`read_text_cached` 级追踪）：只盯 `io.open` 的旧判据看
                # 不见
                # 常驻层命中的读，这两条洞因此躲过了很久——见 `test_conformance_scan.LogicalReadFaceA
                # uditTest`。
                "protocol/output_forms.json",
                "protocol/output_forms_baseline.json")
#: 结果缓存（键 = 输入内容指纹；输入一变指纹就变，故不需要随请求清空）。
_INDEX_CACHE: Dict[str, Any] = {}


def _verify_pack(root: str, pkg: str) -> Tuple[List[str], List[Dict[str, Any]]]:
    """**单个包**的产出面校验（原体；被 `_index_verify_impl` 按包内容键缓存）。"""
    issues: List[str] = []
    rows: List[Dict[str, Any]] = []
    rel = "community/%s/%s" % (pkg, INDEX_REL)
    idx, err = _read_json(_rel(root, rel))
    if err:
        issues.append("%s: %s" % (rel, err))
        return issues, rows
    if idx.get("schema") != "nf-output-index/1":
        issues.append("%s: schema 应为 nf-output-index/1" % rel)
    if idx.get("package") != pkg:
        issues.append("%s: package 字段 %r ≠ 包目录名 %r" % (rel, idx.get("package"), pkg))
    for entry in idx.get("outputs") or []:
        path = entry.get("path") or ""
        form = entry.get("form") or ""
        tier = entry.get("tier") or ""
        if not path:
            issues.append("%s: outputs 条目缺 path" % rel)
            continue
        if tier not in TIERS:
            issues.append("%s: %s 档位非法 %r" % (rel, path, tier))
            continue
        try:
            out_rel = _declared_out_rel(root, pkg, path)
        except ValueError as exc:                     # 外来清单里的越界写法 → 问题，不读盘
            issues.append("%s: %s" % (rel, exc))
            continue
        if not _rel(root, out_rel).is_file():
            issues.append("%s: 声明产出面不存在 %s" % (rel, path))
            continue
        got_form, got_tier = detect(root, out_rel)
        if form and form != got_form:
            issues.append("%s: %s 声明形态 %s，实测 %s" % (rel, path, form, got_form))
        if TIERS.index(tier) > TIERS.index(got_tier):
            issues.append("%s: %s 声明档位 %s 超出本仓可判上限 %s"
                          % (rel, path, tier, got_tier))
        checker = _FORM_CHECK.get(form or got_form)
        sub = checker(root, out_rel) if checker else []
        issues += ["%s: %s %s" % (rel, path, s) for s in sub]
        sch_rel = entry.get("schema") or ""
        if sch_rel:
            try:
                full = _declared_out_rel(root, pkg, sch_rel)
            except ValueError as exc:
                issues.append("%s: %s %s" % (rel, path, exc))
                full = ""
            schema, serr = _read_json(_rel(root, full)) if full else (None, "schema 路径越界")
            if serr:
                issues.append("%s: %s schema %s" % (rel, path, serr))
            else:
                inst, ierr = _read_json(_rel(root, out_rel))
                if ierr:
                    issues.append("%s: %s %s" % (rel, path, ierr))
                else:
                    unsup: List[str] = []
                    errs = json_schema_check(inst, schema, unsupported=unsup)
                    issues += ["%s: %s schema 不符 %s" % (rel, path, e) for e in errs[:8]]
        ds = entry.get("dual_source")
        if isinstance(ds, dict):
            issues += ["%s: %s %s" % (rel, path, m)
                       for m in _dual_source_check(root, pkg, out_rel, ds)]
        rc = entry.get("recompute")
        if isinstance(rc, dict):
            sub_issues, _st = _recompute_entry(root, {**entry, "_pkg": pkg})
            issues += ["%s: %s" % (rel, s) for s in sub_issues]
        elif tier == "T4":
            issues.append("%s: %s 声明 T4（可复算）却无 recompute 声明" % (rel, path))
        rows.append({"package": pkg, "path": path, "form": form or got_form,
                     "tier": tier, "role": entry.get("role") or ""})
    return issues, rows


def index_verify(root: str = ".") -> Tuple[List[str], Dict[str, Any]]:
    """包内产出清单机检（外层）：一次调用内共享「同文件读一次」（见 `_memo_reads`）。

    逐件校验会把同一份产物读 5–8 遍（detect / 查重 / schema / 双源 / 复算）——实测热跑里
    3027 次读盘、占该函数 1.54 s 的一大半。memo 的作用域严格等于**这一次调用**（出口即清），
    所以不会出现「读到陈旧内容」；下一次调用照常重新读盘。

    再叠一层**内容键结果缓存**：本函数是那批输入的纯函数，按输入内容指纹缓存后，同内容重复调用
    （`nf score` 与 `nf conformance` 都会走到它）省掉整轮校验（实测 ~0.72 s）。输入面见
    `INDEX_INPUTS`，并有「读到的文件必须全部落在输入面内」的判据守着
    （见 test_conformance_scan.DerivedResultCacheTest）。
    """
    fp = _csc.face_fingerprint(root, INDEX_INPUTS)
    hit = _INDEX_CACHE.get(fp)
    if hit is None:
        from core import disk_cache
        dkey = disk_cache.key("index-verify", fp, root=root,
                              code_scope=_ig.code_scope_fingerprint(root, ("core.output_forms",)))
        cached = disk_cache.load("index-verify", dkey, validate=_csc.result_pair_ok)
        if cached is None:
            with _memo_reads():
                got = _index_verify_impl(root)
            disk_cache.store("index-verify", dkey,
                             {"issues": list(got[0]), "stats": got[1]})
        else:
            got = (list(cached["issues"]), dict(cached["stats"]))
        # 只**存**不拷：`got` 是本次刚算出来（或刚从盘里读出来）的新对象，不存在与别处的别名；
        # 真正需要的是返回时那一份拷贝（防调用方改到缓存）。过去这里还多深拷一次
        # （实测本仓 1500+ 行产出清单 = 每轮白拷 ~8 ms）。
        hit = _INDEX_CACHE[fp] = got
    return copy.deepcopy(hit[0]), copy.deepcopy(hit[1])


def _index_verify_impl(root: str = ".") -> Tuple[List[str], Dict[str, Any]]:
    """包级产出清单机检：声明存在 / 形态与档位属实 / schema 校验 / 双源一致 / T4 复算。"""
    issues: List[str] = []
    rows: List[Dict[str, Any]] = []
    shared = shared_face_key(root)                 # 共享面每个内容状态只算一遍（过去 111 遍）
    slices = pack_slice_index(root)                # 包切片一次枚举（过去 106 包各 4 条模式 = 424 次）
    for pkg in _pack_dirs(root):
        hit = _verify_pack_cached(root, pkg, shared, slices.get(pkg, []))
        issues += hit[0]
        rows += hit[1]
    stats = {"packages": len(_pack_dirs(root)), "outputs": len(rows),
             "by_role": _count(rows, "role"), "by_tier": _count(rows, "tier"),
             "by_form": _count(rows, "form")}
    return issues, stats


def scan(root: str = ".") -> Tuple[List[str], Dict[str, Any]]:
    """check32 子扫描入口：形态清单 + 包级产出清单 + 机验率基线三合一。

    派生结果按**输入内容指纹**缓存（输入面复用同模块已穷举的 `INDEX_INPUTS`——它正是本入口
    三个子校验的读面）。**冷进程也走这层**（2026-09-29 实测：宽面指纹在同一只读作用域内近乎白拿，
    而重算这条派生账贵得多；见 `quality_depth_scan.scan` 的实测数字）。
    """
    return _csc.memo_pair("output-forms-scan", INDEX_INPUTS, _scan_impl, root,
                          code_modules=("core.output_forms",))


def _scan_impl(root: str = ".") -> Tuple[List[str], Dict[str, Any]]:
    """真算（未命中缓存时走这里）。"""
    issues: List[str] = []
    reg_issues, reg_stats = registry_verify(root)
    issues += ["形态清单: %s" % i for i in reg_issues]
    idx_issues, idx_stats = index_verify(root)
    issues += ["包级产出面: %s" % i for i in idx_issues]
    base_issues, base_stats = baseline_verify(root)
    issues += ["机验率基线: %s" % i for i in base_issues]
    stats = {"registry": reg_stats, "index": idx_stats,
             "meter": base_stats.get("packages", {})}
    return issues, stats
