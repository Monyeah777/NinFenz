---
name: skill-creator
description: Create new skills, revise existing ones, and measure how reliably they trigger. Use when a task needs a reusable skill definition, a revision pass over an existing one, or a performance comparison between drafts.
---

# Skill Creator

本件是 **NF 自写的测试夹具**，不是任何第三方技能的副本。它的形态特征：

- `description` 是**裸值**（不用引号包裹）——解析器须原样保留、不剥字符、不报错；
- 正文是自由散文（无 NF 层级结构）——解析器须判 `mode == "external"`。

## 一个最小流程

1. 想清楚技能要做什么。
2. 写一版草稿。
3. 拿几个测试提示跑一遍，按结果修订。
