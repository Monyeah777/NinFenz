"""interop_export 私有子模块 _docs_b：导出文档 B 组：PROV / CycloneDX / VC / C2PA / CID 索引 / 决策面 / A2A Agent Card。

门面 core.interop_export 按原 API 重新导出；本文件只承载实现，不改变对外面。
"""
from __future__ import annotations

import os
import re

from ._base import CONTRACT_REL, LICENSE_NAME, RECEIPTS_REL, _DEP_ALIAS, _pinned_versions, _read_json
from ._docs_a import sbom_doc
from ._prov import (
    _add_node,
    _asset_entities,
    _library_nodes,
    _prov_counts,
    _receipt_entities,
    _transform_activities,
    _verify_agent,
)



def prov_document(root: str = ".") -> Dict[str, Any]:
    """PROV-O（W3C Provenance Ontology）派生面：资产 / 馆藏 / 回执 → 实体·活动·代理三元组。

    真源：`05_资产库/provenance.json`（资产）+ `library/INDEX.md`（馆藏行）+
    `protocol/transform_log.json`（消化活动）+ `protocol/RECEIPTS.json`（回执绑定）。
    诚实边界：只写仓内**已有**的事实（谁何时入库、资产属谁、改了什么），不推断来源；
    空面如实为空（transform_log 当前 0 条 → activities 里就没有消化活动）。
    """
    prov = _read_json(root, "05_资产库/provenance.json")
    transform = _read_json(root, "protocol/transform_log.json")
    rec = _read_json(root, RECEIPTS_REL)
    nodes: Dict[str, Dict[str, Any]] = {}
    for node in _asset_entities(prov):
        _add_node(nodes, node)
    for node in _library_nodes(root):
        _add_node(nodes, node)
    for node in _receipt_entities(rec):
        _add_node(nodes, node)
    for node in _transform_activities(transform):
        _add_node(nodes, node)
    _add_node(nodes, _verify_agent(root))
    graph = [nodes[k] for k in sorted(nodes)]
    return {
        "@context": {"prov": "http://www.w3.org/ns/prov#",
                     "nf": "https://ninfenz.dev/ns#"},
        "schema": "nf-prov/1",
        "note": "由仓内声明件派生（资产 / 馆藏 / 消化记录 / 回执）；本文件非真源，"
                "空面即如实为空。",
        "@graph": graph,
        "x-nf-counts": _prov_counts(graph),
    }



def cyclonedx_doc(root: str = ".") -> Dict[str, Any]:
    """CycloneDX 1.5 SBOM（派生自依赖登记面 + LICENSE）——SPDX 之外的第二个 SBOM 形状。

    与 `sbom_doc`（SPDX 2.3）**同源不同形**：都读 `purity_scan.HARD_ALLOW / SOFT_IMPORTS`，
    因此不存在「两份 SBOM 互相漂移」的问题；`serialNumber` 用内容寻址的 urn:uuid
    形式（由本仓声明摘要派生，保确定性，非随机 UUID）。
    """
    sbom = sbom_doc(root)
    import sys as _sys
    _sys.path.insert(0, os.path.join(root, "desktop", "src"))
    try:
        from core import purity_scan as ps
        hard, soft = dict(ps.HARD_ALLOW), dict(ps.SOFT_IMPORTS)
    except Exception:  # pragma: no cover
        hard, soft = {}, {}
    import hashlib
    seed = hashlib.sha256((sbom.get("documentNamespace") or "").encode("utf-8")).hexdigest()
    serial = "urn:uuid:%s-%s-%s-%s-%s" % (seed[:8], seed[8:12], seed[12:16],
                                          seed[16:20], seed[20:32])
    pinned = _pinned_versions(root)

    def _purl(name: str) -> Dict[str, Any]:
        proj = _DEP_ALIAS.get(name.lower(), name.lower())
        ver = pinned.get(proj, "")
        return ({"version": ver, "purl": "pkg:pypi/%s@%s" % (proj, ver)} if ver else {})

    components = []
    for name, why in sorted(hard.items()):
        components.append({"type": "library", "bom-ref": "dep:%s" % name, "name": name,
                           "scope": "required", "description": "硬依赖（登记）：%s" % why,
                           **_purl(name)})
    for name, why in sorted(soft.items()):
        components.append({"type": "library", "bom-ref": "opt:%s" % name, "name": name,
                           "scope": "optional",
                           "description": "软依赖（可选，须守卫）：%s" % why,
                           **_purl(name)})
    return {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "serialNumber": serial,
        "version": 1,
        "metadata": {
            "timestamp": sbom.get("creationInfo", {}).get("created", ""),
            "component": {"type": "application", "bom-ref": "pkg:nf/ninfenz@%s"
                          % sbom.get("packages", [{}])[0].get("versionInfo", "0.0.0"),
                          "name": "NinFenz",
                          "licenses": [{"license": {"id": LICENSE_NAME}}]},
            "tools": [{"vendor": "NinFenz", "name": "nf interop --kind cyclonedx",
                       "version": "1.0.0"}],
            # CycloneDX 根级 additionalProperties=false（官方 meta-schema 实测拦下自定义键）
            # → 自述信息只许落在 metadata.properties 里
            "properties": [
                {"name": "nf:source", "value": "purity_scan 依赖登记面（纯派生）"},
                {"name": "nf:note",
                 "value": "与 SPDX 面同源；timestamp 取仓内声明日期最大值（非墙钟）。"},
            ],
        },
        "components": components,
    }



