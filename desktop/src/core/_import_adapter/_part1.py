"""core.import_adapter 私有实现分片 1/2（对外只经 core.import_adapter 门面导入）： 等"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from core.ir import IRDocument, IRLayer, IRModule


def _unquote_yaml_value(val: str) -> str:
    """剥 YAML 标量引号（双引号内 \\" 转义、单引号内 '' 转义）。"""
    if len(val) >= 2 and val[0] == '"' and val[-1] == '"':
        return val[1:-1].replace('\\"', '"').replace("\\\\", "\\")
    if len(val) >= 2 and val[0] == "'" and val[-1] == "'":
        return val[1:-1].replace("''", "'")
    return val


# ============================================================== frontmatter
def parse_frontmatter(text: str) -> tuple[dict, str]:
    """SKILL.md 文本 → (frontmatter dict, body)。

    轻量 YAML 子集：`---` 开闭行之间逐行 `key: value`；value 支持：
    - 裸值（skill-creator：无引号英文说明）
    - 双引号包裹单行（docx：含裸单引号与冒号，剥外层引号保留内部）
    - 单引号包裹单行（剥外层）
    扩展字段（license 等）一律透传。无法解析出闭合 frontmatter 时抛 ValueError。
    """
    if not text.startswith("---"):
        raise ValueError("无 YAML frontmatter（SKILL.md 应以 `---` 开头）")
    lines = text.split("\n")
    end = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end = i
            break
    if end is None:
        raise ValueError("frontmatter 未闭合（缺少第二个 `---`）")
    fm: dict = {}
    for ln in lines[1:end]:
        s = ln.strip()
        if not s or s.startswith("#"):
            continue
        m = re.match(r"^([A-Za-z_][\w-]*):\s*(.*)$", s)
        if not m:
            raise ValueError(f"frontmatter 行无法解析：{ln!r}——请按 `key: value` 格式修正该行")
        key, val = m.group(1), m.group(2)
        fm[key] = _unquote_yaml_value(val)
    body = "\n".join(lines[end + 1:])
    return fm, body


# ============================================================== 结果结构
@dataclass
class SkillParseResult:
    """parse_skill 结果。

    mode='nf'：NF 导出结构，ir 为高保真重建 IRDocument（可 round-trip）。
    mode='external'：非 NF 层级外部技能，ir=None（升 IR 由消费方判定），
    frontmatter/body 原样保留供消费。
    """
    ok: bool
    mode: str                                   # 'nf' | 'external'
    ir: Optional[IRDocument] = None             # nf 模式：重建 IR
    frontmatter: dict = field(default_factory=dict)
    body: str = ""
    warnings: List[str] = field(default_factory=list)
    #: v2.5.0 Wave1：skill 资源随行装载清单（scripts/references/assets 子目录
    #: 相对路径，供导出随行复制/消费方装载；缺省空列表 = 无资源目录）。
    bundled_resources: List[str] = field(default_factory=list)


@dataclass
class Ccv3ParseResult:
    """parse_ccv3 结果：叙事型 IR 骨架 + chara 顶层字段透传。"""
    ok: bool
    ir: Optional[IRDocument] = None
    chara_meta: dict = field(default_factory=dict)   # chara/world 顶层透传
    warnings: List[str] = field(default_factory=list)


# ============================================================== parse_skill
# NF 导出 body 层级模式（对称面：skill_adapter._build_skill_md）
_RE_LAYER = re.compile(r"^## 层\s+([^\s·]+)\s*·\s*(.+)$")


_RE_MODULE = re.compile(r"^###\s+([^\s·]+)\s*·\s*(.+)$")


_RE_EXTRA = re.compile(r"^## 附加规则\s*$")


# NF 导出 description 格式：f"{pipeline_name}（{pipeline_id}）生成：协议/文档操作规格，共 N 个规则块
# 。"
_RE_DESC_NF = re.compile(
    r"^(.+?)[（(]([^（）()]+)[)）]生成[:：]协议/文档操作规格，共\s*(\d+)\s*个规则块。?$")


_PLACEHOLDER_NO_BODY = "（无正文）"


def _nf_state() -> Dict[str, Any]:
    return {"title": None, "layers": [], "extra": [], "warnings": [],
            "cur_layer": None, "cur_mod": None, "buf": [], "in_extra": False}


def _nf_flush(st: Dict[str, Any]) -> None:
    cur_mod = st["cur_mod"]
    if cur_mod is None:
        st["buf"] = []
        return
    content = "\n".join(st["buf"]).strip("\n")
    if content == _PLACEHOLDER_NO_BODY:
        content = ""                      # 占位还原为空正文（高保真）
    cur_mod.content = content
    if st["in_extra"]:
        st["extra"].append(cur_mod)
    elif st["cur_layer"] is not None:
        st["cur_layer"].modules.append(cur_mod)
    else:                                  # 模块头出现在任何层头之前 → 损坏
        st["warnings"].append(f"模块 {cur_mod.full_id} 前无层头，归入层外模块")
        st["extra"].append(cur_mod)
    st["cur_mod"] = None
    st["buf"] = []


