"""mcp_runtime · _tools（自 mcp_runtime.py 拆出；只移动代码，行为/文案不变）。"""
from __future__ import annotations

from pathlib import Path

from core import repo_index, trust_boundary

from ._uris import (
    _repo_root,
)


def _tool_pipeline_list(query: str = "") -> list:
    root = _repo_root()
    out = []
    for it in repo_index.get(root).pipelines():
        rel, title = it["rel"], it["title"]
        if query and query not in rel and query not in title:
            continue
        out.append({"path": rel, "title": title})
    return out




def _tool_spec_list() -> list:
    reg = repo_index.get(_repo_root()).registry()
    return [{
        "id": p.get("id"), "version": p.get("version"),
        "modules": len(p.get("module_ids") or []),
        "categories": p.get("categories") or [],
    } for p in reg.get("protocols", [])]




def _tool_registry_search(query: str) -> dict:
    reg = repo_index.get(_repo_root()).registry()
    q = query.strip()
    modules = [m for m in reg.get("modules", [])
               if q in str(m.get("id")) or q in str(m.get("name"))]
    protos = [p for p in reg.get("protocols", [])
              if q in str(p.get("id")) or q in str(p.get("name"))]
    return {
        "modules": [{"id": m.get("id"), "name": m.get("name")} for m in modules],
        "protocols": [{"id": p.get("id"), "version": p.get("version"),
                       "modules": len(p.get("module_ids") or [])} for p in protos],
    }




def _tool_library_search(query: str, limit: int = 10) -> list:
    """只读检索：馆藏条目（frontmatter 真源，正文级）∪ 仓库文档标题/路径。"""
    # `limit` 在 inputSchema 里声明为 1–50 的整数；未注入 schema_check 的调用方
    # （单测 / 内嵌运行时）仍可能绕过声明面，故处理器自身再闸一次，避免 str 切片崩溃。
    if not isinstance(limit, int) or isinstance(limit, bool):
        raise ValueError("limit 须为 1–50 的整数（收到 %s）" % type(limit).__name__)
    limit = max(1, min(50, limit))
    root = _repo_root()
    q = query.strip()
    idx = repo_index.get(root)
    hits = []
    for h in idx.library_search(q, limit=limit):
        hits.append({"kind": "library", "id": h["id"], "path": h["path"],
                     "title": h["title"], "score": h["score"],
                     "status": h["status"], "type": h["type"],
                     "uri": "nf://repo/library/" + h["id"]})
    hits.extend(idx.docs_matching(q))
    return hits[:limit]




def _tool_library_read(entry_id: str) -> dict:
    """按编号取馆藏条目正文（大小写不敏感；ALIAS 语义内建）。"""
    root = _repo_root()
    want = (entry_id or "").strip()
    e = repo_index.get(root).library_entry(want)
    if e is not None:
        text = e.get("text")
        if not isinstance(text, str):
            text = repo_index.read_text(root, e["path"])
        return {"found": True, "id": e["id"], "path": e["path"],
                "status": str(e["fm"].get("status") or "active"),
                "frontmatter": e["fm"],
                "bytes": len(text.encode("utf-8")), "text": text}
    raise ValueError("馆藏条目未找到：%s（library_search 可枚举；编号大小写不敏感）"
                     "（修复指引：用 nf library ls 列全量编号）" % entry_id)




def _tool_pattern_list() -> list:
    """只读枚举：patterns/*/PATTERN.md 的 id/path/title/status。"""
    root = _repo_root()
    return [{"id": it["id"], "path": it["rel"], "title": it["title"],
             "status": it["status"]}
            for it in repo_index.get(root).patterns()]




def _tool_pattern_read(pattern_id: str) -> dict:
    """按 id 取实践包正文（patterns/<id>/PATTERN.md）。"""
    root = _repo_root()
    want = (pattern_id or "").strip()
    hit = repo_index.get(root).pattern(want)
    if hit is not None:
        text = hit["text"]
        return {"found": True, "id": want, "path": hit["rel"],
                "bytes": len(text.encode("utf-8")), "text": text}
    raise ValueError("pattern 未找到：%s（修复指引：patterns/ 下按目录名取，如 "
                     "fail-closed-verification）" % pattern_id)




