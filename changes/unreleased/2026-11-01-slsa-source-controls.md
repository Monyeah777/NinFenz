### SLSA Source Track 技术控制

- 为 `main` 验证管理员强制保护、linear history、必需状态检查、禁强推和禁删除。
- 为 `refs/tags/v*` 启用禁删除、禁移动、禁强推的 active Ruleset。
- 新增 Source readiness 与 GitHub 控制快照；GitHub 未提供 Source VSA/provenance，
  因此继续声明 Source Level 0，不伪造 Source L2/L3。
