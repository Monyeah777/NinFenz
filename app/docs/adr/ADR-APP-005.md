# ADR-APP-005：统一 nf-import 管线：嗅探 → 结构抽取 → 映射建议

| 项 | 值 |
|---|---|
| 编号 | ADR-APP-005 |
| 状态 | accepted |
| 日期 | 2026-11-15 |
| 范围 | NF APP（Android / Desktop / 平板控制面 + 共享核心） |
| 上位 | `STRATEGY.md` → `app/docs/CONTRACT.md`（A0 冻结）/ `app/docs/CLI.md` |

## 背景

作者素材来自 Markdown/JSON/YAML/zip/模板/Pack，未来还有 html/docx/pdf/OCR。若每种来源各写一套入口：映射语义分裂、上限/安全策略散落、无法统一负例。

## 决策

1. 唯一导入管线：嗅探（魔数 → MIME/扩展 → 内容特征）→ 结构抽取（标题/段落/代码块/表格）→ 映射建议（heading→section、paragraph→slot、code_block→example、table→structured；带 confidence + rationale；无法映射入 unmapped）→ 输出 `nf-import/1` → 生成 DraftProject。
2. 置信度 ∈ [0,1]；< 0.6 必须在 `detected.candidates` 给候选，且不得自动入库（`NF-IMP-002` warn，exit 0 由人确认）。
3. 原文必须保留（`text` 或 `text_digest` + 原文文件）与来源；不静默覆盖已有项目（只生成 DraftProject）。
4. 首版适配器：text / markdown / json / yaml / zip / nftpl / nfpack；次版：html / docx / pdf / ocr——未实现即 exit 3 + `NF-IMP-004`，不得静默当文本处理。
5. 所有上限读 `app/schema/limits.json` 的 import 段，不散落字面量。

## 后果

**正面**

- 单一入口：新增格式只加适配器，映射/上限/负例一次做好。
- 原文保留 + digest：导入结果可回溯、可复算、可重新映射。
- 未实现格式显式拒绝：不会把 docx/pdf 当乱码文本静默入库。

**负面 / 代价**

- 首版格式覆盖有限（html/docx/pdf/ocr 未实现），作者需先转 Markdown。
- 置信度阈值（0.6）是经验值，需要真实语料校准。
- 原文保留增加存储（受 limits 约束，但大文件导入会占空间）。

## 替代方案（及否决理由）

| 方案 | 结论 | 理由 |
|---|---|---|
| A. 每种格式独立命令 | 否决 | 语义/上限/安全策略分裂，测试矩阵爆炸 |
| B. 直接解析成目标 md-spec（跳过 nf-import/1） | 否决 | 丢失原文与映射理由，无法回溯/重映射 |
| C. 依赖外部转换器（pandoc 等） | 否决 | 环境依赖不可控；离线/打包不可行 |
| D. AI 辅助抽取 | 否决（首版） | 违反离线/无密钥约束；若引入须走 CCOS 任务（ADR-APP-001） |

## 证据落点

| 证据 | 路径 / 判据 |
|---|---|
| 导入语义（嗅探顺序/置信度/适配器矩阵/原文保留/不覆盖） | `app/docs/CONTRACT.md` §5.2 |
| `nf-import/1` 结构（source/detected/structure/suggested/warnings） | `app/schema/nf-import.schema.json` |
| 导入类上限（headings/code_blocks/tables） | `app/schema/limits.json` |
| 错误码 NF-IMP-001/002/003/004、NF-MAP-001 | `app/schema/error_codes.json` |
| op 面（import-sniff / import / map-suggest） | `app/docs/CLI.md` §3 |

## 复审条件

- 每新增一个适配器时（必须同步 limits 与安全负例）。
- 置信度阈值需要按真实语料调整时（阈值变更需重跑 golden）。
- 若引入 OCR/AI 抽取（信任边界与密钥面变化，需新 ADR）。

> 本 ADR 只声明决策与边界。实现状态以 `app/docs/ARCHITECTURE.md` §5/§11、`app/results/GATES.json` 与现场复跑命令为准；未落地项写 `OPEN`，不得据本 ADR 声称「已实现」。
