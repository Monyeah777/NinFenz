"""domain_pack · _const（自 domain_pack.py 拆出；只移动代码，行为/文案不变）。"""
from __future__ import annotations

from typing import Dict, List, Tuple

# 导入闭包指纹：由调用方算（持久层不再反向依赖解析层，见 2026-09-29 拆环）
# ——故本模块**不再** import import_graph（残留的那行已于 2026-10-01 删除：定义后从未用到）
SPEC_DIR = ".rivet/private_archive/ai_packs/specs"


MANIFEST_REL = "protocol/domain_packs.json"


REGISTRY_REL = "desktop/src/core/registry.json"


STANDARDS_REL = "protocol/standards_catalog.json"


BINDING_REL = "protocol/standards_binding.json"


DOC02_REL = "02_联动注册表.md"


VERIFY_REL = "verify.sh"



#: 可用管线 id 池（避开层位 id P00/P10…/P80、官方 P00/P01/P90、既有包 P02–P08）
#: 管线 id 池（两位段）——避开层位 id（P00/P10/…/P80）、官方 P00/P01/P90 与既有包 P02–P08。
#: 两位段共 90 个；AI 品类清单有 100 类，**两位段不够**（2026-09-23 实测：第 83 个域包起无号可用），
#: 故按「模块号命名空间扩展」同源做法扩到三位：`P[0-9]{2,3}`（schema 已同步）。
PIPELINE_POOL: List[str] = (
    ["P09"] + ["P1%d" % i for i in range(1, 10)] + ["P2%d" % i for i in range(1, 10)]
    + ["P3%d" % i for i in range(1, 10)] + ["P4%d" % i for i in range(1, 10)]
    + ["P5%d" % i for i in range(1, 10)] + ["P6%d" % i for i in range(1, 10)]
    + ["P7%d" % i for i in range(1, 10)] + ["P8%d" % i for i in range(1, 10)]
    + ["P9%d" % i for i in range(1, 10)]
    # 三位段（P100–P199）：给清单剩下的域包用，避免与两位段/层位/官方号冲突
    + ["P%03d" % i for i in range(100, 200)]
)



SUB_COUNT = 12




# ---------------------------------------------------------------- 标准绑定（可扩展标准面）

#: 段默认 + 关键词规则 + 域码覆盖（与内部 `binding_rules.py` 同源；此处是**执行侧**副本，
#: 保证 core 不依赖 .rivet 内部档案——规则变更时两处同步由 check32 断言「绑定覆盖率 100%」。）
_STD_SECTION_DEFAULT = {
    "A": ["ietf-json-schema", "mlcommons-bench", "onnx"],
    "B": ["ietf-json-schema", "w3c-tabular-data", "frictionless-table"],
    "C": ["cncf-otel-semconv", "mlcommons-bench", "frictionless-table"],
    "D": ["nist-ai-rmf", "w3c-prov-o", "common-criteria"],
    "E": ["commonmark", "w3c-tabular-data", "w3c-epub33"],
    "F": ["nist-ai-rmf", "w3c-prov-o", "spdx-licenses"],
}


