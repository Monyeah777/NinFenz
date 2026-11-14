# 产品发现（PR/FAQ）

> ⛔ 操作指令：本件是 NF-Final §3A D01 产品发现的人读面（**假设性 PR/FAQ**）；机读真源 `protocol/product.json`（`nf-product/1`），GTM/支持见 `docs/product/GTM.md`，访谈计划 `docs/product/INTERVIEWS.md`，判据 `desktop/tests/test_product_contract.py`。**未做访谈/试点，全部假设 unverified**，不伪造结论。
> 状态：v1（G0 · 2026-11-14）· 依据：§3A D01/D14、§15A（P1 盲区 BL-06）
> 纪律：不以外部背书/热度作为质量论据（STRATEGY §3）；不写价格/SLA 承诺。

## 假设性新闻稿（Press Release，尚未验证）

> **NinFenz 让 AI 长内容交付可验证、可复现**——用开放协议把「需求→规范→任务→装配→验收」钉成工程，而不是靠某个模型的手感。
> 换模型、换执行者、断网复算，交付物与证据仍然自洽；外部审查者不需要相信任何一方，只需按文档复算。
> MIT 开源、本地优先、零运行时第三方依赖。

## 问题与 JTBD

| 编号 | 当…（when） | 我想要…（want） | 以便…（so） |
|---|---|---|---|
| J-01 | 要交付长内容却无法保证跨模型一致 | 用契约把交付物与验收钉住 | 换模型/换人不掉质量 |
| J-02 | 需要证明交付物不是凭空生成 | 有可独立复算的证据链 | 外部审查者能复核 |
| J-03 | 多人/多 Agent 并行生产 | 同一 spec 不同执行者产出可比较 | 协作不靠口头约定 |

## 机会解决树（Opportunity Solution Tree，假设）

- **期望结果（Outcome）**：外部审查者能在不理解实现的前提下独立复算一次交付。
  - 机会 1：契约与验收口径不统一 → 方案：nf-contract/nf-spec/nf-task/nf-assembly schema（WP-01）+ Spec Compiler（G1）
  - 机会 2：证据链不可离线复算 → 方案：claim bundle/锚/TSA 离线验证（已落地）+ 复算文档
  - 机会 3：上手成本高 → 方案：quickstart 五分钟路径 + `quickstart_check.sh` 实测
  - 机会 4：跨执行者不可比较 → 方案：Agent adapter parity（G2，OPEN-G2）

## 价值假设（全部 unverified）

| 编号 | 假设 | 指标 | 反指标 | 状态 |
|---|---|---|---|---|
| H-01 | 规范驱动显著降低跨模型交付漂移 | M-01 | CM-01 | unverified |
| H-02 | 离线可复算证据链是外部复核刚需 | M-02 | CM-02 | unverified |
| H-03 | 五分钟上手覆盖首次成功、不需培训 | M-03 | CM-03 | unverified |
| H-04 | 用户愿为「可验证交付」付可选服务费（不绑架开源核心） | M-04 | CM-02 | unverified |

## 成功指标与反指标

| 指标 | 定义 | 反指标 |
|---|---|---|
| M-01 同 spec 跨模型交付差异 | 同 spec 在 ≥2 adapter 下产物过同一契约校验的比例 | CM-01 过度约束扼杀多样性 |
| M-02 证据可独立复算率 | 外部复现者按文档一次复算成功比例 | CM-02 为转化夸大保证 |
| M-03 首次成功耗时 | 按 quickstart 完成一次 verify 复跑的耗时/卡点 | CM-03 为提速跳过校验 |
| M-04 可选服务转化（假设） | 试点转付费比例（当前无数据） | CM-02 |

## MVP 范围

- **做**：协议/契约、生产/装配核心（P00 链）、门禁与冻结链、离线证据与复算、五分钟上手。
- **不做**：托管 SaaS、团队协作 UI、自动发布第三方平台、模型训练。
- **成功判据**：G2 黄金路径 E2E 可复跑；外部审查者可独立复算；五分钟上手无阻断。

## 外部依赖与 OPEN

- **OPEN-PRODUCT**：3 次用户访谈 + 试点/LOI 属外部操作，未执行（见 `docs/product/INTERVIEWS.md`）。
- **OPEN-METRICS**：M-01/M-02/M-04 尚无实测数据（依赖 G2 parity 与外部试点）。
- 因此本件**不声称**「需求已验证/有用户/有市场」；只有假设与验证计划。

## 复核命令

```bash
python -m pytest desktop/tests/test_product_contract.py -q
python -c "import json;d=json.load(open('protocol/product.json',encoding='utf-8'));print(len(d['value_hypotheses']))"
```
