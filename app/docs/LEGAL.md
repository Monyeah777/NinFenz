# NF APP 法务登记（许可 / NOTICE / 模板版权 / AI 条款 / 出口评估）

> ⛔ 操作指令：本件是**工程登记**，不是法律意见，也不构成合规声明。每条口径要么能指到仓库文件/命令，要么写 `OPEN` + owner + 下一步。**不得**把「待人工/律师判定」写成「已合规 / 已定性」。改本件必须同步 `app/docs/DEPENDENCIES.md`（依赖许可）与 `app/scripts/RELEASE_CHECKLIST.md`（发布材料）。
> 状态：v1（2026-11-15）· 性质：法务面工程登记 · 取证时刻：2026-11-15 16:0x · 本机实测：`head -5 LICENSE`、`ls LICENSES`、`grep -n license app/core/Cargo.toml`、本机 cargo 缓存 Cargo.toml 的 license 字段（见 `app/docs/DEPENDENCIES.md`）。
> 依据：`LICENSE`（实读）、`REUSE.toml`、`LICENSES/`、`THIRD-PARTY-NOTICES.md`、`docs/legal/EXPORT.md`、`docs/legal/TRADEMARK.md`、`docs/legal/VENDORS.md`、`app/docs/CONTRACT.md` §6。

## 1. 本仓许可（先实读，不照抄假设）

**实读结论：MIT License，Copyright (c) 2026 Monyeah777。** 判据命令：`head -5 LICENSE`（全文 21 行，标准 MIT 文本，无附加条款）。

| 项 | 实读 | 判据 |
|---|---|---|
| 许可 | MIT | `LICENSE` 第 1–21 行 |
| 版权行 | 2026 Monyeah777 | `LICENSE` 第 3 行 |
| 仓级 SPDX 声明 | 聚合声明 = MIT；投稿面 override = `LicenseRef-Community-Submission` | `REUSE.toml` 顶部注解 |
| 许可文本落点 | `LICENSES/MIT.txt`、`LICENSES/LicenseRef-Community-Submission.txt` | `ls LICENSES` |
| 引用元数据 | `CITATION.cff`；`pyproject.toml` 的 `license = { file = "LICENSE" }` | 实读 |
| APP 核心 crate 许可 | `license = "MIT"` | `app/core/Cargo.toml` |

### 1.1 偏差登记（DEV-LEGAL-001）

- **输入假设**：任务输入转述的内部计划按 **AGPL** 假设讨论许可。
- **仓库实读**：`LICENSE` 为 **MIT**（无 copyleft 条款）。
- **处置**：以实读为准；APP 交付按 MIT 口径（保留版权与许可声明、允许再分发/修改、无源码开放义务）。
- **影响**：（a）不存在 AGPL 的网络使用/源码开放义务；（b）MIT 下仍必须随附第三方组件许可与版权声明（§2）；（c）若作者未来决定改为 AGPL，属**作者决策**，需全量依赖许可兼容性复核 + 本件重写，不由实施 agent 自行改许可。
- **owner**：lead；**状态**：登记完成（以实读为准）。

### 1.2 分层许可（2026-11-28 作者决策，随 0.3.7-preview.1 生效）

- **协议 / 引擎 / 仓库其它面：MIT**（根 `LICENSE` / `LICENSES/MIT.txt`，上表实读不变）。
- **Android 应用（`app/android/**`）：PolyForm Noncommercial 1.0.0**（文本 `LICENSES/PolyForm-Noncommercial-1.0.0.txt`；REUSE override 见 `REUSE.toml`）。个人非商业使用免费；商业使用/商业再分发需书面授权（走仓库 `[cooperation]` issue）。
- **为什么分层**：协议与引擎保持 MIT 以维持「模型无关、可被任何 AI 装载」的生态位；应用端（分发物与未来 Pro 买断）单独按 NC 授权，给商业盗用/二次售卖留下法务抓手，同时不改动 npm/crates/NuGet 等平台的 OSI 发布口径。
- **边界**：MIT 不可撤销，已发布旧版本不受影响；本决策自 0.3.7-preview.1 起生效。Pro 激活校验代码与公钥随 App 源码可见（许可 + 离线验签），**签发私钥永不入仓**（作者本机离线保存）；盗版防线 = 许可 + 离线授权 + R8/拆分包，接受个人分流，不宣称技术不可破解。
- **判据**：`desktop/tests/test_license_chain.py`（根 MIT 链）、`test_reuse_contract.py`（override 与 LICENSES 双向闭合）、`test_governance_docs.py`（LICENSES 存在性）。

