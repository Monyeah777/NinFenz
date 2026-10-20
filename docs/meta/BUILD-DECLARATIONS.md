# 建设层裁定与声明登记（declare / argument 型条目）

> 本文件是 BUILD_MANUAL 105 条里 **declare / argument / 不适用** 那批条目的成文落点。
> 口径：只写可被复核的事实与触发条件，不写「已配置」这类无证据结论。

## 1. 平台设置类（判词 UNKNOWN / 不适用，取证需账号主人）

### BR-06 强制 2FA — UNKNOWN（未取证）
- 取证途径（人工，5 分钟）：GitHub → Settings → Password and authentication → Two-factor authentication。
- 受限原因：本机无 gh CLI、无 API token；账号设置不经仓库 API 暴露。**未取证，不写作已开启**。

### IN-01 Dependents 面板 — UNKNOWN（未取证）
- 取证途径：仓库 Insights → Dependency graph → Dependents（需登录 Web）。
- 替代取证（可脚本化）：跨仓代码搜索对本仓 raw URL / npm 包名 `ninfenz` 的引用；npm 反向依赖查询。
- 当前结论：**未知**；首次取证后把日期与结论回填本文件。

### IN-02 Traffic 分析 — UNKNOWN（未取证）
- 取证途径：Insights → Traffic（views / clones / referrers）。需 admin 权限，API 不暴露。
- 记录计划：首次只记基线（日期 + 三组数字），30 天后第二次，用 referrers 判断分发通道是否有效（总量不是用户数）。

## 2. 不适用（判词本身就是「不适用」，按手册要求写判定依据与重评触发）

### CW-08 Merge Queue — 不适用
- 判定依据：单人单 PR 节奏（近 90 天并发 PR 峰值为 1；仓库无外部贡献者），队列会为单个 PR 多跑一轮全量 CI，收益为负。
- 重评触发：出现连续 2 天同时开启 ≥2 个 PR，或引入第二个有合并权维护者。

### RP-05 Projects 看板 — 不适用
- 判定依据：单人线性推进，issue 状态已足够；看板会变成「卡片停在 Todo」的反向证据。
- 重评触发：出现第二条并行工作线（≥2 个 active 分支同时施工超过两周）。

### HS-01 Git LFS 接管 — 不适用
- 判定依据（现测）：最大单文件 3.01 MB（protocol/generated/asset_contract.frictionless.json，**文本 JSON**）；无二进制大件（图片均 < 6 KB，demo.gif 亦为站点资产），LFS 无适用对象。
- 重评触发：出现需版本化的单文件 > 50 MB（模型权重/设计稿）。

### HS-02 历史清除 — 不适用
- 判定依据（现测）：`git count-objects -vH` size-pack = 26.23 MiB；无 > 100 MB blob，无需 filter-repo。
- 重评触发：任一 blob > 100 MB，或仓库 pack 体积 > 1 GB。

### HS-04 清理后收尾 — 不适用
- 判定依据：HS-02 未执行（无历史清除动作），无强推/通知/远端 GC 的收尾对象。
- 与 HS-02 保持一致；两者同时重评。

## 3. 未做的长期项（写「未做」+ 触发条件，不假装达标）

### SC-11 SLSA 等级目标 — 未做（有内部实现，无对外定位声明）
- 现状事实：check41「构建隔离」+ check42「不可伪造 provenance」已在 verify 内；但缺外部可验签名锚（cosign 不在场，check42 自身 WARN 如实标注）。
- 未做项：对外定位声明（当前等级/满足项/缺口项）。触发条件：首次对外发布二进制制品时一并写。

### SC-12 内容溯源（C2PA） — 未做（先做交付物性质判定）
- 判定：本仓交付物=协议文档 + 生成器 + 内容包（community/library）。**内容包属内容制品**，但当前分发形态是仓库内 md（不是签名内容包），C2PA 无承载对象。
- 触发条件：NF 以「内容包」形态对外分发（下载即用卡片/文档集）时，采用 C2PA 或等价清单签名。

### MT-05 repo-health 信号集 — 未做（部分能力已散在门禁里）
- 现状：CI-04 大文件、FX-07 gitignore 覆盖度、HS-03 体积、verify 42 check 已覆盖大半信号，但**没有一份 PR 前自检清单**。
- 触发条件：接入第二贡献者前补齐为可执行清单（20+ 项）。

### MT-06 CHAOSS 指标 — 未做
- 可算项：发布频率（tag 日期）、贡献者集中度（git shortlog，恒为 1 人）。不可算项：首次响应时间/PR 关闭率（需 GitHub API）。
- 触发条件：接入 GitHub API token 后按月统计；单人阶段这三项不构成缺陷。

### MT-08 独立第三方审计 — 未做
- 触发条件：出现首个企业用户或对外发布承诺时启动；报告可公开部分入 docs/audit/。此前不做自我审计冒充。

### MT-09 中立治理与基金会路径 — 未做
- 事实：提交者 1 人（Monyeah777）；无公开会议/投票；治理见 .github/GOVERNANCE.md 的 BDFL 声明（若该文件尚未落盘，本项如实标未做）。
- 触发条件：≥3 名独立提交者且持续 6 个月，再谈多厂商治理或捐赠。

### CW-09 机器人 Code Review — 不接入
- 定位声明：本仓唯一评审者是维护者本人，机器人评审会制造无人处理的评论噪音；质量面的机器判定已由 verify 42 check + CI 承担。
- 重评触发：PR 流量 > 5/周 或引入第二名评审者。

### IN-03 变更热点分析 — 未做
- 触发条件：任一文件在最近 90 天改动次数进入前 3 且无对应单测时启动；产物落 results/audit/hotspot-<date>.json。