def _tool_knowledge_order_read(clearance: str = "") -> dict:
    """按可见性裁剪解析知识源查询顺序（先合同级后参考级）。"""
    from core import knowledge as kn
    root = _repo_root()
    rows = kn.resolve_order(root, clearance=(clearance or ""))
    # 此前硬编码 True；改为从声明顺序实算（首源 authority=contract ⇒ 合同级在先），
    # 避免「声明改了、字段还说 true」的静默失真。
    contract_first = bool(rows) and str(rows[0].get("authority") or "") == "contract"
    return {"clearance": clearance or "不裁剪", "contract_first": contract_first,
            "count": len(rows), "query_order": rows}




def _tool_module_read(module_id: str) -> dict:
    root = _repo_root()
    hit = repo_index.get(root).module(module_id)
    if hit is None:
        raise ValueError(
            "模块未找到：%s（module ls / registry_search 可枚举）"
            "（修复指引：用仓库内真实模块 id，如 M90、M40 或 通用:M10）" % module_id)
    text = hit["text"]
    return {"found": True,
            "id": hit["mc_id"] or hit["title_id"] or module_id,
            "path": hit["rel"],
            "has_machine_contract": hit["has_contract"],
            "bytes": len(text.encode("utf-8")),
            "text": text}




def _tool_pipeline_read(pipeline: str) -> dict:
    root = _repo_root()
    req = pipeline.strip()
    if req.endswith(".md"):
        # **包含性先判**（词法判据单一出处 = `trust_boundary.relative_path_issue`，
        # 与协议面闸门 `check_arguments` 同源；realpath 包含性用 stdlib 在此补）。
        # 为什么（2026-10-01 金丝雀实证）：此前只看「以 `03_管线库/` 开头 或 含 `/pipelines/`」，
        # 于是 `community/x/pipelines/../../../<仓外>.md` 与 `C:/…/pipelines/x.md` 两种写法都能
        # **读出仓库之外**的正文——协议面由 `trust_boundary.check_arguments` 拦下（远程不可达），
        # 但工具函数自身不该把安全性押在唯一那道闸上（越权面要求纵深，见 AGENTS.md「包含性判据」）。
        # 为什么不用 `core.paths.validate_path`：那会给本模块**新增一条出边**，把自身不稳定性
        # 抬到依赖它的稳定侧之上（实测 I 0.50 → 0.55，触发 endpoint / mcp_package 两条 SDP 违例）——
        # 与 `schema_check` 依赖注置同源的老问题。故复用已依赖的 `trust_boundary` 判据 + stdlib 包含
        # 性。
        issue = trust_boundary.relative_path_issue(req)
        if issue:
            raise ValueError("管线路径越界：%s（修复指引：只传仓库根内相对路径，如 "
                             "03_管线库/P90….md；不得用 ../ 或绝对路径）" % issue)
        root_real = Path(root).resolve()
        path = (root_real / req).resolve()
        if path != root_real and root_real not in path.parents:
            raise ValueError("管线路径逃逸仓库根：%s（修复指引：目标须落在仓库内）" % req)
        if path.is_file():
            allowed = req.startswith("03_管线库/") or "/pipelines/" in req
            if not allowed:
                raise ValueError("管线路径越界：只读 03_管线库 与 community/*/pipelines"
                                 "（修复指引：路径须指向仓库内管线件，如 03_管线库/P90….md）")
            text = repo_index.read_text(root, req)
            return {"found": True, "path": req, "bytes": len(text.encode("utf-8")),
                    "text": text}
    hit = repo_index.get(root).pipeline(req)
    if hit is None:
        raise ValueError("管线未找到：%s（pipeline_list 可枚举）"
                         "（修复指引：用 Pxx 编号或仓库内相对路径）" % pipeline)
    text = hit["text"]
    return {"found": True, "path": hit["rel"],
            "bytes": len(text.encode("utf-8")), "text": text}




