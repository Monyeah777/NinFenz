"""community 仓库盘点（v2.0.x-E5：模块市场雏形深化——可发现 → 可装载）。

E5 承接 E4（方案 21）：zone_g 从「本地已装检索」扩到「community 仓库可发现 +
一键装载入库」。本模块盘点仓库内已检出的 community/* 四包（校园 P02/西幻 P03/
轻混 P04/通用 P05）的 modules + pipelines：

- catalog(store) -> list[CommunityItem]：盘点全部可装载项 + 已装判定
  （module: store.get_module 命中；pipeline: pipelines cache 含 id）。
- install_module(store, item)：parse community/<pkg>/modules/*.md →
  Store.save_module 装入用户工作区（~/.NinFenz/modules），幂等。
- install_pipeline(store, item)：与 pipelines cache 按 id merge 去重 → save。
- load_community_module / load_community_pipeline：只读源正文加载（I5：从源包
  parse，不复制进任何包目录）。

边界（I5 单一真相源）：本模块与 E3 composer.references 只读引用正交——references
是组合包跨包引用「源包模块正文运行时只读入装配」；本模块是用户把 community 包自带
模块「安装进自己的桌面工作区」（等同 seed_from_repo 导入官方核心/zone_g 目录导入
第三方模块的既有模式）。只读源永不写 community/ 目录。
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from itertools import islice
from pathlib import Path
from typing import List, Optional

from .models import CATEGORIES, Module, Pipeline
from .storage import Store


@dataclass
class CommunityItem:
    """盘点单条（轻量元数据，对齐 retriever.Hit）。"""
    kind: str                # community_module / community_pipeline
    pkg: str                 # 来源包名（校园情感领域包…）
    ref: str                 # full_id（情感类:M55）/ pipeline id（P02）
    name: str
    layer: str = ""          # 仅 module
    installed: bool = False  # 已装判定（module: store 命中；pipeline: cache 含 id）


_MODULE_HEAD = re.compile(
    r"#\s*模块\s*([A-Za-z\u4e00-\u9fff]+)?:?(M?\d+)\s*[·.、\-]?\s*(.+)")
_PIPELINE_HEAD = re.compile(r"#\s*管线\s+(P\d+)\s*[·.、\-]?\s*(.+)")
_CATEGORY = re.compile(r"类别\s*[:：]\s*([^｜|\s]+)")
_MOUNT = re.compile(r"挂载点\s*[:：]\s*(P\d\d)")
_YAML_LAYER = re.compile(r"(?m)^\s*layer\s*:\s*(P\d\d)\s*$")
_YAML_NAME = re.compile(r"(?m)^\s+name\s*:\s*(.+?)\s*$")
_META_CACHE: dict = {}
_PIPE_META_CACHE: dict = {}


def _read_head(path: Path, limit: int = 40) -> str:
    """只读文件头（元数据提取用，避免 catalog 逐件全文解析）。"""
    with open(path, encoding="utf-8", errors="replace") as fh:
        return "".join(islice(fh, limit))


def light_module_meta(path: Path) -> Optional[tuple[str, str, str]]:
    """模块头 → (full_id, name, layer)；不识别返回 None（调用方回退完整 parse）。"""
    try:
        st = path.stat()
    except OSError:
        # 无法 stat 的元数据件按未识别处理，调用方会回退完整解析并报告缺口。
        return None
    cache_key = (str(path), st.st_mtime_ns, st.st_size)
    if cache_key in _META_CACHE:
        return _META_CACHE[cache_key]
    try:
        head = _read_head(path)
    except OSError:
        # 读不到文件头时不做猜测；完整解析路径会给出可诊断错误。
        return None
    title = next((ln for ln in head.splitlines() if ln.startswith("# ")), "")
    match = _MODULE_HEAD.match(title)
    if not match:
        result = None
    else:
        prefix = match.group(1) or ""
        num = "M" + match.group(2).lstrip("M").rjust(2, "0")
        cat_map = {c.rstrip("类"): c for c in CATEGORIES}
        cat_raw = _CATEGORY.search(head)
        if cat_raw:
            raw = cat_raw.group(1).strip().rstrip("类")
            category = cat_map.get(raw, raw + "类")
        else:
            category = cat_map.get(prefix, "通用类")
        mount = _MOUNT.search(head) or _YAML_LAYER.search(head)
        layer = mount.group(1) if mount else "P40"
        result = ("%s:%s" % (category, num), match.group(3).strip(), layer)
    if len(_META_CACHE) >= 4096:
        _META_CACHE.clear()
    _META_CACHE[cache_key] = result
    return result


def light_pipeline_meta(path: Path) -> Optional[tuple[str, str]]:
    """管线头 → (id, name)；不识别返回 None（调用方回退完整 parse）。"""
    try:
        st = path.stat()
    except OSError:
        # 无法 stat 的管线件按未识别处理，由调用方回退完整解析。
        return None
    cache_key = (str(path), st.st_mtime_ns, st.st_size)
    if cache_key in _PIPE_META_CACHE:
        return _PIPE_META_CACHE[cache_key]
    try:
        head = _read_head(path, 30)
    except OSError:
        # 读不到文件头时不做猜测；完整解析路径会给出可诊断错误。
        return None
    title = next((ln for ln in head.splitlines() if ln.startswith("# ")), "")
    match = _PIPELINE_HEAD.match(title)
    if match:
        name = match.group(2).strip()
        yaml_name = _YAML_NAME.search(head)
        if yaml_name:
            name = yaml_name.group(1).strip().strip("'\"")
        result = (match.group(1), name)
    else:
        result = None
    if len(_PIPE_META_CACHE) >= 1024:
        _PIPE_META_CACHE.clear()
    _PIPE_META_CACHE[cache_key] = result
    return result


def _community_root() -> Optional[Path]:
    """定位仓库 community/ 根（复用 registry_loader.Registry._community_root）。"""
    from .registry_loader import Registry
    return Registry._community_root()


def _package_dirs() -> List[Path]:
    root = _community_root()
    if root is None:
        return []
    return sorted(d for d in root.iterdir()
                  if d.is_dir() and not d.name.startswith("."))


def _pkg_files(cat: str, pkg: str, sub: str, cache: dict | None = None) -> list[Path]:
    """包内某子目录的件；cache 为**单次 catalog 调用内**复用表（§23.34：不加则 93k 次 glob）。"""
    key = (cat, pkg, sub)
    if cache is not None and key in cache:
        return cache[key]
    from .package_index import files_under
    root = _community_root()
    out = files_under(str(root.parent), cat,
                      "community/%s/%s/" % (pkg, sub)) if root else []
    if cache is not None:
        cache[key] = out
    return out


def _pipeline_ids_in_cache(store: Store) -> set:
    raw = store.load_cache("pipelines")
    ids: set = set()
    if isinstance(raw, list):
        for d in raw:
            if isinstance(d, dict) and d.get("id"):
                ids.add(str(d["id"]))
    return ids


def _module_file(pkg_dir: Path, module_ref: str,
                 files: list[Path] | None = None) -> Path | None:
    """在包 modules/ 目录定位 <id>_*.md（files：已列好的文件表，可省）。"""
    num = str(module_ref).split(":")[-1]
    for f in (files if files is not None
              else _pkg_files("community-modules", pkg_dir.name, "modules")):
        if f.name.startswith(num + "_") or f.stem == num:
            return f
    return None


def load_community_module(pkg: str, full_id: str,
                          files: list[Path] | None = None) -> Module | None:
    """只读加载 community/<pkg>/modules 模块正文（files：已列表，可省）。"""
    from .parser import parse_module
    root = _community_root()
    if root is None:
        return None
    pkg_dir = root / pkg
    f = _module_file(pkg_dir, full_id, files=files)
    if f is None:
        return None
    try:
        module = parse_module(f.read_text(encoding="utf-8"))
        try:
            module.source_path = f.relative_to(root).as_posix()
        except ValueError:
            module.source_path = ""
        return module
    except Exception:  # 件不可读/不可解析 ⇒ None（调用方据此报「不可用」）
        return None


def load_community_pipeline(pkg: str, pid: str,
                            files: list[Path] | None = None) -> Pipeline | None:
    """只读加载 community/<pkg>/pipelines 管线（files 同 load_community_module）。"""
    from .pipeline_loader import load_pipeline_file
    root = _community_root()
    if root is None:
        return None
    for f in (files if files is not None
              else _pkg_files("community-pipelines", pkg, "pipelines")):
        try:
            pl = load_pipeline_file(f)
        except Exception:  # nosec B110/B112 —— 尽力而为：跳过不可读/不可解析项；该类缺口由对应门禁与 AUD-0016 静默跳过清单另行报出
            continue
        if pl is not None and pl.id == pid:
            return pl
    return None


# ---------------------------------------------------------------- 盘点
def catalog(store: Store) -> List[CommunityItem]:
    """盘点 community 四包全部模块 + 管线，附已装判定。

    module 已装 = 本地已装模块中存在同 full_id（一次 list_modules 建索引
    O(N)，避免逐件 get_module 的内部全目录列举 O(N²)）；pipeline 已装 =
    pipelines cache 含该 id。parse 失败的单件跳过（不静默吞——catalog 不抛，
    坏文件只影响自身；合规包不应触发，若出现需人工查）。
    """
    from .models import fid_key
    items: List[CommunityItem] = []
    installed_pipes = _pipeline_ids_in_cache(store)
    installed_mods = {fid_key(m.full_id) for m in store.list_modules()}
    files_cache: dict = {}          # 单次调用内复用（见 _pkg_files 说明）
    for pkg_dir in _package_dirs():
        pkg = pkg_dir.name
        if (pkg_dir / "modules").is_dir():
            mod_files = _pkg_files("community-modules", pkg, "modules", cache=files_cache)
            for f in mod_files:
                meta = light_module_meta(f)
                if meta is None:
                    # 非标准头：回退完整 parse（保持既有兼容面）
                    try:
                        from .parser import parse_module
                        m = parse_module(f.read_text(encoding="utf-8"))
                    except (OSError, ValueError, TypeError, UnicodeError, KeyError):
                        # 坏管线件不进入社区目录；对应门禁会单独报告解析失败。
                        continue
                    full_id, name, layer = m.full_id, m.name, m.layer
                else:
                    full_id, name, layer = meta
                installed = fid_key(full_id) in installed_mods
                items.append(CommunityItem(
                    kind="community_module", pkg=pkg, ref=full_id,
                    name=name, layer=layer, installed=installed))
        if (pkg_dir / "pipelines").is_dir():
            for f in _pkg_files("community-pipelines", pkg, "pipelines", cache=files_cache):
                meta = light_pipeline_meta(f)
                if meta is None:
                    try:
                        from .pipeline_loader import load_pipeline_file
                        pl = load_pipeline_file(f)
                    except (OSError, ValueError, TypeError, UnicodeError, KeyError):
                        # 坏管线件不进入社区目录；对应门禁会单独报告解析失败。
                        continue
                    if pl is None:
                        continue
                    pid, name = pl.id, pl.name
                else:
                    pid, name = meta
                items.append(CommunityItem(
                    kind="community_pipeline", pkg=pkg, ref=pid,
                    name=name, installed=pid in installed_pipes))
    return items


# ---------------------------------------------------------------- 装载
def install_module(store: Store, item: CommunityItem) -> bool:
    """把盘点模块装入用户工作区（幂等：已装判定命中即 True 不重复写）。"""
    if item.kind != "community_module":
        return False
    if store.get_module(item.ref) is not None:
        return True
    m = load_community_module(item.pkg, item.ref)
    if m is None:
        return False
    try:
        store.save_module(m)
        return True
    except Exception:  # 安装失败 ⇒ False（调用方据返回值报失败）
        return False


def install_pipeline(store: Store, item: CommunityItem) -> bool:
    """把盘点管线并入 pipelines cache（按 id merge 去重，不覆盖既有管线）。"""
    if item.kind != "community_pipeline":
        return False
    pl = load_community_pipeline(item.pkg, item.ref)
    if pl is None:
        return False
    raw = store.load_cache("pipelines")
    cur: list = list(raw) if isinstance(raw, list) else []
    seen = set()
    merged = []
    for d in cur:
        if isinstance(d, dict) and d.get("id"):
            if d["id"] in seen:
                continue
            seen.add(d["id"])
            merged.append(d)
        else:
            merged.append(d)   # 非标准条目原样保留
    if pl.id not in seen:
        merged.append(pl.to_json())
    store.save_cache("pipelines", merged)
    return True
