"""core.lsp 私有实现分片 1/4（对外只经 core.lsp 门面导入）：M_INITIALIZE、M_INITIALIZED 等"""

from __future__ import annotations

import os
import re
from pathlib import Path
from urllib.parse import quote, unquote, urlparse

#: LSP 方法名（只实现本模块承诺的面；其余按规范拒/忽略）
M_INITIALIZE = "initialize"


M_INITIALIZED = "initialized"


M_DID_OPEN = "textDocument/didOpen"


M_DID_CHANGE = "textDocument/didChange"


M_DID_SAVE = "textDocument/didSave"


M_DID_CLOSE = "textDocument/didClose"


M_COMPLETION = "textDocument/completion"


M_HOVER = "textDocument/hover"


M_DEFINITION = "textDocument/definition"


M_DOCUMENT_SYMBOL = "textDocument/documentSymbol"


M_WORKSPACE_SYMBOL = "workspace/symbol"


M_REFERENCES = "textDocument/references"


M_FOLDING_RANGE = "textDocument/foldingRange"


M_CODE_ACTION = "textDocument/codeAction"


M_SHUTDOWN = "shutdown"


M_EXIT = "exit"


#: 服务端自述（唯一真相 = 这两个常量；接入面卡 `integrations/lsp/integration.json` 的
#: version 必须与 SERVER_VERSION 一致，由 test_lsp 判据对账——两处各写一遍就会静默漂）。
METHOD_NOT_FOUND = -32601


SERVER_NAME = "nf-lsp"


SERVER_VERSION = "2.7.0"


#: 领域符号种类 → LSP CompletionItemKind / SymbolKind（协议常量，不引入 LSP 依赖）
COMPLETION_KIND = {"module": 9, "asset": 6, "event": 23, "layer": 7, "pipeline": 3}


#: check33 编辑器面判据要求的 initialize 能力键（缺一即红）
_REQUIRED_CAPS = ("positionEncoding", "textDocumentSync", "hoverProvider", "completionProvider",
                  "definitionProvider", "documentSymbolProvider", "workspaceSymbolProvider",
                  "referencesProvider", "foldingRangeProvider", "codeActionProvider")


_FENCE = re.compile(r"^```")


_URI_SAFE = "/:@"


# 注：SEVERITY_WARNING / SYMBOL_KIND / HEADING / WORD 随文档级能力迁到 core/lsp_doc.py——
# 这里不再各留一份（死代码判据 2026-10-08 抓到四处零引用常量，正是「拆完没清场」的痕迹）。

def _within_root(root: str, path: str) -> bool:
    """`path` 是否落在 `root` 内（realpath 包含性；含 root 自身）。

    先 realpath 再判：`../`、符号链接、Windows 大小写都必须在归一后比较——按字符串前缀判
    会被 `root-evil/` 这类兄弟目录骗过（2026-10-10 审计 X2 的同一族教训）。
    """
    try:
        r = Path(root).resolve()
        p = Path(path).resolve()
    except (OSError, ValueError):
        # 归一失败（不存在/不可达/链接循环）⇒ 保守判「不在根内」（fail-closed，宁可拒答）。
        return False
    return p == r or r in p.parents


def uri_to_path(uri: str) -> str:
    """file:// uri → 本地路径（Windows 盘符与 URL 编码均还原）。"""
    parsed = urlparse(uri)
    path = unquote(parsed.path or "")
    if parsed.netloc:
        path = "//%s%s" % (parsed.netloc, path)
    if len(path) > 2 and path[0] == "/" and path[2] == ":":
        path = path[1:]  # /C:/… → C:/…
    return path.replace("/", os.sep)


def path_to_uri(path: str) -> str:
    """本地路径 → file:// uri（盘符与空格/CJK 逐段百分号编码，与客户端回传形态对称）。"""
    p = os.path.abspath(path).replace(os.sep, "/")
    if len(p) > 1 and p[1] == ":":
        p = "/" + p
    return "file://" + quote(p, safe=_URI_SAFE)
