"""interop_export 私有子模块 _docs_a：导出文档 A 组：OpenAPI / AsyncAPI / in-toto / SPDX SBOM / SLSA Provenance。

门面 core.interop_export 按原 API 重新导出；本文件只承载实现，不改变对外面。
"""
from __future__ import annotations

import os
import re

from ._base import CONTRACT_REL, EVENTS_REL, EXTERNAL_EVENTS_REL, LICENSE_NAME, RECEIPTS_REL, _DEP_ALIAS, _declared_max_date, _pinned_versions, _ptr, _read_json, _schema_for



def openapi_doc(root: str = ".") -> Dict[str, Any]:
    """服务端点契约 → OpenAPI 3.1 文档（纯派生）。"""
    contract = _read_json(root, CONTRACT_REL)
    conv = contract.get("conventions") or {}
    # 幂等声明面（RFC 9110 §9.2.2）：默认幂等，例外在契约层登记 → 派生面逐端点标注
    non_idem = {str(e.get("id")): str(e.get("key") or "")
                for e in (contract.get("idempotency_exceptions") or [])}
    paths: Dict[str, Any] = {}
    for ep in contract.get("endpoints") or []:
        path = str(ep.get("path") or "")
        method = str(ep.get("method") or "").lower()
        if not path or not method:
            continue
        req = ep.get("request") or {}
        resp = ep.get("response") or {}
        op: Dict[str, Any] = {
            "operationId": str(ep.get("id") or ""),
            "summary": "maps_to %s" % str(ep.get("maps_to") or ""),
            "x-nf-idempotency": ("non-idempotent（幂等键 %s）" % non_idem[str(ep.get("id"))]
                                 if str(ep.get("id")) in non_idem else "idempotent"),
            "responses": {
                "200": {"description": "成功",
                        "content": {"application/json": {"schema": {
                            "type": "object",
                            "properties": {k: _schema_for(v) for k, v in resp.items()},
                        }}}},
                "default": {"description": "错误（RFC 9457 Problem Details 映射见 "
                                           "x-nf-error-mapping）",
                            "content": {"application/json": {"schema": {
                                "$ref": "#/components/schemas/NfError"}}}},
            },
        }
        if req or method == "post":
            op["requestBody"] = {
                "required": True,
                "content": {"application/json": {"schema": {
                    "type": "object",
                    "properties": {k: _schema_for(v) for k, v in req.items()},
                }}},
            }
        if ep.get("streaming"):
            op["responses"]["200"]["content"]["text/event-stream"] = {
                "schema": {"type": "string"},
                "x-nf-streaming": conv.get("streaming", ""),
            }
        # 路径参数派生（2026-09-24 他证实证修复）：OpenAPI 3.1 要求路径模板变量必须在
        # operation 或 path item 上声明；此前只派生 operation 本体 → 官方校验器
        # （openapi-spec-validator）对 `/library/{id}` 报 “Path parameter 'id' ... was not resolved”
        # 。
        # 口径：模板变量名 → path 参数（type=string），与 endpoint_contract 的 {name} 写法同源。
        tmpl_vars = re.findall(r"\{([^}]+)\}", path)
        if tmpl_vars:
            op["parameters"] = [
                {"name": name, "in": "path", "required": True,
                 "schema": {"type": "string"},
                 "x-nf-derived": "由 protocol/endpoint_contract.json 的路径模板派生"}
                for name in tmpl_vars
            ]
        if ep.get("deprecated"):
            op["deprecated"] = True
            op["x-nf-sunset"] = ep.get("sunset")
            op["x-nf-replacement"] = ep.get("replacement")
        paths.setdefault(path, {})[method] = op
    return {
        "openapi": "3.1.0",
        "info": {"title": "NinFenz 服务端点契约（派生）",
                 "version": "1.0.0",
                 "description": "由 protocol/endpoint_contract.json 实时派生（status=%s）；"
                                "本文件非真源。" % contract.get("status", "")},
        "servers": [],
        "paths": paths,
        "components": {"schemas": {
            "NfError": {
                "type": "object",
                "required": ["error"],
                "properties": {"error": {
                    "type": "object",
                    "required": ["code", "message"],
                    "properties": {"code": {"type": "integer",
                                            "description": "机器可判定错误码"},
                                   "message": {"type": "string",
                                               "description": "人读说明，必须带修复指引"},
                                   "data": {"type": ["object", "null"]}},
                }},
            },
        }},
        "x-nf-error-mapping": {
            "type": "about:blank",
            "title": "error.message",
            "detail": "error.message + 修复指引（patterns/error-message-guidance）",
            "instance": "请求路径",
            "status": "HTTP 状态码（与 message 同源）",
            "source": conv.get("errors", ""),
        },
        "x-nf-endpoints": len(contract.get("endpoints") or []),
    }



