# NF 一致性声明（CONFORMANCE）
> ⛔ 操作指令：本文件是**机检声明**——三段（声明 / 范围 / 排除）由 `nf conformance --declaration` 逐条断言；改数字改不动门禁（版本一律与真源比对）。
> 最后更新：2026-11-14（复核）

> 性质：这是 NF 对「符合什么、管到哪、什么不管」的**显式声明**（机制借鉴 ACP 的 `CONFORMANCE.md`：
> 声明 + scope 白名单 + **显式排除清单**）。它不替代 `nf conformance` 的**报告**，两者互补——
> 报告说"跑过一遍的结论"，本声明说"范围与版本边界"。
>
> **复核（2026-11-14）**：三段（声明 / 范围 / 排除）与规范化摘要口径**复核不变**；本轮补「§现状对照」「§复现与引用口径」——把「三段各多少条、硬约束是什么、哪些数字不许钉」写清。
> 本文三段由 `nf conformance` 的 **declaration** 子检查逐条断言（版本与真源比对、scope 逐路径存在、scope∩排除=∅）；改数字改不动门禁，正解是改真源或改 scope/排除清单。

## 声明

| 规范 | 版本 | 真源 |
|---|---|---|
| protocol.yaml schema | `2` | 01 §6.1 / 各包 `protocol.yaml` |
| registry schema | `2` | 02 头部 + `desktop/src/core/registry.json` |
| machine_contract schema | `1` | `protocol/schema/contract.schema.json` |
| IDL schema 集 | `9 件` | `protocol/schema/` |
| 基线 | `v2.30 · check1-42 · PASS=76` | `verify.sh` + `quality_baseline.EXPECTED_*` |
| 档位 | `quick`（默认：静态 + 受影响测试）· `--full`（发布结论：全量测试） | `verify.sh` 参数；`nf release` 与 CI 固定 `--full --no-cache` |

## 范围

（scope 白名单：以下路径在声明范围内，必须存在且受门禁约束）

- `01_核心协议.md`
- `02_联动注册表.md`
- `06_Agent执行协议.md`
- `07_官方核心出厂与社区预设导航.md`
- `STRATEGY.md`
- `llms.txt`
- `protocol`
- `03_管线库`
- `04_模块库`
- `05_资产库`
- `community`
- `library`
- `patterns`
- `desktop/src`
- `desktop/tests`
- `scripts`
- `skills`
- `integrations`
- `changes`

## 排除

> 「允许不存在」标注的条目为运行期/本地件（可不在库内，缺省不算缺口）；其余条目路径须真实存在。

| 路径 | 理由 |
|---|---|
| `.rivet` | 本地 AI 协作工作区（运行时状态与内部档案，不入库；**允许不存在**——运行期/本地件，fresh clone 无此目录属预期） |
| `results` | 审计与外部实测记录（历史时点事实，不随现状更新） |
| `docs/41_*` | 波 C 逐波实测记录（历史） |
| `docs/42_*` | 42 质量纵深工程记录（历史） |
| `docs/44_*` | 44 波记录（历史） |
| `docs/45_*` | 45 波记录（历史） |
| `docs/external-validation-assets` | 外部验证素材副本（外部产物，非 NF 规范件） |
| `CHANGELOG.md` | 版本功能史（历史散文段不入范围） |
| `docs/L3_FROZEN.md` | 端壳退役记录（冻结史，不再演进） |
| `.github` | 平台配置与投稿模板（平台面，非协议件） |
| `docs/paste_card.md` | 归档件（B2 通道免除后冻结，不再维护） |

## 规范化摘要口径

> 本段是**算法声明**，不是新机制：把回执 / 锚 / 一致性报告 / 模组契约摘要共用的规范化摘要口径写明——
> 此前该口径只存在于实现里（`receipts.py` / `attest.py` / `mvu_adapter.py` / `knowledge_sig.py`），
> **仓外读者侧验证器**（`scripts/nf_verify.py` 形态：纯标准库、零 NF 依赖）无从逐字复现。

**摘要口径**：`SHA-256`（十六进制小写）；输入 = UTF-8 编码的规范 JSON——键按字典序排序（`sort_keys`）、
非 ASCII 不转义（`ensure_ascii=False`）、无多余空白（分隔符 `,` 与 `:`）。

**Merkle（RFC 6962 风格）**：叶 = `SHA-256(0x00 ‖ 载荷)`；节点 = `SHA-256(0x01 ‖ 左 ‖ 右)`；空集 → 无根；单叶 → 该叶。域分隔字节 `0x00` / `0x01` 是防「叶与节点」跨型碰撞的结构手段。

**与 RFC 8785（JSON Canonicalization Scheme）的关系**：本口径**不是** JCS 实现，差异可判定——① 数值序列化：JCS 采用 ECMAScript 数值字面量规则，本仓沿用实现语言的 JSON 序列化；② 键排序：JCS 按 UTF-16 码元排序，本仓按码位排序（非 BMP 字符处可能不同）；③ 转义集规则另有规定。**故本仓摘要只声明「仓内可复现 + 读者侧可按本段复现」，不声明 JCS 兼容**；将来若需对外互操作（L3 导出面），须先做 JCS 对齐评估再改本声明，不得默认两者相等。

## 现状对照（2026-11-14 · 以 declaration 子检查实读为准）

| 面 | 当前口径 | 复核方式 |
|---|---|---|
| 声明行 | **5** 个版本面（protocol.yaml / registry / machine_contract / IDL 集 / 基线） | `nf conformance --json` 的 declaration detail |
| 范围 | **19** 条 scope 白名单（逐条必须**真实存在**） | 同上 |
| 排除 | **11** 条显式排除（每条带理由；`.rivet` 标「允许不存在」） | 同上 |
| 硬约束 | **scope ∩ 排除 = ∅**（不许既在范围又排除） | `conformance_decl.scan` 的断言 |
| 与报告的关系 | 本文**不替代**报告：报告说「跑过一遍的结论」，本文说「范围与版本边界」 | `docs/conformance.md` + 本页 |
| 失败即冻结链阻断 | declaration 失败 → `nf conformance --write` 出 non-conformant → `approve` 拒批 → `receipts` 不推进 | `core/release_gate.DEFAULT_FREEZE_CHAIN` |

**不钉运行时数字**：上表 5/19/11 是**当次实读**（`nf conformance --json`）；条数变化属正常演进，正文不把它们当承诺。版本表里的「基线 · `v2.30 · check1-42 · PASS=76`」是**真源比对项**（与 `quality_baseline.EXPECTED_*` 比对），可以钉、也必须钉。

## 复现与引用口径

```bash
python scripts/nf.py conformance --json        # 含 declaration 子检查：版本 / scope / 排除 / 交集断言
python -c "import sys;sys.path.insert(0,'desktop/src');from core import conformance_decl as cd;print(cd.scan('.'))"
```

- 引用本页时：「符合什么 / 管到哪 / 什么不管」= 三段；「跑过一遍的结论」请引报告（`protocol/conformance_report.json`），别引本文。
- 新增 scope 路径：先确认真实存在、且不在排除清单里；改完跑 `nf conformance`（declaration 必须绿）。
