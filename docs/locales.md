# 语言面与本地化（locales）
> ⛔ 操作指令：本文是语言面与本地化策略的**声明件**；判据在 check34（core/locales.py），读到即执行。
> 最后更新：2026-11-13

## 这是什么

NF 的语言面分两层：**入口面**（README.md / README.en.md / README.ja.md）与**文档面**（docs/<lang>/…）。
真源 = protocol/locales.json：逐语言的入口、责任方（codeowner）、覆盖面声明，以及文档译件 + **源件摘要**。

## 规则（全部机检）

1. **入口面**：每面须含同一组机读锚点 + 语言切换行（逐条列出全部在场语言）+ H2 结构对齐 + canonical 引用的 .md 件齐。
2. **文档面**：译件路径必须**镜像**原文（docs/<lang>/<原文相对路径>）；每件登记 source_sha256，**源件一改即判过期**。
3. **覆盖面诚实**：coverage=entry 的语言不得有文档译件；coverage=entry+guides 必须备齐注册表声明的全部译件。
4. **未声明即红**：docs/<lang>/ 下出现未登记译件 → FAIL（防「没人管的第二语言面」）。

## 怎么加一份译文

（1）写译文：docs/<lang>/<原文相对路径>；
（2）在 protocol/locales.json 的 docs[].translations 登记 path；
（3）跑 python scripts/nf.py locales --write 重签源件摘要；
（4）跑 python scripts/nf.py locales 自检——过期 / 未镜像 / 缺语言 / 未声明 都会红。

  
## 现状对照（2026-11-13 · 以注册表实读为准）

| 面 | 现值 | 复核方式 |
|---|---|---|
| 语言 | **3 语**（zh / en / ja），均为 coverage=entry+guides | protocol/locales.json: locales |
| 入口面 | **3 件**（README.md / README.en.md / README.ja.md） | 注册表 entry + 文件在场 |
| 文档译件 | **12 件** = 6 份指南 × 2 语 | docs[].translations |
| 指南清单 | release / locales / mcp / terminal / layers / **lsp**（6 份） | docs[].path |
| 责任方 | 3 语均登记 codeowner | locales[].codeowner |
| 判据 | check34 + test_locales **12 例** | verify.sh / pytest |

> 本表只作「当时 → 现行」导航；数字以 nf locales 实读为准。

## 复现与引用口径

```bash
python scripts/nf.py locales          # 语言/译件对账 + 过期检测
python scripts/nf.py locales --write  # 重签译件源件摘要（改原文后必须跑）
python -m pytest desktop/tests/test_locales.py -q   # 12 例
```

- 引用本文时：「入口 3 语 + 文档 12 译件、源件一改即过期」= 长期口径；清单以注册表 docs[] 实读为准。
- 本文件自身也是登记译件之一：改它会连带 12 件摘要过期 → 必须同步 en/ja 再 `locales --write`。

## 现状与边界

- 入口面 **3 语**（中文 / English / 日本語）；文档面已覆盖 **6 份**指南：发布 / 本地化 / MCP 接入 / 终端 / 抽象阶梯 / **LSP**（共 12 译件）。
- 其余文档仍单语——**由注册表显式声明**，不是静默单语；新增译文按上面四步走。
- 本机制不引入外部翻译平台、**不做机器翻译**：内容质量由译者负责，判据只保证「声明的都在场且不过期」。
- 语言面责任方见注册表的 codeowner（与 Home Assistant 的 codeowners 同义）。
