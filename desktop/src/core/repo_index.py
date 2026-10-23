"""仓库只读索引池（RepoIndex）：把 MCP 工具的「每次全仓扫描」收敛为一次懒构建 + O(1) 查询。

设计（2026-10-23）：

- **按 family 懒构建**：modules / pipelines / assets / library / patterns / registry / docs
  各自在第一次被用到时建立；`McpRuntime.__init__` 不再全量扫仓库。
- **O(1) 寻址**：id / stem / key → 条目的倒排表；同一 family 内不再每次 glob/read。
- **失效**：
  * 成员变更：family 的目录清单 stamp（只列目录、不读正文）每 `TTL` 秒复核一次；
  * 内容变更：每次取用条目时 `stat(mtime_ns,size)` 校验，命中变化即重建该 family；
  * 读取失败/文件消失：视为失效并重建。
- **只读**：本模块不写仓库、不起进程；所有读取都走 `Path.read_text`/`json_doc.load`。

边界：索引是**进程内**的；跨进程/守护的持久化由调用方决定（daemon 已有自己的常驻层）。
"""
from __future__ import annotations

import re
import time
import urllib.parse as _up
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

from core import json_doc

DEFAULT_TTL = 2.0
_MODULE_TITLE = re.compile(r"#\s*模块\s+([^\s·]+)")
_ASSET_TOKEN = re.compile(r"[A-Z][A-Z0-9_]*")


def md_title(text: str) -> str:
    """首个 markdown 标题（与 mcp_runtime._md_title 同口径）。"""
    for line in text.splitlines():
        if line.startswith("#"):
            return line.lstrip("# ").strip()
    return ""


def _stat(path: Path) -> Optional[Tuple[int, int]]:
    try:
        st = path.stat()
    except OSError:
        # stat 失败等价于条目缺失；索引失效检查会触发重建或未命中。
        return None
    return (int(st.st_mtime_ns), int(st.st_size))