## 2. 第三方许可与 NOTICE 口径

### 2.1 现状

| 面 | 依赖 | 许可 | 声明落点 | 状态 |
|---|---|---|---|---|
| 仓库门禁/开发工具链（Python） | 固定集 `.github/requirements-*.txt` | 见清单（MIT/Apache-2.0/BSD/PSF/MPL 等） | `THIRD-PARTY-NOTICES.md`（由 `scripts/gen_third_party_notices.py` 生成，勿手改） | 在场（既有） |
| APP 共享核心（Rust） | `app/core/Cargo.lock` 40 个依赖包 | 全部宽松：MIT / Apache-2.0 / MIT OR Apache-2.0 / BSD / Zlib / Unlicense / Unicode-3.0；**无 GPL/AGPL** | `app/docs/DEPENDENCIES.md`（逐包表，本机 cargo 缓存元数据实读） | partial（表已在；发布物内 NOTICE 未生成） |
| APP 控制面（Python） | 运行依赖 `jsonschema`（等） | MIT（见 `THIRD-PARTY-NOTICES.md` 既有条目） | `DEPENDENCIES.md` 的 Python 节 | partial |
| 端壳（Android/Desktop） | 未构建 | 未定 | 无（端壳依赖清单待出） | OPEN-TOOLCHAIN |

### 2.2 NOTICE 义务（发布物必须随附）

- MIT：保留版权声明与许可文本（`LICENSES/MIT.txt`）。
- Apache-2.0：保留 NOTICE（若有）与许可文本；标注修改（本仓未修改上游源码，Local Modifications: None）。
- 本仓当前 `THIRD-PARTY-NOTICES.md` 的范围是 **Python 门禁工具链**，**不含 Rust crates**（实读：无 cargo/rust 条目）→ 发布 APK/MSIX/dmg 前必须补一份 APP 侧 NOTICE（含 Rust + Python + 端壳）。
- 建议形态：发布物内置 `licenses/`（或应用内可访问的第三方声明页）+ 仓库内 `app/THIRD-PARTY-NOTICES.md`（**待生成**；生成后为生成物，勿手改）；生成工具建议 `cargo-about`/`cargo-license`（本机未安装 → OPEN-LEGAL-01）。

### 2.3 口径纪律

- 新增依赖必须先出现在 `Cargo.lock`/依赖清单，再过许可检查；**不接受**只在构建脚本里临时安装。
- 禁止引入 GPL/AGPL/SSPL 等与 MIT 分发口径冲突的强 copyleft 依赖（除非作者显式决策并全仓评审）。
- 依赖许可以「实际解析到的版本」为准（`Cargo.lock` + 本机 registry 元数据），不以文档记忆为准。

## 3. 模板 / Pack 内容版权提示

- **真源归属**：模板/协议/规范内容来自仓库真源（MIT，版权 2026 Monyeah777）；APP 只按 `{id, version, digest}` 引用，不取得内容版权（`app/docs/CONTRACT.md` §1/§9）。
- **模板包**：`nf-template/1` 内嵌 protocol/spec 快照 + hashes；随模板分发时必须保留归属声明与许可文本；不得移除或改写版权行（对照 `docs/legal/TRADEMARK.md` 使用规则）。
- **用户作者内容**：用户导入/作者态内容版权归用户（或原权利人）；模板/APP 不主张对用户内容的版权，也不因使用模板而取得用户内容权利。
- **社区投稿内容**：按 `LICENSES/LicenseRef-Community-Submission.txt` 再分发（投稿面 override，见 `REUSE.toml`）；APP 若导入社区包，须展示其许可与归属。**当前未实现**（无社区包导入 UI）→ OPEN-LEGAL-02。
- **出处与责任**：用户须保证导入素材有权使用；APP 不做版权审查，也不为用户的输入背书。

## 4. AI 软件条款提示

- **APP 不内嵌模型、不调模型 API、不训练模型**：AI 执行发生在 CCOS（外部执行面），APP 只产出 `ccos-task/1` 并接收 `ccos-result/1`（ADR-APP-001）。
- **输出为草稿**：`human_review.required` 恒 true；APP 不保证 AI 输出的准确性、合法性、无侵权或可商用性。
- **不主张输出权利**：APP/CCOS 不对 AI 输出主张额外版权；输出能否受版权保护、能否商用，依适用法域与所用模型条款判定，由用户/发布方确认。
- **模型条款不在本仓**：CCOS 侧使用的模型/服务条款由其自身声明；APP 文档不代述、不作担保。
- **变更触发**：若未来引入端上模型、在线推理或任何出站能力，必须同步更新 `app/docs/LEGAL.md` + `PRIVACY.md` + `THREAT_MODEL.md`（新信任边界），并处理模型许可/输出条款。

