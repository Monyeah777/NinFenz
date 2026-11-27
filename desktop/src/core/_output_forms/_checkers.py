"""output_forms 私有子模块 _checkers：各形态校验器与 _FORM_CHECK 登记表（JSON Schema 子集 / CSV / XML / YAML / TOML / Vega / Mermaid / GraphML / 量化指标）。

门面 core.output_forms 按原 API 重新导出；本文件只承载实现，不改变对外面。
"""
from __future__ import annotations

import csv
import io
import re
import xml.etree.ElementTree as ET

from core import json_doc
from core.json_schema import json_schema_check as _js_check

from ._const import _DTD_RE, _MERMAID_KINDS
from ._registry import _read_bytes_cached, _read_json, _read_text_cached, _rel


json_schema_check = _js_check          # 兼容别名：本模块既有调用点（1115/1429 等）不变



# ---------------------------------------------------------------- 形态结构校验

def _check_json(root: str, rel: str) -> List[str]:
    path = _rel(root, rel)
    raw = _read_text_cached(path)
    dups: List[str] = []

    def hook(pairs):
        seen = set()
        for k, _v in pairs:
            if k in seen:
                dups.append(k)
            seen.add(k)
        return dict(pairs)

    try:
        json_doc.loads(raw, None, what="JSON 文本", pairs_hook=hook)
    except ValueError as exc:
        return ["JSON 不可解析：%s" % exc]
    return ["JSON 重复键：%s" % d for d in sorted(set(dups))]



def _check_jsonl(root: str, rel: str) -> List[str]:
    issues: List[str] = []
    for i, line in enumerate(_read_text_cached(_rel(root, rel)).splitlines(), 1):
        if not line.strip():
            continue
        try:
            json_doc.loads(line, None, what=f"第 {i} 行")
        except ValueError as exc:
            issues.append("第 %d 行非 JSON：%s" % (i, exc))
    return issues



def _check_csv(root: str, rel: str) -> List[str]:
    text = _read_text_cached(_rel(root, rel))
    if "\x00" in text:
        return ["含 NUL 字节（非文本 CSV）"]
    rows = list(csv.reader(io.StringIO(text)))
    rows = [r for r in rows if r]
    if not rows:
        return ["空表"]
    width = len(rows[0])
    issues = [] if width else ["表头为空"]
    for i, r in enumerate(rows[1:], 2):
        if len(r) != width:
            issues.append("第 %d 行字段数 %d ≠ 表头 %d" % (i, len(r), width))
    if len(set(rows[0])) != width:
        issues.append("表头有重名列")
    return issues



def _check_xml(root: str, rel: str) -> List[str]:
    text = _read_text_cached(_rel(root, rel))
    guard = _xml_guard(text)
    if guard:
        return [guard]
    try:
        ET.fromstring(text)  # nosec B314 -- DTD/ENTITY rejected in _xml_guard
    except ET.ParseError as exc:
        return ["XML 良构性失败：%s" % exc]
    return []



def _xml_guard(text: str) -> str:
    """XML 解析前哨：拒绝 DTD/ENTITY 声明（堵实体展开 / 十亿笑声类攻击）。

    本仓 XML 面（GraphML / SVG）只由本仓生成器写出，不需要 DTD；一旦出现即视为异常输入，
    直接判不合格而不是「带风险解析」——不引第三方（defusedxml）也守住安全面。
    """
    if _DTD_RE.search(text):
        return "含 DTD/ENTITY 声明（本仓 XML 产出面禁 DTD：堵实体展开类攻击）"
    return ""



def _check_markdown(root: str, rel: str) -> List[str]:
    text = _read_text_cached(_rel(root, rel))
    issues = []
    if not text.strip():
        issues.append("空档")
    if text.count("```") % 2:
        issues.append("代码围栏未闭合（``` 奇数个）")
    return issues