_STD_KEYWORD: List[Tuple[str, str]] = [
    ("许可|版权|知识产权|授权", "creativecommons"),
    ("隐私|个人信息|去标识|合规|监管", "gdpr"),
    ("安全|越狱|红队|攻击|对抗", "owasp-llm"),
    ("漏洞|缺陷|弱点", "cwe"),
    ("供应链|依赖", "spdx-3"),
    ("水印|溯源|凭证|内容来源", "c2pa-spec"),
    ("无障碍|可访问", "w3c-wcag22"),
    ("医疗|临床|病历|诊断", "hl7-fhir"),
    ("影像|放射", "dicom"),
    ("食品|餐饮|膳食", "codex-alimentarius"),
    ("政务|公共事务|政策", "oecd-ai"),
    ("教育|培训|组织学习", "unesco-ai"),
    ("金融|投研|风控|保险|绩效", "gips"),
    ("市场代码|证券", "iso10383"),
    ("支付|结算|清算", "iso20022"),
    ("制造|产线|设备|工业", "opcua"),
    ("能源|电力|电网", "iso-iec-42010"),
    ("农业|种植|养殖", "fao-food"),
    ("物流|仓储|运输", "w3c-wot"),
    ("交通|出行|车机|车辆|导航", "covesa-vss"),
    ("机械|机器人|协作", "eu-machinery"),
    ("固件|OTA|升级", "uptane"),
    ("地理|遥感|地图|空间|三维|点云", "opengeospatial"),
    ("时间线|时序|日期", "w3c-owl-time"),
    ("术语|词表|本体|知识图谱", "w3c-skos"),
    ("三元组|关系抽取", "rdf11"),
    ("溯源|证据链|审计", "w3c-prov-o"),
    ("约束|校验|schema|形状|契约", "ietf-json-schema"),
    ("表格|CSV|列式", "w3c-tabular-data"),
    ("数据集|元数据|标注", "mlcommons-croissant"),
    ("评测|基准|排行榜|跑分", "mlcommons-bench"),
    ("可观测|遥测|监控|日志|成本|可靠性", "cncf-otel-semconv"),
    ("接口|API|端点|服务|部署", "oasis-openapi"),
    ("事件|消息|通道", "cncf-cloudevents"),
    ("工具调用|智能体|工作流|Agent", "mcp"),
    ("多智能体|协同|编排", "a2a"),
    ("模型|推理|量化", "onnx"),
    ("提示|指令|模板", "commonmark"),
    ("图表|可视化|看板", "vega-lite"),
    ("流程|结构图|示意", "mermaid"),
    ("视频|剪辑|字幕", "oci-image"),
    ("音频|语音|声学|音乐|歌声", "w3c-webaudio"),
    ("图像|视觉|扩散|超分|抠图", "w3c-svg2"),
    ("文档|出版|排版|校对", "w3c-epub33"),
    ("公式|数学|符号|证明", "w3c-mathml3"),
    ("单位|量纲|计量", "onvif-ucum"),
    ("浮点|数值|精度|误差", "ieee-754"),
    ("时间戳|时区", "rfc3339"),
    ("检索|向量|嵌入|召回", "frictionless-package"),
    ("问答|知识库", "frictionless-table"),
    ("缓存|分块|上下文", "gfm"),
    ("训练|微调|对齐|蒸馏|偏好", "mlcommons-bench"),
    ("合成数据|数据生成|增强", "mlcommons-croissant"),
    ("采集|清洗|质量|异常|缺失", "frictionless-table"),
    ("权限|访问控制|治理", "nist-800-188"),
    ("风险|伦理|责任", "nist-ai-rmf"),
    ("管理体系|流程|制度", "iec-42001"),
]


_STD_BY_CODE = {
    "A01": ["ietf-json-schema", "mlcommons-bench"],
    "A02": ["w3c-svg2", "mlcommons-croissant"],
    "A09": ["osv", "cwe", "lsp"],
    "A10": ["w3c-mathml3", "peps"],
    "A11": ["arrow", "parquet"],
    "A12": ["mlcommons-bench", "nist-ai-rmf"],
    "A13": ["eu-machinery", "uptane"],
    "A14": ["onnx", "ieee-754"],
    "B09": ["oasis-sarif", "cwe", "osv"],
    "B10": ["nist-800-142", "peps"],
    "B12": ["w3c-tabular-data", "ietf-json-schema"],
    "C01": ["frictionless-table", "w3c-tabular-data"],
    "C08": ["mlcommons-bench", "oasis-sarif"],
    "C11": ["k8s-crd", "cncf-otel-otlp"],
    "C15": ["arrow", "parquet", "frictionless-package"],
    "C16": ["mcp", "oasis-openapi"],
    "C17": ["a2a", "mcp"],
    "C18": ["cncf-otel-semconv", "prometheus-exposition", "openmetrics"],
    "D01": ["hl7-fhir", "dicom"],
    "D04": ["gips", "iso10383"],
    "D20": ["rocrate", "datacite"],
    "E10": ["w3c-epub33", "w3c-epub-a11y"],
    "E13": ["peps", "osi-osd"],
    "E20": ["khronos-gltf", "w3c-webaudio"],
    "F04": ["creativecommons", "spdx-licenses"],
    "F09": ["osi-osd", "spdx-licenses"],
}




#: 数据真实性门槛（check32 domain_packs）：每包的「在册 + 本机实测」复合分
AUTHENTICITY_THRESHOLD = 0.95


