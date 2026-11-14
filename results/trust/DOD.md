# Trust Fabric DoD（验收收口报告）

> 状态：G4 收口件（2026-11-14）。本报告逐条给出**证据指针**与**不满足项**；不把环境受限项写成通过。
> 机器可读自审计：`results/trust/SELF_AUDIT.json`；可复跑门禁：`bash verify.sh --checks-only`（本版 46 条 check / PASS=83）。

## 1. 阶段验收矩阵

| 阶段 | 状态 | 证据 |
|---|---|---|
| G0 冻结（schema/威胁模型/向量/ADR） | ✅ | `protocol/trust/*.schema.json`（13 件）、`docs/trust/THREAT_MODEL.md`、`results/trust/trust_vectors.json`、`protocol/adr/registry.json` |
| G1 证据内核（A1+A2） | ✅ | `trust/bundle.py`、`trust/process.py`、check45、`test_trust_bundle.py`/`test_trust_process.py`、`SELF_AUDIT` G1 收口 |
| G2 签名/密钥/锚（A3） | ✅ | `trust/dsse.py`、`trust/keys.py`、`trust/anchor.py`、`trust/signature.py`、check46、`test_trust_signature.py`（真 TSA 端到端 T2） |
| G3 类型/模型/血缘/复核（A4） | ✅ | `trust/entity.py` + `type-registry`、`trust/model_card.py`、`trust/context_lineage.py`、`trust/human_review.py`；check47/SELF_AUDIT |
| G4 见证与跨语言（B4） | ⚠️ 部分 | T3 见证组合 ✅（WITNESS_SPEC、check47、`test_trust_t3.py` 真 TSA 到 T3）；parity **PARTIAL**（Python↔Node.js 六族 29 条；**ENV-01** 无 .NET SDK）；T4 公共锚 **不声称**（ENV-02） |

## 2. Claim 矩阵汇总

- `UNSUPPORTED` = 0；`TODO` = 0；
- `SUPPORTED` = #13/#15/#16/#18/#19/#32/#33/#34/#35（共 9 条新增收口项）；
- `PARTIAL` = #21（Python↔Node.js parity 已建；.NET 引擎线因 **ENV-01** 未完成）。

## 3. 门禁与证据

| 证明面 | 结果 |
|---|---|
| 静态全量门禁 | `bash verify.sh --checks-only` PASS=83 WARN=2 FAIL=0（46 条 check，check45-48 为 trust 面） |
| 一致性报告 | `nf conformance` verdict=conformant（27/27），approve + receipts 已重签 |
| 新鲜度 / precheck / style | 4/4；23/23 全绿；style 棘轮 9916（无新增） |
| 自审计 | P0=0；open P1=1（#21 PARTIAL，owner=Monyeah777，ENV-01）；UNSUPPORTED=0 |
| 跨语言复算 | Node.js 独立实现（`scripts/trust_parity/verify.mjs`）六族 29 条向量逐字节一致；entity 族显式 skipped 不冒充 |

## 4. 环境阻塞（不得写成通过）

- **ENV-01 无 .NET SDK**：`dotnet --list-sdks` 为空（仅 runtime 6/8）→ Python↔.NET engine-line parity 无法完成；claim #21 保持 PARTIAL。
- **ENV-02 公共锚不可离线验证**：Sigstore/Rekor/公共 TSA 需外部公共基础设施与联网，且本仓纪律封存外部实测 → T4 只报缺项（`PUBLIC-ANCHOR-MISSING`），**不声称 T4**。
- 本仓不运营公共 witness 网络：T3 的 STH/witness 是本仓冻结语句（`WITNESS_SPEC.md`），外部 witness 需按此签名才可互验。

## 5. 残余 OPEN（不在本轮声称范围）

- 自动锚定编排、trust store 多根/类型权限合一、keygen 与 0600 强制；
- 外部 witness 网络与公共锚接入（需外部基础设施）；
- 全量 `bash verify.sh`（3100+ 测试）未跑：本报告口径为「静态面全量 + 受影响面全量 + 仓库原生新鲜度命令」三件套；CI full 档才是发布结论。

## 6. 复现

```bash
bash verify.sh --checks-only                  # 46 条静态 check（含 trust 4 条）
python -m pytest desktop/tests/test_trust_*.py -q
python scripts/trust_self_audit.py --check    # 自审计机器件与重算一致
node scripts/trust_parity/verify.mjs --vectors results/trust/trust_vectors.json
```

## 7. 结论

Trust Fabric 的 G0–G3 全部收口、G4 的 T3 见证组合收口；**跨语言 .NET parity 与公共锚两项受外部环境限制未完成**。因此本报告**不声称「全部完成」**，而是给出可复核的完成面与两项 ENV 阻塞，供维护者决定是否安装 SDK / 接受 T4 出界。
