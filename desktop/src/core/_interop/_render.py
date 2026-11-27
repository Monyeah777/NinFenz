"""interop_export 私有子模块 _render：渲染入口：KINDS 登记表 + 确定性渲染。

门面 core.interop_export 按原 API 重新导出；本文件只承载实现，不改变对外面。
"""
from __future__ import annotations

import json

from ._docs_a import asyncapi_doc, intoto_statement, openapi_doc, sbom_doc, slsa_provenance
from ._docs_b import a2a_agent_card, c2pa_manifest, cid_index, cyclonedx_doc, decision_surface, prov_document, vc_document



KINDS = {
    "openapi": (openapi_doc, "OpenAPI 3.1 服务端点文档"),
    "asyncapi": (asyncapi_doc, "AsyncAPI 3.0 事件通道文档（含 CloudEvents 属性）"),
    "intoto": (intoto_statement, "in-toto Statement v1（协议层回执）"),
    "sbom": (sbom_doc, "SPDX 2.3 SBOM（依赖登记面）"),
    "slsa": (slsa_provenance, "SLSA Provenance v1（本地门禁构建声明）"),
    "a2a": (a2a_agent_card, "A2A Agent Card（能力面投影）"),
    "prov": (prov_document, "PROV-O 溯源图（资产 / 馆藏 / 消化 / 回执）"),
    "cyclonedx": (cyclonedx_doc, "CycloneDX 1.5 SBOM（与 SPDX 面同源）"),
    "vc": (vc_document, "W3C VC 2.0 形状（未签名，含状态注记）"),
    "c2pa": (c2pa_manifest, "C2PA JSON 清单形状（未封装/未签名）"),
    "cid": (cid_index, "CIDv1 内容寻址索引（multiformats）"),
    "decisions": (decision_surface, "决策面（决策能力 + 公开裁决索引；工单不入公开面）"),
}



def render(kind: str, root: str = ".") -> bytes:
    """确定性渲染（排序键 + UTF-8 + LF 尾）——两次调用逐字节一致。"""
    fn, _label = KINDS[kind]
    return (json.dumps(fn(root), ensure_ascii=False, indent=2, sort_keys=True)
            + "\n").encode("utf-8")
