---
id: AUD-0022
title: 可扩展标准目录扩面 126 → 370 条 + 全 100 包「双锚（主锚/辅锚）× 数据真实性」对齐 + 概念图纵深（密度 1.0476 → 1.2647）
date: 2026-09-24
scope: 作者指令「先搜集所有可扩展标准；把所有域包在概念密度与数据真实性上对齐，且质量纵深发展；默认可用决策模型与检索资料」——本件记录：标准目录扩面与依赖边、双锚绑定规则与实测、概念图纵深、数据真实性复合口径、门禁七判据，以及本波修掉的两处门禁根因（含一处真缺陷）
verdict: pass
auditor: 本轮执行者
subjects:
  - desktop/src/core/domain_pack.py:907304ba4ed1918ed3d44dcda4cdb1a1d1a9b0914e2f2d1f7f51859d9b9164f9
  - desktop/src/core/retriever.py:97409e06af9b66d2b30bfde8a660d90b661c008bfe002b0b0712b824c7f6c9c4
  - desktop/tests/test_retriever.py:d47265d825ae4e602c478074ccfa1baf34d3b4a635a067125880e9f62723a854
  - verify.sh:2f3ff458128e2ac56c7fd0de699011740286ccfd7b69f5ec666d8a755a7a88cc
  - docs/domain-packs.md:4c9ee3987699c24f1d78910281b446287dceebb3a77632ef458a07ba618f62d0

---
> 重审（2026-10-28）：tests-only 默认并行度 8→10（实测 285 s 拐点）

> 重审（2026-10-28）：D 第一刀：paths realpath 去重 + text_hygiene 二进制读取走 scan_memo + --pr 档

> 重审（2026-10-28）：tests-only 默认 8 片 + PermissionError 退避重试

> 重审（2026-10-27）：verify.sh: checks 档缓存 put/get 一致（mode=checks）

> 重审（2026-10-27）：checks-only 独立档位缓存（verify_cache mode=checks）

> 重审（2026-10-24）：CI 并发锁、Gitee 诊断与 ADR-0008 改变 verify/脚本字节；重审理由：相应测试与冻结链已同步

> 重审（2026-10-23）：OTLP ID 判据与合作一致性稳定性修正：traceId/spanId 定长 hex，缺失真源诊断去 OS errno

> 重审（2026-10-22）：CI 三刀合入后重绑（诊断目录绝对化/fetch-tags/wasm skip）

> 重审（2026-10-22）：测试执行器、进程原子与 Windows shell 解析修复后重算代码度量基线与角色投影；既有审计结论不变

> 重审（2026-10-19）：check39 挂载五分钟入口判据（docs/quickstart.md ↔ scripts/quickstart_check.sh），verify.sh 结构性新增子判据

> 重审（2026-10-19）：verify.sh 恢复并补 _NF_BG_TESTS_PID 声明

> 重审（2026-10-19）：verify.sh 补 _NF_BG_TESTS_PID 声明（set -u 下 pre-push 钩子炸点）

> 重审（2026-10-19）：EOL 归一 + 译件重签

> 重审（2026-10-19）：verify.sh 诊断目录/临时变量修复后重绑

> 重审（2026-10-19）：诊断目录兜底：TMPDIR/仓库内 .rivet/tmp

> 重审（2026-10-19）：full 重叠回退（实测更慢且内容面互扰）

> 重审（2026-10-19）：full 档也重叠 + 单分片内层线程按核数

> 重审（2026-10-18）：动态队列 + 常驻集收敛 + 分片上限 16

> 重审（2026-10-18）：重叠范围收窄到 quick

> 重审（2026-10-18）：quick 档测试与静态 check 重叠执行

> 重审（2026-10-18）：asset_read 第五轮：按 TDQS 50-100 词上限压到 100，保留 5 段与输出/参数/限制

> 重审（2026-10-18）：P2：分片数按核数自适应

> 重审（2026-10-18）：P3：分层档位 + 判定缓存 + 受影响测试选择

> 重审（2026-10-18）：P2：check12 分片并行（verify_tests 执行器 + 权重基线）

