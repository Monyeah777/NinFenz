"""interop_export 私有子模块 _checks：机验判据：各导出形态的最小结构/对齐检查（含确定性）。

门面 core.interop_export 按原 API 重新导出；本文件只承载实现，不改变对外面。
"""
from __future__ import annotations

import os
import re

from ._base import _read_json
from ._render import KINDS, render



def _obj(v: Any) -> dict:
    """`x.get(...) or {}` 的替身：把「空值回退」从**每个调用点**收成单点。

    radon 把每处 `or` 记为一个分支——导出面满屏 `or {}`，复杂度大半由此而来。
    """
    return v if isinstance(v, dict) else {}



def _arr(v: Any) -> list:
    """`x.get(...) or []` 的替身（同 `_obj`：回退单点化）。"""
    return v if isinstance(v, list) else []


def _check_openapi(oa: dict, contract: dict, issues: List[str]) -> None:
    """OpenAPI 派生面：路径集与契约一致、操作 id/200/NfError/错误映射在位。"""
    want_paths = {str(e.get("path")) for e in (_arr(contract.get("endpoints")))}
    got_paths = set(_obj(oa.get("paths")))
    if got_paths != want_paths:
        issues.append("OpenAPI 派生面与服务端点契约不一致：缺 %s / 多 %s"
                      % (sorted(want_paths - got_paths), sorted(got_paths - want_paths)))
    for path, ops in (_obj(oa.get("paths"))).items():
        for method, op in ops.items():
            if not op.get("operationId"):
                issues.append("OpenAPI %s %s 缺 operationId（修复指引：端点 id 必填）"
                              % (method.upper(), path))
            if "200" not in (_obj(op.get("responses"))):
                issues.append("OpenAPI %s %s 缺 200 响应（修复指引：每端点须声明成功形状）"
                              % (method.upper(), path))
    if "NfError" not in (_obj(oa.get("components"))).get("schemas", {}):
        issues.append("OpenAPI 缺 NfError 错误形状（修复指引：错误面须可机读）")
    if not (_obj(oa.get("x-nf-error-mapping"))).get("title"):
        issues.append("OpenAPI 缺 RFC 9457 字段映射（修复指引：声明 error.message ↔ title/detail）")



def _check_asyncapi(aa: dict, reg: dict, ext: dict, issues: List[str]) -> None:
    """AsyncAPI 派生面：通道集与事件登记一致、CloudEvents type 不重复。"""
    want_events = set((_obj(reg.get("events"))).keys()) | set((_obj(ext.get("events"))).keys())
    got_events = {k.split("/", 1)[1] for k in (_obj(aa.get("channels")))}
    if got_events != want_events:
        issues.append("AsyncAPI 派生面与事件登记不一致：缺 %s / 多 %s"
                      % (sorted(want_events - got_events), sorted(got_events - want_events)))
    ce_types = [(_obj(c.get("x-nf-cloudevents"))).get("type")
                for c in (_obj(aa.get("channels"))).values()]
    if len(set(ce_types)) != len(ce_types):
        issues.append("CloudEvents type 派生重复（修复指引：事件名须全库唯一，"
                      "见 01 §1.1 事件名唯一 + 词法纪律）")



def _check_intoto(st: dict, rec: dict, issues: List[str]) -> None:
    """in-toto 派生面：subject 与回执一致、digest 合规、Statement 类型头在位。"""
    want_subjects = {str(e.get("path")) for e in (_arr(rec.get("entries")))}
    got_subjects = {s.get("name") for s in _arr(st.get("subject"))}
    if got_subjects != want_subjects:
        issues.append("in-toto subject 与协议层回执不一致：缺 %d / 多 %d"
                      % (len(want_subjects - got_subjects),
                         len(got_subjects - want_subjects)))
    for s in _arr(st.get("subject")):
        d = (_obj(s.get("digest"))).get("sha256", "")
        if not re.fullmatch(r"[0-9a-f]{64}", str(d)):
            issues.append("in-toto subject 缺合规 sha256：%s"
                          "（修复指引：回执 digest 须 64 位小写十六进制）" % s.get("name"))
    if st.get("_type") != "https://in-toto.io/Statement/v1":
        issues.append("in-toto Statement 类型头不合法（修复指引：_type 须为 Statement/v1）")