def asyncapi_doc(root: str = ".") -> Dict[str, Any]:
    """事件登记 → AsyncAPI 3.0 文档 + CloudEvents 属性（纯派生）。"""
    reg = _read_json(root, EVENTS_REL)
    ext = _read_json(root, EXTERNAL_EVENTS_REL)
    events: Dict[str, Any] = {}
    for src in (reg.get("events") or {}, ext.get("events") or {}):
        if isinstance(src, dict):
            for name, meta in src.items():
                events.setdefault(str(name), meta if isinstance(meta, dict) else {})
    channels: Dict[str, Any] = {}
    messages: Dict[str, Any] = {}
    for name, meta in sorted(events.items()):
        fields = meta.get("fields") or {}
        channels["nf/%s" % name] = {
            "address": "nf/%s" % name,
            "title": name,
            "messages": {"nf.%s" % name: {"$ref": "#/components/messages/%s" % _ptr(name)}},
            "x-nf-cloudevents": {"type": "nf.%s" % name, "source": "urn:nf:repo",
                                 "specversion": "1.0",
                                 "datacontenttype": "application/json"},
        }
        messages[name] = {
            "name": name,
            "contentType": "application/json",
            "payload": {"type": "object",
                        "properties": {k: _schema_for((v or {}).get("type", ""))
                                       for k, v in fields.items()}},
            "x-nf-note": str(meta.get("note") or "")[:200],
        }
    return {
        "asyncapi": "3.0.0",
        "info": {"title": "NinFenz 事件登记（派生）", "version": "1.0.0",
                 "description": "由 protocol/event_registry.json + external_events.json "
                                "实时派生；本文件非真源。"},
        "channels": channels,
        "operations": {
            "publish/%s" % n: {"action": "send",
                               # 通道键含 `/`，JSON Pointer 必须转义（RFC 6901：`/` → `~1`）。
                               # 2026-09-24 他证实证修复：此前裸写 → 官方 @asyncapi/cli 报 443 条
                               # invalid-ref（`#/channels/nf/xxx` does not exist）。
                               "channel": {"$ref": "#/channels/%s" % _ptr("nf/%s" % n)}}
            for n in sorted(events)},
        "components": {"messages": messages},
        "x-nf-events": len(events),
    }



def intoto_statement(root: str = ".") -> Dict[str, Any]:
    """协议层回执 → in-toto Statement v1（消费者：in-toto / cosign 系校验器）。"""
    rec = _read_json(root, RECEIPTS_REL)
    subject = [{"name": str(e.get("path") or ""),
                "digest": {"sha256": str(e.get("digest") or "")}}
               for e in (rec.get("entries") or [])]
    return {
        "_type": "https://in-toto.io/Statement/v1",
        "subject": subject,
        "predicateType": "https://ninfenz.dev/attestation/protocol-receipts/v1",
        "predicate": {
            "algorithm": rec.get("algorithm", ""),
            "root": rec.get("root", ""),
            "count": rec.get("count", len(subject)),
            "scope": rec.get("scope", ""),
            "note": "派生自 protocol/RECEIPTS.json；inclusion proof 留在原回执单根内。",
        },
    }



