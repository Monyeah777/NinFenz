"""core.repo_index 私有实现分片 2/2（对外只经 core.repo_index 门面导入）：RepoIndex 等"""

from __future__ import annotations

import urllib.parse as _up
from pathlib import Path
from typing import Any, Dict, List, Optional

from core import json_doc

from ._part1 import _glob, _RepoIndexPart1, _stat, md_title, read_text, safe_path


class RepoIndex(_RepoIndexPart1):
    """单个仓库根上的只读索引（懒构建、可失效）。"""

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
            path = safe_path(self.root, rel)
            try:
                text = read_text(self.root, rel)
            except (OSError, UnicodeError, ValueError):
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
        path = safe_path(self.root, rel)

        def build():
            return json_doc.load(path, dict, what=rel)

        return self._family("registry", build, lambda: _stat(path))

    # -------------------------------------------------------------- docs
    def _doc_paths(self) -> List[str]:
        root = self.root
        out = [rel for rel in _glob(root, ("*.md",))
               if Path(rel).name.startswith(("0", "4")) or Path(rel).name[:2].isdigit()]
        out.extend(_glob(root, ("docs/*.md", "community/*/README.md")))
        return out

    def _build_docs(self) -> List[Dict[str, Any]]:
        out = []
        for rel in self._doc_paths():
            path = safe_path(self.root, rel)
            try:
                text = read_text(self.root, rel)
            except (OSError, UnicodeError, ValueError):
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
        if kind != "asset" and len(parts) != 5:
            raise KeyError(uri)
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
            if len(parts) != 6:
                raise KeyError(uri)
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