def _approvals(root: str) -> List[Dict[str, Any]]:
    """protocol/approvals/*.json 的在场审批记录（读不出的跳过）。"""
    approvals: List[Dict[str, Any]] = []
    adir = os.path.join(root, "protocol", "approvals")
    if os.path.isdir(adir):
        for name in sorted(os.listdir(adir)):
            if name.endswith(".json"):
                a = _read_json(root, os.path.join("protocol", "approvals", name))
                if a:
                    approvals.append(a)
    return approvals


def _first_approval_field(approvals: List[Dict[str, Any]], field: str) -> str:
    """首条审批记录的某字段（无审批 → 空串）。"""
    return str((approvals[0].get(field) if approvals else "") or "")


def vc_document(root: str = ".") -> Dict[str, Any]:
    """W3C Verifiable Credential（VC Data Model 2.0 形状）——内容绑定的「一致性凭证」。

    诚实边界：**未签名**。VC 的可验证性来自 proof（JWS/Data Integrity），而 NF 的签名走
    ssh 外挂锚（`nf attest` + `library/anchors/*.sig`），两者套件不同；故本件产出
    **未签名凭证形状**并把状态写进 `x-nf-proof-status`（门禁判该注记必须在场）——
    形状可被 VC 工具链读，但**不宣称可验证**。
    """
    rec = _read_json(root, RECEIPTS_REL)
    rep = _read_json(root, "protocol/conformance_report.json")
    approvals = _approvals(root)
    issuer = _first_approval_field(approvals, "approved_by") or "NinFenz"
    valid_from = _first_approval_field(approvals, "approved_at")
    return {
        "@context": ["https://www.w3.org/ns/credentials/v2",
                     "https://ninfenz.dev/ns/credentials/v1"],
        "type": ["VerifiableCredential", "NfConformanceCredential"],
        "issuer": issuer,
        "validFrom": valid_from,
        "credentialSubject": {
            "id": "nf:conformance_report",
            "verdict": str(rep.get("verdict") or ""),
            "contracts": len(rep.get("contracts") or []),
            "receiptRoot": str(rec.get("root") or ""),
            "receiptCount": int(rec.get("count") or 0),
        },
        "x-nf-proof-status": "unsigned（本仓签名走 ssh 外挂锚 nf attest；未接 JWS/Data Integrity "
                             "签名套件——形状可读，不可验证，勿当凭证使用）",
        "x-nf-note": "派生自 protocol/conformance_report.json + protocol/RECEIPTS.json + "
                     "protocol/approvals/*（纯派生，不新增真源）",
    }



