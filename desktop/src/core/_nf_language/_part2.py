"""core.nf_language 私有实现分片 2/2（对外只经 core.nf_language 门面导入）：_relations 等"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from ._part1 import (
    _ASSET_TOKEN,
    EVENT_REGISTRY_REL,
    REGISTRY_REL,
    SCAN_GLOBS,
    SymbolIndex,
    SymbolOptions,
    _bare_alias,
    _event_relations,
    _events,
    _layers,
    _mount_relations,
    _pipe_id_of,
    _pipeline_relations,
    _read_json,
    _symbol,
    module_meta,
)


def _relations(reg: Dict[str, Any], root: Path) -> Dict[str, List[Dict[str, str]]]:
    """结构化引用关系（token → [{why, target, kind}]）——**全部来自 registry 真源**。

    为什么只做结构化：NF 里的「引用」是有登记的关系（事件 ↔ 发布/订阅模块、模块 ↔ 挂载层、
    管线 ← 域包采用），**不是**文本相似。做全文搜索会给编辑器一堆假引用，正是本仓明令的
    「不猜」；没有登记关系的 token 返回空表（失败关闭）。
    """
    rel: Dict[str, List[Dict[str, str]]] = {}
    _event_relations(reg, rel)
    _mount_relations(reg, rel)
    _pipeline_relations(reg, root, rel)
    return rel


def _mounts_doc(reg: Dict[str, Any]) -> Dict[str, str]:
    """官方核心模块的挂载摘要（id → 文本）；未登记即空表项——不臆造挂载。"""
    out: Dict[str, str] = {}
    for m in reg.get("modules") or []:
        mounts = ", ".join("%s(%s)" % (x.get("layer"), x.get("status"))
                           for x in (m.get("mounts") or []) if isinstance(x, dict))
        out[str(m.get("id") or "")] = "挂载：%s" % (mounts or "未登记")
    return out


def _modules(root: Path, reg: Dict[str, Any], out: List[Dict[str, Any]]) -> None:
    """模块符号：文件面读 `machine_contract.id/name`（域包文件名与编号不对应时仍解析正确）。"""
    mount_doc = _mounts_doc(reg)
    scanned: List[Tuple[str, str, str, str]] = []       # (mid, name, rel, pkg)
    for pat, official in (("04_模块库/*/*.md", True), ("community/*/modules/*.md", False)):
        for path in sorted(root.glob(pat)):
            rel = path.relative_to(root).as_posix()
            mid, name = module_meta(path)
            if not mid:                                # 无契约块 → 按文件名回退（尽力而为）
                mid = path.stem.split("_", 1)[0]
                name = path.stem.split("_", 1)[1] if "_" in path.stem else path.stem
            pkg = "官方核心" if official else rel.split("/")[1]
            scanned.append((mid, name, rel, pkg))
    for mid, name, rel, pkg in scanned:
        if not mid:
            continue
        if pkg == "官方核心":
            detail = "官方核心 · %s" % mount_doc.get(mid, "未登记挂载").split("：")[-1]
        else:
            detail = "社区包 %s" % pkg
        doc = "模块 %s · %s · 归属：%s%s" % (
            mid, name, pkg,
            (" · " + mount_doc[mid]) if pkg == "官方核心" and mid in mount_doc else "")
        out.append(_symbol('module', mid, detail, doc, rel, opts=SymbolOptions(aliases=_bare_alias(mid))))


def _user_assets(root: Path, out: List[Dict[str, Any]]) -> None:
    for ap in sorted(root.glob("05_资产库/用户自定义/*.md")):
        if ap.name == "README.md":
            continue
        rel = ap.relative_to(root).as_posix()
        for key in sorted(set(_ASSET_TOKEN.findall(ap.stem))):
            out.append(_symbol("asset", key, "资产 · 用户自定义",
                               "资产键 %s · 用户自定义扩增槽" % key, rel))


def _assets(root: Path, out: List[Dict[str, Any]]) -> None:
    for ap in sorted(root.glob("community/*/assets/*.md")):
        if ap.name == "README.md":
            continue
        rel = ap.relative_to(root).as_posix()
        pkg = rel.split("/")[1]
        for key in sorted(set(_ASSET_TOKEN.findall(ap.stem))):
            out.append(_symbol("asset", key, "资产 · 包 %s" % pkg,
                               "资产键 %s · 包 %s" % (key, pkg), rel))


def _pipelines(root: Path, reg: Dict[str, Any], out: List[Dict[str, Any]]) -> None:
    seen_pipe: Dict[str, str] = {}
    for path in sorted(root.glob("03_管线库/*.md")):
        pid = _pipe_id_of(path)
        if pid:
            seen_pipe[pid] = path.relative_to(root).as_posix()
    for p in reg.get("protocols") or []:
        pkg, pid = str(p.get("id") or ""), str(p.get("pipeline") or "")
        if not pkg or not pid:
            continue
        for path in sorted((root / "community" / pkg / "pipelines").glob("*.md")):
            seen_pipe.setdefault(pid, path.relative_to(root).as_posix())
    for pid in sorted(seen_pipe):
        out.append(_symbol("pipeline", pid, "管线", "管线 %s" % pid, seen_pipe[pid]))


def signature(root: str) -> Tuple[Tuple[str, int, int], ...]:
    """扫描面孔径签名（路径 / mtime_ns / 大小）；变即索引需要重建。

    含两份 JSON 真源与全部 glob——任一模块/资产/管线件增删改都会改变签名，
    长驻编辑器会话据此惰性重扫（不需要重启 LSP）。
    """
    r = Path(root)
    rows: List[Tuple[str, int, int]] = []
    for rel in (REGISTRY_REL, EVENT_REGISTRY_REL):
        p = r / rel
        try:
            st = p.stat()
        except OSError:
            rows.append((rel, 0, 0))
            continue
        rows.append((rel, st.st_mtime_ns, st.st_size))
    for pat in SCAN_GLOBS:
        for p in sorted(r.glob(pat)):
            try:
                st = p.stat()
            except OSError:
                # 为何可以吞：签名是**失效触发器**，不是判据——glob 在列举与 stat 之间撞上
                # 并发删除（本仓多会话共享工作区）时少一个触发器只会让下次多扫一遍，
                # 不会漏报；缺件由 build() 的符号表如实少给，不走这里。
                continue
            rows.append((p.relative_to(r).as_posix(), st.st_mtime_ns, st.st_size))
    return tuple(sorted(rows))


def build(root: str = ".", sig: Optional[Tuple[Tuple[str, int, int], ...]] = None) -> SymbolIndex:
    """扫描仓库真源 → SymbolIndex。缺 registry.json 时仍给文件面符号（尽力而为，不裸崩）。

    `sig` 可由调用方传入**已算好的**面孔径签名（服务端刚扫过就该复用）——否则这里会再扫一遍，
    实测每次 119.5 ms；长驻会话的首次请求因此白付一倍代价。
    """
    r = Path(root)
    idx = SymbolIndex(root)
    reg = _read_json(r / REGISTRY_REL) or {}
    out: List[Dict[str, Any]] = []
    _layers(reg, out)
    _events(reg, r, out)
    _modules(r, reg, out)
    _assets(r, out)
    _user_assets(r, out)
    _pipelines(r, reg, out)
    idx.symbols = out
    idx._rel = _relations(reg, r)
    for sym in out:
        for key in [sym["name"]] + list(sym.get("aliases") or []):
            idx._by_key.setdefault(key, []).append(sym)
    idx.sig = sig if sig is not None else signature(root)
    return idx
