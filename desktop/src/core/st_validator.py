"""ST 制卡校验器原型 v0（任务书 A-S3）：卡 / 世界书 / MVU 变量 → 可复用报告。

零新依赖（仅标准库）。只做**可自动化项**：
- **R1 结构完备** → C1 可解析且版本可判 / C2 版本字段正确 / C3 基础六字段齐备非空；
- **R3 世界书健康** → W1 entries 结构合法 / W2 key 卫生（逗号分隔符、同书重复）/ W5 扫描范围提示；
- **R4 变量系统** → V2 初始值完备（initial ⊆ 变量集合）/ V5 命名与结构建议（宏、数组优先 record）。

边界（对齐规范与 B 线红线）：**不解析 PNG 实卡**（chunk/base64 解析属后续）、**不新增读写工具**、
级别映射沿用 `protocol/st_quality.json`：M→fail · S→warn · R→info。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

SEV = {"M": "fail", "S": "warn", "R": "info"}
REQUIRED_SIX = ("name", "description", "personality", "scenario",
                "first_mes", "mes_example")
SPEC_EXPECT = {"chara_card_v2": "2.0", "chara_card_v3": "3.0"}


def _issue(rid: str, level: str, detail: str) -> Dict[str, str]:
    return {"rule": rid, "level": level, "severity": SEV.get(level, "info"),
            "detail": detail}


def _card_spec_version(doc: Dict[str, Any], data: Any) -> str:
    return str(doc.get("spec_version") or (data or {}).get("spec_version") or "")


def _card_spec_issues(doc: Dict[str, Any], data: Any) -> List[Dict[str, str]]:
    out: List[Dict[str, str]] = []
    spec = str(doc.get("spec") or "")
    if spec:
        if spec not in SPEC_EXPECT:
            out.append(_issue("C1", "M", "spec 非法：%s（应为 chara_card_v2/v3）" % spec))
        want = SPEC_EXPECT.get(spec)
        got = _card_spec_version(doc, data)
        if want and got != want:
            out.append(_issue("C2", "M", "spec_version 应为 %s，实为 %s" % (want, got or "(缺)")))
    elif data is not None:
        out.append(_issue("C1", "M", "有 data 但缺 spec——无法判定 V2/V3"))
    return out


def _card_body(doc: Dict[str, Any], data: Any) -> Dict[str, Any]:
    if str(doc.get("spec") or ""):
        return data or {}
    if data is not None:
        return data
    return doc                      # V1 平铺


def check_card(doc: Dict[str, Any]) -> List[Dict[str, str]]:
    """R1：卡结构（V1/V2/V3）。"""
    out: List[Dict[str, str]] = []
    data = doc.get("data") if isinstance(doc.get("data"), dict) else None
    out += _card_spec_issues(doc, data)
    body = _card_body(doc, data)
    for k in REQUIRED_SIX:
        v = body.get(k)
        if v is None or (isinstance(v, str) and not v.strip()):
            out.append(_issue("C3", "M", "基础字段缺失或为空：%s" % k))
    return out


def _wb_rows(doc: Dict[str, Any]) -> Any:
    raw = doc.get("entries")
    if raw is None and isinstance(doc.get("character_book"), dict):
        raw = doc["character_book"].get("entries")
    if isinstance(raw, dict):
        return [v for v in raw.values() if isinstance(v, dict)]
    if isinstance(raw, list):
        return [v for v in raw if isinstance(v, dict)]
    return None


def _wb_entry_keys(e: Dict[str, Any]) -> List[str]:
    keys = e.get("keys") if e.get("keys") is not None else e.get("key")
    if isinstance(keys, str):
        keys = [keys]
    return [str(k) for k in (keys or []) if str(k).strip()]


def _wb_entry_issues(e: Dict[str, Any], i: int, keys: List[str],
                     seen: Dict[str, int]) -> List[Dict[str, str]]:
    out: List[Dict[str, str]] = []
    if not keys:
        out.append(_issue("W1", "M", "第 %d 条 key 为空" % i))
    if not str(e.get("content") or "").strip():
        out.append(_issue("W1", "M", "第 %d 条 content 为空" % i))
    for k in keys:
        if "," in k:
            out.append(_issue("W2", "S", "key 含逗号（会被当分隔符）：%s" % k))
        seen[k] = seen.get(k, 0) + 1
    if e.get("scanDepth") is None:
        out.append(_issue("W5", "S", "第 %d 条未声明 scanDepth（触发可能在扫描范围外）" % i))
    return out


def check_worldbook(doc: Dict[str, Any]) -> List[Dict[str, str]]:
    """R3：世界书健康。"""
    out: List[Dict[str, str]] = []
    rows = _wb_rows(doc)
    if rows is None:
        return [_issue("W1",
 "M",
 "entries 缺失或不是 dict/list（ST convertCharacterBook 要求数组）")]
    seen: Dict[str, int] = {}
    for i, e in enumerate(rows):
        out += _wb_entry_issues(e, i, _wb_entry_keys(e), seen)
    for k, n in seen.items():
        if n > 1:
            out.append(_issue("W2", "S", "同书内 key 重复 %d 次：%s" % (n, k)))
    return out


def _mvu_initial_issues(names: List[str], init: Dict[str, Any]) -> List[Dict[str, str]]:
    out: List[Dict[str, str]] = []
    extra = sorted(set(init) - set(names))
    if extra:
        out.append(_issue("V2", "M", "initial 含未声明变量：%s" % "、".join(extra)))
    missing = sorted(set(names) - set(init))
    if missing:
        out.append(_issue("V2", "M", "变量缺初始值：%s" % "、".join(missing)))
    return out


def _mvu_name_issues(names: List[str]) -> List[Dict[str, str]]:
    out: List[Dict[str, str]] = []
    for n in names:
        if "{{" in n or "}}" in n:
            out.append(_issue("V5", "S", "变量名含宏：%s" % n))
        if n.startswith(("_", "$")):
            out.append(_issue("V4", "S", "变量名带可见性前缀（%s）——确认语义正确" % n[0]))
    return out


def _mvu_array_issues(variables: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    out: List[Dict[str, str]] = []
    for v in variables:
        if str(v.get("kind")) == "array":
            out.append(_issue("V5", "S", "变量 %s 为 array，规范建议优先 record" % v.get("name")))
    return out


def check_mvu_variables(doc: Dict[str, Any]) -> List[Dict[str, str]]:
    """R4：MVU 变量系统。"""
    out: List[Dict[str, str]] = []
    variables = doc.get("variables") or []
    names = [str(v.get("name")) for v in variables if v.get("name")]
    if not names:
        return [_issue("V2", "M", "变量表为空——无 schema 可校验")]
    init = doc.get("initial") or {}
    out += _mvu_initial_issues(names, init)
    out += _mvu_name_issues(names)
    out += _mvu_array_issues(variables)
    return out


def _dispatch(doc: Dict[str, Any]) -> Any:
    if doc.get("variables") is not None and doc.get("initial") is not None:
        return "mvu-variables", check_mvu_variables(doc)
    if doc.get("entries") is not None or doc.get("character_book") is not None:
        return "worldbook", check_worldbook(doc)
    if doc.get("spec") is not None or doc.get("name") is not None:
        return "card", check_card(doc)
    return "unknown", [_issue("C1", "M", "无法识别资产类型（无 spec/name/entries/variab"
            "les 特征）")]


def validate(path: str) -> Dict[str, Any]:
    """按形状分派（卡 / 世界书 / MVU 变量）→ 报告。"""
    p = Path(path)
    doc = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(doc, dict):
        return {"path": path, "kind": "unknown", "issues": [
            _issue("C1", "M", "顶层不是对象，无法判定资产类型")]}
    kind, issues = _dispatch(doc)
    return {"path": path, "kind": kind, "issues": issues,
            "counts": {s: sum(1 for i in issues if i["severity"] == s)
                       for s in ("fail", "warn", "info")}}


def report_markdown(rep: Dict[str, Any]) -> str:
    c = rep.get("counts", {})
    out = ["# ST 制卡校验报告", "",
           "- 对象：`%s`" % rep.get("path"), "- 判定形态：**%s**" % rep.get("kind"),
           "- 结果：fail %d · warn %d · info %d" % (c.get("fail", 0), c.get("warn", 0),
                                                    c.get("info", 0)), ""]
    if not rep.get("issues"):
        out += ["**零问题**——该对象在可自动化项（R1/R3/R4）上全部通过。", ""]
    else:
        out += ["| 规则 | 级别 | 严重度 | 说明 |", "|---|---|---|---|"]
        for i in rep["issues"]:
            out.append("| %s | %s | %s | %s |" % (i["rule"], i["level"], i["severity"],
                                                  i["detail"]))
        out.append("")
    out += ["> 本报告只覆盖**可自动化项**（R1 结构 / R3 世界书 / R4 变量）；",
            "> R2 引用一致、R5 可复现、R6 长会话友好等仍需人工清单（见 `docs/st-quality-checklist.m"
                "d`）。",
            "> 校验器原型 v0 不解析 PNG 实卡；输入为已解出的 JSON。", ""]
    return "\n".join(out)