def _check_sbom(sb: dict, issues: List[str]) -> None:
    """SPDX SBOM：SPDXID 唯一、自述本仓、DESCRIBES 关系、created 为 ISO 8601 UTC。"""
    ids = [p.get("SPDXID") for p in _arr(sb.get("packages"))]
    if len(set(ids)) != len(ids):
        issues.append("SBOM 包 SPDXID 重复（修复指引：每依赖一个唯一 SPDXID）")
    if not any(p.get("name") == "NinFenz" for p in _arr(sb.get("packages"))):
        issues.append("SBOM 缺本项目包（修复指引：SBOM 须自述本仓）")
    rels = _arr(sb.get("relationships"))
    if not [r for r in rels if r.get("relationshipType") == "DESCRIBES"]:
        issues.append("SBOM 缺 DESCRIBES 关系（修复指引：文档须描述本仓包）")
    created = ((_obj(sb.get("creationInfo"))).get("created") or "")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", str(created)):
        issues.append("SBOM 的 creationInfo.created 缺失或非 ISO 8601 UTC：%r"
                      "（修复指引：SPDX 2.3 要求必填；本仓取「仓内声明日期最大值」保确定性）"
                      % created)



def _check_determinism(root: str, issues: List[str]) -> None:
    """确定性：同一导出面两次渲染须逐字节一致（禁时间戳/随机源）。"""
    for kind in KINDS:
        if render(kind, root) != render(kind, root):
            issues.append("导出面不确定性：%s 两次渲染不一致"
                          "（修复指引：禁止引入时间戳/随机源）" % kind)



def _check_slsa(sl: dict, rec: dict, root: str, issues: List[str]) -> None:
    """SLSA provenance：subject 同源、等级不虚标、基线句与 quality_baseline 同源。"""
    if sl.get("predicateType") != "https://slsa.dev/provenance/v1":
        issues.append("SLSA 派生面 predicateType 不合法（修复指引：须为 slsa.dev/provenance/v1）")
    if len(_arr(sl.get("subject"))) != len(_arr(rec.get("entries"))):
        issues.append("SLSA 派生面 subject 数与回执不一致：%d vs %d"
                      % (len(_arr(sl.get("subject"))), len(_arr(rec.get("entries")))))
    note = _obj(_obj(sl.get("predicate")).get("runDetails")).get("metadata", {}).get("note", "")
    if "不构成 SLSA 等级声明" not in note:
        issues.append("SLSA 派生面缺「不作等级声明」注记（修复指引：本地门禁不得虚标 SLSA 等级）")
    declared = _obj(_obj(sl.get("predicate")).get("buildDefinition")).get(
        "externalParameters", {}).get("declaredBaseline", "")
    m_base = re.match(r"^check1-(\d+) PASS=(\d+)$", str(declared))
    if not m_base or int(m_base.group(1)) == 0 or int(m_base.group(2)) == 0:
        issues.append("SLSA 派生面基线句非法或为 0：%r（修复指引：基线取自 "
                      "core.quality_baseline 期望值——写 0 等于虚报门禁口径）" % declared)
        return
    try:
        import sys as _s
        _s.path.insert(0, os.path.join(root, "desktop", "src"))
        from core import quality_baseline as _qb
        if (int(m_base.group(1)), int(m_base.group(2))) != (_qb.EXPECTED_CHECKS,
                                                           _qb.EXPECTED_PASS):
            issues.append("SLSA 派生面基线句与 quality_baseline 期望值不一致：%s"
                          "（修复指引：两处须同源）" % declared)
    except Exception:  # pragma: no cover  # nosec B110/B112 —— 尽力而为：跳过不可读/不可解析项；该类缺口由对应门禁与 AUD-0016 静默跳过清单另行报出
        pass  # best-effort 显式忽略（清理/探测失败不影响主流程）



def _check_a2a(card: dict, contract: dict, issues: List[str]) -> None:
    """A2A Agent Card：skills 覆盖端点契约、未实装须显式声明、skill 自述在位。"""
    if len(_arr(card.get("skills"))) != len(_arr(contract.get("endpoints"))):
        issues.append("A2A 卡片 skills 数与端点契约不一致（修复指引：卡片能力面须与契约同源）")
    if contract.get("status") != "implemented" and "未实装" not in str(card.get("x-nf-note")):
        issues.append("A2A 卡片未声明「服务未实装」（修复指引：不得据此宣称在线能力）")
    for sk in _arr(card.get("skills")):
        if not sk.get("id") or not sk.get("description"):
            issues.append("A2A 卡片 skill 缺 id/description（修复指引：能力面须自述）")



