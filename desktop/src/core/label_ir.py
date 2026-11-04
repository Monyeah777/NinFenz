"""标注 IR v0（`cc_label` 的**形状层**）：只描述「该有哪些标识」，不写载体。

为什么只到 IR（2026-11-05 实测）：本仓没有标识写入/载体注入子系统，任何「已写入水印 / 已嵌入元数据」
的宣称都不可证。故本模块只做三件事：

1. 给出标准规则表（GB 45438 的显式/隐式标识分类；**v0 映射，待按标准原文复核**）；
2. 由「对象 + 契约 + 声明项」组装 `nf-label/1` IR（纯数据、确定性、无时间戳）；
3. 校验 IR 是否满足所选档位（minimal / full），并把「载体未证明已写入」**如实**记为 warning——
   不提升任何强度，也不假装完成。

边界（写进判据也写进文档）：本模块**不写盘、不碰载体**；它判的是「声明得齐不齐、形状对不对」，
不是「内容是否真的带标识」。后者需要标识写入子系统，本仓目前没有。
"""
from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any

SCHEMA = "nf-label/1"
#: 标准真源（v0 只认这一份；换标准要显式改这里并补判据）
STANDARD = "GB 45438-2025"
#: 档位：minimal = 最少必需（显式文字 + 隐式元数据）；full = 再加语音提示/显式元数据/数字水印
LEVELS = ("minimal", "full")
#: 判定词表（与证据线同源：ok / invalid——标注面没有 revoked/expired 概念）
VERDICTS = ("ok", "invalid")
GUIDE = "修复指引："
_HEX64 = re.compile(r"^[0-9a-f]{64}$")

#: 规则表：每条 = 一个可被「声明项」满足的最小要求。
#: `level` 指**从哪一档起必需**（minimal 必含 / full 追加）。
RULES: tuple[dict[str, Any], ...] = (
    {"id": "E1", "face": "explicit", "kind": "text", "level": "minimal",
     "required": ("where", "value"),
     "desc": "显式文字提示（内容起始 / 末尾 / 交互界面）"},
    {"id": "E2", "face": "explicit", "kind": "audio", "level": "full",
     "required": ("value",),
     "desc": "音频 / 视频的可听提示"},
    {"id": "E3", "face": "explicit", "kind": "metadata", "level": "full",
     "required": ("key", "value"),
     "desc": "显式元数据声明（生成合成标识字段）"},
    {"id": "I1", "face": "implicit", "kind": "watermark", "level": "full",
     "required": ("algorithm", "value"),
     "desc": "隐式数字水印"},
    {"id": "I2", "face": "implicit", "kind": "metadata", "level": "minimal",
     "required": ("key", "value"),
     "desc": "隐式元数据（文件元数据字段）"},
)


def rules(level: str = "minimal") -> list[dict[str, Any]]:
    """按档位取必需规则（顺序稳定；未知档位带指引拒绝）。"""
    if level not in LEVELS:
        raise ValueError(f"未知档位 {level!r}（{GUIDE}可用档位：{', '.join(LEVELS)}）")
    if level == "minimal":
        return [dict(r) for r in RULES if r["level"] == "minimal"]
    return [dict(r) for r in RULES]


def _clean_item(item: dict[str, Any]) -> dict[str, Any]:
    """声明项归一：只保留字符串字段（其余视为非法，交校验面判）。"""
    out: dict[str, Any] = {}
    for key, val in item.items():
        if not isinstance(key, str):
            continue
        out[key] = val.strip() if isinstance(val, str) else val
    return out


def build(object_path: str, digest: str, contract: str = "", level: str = "minimal",
          items: Iterable[dict[str, Any]] = (), producer: str = "") -> dict[str, Any]:
    """组装 IR（纯数据；同一输入逐字节一致——不含时间戳，可复现）。"""
    faces = {"explicit": [], "implicit": []}
    for item in items:
        face = str(item.get("face") or "")
        if face in faces:
            faces[face].append(_clean_item(item))
    return {
        "schema": SCHEMA,
        "standard": STANDARD,
        "level": level,
        "contract": contract,
        "object": {"path": object_path, "digest": digest},
        "explicit": faces["explicit"],
        "implicit": faces["implicit"],
        "carrier": {"embedded": False, "producer": producer},
        "boundary": ("本件只声明「该有哪些标识」；不证明载体里真的写入了任何标识。"),
    }


