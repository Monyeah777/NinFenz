---
id: error-message-guidance
name: 报错必须带修复指引
status: active
scope:
  - 代码层
  - 协议层
applies_to:
  - desktop/src/core
  - verify.sh
rules:
  - 每条 raise/异常消息必须写出「缺什么 · 补什么」（含具体路径/命令或可照做的下一步）
  - 门禁对缺失指引的 raise 判 FAIL，不做"提示性通过"
  - 修复指引里不得出现无法执行的占位（如「请自行检查」）
evidence:
  - check27
  - desktop/src/core/purity_scan.py
---

## 为什么

报错是**最后一次可执行的交互**。只说"失败了"会把定位成本全部推给读者；NF 的读者常常是 AI，
没有修复指引时它会**猜**——猜出的补丁比错误本身更贵。

## 怎么用

```python
raise ValueError("资产键未找到：%s（修复指引：nf asset ls / 包 assets/README.md 可枚举）" % key)
```

## 反例

```python
raise ValueError("invalid input")          # ✗ 无修复指引
raise ValueError("模块未找到，请检查")        # ✗ 指引不可执行
```

## 已有的实证

`purity_scan.py` 的 R4 规则在 check27 里常驻；该规则曾当场拦下一次本仓提交（`取代者不能是自己`）。


---

## 现状对照（2026-11-14 · 以 `purity_scan` / check27 实读为准）

| 面 | 当前口径 | 复核方式 |
|---|---|---|
| 规则载体 | `desktop/src/core/purity_scan.py` 的 **R4**（「错误信息即微型文档」） | 该文件头部规则表 |
| 门禁接线 | **check27**（架构纯度体检）内含「core raise 消息修复指引审计」 | `python scripts/nf.py verify --only 27` |
| 适用面 | `desktop/src/core`（整目录）+ `verify.sh` | frontmatter `applies_to`（两者都在场） |
| 实证 | `check27` + `purity_scan.py`（`evidence` 两条均可解析） | `nf patterns verify` |
| 覆盖规模 | `desktop/src/core/*.py` 中「修复指引」出现约 **900** 处（**以 grep 实读为准，本文不钉具体数**） | `grep -c` 汇总 |

- **本文不钉固定命中数**：那是随提交变化的运行时事实；机制断言（每条 raise 必须写「缺什么 · 补什么」）才是长期口径。
- check27 的 PASS 只覆盖它自己的判据面——**不等于全量门禁**（`nf verify` 会明确打印未迁入的 check 列表）。

## 复现与引用口径

```bash
python scripts/nf.py verify --only 27     # 单跑 check27（含 raise 修复指引审计）
python scripts/nf.py patterns verify      # 格式 + 可证性 + INDEX 投影
```

- 写新 `raise` 时：消息里带**可执行**的下一步（具体路径/命令），不要写「请自行检查」这类占位。
- 引用本 pattern 时：「报错是最后一次可执行的交互」是动机；可检面是 check27 的 R4 审计。
