"""core.lsp 私有实现分片 3/4（对外只经 core.lsp 门面导入）：LspServer、_check_capabilities 等"""

from __future__ import annotations

import io
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, TextIO
from urllib.parse import unquote

from core.lsp_client import CLIENT_EDITORS, render_client_config
from core.lsp_framing import BAD_FRAME, read_message, write_message
from core.lsp_params import (
    INVALID_PARAMS,
    INVALID_REQUEST,
    SERVER_NOT_INITIALIZED,
    advise_request,
    did_change_text,
    did_open_payload,
    lifecycle_problem,
)

from ._part1 import (
    _REQUIRED_CAPS,
    M_COMPLETION,
    M_DEFINITION,
    M_DID_CHANGE,
    M_DID_CLOSE,
    M_DID_OPEN,
    M_DID_SAVE,
    M_DOCUMENT_SYMBOL,
    M_EXIT,
    M_FOLDING_RANGE,
    M_HOVER,
    M_INITIALIZE,
    M_INITIALIZED,
    M_REFERENCES,
    M_SHUTDOWN,
    METHOD_NOT_FOUND,
    SERVER_NAME,
    SERVER_VERSION,
    _within_root,
    uri_to_path,
)
from ._part2 import _REQUESTS, _error, _LspServerPart1