def _rel(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def _glob(root: Path, patterns: Iterable[str]) -> List[str]:
    out: List[str] = []
    for pat in patterns:
        out.extend(_rel(root, p) for p in sorted(root.glob(pat)) if p.is_file())
    return out


def _keys_of_file(path: Path) -> List[str]:
    """资产文件内登记的键（文件名令牌 ∪ 正文键声明）。与 mcp_runtime 同口径。"""
    keys = set(_ASSET_TOKEN.findall(path.stem))
    try:
        head = path.read_text(encoding="utf-8")[:6000]
    except OSError:
        return sorted(keys)
    keys.update(re.findall(r"`([A-Z][A-Z0-9_]{2,})`", head))
    keys.update(re.findall(r"\"([A-Z][A-Z0-9_]{2,})\"\s*:", head))
    keys.update(re.findall(r"##\s*([A-Z][A-Z0-9_]{2,})", head))
    return sorted(keys)


class RepoIndex:
    """单个仓库根上的只读索引（懒构建、可失效）。"""

    def __init__(self, root: Path, ttl: float = DEFAULT_TTL):
        self.root = Path(root).resolve()
        self.ttl = ttl
        self._families: Dict[str, Dict[str, Any]] = {}

    # ------------------------------------------------------------ 通用层
    def _family(self, name: str, build: Callable[[], Any],
                stamp: Optional[Callable[[], Any]]) -> Any:
        fam = self._families.get(name)
        now = time.monotonic()
        if fam is None:
            data = build()
            fam = self._families[name] = {
                "data": data, "stamp": stamp() if stamp is not None else None, "at": now}
            return data
        if stamp is not None and now - fam["at"] >= self.ttl:
            current = stamp()
            if current != fam["stamp"]:
                fam["data"] = build()
                fam["stamp"] = current
            fam["at"] = now
        return fam["data"]

    def _rebuild(self, name: str, build: Callable[[], Any],
                 stamp: Callable[[], Any]) -> Any:
        data = build()
        self._families[name] = {"data": data, "stamp": stamp(), "at": time.monotonic()}
        return data

    def _entry_valid(self, entry: Dict[str, Any]) -> bool:
        rel = entry.get("rel") or entry.get("path")
        if not rel:
            return True
        return _stat(self.root / rel) == entry.get("stat")

    def _validate_all(self, name: str, build: Callable[[], Any],
                      stamp: Callable[[], Any]) -> Any:
        data = self._family(name, build, stamp)
        if any(not self._entry_valid(e) for e in data):
            return self._rebuild(name, build, stamp)
        return data

    # ------------------------------------------------------------ modules
    def _module_paths(self) -> List[str]:
        from core import conformance_scan as csc
        return sorted(_rel(self.root, Path(p)) for p in csc._module_docs(str(self.root))
                     if Path(p).is_file())

    def _build_modules(self) -> List[Dict[str, Any]]:
        from core import conformance_scan as csc
        out: List[Dict[str, Any]] = []
        for rel in self._module_paths():
            path = self.root / rel
            try:
                text = path.read_text(encoding="utf-8")
            except OSError:
                # 索引不收录不可读模块；MCP 读取会按未命中返回明确错误。
                continue
            parsed = csc._fence_yaml(text, "machine_contract")
            mc = parsed.get("machine_contract") if isinstance(parsed, dict) else None
            mid = mc.get("id") if isinstance(mc, dict) else None
            match = _MODULE_TITLE.search(text)
            out.append({"rel": rel, "mc_id": mid,
                        "title_id": match.group(1).strip() if match else None,
                        "text": text, "has_contract": bool(mid),
                        "stat": _stat(path)})
        out.sort(key=lambda e: str(e["rel"]))
        return out

    def modules(self) -> List[Dict[str, Any]]:
        return self._validate_all("modules", self._build_modules, self._module_paths)

    def module(self, module_id: str) -> Optional[Dict[str, Any]]:
        req = str(module_id).strip()
        def find(data):
            exact = [e for e in data if req in (e["mc_id"], e["title_id"])]
            if exact:
                return exact[0]
            if req.isdigit():
                suffix = [e for e in data
                          if any(isinstance(x, str) and x.split(":", 1)[-1] == req
                                 for x in (e["mc_id"], e["title_id"]))]
                if len(suffix) == 1:
                    return suffix[0]
                if len(suffix) > 1:
                    raise ValueError(
                        "module_id 存在多个同号限定（如 通用:M10 / 生存:M10）——请用限定 id"
                        "（修复指引：先 registry_search 查全限定 id 再重试）")
            return None

        data = self._family("modules", self._build_modules, None)
        hit = find(data)
        if hit is not None and self._entry_valid(hit):
            return dict(hit)
        # 未命中 / 命中但内容已变：重建一次
        data = self._rebuild("modules", self._build_modules, self._module_paths)
        hit = find(data)
        if hit is not None:
            return dict(hit)
        return None

    # ---------------------------------------------------------- pipelines
    def _pipeline_paths(self) -> List[str]:
        return _glob(self.root, ("03_管线库/*.md", "community/*/pipelines/*.md"))

    def _build_pipelines(self) -> List[Dict[str, Any]]:
        out = []
        for rel in self._pipeline_paths():
            path = self.root / rel
            try:
                text = path.read_text(encoding="utf-8")
            except OSError:
                # 索引不收录不可读管线；读取会按未命中返回明确错误。
                continue
            out.append({"id": path.name.split("_", 1)[0], "rel": rel,
                        "title": md_title(text), "text": text,
                        "stat": _stat(path)})
        return out

    def pipelines(self) -> List[Dict[str, Any]]:
        return self._validate_all("pipelines", self._build_pipelines, self._pipeline_paths)

    def pipeline(self, pipeline_id: str) -> Optional[Dict[str, Any]]:
        req = str(pipeline_id).strip()
        data = self._family("pipelines", self._build_pipelines, None)
        for e in data:
            if e["id"] == req:
                if self._entry_valid(e):
                    return dict(e)
                break
        data = self._rebuild("pipelines", self._build_pipelines, self._pipeline_paths)
        for e in data:
            if e["id"] == req:
                return dict(e)
        return None

    # ------------------------------------------------------------- assets
    def _asset_paths(self, package: str = "") -> List[str]:
        pats = (["community/%s/assets/*.md" % package] if package
                else ["community/*/assets/*.md", "05_资产库/用户自定义/*.md"])
        return [rel for rel in _glob(self.root, pats)
                if not rel.endswith("/README.md") and rel != "README.md"]

    def _build_assets(self) -> List[Dict[str, Any]]:
        out = []
        for rel in self._asset_paths():
            path = self.root / rel
            keys = _keys_of_file(path)
            if not keys:
                continue
            package = rel.split("/")[1] if rel.startswith("community/") else "官方"
            out.append({"package": package, "rel": rel, "file": rel,
                        "keys": keys, "stat": _stat(path)})
        return out

    def assets(self, package: str = "") -> List[Dict[str, Any]]:
        data = self._validate_all("assets", self._build_assets,
                                  lambda: self._asset_paths())
        if package:
            data = [e for e in data if e["package"] == package]
        return [{"package": e["package"], "file": e["file"], "keys": list(e["keys"])}
                for e in data]

    def asset_matches(self, key: str, package: str = "") -> List[Dict[str, Any]]:
        data = self._family("assets", self._build_assets, None)
        req = str(key).strip()
        out = [e for e in data if req in e["keys"]
               and (not package or e["package"] == package)]
        if not out or any(not self._entry_valid(e) for e in out):
            data = self._rebuild("assets", self._build_assets,
                                 lambda: self._asset_paths())
            out = [e for e in data if req in e["keys"]
                   and (not package or e["package"] == package)]
        return [dict(e) for e in out]

    # ------------------------------------------------------------ library
    def _library_paths(self) -> List[str]:
        return _glob(self.root, ("library/NF-*.md",))

    def _build_library(self) -> Dict[str, Any]:
        from core import library as nflib
        rows = nflib.entries(str(self.root))
        for row in rows:
            row["stat"] = _stat(self.root / row["path"])
        by_id = {str(r["id"]).lower(): r for r in rows}
        index = nflib.build_index(str(self.root), rows=rows)
        return {"rows": rows, "by_id": by_id, "index": index}

    def library(self) -> Dict[str, Any]:
        data = self._family("library", self._build_library, None)
        if any(not self._entry_valid(r) for r in data["rows"]):
            data = self._rebuild("library", self._build_library, self._library_paths)
        return data

    def library_entry(self, entry_id: str) -> Optional[Dict[str, Any]]:
        data = self._family("library", self._build_library, self._library_paths)
        hit = data["by_id"].get(str(entry_id).strip().lower())
        if hit is not None and self._entry_valid(hit):
            return dict(hit)
        data = self._rebuild("library", self._build_library, self._library_paths)
        hit = data["by_id"].get(str(entry_id).strip().lower())
        return dict(hit) if hit is not None else None

    def library_search(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        from core import library as nflib
        data = self._family("library", self._build_library, None)
        out: List[Dict[str, Any]] = []
        for attempt in (0, 1):
            rows = data["rows"]
            by_id = data["by_id"]
            scores: Dict[str, int] = {}
            q_low = str(query).strip().lower()
            for tok in set(nflib._tokens(str(query))):
                for eid, weight in (data["index"].get(tok) or {}).items():
                    scores[eid] = scores.get(eid, 0) + weight
            for row in rows:
                if q_low and q_low in (row.get("text") or "").lower():
                    scores[row["id"]] = scores.get(row["id"], 0) + 2
            out = []
            stale = False
            for eid, score in sorted(scores.items(), key=lambda kv: (-kv[1], kv[0])):
                hit = by_id.get(str(eid).lower())
                if hit is None:
                    continue
                if not self._entry_valid(hit):
                    stale = True
                    break
                out.append({"id": eid, "score": score,
                            "title": hit["fm"].get("title", eid),
                            "type": hit["fm"].get("type", ""),
                            "status": hit["fm"].get("status", "active"),
                            "path": hit["path"],
                            "description": hit["fm"].get("description", "")})
            if not stale:
                return out[:max(1, min(50, int(limit)))]
            data = self._rebuild("library", self._build_library, self._library_paths)
        return out[:max(1, min(50, int(limit)))]

    # ----------------------------------------------------------- patterns
    def _pattern_paths(self) -> List[str]:
        return _glob(self.root, ("patterns/*/PATTERN.md",))

    def _build_patterns(self) -> List[Dict[str, Any]]:
        from core.library_entries import parse_frontmatter
        out = []
        for rel in self._pattern_paths():
            path = self.root / rel
            try:
                text = path.read_text(encoding="utf-8")
            except OSError:
                # 索引不收录不可读实践包；读取会按未命中返回明确错误。
                continue
            fm, _body = parse_frontmatter(text)
            out.append({"id": path.parent.name, "rel": rel, "text": text,
                        "title": str(fm.get("title") or fm.get("name") or path.parent.name),
                        "status": str(fm.get("status") or "active"),
                        "stat": _stat(path)})
        return out

    def patterns(self) -> List[Dict[str, Any]]:
        return self._validate_all("patterns", self._build_patterns, self._pattern_paths)

    def pattern(self, pattern_id: str) -> Optional[Dict[str, Any]]:
        req = str(pattern_id).strip()
        data = self._family("patterns", self._build_patterns, None)
        for e in data:
            if e["id"] == req:
                if self._entry_valid(e):
                    return dict(e)
                break
        data = self._rebuild("patterns", self._build_patterns, self._pattern_paths)
        for e in data:
            if e["id"] == req:
                return dict(e)
        return None

    # ----------------------------------------------------------- registry
    def registry(self) -> Dict[str, Any]:
        rel = "desktop/src/core/registry.json"
        path = self.root / rel

        def build():
            return json_doc.load(path, dict, what=rel)

        return self._family("registry", build, lambda: _stat(path))

    # -------------------------------------------------------------- docs
    def _doc_paths(self) -> List[str]:
        root = self.root
        out = []
        for p in sorted(root.glob("*.md")):
            if p.name.startswith(("0", "4")) or p.name[:2].isdigit():
                out.append(p.name)
        out.extend(_glob(root, ("docs/*.md", "community/*/README.md")))
        return out

    def _build_docs(self) -> List[Dict[str, Any]]:
        out = []
        for rel in self._doc_paths():
            path = self.root / rel
            try:
                text = path.read_text(encoding="utf-8")
            except OSError:
                # 文档索引只收可读件；不可读件由文档门禁报告。
                continue
            out.append({"path": rel, "title": md_title(text), "stat": _stat(path)})
        return out

    def docs(self) -> List[Dict[str, Any]]:
        return self._validate_all("docs", self._build_docs, self._doc_paths)

    def docs_matching(self, query: str) -> List[Dict[str, Any]]:
        q = str(query)
        return [{"kind": "doc", "path": d["path"], "title": d["title"]}
                for d in self.docs()
                if q in Path(d["path"]).name or q in d["title"]]

    # ----------------------------------------------------------- resources
    def resource_metas(self) -> List[Dict[str, Any]]:
        metas: List[Dict[str, Any]] = []
        for it in self.modules():
            mid = it["mc_id"] or it["title_id"]
            if not mid:
                continue
            rel = it["rel"]
            package = rel.split("/")[1] if rel.startswith("community/") else "官方"
            metas.append({"uri": "nf://repo/module/" + _up.quote(str(mid), safe=""),
                          "name": "模块 %s" % mid, "mimeType": "text/markdown",
                          "package": package, "source": rel})
        for it in self.pipelines():
            rel = it["rel"]
            package = rel.split("/")[1] if rel.startswith("community/") else "官方"
            metas.append({"uri": "nf://repo/pipeline/" + _up.quote(it["id"], safe=""),
                          "name": "管线 %s" % it["id"], "mimeType": "text/markdown",
                          "package": package, "source": rel})
        for it in self.assets():
            for key in it["keys"]:
                metas.append({"uri": "nf://repo/asset/"
                                     + _up.quote(it["package"], safe="") + "/"
                                     + _up.quote(key, safe=""),
                              "name": "资产 %s/%s" % (it["package"], key),
                              "mimeType": "text/markdown",
                              "package": it["package"], "source": it["file"]})
        for e in self.library()["rows"]:
            metas.append({"uri": "nf://repo/library/" + _up.quote(e["id"], safe=""),
                          "name": "馆藏 %s" % e["id"], "mimeType": "text/markdown",
                          "package": "图书馆", "source": e["path"]})
        for it in self.patterns():
            metas.append({"uri": "nf://repo/pattern/" + _up.quote(it["id"], safe=""),
                          "name": "实践包 %s" % it["id"], "mimeType": "text/markdown",
                          "package": "patterns", "source": it["rel"]})
        metas.sort(key=lambda m: m["uri"])
        return metas

    def source_of(self, uri: str) -> str:
        """`nf://repo/<kind>/…` → 仓库相对路径；未知结构抛 KeyError。"""
        parts = str(uri).split("/")
        if len(parts) < 4 or parts[0] != "nf:" or parts[2] != "repo":
            raise KeyError(uri)
        kind = parts[3]
        if kind == "library":
            eid = _up.unquote(parts[4])
            hit = self.library_entry(eid)
            if hit is None:
                raise KeyError(uri)
            return hit["path"]
        if kind == "pattern":
            hit = self.pattern(_up.unquote(parts[4]))
            if hit is None:
                raise KeyError(uri)
            return hit["rel"]
        if kind == "module":
            hit = self.module(_up.unquote(parts[4]))
            if hit is None:
                raise KeyError(uri)
            return hit["rel"]
        if kind == "pipeline":
            hit = self.pipeline(_up.unquote(parts[4]))
            if hit is None:
                raise KeyError(uri)
            return hit["rel"]
        if kind == "asset":
            package = _up.unquote(parts[4])
            key = _up.unquote(parts[5])
            hits = self.asset_matches(key, package)
            if not hits:
                raise KeyError(uri)
            return hits[0]["rel"]
        raise KeyError(uri)


_INDEXES: Dict[str, RepoIndex] = {}
MAX_INDEXES = 16


def get(root: str | Path = ".") -> RepoIndex:
    """按根取进程内单例（同一 root 的 MCP 会话/工具共享同一索引）。"""
    key = str(Path(root).resolve())
    idx = _INDEXES.get(key)
    if idx is None:
        if len(_INDEXES) >= MAX_INDEXES:
            _INDEXES.clear()
        idx = _INDEXES[key] = RepoIndex(Path(root))
    return idx


def clear(root: Optional[str | Path] = None) -> None:
    """清空索引（测试/显式失效用；`root` 为空清全部）。"""
    if root is None:
        _INDEXES.clear()
    else:
        _INDEXES.pop(str(Path(root).resolve()), None)


__all__ = ["RepoIndex", "clear", "get", "md_title"]
