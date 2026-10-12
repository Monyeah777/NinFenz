"""微内核插件清单（nf-plugin-manifest/1）的**装载期校验**（P5-01.3 / P5-03）。

纪律来源（计划 §18.3/§18.4/§18.7）：

- 插件默认**无 fs、无 net、无 env、无时钟、无随机**。清单里对 fs/net 的任何非空请求一律
  **拒绝装载**（deny by default），而不是「声明了就给」——「默认不授予」只有做成装载期的硬
  拒绝才不是一句口号；
- 声明 determinism=deterministic 的插件不得要时钟或随机（否则声明自相矛盾）；
- 方法名必须与 WIT 接口（engine/wasm/ninfenz-plugin.wit）导出的函数名对得上——这是「装载时
  校验」的实质：接口不在契约里就不许装；
- 产物路径必须是**仓库内相对路径**（走 core.paths.validate_path，与资产台账/产出面同源，
  不再另写一份宽窄可能分叉的判据）。

依赖姿态：core.paths（stdlib-only 叶子）。不 import 任何宿主/进程设施——本模块只判清单，
不跑插件；跑插件在适配器侧（scripts/plugin_host.py）。
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from core import paths as _paths

SCHEMA = "nf-plugin-manifest/1"
#: 已知 ABI。CLI 形态是当前产出；组件形态是 P5-03 的目标，先登记名字以便未来直接接。
ABIS = ("wasi-preview1-cli", "wasi-preview2-component")
DETERMINISM = ("deterministic", "nondeterministic")
CAP_KEYS = ("fs", "net", "env", "clocks", "random")
#: 非空即拒装的能力（deny by default）
DENIED_ON_REQUEST = ("fs", "net")
#: deterministic 声明下必须为 deny 的能力
MUST_DENY_WHEN_DETERMINISTIC = ("clocks", "random")
#: 成本模型
COST_KINDS = ("constant", "linear")
_REQUIRED = ("schema", "id", "version", "abi", "methods")
_WIT_EXPORT = re.compile(r"^\s*([a-z][a-z0-9]*(?:-[a-z0-9]+)*)\s*:\s*func\s*\(", re.M)


def load(path: str) -> dict[str, Any]:
    """读清单（坏件即抛，不静默降级）。"""
    return json.loads(Path(path).read_text(encoding="utf-8"))


def wit_exports(text: str) -> list[str]:
    """从 WIT 文本取导出的方法名（跳过注释行）。

    只认 name: func( 形态；package/interface/world 等声明自然不匹配。
    """
    body = "\n".join(ln for ln in text.splitlines() if not ln.lstrip().startswith(("//", "///")))
    return sorted(set(_WIT_EXPORT.findall(body)))


def validate(doc: Any) -> list[str]:
    """→ 装载问题清单（空表 = 可装）。纯函数，便于变异自证。"""
    issues: list[str] = []
    if not isinstance(doc, dict):
        return ["清单不是对象"]
    for key in _REQUIRED:
        if not doc.get(key):
            issues.append(f"缺字段：{key}")
    if doc.get("schema") and doc["schema"] != SCHEMA:
        issues.append(f"schema 不是 {SCHEMA}：{doc['schema']!r}")
    if doc.get("abi") and doc["abi"] not in ABIS:
        issues.append(f"未知 ABI：{doc['abi']!r}（在册：{' | '.join(ABIS)}）")
    ver = str(doc.get("version") or "")
    if ver and not re.match(r"^\d+\.\d+\.\d+", ver):
        issues.append(f"version 不是 x.y.z 形态：{ver!r}")

    methods = doc.get("methods")
    if not isinstance(methods, list) or not methods:
        issues.append("methods 必须是非空列表")
        methods = []
    seen = set()
    for i, m in enumerate(methods):
        if not isinstance(m, dict):
            issues.append(f"methods[{i}] 不是对象")
            continue
        name = str(m.get("name") or "")
        if not re.match(r"^[a-z][a-z0-9-]*$", name):
            issues.append(f"methods[{i}].name 形状非法：{name!r}")
        elif name in seen:
            issues.append(f"方法名重复：{name}")
        seen.add(name)
        if m.get("determinism") not in DETERMINISM:
            issues.append(f"{name}.determinism 非法：{m.get('determinism')!r}")
        io = m.get("io")
        if not isinstance(io, dict) or not (io.get("stdin") or io.get("argv")):
            issues.append(f"{name}.io 缺输入面（stdin 或 argv 至少其一）")
        cost = m.get("cost")
        if not isinstance(cost, dict) or cost.get("kind") not in COST_KINDS or not cost.get("unit"):
            issues.append(f"{name}.cost 须为 {{kind: {'|'.join(COST_KINDS)}, unit: ...}}")
        issues.extend(_fuel_issues(name, m))
        issues.extend(_capability_issues(name, m, m.get("determinism")))

    art = doc.get("artifact")
    if art is not None:
        if not isinstance(art, dict) or not art.get("path"):
            issues.append("artifact 存在但无 path")
        else:
            try:
                _paths.validate_path(".", str(art["path"]))
            except _paths.PathEscapeError as exc:
                issues.append(f"artifact.path 逃逸仓库根：{exc}")
    return issues


def _fuel_issues(name: str, method: dict[str, Any]) -> list[str]:
    """燃料预算必须**随输入规模伸缩**。

    实测（wasmtime 49 + 本仓 sha256 插件，2026-10-12）：约 **138,776 燃料/KiB**，线性。
    若线性的方法只声明一个固定预算，那个数字就变成了**意外的输入长度上限**——32 MiB
    的输入会「恰好」耗尽 4e9 燃料并触发回退。故线性成本**必须**声明 per_kib。
    """
    fuel = method.get("fuel")
    if not isinstance(fuel, dict):
        return [f"{name}.fuel 缺失（须 {{base, per_kib?}}）"]
    out: list[str] = []
    base = fuel.get("base")
    if not isinstance(base, int) or base <= 0:
        out.append(f"{name}.fuel.base 须为正整数")
    kind = (method.get("cost") or {}).get("kind")
    if kind == "linear":
        per_kib = fuel.get("per_kib")
        if not isinstance(per_kib, int) or per_kib <= 0:
            out.append(f"{name} 成本为 linear，fuel.per_kib 须为正整数（否则预算=隐式输入上限）")
    cap = fuel.get("hard_cap")
    if cap is not None and (not isinstance(cap, int) or cap <= 0):
        out.append(f"{name}.fuel.hard_cap 须为正整数")
    return out


def _capability_issues(name: str, method: dict[str, Any], determinism: Any) -> list[str]:
    """能力声明的三类问题：未知键 / 明令禁止的能力 / 与确定性声明矛盾。"""
    caps = method.get("capabilities")
    if not isinstance(caps, dict):
        return [f"{name}.capabilities 缺失（默认不授予不等于可以不声明）"]
    out: list[str] = []
    for key in caps:
        if key not in CAP_KEYS:
            out.append(f"{name}.capabilities 未知键：{key}")
    for key in DENIED_ON_REQUEST:
        if caps.get(key):
            out.append(f"{name} 请求了 {key}：默认不授予（deny by default，装配拒绝）")
    for key in MUST_DENY_WHEN_DETERMINISTIC:
        if determinism == "deterministic" and caps.get(key) != "deny":
            out.append(f"{name} 声明 deterministic 却把 {key} 设成 {caps.get(key)!r}（须 deny）")
    if caps.get("env"):
        out.append(f"{name} 请求了 env：环境变量会破坏可复现性，默认不授予")
    return out


def validate_against_wit(doc: dict[str, Any], wit_text: str) -> list[str]:
    """清单声明的方法必须**全部**在 WIT 接口里导出；反之 WIT 里的方法也必须有清单条目。

    两侧都查：只查一侧的话，「清单写了但接口没有」与「接口有但没人声明」都会漏。
    """
    declared = sorted(str((m or {}).get("name") or "") for m in (doc.get("methods") or []))
    exported = wit_exports(wit_text)
    issues = [f"清单方法 {n} 不在 WIT 契约里" for n in declared if n and n not in exported]
    issues += [f"WIT 方法 {n} 没有清单条目" for n in exported if n not in declared]
    return issues


def method(doc: dict[str, Any], name: str) -> dict[str, Any] | None:
    """取某方法的清单条目；无则 None。"""
    for m in doc.get("methods") or []:
        if str((m or {}).get("name")) == name:
            return m
    return None


def granted_capabilities(doc: dict[str, Any]) -> dict[str, Any]:
    """宿主**实际**授予的能力（与声明无关）：一律为空/deny。"""
    return {"fs": [], "net": [], "env": [], "clocks": "deny", "random": "deny",
            "abi": doc.get("abi")}


def artifact_path(doc: dict[str, Any], root: str = ".") -> Path | None:
    """产物绝对路径；未声明 / 逃逸一律 None（fail-closed）。"""
    art = doc.get("artifact") or {}
    rel = str(art.get("path") or "")
    if not rel:
        return None
    try:
        safe = _paths.validate_path(root, rel)
    except _paths.PathEscapeError:
        return None
    return Path(root) / safe