def _tool_asset_list(package: str = "") -> list:
    """只读枚举：资产文件 → {package, file, keys}（跳过 README）。"""
    root = _repo_root()
    return repo_index.get(root).assets(package)




def _tool_asset_get(key: str, package: str = "") -> dict:
    root = _repo_root()
    req = key.strip()
    hits = repo_index.get(root).asset_matches(req, package)
    if not hits:
        raise ValueError("资产键未找到：%s（asset ls / 包 assets/README.md 可枚举）"
                         "（修复指引：用包内资产键表登记的键名重试）" % key)
    out = []
    for h in hits:
        try:
            text = repo_index.read_text(root, h["rel"])
        except ValueError as exc:
            raise ValueError(
                f"资产路径越出仓库根：{h['rel']}（修复指引：重新生成资产索引）"
            ) from exc
        out.append({"package": h["package"], "file": h["file"],
                    "bytes": len(text.encode("utf-8")), "text": text})
    return {"key": req, "matches": out}




TOOL_HANDLERS = {
    "pipeline_list": lambda a: _tool_pipeline_list((a or {}).get("query", "")),
    "spec_list": lambda a: _tool_spec_list(),
    "registry_search": lambda a: _tool_registry_search((a or {}).get("query", "")),
    "library_search": lambda a: _tool_library_search((a or {}).get("query", ""),
                                                     (a or {}).get("limit", 10)),
    "library_read": lambda a: _tool_library_read((a or {}).get("entry_id", "")),
    "pattern_list": lambda a: _tool_pattern_list(),
    "pattern_read": lambda a: _tool_pattern_read((a or {}).get("pattern_id", "")),
    "knowledge_order_read": lambda a: _tool_knowledge_order_read((a or {}).get("clearance", "")),
    "module_read": lambda a: _tool_module_read((a or {}).get("module_id", "")),
    "pipeline_read": lambda a: _tool_pipeline_read((a or {}).get("pipeline", "")),
    "asset_list": lambda a: _tool_asset_list((a or {}).get("package", "")),
    "asset_read": lambda a: _tool_asset_get((a or {}).get("key", ""),
                                            (a or {}).get("package", "")),
}



#: 兼容别名（不进 `tools/list`）：旧客户端仍可调旧名；新面只发布 `_list/_search/_get`。
TOOL_ALIASES = {
    "asset_get": "asset_read",
    "pipeline_ls": "pipeline_list",
    "spec_ls": "spec_list",
    "pattern_ls": "pattern_list",
    "asset_ls": "asset_list",
    "registry_query": "registry_search",
    "knowledge_order": "knowledge_order_read",
    "knowledge_order_get": "knowledge_order_read",
}




def _prompt_assemble_guide() -> str:
    return (
        "你是 NinFenz 装配师。取件顺序：07_官方核心出厂与社区预设导航.md（包索引）→ "
        "02_联动注册表.md（登记/依赖真相源）→ 01_核心协议.md（契约）→ 06_Agent执行协议.md。"
        "选装配包：community/<领域包>/README.md（含装载清单/资产/验收）。装配主规范："
        "docs/agent/agent_组装指令包_v0.2.md。输出完整版 md 自检过 "
        "「##7. 自检清单」；引用式档位须如实标注缺口，禁止编造未读内容。仓库验证：bash verify.sh。"
        "取实质内容用内容工具：module_read <模块 id>（模块正文）/ pipeline_read <Pxx 或路径>"
        "（管线正文）/ asset_read <资产键>（资产正文）——禁止凭记忆写未读取的模块/资产内容。"
        "标准资源面亦可取正文：resources/read nf://repo/module/<id> / nf://repo/pipeline/<Pxx> "
        "/ nf://repo/asset/<包>/<键>。"
    )
