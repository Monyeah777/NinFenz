"""模块解析器：从文本中提取模块结构（指令集 5.1 parse_module）。

兼容两种来源格式：
1. 指令集格式（AI 按模板生成，导入对话框示例）：
   # M44：社团竞争系统
   ## 定义
   - 层：P30
   - 输入：M40, M22
   - 输出：competition_score:int
   ## 规则 / ## 核心逻辑：...
   ## 引用的资产：LOCATIONS, GANG
2. NinFenz 仓库格式（真实模块，如 community/校园情感领域包/modules/M22_三冲动驱动.md）：
   # 模块 情感:M22 · 三冲动驱动
   > 类别：情感｜来源：校园｜挂载点：P40 行为决策（active）｜依赖：M00、M40｜发布：npc_action
   ## 1. 职责 / ## 2. 出厂规则 ...
"""
from __future__ import annotations

import re

from .models import Module, CATEGORIES


def _norm_list(v) -> list:
    """把 'M40, M22' / ['M40','M22'] / '' 统一成 list[str]"""
    if v is None:
        return []
    if isinstance(v, list):
        return [str(x).strip() for x in v if str(x).strip()]
    if isinstance(v, str):
        s = v.strip()
        if not s:
            return []
        # 支持中文顿号/逗号/空格分隔
        parts = re.split(r"[、,，;\s]+", s)
        return [p.strip() for p in parts if p.strip()]
    return [str(v)]


def _title_line(lines: list) -> str:
    """首个 `# ` 一级标题行（无则空串）。"""
    for ln in lines:
        if ln.startswith("# "):
            return ln
    return ""


def _resolve_category(prefix: str, category_hint: str) -> str:
    """类别归一（情感/生存/世界/事件/通用/技术文档 → 情感类…）。"""
    cat_map = {c.rstrip("类"): c for c in CATEGORIES}
    if prefix in cat_map:
        return cat_map[prefix]
    if category_hint:
        return category_hint
    return "通用类"


def _try_nf_header(m: Module, lines: list, title_line: str,
                   category_hint: str) -> Module | None:
    """格式2：仓库式头部 # 模块 情感:M22 · 三冲动驱动 → 解析成功则返回模块。"""
    m2 = re.match(r"#\s*模块\s*([A-Za-z\u4e00-\u9fff]+)?:?(M?\d+)\s*[·.、\-]?\s*(.+)",
                  title_line)
    if not (m2 and ("模块" in title_line[:4] or ":" in title_line.split("·")[0])):
        return None
    prefix = m2.group(1) or category_hint or ""
    m.id = "M" + m2.group(2).lstrip("M").rjust(2, "0")
    m.name = m2.group(3).strip()
    m.category = _resolve_category(prefix, category_hint)
    return _parse_nf_style(m, lines)


def _try_directive_header(m: Module, lines: list, title_line: str,
                          category_hint: str) -> Module | None:
    """格式1：指令集式 # M44：社团竞争系统 → 解析成功则返回模块。"""
    m1 = re.match(r"#\s*(?:模块\s*)?([A-Za-z\u4e00-\u9fff]+:)?(M?\d+)[:：·.\-\s]*(.*)", title_line)
    if not m1:
        return None
    prefix = m1.group(1).rstrip(":：") if m1.group(1) else ""
    m.id = "M" + m1.group(2).lstrip("M").rjust(2, "0")
    m.name = m1.group(3).strip() or m.id
    m.category = _resolve_category(prefix, category_hint)
    return _parse_directive_style(m, lines)


def parse_module(content: str, category_hint: str = "") -> Module:
    """从文本解析模块。解析失败时抛 ValueError（附原因）。"""
    if not content or not content.strip():
        raise ValueError("内容为空，无法解析——请先填充模块内容再解析")

    m = Module()
    m.source_md = content.strip()
    lines = content.splitlines()
    title_line = _title_line(lines)          # ---- 识别标题行 ----
    parsed = _try_nf_header(m, lines, title_line, category_hint)
    if parsed is not None:
        return parsed
    parsed = _try_directive_header(m, lines, title_line, category_hint)
    if parsed is not None:
        return parsed
    raise ValueError("无法识别模块标题——请按 `# M44：名称` 或 `# 模块 情感:M22 · 名称` 修正后重试")


def _style_section_step(m: Module, current_section: str, s: str, logic_buf: list,
                        definition_fields: dict[str, str]) -> str:
    """单行归段：返回（可能更新的）当前小节名。"""
    if s.startswith("## "):
        return s[3:].strip()
    if not s or s.startswith("#"):
        return current_section
    if current_section in ("定义", "Definition", "def"):
        mm = re.match(r"^[-*]\s*([^:：]{1,16})[:：]\s*(.+)$", s)
        if mm:
            definition_fields[mm.group(1).strip()] = mm.group(2).strip()
    elif current_section in ("规则", "核心逻辑", "逻辑", "Rules", "logic"):
        logic_buf.append(s)
    elif current_section in ("引用的资产", "资产", "Assets", "assets"):
        mm = re.match(r"^[-*]\s*(.+)$", s)
        if mm:
            m.assets.extend(_norm_list(mm.group(1)))
    return current_section


def _scan_style_sections(m: Module, lines: list) -> tuple[list[str], dict[str, str]]:
    """扫全文分段：返回 (逻辑缓冲, 定义字段表)；资产段直接并入 m.assets。"""
    current_section = ""
    logic_buf: list[str] = []
    definition_fields: dict[str, str] = {}
    for ln in lines:
        s = ln.strip()
        current_section = _style_section_step(m, current_section, s, logic_buf,
                                              definition_fields)
    return logic_buf, definition_fields


