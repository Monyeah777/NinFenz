# NF Patterns 索引
> 最后更新：2026-11-14（复核）
> 本页**整体是生成物**：标题以下全部由 `nf patterns reindex` 从各 `PATTERN.md` 重建（含「现状对照」的计数）；手改会被覆盖。

<!-- BEGIN GENERATED: patterns-index -->

## Pattern 登记表（由各包 frontmatter 生成，勿手改）

| id | 名称 | 状态 | 适用面 | 规则数 |
|---|---|---|---|---|
| dependency-direction | 依赖方向：需要低层能力时由调用方注入 | active | 代码层 | 3 |
| error-message-guidance | 报错必须带修复指引 | active | 代码层、协议层 | 3 |
| fail-closed-verification | 缺验证器即拒绝，不静默降级 | active | 代码层、协议层 | 3 |
| predicate-single-source | 扫描面收敛：一条判据只准有一处实现 | active | 代码层 | 3 |
| single-source-truth | 真源 + 投影，禁止双写 | active | 协议层、资产层 | 3 |
| verifier-must-run | 判据必须接线：没跑过的判据不算判据 | active | 代码层 | 3 |
| worktree-vs-index | 门禁看工作区、git 看索引——两处口径先对齐 | active | 代码层 | 3 |

> 真源 = 各包 `PATTERN.md` 的 frontmatter；本表为投影（`nf patterns reindex` 重建）。

## 现状对照（生成 · 计数由本表实时算出）

| 面 | 现值 | 说明 |
|---|---|---|
| 实践包 | **7** | 生成区表格行数 |
| 规则总数 | **21** | 各包 rules 长度求和（每包 3 条） |
| 状态分布 | active 7 | 各包 frontmatter 的 status |

**包 id**（生成）：`dependency-direction`、`error-message-guidance`、`fail-closed-verification`、`predicate-single-source`、`single-source-truth`、`verifier-must-run`、`worktree-vs-index`

## 复现与引用口径（生成）

```bash
python scripts/nf.py patterns ls         # 列全部实践包（真源 = 各 PATTERN.md）
python scripts/nf.py patterns verify     # 格式 + 可证性机检
python scripts/nf.py patterns reindex    # 重建本页（幂等：无变化即输出「无变化」）
```

- **本页整体是生成物**：手改会被下一次 reindex 覆盖；要改内容请改 patterns/<id>/PATTERN.md。

<!-- END GENERATED: patterns-index -->