def _check_object(doc: dict[str, Any], issues: list[str]) -> None:
    obj = doc.get("object")
    if not isinstance(obj, dict):
        issues.append("缺 object 段（" + GUIDE + "需要 {path, digest}）")
        return
    path = obj.get("path")
    digest = str(obj.get("digest") or "").strip().lower()
    if not isinstance(path, str) or not path.strip():
        issues.append("object.path 缺失或为空（" + GUIDE + "请给对象路径）")
    if not _HEX64.match(digest):
        issues.append("object.digest 必须是 64 位十六进制 sha256（" + GUIDE +
                      "请用 nf label ir 生成，或核对摘要来源）")


def _check_items(doc: dict[str, Any], issues: list[str], warnings: list[str]) -> None:
    """逐条形状校验 + 未证明载体写入的如实提示。"""
    allowed = {"explicit": {"text", "audio", "metadata"},
               "implicit": {"watermark", "metadata"}}
    for face, kinds in allowed.items():
        items = doc.get(face)
        if not isinstance(items, list):
            issues.append(f"缺 {face} 列表（" + GUIDE + "没有就写空数组，不要省略字段）")
            continue
        for i, item in enumerate(items):
            if not isinstance(item, dict):
                issues.append(f"{face}[{i}] 应为对象（" + GUIDE + "声明项是键值对）")
                continue
            kind = item.get("kind")
            if kind not in kinds:
                issues.append(f"{face}[{i}].kind 非法：{kind!r}（" + GUIDE +
                              f"可用：{', '.join(sorted(kinds))}）")
    carrier = doc.get("carrier")
    if not isinstance(carrier, dict):
        issues.append("缺 carrier 段（" + GUIDE + "需要 {embedded: bool, producer}）")
        return
    embedded = carrier.get("embedded")
    if not isinstance(embedded, bool):
        issues.append("carrier.embedded 必须是布尔值（" + GUIDE + "true 表示自称已写入载体）")
        return
    if embedded:
        warnings.append("carrier.embedded=true 只是**自称**：本仓没有载体写入子系统，"
                        "本判定无法证明标识真的写进了文件——不要把它当已实装")


def _covered(item: dict[str, Any], rule: dict[str, Any]) -> bool:
    """声明项是否满足某条规则：kind 相符 + 必填字段非空。"""
    if item.get("kind") != rule["kind"]:
        return False
    for field in rule["required"]:
        val = item.get(field)
        if not isinstance(val, str) or not val.strip():
            return False
    return True


def validate(doc: dict[str, Any]) -> dict[str, Any]:
    """校验 IR → {ok, verdict, level, applied, issues, warnings, missing}。"""
    res: dict[str, Any] = {"ok": False, "verdict": "invalid", "level": "none",
                           "applied": [], "issues": [], "warnings": [], "missing": []}
    if not isinstance(doc, dict):
        res["issues"].append("IR 顶层应为对象（" + GUIDE + "不是数组/标量）")
        return res
    if doc.get("schema") != SCHEMA:
        res["issues"].append(f"schema 不匹配：{doc.get('schema')!r}（" + GUIDE +
                             f"期望 {SCHEMA}）")
    if doc.get("standard") != STANDARD:
        res["issues"].append(f"standard 不匹配：{doc.get('standard')!r}（" + GUIDE +
                             f"v0 只认 {STANDARD}）")
    level = doc.get("level")
    if level not in LEVELS:
        res["issues"].append(f"level 非法：{level!r}（" + GUIDE +
                             f"可用：{', '.join(LEVELS)}）")
    _check_object(doc, res["issues"])
    _check_items(doc, res["issues"], res["warnings"])
    if isinstance(level, str) and level in LEVELS:
        res["level"] = level
        explicit = [i for i in (doc.get("explicit") or []) if isinstance(i, dict)]
        implicit = [i for i in (doc.get("implicit") or []) if isinstance(i, dict)]
        for rule in rules(level):
            pool = explicit if rule["face"] == "explicit" else implicit
            hit = next((i for i in pool if _covered(i, rule)), None)
            if hit is None:
                res["missing"].append(rule["id"])
                res["issues"].append(f"缺 {rule['id']}：{rule['desc']}（" + GUIDE +
                                     "补对应声明项，或把档位降到 minimal）")
                continue
            res["applied"].append({"rule": rule["id"], "kind": hit.get("kind")})
    res["ok"] = not res["issues"]
    res["verdict"] = "ok" if res["ok"] else "invalid"
    return res


# （删掉过 applied_rules：没人用——死代码判据当场抓出来。取已满足规则请读 validate()["applied"]）