> 重审（2026-10-17）：步骤5：在场/关键词组收敛到 _decl_check（等价性 15 例逐字节一致）

> 重审（2026-10-17）：步骤4：新增 check41/42（构建隔离 + 不可伪造 provenance）与对应判据模块

> 重审（2026-10-17）：拆聚合门：check32/33/35/36 失败逐条透出（只动 bash 呈现层）

> 重审（2026-10-17）：门禁提速收口：check39 剪枝定为 target/obj（刻意不剪 bin——实测零收益且可能承载入库脚本）；check39 7.15s→4.06s，差分 6/6

> 重审（2026-10-17）：门禁提速：check39 遍历再剪构建产物目录（target/bin/obj）——engine/rust/target 一处 22454 目录（gitignore），只含产物不含源；实测目录 24712→1949、遍历 4.36s→0.28s（15.5×），判定逐项等价（禁名命中与 desktop/src/ui 在场性一致），差分 6/6 通过；nf verify 冷跑 17.8s→16.3s

> 重审（2026-10-16）：门禁提速（收口）：修 check30 批量化引入的两处路径归一缺陷（git quotepath 非ASCII转义 + Windows glob 反斜杠）——被 test_check30_bump 当场抓出；另打破 gate_engine↔subcheck_cache 模块环（依赖倒置，只回稳定字段字典），并补两处静默兜底理由

> 重审（2026-10-16）：门禁提速：check30 的 127 次 git diff 合并为一次全量调用后按块取（实测 2.016s→0.196s，42 件逐字节等价）；连同 check39 遍历优化，22 条已迁入合计 30.6s→19.1s、nf verify 冷跑 28.7s→17.8s

> 重审（2026-10-16）：门禁提速：check39 遍历由 os.walk 换单遍 os.scandir（同层剪枝 + follow_symlinks=False，省掉每条目一次 lstat 与整棵被排除子树）；实测 10.34s→6.70s，结果集逐字段一致（24712 目录/7221 py），差分 6/6 通过

> 重审（2026-10-16）：L-D 并行结论：默认保持串行（并行结论不稳定：共享守护单例 + 派生面可写），verify_parallel.py 保留为开发侧工具；verify.sh 字节已变，重绑 digest

> 重审（2026-10-16）：L-D 并行收尾：check12 默认按核数并行（上限 16）+ 守护卫生；相关派生面重冻后重绑

> 重审（2026-10-16）：L-D 并行接线：check12 改走 scripts/verify_parallel.py（模块级并行，8 路实测 1255→409 s）+ 守护卫生（只收本次拉起的）；verify.sh 字节已变，重绑 digest


> 重审（2026-10-14 · 核心文档改名/路径迁移）：被审对象随本波改名或引用替换而变，subjects 依「重审并更新 digest」机械重绑；本轮不主张新的语义审计。

> 重审（2026-10-13 · 核心语义通用化）：被审对象 verify.sh 随本波改动（check4/check5 判据键集由「认知/白描」泛化为「可见性/profile」），subjects 依「重审并更新 digest」处置；本轮为**机械重绑**，不主张新的语义审计，既有结论不变。

> 重审（2026-10-13 · 投稿面整体架构对齐）：被审对象随本轮改动（issue 模板 / INDEX 须知 / intake.json submission 段 / verify.sh check34 接线）而变，subjects 依「重审并更新 digest」处置。本次为**机械重绑**（同 §15 约定）——本轮不主张新的语义审计，只把既有结论重新绑定到新对象。

> 重审（2026-10-11 · §15 审计修复波）：被审对象随修复波改动，subjects 依「重审并更新 digest」处置。本次为**机械重绑**（作者裁定 A）：修复波本身带判据与全量测试证据（doctor 17/17、四棘轮与基线相等、分块全量测试除本项外全绿），非新的语义审计。

> 签收位：本件**未填 `accepted_by`/`accepted_at`**——验收签收属作者动作，执行者不自签。
> subjects = 5 件（域包工厂、检索反向引用、其回归测试、门禁脚本、公开文档）；
> **不含派生物**——`protocol/standards_catalog.json`（探针脚本产出）与
> `protocol/standards_binding.json`（工厂产出）、100 包的 `DOMAIN_SPEC.json` 与
> `domain_packs.json` 名录均为可复算投影。

