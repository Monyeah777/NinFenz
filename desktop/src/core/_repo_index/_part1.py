"""core.repo_index 私有实现分片 1/2（对外只经 core.repo_index 门面导入）：DEFAULT_TTL 等"""

from __future__ import annotations

import re
import time
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

from core import paths as _paths

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


def safe_path(root: str | Path, rel: str) -> Path:
    """把仓库相对路径解析为 realpath；越根或符号链接逃逸一律抛 PathEscapeError。"""
    return Path(_paths.validate_path(str(root), str(rel)))


def _rel(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def _glob(root: Path, patterns: Iterable[str]) -> List[str]:
    out: List[str] = []
    for pat in patterns:
        for p in sorted(root.glob(pat)):
            try:
                target = safe_path(root, _rel(root, p))
            except (_paths.PathEscapeError, OSError, ValueError):
                # 符号链接/连接点指向仓外时，索引不得把它登记成可读资源。
                continue
            if target.is_file():
                out.append(_rel(root, p))
    return out


def _keys_of_file(path: Path) -> List[str]:
    """资产文件内登记的键（文件名令牌 ∪ 正文键声明）。与 mcp_runtime 同口径。"""
    keys = set(_ASSET_TOKEN.findall(path.stem))
    try:
        with path.open("rb") as fh:
            head = fh.read(6000).decode("utf-8")
    except (OSError, UnicodeDecodeError):
        return sorted(keys)
    keys.update(re.findall(r"`([A-Z][A-Z0-9_]{2,})`", head))
    keys.update(re.findall(r"\"([A-Z][A-Z0-9_]{2,})\"\s*:", head))
    keys.update(re.findall(r"##\s*([A-Z][A-Z0-9_]{2,})", head))
    return sorted(keys)


#: 单件仓库正文读取上限（字节）：MCP/索引都是请求级读取，不允许外来大文件无界入内存。
MAX_RESOURCE_BYTES = 8 << 20


def read_text(root: str | Path, rel: str) -> str:
    """仓库相对路径 → 有界 UTF-8 文本；越根、超大与非 UTF-8 一律 fail-closed。"""
    path = safe_path(root, rel)
    with path.open("rb") as fh:
        raw = fh.read(MAX_RESOURCE_BYTES + 1)
    if len(raw) > MAX_RESOURCE_BYTES:
        raise ValueError(f"仓库文本超过上限 {MAX_RESOURCE_BYTES} 字节：{rel}"
                         "（修复指引：拆分文件，或改用支持分页的产出面）")
    text = raw.decode("utf-8")
    return text.replace("\r\n", "\n").replace("\r", "\n")


class _RepoIndexPart1:

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
        try:
            return _stat(safe_path(self.root, rel)) == entry.get("stat")
        except (_paths.PathEscapeError, OSError, ValueError):  # 失效条目按缺失重建
            return False

    def _validate_all(self, name: str, build: Callable[[], Any],
                      stamp: Callable[[], Any]) -> Any:
        data = self._family(name, build, stamp)
        if any(not self._entry_valid(e) for e in data):
            return self._rebuild(name, build, stamp)
        return data

    # ------------------------------------------------------------ modules
    def _module_paths(self) -> List[str]:
        from core import conformance_scan as csc
        out = []
        for p in csc._module_docs(str(self.root)):
            try:
                target = safe_path(self.root, _rel(self.root, Path(p)))
            except (_paths.PathEscapeError, OSError, ValueError):  # 越根候选不进入只读索引
                continue
            if target.is_file():
                out.append(_rel(self.root, Path(p)))
        return sorted(out)

    def _build_modules(self) -> List[Dict[str, Any]]:
        from core import conformance_scan as csc
        out: List[Dict[str, Any]] = []
        for rel in self._module_paths():
            path = safe_path(self.root, rel)
            try:
                text = read_text(self.root, rel)
            except (OSError, UnicodeError, ValueError):
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
            path = safe_path(self.root, rel)
            try:
                text = read_text(self.root, rel)
            except (OSError, UnicodeError, ValueError):
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
            path = safe_path(self.root, rel)
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
        from core.library_entries import read_entry
        rows = []
        for rel in self._library_paths():
            path = safe_path(self.root, rel)
            if path.stat().st_size > MAX_RESOURCE_BYTES:
                continue
            rows.append(read_entry(str(path)))
        for row in rows:
            row["path"] = _rel(self.root, Path(row["path"]))
        for row in rows:
            row["stat"] = _stat(safe_path(self.root, row["path"]))
        rows.sort(key=lambda e: e["id"])
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
