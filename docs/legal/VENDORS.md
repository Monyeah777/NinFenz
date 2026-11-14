# 供应商与第三方（VENDORS）

> ⛔ 操作指令：本件是供应商登记与退出计划的人读面；机读真源 `protocol/vendors.json`（`nf-vendors/1`），判据 `desktop/tests/test_ops_contract.py`（含 vendor-exit 就绪演练）。
> 状态：v1（G0 · 2026-11-14）· 依据：`NF-Final-方案-2026-11-13.md` §15A.5（D18）
> 纪律：本仓**本地优先、不处理他方个人数据**；不签 DPA（无数据委托处理）；第三方许可清单见 `THIRD-PARTY-NOTICES.md`。

## 供应商登记

| 编号 | 供应商 | 类别 | 关键度 | 消费点 | Attestation | 退出兜底 | 状态 |
|---|---|---|---|---|---|---|---|
| V-01 | 外部模型/Agent provider（用户自选） | model-provider | medium | `desktop/src/core/driver.py`、`agent_rules_adapter.py` | —（外部） | 切 mock/其它模型 adapter | optional |
| V-02 | RFC 3161 TSA（如 freeTSA） | tsa | medium | `desktop/src/core/timestamp.py` | `results/interop/sbom.json` | 本地 TSA 桩/离线 token 验证 | optional |
| V-03 | Sigstore/Rekor 公共日志 | transparency-log | medium | `desktop/src/core/trust/public_anchor.py` | `results/trust/PUBLIC_ANCHOR_LIVE.json` | 不声称 T4；离线验证已抓取条目 | optional |
| V-04 | GitHub（托管/CI/Advisory） | hosting | high | `.github/workflows/ci-verify.yml` | `results/interop/slsa.json` | 本地仓库 + 远端镜像 | active |
| V-05 | 包注册源（PyPI/npm/Cargo/NuGet） | package-registry | high | `requirements.txt`、`packaging/npm/package.json` | `results/interop/sbom.json`、`cyclonedx.json` | 固定版本 wheel/离线镜像 | active |
| V-06 | Cloudflare（站点部署，可选） | deploy | low | `wrangler.jsonc` | — | 本地/其它静态托管 | optional |

## 数据条款（摘要）

- 本仓不向第三方发送用户内容：模型调用由用户本地配置；TSA 只提交摘要级 token 请求；公共日志只读抓取；托管只承载公开仓库内容。
- 各供应商的 `data_terms.stores_user_data` 必须为 `false`（机检）；凭据由用户自持、不入仓（见 `PRIVACY.md` / `.gitignore`）。

## 退出与替换演练

- 每个 vendor 必须有：兜底方案（fallback）+ ≥2 步退出动作 + owner；`critical/high` 必须有 attestation（SBOM/来源/锚证据）——机检。
- 就绪演练（DR-04 / VD-01）：静态检查 used_by/attestation/退出计划可执行（`python scripts/ops_drill.py --check`）。
- **真实网络替换**（换 TSA/换日志/断供演练）属外部操作，标 UNOBSERVABLE，不冒充已演练。

## 复核命令

```bash
python scripts/ops_drill.py --check
python -m pytest desktop/tests/test_ops_contract.py -q
```
