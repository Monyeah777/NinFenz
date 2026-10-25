# 附加许可（AGPL-3.0-only §7 additional permissions）

> **免责声明：本文件不构成法律意见。THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND.**
> 本文件只授予**额外许可**（§7），**不含任何费用、罚则或审计义务**——那类条款若写进许可证即属
> "further restriction"（AGPL §10 允许被许可人移除），故只能出现在 `COMMERCIAL.md` 的商业合同语境里。

> 依 AGPL-3.0 第 7 节授予的**additional permissions**：只增加权利，不增加限制。
> 若某条款与 AGPL 冲突，以 AGPL 为准（§7 明确：额外限制无效）。
> 本文件只公开**许可性质**的条款；小实体定价、商业触发阈值等商务内容在商业协议内（COMMERCIAL.md）。

## E1 · 产物与数据例外（Output & Data Exception）

用本软件**生成**的产物（文档、图纸、装配结果、报告、中间数据）版权归**使用者**所有，
不属于 AGPL 下的"covered work"，不受 AGPL 传染，可自由商用与闭源分发。
前提：产物不是"本软件的修改版本"（即不是把 NF 源码/资源整体复制成另一份产品）。

## E2 · 内部使用澄清（Internal Use Clarification）

组织内部**部署与使用**（含自建服务器、内部 CI、内部平台）不构成对外"传送"，
**不触发** AGPL §13 的远程源码提供义务；只有当你把基于 NF 的服务**提供给该组织之外的人**时才触发。
（依据：AGPL §2 对 propagate/convey 的定义；本条是对既有法律状态的确认，不扩张也不限缩。）

## E3 · CI / 评估例外（CI & Evaluation Exception）

在 CI、测试、基准、技术评估、教学演示中运行/修改本软件，**不**要求公开你的流水线配置、
测试夹具或评估报告；只需在你**分发**本软件或其修改版本时履行 AGPL 义务。

## E5 · 聚合与插件边界（Aggregation & Plugin Boundary）

- 与本软件"仅仅放在一起分发"的**独立程序**（不同进程、通过文件/CLI/网络协议通信）属**聚合**，
  不受 AGPL 传染（依据 AGPL §5 末段）。
- 通过**公开协议**（如 `MCP`、`nf` CLI、协议层 JSON 契约）与本软件通信的插件/适配器，
  视为独立作品；但**链接/内嵌**本软件代码的插件属衍生作品，受 AGPL 约束。
- 边界判定以"是否在同一地址空间内链接/内嵌"为准，不以"是否在同一仓库"为准。

## E6 · 商标与命名（Trademark & Naming）

AGPL 不授予商标权。你可以说"基于 NinFenz 构建"，但**不得**：
- 用 `NinFenz` / `NF` 作为你产品的名字或主要标识；
- 暗示作者为你背书；
- 把修改版继续叫 `nf` 官方 CLI 而不加区分。
详见 `TRADEMARK.md`。

## E9 · 生效、变更与终止（Effect, Change, Termination）

- 本附加许可随对应版本**永久生效**；作者可在**新版本**调整附加许可，但不追溯已发布版本；
- 你违反 AGPL 时，本附加许可随 AGPL 授权一并终止（AGPL §8 的恢复机制同样适用）；
- 本附加许可不构成对 AGPL 的修改，只是 §7 允许的补充。