def _nf_skip_line(st: Dict[str, Any], ln: str, lines: List[str]) -> bool:
    if st["title"] is not None and ln == lines[0]:
        return True                           # # title 行本身不入 content
    if ln.startswith(("# ", "## ", "### ", "#### ")):
        # 未匹配 NF 层级模板的标题行：宽容保留进当前 content，不静默丢
        if st["cur_mod"] is not None or st["cur_layer"] is not None:
            st["buf"].append(ln)
        return True
    return False


def _nf_line(st: Dict[str, Any], ln: str, lines: List[str]) -> None:
    lm = _RE_LAYER.match(ln)
    if lm:
        _nf_flush(st)
        st["in_extra"] = False
        st["cur_layer"] = IRLayer(id=lm.group(1).strip(),
                                  name=lm.group(2).strip())
        st["layers"].append(st["cur_layer"])
        return
    if _RE_EXTRA.match(ln):
        _nf_flush(st)
        st["in_extra"] = True
        st["cur_layer"] = None
        return
    mm = _RE_MODULE.match(ln)
    if mm:
        _nf_flush(st)
        full_id = mm.group(1).strip()
        st["cur_mod"] = IRModule(full_id=full_id,
                                 name=mm.group(2).strip(),
                                 layer=(st["cur_layer"].id if st["cur_layer"] else ""))
        return
    if _nf_skip_line(st, ln, lines):
        return
    if st["cur_mod"] is not None or st["in_extra"]:
        st["buf"].append(ln)
    # 层头与模块头之间的空行/游离行不收集（对齐 _build_skill_md 结构）


def _nf_title(lines: List[str]) -> Optional[str]:
    # 一级标题 = title（NF 导出 body 首行 # {title}）
    for ln in lines:
        if ln.startswith("# "):
            return ln[2:].strip()
    return None


def _parse_nf_body(body: str) -> tuple[Optional[str], List[IRLayer], List[IRModule],
                                       List[str]]:
    """解析 NF 层级正文 → (title, layers, extra_modules, warnings)。"""
    st = _nf_state()
    lines = body.split("\n")
    st["title"] = _nf_title(lines)
    for raw in lines:
        ln = raw.rstrip("\r")
        _nf_line(st, ln, lines)
    _nf_flush(st)
    return st["title"], st["layers"], st["extra"], st["warnings"]


#: skill 资源随行装载目录（Agent Skills 目录约定：scripts/references/assets）
_BUNDLED_DIRS = ("scripts", "references", "assets")


def _scan_resources(skill_dir: Path) -> List[str]:
    """扫描 skill 目录下 scripts/references/assets 子目录文件 → 相对路径清单。

    v2.5.0 Wave1：读入侧资源随行装载（对称面 export_skill 仅产单 SKILL.md，
    资源由外部 skill 携带；本函数把同目录资源登记进 bundled_resources 供消费方
    装载/复制）。目录不存在 → 空清单（不报错，资源可缺省）。
    """
    out: List[str] = []
    for d in _BUNDLED_DIRS:
        sub = skill_dir / d
        if not sub.is_dir():
            continue
        for f in sorted(sub.rglob("*")):
            if f.is_file() and not f.is_symlink():
                out.append(str(f.relative_to(skill_dir)).replace("\\", "/"))
    return out


def _skill_header(text: str, skill_dir: Optional[Path]) -> tuple:
    bundled = _scan_resources(skill_dir) if skill_dir else []
    if not text or not text.strip():
        raise ValueError("SKILL.md 内容为空——请先填充正文再解析")
    fm, body = parse_frontmatter(text)
    name = fm.get("name", "").strip()
    desc = fm.get("description", "").strip()
    if not name:
        raise ValueError("frontmatter 缺少必填字段 name")
    if not desc:
        raise ValueError("frontmatter 缺少必填字段 description")
    if not body.strip():
        raise ValueError("SKILL.md 正文为空——请先补正文（非空）再解析")
    return bundled, fm, body, name, desc


def _external_result(fm: Dict[str, Any], body: str, bundled: List[Any]) -> SkillParseResult:
    return SkillParseResult(
        ok=True, mode="external", ir=None,
        frontmatter=fm, body=body,
        bundled_resources=bundled,
        warnings=["正文非 NF 导出层级结构（`## 层`/`## 附加规则` 未命中），"
                  "按宽容层保留 frontmatter 与正文；是否升 IR 由消费方判定"])


