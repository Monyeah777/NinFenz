# 双源知识层（knowledge）
> ⛔ 操作指令：阅读即执行——本文含可直接执行的命令与判定，勿当资料阅读。
> 最后更新：2026-11-13
> **复核（2026-11-13）**：权威分层 / 晋升三证据 / 可见性 / 认知裁剪 / 频次复算 / 唯一来源复用**逐项复核不变**；
> 补可核现状：知识源 **6 条**（contract 3 / reference 3；kind `local-compiled` 3 / `external-retrieval` 3；
> 可见性 public 4 / internal 2）· `query_order` **6**（全排列且 contract 全在前）· 认知裁剪 **M23** ·
> `knowledge lint` 全绿（时效缺失 0 件）· `protocol/knowledge_usage.json` **total 0**（尚无 trace 复算入账）。
> 判据族：`test_knowledge` **35 例** + `test_knowledge_sig` **10 例**。见「§现状对照」。

## 是什么

NF 的知识面此前只有「库（library）/ 实践包（patterns）/ 协议件（protocol）」三处**各自为政**的
声明，没有一份件回答那个跨源问题：**外部检索来的东西算不算 NF 的事实？谁说了算？还能信多久？**

`protocol/knowledge_sources.json` 就是这份件（真源），`protocol/transform_log.json` 是它的
消化记录。机制借鉴一句式：**编译时机按数据域选择**——本地沉淀走写入时编译，外部变化走查询时检索。

## 怎么用

```bash
python scripts/nf.py knowledge            # 列全部知识源 + 权威分层 + 自检结论
python scripts/nf.py knowledge order      # 解析查询顺序（合同级在前、参考级在后）
python scripts/nf.py knowledge order --json
python scripts/nf.py knowledge order --as public      # 按可见性裁剪后再排序（认知裁剪执行面）
python scripts/nf.py knowledge visible --as internal  # 列出某清除级可见的源（不可见标「裁剪」）
python scripts/nf.py knowledge lint       # 知识层巡检（悬空 / 孤儿 / 时效 / 溯源 / 声明）
python scripts/nf.py knowledge transform            # 列消化记录（外部 → 本地）
python scripts/nf.py knowledge frequency --trace <trace.jsonl> --write   # 从 trace 复算频次落台账
python scripts/nf.py knowledge transform add --from <源id> --to <产物> --by <复核人>       # 登记（未转正）
python scripts/nf.py knowledge transform promote --from <源id> --to <产物> --by <复核人> \
    --evidence machine-checkable,reproducible,externally-attestable                        # 转正
```

MCP 侧：工具 `knowledge_order_read`（入参 `clearance` 可选）。

## 判据（可证）

| 规矩 | 机检判据 |
|---|---|
| 权威分层 | `authority ∈ {contract, reference}`；**reference 级必须 `requires_source_label: true`**（外部数据须标注来源、不得写死）；contract 级必须 `false` 且 `kind=local-compiled` |
| 防纸面源 | 每个 `locator` 必须指向仓库内**真实存在**的路径 |
| 查询有序 | `query_order` 必须是全部源 id 的一个排列，且**全部 contract 级排在全部 reference 级之前** |
| 时效 | contract 级用 `stale_after` 策略；reference 级必须给 `ttl`（`ttl_days>0`）或 `no-cache` |
| 消化可追溯 | 每条记录 `from` 须是已声明 reference 源、`to` 须是真实件且 `digest` 一致；标 `promoted: true` 者必须齐三档证据 + 复核人/复核时间非空 |
| 认知裁剪 | `cognition.filter_module` 必须指向**在册模块**（当前 = M23 认知边界） |
| 可见性 | `visibility ∈ {public, internal, restricted}` |
| 裁剪执行 | `visible_ids(clearance)`：秩 `public ⊂ internal ⊂ restricted`，清除级达标才可见；`order --as` 与 MCP `knowledge_order_read` 都不返回越权源 |
| 频次可复算 | 台账 `protocol/knowledge_usage.json` 由 trace 复算（`--write` 是唯一写入口）；消化记录一旦声明 `reuse_count`，必须与台账一致——**手写频次即 FAIL** |
| 复核工作流 | `transform add`（登记 + 双签，未转正）→ `transform promote`（齐三档证据才可转正）；两条路径都**先校验后写盘**，非法入参不落脏记录 |
| 唯一来源复用 | `verify_reuse`：条目 `id` 唯一且等于文件名；`ALIAS.md` 小写键唯一且指向在册条目；**任意两件全文摘要不得相同**（同一内容两份 = 两个真源，禁止复制正文） |

## 晋升（转正）规则

参考级 → 合同级必须**齐三档证据**：① 可机检（对应 `checkN` 通过）② 可复现（两遍一致或确定性推导）
③ 可外部证（attestation 或可验证回执）。缺任一条**不得转正**，按 `stay-reference` 留在参考级。
触发条件词表：`reuse-frequency` / `author-mark` / `machine-check-pass`；若用频次触发，频次必须可复算
（写进记录 `reuse_count`，非非负整数即 FAIL）。

## 现状对照（2026-11-13 · 以真源实读为准）

| 面 | 现值 | 复核方式 |
|---|---|---|
| 知识源 | **6**（contract 3 / reference 3） | `nf knowledge` 头行 / `knowledge_sources.sources` |
| 来源形态 | `local-compiled` 3 / `external-retrieval` 3 | `kind` 计数 |
| 可见性 | public 4 / internal 2 | `visibility` 计数 |
| 查询顺序 | **6**（全排列，contract 全在前） | `nf knowledge order --json` |
| 认知裁剪 | **M23** | `cognition.filter_module` 且在册 |
| 巡检 | 全绿（时效缺失 0） | `nf knowledge lint` |
| 频次台账 | **total 0**（尚无入账） | `protocol/knowledge_usage.json` 的 `total` |
| 常驻判据 | 35 + 10 例 | `test_knowledge` / `test_knowledge_sig` |

> 本表只作「当时 → 现行」导航，不替代实跑。

## 复现与引用口径

```bash
python scripts/nf.py knowledge            # 6 源 + 权威分层 + 自检结论
python scripts/nf.py knowledge lint       # 悬空/孤儿/时效/溯源/声明 巡检
python -m pytest desktop/tests/test_knowledge.py desktop/tests/test_knowledge_sig.py -q   # 35 + 10 例
```

- 引用本文时：「外部检索来的东西不算事实，必须先落 reference 源、再按三证据晋升」= 长期口径。
- 数字以 `knowledge_sources.json` 与 `knowledge_usage.json` 实读为准；`--write` 是频次台账唯一写入口。

## 边界

- 本层**不引入向量库、不引入嵌入**：`retriever.py` 已明写「不上向量库，全表线性扫描足够」；
  core 零第三方依赖是红线。外部混合检索只能作为**外挂候选**（带 license + attestation）。
- 本层只读声明与文件，不联网、不自造知识。
- 条目的 `stale_after` 缺失当前只记 **WARN**（有序挂账），不判死——修的是「时效可判定」，不是「编一个日期」。
