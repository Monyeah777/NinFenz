---
name: 🐛 缺陷上报
about: 提交缺陷帮助改进 NinFenz
title: '[BUG] '
labels: bug
assignees: ''
---

> ⚠️ **安全问题（漏洞 / 越权 / 凭据泄露）不要开公开 Issue**：请走 [SECURITY.md](SECURITY.md) 的私密通道（仓库页 → Security → Report a vulnerability）。公开 Issue 会触发云端代收站自动入库。

## 缺陷描述
（发生了什么？期望什么？实际什么？）

## 影响与等级
- [ ] 阻塞（无法继续使用 / 产物损坏）
- [ ] 严重（主流程可走，但结果错误）
- [ ] 一般（有绕行办法）

复现稳定性：每次都复现 / 偶发（__/__ 次）

## 复现步骤
1.
2.
3.

- 最小复现：一条命令 + 期望 + 实得（最小可复现片段，不要贴整仓）

## 期望行为

## 实际行为

## 环境信息
- 形态：CLI（scripts/nf.py）｜协议内容（模块/管线/资产/community 包）｜文档/质量门禁（verify.sh）｜其他（桌面 GUI 端壳已于 2026-09-09 退役移出）
- 系统版本：
- Python 版本（要求 ≥3.11）：
- `nf --version` / 版本（verify 基线 / tag）：
- 基线 commit / tag：
- `nf doctor` 输出：

## 日志
> CLI 侧附终端报错输出；协议/内容问题附相关文件路径与 check 输出。
> **粘贴前先脱敏**：token / 密钥 / 私密路径一律替换为 `***`——出现在公开 Issue 的凭据按已泄露处理（SECURITY.md §四）。

## 补充
（截图 / 相关文件）