def _pipeline_fields(desc: str, layers: List[IRLayer], extra: List[IRModule],
                     warnings: List[str]) -> tuple:
    pipeline_id = pipeline_name = ""
    mdesc = _RE_DESC_NF.match(desc)
    if mdesc:
        pipeline_name = mdesc.group(1).strip()
        pipeline_id = mdesc.group(2).strip()
        n_declared = int(mdesc.group(3))
        n_actual = sum(len(l.modules) for l in layers) + len(extra)
        if n_declared != n_actual:
            warnings.append(
                f"frontmatter description 声明 {n_declared} 个规则块，"
                f"正文解析出 {n_actual} 个——以正文为准")
    else:
        warnings.append(
            "description 非 NF 导出格式（未解析出 pipeline/规则块计数），"
            "pipeline 字段留空，正文层级仍按结构层重建")
    return pipeline_id, pipeline_name


def parse_skill(text: str, skill_dir: Optional[Path] = None) -> SkillParseResult:
    """SKILL.md 文本 → SkillParseResult（结构层高保真重建 / 宽容层保留）。

    skill_dir（v2.5.0 Wave1）：传入 SKILL.md 所在目录时，扫描 scripts/
    references/assets 子目录随行资源 → bundled_resources 清单。
    """
    bundled, fm, body, name, desc = _skill_header(text, skill_dir)

    # ---- 宽容层判定：body 无 NF 层级模式（官方技能自由说明文）→ 不套层级
    # 注意：正则无 re.MULTILINE，`^` 只锚定串首——须逐行 match 而非整串 search
    has_nf_hierarchy = any(
        _RE_LAYER.match(ln) or _RE_EXTRA.match(ln)
        for ln in body.splitlines())
    if not has_nf_hierarchy:
        return _external_result(fm, body, bundled)

    # ---- 结构层：NF 层级 body → 高保真重建 IRDocument（techdoc 型）
    title, layers, extra, w = _parse_nf_body(body)
    warnings = list(w)
    if title is None:
        # NF 导出必有 # title；缺失时回退 frontmatter name（罕见，记警告）
        title = name
        warnings.append("正文未找到一级标题 `# ...`，title 回退 frontmatter name")
    # description 回填 pipeline 字段（NF 导出格式）
    pipeline_id, pipeline_name = _pipeline_fields(desc, layers, extra, warnings)
    ir = IRDocument(
        type="techdoc", title=title,
        pipeline_id=pipeline_id, pipeline_name=pipeline_name,
        layers=layers, extra_modules=extra,
        warnings=warnings,
        meta={"adapter_in": "parse_skill",
              "source": "SKILL.md",
              "frontmatter": fm,
              "bundled_resources": bundled},
    )
    return SkillParseResult(ok=True, mode="nf", ir=ir,
                            frontmatter=fm, body=body, warnings=warnings,
                            bundled_resources=bundled)


# ============================================================== parse_ccv3
_RE_COMMENT_LAYER = re.compile(r"^NF 层\s*([^\s·]+)\s*·\s*(.+)$")


_COMMENT_EXTRA = "NF 层外模块"


_COMMENT_ASSET = "NF 资产素材"


# NF 导出 chara description：f"{pipeline_name}（{pipeline_id}）装配产物 · N 个规则模块 + M 项资产素
# 材。由宁封子 2.0 导出层生成。"
_RE_DESC_CCV3 = re.compile(
    r"^(.+?)[（(]([^（）()]+)[)）]装配产物")


def _entry_head(e: dict, seen: set, warnings: List[str]) -> Optional[str]:
    keys = e.get("keys") or []
    full_id = str(keys[0]) if keys else str(e.get("name") or "")
    if not full_id:
        warnings.append("world 条目缺少 keys/name，跳过")
        return None
    if full_id in seen:
        return None                            # 已收集（chara 与 world 重复）
    seen.add(full_id)
    return full_id


def _entry_to_module(e: dict, seen: set, warnings: List[str]) -> Optional[IRModule]:
    """chara/world lorebook 条目 → IRModule（含层位/资产/层外归属判定）。"""
    full_id = _entry_head(e, seen, warnings)
    if full_id is None:
        return None
    name = str(e.get("name") or full_id)
    content = str(e.get("content") or "")
    comment = str(e.get("comment") or "")
    if comment == _COMMENT_ASSET:
        return None                            # 资产条目由调用方还原 asset_refs
    lm = _RE_COMMENT_LAYER.match(comment)
    layer_id = lm.group(1).strip() if lm else ""
    if not lm:
        warnings.append(f"条目 {full_id} 无 NF 层位注释（comment={comment!r}），"
                        "归入层外模块（extra_modules）")
    return IRModule(full_id=full_id, name=name,
                    layer=layer_id,
                    content=content)


def _record_asset(e: dict, full_id: str, asset_refs: dict, seen: set) -> bool:
    """资产条目（comment 为资产标记且有 full_id）→ 记入 asset_refs；命中返回 True。"""
    if str(e.get("comment") or "") == _COMMENT_ASSET and full_id:
        asset_refs[full_id] = str(e.get("content") or "")
        seen.add(full_id)
        return True
    return False
