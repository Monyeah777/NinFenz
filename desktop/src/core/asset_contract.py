"""数字资产契约层：三面验证（数据 / 代码 / 脚本组合 · 声明即契约）。

为什么需要（内部差距实证 2026-10-03）：NF 的门禁此前只守「NF 自己产出的内容资产」——
`export_schema`（5 种产物 shape）、`json_schema`（协议件）、`code_metrics`（AST 度量）、
`purity_scan`（sink 面/纯度）、`sast_check`（bandit + ruff-S 计数棘轮）。而「任何 AI 产出的
数字资产（数据文件 / 生成代码 / 多语言脚本链）」没有统一契约面：数据格式与字段完整性只能
逐件人查，脚本组合的「A 的输出必须匹配 B 的输入」完全没有判据。本模块把这一面做成
**声明即契约 + 只判可证**的机读门禁（真源 `protocol/asset_contracts.json`）。

三面口径：
- **数据面**：JSON（严格 RFC 8259：拒 NaN/Infinity）/ CSV（表头 + 逐行列数）/ Markdown
  （frontmatter + 表格列数）；必填字段；可选 sha256 防篡改；可选 link（某字段是文件路径，
  其行数必须等于另一字段的计数——输入输出一致性）。
- **代码面**：AST 规范符合性（可解析 + 禁用调用面）+ **可证**空指针（同一语句序列内
  `x = None` 之后解引用 x，且期间无重新赋值/无分支并入）+ 测试用例在场（声明的测试件必须
  存在、可解析、且点名被测模块）。**安全漏洞面不另造一套**——SQL 拼接 / 命令注入 / 弱随机等
  由 `scripts/sast_check.py`（bandit + ruff-S 计数棘轮）与 `purity_scan` R6 守着，
  本模块重复造第二套只会造出两套口径。
- **脚本面**：脚本自带的 `nf-io:` 头（Python `#` / Bash `#` / VBA ``` 用同一声明格式）
  是契约双源之一，声明件是另一源；两源必须逐字一致；链（A→B）上「A 的产物」必须落在
  「B 的输入」里且路径对齐。**只判字面路径**——变量拼出来的路径不判（不编造）。
- **测试执行**：`run_tests()` 是**显式开启**面（`nf asset contract --run-tests`），
  默认门禁不执行任何被声明脚本的代码——门禁必须静态可复现。

纪律：纯标准库；只读扫描（唯 `freeze()` 写声明件）；解析不到的面写「未收窄」，不替它
编结论；问题消息带修复指引。
"""
from __future__ import annotations

import ast
import csv
import hashlib
import importlib.util
import io
import json
import os
import re
import subprocess
import unittest
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from core import atomic_write, json_doc

DECL_REL = "protocol/asset_contracts.json"
EXPORT_REL = "protocol/generated/asset_contract.frictionless.json"
SCHEMA_REL = "protocol/schema/asset_contracts.schema.json"
SCHEMA = "nf-asset-contracts/1"
FACES = ("data", "code", "script", "index")
LANGS = ("python", "bash", "vba", "powershell")
FORMATS = ("json", "csv", "markdown", "text", "yaml", "toml", "jsonl",
           "graphml", "mmd")
#: 脚本自带 I/O 契约头：Python/Bash 用 #，VBA 用单引号——同一条 nf-io: 声明格式；
#: 不锚行首：允许挂在既有注释行尾（不新增行 ⇒ 不触发 code_metrics 行数棘轮）。
_IO_RE = re.compile(r"(?:#|')[ \t]*nf-io:[ \t]*(.+?)[ \t]*$", re.M)
_MISSING = object()


# ---------------------------------------------------------------- 基础
def _strict_json(text: str) -> Any:
    """严格如 RFC 8259：NaN/Infinity 不是 JSON 常量，出现即报错（不静默收下）。"""
    return json_doc.loads(text, dict, what="资产契约文本", strict_constants=True)


def digest_of(path: Path) -> str:
    """文件内容摘要（防篡改判据的单一口径：sha256 十六进制）。"""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read(root: str, rel: str) -> Tuple[Optional[str], Optional[str]]:
    """读文本件 → (text, issue)。缺件/不可读不抛裸异常，如实报问题（扫描要能出报告）。"""
    p = Path(root) / rel
    try:
        return p.read_text(encoding="utf-8"), None
    except OSError as exc:
        return None, "读不到 %s：%s（修复指引：核对声明里的路径在场）" % (rel, exc)
    except UnicodeDecodeError as exc:
        return None, "%s 不是 UTF-8：%s（修复指引：转成 UTF-8 再入库）" % (rel, exc)


#: root → 受跟踪文件集（或 None = 非 git 仓根）。一次进程内记忆：同一根只问一次 git。
_TRACKED: dict[str, set | None] = {}


def _tracked_files(root: str) -> set | None:
    """→ 仓库**受跟踪**文件集（仓库根相对 posix 路径）；root 不是 git 仓根 → None。

    为什么需要（2026-10-22 基线修复）：`glob` 会把**构建产物**也算进 `files` 统计——实测
    `engine/dotnet/**/*.cs` 在「build 过」的树上多出 3–9 个 `obj/` 生成件，于是同一个提交
    在不同机器上得到不同的 `files` 计数，机器可读报告（root_digest）因此**不可复核**。
    只认受跟踪件 ⇒ 计数与「build 没 build」无关（生成物不是仓库内容）。
    非 git 仓根（单测夹具 / 临时树）保持原语义：按文件系统 glob（不能因为夹具没 .git 就判空）。
    """
    key = os.path.normcase(os.path.abspath(str(root)))
    if key in _TRACKED:
        return _TRACKED[key]
    got: set | None = None
    try:
        top = subprocess.run(["git", "-C", key, "rev-parse", "--show-toplevel"],
                             capture_output=True, text=True, encoding="utf-8",
                             timeout=120)
        if top.returncode == 0 and top.stdout.strip():
            top_path = os.path.normcase(os.path.abspath(top.stdout.strip()))
            if top_path == key:            # **仓根**才按跟踪面收窄（子目录夹具照旧走 glob）
                ls = subprocess.run(["git", "-C", key, "ls-files", "-z"],
                                    capture_output=True, timeout=120)
                if ls.returncode == 0:
                    got = {x.replace("\\", "/") for x in
                           ls.stdout.decode("utf-8", "replace").split("\0") if x}
    except (OSError, subprocess.SubprocessError):
        got = None
    _TRACKED[key] = got
    return got


def resolve(root: str, spec: Dict[str, Any]) -> List[str]:
    """声明 → 命中的仓库相对路径列表（`path` 单件 / `glob` 多件，后者稳定排序）。

    `glob` 命中面按**受跟踪件**收窄（见 `_tracked_files`）：构建产物不算契约面。
    """
    r = Path(root)
    if spec.get("path"):
        rel = str(spec["path"]).replace("\\", "/")
        return [rel] if (r / rel).is_file() else []
    pat = str(spec.get("glob") or "")
    if not pat:
        return []
    hits = [p for p in r.glob(pat) if p.is_file()]
    tracked = _tracked_files(root)
    if tracked is not None:
        hits = [p for p in hits if p.relative_to(r).as_posix() in tracked]
    return sorted(p.relative_to(r).as_posix() for p in hits)