def _check_toml(root: str, rel: str) -> List[str]:
    try:
        import tomllib  # Python 3.11+ 标准库
    except ImportError:  # pragma: no cover - 3.10 及以下
        return []
    try:
        tomllib.loads(_read_text_cached(_rel(root, rel)))
    except Exception as exc:
        return ["TOML 不可解析：%s" % exc]
    return []



def _check_yaml(root: str, rel: str) -> List[str]:
    """YAML 只做**收窄子集**良构判定（本项目自用面：映射/列表/标量），不引第三方。"""
    text = _read_text_cached(_rel(root, rel))
    issues: List[str] = []
    for i, line in enumerate(text.splitlines(), 1):
        if "\t" in line[: len(line) - len(line.lstrip())]:
            issues.append("第 %d 行用 Tab 缩进（YAML 禁 Tab）" % i)
        stripped = line.strip()
        if stripped.startswith("- ") or not stripped or stripped.startswith("#"):
            continue
        if ":" not in line:
            issues.append("第 %d 行非映射项（收窄子集要求 key: value）：%s" % (i, stripped[:40]))
    return issues



def _check_vega_lite(root: str, rel: str) -> List[str]:
    data, err = _read_json(_rel(root, rel))
    if err:
        return [err]
    issues: List[str] = []
    if "vega-lite" not in str(data.get("$schema") or ""):
        issues.append("缺 $schema（应为 vega-lite v5）")
    if not any(k in data for k in ("mark", "layer", "hconcat", "vconcat",
                                   "concat", "facet", "spec", "repeat")):
        issues.append("缺 mark/layer 等绘图主体")
    if "data" not in data:
        issues.append("缺 data（图不能没有数据源）")
    enc = data.get("encoding")
    if isinstance(enc, dict):
        for ch, spec in enc.items():
            if not isinstance(spec, dict):
                issues.append("encoding.%s 非对象" % ch)
                continue
            if not any(k in spec for k in ("field", "aggregate", "value", "datum",
                                           "timeUnit", "bin")):
                issues.append("encoding.%s 无 field/aggregate/value（通道未绑定）" % ch)
    elif enc is not None and not isinstance(enc, dict):
        issues.append("encoding 非对象")
    return issues



def _check_mermaid(root: str, rel: str) -> List[str]:
    lines = [x.rstrip() for x in _read_text_cached(_rel(root, rel)).splitlines()]
    body = [x for x in lines if x.strip() and not x.strip().startswith("%%")]
    if not body:
        return ["空图"]
    issues = []
    head = body[0].strip().lower()
    if not any(head.startswith(k) for k in _MERMAID_KINDS):
        issues.append("首行非已知图种：%r" % body[0].strip()[:40])
    return issues



def _check_dot(root: str, rel: str) -> List[str]:
    text = _read_text_cached(_rel(root, rel))
    issues = []
    if not re.search(r"^\s*(strict\s+)?(di)?graph\b", text, re.M):
        issues.append("缺 digraph/graph 头")
    if text.count("{") != text.count("}"):
        issues.append("花括号不配对（{ %d / } %d）" % (text.count("{"), text.count("}")))
    return issues



def _check_graphml(root: str, rel: str) -> List[str]:
    path = _rel(root, rel)
    guard = _xml_guard(_read_text_cached(path))
    if guard:
        return ["GraphML %s" % guard]
    try:
        # 从**已缓存的字节**解析（`_read_bytes_cached` 与 `_read_text_cached` 共用同一次物理读）
        # ——`ET.parse(path)` 会自己再开一次文件，同一件在一次重算里被读两遍（实测 105 次）。
        r = ET.fromstring(_read_bytes_cached(path))  # nosec B314 -- DTD/ENTITY 已在 _xml_guard 拒掉
    except ET.ParseError as exc:
        return ["GraphML XML 解析失败：%s" % exc]
    tag = r.tag.split("}")[-1]
    issues = []
    if tag != "graphml":
        issues.append("根元素应为 graphml，实为 %s" % tag)
    graphs = r.findall(".//{*}graph")
    if not graphs:
        issues.append("缺 <graph> 元素")
    nodes = {n.get("id") for g in graphs for n in g.findall("{*}node")}
    for g in graphs:
        for e in g.findall("{*}edge"):
            for end in ("source", "target"):
                if e.get(end) not in nodes:
                    issues.append("边端点悬空：%s=%s" % (end, e.get(end)))
    return issues



