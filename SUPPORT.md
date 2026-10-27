# 获取支持

## 先看这里

- 想快速上手：`README.md`「五分钟快速开始」，或跑 `nf doctor` 看环境自检。
- 命令不确定：`nf help <子命令>`；编辑器接入见 `docs/lsp.md` 与 `nf lsp --print-config`。
- 协议与仓库结构：`docs/` 下的导航与 `llms.txt`。

## 提问

- **缺陷 / 功能请求**：开 Issue（附最小复现：命令 + 期望 + 实得 + 环境）。
- **安全漏洞 / 行为准则举报**：**不要**开公开 Issue，走 [SECURITY.md](SECURITY.md) 的私密通道。
- **投稿**：见 [CONTRIBUTING.md](CONTRIBUTING.md) 与投稿模板（GitHub 侧 `.github/ISSUE_TEMPLATE/library_submission.md`；Gitee 侧 `.github/ISSUE_TEMPLATE/NF投稿.md`）。

## 举报与申诉（治理通道 · Z6）

- **举报**：内容越界 / 侵权 / 滥用——走 [SECURITY.md](SECURITY.md) 的私密通道（**不要**开公开 Issue）。
- **申诉**：投稿被拒、条目被下架或被限制——在同一私密通道提交，注明被处理的编号（Issue 或 NF-ID）
  与理由。维护者按 [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) 的**同一把尺**复核，并在原处理线程给出
  书面结论：维持或改判，**都附依据**（对照哪一条准则 / 哪一条验收判据）。
- **不静默丢弃**：不承诺 SLA（见下），但「受理与否」必有明确回复。
- 通道只覆盖本项目管理范围内的内容；上游依赖与标准组织的问题请找对应上游。

## 支持边界（诚实声明）

本项目是**离线、单人维护、零门槛投稿**的仓库，不提供 SLA、不承诺响应时限，也不对投稿
内容的正确性或版权作担保（投稿授权链见 `CONTRIBUTING.md`）。

## 支持版本

- 当前 npm / CLI / MCP 支持线为 **1.1.x**；运行环境为 Node.js **>= 18.17** 与 Python **>= 3.11**。
- 安全修复优先覆盖当前最新 1.x 版本。1.0.x 及更早版本只在缺陷可利用性和修复成本允许时按补丁
  回移；不承诺长期并行维护，也不承诺固定 EOL 日期。
- 已发布 tag 不覆写；被取代的版本可能停止收到安全更新，用户应升级到当前 1.1.x，并复核对应
  Release 的 checksums、SBOM、OpenVEX、provenance 与 VSA。
