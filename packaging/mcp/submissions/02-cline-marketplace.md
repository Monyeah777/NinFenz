# 02 · Cline MCP Marketplace —— Issue 正文（复制整段）

> 用途：打开 https://github.com/cline/mcp-marketplace/issues/new?template=mcp-server-submission.yml 并粘进对应字段。
> **上传附件**：仓库里的 `packaging/mcp/assets/icon-400.png`（要求 400×400 PNG）。

```text
### GitHub Repo URL
https://github.com/Monyeah777/NinFenz

### Logo
（附件已上传：icon-400.png，400×400 PNG）

### Reason for Addition
NinFenz Content Gate 是一个只读 MCP 服务器：把长内容的验收标准（协议 / 模块 / 管线 / 资产 / 馆藏）变成 agent 可调用的检索与取件工具面。
给 Cline 用户的价值：
- 12 个只读工具 + 1 个 prompt（assemble_guide）；无写路径，不会改用户仓库；
- 零第三方依赖（Python 标准库），一条 `npx -y ninfenz serve` 即可装载；
- 双协议版本（modern 2026-07-28 + legacy 2025-11-25），参数按 inputSchema 逐条校验（不合即 -32602）；
- 仓库自带确定性门禁（门禁条数与 PASS 基线以仓库 `nf stats` 生成区为准，**不在提交文案里钉**），安装说明见仓库根 `llms-install.md`。

### 实测确认（先在 Cline 里跑一次，再留下这句）
把仓库根 `llms-install.md` 交给 Cline，安装成功并能列出 12 个工具。
```


---

## 审核要点自检（2026-11-14 复核补）

| 面 | 现值 | 复核方式 |
|---|---|---|
| 仓库 URL | `https://github.com/Monyeah777/NinFenz` | 与材料包同源（本目录 10 份提交件共用值） |
| 图标 | `packaging/mcp/assets/icon-400.png`，**真实 400×400 PNG**（文件名不作数，读 IHDR） | 像素实测命令见 `assets/README.md` |
| 安装说明 | 仓库根 `llms-install.md` 在场（Cline 要靠它完成一键安装） | 文件实读 |
| 工具面 | **12 只读工具 + 1 prompt**，无写路径 | `desktop/src/core/mcp_runtime.py` |
| 双协议 | modern `2026-07-28` + legacy `2025-11-25` | `mcp_runtime.py` 的协议事实段 |
| 审核状态 | **平台侧未验**（Cline 人工审核：社区活跃度 / 维护者可信度 / 成熟度 / 安全四维） | 需等审核结果 |
| 「实测确认」 | **待作者在 Cline 客户端里跑一次**（不是仓库能代做的动作） | 提交前手动完成 |

- **不再钉运行时计数**：本件此前写「check1-40 · PASS=72 · 约 2500 单测」，2026-11-14 实测与仓库当前基线不一致（且提交给目录审核的文案不该带会过期的数字）——已改为「以 `nf stats` 生成区为准」。
- 提交前把上表逐行过一遍；审核若要求补材料，只补这一份，不要新开 issue。