def sbom_doc(root: str = ".") -> Dict[str, Any]:
    """依赖登记面 → SPDX 2.3 风格 SBOM（消费者：外部依赖扫描器）。"""
    import sys

    nf_version = "0.0.0"
    verify_path = os.path.join(root, "verify.sh")
    if os.path.isfile(verify_path):
        with open(verify_path, encoding="utf-8") as fh:
            m = re.search(r"# 版本\s*:\s*(v[0-9.]+)", fh.read())
        if m:
            nf_version = m.group(1)
    sys.path.insert(0, os.path.join(root, "desktop", "src"))
    try:
        from core import purity_scan as ps
        hard = dict(ps.HARD_ALLOW)
        soft = dict(ps.SOFT_IMPORTS)
    except Exception:  # pragma: no cover - 登记面不可读即空表（门禁侧会报）
        hard, soft = {}, {}
    packages: List[Dict[str, Any]] = [{
        "SPDXID": "SPDXRef-Package-ninfenz",
        "name": "NinFenz",
        "versionInfo": nf_version,
        "downloadLocation": "NOASSERTION",
        "licenseConcluded": LICENSE_NAME,
        "licenseDeclared": LICENSE_NAME,
        "copyrightText": "NOASSERTION",
    }]
    pinned = _pinned_versions(root)

    def _dep_meta(name: str) -> Dict[str, Any]:
        """依赖包的版本证据（审计 Z4）：钉版在场 → versionInfo + pip purl；不在场 → 留空。"""
        proj = _DEP_ALIAS.get(name.lower(), name.lower())
        ver = pinned.get(proj, "")
        if not ver:
            return {}
        return {"versionInfo": ver,
                "externalRefs": [{"referenceCategory": "PACKAGE-MANAGER",
                                  "referenceType": "purl",
                                  "referenceLocator": "pkg:pypi/%s@%s" % (proj, ver)}]}

    deps: List[Tuple[str, str]] = []
    for name, why in sorted(hard.items()):
        pkg = "SPDXRef-Dependency-%s" % name
        packages.append({"SPDXID": pkg, "name": name, "downloadLocation": "NOASSERTION",
                         "licenseConcluded": "NOASSERTION",
                         "comment": "硬依赖（登记）：%s" % why, **_dep_meta(name)})
        deps.append((pkg, "DEPENDENCY_OF"))
    for name, why in sorted(soft.items()):
        pkg = "SPDXRef-Optional-%s" % name
        packages.append({"SPDXID": pkg, "name": name, "downloadLocation": "NOASSERTION",
                         "licenseConcluded": "NOASSERTION",
                         "comment": "软依赖（可选，须 try/except 守卫）：%s" % why,
                         **_dep_meta(name)})
        deps.append((pkg, "OPTIONAL_DEPENDENCY_OF"))
    return {
        "spdxVersion": "SPDX-2.3",
        "dataLicense": "CC0-1.0",
        "SPDXID": "SPDXRef-DOCUMENT",
        "name": "ninfenz-sbom",
        "documentNamespace": "https://ninfenz.dev/spdx/%s" % nf_version,
        "creationInfo": {
            "creators": ["Tool: nf interop --kind sbom"],
            "created": ("%sT00:00:00Z" % _declared_max_date(root)) if _declared_max_date(root)
                       else "",
            "comment": "由纯度扫描登记面（HARD_ALLOW / SOFT_IMPORTS）实时派生；"
                       "created = 仓内声明日期最大值（非墙钟，保确定性）",
        },
        # SPDX 2.3 根级允许 `comment`（`documentComment` 不在词表内，实测被 meta-schema 拦下）
        "comment": "派生面非真源；created = max(仓内声明日期: "
                   "score_baseline / provenance / approvals)（保确定性，非墙钟）。",
        "packages": packages,
        "relationships": ([{"spdxElementId": "SPDXRef-DOCUMENT",
                            "relatedSpdxElement": "SPDXRef-Package-ninfenz",
                            "relationshipType": "DESCRIBES"}]
                          + [{"spdxElementId": pkg,
                              "relatedSpdxElement": "SPDXRef-Package-ninfenz",
                              "relationshipType": rel} for pkg, rel in deps]),
    }



def slsa_provenance(root: str = ".") -> Dict[str, Any]:
    """SLSA Provenance v1（in-toto predicate）——从**本地门禁事实**派生，不宣称外部构建。

    诚实边界：NF 的「构建」= 本地 verify 门禁（无远程 builder、无托管构建平台），
    因此 `builder.id` 指向本仓门禁脚本、`buildType` 是 NF 自定义型别，并在 `metadata` 里
    写明这不是 SLSA 认证等级声明。派生源 = verify.sh 版本头 + `protocol/score_baseline.json`
    + `protocol/RECEIPTS.json`（三者都是既有真源）。
    """
    rec = _read_json(root, RECEIPTS_REL)
    # 基线句的真源 = core.quality_baseline（verify.sh 为单一真值，本模块只读期望值）；
    # 不读 score_baseline.json——它只有分数与信号，没有 check 数/PASS 数（早期写成 0 的真事故）。
    import sys as _sys
    _sys.path.insert(0, os.path.join(root, "desktop", "src"))
    try:
        from core import quality_baseline as qb
        want_checks, want_pass = qb.EXPECTED_CHECKS, qb.EXPECTED_PASS
    except Exception:  # pragma: no cover - 真源不可读即 0（门禁侧会判 FAIL）
        want_checks = want_pass = 0
    version = ""
    verify_path = os.path.join(root, "verify.sh")
    if os.path.isfile(verify_path):
        with open(verify_path, encoding="utf-8") as fh:
            m = re.search(r"# 版本\s*:\s*(v[0-9.]+)", fh.read())
        version = m.group(1) if m else ""
    subjects = [{"name": str(e.get("path") or ""),
                 "digest": {"sha256": str(e.get("digest") or "")}}
                for e in (rec.get("entries") or [])]
    return {
        "_type": "https://in-toto.io/Statement/v1",
        "subject": subjects,
        "predicateType": "https://slsa.dev/provenance/v1",
        "predicate": {
            "buildDefinition": {
                "buildType": "https://ninfenz.dev/buildtypes/local-gate/v1",
                "externalParameters": {
                    "gate": "verify.sh",
                    "gateVersion": version,
                    "declaredBaseline": "check1-%d PASS=%d" % (
                        want_checks, want_pass),
                    "note": "参数取自仓内声明件（不引入新真源）",
                },
                "internalParameters": {"repoRoot": "relative"},
                "resolvedDependencies": [{"uri": "nf://repo/%s" % s["name"]}
                                         for s in subjects],
            },
            "runDetails": {
                "builder": {"id": "https://ninfenz.dev/builder/verify-sh"},
                "metadata": {
                    "invocationId": str(rec.get("root") or "")[:16],
                    "note": "本地门禁执行事实；**不构成 SLSA 等级声明**（无远程 builder）",
                },
            },
        },
    }