def _apply_layer(m: Module, f: dict[str, str]) -> None:
    """挂载层归一（层/layer/挂载 → Pdd，缺省 P40）。"""
    if not (f.get("层") or f.get("layer") or f.get("挂载")):
        return
    m.layer = (f.get("层") or f.get("layer") or f.get("挂载") or "").strip()
    lm = re.search(r"P\d\d", m.layer)
    m.layer = lm.group(0) if lm else (m.layer or "P40")


def _apply_lists(m: Module, f: dict[str, str]) -> None:
    """输入/输出/发布/订阅 四张列表归一。"""
    m.inputs = _norm_list(f.get("输入") or f.get("inputs") or f.get("依赖"))
    m.outputs = _norm_list(f.get("输出") or f.get("outputs"))
    m.events_publish = _norm_list(f.get("发布") or f.get("events_publish") or f.get("发布事件"))
    m.events_subscribe = _norm_list(f.get("订阅") or f.get("events_subscribe"))


def _apply_assets(m: Module, f: dict[str, str]) -> None:
    """定义区资产（- 资产：LOCATIONS, GANG）与『## 引用的资产』段落合并去重。"""
    for a in _norm_list(f.get("资产") or f.get("assets")):
        if a and a not in m.assets:
            m.assets.append(a)


def _apply_replaceable(m: Module, f: dict[str, str]) -> None:
    """可替换标志（可替换/replaceable，缺省 true）。"""
    if f.get("可替换") is None and f.get("replaceable") is None:
        return
    raw = (f.get("可替换") or f.get("replaceable") or "true").strip().lower()
    m.replaceable = raw not in ("false", "否", "0", "no")


def _apply_definition_fields(m: Module, f: dict[str, str]) -> None:
    """定义字段整体归一到 Module。"""
    if not m.name:
        m.name = m.id
    _apply_layer(m, f)
    _apply_lists(m, f)
    _apply_assets(m, f)
    _apply_replaceable(m, f)


def _parse_directive_style(m: Module, lines: list) -> Module:
    """指令集格式：## 定义 / - key: value / ## 规则 / ## 引用的资产"""
    logic_buf, definition_fields = _scan_style_sections(m, lines)
    # 字段名归一（层/layer、输入/inputs、输出/outputs、发布/events_publish…）
    f = definition_fields
    _apply_definition_fields(m, f)
    logic = "\n".join(logic_buf).strip()
    if logic:
        m.logic = logic
    elif f.get("logic"):
        m.logic = f["logic"]
    return m


def _apply_meta_kv(m: Module, k: str, v: str) -> None:
    """元信息单键归一到 Module（类别/挂载点/依赖/发布/订阅）。"""
    if k in ("类别", "分类"):
        cat_map = {c.rstrip("类"): c for c in CATEGORIES}
        m.category = cat_map.get(v.rstrip("类"), v + "类" if v else m.category)
    elif k == "挂载点":
        lm = re.search(r"P\d\d", v)
        if lm:
            m.layer = lm.group(0)
        if "active" in v:
            m.replaceable = False
    elif k == "依赖":
        m.inputs = _norm_list(v)
    elif k == "发布":
        m.events_publish = _norm_list(v)
    elif k == "订阅":
        m.events_subscribe = _norm_list(v)


def _nf_meta_line(m: Module, s: str) -> None:
    """一行 `> 类别：…｜来源：…` 元信息 → 逐段按 `k: v` 归一。"""
    for seg in re.split(r"[｜|]", s.lstrip("> ")):
        kv = re.split(r"[:：]", seg, maxsplit=1)
        if len(kv) != 2:
            continue
        _apply_meta_kv(m, kv[0].strip(), kv[1].strip())


def _nf_code_logic(lines: list) -> str:
    """代码块里的规则正文（去围栏，逐行 strip 后连接）。"""
    buf: list[str] = []
    in_code = False
    for ln in lines:
        s = ln.strip()
        if s.startswith("```"):
            in_code = not in_code
            continue
        if in_code and s:
            buf.append(s)
    return "\n".join(buf).strip()


def _nf_heading_logic(lines: list) -> str:
    """无代码块时抓 ## 职责 / ## 规则 之后的正文。"""
    buf: list[str] = []
    hit = False
    for ln in lines:
        s = ln.strip()
        if s.startswith("## "):
            hit = "职责" in s or "规则" in s
            continue
        if hit and s and not s.startswith(("#", "```", ">")):
            buf.append(s)
    return "\n".join(buf)[:2000]


def _parse_nf_style(m: Module, lines: list) -> Module:
    """仓库格式：> 类别：…｜来源：…｜挂载点：P40 …（active）｜依赖：M00、M40｜发布：…"""
    for ln in lines:
        s = ln.strip()
        if s.startswith(">"):
            _nf_meta_line(m, s)          # 元信息行
    # 逻辑：抓取规则/职责正文（精简：取 ## 后代码块/要点，最多 2000 字）
    logic = _nf_code_logic(lines)
    if logic:
        m.logic = logic[:2000]
    if not m.logic:  # 无代码块则抓 ## 职责 后正文
        m.logic = _nf_heading_logic(lines)
    return m


def parse_asset_entries_from_text(text: str) -> dict:
    """把资产文本按 '## 键' 分段拆成 {键: 内容}"""
    out: dict = {}
    cur_key = None
    buf: list[str] = []
    for ln in text.splitlines():
        s = ln.strip()
        if s.startswith("## ") and len(s) < 80:
            if cur_key:
                out[cur_key] = "\n".join(buf).strip()
            cur_key = s[3:].strip()
            buf = []
        elif cur_key:
            buf.append(ln)
    if cur_key:
        out[cur_key] = "\n".join(buf).strip()
    return out