## 5. 出口评估（工程登记，不作定性）

与 `docs/legal/EXPORT.md` 衔接。APP 侧的密码学/双用途面：

| 组件 | 用途 | 形态 | 评估要点 |
|---|---|---|---|
| `sha2`（RustCrypto，经 `app/core/Cargo.lock` 钉死） | SHA-256 完整性摘要（canonical/pack digest） | 哈希函数，非加密/非密钥交换 | 通用完整性摘要，通常不构成受控加密物项 |
| `zip`/`flate2`/`zopfli` | zip 打包/压缩 | 压缩（非加密） | 不提供机密性；无密码学用途 |
| 分享/导出 | 产物外发 | 文件/zip | 不含加密；无网络传输层 |
| CCOS 交接 | 任务/结果文件 | 文件/zip | 无 TLS/无网络；机密性依赖用户选择的传输通道（APP 不提供） |

- **立场**：APP 不实现加密、不做密钥交换、不提供网络传输层；仅做完整性摘要与压缩。按公开可得/大众市场软件的一般口径，通常不构成受控加密物项。
- **但**：是否受控、是否需要许可/申报，由人工/律师按适用司法辖区判定 → `OPEN-LEGAL-03`（owner lead）。本件不作定性。
- **触发评审**（沿用 `docs/legal/EXPORT.md`）：新增密码算法/密钥交换/加密库；对外分发含签名/加密能力的构建物；引入外部 TSA/CA/透明日志；目标辖区有额外出口/制裁要求。

## 6. 供应商与数据处理

- APP 无服务器、无账号、无第三方分析/崩溃 SDK → 不处理他方个人数据，不签 DPA（对照 `docs/legal/VENDORS.md` 口径）。
- CCOS 若由第三方运营，属**用户与 CCOS 之间**的关系；APP 只做文件交接，不代签、不担保。
- 端壳依赖的第三方 SDK（若引入）必须进 `DEPENDENCIES.md` 并在发布前过许可与隐私审查（`PRIVACY.md` §3）。

## 7. 免责与边界（明确）

- **本文件不构成法律意见**：不得作为合规（GDPR/CCPA/COPPA/出口管制/内容分级）结论引用。
- 本文件不替代正式隐私政策与最终用户许可协议（EULA）；上架/分发前需由发布方在法务审核后单独出具。
- 本文件不评价仓库既有 `docs/legal/*` 的实体结论，只做 APP 面的衔接与登记。
- 许可/法律问题走作者（仓库 `README.md` 的联系口径）或 `SECURITY.md` 通道（若涉安全），不走公开 Issue 讨论未公开漏洞。

## 8. OPEN 登记

| id | 内容 | owner | 下一步 |
|---|---|---|---|
| OPEN-LEGAL-01 | APP 侧第三方 NOTICE 未生成（现 `THIRD-PARTY-NOTICES.md` 不含 Rust crates / 端壳依赖） | lead | 用 cargo-about/cargo-license（或等价脚本）生成 `app/THIRD-PARTY-NOTICES.md` 并随发布物分发 |
| OPEN-LEGAL-02 | 社区包导入的许可/归属展示未实现 | kotlin-ui | 端壳导入流程展示许可文本与归属；导入前校验包内 license 声明 |
| OPEN-LEGAL-03 | 出口/制裁定性未做（需人工/律师） | lead | 按 `docs/legal/EXPORT.md` 触发条件执行；结论回填本件 §5 |
| OPEN-LEGAL-04 | 正式隐私政策/EULA 未出具 | lead | 发布前由发布方法务审核出具，引用 `PRIVACY.md` 数据地图 |
| OPEN-TOOLCHAIN | 端壳依赖清单缺失（许可审查前置） | kotlin-ui | 端壳工程落地后出 Gradle 依赖清单进 `DEPENDENCIES.md` |

## 9. 判据命令（本件取证）

```bash
head -5 LICENSE                      # 期望：MIT License / Copyright (c) 2026 Monyeah777
ls LICENSES                          # 期望：MIT.txt / LicenseRef-Community-Submission.txt
grep -n license app/core/Cargo.toml  # 期望：license = "MIT"
grep -c "name = " app/core/Cargo.lock  # 依赖包计数（逐包许可见 app/docs/DEPENDENCIES.md）
grep -niE "gpl|agpl|sspl" app/docs/DEPENDENCIES.md  # 期望：仅出现在「禁止引入」口径行
```

