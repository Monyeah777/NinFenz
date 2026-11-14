# 用户访谈计划（INTERVIEWS）

> ⛔ 操作指令：本件是访谈**计划与问题脚本**（NF-Final §3A D01 外部验证入口）；机读真源 `protocol/product.json` 的 `interviews` 段，判据 `desktop/tests/test_product_contract.py`。**尚未执行访谈**（status=planned-external），不得把计划写成结论。
> 状态：v1（G0 · 2026-11-14）· 纪律：不诱导、不伪造、不在仓内存访谈原文。

## 状态

| 编号 | 角色假设 | 状态 |
|---|---|---|
| I-01 | 内容生产者（个人/小团队） | planned-external |
| I-02 | 需要复核 AI 产出的审查者/采购方 | planned-external |
| I-03 | 跨模型生产的技术团队 | planned-external |

- 目标次数：3（`target_count=3`）；当前真实证据件：0（`results/product/interviews/` 为空）。
- 外部操作声明：访谈属外部操作，需要真人时间与同意；本仓只提供脚本与证据格式。

## 同意与隐私

- 访谈前取得明确同意（用途、保存方式、是否录音、可随时撤回）。
- 访谈记录属**用户数据**（`PRIVACY.md` DC-02 机密）：只存本地；仓内**不存原文**，只存去标识摘要或 digest。
- 记录落点（若执行）：`results/product/interviews/I-0x.json`，schema `nf-interview/1`（含 consent/时间/角色/问题清单/要点摘要/digest）。

## 问题脚本（JTBD 风格，避免诱导）

1. 最近一次「要交付长内容但无法保证一致」是什么场景？当时怎么判断交付合格？
2. 你如何向别人证明这份产出不是凭空生成的？（现有证据是什么）
3. 换模型/换人重做时，哪些环节最常漂移？你怎么发现漂移？
4. 「五分钟内完成一次可复算验证」——对你意味着什么？哪些步骤会卡住？
5. 如果有一个工具把上述验收钉住，你愿意为哪部分付费？（可选服务/支持/纯开源）
6. 反例追问：什么情况下你会**不**用它？（避免只收集支持证据）

## 信号解读规则（防自欺）

- 只记录原话要点，不替用户总结成「需求已验证」；3 次访谈不足以宣称市场验证，状态最多到 hypothesis。
- 支持与反对证据都记录；反对证据不得被删。
- 访谈结论若与 `protocol/product.json` 假设冲突 → 改假设或标 rejected，并同步 `docs/RAID.md`（AS-01/AS-02）。

## 复核命令

```bash
python -m pytest desktop/tests/test_product_contract.py -q
python -c "import json;d=json.load(open('protocol/product.json',encoding='utf-8'));print(d['interviews']['status'])"
```