def _dig(obj: Any, path: str) -> Any:
    """按点号路径取值（dict 键 / list 下标）；取不到返回哨兵（不抛异常）。"""
    cur = obj
    for part in str(path).split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        elif isinstance(cur, list) and part.isdigit() and int(part) < len(cur):
            cur = cur[int(part)]
        else:
            return _MISSING
    return cur


# ---------------------------------------------------------------- 数据面
def _data_json(root: str, rel: str, text: str, spec: Dict[str, Any]
               ) -> Tuple[List[str], Dict[str, Any]]:
    issues: List[str] = []
    stats: Dict[str, Any] = {}
    try:
        obj = _strict_json(text)
    except ValueError as exc:
        return ["数据件 %s 不是合法 JSON：%s（修复指引：修好语法或换 format）" % (rel, exc)], {}
    sch_rel = str(spec.get("schema") or "")
    if not sch_rel:
        # schema 兄弟候选（D2）：按 {stem} 约定在同目录找，先命中先用；全不命中则记 no_schema
        # 并**只**跳过 schema 面（必填字段仍判）——不许把「没 schema」当成「没问题」。
        for tmpl in spec.get("schema_siblings") or []:
            cand = (Path(rel).parent / str(tmpl).replace("{stem}", Path(rel).stem)).as_posix()
            if (Path(root) / cand).is_file():
                sch_rel = cand
                break
    if sch_rel:
        sch_text, err = _read(root, sch_rel)
        if err:
            issues.append("数据件 %s 的 schema 读不到：%s" % (rel, err))
        else:
            from core import json_schema as js
            try:
                errs = js.json_schema_check(obj, _strict_json(sch_text or ""))
            except ValueError as exc:
                errs = ["schema 本身不是合法 JSON：%s" % exc]
            issues += ["数据件 %s 不符 schema %s：%s" % (rel, sch_rel, e) for e in errs[:5]]
    for field in spec.get("required_fields") or []:
        if _dig(obj, field) is _MISSING:
            issues.append("数据件 %s 缺必填字段 %s（修复指引：补字段或从声明里删掉——声明即契约）"
                          % (rel, field))
    if spec.get("schema_siblings") and not sch_rel:
        stats["no_schema"] = 1          # 可见缺口：有 schema 兄弟约定但该件没有 schema
    stats["fields"] = len(spec.get("required_fields") or [])
    return issues, stats


def _csv_rows(text: str) -> List[List[str]]:
    return [row for row in csv.reader(io.StringIO(text))]


def _data_csv(rel: str, text: str, spec: Dict[str, Any]) -> Tuple[List[str], Dict[str, Any]]:
    issues: List[str] = []
    rows = _csv_rows(text)
    if not rows:
        return ["数据件 %s 是空 CSV（修复指引：至少要有表头行）" % rel], {"rows": 0}
    header = [c.strip() for c in rows[0]]
    if any(not c for c in header):
        issues.append("数据件 %s 表头有空列名（修复指引：每列都要有名字）" % rel)
    width = len(header)
    data = [r for r in rows[1:] if r != [""]]
    bad = [i for i, r in enumerate(data, 2) if len(r) != width]
    if bad:
        issues.append("数据件 %s 第 %s 行列数 != 表头 %d（修复指引：补齐/删除多余的分隔符）"
                      % (rel, ",".join(str(b) for b in bad[:3]), width))
    missing = [c for c in spec.get("required_columns") or [] if c not in header]
    if missing:
        issues.append("数据件 %s 缺必需列 %s（修复指引：加列或改声明）" % (rel, ",".join(missing)))
    any_cols = [str(c) for c in spec.get("required_any_columns") or []]
    if any_cols and not any(c in header for c in any_cols):
        # 表头**族**各不相同（实测 CASES.csv 有 11 种表头），故只判「至少含一个」而非全等。
        issues.append("数据件 %s 表头不含任一必需列 %s（实为 %s）（修复指引：改用族内表头或改声明）"
                      % (rel, "|".join(any_cols), ",".join(header[:6])))
    low = int(spec.get("min_rows") or 0)
    if len(data) < low:
        issues.append("数据件 %s 数据行 %d < min_rows %d（修复指引：补样例或下调声明）"
                      % (rel, len(data), low))
    return issues, {"rows": len(data), "columns": width}


def _md_tables(text: str) -> List[List[List[str]]]:
    """按连续竖线行切表 → 每张表是行列表（表头 + 分隔行 + 数据行）。"""
    tables: List[List[List[str]]] = []
    cur: List[List[str]] = []
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("|") and s.count("|") >= 2:
            cur.append([c.strip() for c in s.strip("|").split("|")])
        elif cur:
            tables.append(cur)
            cur = []
    if cur:
        tables.append(cur)
    return tables


def _data_markdown(rel: str, text: str, spec: Dict[str, Any]) -> Tuple[List[str], Dict[str, Any]]:
    issues: List[str] = []
    if spec.get("frontmatter") and not text.startswith("---"):
        issues.append("数据件 %s 缺 frontmatter（修复指引：件首补 --- 块）" % rel)
    n = 0
    for table in _md_tables(text):
        if len(table) < 2:
            continue
        header = table[0]
        body = [r for r in table[1:] if not all(set(c) <= set("-:") for c in r)]
        ragged = [r for r in body if len(r) != len(header)]
        if ragged:
            issues.append("数据件 %s 有一张表列数不齐：表头 %d 列 vs 数据 %d 列（修复指引：对齐竖线"
                "）"
                          % (rel, len(header), len(ragged[0])))
        n += 1
    return issues, {"tables": n}


def _data_link(root: str, rel: str, spec: Dict[str, Any], obj: Any) -> List[str]:
    """输入输出一致性：路径字段指向的文件必须在场，其行数必须等于计数字段。"""
    link = spec.get("link") or {}
    issues: List[str] = []
    target = _dig(obj, str(link.get("path_field") or ""))
    if not isinstance(target, str) or not target:
        return ["数据件 %s 的 link.path_field=%s 取不到字符串路径（修复指引：核对字段名）"
                % (rel, link.get("path_field"))]
    rel_dir = Path(rel).parent
    bases = [str(link.get("base"))] if link.get("base") else [str(rel_dir), str(rel_dir.parent)]
    found = None
    for base in bases:
        cand = Path(root) / base / target
        if cand.is_file():
            found = cand
            break
    if found is None:
        return ["数据件 %s 指向的 %s 不在场（修复指引：补件或修正 link.base）" % (rel, target)]
    rows_field = str(link.get("rows_field") or "")
    if rows_field:
        want = _dig(obj, rows_field)
        got = len(_csv_rows(found.read_text(encoding="utf-8"))[1:])
        if want != got:
            issues.append("数据件 %s 的 %s=%s 与 %s 数据行 %d 不一致（修复指引：重算或改声明）"
                          % (rel, rows_field, want, target, got))
    return issues


#: Mermaid 图的首关键词（结构判据：只认「这是一张什么图」，不解析图内容）
_MMD_KINDS = ("graph", "flowchart", "sequenceDiagram", "classDiagram", "stateDiagram",
              "erDiagram", "gantt", "pie", "mindmap", "timeline", "journey", "gitGraph",
              "quadrantChart", "xychart-beta", "requirementDiagram", "C4Context", "block-beta")


