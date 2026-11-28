# 法务 / 许可 / IP / 出口（LEGAL）

> ⛔ 操作指令：本件是法务面的入口与摘要；机读真源 `protocol/legal.json`（`nf-legal/1`），审计入口 `python scripts/legal_audit.py`，判据 `desktop/tests/test_legal_contract.py`。**本件不构成法律意见**，签署/分发前须人工或律师复核。
> 状态：v1（G0 · 2026-11-14）· 依据：`NF-Final-方案-2026-11-13.md` §15A.2（P1 盲区 BL-07）

## 许可（以仓内文本为真源）

- 本仓许可：**MIT**（SPDX `MIT`；文本 `LICENSE` / `LICENSES/MIT.txt`）。
- **分层例外（2026-11-28）**：Android 应用（`app/android/**`）按 **PolyForm Noncommercial 1.0.0**（文本 `LICENSES/PolyForm-Noncommercial-1.0.0.txt`，REUSE override 见 `REUSE.toml`）：个人非商业使用免费，商业使用/商业再分发需书面授权；协议与引擎仍为 MIT。
- 投稿面（`library/NF-*.md`、`library/anchors/**`、`community/**`）：按 `LicenseRef-Community-Submission` 再分发（文本 `LICENSES/LicenseRef-Community-Submission.txt`，条款与 library 投稿须知同源）。
- REUSE 3.x 标注：`REUSE.toml`（聚合 MIT + 投稿面 override）；判据 `desktop/tests/test_reuse_contract.py`。
- **与方案的偏差（显式登记）**：方案 §15A.2 假设 AGPL-3.0-only/商业双许可；本仓实际为 MIT（更宽松）+ 投稿面 LicenseRef。**不虚构双许可或 AGPL 结论**，以仓内文本为准。

## 第三方与 NOTICE

- `THIRD-PARTY-NOTICES.md` 由 `scripts/gen_third_party_notices.py` 从 PyPI 官方元数据生成，**请勿手改**；对照面 `results/ccos/sbom.json`。
- 分发边界：所列组件是**门禁/开发工具链**依赖，不随产品分发；运行时核心零第三方（`pyproject.toml` `[project].dependencies=[]`、`packaging/npm/package.json` 无 `dependencies`，均机检）。
- 逐组件归属/许可见 NOTICE 清单；本仓未修改上游源码（Local Modifications: None）。

## 商标 / 署名

- 名称与标识（NinFenz / 宁封子）仅用于指代本仓来源；**不得暗示官方认证、背书或关联**。
- 二次分发须保留署名与 `LICENSE`/`NOTICE`；协议/引擎的商业使用按 MIT 条款，Android 应用商业使用按 PolyForm Noncommercial 1.0.0（需授权）。详见 `docs/legal/TRADEMARK.md`。

## 合同模板

- 服务 / 试点 / 保密（NDA） / 数据处理（DPA）四类模板大纲见 `docs/legal/CONTRACTS.md`；状态 `template-in-doc`（未签署，供人工复核后使用）。
- 本仓本地优先、不处理他方个人数据，因此**不签 DPA**；如客户要求，按模板逐条评审（见 `docs/legal/VENDORS.md`）。

## 出口 / 加密组件

- 加密组件清单（Ed25519/HMAC、RFC 3161、透明日志包含证明）与评审触发条件见 `docs/legal/EXPORT.md`，机读在 `protocol/legal.json` 的 `export` 段。
- 本清单只做工程登记，**不构成出口/制裁法律意见**。

## 复核命令

```bash
python scripts/legal_audit.py
python -m pytest desktop/tests/test_legal_contract.py -q
python -m pytest desktop/tests/test_reuse_contract.py -q
```
