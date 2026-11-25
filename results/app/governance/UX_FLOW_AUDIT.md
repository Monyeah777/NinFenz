# 用户细节流程审计（全面扫盲）

> 范围：Library / NewProject / Import / Author / ProjectFlow / Assembly / Delivery / PackCenter / Settings / Search / DecisionLog。
> 结论：能跑通主链，但“可发现、可逆、可微调、可解释”缺口很多；下面按 P0/P1/P2 记，已修项标 ✅。

## P0：主链阻断/高频挫败

| # | 流程 | 问题 | 处理 |
|---|---|---|---|
| 1 | Delivery | 顶部 1>2>3>4 只是状态条，不能点；整页长滚动 | ✅ NfStepStrip 可点，滚到对应区块；Assembly 页也加了步骤跳转 |
| 2 | Assembly | 不能临时加槽位 | ✅ 槽位页支持添加/移除临时槽位 |
| 3 | Assembly/Delivery | 装配前不能浏览 plan/spec | ✅ Assembly 与 Delivery 都加“浏览计划”（steps/sections/slots/已填数） |
| 4 | Delivery | 最近导出不能单条删除 | ✅ 每条“移除记录” |
| 5 | Delivery | 最近导出不能收展 | ✅ 标题可收起/展开 |
| 6 | Project | 已有项目不能换 Pack | ✅ “换一个 Pack（复制为新项目）”：新 Pack 新建，复制旧项目 sidecars + 交付草稿；不改绑 |
| 7 | Delivery | 仍是单页长滚动，步骤条只是锚点 | ✅ 已按 activeStep 只渲染当前面板（1 计划 / 2 槽位 / 3 装配校验 / 4 导出） |
| 8 | Delivery | 不能预览装配结果并微调 | ⬜ 当前只有 assemble 后才能看 markdown；应在 step 3 加预览/块编辑 |
| 8b | Delivery | 微调只在“预览”里，回到装配没有“应用改动”闭环 | ✅ 预览保存置 needsRevalidate + 跳 step2；导出禁用，assemble 后自动 L1 重校验 |
| 9 | NewProject/Pack | Pack 列表无搜索/分组/自定义导入入口 | ✅ NewProject/换 Pack/PackCenter 加搜索；PackCenter 顶部已有 zip 导入 |
| 10 | Import | OCR/切片低置信没有逐块确认页 | ⚠️ 已有逐条 mapping Switch；新增“只看低置信”过滤 |

## P1：可理解/可恢复

| # | 流程 | 问题 | 处理 |
|---|---|---|---|
| 11 | Assembly | 槽位只有“必填已填 n/m”，没有逐槽位错误/示例 | ⬜ 需字段级校验与示例展开 |
| 12 | Assembly | 批量导入没有预览/回滚 | ⬜ 只有 textarea |
| 13 | Delivery | 最近导出只展示 5 条，没有“全部”页 | ✅ “全部导出”+“回收站恢复”；删除移入 exports/trash |
| 14 | Delivery | 删除导出记录不删文件、不可撤销 | ⬜ 需二次确认/回收站 |
| 15 | Delivery | 分享/打开/删除按钮挤在一行，窄屏易误触 | ⬜ 应收进 overflow |
| 16 | Project | 项目详情没有“当前 Pack 可换/可升级”说明 | ⬜ |
| 17 | PackCenter | 更新前没有文件级 diff/影响项目 | ⬜ 需更新预览 |
| 18 | Settings | 没有“导出全部数据/退出”入口（有备份但非可携带） | ⬜ portable UI 未接 |
| 19 | Search | 无“仅当前 Pack/项目”过滤 | ⬜ |
| 20 | DecisionLog | 无按动作/时间过滤，长列表不可用 | ⬜ |

## P2：打磨

| # | 流程 | 问题 |
|---|---|---|
| 21 | Library | 最近项目只显示标题，缺状态/最后修改/绑定 Pack |
| 22 | Library | 粘贴框与“粘贴开始”重复，主 CTA 不唯一 |
| 23 | NewProject | 创建失败只 toast/错误，缺字段级保留 |
| 24 | Import | 文件选择后无“取消/替换来源” |
| 25 | Author | 长文编辑无自动保存指示/冲突提示 |
| 26 | Delivery | 导出成功没有“打开所在文件夹/再次分享”聚合 |
| 27 | Delivery | 步骤 3/4 没有状态摘要（未装配/未校验/可导出） |
| 28 | Settings | 诊断/备份/隐私混在一页，缺搜索 |
| 29 | 全局 | 返回键在脏状态无确认 | 部分：Delivery 步骤内 Back 回上一步；脏草稿确认仍待补 |
| 30 | 全局 | 无全局“最近动作/撤销”入口（DecisionLog 只在设置） |

## 已修（本轮）

- Delivery 改为 4 个面板，只渲染当前步骤（计划/槽位/装配校验/导出），顶部步骤条可点。
- 预览保存后自动回到装配面板，needsRevalidate 生效，导出保持禁用；assemble 后自动 L1 重校验。
- 槽位页可添加/移除临时槽位（参与 assemble inputs）。
- “浏览计划”展示 plan steps、spec sections、槽位数量。
- 换 Pack 面板加搜索；创建新项目时复制旧 authoring/草稿。
- 最近导出可收起/展开、单条移除；“全部导出”页；删除文件移入 exports/trash。
- 导入映射加“只看低置信”过滤。
- 导出 PDF/UA 记录进入 DecisionLog。

## 下一批建议

1. 把 Assembly 从长页改成真正的 4 个步骤面板（只渲染当前步骤），下一步/上一步。
2. 在 step 3 加“预览并微调”，dirty 后必须重新 assemble/validate 才能导出。
3. Project 加“复制并换 Pack”，走 ProjectCreator，不直接改绑。
4. Delivery 最近导出加“全部”页、单条删除二次确认、文件回收站。
5. PackCenter 更新前 diff + 影响项目列表。

## 本轮验证

- Delivery 4 面板真机验证：step1 只显示计划，step2 只显示槽位；step3/4 只显示装配/导出。
- Android 单测：559/559（修正 StateRestorationTest 的搜索框索引后）。
- 真机 PLF110：装配 -> 导出 PDF/UA -> veraPDF PASS（C6-10-device.pdf）。
- Python：204 passed。

## Round 2

- PackCenter 顶部已有 zip 导入；NewProject/换 Pack/PackCenter 三处加 Pack 搜索。
- 最近导出“回收站”可恢复；删除写入 .restore 侧车。
- Delivery 步骤内 Back 先回上一步。
- Android 559/559；真机 4 面板已验证。

## Round 2 结果

- Android 559/559；真机四面板验证（step1 只计划、step2 只槽位）。
- 回收站/全部导出/只低置信/换 Pack 搜索均已接 UI。