## 一、内部差距（开工依据）

1. 目录只有 **126 条**、65 家机构，覆盖偏窄：**工业/能源/交通协议**、**出版与文档形态族**、
   **治理细则（NIST 800 系列 / PCI / HIPAA / 巴塞尔 / FATF / ISSB）**、**工程出品面
   （SLSA / in-toto / Sigstore / CT / CSAF / SSVC / 建模标准族）**几乎空缺。
2. 每条细分**只绑一条标准**：一条标准要同时承担「这条细分依据什么口径」与「这条细分的产出靠什么承载」
   两种职责，二者混在一处，谁也证不清。
3. 「数据真实性」当时只有一句话断言（在册 + 可达），**没有复合口径、没有逐包复算数值、没有门槛**。
4. 概念图的标准分支是**星形**（概念 → 标准），标准之间的**真实依赖关系**（如 OpenAPI → JSON Schema、
   C2PA → CBOR）完全没进图。

## 二、标准目录扩面（126 → 370 条）+ 依赖边

| 指标 | 上一波 | 本波 |
|---|---|---|
| 标准条数 | 126 | **370**（新增 244） |
| 发布机构 | 65 | **194** |
| 本机可达 200 | 115 | **330** |
| 规范依赖边 `depends_on` | 0 | **206** |
| 层分布 | data 38 / gov 38 / iface 29 / form 13 / eng 8 | data 148 / iface 84 / gov 71 / eng 38 / form 29 |

新增面覆盖：数据格式族（ORC / Iceberg / Delta / HDF5 / NetCDF / Zarr / FITS / LAS / CityGML /
GeoJSON / JPEG XL / AVIF / HEIF / OpenEXR / USD / IFC / GTFS / NeTEx / STIX-TAXII…）；
接口族（OAuth2 / OIDC / SAML / SCIM / WebAuthn / GNAP / QUIC / TLS 1.3 / HTTP 语义与缓存 /
MQTT5 / AMQP / Kafka / Matrix / ActivityPub / OPC UA / Modbus / BACnet / OCPP / SunSpec /
Redfish / SPIFFE / Matter / ROS 2 / MAVLink…）；形态族（Vega / AsciiDoc / reST / OPC-OOXML /
OMML / ODF / WAI-ARIA / ATAG / ITS / WebVTT / TTML / SSML…）；治理族（NIST 800-53·CSF·800-63·800-207 /
OSCAL / FedRAMP / PCI DSS / HIPAA / 巴塞尔 III / FATF / IFRS / ISSB / GHG / CIS / ASVS / SOC 2 /
EN 301 549 / Section 508 / EAA…）；工程族（SemVer / Conventional Commits / TAP / JUnit XML /
可重现构建 / SLSA / in-toto / Sigstore / **证书透明 v2（RFC 9162）** / SCITT / OpenVEX / CSAF /
SSVC / OpenChain / REUSE / OPA·CUE / BPMN·DMN·UML·SysML / ArchiMate·TOGAF / FinOps / SCI…）。

**不可达如实记（40 条）**：bot 防护 403（iso.org / loc.gov / hhs.gov / fatt / coe / ebu /
sunspec / modbus…）、反爬 202（eur-lex / hl7.org / editeur）、本机出口不通（autosar / cipa SSL）、
付费墙与登录 401（pubs.opengroup）——**不假装可达**，且绑定时**可达优先**。

## 三、双锚绑定（1200 → 2400 条）

- **主锚**（`standard`）：该细分依据的域口径标准（关键词 → 域码专属 → 段默认轮换 → 多样性补位），
  新增**可达优先**：同一命中位有本机实测可达的候选即先取可达者。
- **辅锚**（`support_standard`）：该细分**产出的承载标准**（契约 / 数据表 / 图表 / 图示 / 溯源 /
  时间 / 单位 / 数值 / 遥测 / 凭证 / 清单 / 文本 / 许可 / 身份 / 接口 / 事件），按产出形态关键词选择，
  **优先与主锚异层**；辅锚覆盖率 **100%**。