def _schema_of(root: str, rel: str, spec: Dict[str, Any]) -> str:
    """声明的 schema 路径：显式 `schema` 优先，其次 `schema_siblings` 里第一个在场的兄弟候选。"""
    sch = str(spec.get("schema") or "")
    if sch:
        return sch
    for tmpl in spec.get("schema_siblings") or []:
        cand = (Path(rel).parent / str(tmpl).replace("{stem}", Path(rel).stem)).as_posix()
        if (Path(root) / cand).is_file():
            return cand
    return ""


def _schema_issues(root: str, rel: str, obj: Any, sch_rel: str) -> List[str]:
    """按 schema 校验已解析对象（四格式共用：YAML/TOML 解析后与 JSON 同一数据模型）。"""
    from core import json_schema as js
    sch_text, err = _read(root, sch_rel)
    if err:
        return ["数据件 %s 的 schema 读不到：%s" % (rel, err)]
    try:
        errs = js.json_schema_check(obj, _strict_json(sch_text))
    except ValueError as exc:
        errs = ["schema 本身不是合法 JSON：%s" % exc]
    return ["数据件 %s 不符 schema %s：%s" % (rel, sch_rel, e) for e in errs[:5]]


def _fields_issues(rel: str, obj: Any, spec: Dict[str, Any]) -> List[str]:
    return ["数据件 %s 缺必填字段 %s（修复指引：补字段或从声明里删掉——声明即契约）" % (rel, f)
            for f in spec.get("required_fields") or [] if _dig(obj, f) is _MISSING]


def _data_yaml(root: str, rel: str, text: str,
               spec: Dict[str, Any]) -> Tuple[List[str], Dict[str, Any]]:
    """YAML 数据件：复用仓库既有懒加载 YAML（软依赖），解析后与 JSON 同判据。"""
    from core import lazy_yaml
    ymod = lazy_yaml.module()                # 惰性入口：缺 PyYAML 时返回 None（不是即报）
    if ymod is None:
        # 契约判据**不许**在缺依赖时静默放行（那等于假绿）：报缺口并给安装指引。
        return ["数据件 %s 未判：PyYAML 不在场"
                "（修复指引：pip install pyyaml，或改成 format=text）"
                % rel], {"yaml_unavailable": 1}
    try:
        loader = lazy_yaml.safe_loader()
        obj = ymod.load(text, Loader=loader) if loader is not None else ymod.safe_load(text)
    except Exception as exc:                                  # noqa: BLE001 —— 解析器异常按坏件报
        return ["数据件 %s 不是合法 YAML：%s（修复指引：修好缩进/语法）"
                % (rel, exc)], {}
    issues: List[str] = []
    sch = _schema_of(root, rel, spec)
    if sch:
        issues += _schema_issues(root, rel, obj, sch)
    issues += _fields_issues(rel, obj, spec)
    return issues, {"fields": len(spec.get("required_fields") or [])}


def _data_toml(root: str, rel: str, text: str,
               spec: Dict[str, Any]) -> Tuple[List[str], Dict[str, Any]]:
    """TOML 数据件：stdlib `tomllib`（3.11+）；解析后同 JSON 判据。"""
    import tomllib
    try:
        obj = tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        return ["数据件 %s 不是合法 TOML：%s（修复指引：修好语法或换 format）" % (rel, exc)], {}
    issues: List[str] = []
    sch = _schema_of(root, rel, spec)
    if sch:
        issues += _schema_issues(root, rel, obj, sch)
    issues += _fields_issues(rel, obj, spec)
    return issues, {"fields": len(spec.get("required_fields") or [])}


def _data_jsonl(rel: str, text: str, spec: Dict[str, Any]) -> Tuple[List[str], Dict[str, Any]]:
    """JSONL：**逐行**严格 JSON（空行跳过）；必填字段对每一行判。"""
    issues: List[str] = []
    rows = 0
    for i, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            continue
        rows += 1
        try:
            obj = _strict_json(line)
        except ValueError as exc:
            issues.append("数据件 %s 第 %d 行不是合法 JSON：%s（修复指引：一行一条）"
                          % (rel, i, exc))
            continue
        for f in spec.get("required_fields") or []:
            if _dig(obj, f) is _MISSING:
                issues.append("数据件 %s 第 %d 行缺必填字段 %s（修复指引：补字段）"
                              % (rel, i, f))
    if spec.get("min_rows") and rows < int(spec["min_rows"]):
        issues.append("数据件 %s 行数 %d < min_rows %s（修复指引：补样例或下调声明）"
                      % (rel, rows, spec["min_rows"]))
    return issues, {"rows": rows}


def _data_graphml(rel: str, text: str, spec: Dict[str, Any]) -> Tuple[List[str], Dict[str, Any]]:
    """GraphML：XML 良构 + 节点/边计数（图结构资产的可证那部分）。

    解析前的**拒收门槛**：含 DTD / 实体声明的图件直接拒——Billion-Laughs / XXE 的载体都在那两处，
    而本层处理的是仓内资产（非不可信输入），故 `# nosec` 的例外只需覆盖「标准库 XML 解析」本身，
    不覆盖实体展开（那条已在入口拒掉）。
    """
    if re.search(r"<!DOCTYPE|<!ENTITY", text):
        return ["数据件 %s 含 DTD/实体声明，拒绝解析（修复指引：去掉 DOCTYPE/ENTITY——导出工具重跑）"
                % rel], {}
    import xml.etree.ElementTree as ET  # nosec B405 —— 见函数自述：入口已拒 DTD/ENTITY
    try:
        root_el = ET.fromstring(text)        # nosec B314  # noqa: S314
    except ET.ParseError as exc:
        return ["数据件 %s 不是良构 XML：%s（修复指引：修好 XML）" % (rel, exc)], {}
    ns = {"g": "http://graphml.graphdrawing.org/xmlns"}
    nodes = len(root_el.findall(".//g:node", ns)) or len(root_el.findall(".//node"))
    edges = len(root_el.findall(".//g:edge", ns)) or len(root_el.findall(".//edge"))
    issues: List[str] = []
    if spec.get("min_nodes") and nodes < int(spec["min_nodes"]):
        issues.append("数据件 %s 节点数 %d < min_nodes %s（修复指引：补结构或下调声明）"
                      % (rel, nodes, spec["min_nodes"]))
    return issues, {"nodes": nodes, "edges": edges}


def _data_mmd(rel: str, text: str, spec: Dict[str, Any]) -> Tuple[List[str], Dict[str, Any]]:
    """Mermaid：首关键词须是合法图型（结构判据，不解析图内容）。"""
    first = ""
    for line in text.splitlines():
        s = line.strip()
        if s and not s.startswith("%%"):
            first = s.split()[0] if s.split() else ""
            break
    if not first:
        return ["数据件 %s 是空 Mermaid 图（修复指引：补图声明）" % rel], {}
    base = first.split("-")[0] if first.startswith(("xychart", "block")) else first
    if first not in _MMD_KINDS and base not in _MMD_KINDS:
        return ["数据件 %s 首关键词 %r 不是合法 Mermaid 图型"
                "（修复指引：用 graph/flowchart/sequenceDiagram 等）"
                % (rel, first)], {}
    return [], {"kind": first}