class LspServer(_LspServerPart1):
    """NF LSP 会话（stdio）。不写盘：编辑只经 codeAction 交客户端。"""

    # ---- 消息面
    # ---- 消息面
    def handle(self, msg: Dict[str, Any]) -> List[Dict[str, Any]]:
        """单条消息 → 待发消息列表（表驱动分派；通知/请求分开走，便于各自收敛）。"""
        method = msg.get("method")
        params = msg.get("params") or {}
        rid = msg.get("id")
        problem = lifecycle_problem(method, rid, self.shutting_down, self.initialized)
        if problem:
            return [_error(rid, problem[0], problem[1])]
        if method == M_INITIALIZE:
            return [self._handshake(rid, params)]
        if method in (M_INITIALIZED, M_EXIT):
            return []                      # 规范：initialized 通知忽略；exit 由 serve 循环收口
        if (method or "").startswith("$/"):
            # 规范（$/ 请求与通知）：**通知**可忽略；**请求**必须回 MethodNotFound——
            # 静默不回会让合规客户端一直等应答（2026-10-08 实测：旧实现两种都吞掉）。
            if rid is None:
                return []
            return [_error(rid, METHOD_NOT_FOUND, "Method not found: %s" % method)]
        if not self.initialized:
            # 未握手前的**通知**一律不做（请求已在状态机处回 -32002）：根还没采纳，照做只会
            # 用 CLI 默认根产出「看起来对」的诊断与索引状态。
            return []
        note = self._notification(method, params)
        if note is not None:
            return note
        if method == M_SHUTDOWN:
            self.shutting_down = True
            if rid is None:                    # 通知形态的 shutdown：记状态但不回应答
                return []
            return [{"jsonrpc": "2.0", "id": rid, "result": None}]
        return self._dispatch_request(method, params, rid)

    def _dispatch_request(self, method: Any, params: Dict[str, Any],
                          rid: Any) -> List[Dict[str, Any]]:
        """请求分派：参数准入 → 处理器；未知方法回 -32601、参数不合回 -32602。"""
        handler = _REQUESTS.get(method)
        if rid is None:
            # 无 id = **通知**：JSON-RPC 2.0 §4.1 禁止应答。2026-10-08 实测：旧实现对
            # 「请求方法当通知发」会回一条 id=null 的应答——客户端会收到不请自来的响应
            # （同族口径在 MCP 面是对的，两轴判据 test_two_faces_jsonrpc 把它抓了出来）。
            return []
        if handler is None:
            return [_error(rid, METHOD_NOT_FOUND, "Method not found: %s" % method)]
        problem = advise_request(method, params)
        if problem:
            return [_error(rid, INVALID_PARAMS, problem)]
        return [{"jsonrpc": "2.0", "id": rid, "result": handler(self, params)}]

    def _handshake(self, rid: Any, params: Dict[str, Any]) -> Dict[str, Any]:
        """initialize 应答（能力清单 + 服务端自述）；成功后会话才算建立。"""
        self._on_initialize(params)
        self.initialized = True
        return {"jsonrpc": "2.0", "id": rid,
                "result": {"capabilities": self.capabilities(),
                           "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION}}}

    def _notification(self, method: Any, params: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:
        """文档生命周期通知 → 待发消息；**非通知返回 None**（交由请求分派）。"""
        if method not in (M_DID_OPEN, M_DID_CHANGE, M_DID_SAVE, M_DID_CLOSE):
            return None
        if method == M_DID_SAVE:
            # 磁盘件可能刚被改：下次取索引强制重扫签名（放在 docs 守卫之前——没跟踪的文档
            # 也可能是仓库件，保存事实本身就足以让缓存失效）。
            self.invalidate()
        uri = (params.get("textDocument") or {}).get("uri", "")
        if method == M_DID_OPEN:
            payload = did_open_payload(params)          # 不合形即丢弃（详见 core/lsp_params）
            if payload is None:
                return []
            self.docs[payload[0]] = {"path": uri_to_path(payload[0]), "text": payload[1]}
            return [self._publish(payload[0])]
        if method == M_DID_CLOSE:
            self.docs.pop(uri, None)
            return [self._publish(uri, clear=True)]
        if uri not in self.docs:
            return []
        if method == M_DID_CHANGE:
            text = did_change_text(params)               # 同上：坏帧不进状态
            if text is None:
                return []
            self.docs[uri]["text"] = text
        return [self._publish(uri)]

    def _on_initialize(self, params: Dict[str, Any]) -> None:
        self.client_caps = params.get("capabilities") or {}
        if self.explicit_root:
            return
        root = params.get("rootUri")
        if not root:
            folders = params.get("workspaceFolders") or []
            root = (folders[0] or {}).get("uri") if folders else ""
        if not root:
            root = params.get("rootPath")
        if not root:
            return
        candidate = uri_to_path(str(root)) if str(root).startswith("file:") else str(root)
        # **采纳是有条件的**（审计 X2，P1）：rootUri 决定此后 `_text_of` 的包含性边界，
        # 无条件照单全收等于把「能读哪些文件」的裁决权交给客户端。两条判据：① 落点必须是
        # **在场目录**；② 必须落在**启动根**内（`nf lsp` 的仓库根 / `--root`）。不满足一律
        # 拒绝并保留启动根——fail-closed：宁可少服务一个 workspace，不可越界读根外文件。
        if not os.path.isdir(candidate) or not _within_root(self._launch_root, candidate):
            return
        self.root = os.path.abspath(candidate)

    def capabilities(self) -> Dict[str, Any]:
        """服务端能力（`positionEncoding` 固定 utf-16——LSP 规范要求客户端必须支持）。"""
        return {
            "positionEncoding": "utf-16",
            "textDocumentSync": {"openClose": True, "change": 1, "save": True},
            "hoverProvider": True,
            "completionProvider": {"triggerCharacters": [":", "`", "\"", "'", "{", "[", " "],
                                   "resolveProvider": False},
            "definitionProvider": True,
            "documentSymbolProvider": True,
            "workspaceSymbolProvider": True,
            "referencesProvider": True,
            "foldingRangeProvider": True,
            "codeActionProvider": {"codeActionKinds": ["quickfix"]},
        }

    # ---- transport
    def serve(self, stdin: Optional[TextIO] = None,
              stdout: Optional[TextIO] = None) -> int:
        """stdio 主循环；返回进程退出码（规范：未收 shutdown 就 exit ⇒ 1）。"""
        stdin = stdin if stdin is not None else sys.stdin
        stdout = stdout if stdout is not None else sys.stdout
        while True:
            msg = read_message(stdin)
            if msg is None:
                return 0          # 传输关闭（EOF）：按旧行为正常收摊；退出码约束只针对 exit 通知
            if msg is BAD_FRAME:
                # 坏帧不杀会话：回 -32700（id 不可判定 ⇒ null）后继续读下一帧。
                write_message(stdout, {
                    "jsonrpc": "2.0", "id": None,
                    "error": {"code": -32700,
                              "message": "Parse error（非法 UTF-8 / 非法 JSON / 坏 Content-Length；"
                                         "修复指引：Content-Length 以**字节**计，正文为 UTF-8 JSON"
                                             "）"}})
                continue
            if not isinstance(msg, dict):
                # JSON-RPC 2.0：消息须为对象（本实现不支持批量数组）→ -32600 后继续。
                write_message(stdout, {
                    "jsonrpc": "2.0", "id": None,
                    "error": {"code": -32600,
                              "message": "Invalid Request（消息须为 JSON 对象；"
                                         "修复指引：勿发数组/标量，本服务不支持批量请求）"}})
                continue
            if msg.get("method") == M_EXIT:
                return 0 if self.shutting_down else 1
            try:
                for resp in self.handle(msg):
                    write_message(stdout, resp)
            except Exception as exc:  # 单条异常不杀会话
                if "id" in msg:
                    write_message(stdout, {"jsonrpc": "2.0", "id": msg["id"],
                                           "error": {"code": -32603,
                                                     "message": str(exc)}})


def _check_capabilities(srv: "LspServer", init: Dict[str, Any]) -> List[str]:
    """initialize 能力声明：编辑器面要用的能力必须齐备且口径正确。

    `init` = 握手应答（由 check() 送**一次** initialize 得到；本函数不再自己发包——
    2026-10-08 补状态机后，重复 initialize 会正确地回 -32600）。
    """
    issues: List[str] = []
    caps = init["capabilities"]
    for key in _REQUIRED_CAPS:
        if key not in caps:
            issues.append("initialize 能力缺 " + key)
    if caps.get("positionEncoding") != "utf-16":
        issues.append("positionEncoding 应为 utf-16（LSP 默认口径，客户端必须支持）")
    if not (caps.get("codeActionProvider") or {}).get("codeActionKinds"):
        issues.append("codeActionProvider 未声明 codeActionKinds")
    server = init["serverInfo"]
    if server.get("name") != SERVER_NAME or server.get("version") != SERVER_VERSION:
        issues.append("serverInfo 与 SERVER_NAME/SERVER_VERSION 不一致：%s" % server)
    return issues


def _lifecycle_close_issues(srv: "LspServer", probe: str) -> List[str]:
    issues: List[str] = []
    diags = srv._publish(probe)["params"]["diagnostics"]
    if not diags:
        issues.append("已知坏文档零诊断（诊断源与 nf lint 失同源？）")
    elif all(d["range"]["start"]["character"] == 0 for d in diags):
        issues.append("诊断位置全为列 0——编辑器无法定位到正文")
    srv.handle({"jsonrpc": "2.0", "method": M_DID_CLOSE,
                "params": {"textDocument": {"uri": probe}}})
    if probe in srv.docs:
        issues.append("didClose 未清理文档状态（长驻会话状态泄漏）")
    return issues


def _lifecycle_state_issues(probe: str, root_s: str) -> List[str]:
    issues: List[str] = []
    # 协议状态机（2026-10-08 补）：未初始化就发请求 / 重复 initialize / shutdown 后再发请求
    fresh = LspServer(root=root_s, explicit_root=True)
    pre = fresh.handle({"jsonrpc": "2.0", "id": 90, "method": M_COMPLETION,
                        "params": {"textDocument": {"uri": probe}}})[0]
    if (pre.get("error") or {}).get("code") != SERVER_NOT_INITIALIZED:
        issues.append("未 initialize 就发请求未回 -32002（协议状态机）")
    fresh.handle({"jsonrpc": "2.0", "id": 91, "method": M_INITIALIZE, "params": {}})
    again = fresh.handle({"jsonrpc": "2.0", "id": 92, "method": M_INITIALIZE, "params": {}})[0]
    if (again.get("error") or {}).get("code") != INVALID_REQUEST:
        issues.append("重复 initialize 未回 -32600（协议：一个会话只允许一次）")
    fresh.handle({"jsonrpc": "2.0", "id": 93, "method": M_SHUTDOWN, "params": {}})
    after = fresh.handle({"jsonrpc": "2.0", "id": 94, "method": M_COMPLETION,
                          "params": {"textDocument": {"uri": probe}}})[0]
    if (after.get("error") or {}).get("code") != INVALID_REQUEST:
        issues.append("shutdown 之后仍服务请求（未回 -32600）")
    return issues


def _check_lifecycle(srv: "LspServer", probe: str, root_s: str) -> List[str]:
    """诊断定位 / didClose 清理 / 未 shutdown 的 exit 退出码。"""
    issues: List[str] = []
    srv.handle({"jsonrpc": "2.0", "method": M_DID_OPEN,
                "params": {"textDocument": {"uri": probe, "text": "# 标题  \n\n正文  \n"}}})
    issues += _lifecycle_close_issues(srv, probe)
    issues += _lifecycle_state_issues(probe, root_s)
    buf = io.BytesIO()
    write_message(buf, {"jsonrpc": "2.0", "method": M_EXIT})
    if LspServer(root=root_s).serve(stdin=io.BytesIO(buf.getvalue()),
                                    stdout=io.BytesIO()) != 1:
        issues.append("未 shutdown 直接 exit 应返回 1（LSP 规范）")
    return issues


def _references_issues(srv: "LspServer", probe: str) -> List[str]:
    """引用面体检：**登记关系**（事件 ↔ 发布/订阅模块）必须给出可解释的位置。"""
    srv.handle({"jsonrpc": "2.0", "method": M_DID_OPEN,
                "params": {"textDocument": {"uri": probe,
 "text": "# 探针\n事件 narrative_event\n"}}})
    out = srv.handle({"jsonrpc": "2.0", "id": 70, "method": M_REFERENCES,
                      "params": {"textDocument": {"uri": probe},
                                 "position": {"line": 1, "character": 4}}})[0]
    locs = out.get("result") or []
    if not locs:
        return ["引用面为空：事件 narrative_event 的登记引用（发布/订阅）未给出位置"]
    if not all(str(x.get("uri") or "").startswith("file:") for x in locs):
        return ["引用面给了非 file: 的 uri（编辑器打不开）"]
    return []


def _folding_issues(srv: "LspServer", probe: str) -> List[str]:
    """折叠面体检：多标题文档必须给出 ≥2 条区间，且不得出现空跨（客户端会忽略）。

    为什么值得进闸门（2026-10-08）：折叠是「长档可用性」的地基（02_联动注册表.md 1151 行），
    而它的实现直接依赖标题口径——口径一变（例如把围栏内 # 当标题）折叠就会碎成噪声。
    """
    srv.handle({"jsonrpc": "2.0", "method": M_DID_OPEN,
                "params": {"textDocument": {"uri": probe,
                                            "text": "# 一级\n\n正文\n\n## 二级\n\n正文\n"}}})
    ranges = srv.handle({"jsonrpc": "2.0", "id": 71, "method": M_FOLDING_RANGE,
                         "params": {"textDocument": {"uri": probe}}})[0].get("result") or []
    if len(ranges) < 2:
        return ["折叠面区间过少（多标题文档应给出 ≥2 条）：%s" % ranges]
    if any(int(r.get("endLine") or 0) <= int(r.get("startLine") or 0) for r in ranges):
        return ["折叠区间出现空跨（endLine ≤ startLine）：%s" % ranges]
    return []


def _helix_issues(cfg: str) -> List[str]:
    import tomllib
    issues: List[str] = []
    try:
        data = tomllib.loads("\n".join(cfg.split("\n")[1:]))
    except tomllib.TOMLDecodeError as exc:
        return ["Helix 配置不是合法 TOML：%s" % exc]
    srv_cfg = ((data.get("language-server") or {}).get("nf-lsp") or {})
    if srv_cfg.get("command") != "python" or "lsp" not in (srv_cfg.get("args") or []):
        issues.append("Helix 配置的 language-server 段结构不对：%s" % srv_cfg)
    return issues


def _client_config_issues(r: Path) -> List[str]:
    """客户端配置体检：生成件必须指向 nf lsp 入口，且 **Helix 那份要能当 TOML 解析**。

    为什么加解析（2026-10-08）：此前只查子串——生成器若把 Windows 路径写成非法 TOML
    （反斜杠留在基本字符串里），子串判据全绿，用户粘进 languages.toml 才炸。
    """
    out = []
    for editor in CLIENT_EDITORS:
        cfg = render_client_config(editor, str(r.resolve()))
        if "scripts/nf.py" not in cfg or '"lsp"' not in cfg:
            out.append("客户端配置 %s 未指向 nf lsp 入口" % editor)
        if editor != "helix":
            continue
        out += _helix_issues(cfg)
    return out


def _symbol_issue(srv: "LspServer", r: Path) -> List[str]:
    sym = srv.symbols().resolve("M00")
    if sym is None or not (r / sym["path"]).is_file():
        return ["模块 M00 未解析到真实模块件（符号表与仓库失同步）"]
    return []


def _probe_issues(srv: "LspServer", probe: str) -> List[str]:
    issues: List[str] = []
    srv.handle({"jsonrpc": "2.0", "method": M_DID_OPEN,
                "params": {"textDocument": {"uri": probe, "text": "# 模块 M00\n"}}})
    pos = {"line": 0, "character": 6}
    doc = {"textDocument": {"uri": probe}, "position": pos}
    comp = srv.handle({"jsonrpc": "2.0", "id": 3, "method": M_COMPLETION,
                       "params": doc})[0]["result"]["items"]
    if not any(i["label"] == "M00" for i in comp):
        issues.append("补全未给模块 M00")
    hov = srv.handle({"jsonrpc": "2.0", "id": 4, "method": M_HOVER,
                      "params": doc})[0]["result"]
    if not hov or "模块 M00" not in hov["contents"]["value"]:
        issues.append("悬停未给模块元数据")
    defn = srv.handle({"jsonrpc": "2.0", "id": 5, "method": M_DEFINITION,
                       "params": doc})[0]["result"]
    if not defn or "M00_" not in unquote(defn["uri"]):
        issues.append("跳定义未指向模块件")
    outl = srv.handle({"jsonrpc": "2.0", "id": 6, "method": M_DOCUMENT_SYMBOL,
                       "params": {"textDocument": {"uri": probe}}})[0]["result"]
    if not outl:
        issues.append("文档大纲为空")
    return issues


def _check_intelligence(srv: "LspServer", probe: str, r: Path) -> List[str]:
    """领域解析（真仓库件）+ 补全 / 悬停 / 跳定义 / 大纲真跑 + 客户端配置生成。"""
    issues = _symbol_issue(srv, r)
    issues += _probe_issues(srv, probe)
    issues += _client_config_issues(r)
    issues += _references_issues(srv, probe)
    issues += _folding_issues(srv, probe)
    # 参数准入（2026-10-08 补）：非法参数必须回 -32602，而不是冒成 -32603 内部错误。
    bad = srv.handle({"jsonrpc": "2.0", "id": 8, "method": M_HOVER,
                      "params": {"textDocument": {"uri": probe},
                                 "position": {"line": "a", "character": 0}}})[0]
    if (bad.get("error") or {}).get("code") != INVALID_PARAMS:
        issues.append("参数准入失效：非法 position 未回 -32602（实得 %s）" % (bad.get("error"),))
    return issues
