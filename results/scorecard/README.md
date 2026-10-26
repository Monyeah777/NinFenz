# OpenSSF Scorecard 证据

状态：**配置已就绪**。

`.github/workflows/scorecard.yml` 在每次真实运行时保留 `results.sarif`、可追溯摘要
`scorecard-summary.json` 和上传工件。摘要记录提交、run id、工作流 URL、SARIF 结果数与
SHA-256，避免把运行时刻分数写进静态门禁基线。

本目录不预置未经运行的分数或伪造快照。发版负责人可按需归档某次运行摘要；在提供具体
commit、run id、日期、SARIF 摘要的**平台启用证据**前，不宣称 Allstar 或 Scorecard
已由外部平台持续执行。