def _check_data(root: str, spec: Dict[str, Any]) -> Tuple[List[str], Dict[str, Any]]:
    sid = str(spec.get("id") or spec.get("path") or spec.get("glob") or "?")
    rels = resolve(root, spec)
    if not rels:
        return (["数据契约 %s 未命中任何文件（修复指引：修正 path/glob —— 空气不是契约）" % sid],
                {"files": 0})
    fmt = str(spec.get("format") or "").lower()
    if fmt not in FORMATS:
        return (["数据契约 %s 的 format=%r 不在词表 %s（修复指引：改用词表内格式）"
                 % (sid, fmt, "/".join(FORMATS))], {"files": len(rels)})
    if spec.get("sha256") and len(rels) != 1:
        return (["数据契约 %s 声明了 sha256 却命中 %d 件（修复指引：sha256 只用于 path 单件）"
                 % (sid, len(rels))], {"files": len(rels)})
    issues: List[str] = []
    stats: Dict[str, Any] = {"files": len(rels), "format": fmt}
    for rel in rels:
        text, err = _read(root, rel)
        if err:
            issues.append(err)
            continue
        text = text or ""
        obj: Any = None
        if fmt == "json":
            sub, s = _data_json(root, rel, text, spec)
            try:
                obj = _strict_json(text)
            except ValueError:
                obj = None
        elif fmt == "csv":
            sub, s = _data_csv(rel, text, spec)
        elif fmt == "markdown":
            sub, s = _data_markdown(rel, text, spec)
        elif fmt == "yaml":
            sub, s = _data_yaml(root, rel, text, spec)
        elif fmt == "toml":
            sub, s = _data_toml(root, rel, text, spec)
        elif fmt == "jsonl":
            sub, s = _data_jsonl(rel, text, spec)
        elif fmt == "graphml":
            sub, s = _data_graphml(rel, text, spec)
        elif fmt == "mmd":
            sub, s = _data_mmd(rel, text, spec)
        else:
            sub, s = [], {"lines": len(text.splitlines())}
        issues += sub
        for _k in ("no_schema", "yaml_unavailable"):
            if s.get(_k):
                stats[_k] = int(stats.get(_k) or 0) + 1
                s = {k: v for k, v in s.items() if k != _k}
        stats.update(s)
        if spec.get("sha256"):
            got = digest_of(Path(root) / rel)
            if got != str(spec["sha256"]):
                issues.append("数据件 %s 摘要不符（记录 %s / 实测 %s）（修复指引：核对改动，"
                              "确认后用 nf asset contract --freeze 重冻）"
                              % (rel, str(spec["sha256"])[:12], got[:12]))
        if spec.get("link") and obj is not None:
            issues += _data_link(root, rel, spec, obj)
    return issues, stats


# ---------------------------------------------------------------- 代码面
def _walk_scope(node: ast.AST) -> Iterable[ast.AST]:
    """遍历作用域内节点，**不进入**嵌套函数/lambda（各自另算，避免跨作用域误判）。"""
    stack = [node]
    while stack:
        cur = stack.pop()
        if isinstance(cur, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)):
            continue
        yield cur
        stack.extend(ast.iter_child_nodes(cur))


def _assigned_names(node: ast.AST) -> set:
    out = set()
    for n in _walk_scope(node):
        if isinstance(n, ast.Assign):
            out |= {t.id for t in n.targets if isinstance(t, ast.Name)}
        elif isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name):
            out.add(n.target.id)
        elif isinstance(n, ast.AugAssign) and isinstance(n.target, ast.Name):
            out.add(n.target.id)
        elif isinstance(n, (ast.For, ast.AsyncFor)) and isinstance(n.target, ast.Name):
            out.add(n.target.id)
        elif isinstance(n, ast.withitem) and isinstance(n.optional_vars, ast.Name):
            out.add(n.optional_vars.id)
    return out


def _is_none(node: Optional[ast.AST]) -> bool:
    return isinstance(node, ast.Constant) and node.value is None


def _assigns_none(stmt: ast.AST, name: str) -> bool:
    """该赋值语句是否把 name 明确置为 None（可证）。"""
    if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1:
        tgt = stmt.targets[0]
        return isinstance(tgt, ast.Name) and tgt.id == name and _is_none(stmt.value)
    if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
        return stmt.target.id == name and _is_none(stmt.value)
    return False


def _guard(stmt: ast.AST) -> Optional[Tuple[str, str]]:
    """识别 `x is None` / `x is not None` → (名字, is-none | is-not-none)。"""
    test = getattr(stmt, "test", None)
    if not isinstance(test, ast.Compare) or len(test.ops) != 1 or len(test.comparators) != 1:
        return None
    if not isinstance(test.left, ast.Name) or not _is_none(test.comparators[0]):
        return None
    if isinstance(test.ops[0], ast.Is):
        return (test.left.id, "is-none")
    if isinstance(test.ops[0], ast.IsNot):
        return (test.left.id, "is-not-none")
    return None


def _always_exits(stmts: List[ast.stmt]) -> bool:
    if not stmts:
        return False
    last = stmts[-1]
    if isinstance(last, (ast.Return, ast.Raise, ast.Continue, ast.Break)):
        return True
    return (isinstance(last, ast.If) and bool(last.orelse)
            and _always_exits(last.body) and _always_exits(last.orelse))