def c2pa_manifest(root: str = ".") -> Dict[str, Any]:
    """C2PA 内容凭证的 **JSON 清单形态**（未做 JUMBF/CBOR 封装、未签名）。

    取 C2PA 2.x 的 JSON 表示字段面（`claim_generator` / `assertions[label,data]`），
    硬绑定用 `c2pa.hash.data`（sha256）指向被证内容——与回执/attest 同一份摘要口径。
    诚实边界：生产级 C2PA 需要 CBOR/JUMBF 封装与 X.509 签名，本仓**不做**（无证书链），
    故只出 JSON 清单并把状态写进 `x-nf-package-status`（门禁判该注记在场）。
    """
    rec = _read_json(root, RECEIPTS_REL)
    sample = next((e for e in (rec.get("entries") or []) if e.get("path")), None)
    assertions = [{"label": "c2pa.actions",
                   "data": {"actions": [{"action": "c2pa.created",
                                         "digitalSourceType": "http://cv.iptc.org/newscodes/"
                                                              "digitalsourcetype/digitalCapture"
                                                                  ""}]}}]
    if sample:
        assertions.append({"label": "c2pa.hash.data",
                           "data": {"alg": "sha256", "hash": str(sample.get("digest") or ""),
                                    "name": str(sample.get("path"))}})
    return {
        "claim_generator": "NinFenz/1.0 (nf interop --kind c2pa)",
        "claim_generator_info": [{"name": "NinFenz", "version": "1.0.0"}],
        "title": "NinFenz 协议层内容清单",
        "format": "application/json",
        "assertions": assertions,
        "x-nf-package-status": "未封装（无 JUMBF/CBOR 容器）、未签名（无 X.509 证书链）——"
                               "只出 JSON 清单形状，不得当作可验证内容凭证",
        "x-nf-source": "protocol/RECEIPTS.json（回执摘要）",
    }



def cid_index(root: str = ".") -> Dict[str, Any]:
    """内容寻址索引：回执 → CIDv1（multibase base32 / codec raw / sha2-256）。

    为什么有用：CID 给外部系统一个**自描述、可校验、跨系统唯一**的内容地址
    （multiformats 生态），不必依赖 NF 路径约定。实现只用标准库（`base64.b32encode`
    小写化去填充），故零依赖；已知向量见单测：raw codec（0x71）+ sha2-256 下
    `sha256("")` → `bafyreihdwdcefgh4dqkjv67uzcmw7ojee6xedzdetojuzjevtenxquvyku`
    （注：IPFS 空文件常见的 `bafkrei…` 是 dag-pb codec 0x70，非本面所用的 raw codec）。
    """
    import base64
    rec = _read_json(root, RECEIPTS_REL)

    def cidv1_raw_sha256(digest_hex: str) -> str:
        raw = bytes.fromhex(digest_hex)
        mh = b"\x12\x20" + raw               # 0x12 = sha2-256, 0x20 = 32 字节
        return "b" + base64.b32encode(b"\x01\x71" + mh).decode("ascii").lower().rstrip("=")

    entries = []
    for e in rec.get("entries") or []:
        d = str(e.get("digest") or "")
        entries.append({"path": str(e.get("path") or ""), "sha256": d,
                        "cid": cidv1_raw_sha256(d) if re.fullmatch(r"[0-9a-f]{64}", d) else ""})
    return {
        "schema": "nf-cid-index/1",
        "multibase": "base32 (lowercase, no padding, prefix 'b')",
        "codec": "raw (0x71)",
        "multihash": "sha2-256 (0x12)",
        "entries": entries,
        "x-nf-note": "派生自 protocol/RECEIPTS.json；CID 可被 multiformats 生态直接校验。",
    }



def _audit_record(path: str) -> dict | None:
    """单个公开审计件的 frontmatter 记录（无 id / 非 frontmatter / 读不到 → None）。"""
    try:
        with open(path, encoding="utf-8") as fh:
            head = fh.read(1200)
    except OSError:            # 尽力而为：读不到该审计件就跳过（缺件由 check35 回执门报出）
        return None
    if not head.startswith("---"):
        return None
    block = head.split("---", 2)[1]
    rec: dict[str, str] = {}
    for line in block.splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            rec[k.strip()] = v.strip()
    return rec if rec.get("id") else None


