# 迁移指南 · 基于 `nf sig` / `nf diff`（41 波C D5 · C2 产物衍生文档位）
> ⛔ 操作指令：阅读即执行——本文含可直接执行的命令/步骤/判定，勿当资料阅读。
> 最后更新：2026-11-13
> **复核（2026-11-13）**：三步流程（基线 → 差异 → 修复指引 → 验收）与「与既有门禁的关系」**复核不变**；补可核现状：
> `nf sig --verify` 实读**文档 4 · 可复现**（根目录 `01/02/06/07`）· `nf diff --history` 允许历史面 = 根协议 **4** + `protocol/` **2**（CONFORMANCE / EXTENSION）+ `protocol/schema/*.json` **9** = **15** 个可查目标 · 影响度词表 **3** 值（`editorial` / `additive` / `bump`）。见「§现状对照」。

> 用途：协议/方案文档演进与迁移核查的衍生工具文档位——C2 版本差异检测产物的「怎么用」入口。

## 一、何时用

- 大版本升级前：先 `python scripts/nf.py sig --verify` 确认 01-36 基线签名可复现（check25）。
- 改动某协议/方案文档后、提交前：对照旧提交跑 `nf diff`，判断改动是字段级/引用级/破坏级。
- 收到迁移要求（如协议版本 bump、模块改号）：用 diff 定位受影响引用，再按 `nf explain` 修复对应 check。

## 二、标准流程

1. **基线**：`python scripts/nf.py sig <旧文件> <新文件> --json` 或全量 `sig --verify`。
2. **差异**：`python scripts/nf.py diff <旧版文件> <新版文件>`（如改动前后的 `01_核心协议.md`）
   - 输出逐字段差异（字段变更 / 新增 / 移除）+ 判定（破坏 / 需评审 / 兼容）。
   - 判定规则：文档编号变更 = 破坏；引用/章节移除 = 需评审；仅版本演进 = 兼容。
3. **修复指引**：`python scripts/nf.py explain <check>`（如 check24/25/26）取「缺什么/补什么/示例」。
4. **验收**：`bash verify.sh` 全绿（0 WARN / 0 FAIL；check 数与 PASS 基线见 `nf stats --check` 生成区，**不钉死**——此处曾停在 check1-36/PASS=59）方可提交；迁移记录进 CHANGELOG 归档。

## 三、契约演进时间线

单次 `nf diff OLD NEW` 只回答两份文件之间的变化；需要追查一份正式契约如何演进时，用：

```bash
python scripts/nf.py diff --history 20 01_核心协议.md
python scripts/nf.py diff --history 20 protocol/schema/contract.schema.json --json
```

时间线按 Git 历史从旧到新重算每版签名与摘要，并对相邻版本给出 `editorial / additive / bump`
影响度。Markdown 契约复用 `nf sig` 的章节、引用和版本面；JSON schema 额外比较结构化键路径，
必填项增加、类型变化、移除和版本槽位变化均判 `bump`。

允许的历史面：`01/02/06/07` 协议文档、`protocol/CONFORMANCE.md`、`protocol/EXTENSION.md`
及 `protocol/schema/*.json`。命令只读，不生成或改写迁移记录；`bump` 仍须按 02 §9.3 留档。

## 四、与既有门禁的关系

`nf diff` 是**编译期冲突发现**（录入时），verify check25 是其自动闸门（可复现）；两者互补但不替代

## 现状对照（2026-11-13 · 以 `nf sig --verify` 与 core/contract_history 实读为准）

| 面 | 现值 | 复核方式 |
|---|---|---|
| 签名文档 | **4**（根 `01_核心协议.md` / `02_联动注册表.md` / `06_Agent执行协议.md` / `07_官方核心出厂与社区预设导航.md`） | `nf sig --verify` |
| 可复现 | **1**（两遍一致，check25 同语义） | 同上尾行 |
| 历史面 · 根协议 | **4** | `core/contract_history.ROOT_CONTRACTS` |
| 历史面 · protocol | **2**（`CONFORMANCE.md` / `EXTENSION.md`） | 同上 `PROTOCOL_CONTRACTS` |
| 历史面 · schema | **9**（`protocol/schema/*.json`） | 目录计数 |
| 历史面合计 | **15** | 4 + 2 + 9 |
| 影响度词表 | **3** 值：`editorial` / `additive` / `bump` | `nf diff --history` 输出 |
| 命令形态 | **3**：`sig` / `diff` / `diff --history N`（+ `--json`） | CLI `--help` |

> 本表只作「当时 → 现行」导航；数字以 `nf sig --verify` 与 core 常量实读为准。

## 复现与引用口径

```bash
python scripts/nf.py sig --verify                       # check25 同语义：基线两遍一致
python scripts/nf.py diff <旧文件> <新文件> --json       # 字段级差异 + 兼容判定
python scripts/nf.py diff --history 20 01_核心协议.md    # 契约演进时间线（Git 重算）
```

- 引用本文时：「单次 diff 只答两份文件之间；追查演进用 `--history`」= 长期口径。
- `--history` 只读、不改写迁移记录；`bump` 仍须按 02 §9.3 留档（本工具不替代正式迁移流程）。
check13（协议版本一致性/迁移完整性四步）与 CHANGELOG 归档——协议层真迁移仍走 02 §9.3。