#: 概念密度门槛（边/节点）：本轮扩到「双锚 + 标准依赖边」后的对齐基线
#: （上一波实测最小 1.0476 → 本波实测最小 1.2647；门槛按「只增不减」定在实测下界之下）
DENSITY_THRESHOLD = 1.25


#: 绑定标准的本机实测可达率门槛（bot 防护 / 付费墙类如实计入不可达）
REACHABLE_RATIO_THRESHOLD = 0.9



#: 载体锚（辅锚）关键词规则：细分名命中 → 该细分**产出承载形态**对应的标准。
#: 与主锚（域口径锚）分工：主锚 = 这条细分依据什么口径；辅锚 = 这条细分的产出靠什么承载/交换。
_STD_SUPPORT_KEYWORD: List[Tuple[str, str]] = [
    ("契约|schema|形状|校验|约束|字段", "ietf-json-schema"),
    ("表|CSV|列式|清单|台账", "w3c-tabular-data"),
    ("图|图表|可视化|看板|仪表", "vega-lite"),
    ("图示|流程|结构图|示意|拓扑", "mermaid"),
    ("溯源|来源|证据链|血缘|审计", "w3c-prov-o"),
    ("时间|时序|时间线|日期|时效", "ietf-ixdtf"),
    ("单位|量纲|计量", "onvif-ucum"),
    ("数值|精度|误差|浮点", "ieee-754"),
    ("遥测|监控|指标|成本|可靠性", "cncf-otel-semconv"),
    ("水印|凭证|内容来源|生成标识", "c2pa-spec"),
    ("依赖|供应链|SBOM|资产清单", "spdx-3"),
    ("文本|长文|提示|文档|写作", "commonmark"),
    ("授权|许可|版权|开源", "spdx-licenses"),
    ("身份|DID|权限|访问控制", "w3c-vc"),
    ("接口|API|端点|服务|部署", "oasis-openapi"),
    ("事件|消息|流|通道", "cncf-cloudevents"),
]



#: 载体锚的段默认池（无关键词命中时按 index 轮换；优先与主锚**异层**）
_STD_SUPPORT_SECTION: Dict[str, List[str]] = {
    "A": ["ietf-json-schema", "w3c-tabular-data", "vega-lite", "mermaid", "w3c-prov-o"],
    "B": ["ietf-json-schema", "w3c-tabular-data", "vega-lite", "commonmark", "w3c-prov-o"],
    "C": ["ietf-json-schema", "w3c-tabular-data", "vega-lite", "mermaid", "cncf-otel-semconv"],
    "D": ["ietf-json-schema", "w3c-prov-o", "vega-lite", "mermaid", "w3c-tabular-data"],
    "E": ["ietf-json-schema", "commonmark", "mermaid", "vega-lite", "w3c-tabular-data"],
    "F": ["ietf-json-schema", "w3c-prov-o", "spdx-3", "vega-lite", "mermaid"],
}




