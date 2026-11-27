"""core.nf_language 私有实现分片 1/2（对外只经 core.nf_language 门面导入）：REGISTRY_REL 等"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from core import json_doc

REGISTRY_REL = "desktop/src/core/registry.json"


EVENT_REGISTRY_REL = "protocol/event_registry.json"


#: 索引扫描面（仓库相对 glob；`signature()` 与 `_modules` 共用同一份——单一出处）
SCAN_GLOBS = (
    "04_模块库/*/*.md",
    "03_管线库/*.md",
    "community/*/modules/*.md",
    "community/*/pipelines/*.md",
    "community/*/assets/*.md",
    "05_资产库/用户自定义/*.md",
)


#: 符号种类（与 `lsp.py` 的 CompletionItemKind 映射解耦：本模块只说领域语义）
KINDS = ("module", "asset", "event", "layer", "pipeline")


_PIPE_ID = re.compile(r"^\s*id:\s*(P\d{2})\s*$", re.M)


_ASSET_TOKEN = re.compile(r"[A-Z][A-Z0-9_]{2,}")


_BARE_NUM = re.compile(r"^([^:]+):(M\d{2,3})$")


def _read_json(path: Path) -> Optional[Dict[str, Any]]:
    """读 JSON；缺件/坏件返回 None（调用方如实少给符号，不裸崩、不臆造）。"""
    try:
        return json_doc.load(path, dict, what=str(path))
    except (OSError, ValueError):
        return None


def _head(path: Path, n: int = 3000) -> str:
    try:
        return path.read_text(encoding="utf-8")[:n]
    except OSError:
        return ""


def _pipe_id_of(path: Path) -> str:
    """管线件的 `id: Pxx` 声明（与 check14 ⑧ 的管线 id 反解同口径）。"""
    m = _PIPE_ID.search(_head(path, 4000))
    return m.group(1) if m else ""


#: 模块身份行（全仓统一形制：`# 模块 <id> · <name>`）
_TITLE = re.compile(r"^#\s*模块\s+(\S+?)\s*[·・]\s*(.+?)\s*$", re.M)


def module_meta(path: Path) -> Tuple[str, str]:
    """模块身份：标题行 `# 模块 <id> · <name>` 优先，其次 `machine_contract` 块，最后文件名。

    为什么标题优先：存量社区包的契约块有两处不可靠——校园包 M22 等**没有**契约块，西幻
    存活包又把限定 id 写成裸号（`id: M10`，真身份是 `生存:M10`）。标题行是全仓统一形制
    （248 件模块文件逐件可解析），且与 02 §2 的模块表、管线的 default_modules 引用同一套
    id 写法；契约块作为第二选择，文件名只作最后兜底。
    """
    text = _head(path)
    m = _TITLE.search(text)
    if m:
        return m.group(1).strip(), m.group(2).strip()
    mid = name = ""
    inblk = False
    for ln in text.splitlines():
        s = ln.strip()
        if not inblk:
            if s.startswith("machine_contract:"):
                inblk = True
            continue
        if s.startswith("```"):
            break
        if s.startswith("id:") and not mid:
            mid = s.split(":", 1)[1].strip().strip("\"'")
        elif s.startswith("name:") and not name:
            name = s.split(":", 1)[1].strip().strip("\"'")
        if mid and name:
            break
    return mid, name


@dataclass(frozen=True)
class SymbolOptions:
    """参数对象（审计 C-007：把成组参数收成不可变对象）。"""
    line: int = 0
    aliases: Optional[List[str]] = None


def _symbol(
    kind: str,
    name: str,
    detail: str,
    doc: str,
    rel: str,
    opts: SymbolOptions | None = None,
) -> Dict[str, Any]:
    opts = opts if opts is not None else SymbolOptions()
    line = opts.line
    aliases = opts.aliases
    return {"kind": kind, "name": name, "detail": detail, "doc": doc,
            "path": rel, "line": line, "aliases": sorted(set(aliases or []))}


def _bare_alias(mid: str) -> List[str]:
    """限定 id 的裸号别名（`通用:M10` → `M10`）——补全按裸号也能命中，歧义由解析面判定。"""
    m = _BARE_NUM.match(mid)
    return [m.group(2)] if m else []


class SymbolIndex:
    """NF 符号表（只读快照）。同名候选多于一个即判歧义，`resolve` 不猜。"""

    def __init__(self, root: str) -> None:
        self.root = Path(root)
        self.symbols: List[Dict[str, Any]] = []
        self._by_key: Dict[str, List[Dict[str, Any]]] = {}
        self._rel: Dict[str, List[Dict[str, str]]] = {}
        self.sig: Tuple[Tuple[str, int, int], ...] = ()

    # ------------------------------------------------------------------ 查询
    def all_symbols(self) -> List[Dict[str, Any]]:
        return list(self.symbols)

    def resolve_all(self, token: str) -> List[Dict[str, Any]]:
        """全部同名候选（悬停/补全展示用；空表 = 未登记）。"""
        return list(self._by_key.get((token or "").strip(), []))

    def resolve(self, token: str) -> Optional[Dict[str, Any]]:
        """唯一才返回；歧义 / 未登记返回 None——失败关闭，不猜（跳定义依赖此语义）。"""
        t = (token or "").strip()
        hits = self._by_key.get(t, [])
        if len(hits) == 1:
            return hits[0]
        if hits:
            return None
        if t.endswith("类") and ":" in t:            # 模型形态长名：通用类:M00 → 通用:M00
            head, num = t.split(":", 1)
            alt = self._by_key.get(head[:-1] + ":" + num, [])
            return alt[0] if len(alt) == 1 else None
        return None

    def _resolve_kind(self, token: str, kind: str) -> Optional[Dict[str, Any]]:
        """按**声明的目标种类**解析（`P00` 层位/管线同名先例：按 kind 取唯一命中才给）。

        无同种候选时回退到通用 resolve（别名 / 裸号口径）；同种多候选一律放弃（歧义不猜）。
        """
        same = [c for c in self.resolve_all(token) if c["kind"] == kind]
        if len(same) == 1:
            return same[0]
        if not same:
            return self.resolve(token)
        return None

    def references(self, token: str) -> List[Dict[str, Any]]:
        """结构化引用 → [{name, kind, path, line, why}]（只认登记关系；未登记即空表）。

        每条都带 **why**（发布方 / 订阅方 / 挂载于 Pxx / 被域包 X 采用），编辑器里因此能
        说清「为什么这里是引用」，而不是给一串匿名的位置。
        """
        out, seen = [], set()
        for edge in (self._rel.get((token or "").strip()) or []):
            if edge.get("kind") == "file":
                item = {"name": edge["target"].split("/")[1], "kind": "package",
                        "path": edge["target"], "line": 0, "why": edge["why"]}
            else:
                sym = self._resolve_kind(edge.get("target") or "", edge.get("kind") or "")
                if sym is None:
                    continue              # 目标符号未登记 ⇒ 少给一条，不臆造位置
                item = {"name": sym["name"], "kind": sym["kind"], "path": sym["path"],
                        "line": int(sym.get("line") or 0), "why": edge["why"]}
            key = (item["path"], item["line"], item["why"], item["name"])
            if key in seen:
                continue
            seen.add(key)
            out.append(item)
        out.sort(key=lambda x: (x["path"], x["line"], x["why"], x["name"]))
        return out

    def complete(self, prefix: str, limit: int = 200) -> List[Dict[str, Any]]:
        """前缀补全（空前缀返回空表——不向编辑器喷全仓符号）。"""
        p = (prefix or "").strip()
        if not p:
            return []
        out: List[Dict[str, Any]] = []
        seen: set[str] = set()
        for sym in self.symbols:
            names = [sym["name"]] + list(sym.get("aliases") or [])
            if not any(n.startswith(p) for n in names):
                continue
            if sym["name"] in seen:
                continue
            seen.add(sym["name"])
            out.append(sym)
        out.sort(key=lambda s: (KINDS.index(s["kind"]), s["name"]))
        return out[:limit]


# --------------------------------------------------------------- 各类符号构造
def _layers(reg: Dict[str, Any], out: List[Dict[str, Any]]) -> None:
    for lid, mp in sorted((reg.get("mount_points") or {}).items()):
        if not isinstance(mp, dict):
            continue
        default = ", ".join(str(x) for x in (mp.get("default") or [])) or "无"
        alias = [str(mp.get("name") or "")]
        out.append(_symbol(
            'layer',
            str(lid),
            '%s（%s）' % (mp.get('name') or '', 'optional' if mp.get('optional') else 'required'),
            '挂载层 %s · 默认模块：%s · 可用：%s' % (mp.get('name') or lid, default, ', '.join((str(x) for x in mp.get('available') or [])) or '无'),
            '02_联动注册表.md',
            opts=SymbolOptions(aliases=alias),
        ))


def _events(reg: Dict[str, Any], root: Path, out: List[Dict[str, Any]]) -> None:
    subs = reg.get("subscriptions") or {}
    extra = (_read_json(root / EVENT_REGISTRY_REL) or {}).get("events") or {}
    for name in sorted(set(subs) | set(extra)):
        s = subs.get(name) or {}
        note = str(s.get("note") or "")
        payload = extra.get(name) or {}
        fields = ", ".join(sorted((payload.get("fields") or {}))) if isinstance(payload,
 dict) else ""
        doc = "事件 %s · 发布方：%s · 订阅方：%s%s%s" % (
            name, s.get("publisher") or "未登记",
            ", ".join(str(x) for x in (s.get("subscribers") or [])) or "无",
            (" · 载荷字段：" + fields) if fields else "",
            (" · 备注：" + note) if note else "")
        out.append(_symbol(
            "event", str(name),
            "事件（发布方：%s）" % (s.get("publisher") or "未登记"), doc,
            EVENT_REGISTRY_REL if name in extra else "02_联动注册表.md"))


def _edge(rel: Dict[str, List[Dict[str, str]]], src: str, why: str,
          target: str, kind: str) -> None:
    """登记一条引用边（token → 目标 + 可解释的 why）。"""
    rel.setdefault(src, []).append({"why": why, "target": target, "kind": kind})


def _event_relations(reg: Dict[str, Any], rel: Dict[str, List[Dict[str, str]]]) -> None:
    """事件 ↔ 模块：发布方 / 订阅方（registry.subscriptions）。"""
    for ev, s in sorted((reg.get("subscriptions") or {}).items()):
        if not isinstance(s, dict):
            continue
        pub = str(s.get("publisher") or "")
        if pub:
            _edge(rel, str(ev), "发布方", pub, "module")
        for sub in s.get("subscribers") or []:
            _edge(rel, str(ev), "订阅方", str(sub), "module")


def _mount_relations(reg: Dict[str, Any], rel: Dict[str, List[Dict[str, str]]]) -> None:
    """模块 ↔ 挂载层（registry.modules[].mounts，双向登记）。"""
    for m in reg.get("modules") or []:
        if not isinstance(m, dict):
            continue
        mid = str(m.get("id") or "")
        for mt in m.get("mounts") or []:
            layer = str((mt or {}).get("layer") or "") if isinstance(mt, dict) else ""
            if mid and layer:
                _edge(rel, mid, "挂载于 %s" % layer, layer, "layer")
                _edge(rel, layer, "在此层挂载", mid, "module")


def _pipeline_relations(reg: Dict[str, Any], root: Path,
                        rel: Dict[str, List[Dict[str, str]]]) -> None:
    """管线 ← 域包采用（registry.protocols；位置取该包 README，**不可证即不给**）。"""
    for p in reg.get("protocols") or []:
        if not isinstance(p, dict):
            continue
        pkg, pipe = str(p.get("id") or ""), str(p.get("pipeline") or "")
        readme = str((p.get("assets") or {}).get("readme") or "")
        loc = "community/%s/%s" % (pkg, readme) if (pkg and readme) else ""
        if pipe and loc and (root / loc).is_file():
            _edge(rel, pipe, "被域包 %s 采用" % pkg, loc, "file")
