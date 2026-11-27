"""core.lsp 私有实现分片 2/4（对外只经 core.lsp 门面导入）：INDEX_TTL_S、_LspServerPart1 等"""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from core import autofix, nf_language
from core.lsp_doc import (
    diagnose,
    folding_ranges,
    outline,
    prefix_before,
    text_edits,
    u16_col,
    word_span,
)

from ._part1 import (
    COMPLETION_KIND,
    M_CODE_ACTION,
    M_COMPLETION,
    M_DEFINITION,
    M_DOCUMENT_SYMBOL,
    M_FOLDING_RANGE,
    M_HOVER,
    M_REFERENCES,
    M_WORKSPACE_SYMBOL,
    path_to_uri,
    uri_to_path,
)

#: 索引签名复查的 TTL（秒）：同一窗口内复用索引，避免每请求都逐件 stat（实测 119.5 ms/次）
INDEX_TTL_S = 1.0


class _LspServerPart1:

    def __init__(self, root: str = ".", today: str = "", explicit_root: bool = False):
        self.root = os.path.abspath(root or ".")
        #: 启动根：initialize 采纳 rootUri 时的**上界**（客户端不得把会话根搬到它之外）。
        self._launch_root = self.root
        self.today = today
        self.explicit_root = explicit_root
        self.docs: Dict[str, Dict[str, str]] = {}
        self.client_caps: Dict[str, Any] = {}
        self.shutting_down = False
        self.initialized = False
        self._index: Optional[nf_language.SymbolIndex] = None
        self._sig_at = 0.0

    # ---- 索引：惰性 + 面孔径签名失效（长驻会话不需要重启就能看到新件）
    def invalidate(self) -> None:
        """强制下一次取索引时重扫签名（客户端**显式**告知仓库件变了的场合用，如 didSave）。"""
        self._sig_at = 0.0

    def symbols(self) -> nf_language.SymbolIndex:
        """NF 符号表（TTL 内复用；过期即重算签名，变了才重建）。

        为什么要有 TTL（2026-10-08 本机实测）：签名要对**全部扫描面**（731 件）逐件 stat，
        实测 **119.5 ms/次**——而补全/悬停/跳定义每个请求都要取一次索引，实测补全 158 ms/请求。
        编辑器里那就是「每敲一个字卡一下」。加 TTL 后同一窗口内复用：索引刷新最多滞后一个
        TTL，而 didSave（磁盘件真变了）会 invalidate() 强制下次重扫——**正确性不降**，
        只是把「每次请求都问一遍仓库变没变」换成「每 TTL 问一遍」。
        """
        now = time.monotonic()
        if self._index is not None and (now - self._sig_at) < INDEX_TTL_S:
            return self._index
        sig = nf_language.signature(self.root)
        self._sig_at = now
        if self._index is None or self._index.sig != sig:
            self._index = nf_language.build(self.root, sig)   # 复用刚扫的签名，不再扫第二遍
        return self._index

    def _resolve_within_root(self, path: str) -> str:
        """客户端给的路径 → **根内**绝对路径；不在根内返回空串（拒绝）。

        审计 X2（P1）的修法落点：此前 `_text_of` 对客户端 uri 裸 `open()`，工作区外任意
        文件都能被读出并**整文件回给客户端**（CWE-22 → CWE-200）。边界 = 当前会话根，
        realpath 归一是关键（`../`、符号链接、百分号编码都必须在归一后判）。
        """
        raw = str(path or "")
        if not raw:
            return ""
        try:
            root_real = Path(self.root).resolve()
            p = Path(raw)
            target = p.resolve() if p.is_absolute() else (root_real / p).resolve()
        except (OSError, ValueError):
            return ""
        return str(target) if target == root_real or root_real in target.parents else ""

    def _text_of(self, uri: str) -> str:
        doc = self.docs.get(uri)
        if doc:
            return doc.get("text", "")
        path = self._resolve_within_root(uri_to_path(uri))
        if not path:                       # 根外/不可解析：空正文（绝不把文件内容外带）
            return ""
        try:
            with open(path, encoding="utf-8") as fh:
                return fh.read()
        except OSError:
            return ""

    def _rel(self, path: str) -> str:
        try:
            return os.path.relpath(os.path.abspath(path), self.root).replace("\\", "/")
        except ValueError:                     # 跨盘符（Windows）——退化为绝对路径，不裸崩
            return path.replace("\\", "/")

    def _publish(self, uri: str, clear: bool = False) -> Dict[str, Any]:
        path = (self.docs.get(uri) or {}).get("path") or uri_to_path(uri)
        text = "" if clear else self._text_of(uri)
        diags = [] if clear else diagnose(self._rel(path), text, self.root)
        return {"jsonrpc": "2.0", "method": "textDocument/publishDiagnostics",
                "params": {"uri": uri, "diagnostics": diags}}

    def _hierarchical(self) -> bool:
        ds = ((self.client_caps.get("textDocument") or {}).get("documentSymbol") or {})
        return bool(ds.get("hierarchicalDocumentSymbolSupport"))

    # ---- 各类请求
    def _line_at(self, uri: str, line_no: int) -> Tuple[List[str], int, str]:
        """文档行快照 → (全部行, 收敛后行号, 该行正文)；行号越界收敛到文末那一行。"""
        lines = self._text_of(uri).split("\n")
        ln = min(max(0, line_no), max(0, len(lines) - 1))
        return lines, ln, (lines[ln] if lines else "")

    def _completion(self, params: Dict[str, Any]) -> Dict[str, Any]:
        uri = (params.get("textDocument") or {}).get("uri", "")
        pos = params.get("position") or {}
        _lines, _ln, line = self._line_at(uri, int(pos.get("line", 0) or 0))
        prefix = prefix_before(line, int(pos.get("character", 0) or 0))
        items = []
        for sym in self.symbols().complete(prefix):
            items.append({"label": sym["name"], "kind": COMPLETION_KIND.get(sym["kind"], 1),
                          "detail": sym["detail"], "documentation": {"kind": "markdown",
                                                                     "value": sym["doc"]},
                          "sortText": "%d_%s" % (nf_language.KINDS.index(sym["kind"]),
 sym["name"])})
        return {"isIncomplete": False, "items": items}

    def _hover(self, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        uri = (params.get("textDocument") or {}).get("uri", "")
        pos = params.get("position") or {}
        lines, ln, cur = self._line_at(uri, int(pos.get("line", 0) or 0))
        tok, start, end = word_span(cur, int(pos.get("character", 0) or 0))
        hits = self.symbols().resolve_all(tok) if tok else []
        if not hits:
            return None
        blocks = []
        for sym in hits:
            blocks.append("**%s**（%s）\n\n%s\n\n定义：`%s`" % (
                sym["name"], sym["kind"], sym["doc"], sym["path"]))
        if len(hits) > 1:
            blocks.insert(0, "> 有 %d 个同名符号（歧义：跳定义按失败关闭处理）" % len(hits))
        return {"contents": {"kind": "markdown", "value": "\n\n---\n\n".join(blocks)},
                "range": {"start": {"line": ln, "character": u16_col(lines[ln], start)},
                          "end": {"line": ln, "character": u16_col(lines[ln], end)}}}

    def _definition(self, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        uri = (params.get("textDocument") or {}).get("uri", "")
        pos = params.get("position") or {}
        _lines, _ln, cur = self._line_at(uri, int(pos.get("line", 0) or 0))
        tok, _s, _e = word_span(cur, int(pos.get("character", 0) or 0))
        sym = self.symbols().resolve(tok) if tok else None
        if not sym:
            return None
        target = os.path.join(self.root, sym["path"])
        tl = int(sym.get("line", 0) or 0)
        return {"uri": path_to_uri(target),
                "range": {"start": {"line": tl,
 "character": 0},
 "end": {"line": tl,
 "character": 0}}}

    def _document_symbols(self, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        uri = (params.get("textDocument") or {}).get("uri", "")
        tree = outline(self._text_of(uri))
        if self._hierarchical():
            return tree
        flat: List[Dict[str, Any]] = []

        def walk(nodes):
            for n in nodes:
                flat.append({"name": n["name"], "kind": n["kind"], "location": {"uri": uri,
                                                                                "range": n["range"]}})
                walk(n.get("children") or [])
        walk(tree)
        return flat

    def _workspace_symbols(self, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        q = str(params.get("query") or "")
        out = []
        for sym in self.symbols().all_symbols():
            if q and q not in sym["name"] and not any(q in a for a in sym.get("aliases") or []):
                continue
            out.append({"name": sym["name"], "kind": COMPLETION_KIND.get(sym["kind"], 1),
                        "containerName": sym["kind"],
                        "location": {"uri": path_to_uri(os.path.join(self.root, sym["path"])),
                                     "range": {"start": {"line": int(sym.get("line") or 0),
                                                         "character": 0},
                                               "end": {"line": int(sym.get("line") or 0),
                                                       "character": 0}}}})
        return out[:500]

    def _references(self, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """结构化引用 → LSP Location[]（**只认登记关系**；未登记即空表，失败关闭）。

        为什么值得单列（2026-10-08）：NF 的引用是**有登记的**（事件 ↔ 发布/订阅模块、模块 ↔
        挂载层、管线 ← 域包采用），编辑器里「谁引用了这个事件」因此能给出**可解释**的位置；
        若改成全文搜索，只会喷出同名噪声——本仓对「不猜」有明确纪律（同 hover 的歧义口径）。
        `context.includeDeclaration=false` 时去掉与符号自身定义同位置的那条（规范语义）。
        """
        uri = (params.get("textDocument") or {}).get("uri", "")
        pos = params.get("position") or {}
        _lines, _ln, cur = self._line_at(uri, int(pos.get("line", 0) or 0))
        tok, _s, _e = word_span(cur, int(pos.get("character", 0) or 0))
        if not tok:
            return []
        include_decl = bool((params.get("context") or {}).get("includeDeclaration", True))
        decl = self.symbols().resolve(tok)
        decl_key = (decl["path"], int(decl.get("line") or 0)) if decl else None
        out = []
        for ref in self.symbols().references(tok):
            if not include_decl and (ref["path"], int(ref["line"])) == decl_key:
                continue
            out.append({"uri": path_to_uri(os.path.join(self.root, ref["path"])),
                        "range": {"start": {"line": int(ref["line"]), "character": 0},
                                  "end": {"line": int(ref["line"]), "character": 0}}})
        return out

    def _folding_ranges(self, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """折叠区间（标题小节 + 代码围栏）——派生自与大纲同一份标题口径，不新造事实。"""
        uri = (params.get("textDocument") or {}).get("uri", "")
        return folding_ranges(self._text_of(uri))

    def _code_actions(self, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        uri = (params.get("textDocument") or {}).get("uri", "")
        only = ((params.get("context") or {}).get("only") or [])
        if only and "quickfix" not in only:
            return []
        diags = (params.get("context") or {}).get("diagnostics") or []
        rules = sorted({str(d.get("code")) for d in diags if d.get("code") in autofix.RULES})
        if not rules:
            return []
        before = self._text_of(uri)
        after = autofix.apply_rules(before, rules, self.today)
        if after == before:
            return []
        return [{
            "title": "NF：机械修复（%s）" % "、".join(rules),
            "kind": "quickfix",
            "isPreferred": True,
            "diagnostics": [d for d in diags if d.get("code") in rules],
            "edit": {"changes": {uri: text_edits(before, after)}},
        }]


def _error(rid: Any, code: int, message: str) -> Dict[str, Any]:
    """JSON-RPC 错误应答（三种入站拒绝共用一处形状）。"""
    return {"jsonrpc": "2.0", "id": rid, "error": {"code": code, "message": message}}


#: 请求方法 → 处理器（表驱动分派：避免 handle 的线性分支把圈复杂度推过高限）
_REQUESTS: Dict[str, Any] = {
    M_COMPLETION: lambda s, p: s._completion(p),
    M_HOVER: lambda s, p: s._hover(p),
    M_DEFINITION: lambda s, p: s._definition(p),
    M_DOCUMENT_SYMBOL: lambda s, p: s._document_symbols(p),
    M_WORKSPACE_SYMBOL: lambda s, p: s._workspace_symbols(p),
    M_REFERENCES: lambda s, p: s._references(p),
    M_FOLDING_RANGE: lambda s, p: s._folding_ranges(p),
    M_CODE_ACTION: lambda s, p: s._code_actions(p),
}