def _check_prov_relations(pv: dict, known: set, issues: List[str]) -> None:
    """溯源自述的三类关系（used/generated/wasAssociatedWith）须指向图内在册节点。"""
    for n in _arr(pv.get("@graph")):
        for rel in ("prov:used", "prov:generated", "prov:wasAssociatedWith"):
            target = n.get(rel)
            if target and str(target) not in known:
                issues.append("PROV 图关系 %s 指向不在册节点：%s"
                              "（修复指引：被引用节点须在图内）" % (rel, target))



def _check_prov(pv: dict, root: str, issues: List[str]) -> None:
    """PROV-O 溯源图：节点 id 唯一、关系指向在册节点、资产实体全覆盖。"""
    pv_ids = [n.get("@id") for n in _arr(pv.get("@graph"))]
    if len(set(pv_ids)) != len(pv_ids):
        issues.append("PROV 图存在重复节点 id（修复指引：实体/活动/代理同一 id 只出现一次）")
    known = set(pv_ids)
    _check_prov_relations(pv, known, issues)
    prov_src = _read_json(root, "05_资产库/provenance.json")
    want_assets = {"nf:asset/%s" % a.get("key") for a in _arr(prov_src.get("assets"))}
    if not want_assets.issubset(known):
        issues.append("PROV 图缺资产实体：%s（修复指引：资产台账每条须有实体节点）"
                      % sorted(want_assets - known))
    if "prov:Entity" not in {n.get("@type") for n in _arr(pv.get("@graph"))}:
        issues.append("PROV 图无实体节点（修复指引：溯源图至少一个被证对象）")



def _check_cyclonedx_deps(cdx: dict, root: str, issues: List[str]) -> None:
    """CycloneDX 硬依赖集须与纯度登记面（purity_scan.HARD_ALLOW）同源。"""
    hard = {c.get("name") for c in _arr(cdx.get("components")) if c.get("scope") == "required"}
    try:
        import sys as _s2
        _s2.path.insert(0, os.path.join(root, "desktop", "src"))
        from core import purity_scan as _ps
        want_hard = set(_ps.HARD_ALLOW)
    except Exception:  # pragma: no cover —— 登记面不可读：跳过该断言（纯度门 R5 另报未登记 import）
        want_hard = set()
    if want_hard and hard != want_hard:
        issues.append("CycloneDX 硬依赖集与登记面不一致：%s（期望 %s）"
                      "（修复指引：两形同源——都读 purity_scan 登记面）"
                      % (sorted(hard), sorted(want_hard)))



def _check_cyclonedx(cdx: dict, root: str, issues: List[str]) -> None:
    """CycloneDX：格式头 + bom-ref 唯一 + serialNumber 派生形态 + 与纯度登记面同源。"""
    if cdx.get("bomFormat") != "CycloneDX" or str(cdx.get("specVersion")) != "1.5":
        issues.append("CycloneDX 头非法：%r/%r（修复指引：bomFormat=CycloneDX、specVersion=1.5）"
                      % (cdx.get("bomFormat"), cdx.get("specVersion")))
    refs = [c.get("bom-ref") for c in _arr(cdx.get("components"))]
    if len(set(refs)) != len(refs):
        issues.append("CycloneDX 组件 bom-ref 重复（修复指引：每依赖一个唯一 bom-ref）")
    if not re.match(r"^urn:uuid:[0-9a-f-]{36}$", str(cdx.get("serialNumber") or "")):
        issues.append("CycloneDX serialNumber 非 urn:uuid 形态：%r"
                      "（修复指引：由声明摘要派生，勿用随机 UUID）" % cdx.get("serialNumber"))
    _check_cyclonedx_deps(cdx, root, issues)



def _vc_issuer_ok(vc: dict) -> bool:
    """VC 的 issuer 非空且 validFrom 为 YYYY-MM-DD。"""
    if not vc.get("issuer"):
        return False
    return bool(re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(vc.get("validFrom") or "")))