SYSTEM_CARD_SCHEMA_JSON = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "https://ninfenz.local/schema/domain-system-card.schema.json",
    "title": "域包系统卡（模型无关的机验形态）",
    "description": "机制借鉴 Model Cards / Datasheets / NIST AI RMF 的字段面（取机制，不引外部文本"
        "背书）："
                   "把「这个域包是什么 / 能做什么 / 不能做什么 / 怎么验的」写成有 schema 的数据。",
    "type": "object",
    "additionalProperties": False,
    "required": ["kind", "system", "intended_use", "limitations", "data", "evaluation",
                 "human_oversight", "risk_management", "out_of_scope", "not_claims"],
    "properties": {
        "kind": {"const": "nf-system-card/1"},
        "system": {
            "type": "object", "additionalProperties": False,
            "required": ["id", "name", "version", "kind_of_system", "model_agnostic"],
            "properties": {
                "id": {"type": "string", "pattern": "^[A-Z0-9-]{3,}$"},
                "name": {"type": "string", "minLength": 1},
                "version": {"type": "string", "pattern": "^\\d+\\.\\d+\\.\\d+$"},
                "kind_of_system": {"enum": ["domain-package", "pipeline", "module", "runtime"]},
                "model_agnostic": {"type": "boolean"},
            },
        },
        "intended_use": {
            "type": "object", "additionalProperties": False,
            "required": ["purpose", "consumers", "in_scope"],
            "properties": {
                "purpose": {"type": "string", "minLength": 8},
                "consumers": {"type": "array", "minItems": 1,
                              "items": {"type": "string", "minLength": 1}},
                "in_scope": {"type": "array", "minItems": 1,
                             "items": {"type": "string", "minLength": 1}},
            },
        },
        "limitations": {"type": "array", "minItems": 1,
                        "items": {"type": "string", "minLength": 8}},
        "data": {
            "type": "object", "additionalProperties": False,
            "required": ["sources", "provenance_policy", "personal_data"],
            "properties": {
                "sources": {"type": "array", "minItems": 1,
                            "items": {"type": "object", "additionalProperties": False,
                                      "required": ["id", "kind", "note"],
                                      "properties": {
                                          "id": {"type": "string", "minLength": 1},
                                          "kind": {"enum": ["self-authored",
                                                            "external-structure",
                                                            "repository-artifact",
                                                            "generated"]},
                                          "note": {"type": "string", "minLength": 3}}}},
                "provenance_policy": {"type": "string", "minLength": 8},
                "personal_data": {"enum": ["none", "synthetic-only", "unknown"]},
            },
        },
        "evaluation": {
            "type": "object", "additionalProperties": False,
            "required": ["method", "faces", "reproduce_command", "not_measured"],
            "properties": {
                "method": {"type": "string", "minLength": 8},
                "faces": {"type": "array", "minItems": 1,
                          "items": {"type": "object", "additionalProperties": False,
                                    "required": ["name", "gate", "result"],
                                    "properties": {
                                        "name": {"type": "string", "minLength": 2},
                                        "gate": {"type": "string", "minLength": 2},
                                        "result": {"type": "string", "minLength": 1}}}},
                "reproduce_command": {"type": "string", "minLength": 4},
                "not_measured": {"type": "array", "minItems": 1,
                                 "items": {"type": "string", "minLength": 4}},
            },
        },
        "human_oversight": {"type": "array", "minItems": 1,
                            "items": {"type": "string", "minLength": 8}},
        "risk_management": {
            "type": "object", "additionalProperties": False,
            "required": ["framework", "functions", "residual_risks"],
            "properties": {
                "framework": {"enum": ["NIST AI RMF 1.0", "ISO/IEC 42001", "none-declared"]},
                "functions": {"type": "object", "additionalProperties": False,
                              "required": ["GOVERN", "MAP", "MEASURE", "MANAGE"],
                              "properties": {
                                  k: {"type": "array", "minItems": 1,
                                      "items": {"type": "string", "minLength": 3}}
                                  for k in ("GOVERN", "MAP", "MEASURE", "MANAGE")}},
                "residual_risks": {"type": "array", "minItems": 1,
                                   "items": {"type": "string", "minLength": 8}},
            },
        },
        "out_of_scope": {"type": "array", "minItems": 1,
                         "items": {"type": "string", "minLength": 4}},
        "not_claims": {"type": "array", "minItems": 1,
                       "items": {"type": "string", "minLength": 8}},
    },
}




#: `scan()` 的全部输入：各包实况（community 全树）+ 名录/登记/绑定三类声明 + **域规格**
#: （`.rivet/private_archive/ai_packs/specs/*.json`，逐包一份）+ registry。
#:
#: **2026-09-29 实测教训**：这里原先写的是 `.rivet/**/*`（整棵私档）——于是「见证」要把
#: **676 MB**（含一个 628 MB 的模型文件）读一遍算摘要，一次唯一新状态里光这一项就 ~1.0 s ✗，
# : 而本扫描器其实只读那 100 份 specs（实测读盘面 = community 300 + specs 100 + protocol 3 + registr
# y 1）。
#: 收窄到 specs 之后，「读盘面 ⊆ 输入面」判据仍然绿。**输入面只该声明「真的读到的」**，
#: 宽到把无关大件卷进来，等于是给每条请求加一笔纯亏的见证成本。
SCAN_INPUTS = ("community/**/*", ".rivet/private_archive/ai_packs/specs/*.json",
               "protocol/*.json",
               "desktop/src/core/registry.json")
# ruff: noqa: UP035 — 拆分产物按需重复 typing 注解 import（债未新增）