def _public_decision_index(root: str) -> list[dict]:
    """results/audit/*.md frontmatter → 公开决策与裁决索引。"""
    import glob as _glob
    out: list[dict] = []
    for p in sorted(_glob.glob(os.path.join(root, "results", "audit", "*.md"))):
        rec = _audit_record(p)
        if rec is not None:
            out.append({"id": rec.get("id"), "title": rec.get("title", ""),
                        "date": rec.get("date", ""), "verdict": rec.get("verdict", "")})
    return out


def _adapter_rows(decl: dict) -> list[dict]:
    """decision_layer.adapters → 决策面适配器行。"""
    return [{"id": a.get("id"), "kind": a.get("kind"),
             "inGatePath": a.get("in_gate_path"),
             "calibrated": a.get("calibrated")}
            for a in (decl.get("adapters") or [])]


def _candidate_rows(decl: dict) -> list[dict]:
    """decision_layer.candidates → 决策面候选行。"""
    return [{"id": c.get("id"), "source": c.get("source"),
             "license": c.get("license"), "pulled": c.get("pulled"),
             "evidence": str(c.get("evidence") or "")[:200],
             "local": ({"runtime": (c.get("local") or {}).get("runtime"),
                        "servedBy": (c.get("local") or {}).get("served_by")}
                       if c.get("local") else None)}
            for c in (decl.get("candidates") or [])]


def decision_surface(root: str = ".") -> Dict[str, Any]:
    """决策面（派生）：外部工具链能读到「本仓有哪些决策能力、按什么规则、模型拉取状态如何」。

    派生真源 = `protocol/decision_layer.json`（原语/适配器/候选/边界/workloop 契约）+
    `results/audit/*.md` 的 frontmatter（公开的决策与裁决**索引**：id/标题/日期/结论）。
    **不导出逐次工单**：工单与收口件留在内部档案（`STRATEGY §四` 计划内部消化），
    本面显式声明这一点（门禁判该声明必须在位），避免"看起来什么都导出了"的错觉。
    """
    decl = _read_json(root, "protocol/decision_layer.json")
    audits = _public_decision_index(root)
    return {
        "schema": "nf-decision-surface/1",
        "primitives": decl.get("primitives") or {},
        "responseContract": decl.get("response_contract") or {},
        "adapters": _adapter_rows(decl),
        "candidates": _candidate_rows(decl),
        "boundaries": decl.get("boundaries") or [],
        "workloop": decl.get("workloop") or {},
        "publicDecisionIndex": audits,
        "x-nf-internal": "逐次工单（挑活/风险/收口）留在内部档案 .rivet/private_archive/work_orders"
            "/，"
                         "不随本面发布（STRATEGY §四 计划内部消化）；本面只投影**能力与公开裁决索引"
                             "**。",
    }



def a2a_agent_card(root: str = ".") -> Dict[str, Any]:
    """A2A Agent Card（能力面投影）——skills 来自服务端点契约 + MCP 包声明，不新增真源。"""
    contract = _read_json(root, CONTRACT_REL)
    pkg = _read_json(root, "protocol/mcp_package.json")
    skills = []
    for ep in contract.get("endpoints") or []:
        skills.append({
            "id": str(ep.get("id") or ""),
            "name": str(ep.get("id") or ""),
            "description": "maps_to %s（%s %s）" % (ep.get("maps_to"), ep.get("method"),
                                                    ep.get("path")),
            "tags": ["ninfenz", "content-contract"],
        })
    return {
        "protocolVersion": "0.2.5",
        "name": "NinFenz",
        "description": "内容契约层：装配 / 质检 / 图书馆 / 一致性报告（只读面）",
        "url": "urn:nf:repo",
        "preferredTransport": "stdio",
        "version": str(pkg.get("version") or "1.0.0"),
        "capabilities": {"streaming": any(e.get("streaming")
                                         for e in (contract.get("endpoints") or [])),
                         "pushNotifications": False},
        "defaultInputModes": ["text/plain", "application/json"],
        "defaultOutputModes": ["text/plain", "application/json"],
        "skills": skills,
        "x-nf-note": "能力面 = protocol/endpoint_contract.json 的投影；服务本体 status=%s"
                     "（未实装，本卡不据此宣称在线）" % contract.get("status", ""),
    }
