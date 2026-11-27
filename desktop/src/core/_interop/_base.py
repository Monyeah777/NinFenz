"""interop_export 私有子模块 _base：基础层：钉版清单、仓内声明日期、JSON 读入、字段说明→JSON Schema 片段、JSON Pointer。

门面 core.interop_export 按原 API 重新导出；本文件只承载实现，不改变对外面。
"""
from __future__ import annotations

import glob
import os
import re

from core import json_doc



#: 依赖名别名（纯度登记的 import 名 → PyPI 项目名）：SBOM 的 purl/versionInfo 要用后者。
_DEP_ALIAS = {"yaml": "pyyaml"}



def _pinned_versions(root: str) -> Dict[str, str]:
    """钉版清单 → {PyPI 名(小写): 版本}：.github/requirements-*.txt 优先，pyproject 可选依赖补。

    2026-10-10 审计 Z4 / §11k.6：此前 SBOM 的依赖包**没有 versionInfo**，依赖扫描器
    （pip-audit / Grype / Dependabot）拿不到可比对的版本号，结论只能是「无版本 SBOM」。
    版本必须来自**已钉**的清单（不猜、不取 latest）。
    """
    out: Dict[str, str] = {}
    for p in sorted(glob.glob(os.path.join(root, ".github", "requirements-*.txt"))):
        try:
            with open(p, encoding="utf-8") as fh:
                lines = fh.read().splitlines()
        except OSError:
            # 尽力而为：依赖清单不可读 ⇒ 跳过该面（缺口由 self_stats / 供应链判据另行报出）。
            continue
        for line in lines:
            body = line.split("#", 1)[0].strip()
            if not body or body.startswith("-") or "==" not in body:
                continue          # 跳过 pip-compile 的 `--hash=` 续行与选项行
            name, _, ver = body.partition("==")
            name = name.strip().lower()
            if "[" in name:
                name = name.split("[", 1)[0].strip()   # `pkg[extra]==…` 取项目名
            ver = ver.split(";", 1)[0].strip().rstrip("\\").strip()
            if name and ver:
                out.setdefault(name, ver)
    pp = os.path.join(root, "pyproject.toml")
    if os.path.isfile(pp):
        try:
            import tomllib                      # 3.11+
            with open(pp, "rb") as fh:
                doc = tomllib.load(fh)
            extras = (doc.get("project", {}) or {}).get("optional-dependencies") or {}
            for specs in extras.values():
                for spec in (specs if isinstance(specs, list) else []):
                    if isinstance(spec, str) and "==" in spec:
                        name, ver = spec.split("==", 1)
                        out.setdefault(name.strip().lower(), ver.strip())
        except (OSError, ValueError, TypeError):
            pass
    return out


CONTRACT_REL = "protocol/endpoint_contract.json"

EVENTS_REL = "protocol/event_registry.json"

EXTERNAL_EVENTS_REL = "protocol/external_events.json"

RECEIPTS_REL = "protocol/RECEIPTS.json"


#: NF 项目自身的许可结论（与 LICENSE 同源）
LICENSE_NAME = "MIT"


#: SBOM `created` 的派生源（N=非墙钟）：从仓内**已声明日期**取最大值——
#: 目的有二：① SPDX 2.3 的 `creationInfo.created` 是必填（外部 meta-schema 实测会 FAIL）；
#: ② 摘要/导出面必须确定性可复现，用 `now()` 会破坏「两次渲染逐字节一致」的判据。
_DATE_SOURCES = ("protocol/score_baseline.json", "05_资产库/provenance.json")

_DATE_RE = re.compile(r"20\d\d-\d\d-\d\d")



def _declared_max_date(root: str) -> str:
    """仓内声明日期的最大值（YYYY-MM-DD）；取不到返回空串（门禁侧会记 FAIL）。"""
    dates: List[str] = []
    for rel in _DATE_SOURCES:
        path = os.path.join(root, rel)
        if os.path.isfile(path):
            with open(path, encoding="utf-8") as fh:
                dates += _DATE_RE.findall(fh.read())
    d = os.path.join(root, "protocol", "approvals")
    if os.path.isdir(d):
        for name in sorted(os.listdir(d)):
            if name.endswith(".json"):
                with open(os.path.join(d, name), encoding="utf-8") as fh:
                    dates += _DATE_RE.findall(fh.read())
    return max(dates) if dates else ""



def _read_json(root: str, rel: str) -> Dict[str, Any]:
    path = os.path.join(root, rel)
    if not os.path.isfile(path):
        # 缺件 ⇒ 空面（可选源，例如 provenance/transform_log 在局部树上可能不在场）
        return {}
    with open(path, encoding="utf-8") as fh:
        try:
            return json_doc.loads(fh.read(), dict, what=rel)
        except ValueError as exc:
            # **在场但坏** 不是「空面」：静默当空会让导出的标准文档**悄悄少一大段**
            # （而 check 判的是「在盘产物 == 实时派生」，两边一起空 ⇒ 永远绿）。fail-closed。
            raise ValueError("源件不可解析：%s（%s）（修复指引：修好该 JSON 后重跑 "
                             "`nf interop --all`）" % (rel, exc)) from None



_TYPE_MAP = {"string", "integer", "number", "boolean", "object", "array"}

_HEAD = re.compile(r"^\s*([a-z]+)")



def _schema_for(desc: str) -> Dict[str, Any]:
    """字段说明串 → JSON Schema 片段（只做可判定映射，未识别一律 object 保守兜底）。"""
    m = _HEAD.match(str(desc or ""))
    token = m.group(1) if m else ""
    jtype = token if token in _TYPE_MAP else "object"
    nullable = "null" in str(desc or "")
    out: Dict[str, Any] = {"type": [jtype, "null"] if nullable else jtype}
    if jtype == "array":
        out["items"] = {}
    if jtype == "object":
        out["additionalProperties"] = True
    if str(desc or "").strip():
        out["description"] = str(desc)
    return out



def _ptr(token: str) -> str:
    """JSON Pointer 转义（RFC 6901）：`~` → `~0`、`/` → `~1`。

    为什么需要：AsyncAPI 通道键写作 `nf/<事件名>`，而 `$ref` 片段里的 `/` 是层级分隔符；
    不转义会被官方校验器判为「引用的通道不存在」（2026-09-24 他证实证：443 条 invalid-ref）。
    """
    return str(token).replace("~", "~0").replace("/", "~1")
