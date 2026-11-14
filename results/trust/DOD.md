# Trust Fabric DoD（验收收口报告）

> 状态：G4 收口件（2026-11-14）。本报告逐条给出**证据指针**与**不满足项**；不把环境受限项写成通过。
> 机器可读自审计：`results/trust/SELF_AUDIT.json`；可复跑门禁：`bash verify.sh --checks-only`（本版 46 条 check / PASS=83）。

## 1. 阶段验收矩阵

| 阶段 | 状态 | 证据 |
|---|---|---|
| G0 冻结（schema/威胁模型/向量/ADR） | ✅ | `protocol/trust/*.schema.json`（14 件）、`docs/trust/THREAT_MODEL.md`、`results/trust/trust_vectors.json`、`protocol/adr/registry.json` |
| G1 证据内核（A1+A2） | ✅ | `trust/bundle.py`、`trust/process.py`、check45、`test_trust_bundle.py`/`test_trust_process.py`、`SELF_AUDIT` G1 收口 |
| G2 签名/密钥/锚（A3） | ✅ | `trust/dsse.py`、`trust/keys.py`、`trust/anchor.py`、`trust/signature.py`、check46、`test_trust_signature.py`（真 TSA 端到端 T2） |
| G3 类型/模型/血缘/复核（A4） | ✅ | `trust/entity.py` + `type-registry`、`trust/model_card.py`、`trust/context_lineage.py`、`trust/human_review.py`；check47/SELF_AUDIT |
| G4 见证与跨语言（B4） | ✅ | T3 见证组合 ✅（WITNESS_SPEC、check47、真 TSA 到 T3）；parity ✅（Python↔Node.js + Python↔.NET 双实现各六族 29 条逐字节一致）；T4 公共锚验证面 ✅（`nf-public-anchor/1`：inclusion+SET+目标绑定 + CLI 抓取；实际提交公共条目需维护者身份，属外部操作） |

## 2. Claim 矩阵汇总

- `UNSUPPORTED` = 0；`TODO` = 0；
- `SUPPORTED` = #13/#15/#16/#18/#19/#21/#32/#33/#34/#35/#36（全部收口项）；
- `PARTIAL` = 0（此前 #21 的 ENV-01 阻塞已由本机 SDK 安装 + C# parity 解除）。

## 3. 门禁与证据

| 证明面 | 结果 |
|---|---|
| 静态全量门禁 | `bash verify.sh --checks-only` PASS=83 WARN=2 FAIL=0（46 条 check，check45-48 为 trust 面） |
| 一致性报告 | `nf conformance` verdict=conformant（27/27），approve + receipts 已重签 |
| 新鲜度 / precheck / style | 4/4；23/23 全绿；style 棘轮 9916（无新增） |
| 自审计 | P0=0；open P1=1（#21 PARTIAL，owner=Monyeah777，ENV-01）；UNSUPPORTED=0 |
| 跨语言复算 | Node.js `scripts/trust_parity/verify.mjs` + .NET 8 C# `scripts/trust_parity/csharp/` 双实现各六族 29 条向量逐字节一致；entity 族显式 skipped 不冒充 |
| 公共锚 live | Sigstore Rekor 真实条目（logIndex 0 / tree 4163431 / 22 级 proof）离线验签通过：`results/trust/PUBLIC_ANCHOR_LIVE.*` + `test_trust_public_anchor_live.py` |

## 4. 环境阻塞（不得写成通过）

- **ENV-01（已解决，2026-11-14）**：本机安装 .NET SDK 8.0.4xx 到 `%USERPROFILE%\.dotnet`；`dotnet --list-sdks` 有 SDK，C# 独立实现跑六族 29 条向量 mismatches=0（claim #21 SUPPORTED）。
- **ENV-02（验证面已解决，2026-11-14）**：`trust/public_anchor.py` 可离线验 Rekor 风格条目（inclusion+SET+目标绑定），CLI 可显式联网 fetch；实际向公共日志提交本仓链头条目需维护者 Sigstore 身份（外部操作，未执行，不冒充已提交）。
- 本仓不运营公共 witness 网络：T3 的 STH/witness 是本仓冻结语句（`WITNESS_SPEC.md`），外部 witness 需按此签名才可互验。

## 5. 残余 OPEN（不在本轮声称范围）

- ~~自动锚定编排~~ 已完成（`trust/anchor.py::auto_anchor` + `trust_verify.py --auto-anchor`：先验链头再组装锚件；错头/空组件必拒）；
- ~~trust store 多根/类型权限合一~~ 已完成（`trust/trust_store.py`：policy×issuer registry×type registry 装配一致性 + lookup）；
- ~~keygen 与 0600 强制~~ 已完成（`trust/key_material.py` + `scripts/trust_keygen.py`：0600/拒绝覆盖/拒绝符号链接/POSIX 权限校验；Windows 语义如实告警）；
- 实际向公共透明日志提交本仓条目、运营外部 witness 网络（需维护者 Sigstore 身份/公共基础设施，属外部操作）；
- 全量 `bash verify.sh`（3100+ 测试）未跑：本报告口径为「静态面全量 + 受影响面全量 + 仓库原生新鲜度命令」三件套；CI full 档才是发布结论。

## 6. 复现

```bash
bash verify.sh --checks-only                  # 46 条静态 check（含 trust 4 条）
python -m pytest desktop/tests/test_trust_*.py -q
python scripts/trust_self_audit.py --check    # 自审计机器件与重算一致
node scripts/trust_parity/verify.mjs --vectors results/trust/trust_vectors.json
```

## 7. 结论

Trust Fabric 的 G0–G4 代码与验证面全部收口：G4 的 T3 见证组合、Python↔Node.js/.NET 双实现 parity、T4 公共锚验证面均已有代码锚点 + 测试 + 门禁。**实际向公共透明日志提交本仓条目**与**运营外部 witness 网络**属外部操作，不在本仓代码交付范围（需维护者 Sigstore 身份/公共基础设施），已在残余 OPEN 中显式登记；因此本报告**不声称「全部完成」**：准确口径是「代码与验证面完成；两项外部操作（公共日志提交、外部 witness 网络）未执行」，不把外部提交写成已完成。