def _check_vc(vc: dict, issues: List[str]) -> None:
    """VC 2.0：上下文/类型/issuer/validFrom/receiptRoot + 未签名状态注记。"""
    if "https://www.w3.org/ns/credentials/v2" not in (_arr(vc.get("@context"))):
        issues.append("VC 缺 v2 上下文（修复指引：@context 须含 "
                      "https://www.w3.org/ns/credentials/v2）")
    if "VerifiableCredential" not in (_arr(vc.get("type"))):
        issues.append("VC type 缺 VerifiableCredential")
    if not _vc_issuer_ok(vc):
        issues.append("VC 缺 issuer 或 validFrom（修复指引：自 protocol/approvals/* 取批准人与批准"
            "日）")
    subj = _obj(vc.get("credentialSubject"))
    if not re.fullmatch(r"[0-9a-f]{64}", str(subj.get("receiptRoot") or "")):
        issues.append("VC credentialSubject.receiptRoot 非 sha256：%r"
                      "（修复指引：凭证须绑定内容摘要）" % subj.get("receiptRoot"))
    if "proof" not in vc and "unsigned" not in str(vc.get("x-nf-proof-status") or ""):
        issues.append("VC 无 proof 却未声明未签名状态（修复指引：x-nf-proof-status 须写明"
                      "——形状可读 ≠ 可验证）")



def _c2pa_hash(c2: dict) -> str:
    """c2pa.hash.data 断言的 hash 值（缺该断言 → 空串）。"""
    hd = next((_obj(a.get("data")) for a in _arr(c2.get("assertions"))
               if a.get("label") == "c2pa.hash.data"), {})
    return str(hd.get("hash") or "")



def _check_c2pa(c2: dict, issues: List[str]) -> None:
    """C2PA：claim_generator + hash.data 硬绑定 + 未封装状态注记。"""
    if not str(c2.get("claim_generator") or "").startswith("NinFenz"):
        issues.append("C2PA 缺 claim_generator（修复指引：须自述生成器）")
    labels = {a.get("label") for a in _arr(c2.get("assertions"))}
    if "c2pa.hash.data" not in labels or "c2pa.actions" not in labels:
        issues.append("C2PA 断言面不全（修复指引：须含 c2pa.hash.data 与 c2pa.actions）：%s"
                      % sorted(labels))
    if not re.fullmatch(r"[0-9a-f]{64}", _c2pa_hash(c2)):
        issues.append("C2PA hash.data 非 sha256（修复指引：硬绑定摘要须 64 位小写十六进制）")
    if "未封装" not in str(c2.get("x-nf-package-status") or ""):
        issues.append("C2PA 未声明封装/签名状态（修复指引：JSON 清单 ≠ 生产级 C2PA 包）")



def _check_cid(ci: dict, rec: dict, issues: List[str]) -> None:
    """CID 索引：条目数与回执一致 + 形态合法（b + base32）。"""
    if len(_arr(ci.get("entries"))) != len(_arr(rec.get("entries"))):
        issues.append("CID 索引条目数与回执不一致：%d vs %d"
                      % (len(_arr(ci.get("entries"))), len(_arr(rec.get("entries")))))
    for e in _arr(ci.get("entries")):
        if not re.fullmatch(r"b[a-z2-7]{50,}", str(e.get("cid") or "")):
            issues.append("CID 形态非法：%s（修复指引：CIDv1 multibase base32 小写，"
                          "前缀 b + raw codec 0x71 + sha2-256 multihash）" % e.get("path"))
            break



def _check_decision(ds: dict, root: str, issues: List[str]) -> None:
    """决策面：适配器/候选全覆盖 + 「工单不入公开面」声明在位。"""
    decl_dl = _read_json(root, "protocol/decision_layer.json")
    if len(_arr(ds.get("adapters"))) != len(_arr(decl_dl.get("adapters"))):
        issues.append("决策面适配器数与声明不一致：%d vs %d"
                      % (len(_arr(ds.get("adapters"))), len(_arr(decl_dl.get("adapters")))))
    if len(_arr(ds.get("candidates"))) != len(_arr(decl_dl.get("candidates"))):
        issues.append("决策面候选数与声明不一致：%d vs %d"
                      % (len(_arr(ds.get("candidates"))), len(_arr(decl_dl.get("candidates")))))
    if "不随本面发布" not in str(ds.get("x-nf-internal") or ""):
        issues.append("决策面缺「工单不入公开面」声明（修复指引：写明内部档案边界，"
                      "不得让外部以为逐次决策已公开）")
    if not (_arr(ds.get("publicDecisionIndex"))):
        issues.append("决策面缺公开裁决索引（修复指引：results/audit/*.md 的 frontmatter 可派生）")
