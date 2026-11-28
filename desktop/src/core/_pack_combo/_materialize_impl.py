"""core.pack_combo 私有实现分片：组合包产物化（materialize）的真算。

对外只经 core.pack_combo 门面（经 _part1 重新导出）导入；本文件只承载实现，不改变对外面。
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Sequence, Tuple

from core import atomic_write
from core._pack_combo._base import _read_json
from core._pack_combo._combine import combine
from core._pack_combo._const import CORE13
from core._pack_combo._materialize import _flatten_sources, combo_outputs, prof_get_module
from core._pack_combo._readme import combo_assets_readme, combo_pipeline, combo_readme


# ---------------------------------------------------------------- materialize
def _reserve_pipeline(root: str, name: str) -> str:
    """管线 id：已存在组合包复用其号；否则池里取未占用。"""
    used: set = set()
    reg = _read_json(Path(root) / "desktop/src/core/registry.json") or {}
    used |= {str(p.get("pipeline")) for p in reg.get("protocols") or []}
    # 幂等：本组合包若已存在（protocol.yaml 有合形管线号）→ 复用，不再重新分配
    # （实测 2026-09-23：重复 materialize 会把 P108 换成 P109，产生无谓 churn 与陈旧管线文件）
    existing = Path(root) / "community" / name / "protocol.yaml"
    if existing.is_file():
        m = re.search(r"(?m)^\s*pipeline:\s*(P\d{2,3})\s*$",
                      existing.read_text(encoding="utf-8"))
        if m:
            return m.group(1)
    return next((x for x in ["P%03d" % i for i in range(100, 200)] if x not in used), "")


def _layer_map(root: str, modules: Sequence[str]) -> Dict[str, List[str]]:
    """组合模块 → {层: [模块]}（缺省层 P40）。"""
    layers: Dict[str, List[str]] = {}
    for m in modules:
        rec = prof_get_module(root, m)
        lay = str(rec.get("layer") or "P40")
        layers.setdefault(lay, [])
        if m not in layers[lay]:
            layers[lay].append(m)
    return layers


def _proto_lines(name: str, pid: str, cat: str, refs: List[Any],
                 layers: Dict[str, List[str]]) -> List[str]:
    """protocol.yaml 正文行（组合包不新增模块，全部 references 只读借阅）。"""
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
    return proto


def _bundle_files(root: str, name: str, pid: str, refs: List[Any],
                  layers: Dict[str, List[str]], ctx: Dict[str, Any]) -> Dict[str, str]:
    """组合包全部产物文件（协议/README/资产说明/管线/机验产出面）。"""
    files: Dict[str, str] = {}
    proto = _proto_lines(name, pid, ctx["category"], refs, layers)
    files["community/%s/protocol.yaml" % name] = "\n".join(proto) + "\n"
    files["community/%s/README.md" % name] = combo_readme(
        name, ctx["packs"], ctx["cert"], refs, layers, pid)
    files["community/%s/assets/README.md" % name] = combo_assets_readme(refs, layers)
    files["community/%s/pipelines/%s_%s装配流管线.md" % (name, pid, name)] = combo_pipeline(
        name, pid, layers, ctx["cert"])
    files.update(combo_outputs(root, name, ctx["cert"], layers))
    return files


def _cleanup_stale_pipelines(pkg_dir: Path, pid: str) -> None:
    """删陈旧管线（改号残留）。"""
    if not (pkg_dir / "pipelines").is_dir():
        return
    for f in sorted((pkg_dir / "pipelines").glob("*.md")):
        tok = f.name.split("_")[0]
        if re.fullmatch(r"P\d{2,3}", tok) and tok != pid:
            f.unlink()


def _write_bundle(root: str, files: Dict[str, str],
                  write: bool) -> Tuple[List[str], List[str]]:
    """落盘（原子写）→ (changed, written)。"""
    changed: List[str] = []
    written: List[str] = []
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
    return changed, written


def _materialize_result(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """materialize 成功返回面（证书 + 计数）。"""
    return {"ok": True, "package": ctx["name"], "pipeline": ctx["pid"],
            "category": ctx["cat"],
            "references": sum(len(ms) for _, ms in ctx["refs"]), "modules": len(ctx["own"]),
            "layers": {k: len(v) for k, v in sorted(ctx["layers"].items())},
            "files": len(ctx["files"]), "changed": len(ctx["changed"]),
            "written": len(ctx["written"]),
            "combo_packs_flattened": ctx["combo_packs"], "certificate": ctx["cert"]}


def _combo_identity(packs: Sequence[str], combo_id: str,
                    category: str) -> Tuple[str, str]:
    """组合包名与品类（缺省派生；不做形状校验）。"""
    name = combo_id or ("组合包-" + "-".join(packs[:2]))
    cat = category or ("组合域-%s" % name.replace("组合包-", ""))
    return name, cat


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
    name, cat = _combo_identity(packs, combo_id, category)
    if not re.fullmatch(r"[\u4e00-\u9fffA-Za-z0-9_\-]{2,40}", name):
        return {"ok": False, "reason": "组合包名不合形：%r" % name}
    pid = _reserve_pipeline(root, name)
    if not pid:
        return {"ok": False, "reason": "管线 id 池已用尽", "certificate": cert}
    layers = _layer_map(root, cert["modules"])
    refs = [(sp, ms) for sp, ms in sorted(src_map.items()) if ms]
    files = _bundle_files(root, name, pid, refs, layers,
                          {"category": cat, "packs": packs, "cert": cert})
    _cleanup_stale_pipelines(Path(root) / "community" / name, pid)
    changed, written = _write_bundle(root, files, write)
    return _materialize_result({"name": name, "pid": pid, "cat": cat, "refs": refs,
                                "own": own, "layers": layers, "files": files,
                                "combo_packs": combo_packs, "cert": cert,
                                "changed": changed, "written": written})