def _check_quant_metrics(root: str, rel: str) -> List[str]:
    """口径注册表语义检查：**宣称的引擎必须真实存在**（宣称≠实现），口径参数自洽。"""
    issues = _check_json(root, rel)
    data, err = _read_json(_rel(root, rel))
    if err or not isinstance(data, dict):
        return issues + ([err] if err else [])
    from core import quant_metrics as qm

    for m in list(data.get("metrics") or []) + list(data.get("declared_only") or []):
        if not isinstance(m, dict):
            issues.append("条目非对象：%r" % (m,))
            continue
        mid = m.get("id") or "?"
        eng = str(m.get("engine") or "")
        if eng:
            mod, _, fn = eng.partition(":")
            if mod != "quant_metrics" or not hasattr(qm, fn):
                issues.append("%s: 宣称 engine=%s，但 core/quant_metrics 无该实现（宣称≠实现）"
                              % (mid, eng))
        if m.get("verifiable") == "T4" and not eng:
            issues.append("%s: 标 T4（可复算）却无 engine" % mid)
        params = m.get("required_params") or []
        if m.get("annual_factor_required") and "annual_factor" not in params:
            issues.append("%s: 需年化因子却未列入 required_params（口径四要素不全）" % mid)
    names = {str(m.get("id")) for m in (data.get("metrics") or [])}
    expected = {k for k in data.get("annual_factors", {})}
    if expected != {"daily", "weekly", "monthly"}:
        issues.append("annual_factors 键集应为 daily/weekly/monthly，实为 %s" % sorted(expected))
    if len(names) != len(data.get("metrics") or []):
        issues.append("metrics 存在重复 id")
    return issues



def _check_domain_spec(root: str, rel: str) -> List[str]:
    """域口径表机读投影：条数口径 + id 序 + 判据/锚齐备（语义面，不只形状）。"""
    issues = _check_json(root, rel)
    data, err = _read_json(_rel(root, rel))
    if err or not isinstance(data, dict):
        return issues + ([err] if err else [])
    code = str(data.get("code") or "")
    subs = data.get("subdivisions") or []
    if len(subs) != 12:
        issues.append("细分条目应为 12 条，实为 %d" % len(subs))
    for i, s in enumerate(subs, 1):
        want = "%s-%02d" % (code, i)
        if s.get("id") != want:
            issues.append("第 %d 条 id 应为 %s，实为 %r" % (i, want, s.get("id")))
        if not str(s.get("anchor") or "").startswith(("http://", "https://")):
            issues.append("%s 锚非绝对 URL" % s.get("id"))
        if int(s.get("anchor_status") or 0) == 0:
            issues.append("%s 锚缺可达性实测值（不得假装可达：探不到记 0 并在锚表注明）"
                          % s.get("id"))
    return issues



def _check_domain_report(root: str, rel: str) -> List[str]:
    """域报告：形状 + 口径族在册 + 样例规模自洽（复算一致由 recompute 面判）。"""
    from core import domain_metrics as dm

    issues = _check_json(root, rel)
    data, err = _read_json(_rel(root, rel))
    if err or not isinstance(data, dict):
        return issues + ([err] if err else [])
    fam = str(data.get("family") or "")
    if fam not in dm.FAMILIES:
        issues.append("度量族未在本仓引擎登记：%r（不得宣称可复算）" % fam)
    metrics = data.get("metrics") or {}
    if str(metrics.get("family") or "") != fam:
        issues.append("metrics.family 与报告 family 不一致")
    if int(data.get("sample_rows") or 0) < 1:
        issues.append("样例规模为 0（无样例即无口径值）")
    return issues