def _head_exprs(stmt: ast.AST) -> List[ast.AST]:
    """语句**自身**要立刻求值的表达式（复合语句只取条件/迭代表达式，不含子块）。

    子块由 _scan_block 带各自状态扫描；这里只取头部表达式，避免把「分支里先重新赋值再解引用」
    错判成外层 None 的解引用（宁少勿滥）。
    """
    if isinstance(stmt, (ast.If, ast.While)):
        return [stmt.test]
    if isinstance(stmt, (ast.For, ast.AsyncFor)):
        return [stmt.iter]
    if isinstance(stmt, (ast.With, ast.AsyncWith)):
        return [i.context_expr for i in stmt.items]
    if isinstance(stmt, (ast.Try, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        return []
    return [stmt]


def _derefs(stmt: ast.AST, names: set) -> List[int]:
    """该语句头部对「当前可证为 None」的名字做的解引用行号（属性/下标/调用）。"""
    out = []
    for head in _head_exprs(stmt):
        for n in _walk_scope(head):
            if (isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name)
                    and n.value.id in names):
                out.append(n.lineno)
            elif (isinstance(n, ast.Subscript) and isinstance(n.value, ast.Name)
                  and n.value.id in names):
                out.append(n.lineno)
            elif isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in names:
                out.append(n.lineno)
    return out


def _scan_block(stmts: List[ast.stmt], cur: set, rel: str,
                out: List[Tuple[str, int, str]]) -> set:
    """顺序扫描一个语句块；**不跨分支并入**（只判同一序列内可证的 None 解引用）。

    复合语句（if/for/while/with/try）只在各自子块里检测，不把子块的 None 状态并回外层；
    分支里可能发生的重新赋值则从外层状态里扣除（保守方向：宁少勿滥）。
    """
    cur = set(cur)
    for st in stmts:
        for lineno in _derefs(st, cur):
            out.append((rel, lineno, ",".join(sorted(cur))))
        if isinstance(st, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
            for name in _assigned_names(st):
                (cur.add if _assigns_none(st, name) else cur.discard)(name)
        elif isinstance(st, ast.Assert):
            g = _guard(st)
            if g and g[1] == "is-not-none":
                cur.discard(g[0])
        elif isinstance(st, ast.If):
            g = _guard(st)
            if g and g[1] == "is-not-none":
                _scan_block(st.body, cur - {g[0]}, rel, out)
                _scan_block(st.orelse, cur, rel, out)
            elif g and g[1] == "is-none":
                _scan_block(st.body, cur, rel, out)
                _scan_block(st.orelse, cur - {g[0]}, rel, out)
            else:
                _scan_block(st.body, cur, rel, out)
                _scan_block(st.orelse, cur, rel, out)
            if g and g[1] == "is-none" and _always_exits(st.body):
                cur.discard(g[0])
            cur -= _assigned_names(st)
        elif isinstance(st, (ast.For, ast.AsyncFor, ast.While, ast.With, ast.AsyncWith)):
            _scan_block(st.body, cur, rel, out)
            cur -= _assigned_names(st)
        elif isinstance(st, ast.Try):
            _scan_block(st.body, cur, rel, out)
            for handler in st.handlers:
                _scan_block(handler.body, cur, rel, out)
            _scan_block(st.orelse, cur, rel, out)
            _scan_block(st.finalbody, cur, rel, out)
            cur -= _assigned_names(st)
    return cur


def _none_deref(tree: ast.AST, rel: str) -> List[str]:
    """可证空指针：x = None（或默认参数 None）之后在同一语句序列里解引用 x。"""
    out: List[Tuple[str, int, str]] = []
    seeds: List[Any] = [(list(getattr(tree, "body", [])), set())]
    for fn in ast.walk(tree):
        if isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            default_none = set()
            pos = list(fn.args.posonlyargs) + list(fn.args.args)
            pos_defaults = list(fn.args.defaults)
            # 位置默认值对应**尾部**参数（python 语义）——首版错配到头部，把普通形参也当成
            # None 默认（实测 json_schema._check 假红 37 条）；kw_defaults 与 kwonlyargs 一一对应。
            pairs: List[Tuple[ast.arg,
 Any]] = list(zip(pos[len(pos) - len(pos_defaults):],
 pos_defaults))
            pairs += list(zip(fn.args.kwonlyargs, fn.args.kw_defaults))
            for arg, default in pairs:
                if _is_none(default):
                    default_none.add(arg.arg)
            seeds.append((fn.body, default_none))
    for body, seed in seeds:
        _scan_block(body, seed, rel, out)
    msgs = []
    seen = set()
    for rel_name, lineno, names in sorted(out, key=lambda x: x[1]):
        if (lineno, names) in seen:
            continue
        seen.add((lineno, names))
        msgs.append("代码件 %s 第 %d 行解引用可证为 None 的 %s（修复指引：解引用前判空，或把初始值"
                    "改成真实对象——同一语句序列内没有任何重新赋值）" % (rel_name, lineno, names))
    return msgs


def _dotted(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _dotted(node.value)
        return "%s.%s" % (base, node.attr) if base else node.attr
    return ""


def _denied_calls(tree: ast.AST, rel: str, deny: set) -> List[str]:
    out = []
    for n in ast.walk(tree):
        if isinstance(n, ast.Call):
            name = _dotted(n.func)
            if name and name in deny:
                out.append("代码件 %s 第 %d 行调用了禁用面 %s（修复指引：换用不执行任意代码的等价实"
                    "现；"
                           "确需保留须改声明并写明理由）" % (rel, n.lineno, name))
    return out


def _check_tests(root: str, rel: str, spec: Dict[str, Any]) -> List[str]:
    issues = []
    stem = Path(rel).stem
    if not spec.get("tests"):
        issues.append("代码件 %s 未声明测试件（修复指引：补 tests 列表——没有用例的代码资产不算"
                      "通过测试）" % rel)
    for t in spec.get("tests") or []:
        trel = str(t).replace("\\", "/")
        p = Path(root) / trel
        if not p.is_file():
            issues.append("代码件 %s 声明的测试件不在场：%s（修复指引：先写测试再登记）" % (rel,
 trel))
            continue
        text = p.read_text(encoding="utf-8", errors="replace")
        try:
            ast.parse(text)
        except SyntaxError as exc:
            issues.append("测试件 %s 语法坏：%s（修复指引：先修语法）" % (trel, exc))
            continue
        if stem not in text:
            issues.append("测试件 %s 未点名被测模块 %s（修复指引：在测试里 import 或引用该模块）"
                          % (trel, stem))
    return issues


def _code_structural(root: str, spec: Dict[str, Any]) -> Tuple[List[str], Dict[str, Any]]:
    """第二实现线的**结构契约**（E2）：不做完整 AST，只判可证的正则面（禁用式 / 计数上限）。

    为什么：`engine/**` 在职能坐标里是 verify（只读判据的第二实现），而代码面此前只有 Python AST。
    完整 Rust/C# 语法树不在本层能力内（ADR-0005 的范围划分），故只声明**范围**与**只减不增**的计数——
    这比「装作 AST 判过」诚实，也比不判多一层门。
    """
    sid = str(spec.get("id") or "?")
    rels = resolve(root, spec)
    if not rels:
        return ["代码契约 %s 未命中任何文件（修复指引：修正 path/glob）" % sid], {"files": 0}
    texts = []
    for rel in rels:
        text, err = _read(root, rel)
        if err:
            return [err], {"files": len(rels)}
        texts.append((rel, text))
    issues: List[str] = []
    stats: Dict[str, Any] = {"files": len(rels)}
    for rule in spec.get("forbid_regex") or []:
        rx = re.compile(str(rule.get("pattern") or ""))
        hits = ["%s:%d" % (rel, text.count(chr(10), 0, m.start()) + 1)
                for rel, text in texts for m in rx.finditer(text)]
        stats["forbid:%s" % rule.get("name")] = len(hits)
        if hits:
            issues.append("代码契约 %s 命中禁用式 %s（%d 处，例 %s）（修复指引：%s）"
                          % (sid, rule.get("name"), len(hits), "、".join(hits[:3]),
                             rule.get("why") or "换成不越界的等价实现"))
    for rule in spec.get("regex_limits") or []:
        rx = re.compile(str(rule.get("pattern") or ""))
        n = sum(len(rx.findall(text)) for _rel, text in texts)
        cap = int(rule.get("max") or 0)
        stats["limit:%s" % rule.get("name")] = n
        if n > cap:
            issues.append("代码契约 %s 的 %s 计数 %d > 上限 %d（棘轮只减不增）"
                          "（修复指引：先降后改声明）"
                          % (sid, rule.get("name"), n, cap))
    return issues, stats


def _check_code(root: str, spec: Dict[str, Any]) -> Tuple[List[str], Dict[str, Any]]:
    if spec.get("forbid_regex") or spec.get("regex_limits"):
        return _code_structural(root, spec)
    rel = str(spec.get("path") or "")
    if str(spec.get("lang") or "python") != "python":
        return (["代码契约 %s 的 lang=%s 不在支持面（仅 python 走 AST；Bash/VBA 走脚本面声明式契约"
            "）"
                 % (spec.get("id"), spec.get("lang"))], {})
    rels = resolve(root, spec)
    if not rels:
        return (["代码契约 %s 未命中任何文件（修复指引：修正 path/glob）" % spec.get("id")],
 {"files": 0})
    issues: List[str] = []
    stats: Dict[str, Any] = {"files": len(rels)}
    deny = {str(x) for x in spec.get("deny_calls") or []}
    for one in rels:
        text, err = _read(root, one)
        if err:
            issues.append(err)
            continue
        text = text or ""
        try:
            tree = ast.parse(text)
        except SyntaxError as exc:
            issues.append("代码件 %s 语法坏：%s（修复指引：先修语法，AST 判据需要可解析的树）"
                          % (one, exc))
            continue
        issues += _denied_calls(tree, one, deny)
        issues += _none_deref(tree, one)
    if rel:
        issues += _check_tests(root, rel, spec)
    return issues, stats


# ---------------------------------------------------------------- 脚本面
def parse_io_header(text: str) -> Optional[Dict[str, List[str]]]:
    """解析脚本自带 nf-io 头 → {"inputs": [...], "outputs": [...]}；没有头返回 None。

    格式（三种语言同一写法，注释符不同）：# nf-io: inputs=a,b outputs=c；- 表示空。
    """
    m = _IO_RE.search(text)
    if not m:
        return None
    out: Dict[str, List[str]] = {"inputs": [], "outputs": []}
    for token in m.group(1).split():
        if "=" not in token:
            continue
        key, val = token.split("=", 1)
        key = key.strip().lower()
        if key not in out:
            continue
        out[key] = [] if val.strip() in ("-", "") else \
            [x.strip() for x in val.split(",") if x.strip()]
    return out


def observed_paths(text: str, lang: str) -> List[str]:
    """脚本里**字面量**形式的文件路径（可证的那部分；变量拼出来的不判）。"""
    out: List[str] = []
    if lang == "python":
        try:
            tree = ast.parse(text)
        except SyntaxError:
            return out
        for n in ast.walk(tree):
            if not isinstance(n, ast.Call):
                continue
            if _dotted(n.func) not in ("open", "Path", "pathlib.Path"):
                continue
            for a in n.args:
                if isinstance(a, ast.Constant) and isinstance(a.value, str):
                    out.append(a.value)
    elif lang == "bash":
        for m in re.finditer(r">>?[ \t]*([^\s;|&()]+)|<[ \t]*([^\s;|&()]+)", text):
            out.append(m.group(1) or m.group(2) or "")
    elif lang == "powershell":
        # `#` 注释与 bash 同形（parse_io_header 已覆盖）；路径取字面量的重定向/读写 cmdlet。
        for m in re.finditer(r"(?:>>?|Out-File|Set-Content|Add-Content|Get-Content|Import-Csv)"
                             r"[ \t]+([^\s;|&()\[\]$]+)", text):
            out.append(m.group(1))
    elif lang == "vba":
        for m in re.finditer(r'(?i)\bOpen\s+"([^"]+)"', text):
            out.append(m.group(1))
    skip = {"/dev/null", "/dev/stdin", "/dev/stdout", "-"}
    return [p for p in out if p and p not in skip and not p.startswith("$")]


def _check_script(root: str, spec: Dict[str, Any]) -> Tuple[List[str], Dict[str, Any]]:
    sid = str(spec.get("id") or spec.get("path") or "?")
    lang = str(spec.get("lang") or "")
    if lang not in LANGS:
        return (["脚本契约 %s 的 lang=%r 不在词表 %s（修复指引：改用词表内语言）"
                 % (sid, lang, "/".join(LANGS))], {})
    rel = str(spec.get("path") or "")
    if not (Path(root) / rel).is_file():
        return (["脚本契约 %s 的件不在场：%s（修复指引：修正 path）" % (sid, rel)], {"files": 0})
    text, err = _read(root, rel)
    if err:
        return [err], {"files": 1}
    text = text or ""
    issues: List[str] = []
    header = parse_io_header(text)
    if header is None:
        issues.append("脚本 %s 未自带 nf-io 头（修复指引：顶部加一行注释 # nf-io: inputs=a,b "
                      "outputs=c；VBA 用单引号起头——脚本契约必须双源）" % rel)
        header = {"inputs": [], "outputs": []}
    for key in ("inputs", "outputs"):
        declared = list(spec.get(key) or [])
        embedded = list(header.get(key) or [])
        if declared != embedded:
            issues.append("脚本 %s 的 %s 双源不一致：声明=%s / 头=%s（修复指引：让两边逐字一致）"
                          % (rel, key, declared, embedded))
    declared_all = set(spec.get("inputs") or []) | set(spec.get("outputs") or [])
    extra = sorted({x for x in observed_paths(text, lang) if x not in declared_all})
    if extra:
        issues.append("脚本 %s 出现未声明的字面路径 %s（修复指引：补进 inputs/outputs 或去掉硬编码"
            "）"
                      % (rel, ",".join(extra[:3])))
    return issues, {"files": 1, "inputs": len(spec.get("inputs") or []),
                    "outputs": len(spec.get("outputs") or [])}


def _check_index(root: str, spec: Dict[str, Any]) -> Tuple[List[str], Dict[str, Any]]:
    """S1 包自述契约：读包自己的 `outputs/INDEX.json`，与**磁盘实况**双向对账。

    为什么归到「资产契约」：包清单（`nf-output-index/1`）本就是**包自带**的产出面契约
    （path / form / tier / role / schema / inputs）。NF 侧再拿 glob 猜一遍就是两套词表；本判据让
    **声明**与**实况**互相对齐——声明的件必须在场，`outputs/` 下的实况必须都被声明。
    """
    sid = str(spec.get("id") or "?")
    rels = resolve(root, spec)
    if not rels:
        return ["包清单契约 %s 未命中任何清单（修复指引：修正 glob）" % sid], {"files": 0}
    issues: List[str] = []
    declared_total = 0
    for rel in rels:
        text, err = _read(root, rel)
        if err:
            issues.append(err)
            continue
        try:
            doc = _strict_json(text)
        except ValueError as exc:
            issues.append("包清单 %s 不是合法 JSON：%s（修复指引：重跑 nf domain build）"
                          % (rel, exc))
            continue
        base = Path(rel).parent.parent          # <包>/outputs/INDEX.json → <包>
        outs = doc.get("outputs")
        if not isinstance(outs, list) or not outs:
            issues.append("包清单 %s 的 outputs 为空（修复指引：重跑 nf domain build）" % rel)
            continue
        declared = set()
        for item in outs:
            if not isinstance(item, dict):
                continue
            pth = str(item.get("path") or "")
            if not pth:
                issues.append("包清单 %s 有一条无 path 的声明（修复指引：补 path）" % rel)
                continue
            declared.add(pth)
            declared_total += 1
            if not (Path(root) / base / pth).is_file():
                issues.append("包清单 %s 声明的 %s 不在场"
                              "（修复指引：补件或重跑 nf domain build）" % (rel, pth))
            sch = str(item.get("schema") or "")
            if sch and not (Path(root) / base / sch).is_file():
                issues.append("包清单 %s 声明的 schema %s 不在场（修复指引：补件）" % (rel, sch))
            ins = item.get("inputs") or ((item.get("recompute") or {}).get("inputs") or [])
            for inp in ins:
                if not (Path(root) / base / str(inp)).is_file():
                    issues.append("包清单 %s 声明的输入 %s 不在场"
                                  "（修复指引：补件或改声明）" % (rel, inp))
        on_disk = {q.relative_to(Path(root) / base).as_posix()
                   for q in sorted((Path(root) / base / "outputs").rglob("*")) if q.is_file()}
        self_rel = Path(rel).relative_to(base).as_posix()   # 清单自身不是产出面（它是清单）
        missing = sorted(x for x in on_disk
                         if x not in declared and x != self_rel
                         and not x.startswith("outputs/samples/"))
        if missing:
            issues.append("包清单 %s 未声明 %d 件实况（例 %s）"
                          "（修复指引：重跑 nf domain build 让清单与实况同步）"
                          % (rel, len(missing), "、".join(missing[:3])))
    return issues, {"files": len(rels), "declared": declared_total}


def _check_chain(specs: Dict[str, Dict[str, Any]], chain: Dict[str, Any]
                 ) -> Tuple[List[str], Dict[str, Any]]:
    a_id, b_id = str(chain.get("from") or ""), str(chain.get("to") or "")
    if a_id not in specs or b_id not in specs:
        return (["链 %s→%s 的端点未在脚本面登记（修复指引：先登记两端脚本契约）" % (a_id,
 b_id)],
 {})
    a, b = specs[a_id], specs[b_id]
    ao = [str(x).replace("\\", "/") for x in a.get("outputs") or []]
    bi = [str(x).replace("\\", "/") for x in b.get("inputs") or []]
    issues: List[str] = []
    feeds = chain.get("feeds") or []
    if feeds:
        for f in feeds:
            out_p = str(f.get("output") or "").replace("\\", "/")
            in_p = str(f.get("input") or "").replace("\\", "/")
            if out_p not in ao:
                issues.append("链 %s→%s：上游未声明产物 %s（修复指引：补进上游 outputs）"
                              % (a_id, b_id, out_p))
            if in_p not in bi:
                issues.append("链 %s→%s：下游未声明该输入 %s（修复指引：补进下游 inputs）"
                              % (a_id, b_id, in_p))
            if out_p != in_p:
                issues.append("链 %s→%s：产物路径不对齐（上游 %s vs 下游 %s）（修复指引：统一路径写"
                    "法）"
                              % (a_id, b_id, out_p, in_p))
    elif not set(ao) & set(bi):
        issues.append("链 %s→%s：上游产物与下游输入无交集（上游 %s / 下游 %s）（修复指引："
                      "契约未对齐——A 的输出必须匹配 B 的输入）"
                      % (a_id, b_id, ao[:3], bi[:3]))
    return issues, {"matched": len(set(ao) & set(bi))}


# ---------------------------------------------------------------- 聚合 / 入口
def _registry_issues(root: str, doc: Dict[str, Any]) -> List[str]:
    """D1 两册合一：本册声明为数据的 `protocol/` 件必须已在 `protocol/data_contracts.json` 登记。

    为什么：仓库里已有「数据契约登记册」（ODCS 式：谁判 / 谁管 / 坏了怎么重建）。资产册再造一份
    「谁管」就是第二套词表——同型病。判据只问一句：**同一 artifact 不许只在资产册出现**。
    """
    targets = [rel for spec in doc.get("data") or [] for rel in resolve(root, spec)
               if rel.startswith("protocol/") and rel.endswith(".json")]
    if not targets:
        return []                      # 本册没有 protocol 真源件 ⇒ 登记册判据不适用（临时场景常见）
    p = Path(root) / "protocol/data_contracts.json"
    if not p.is_file():
        return ["缺 protocol/data_contracts.json"
                "（修复指引：补登记册——本册有 protocol 真源件须登记）"]
    try:
        reg = _strict_json(p.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return ["protocol/data_contracts.json 不可读：%s（修复指引：修好 JSON）" % exc]
    arts = {str(c.get("artifact")) for c in (reg.get("contracts") or []) if isinstance(c, dict)}
    issues: List[str] = []
    for spec in doc.get("data") or []:
        for rel in resolve(root, spec):
            if rel.startswith("protocol/") and rel.endswith(".json") and rel not in arts:
                issues.append("资产 %s 未在 protocol/data_contracts.json 登记"
                              "（修复指引：补一条契约——"
                              "同一 artifact 不许只在资产册出现）" % rel)
                break
    return issues


def load(root: str = ".") -> Tuple[Dict[str, Any], List[str]]:
    """读契约声明件 → (doc, issues)。缺件/坏件如实报，不抛裸异常。"""
    p = Path(root) / DECL_REL
    if not p.is_file():
        return {}, ["缺数字资产契约声明 %s（修复指引：新建并写入 schema=%s 与 data/code/script 三面"
            "）"
                    % (DECL_REL, SCHEMA)]
    try:
        doc = _strict_json(p.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return {}, ["%s 不可读或不是合法 JSON：%s（修复指引：修好语法）" % (DECL_REL, exc)]
    if not isinstance(doc, dict) or doc.get("schema") != SCHEMA:
        return {}, ["%s schema 不匹配（期望 %s）（修复指引：改为声明件当前形态）" % (DECL_REL,
 SCHEMA)]
    return doc, []


_FRIENDLY = {"string": "string", "integer": "integer", "number": "number",
                      "boolean": "boolean", "array": "array", "object": "object",
                      "null": "any"}


def frictionless_export(root: str = ".") -> Tuple[Dict[str, Any], List[str]]:
    """S3 导出：把已声明的数据资产映射成 **Frictionless Data Package**（可被别的生态直接消费）。

    诚实边界：`fields` 是 JSON Schema `properties` 的**尽力映射**（类型名对齐 Frictionless Table
    Schema），原始 JSON Schema 仍在 `x-nf-json-schema` 里逐字段保留——映射丢信息就是装饰，故不丢。
    只导出**资产面**（包产物/库索引），协议层真源不外发。
    """
    doc, issues = load(root)
    if issues:
        return {}, issues
    res: List[Dict[str, Any]] = []
    for spec in doc.get("data") or []:
        if not isinstance(spec, dict):
            continue
        for rel in resolve(root, spec):
            if rel.startswith("protocol/"):
                continue
            item: Dict[str, Any] = {"name": rel.replace("/", "--"), "path": rel}
            fmt = str(spec.get("format") or "")
            if fmt:
                item["format"] = fmt
            sch_rel = _schema_of(root, rel, spec)
            if sch_rel:
                stext, err = _read(root, sch_rel)
                if not err:
                    try:
                        sch = _strict_json(stext)
                    except ValueError:
                        sch = {}
                    keep = ("type", "required", "properties", "$schema", "title", "description")
                    if sch:
                        item["x-nf-json-schema"] = {k: sch[k] for k in keep if k in sch}
                        item["x-nf-schema-source"] = sch_rel
                    fields = [{"name": k, "type": _FRIENDLY.get(str(v.get("type") or ""), "any")}
                              for k, v in sorted((sch.get("properties") or {}).items())
                              if isinstance(v, dict)]
                    if fields:
                        item["schema"] = {"fields": fields}
            res.append(item)
    return {"profile": "data-package", "name": "ninfenz-asset-contracts",
            "title": "NinFenz 数字资产契约（Frictionless Data Package 导出）",
            "x-nf-generated-by": "nf asset contract --export",
            "x-nf-note": "由已声明契约面确定性导出；领域包产物按同名 schema 约定带 fields 映射",
            "resources": res}, []


def write_export(root: str = ".") -> int:
    """落盘导出件（原子写）；返回资源数。"""
    pkg, issues = frictionless_export(root)
    if issues:
        return 0
    atomic_write.write_text(Path(root) / EXPORT_REL,
                            json.dumps(pkg, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    return len(pkg.get("resources") or [])


def _schema_self_check(root: str) -> List[str]:
    """⑤ 声明必须过**可移植 schema**（S2）：规范要可执行，不做文档摆设。"""
    sp = Path(root) / SCHEMA_REL
    if not sp.is_file():
        return ["⑤ 缺可移植 schema %s（修复指引：补该件——对外可移植契约靠它定型）" % SCHEMA_REL]
    try:
        doc = _strict_json((Path(root) / DECL_REL).read_text(encoding="utf-8"))
        sch = _strict_json(sp.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return ["⑤ 声明或 schema 不可读：%s（修复指引：修好 JSON）" % exc]
    from core import json_schema as js
    return ["⑤ 声明不符可移植 schema %s：%s（修复指引：改声明或改 schema——两者只能有一个对）"
            % (SCHEMA_REL, e) for e in js.json_schema_check(doc, sch)[:5]]


def _export_drift(root: str) -> List[str]:
    """④ 导出件 == 实时导出（缺件/漂移都 FAIL：导出面不许只在人手里新鲜）。"""
    p = Path(root) / EXPORT_REL
    live, errs = frictionless_export(root)
    if errs:
        return errs
    if not p.is_file():
        return ["④ 缺契约导出 %s（修复指引：nf asset contract --export）" % EXPORT_REL]
    try:
        disk = _strict_json(p.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return ["④ %s 不可读：%s（修复指引：nf asset contract --export）" % (EXPORT_REL, exc)]
    if disk != live:
        return ["④ %s 与实时导出不一致（修复指引：nf asset contract --export）" % EXPORT_REL]
    return []


def scan(root: str = ".", faces: Iterable[str] = ()
         ) -> Tuple[List[str], List[str], Dict[str, Any]]:
    """四面契约扫描（数据/代码/脚本/包清单）→ (issues, warns, stats)；门禁入口（check40 同源）。"""
    doc, issues = load(root)
    warns: List[str] = []
    stats: Dict[str, Any] = {f: 0 for f in FACES}
    stats.update({"files": 0, "chains": 0})
    if issues:
        return issues, warns, stats
    issues += _registry_issues(root, doc)
    if not faces:                      # ④/⑤ 是**声明面整体**判据；--face 是显式收窄，不判整体
        issues += _export_drift(root)
        issues += _schema_self_check(root)
    want = {str(x) for x in faces} or set(FACES)
    for face in FACES:
        if face not in want:
            continue
        for spec in doc.get(face) or []:
            if not isinstance(spec, dict):
                issues.append("契约 %s 面有非对象条目（修复指引：每条须是对象）" % face)
                continue
            if face == "data":
                sub, s = _check_data(root, spec)
            elif face == "code":
                sub, s = _check_code(root, spec)
            elif face == "index":
                sub, s = _check_index(root, spec)
            else:
                sub, s = _check_script(root, spec)
            issues += sub
            stats[face] += 1
            stats["files"] += s.get("files", 0)
            stats["no_schema"] = int(stats.get("no_schema") or 0) + int(s.get("no_schema") or 0)
    specs = {str(s.get("id")): s for s in doc.get("script") or [] if isinstance(s, dict)}
    if "script" in want:
        for chain in doc.get("chains") or []:
            sub, _ = _check_chain(specs, chain if isinstance(chain, dict) else {})
            issues += sub
            stats["chains"] += 1
    return issues, warns, stats


def freeze(root: str = ".") -> Tuple[List[str], Dict[str, Any]]:
    """按当前内容重冻声明的 sha256（防篡改棘轮：改动须显式重冻，不由扫描器偷偷写）。"""
    doc, issues = load(root)
    if issues:
        return issues, {"frozen": 0}
    n = 0
    for spec in doc.get("data") or []:
        if not isinstance(spec, dict) or not spec.get("sha256"):
            continue
        rel = str(spec.get("path") or "")
        p = Path(root) / rel
        if not p.is_file():
            issues.append("数据契约 %s 的 %s 不在场（修复指引：补件后再冻）" % (spec.get("id"),
 rel))
            continue
        spec["sha256"] = digest_of(p)
        n += 1
    if not issues:
        atomic_write.write_text(Path(root) / DECL_REL,
                                json.dumps(doc,
 ensure_ascii=False,
 indent=2,
 sort_keys=True) + "\n")
    return issues, {"frozen": n}


def _run_test_file(path: Path) -> Tuple[List[str], int]:
    """按路径加载一个测试件并跑它（显式开启面；门禁默认不执行被声明脚本的代码）。"""
    name = "nf_asset_contract_test_%s" % hashlib.sha256(str(path).encode("utf-8")).hexdigest()[:12]
    spec = importlib.util.spec_from_file_location(name, str(path))
    if spec is None or spec.loader is None:
        return ["测试件不可加载：%s（修复指引：核对路径与扩展名）" % path], 0
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
    except Exception as exc:                                    # noqa: BLE001 —— 测试件任意错误都记档
        return ["测试件执行失败：%s（%s: %s）（修复指引：先修测试件）"
                % (path.name, type(exc).__name__, exc)], 0
    suite = unittest.defaultTestLoader.loadTestsFromModule(mod)
    res = unittest.TextTestRunner(stream=io.StringIO(), verbosity=0).run(suite)
    issues = []
    for case, tb in list(res.failures) + list(res.errors):
        issues.append("测试未过：%s（修复指引：修到全绿；%s）"
                      % (case, tb.strip().splitlines()[-1][:160]))
    return issues, res.testsRun


def run_tests(root: str = ".", ids: Iterable[str] = ()) -> Tuple[List[str], Dict[str, Any]]:
    """跑声明的测试件（nf asset contract --run-tests）→ (issues, stats)。"""
    doc, issues = load(root)
    out: Dict[str, Any] = {"files": 0, "tests": 0}
    if issues:
        return issues, out
    want = {str(x) for x in ids}
    for spec in doc.get("code") or []:
        if not isinstance(spec, dict) or (want and str(spec.get("id")) not in want):
            continue
        for t in spec.get("tests") or []:
            p = Path(root) / str(t)
            if not p.is_file():
                issues.append("测试件不在场：%s（修复指引：先写测试再改契约）" % t)
                continue
            out["files"] += 1
            sub, ran = _run_test_file(p)
            issues += sub
            out["tests"] += ran
    return issues, out