- 绑定行逐条落 `layer / body / url / reachable / probe_date`——**实测证据跟着绑定走**，
  绑定表本身即可复核真实性。

**口径修正（本波顺手修的两处语义偏差）**：D 段默认锚 `iso-iec-25010`（ISO 软件质量模型，
iso.org 403 不可达）→ **Common Criteria（ISO 15408，可扩展保护轮廓，本机可达）**；
制造类关键词锚 `iso-iec-25010` → **OPC UA**（工业互联，本机可达）。两处同时提升**可达性**与**语义贴合度**
（软件质量模型本不是工业制造的首选口径锚）。

## 四、概念图纵深（密度门槛 1.0 → 1.25）

标准分支由「概念 → 主锚」单边扩为**三类边**：概念 → 主锚、概念 → 辅锚、**标准 → 标准（依赖）**；
依赖边端点（被依赖标准）一并入图，保证「有边必有端点」。实测 100 包：

| 指标 | 上一波 | 本波 |
|---|---|---|
| 节点/包 | 15–20 | **21–34** |
| 边/包 | 21–24 | **38–60** |
| 标准依赖边/包 | 0 | **3–12** |
| 最小密度 | 1.0476 | **1.2647**（均值 1.8566） |

## 五、数据真实性（逐包可复算的复合分）

```
data_authenticity = 在册率 × (0.5 + 0.5 × 本机实测可达率) × 证据齐备率
```

乘法口径，**任一环缺即降分**（不用加权和掩盖缺口）。三要素 + 细分锚已探率逐包复算并落
`DOMAIN_SPEC.json` 的 `data_authenticity` 块与名录；实测 100/100 包：
在册率 1.0 · 可达率 1.0 · 证据齐备 1.0 · 细分锚已探率 1.0 → **真实性分 1.0000**（门槛 0.95）。

check32 `domain_packs` 子扫描由四判据扩到**七判据**：覆盖率 100% / 引用在册 / 每包 ≥3 条不同标准 /
密度 ≥1.25 / **辅锚覆盖率 = 1.0** / **标准依赖边 ≥1** / **真实性 ≥0.95 且可达率 ≥0.9**。
绑定表逐行还须带**在册证明与实测记录**（缺任一即 FAIL）。

## 六、本波修掉的两处门禁根因

1. **`check16-B` 的过强假设**：原判据要求「每个被 `asset_readonly` 白名单引用的源包必须有
   `assets/*.md`」，对**声明 0 自有资产的借阅型包**（`校园西幻轻混组合包`，只有 modules/pipelines）
   直接判 FAIL——这是**判据错**（该包 `protocol.yaml` 明写 `assets.count: 0`）。改为：
   查到 `count: 0` 判「不虚标可寻址」（并断言 `asset_get` 返回 None），缺声明才判违约。
2. **`referenced_by` 的跨类别误命中（真缺陷）**：反向引用查询对**类别限定 id** 只按裸号尾部匹配，
   于是查 `AI保险:M01` 会返回 `数据采集与清洗:M01` / `法律与合规:M01` 的引用方——
   组合包产物化后类别限定 id 变多，这个缺陷才被硬编码期望的过期暴露出来。改为**类别感知匹配**
   （查询带类别 → 命中同类别或裸号声明，异类别同号不命中；查询裸号 → 保留裸号检索便利），
   并把测试期望改为「按声明侧类别感知复算」+ 加跨类别回归断言（不再写死 `== []`）。

## 七、边界（不宣称）

- **标准对齐 ≠ 遵从认证**：目录与绑定只声明「与该标准对齐、且该标准本机实测可达」，
  不声明合规、认证或采用；外部标准只作口径与机制参照（STRATEGY §3.2/§3.3）。
- 不可达标准**不当唯一锚**：可达优先 + 辅锚兜底，保证每条细分至少有一条本机实测可达的锚。
- 密度是**图结构指标**，不衡量内容质量；密度达标不等于口径正确。
- 12 条细分内容仍来自内部域规格档（作者侧输入），公开面只呈现结果与判据。
