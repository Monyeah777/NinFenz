# NF 元认知原子菜单（AI 可读）

> 用法：先读当前 need；只选 1-3 个原子；下轮重新读 need，不要一次排完整计划。

## 知识

- `k.represent` 表征（M0-M2）：需要把隐性内容外化；产出：结构化表征；常配：`k.partition`, `k.define`
- `k.partition` 划分（M0-M1）：整体需要分解；产出：部分集合；常配：`k.define`, `k.classify`, `m.check`
- `k.relate` 关联（M0-M1）：对象之间存在因果/时序/相似关系；产出：关系断言；常配：`k.quantify`, `k.instantiate`, `m.trace`
- `k.abstract` 抽象（M1-M2）：需要从实例提炼共相；产出：共同结构；常配：`i.compose`, `e.verify`, `i.merge`
- `k.define` 定义（M0-M2）：术语歧义或边界不清；产出：定义与适用范围；常配：`k.partition`, `k.classify`, `m.check`
- `k.instantiate` 实例化（M0-M2）：抽象需要落地检验；产出：具体实例；常配：`k.relate`, `k.quantify`, `m.trace`
- `k.classify` 分类（M0-M2）：需要归入已知类别；产出：类别归属；常配：`k.partition`, `k.define`, `m.check`
- `k.quantify` 量化（M0-M2）：属性可度量；产出：数值或量级；常配：`m.trace`, `k.relate`, `k.instantiate`
- `k.criterion` 判据设定（M2-M4）：需要确定合格标准；产出：判据集合；常配：`e.audit`, `e.calibrate`
- `k.standard` 标准选择（M3-M4）：不同任务需要不同有效性标准；产出：证据/有效性标准；常配：`c.select`, `i.transfer`

## 监控

- `m.observe` 观察（M0-M4）：需要了解当前认知状态；产出：状态读数；常配：`m.estimate`, `m.detect`, `c.stop`
- `m.compare` 比较（M0-M3）：需要判断变化或差异；产出：差异/相似读数；常配：`i.cluster`, `k.quantify`, `e.benchmark`
- `m.check` 核验（M0-M3）：命题需要被检验；产出：通过/不通过；常配：`e.adjudicate`, `e.falsify`, `k.partition`
- `m.estimate` 置信估计（M1-M3）：需要表达不确定性；产出：置信度；常配：`m.observe`, `m.detect`, `c.stop`
- `m.detect` 异常检测（M1-M3）：状态可能偏离预期；产出：异常/缺口标记；常配：`m.observe`, `m.estimate`, `c.stop`
- `m.trace` 溯源（M0-M2）：需要确认来源与推导；产出：来源链；常配：`k.quantify`, `k.relate`, `k.instantiate`

## 控制

- `c.select` 选择（M0-M4）：存在多个可选路径；产出：选中项；常配：`k.standard`, `i.transfer`, `c.sequence`
- `c.sequence` 排序（M1-M3）：步骤之间存在依赖；产出：执行顺序；常配：`c.select`, `c.allocate`, `c.switch`
- `c.allocate` 分配（M2-M3）：资源有限；产出：预算/注意力分配；常配：`c.select`, `c.sequence`, `c.switch`
- `c.switch` 切换（M2-M3）：当前策略失效或低效；产出：策略切换；常配：`c.select`, `c.sequence`, `c.allocate`
- `c.stop` 停止/继续（M2-M4）：达到收敛或预算边界；产出：停止/继续决策；常配：`m.observe`, `m.estimate`, `m.detect`

## 评价

- `e.verify` 验证（M0-M3）：产物需要对照判据；产出：合格/不合格；常配：`i.compose`, `k.abstract`, `i.hierarchy`
- `e.falsify` 证伪（M1-M2）：断言需要主动攻击；产出：反驳/存活；常配：`m.check`, `e.adjudicate`
- `e.adjudicate` 裁决（M1-M3）：存在冲突或不确定；产出：裁决结论；常配：`m.check`, `e.falsify`, `e.audit`
- `e.audit` 审计（M2-M4）：需要检查评价本身；产出：审计发现；常配：`k.criterion`, `e.calibrate`, `m.check`
- `e.calibrate` 校准（M2-M4）：置信与实际命中偏离；产出：校准后的置信；常配：`e.audit`, `k.criterion`
- `e.benchmark` 基准对照（M1-M3）：需要与基线比较；产出：相对差异；常配：`m.compare`, `k.quantify`, `m.trace`

## 整合

- `i.merge` 合并（M1-M2）：多个产物可相容；产出：合并产物；常配：`k.abstract`, `i.reconcile`, `e.adjudicate`
- `i.reconcile` 冲突消解（M1-M2）：产物之间存在矛盾；产出：消解结果；常配：`k.abstract`, `i.merge`, `e.adjudicate`
- `i.cluster` 聚类（M1-M2）：实例需要归组；产出：主题簇；常配：`m.compare`
- `i.hierarchy` 层级化（M1-M2）：需要组织上下位关系；产出：偏序/层级；常配：`i.compose`, `e.verify`
- `i.compose` 组合（M1-M3）：部件需要装配成整体；产出：组合结构；常配：`e.verify`, `k.abstract`, `i.hierarchy`
- `i.transfer` 迁移（M2-M4）：需要跨域复用；产出：跨域映射；常配：`c.select`, `k.standard`

## 快速组合（按当前 need）

- understand → `k.represent`, `k.partition`, `k.define`
- relate → `k.relate`, `m.trace`
- challenge → `e.falsify`
- resolve → `i.reconcile`
- synthesize → `k.abstract`, `i.compose`
- ground → `m.trace`, `e.verify`

> 这些不是固定管线；need 一变就立刻换簇。
