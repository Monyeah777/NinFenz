# NF Evidence Gate（GitHub Action）

给 CI 一个**本地、离线可复算**的产物证据卡：不联网、零依赖（Python 标准库）。

```yaml
- uses: Monyeah777/NinFenz/packaging/evidence-action@main
  with:
    path: docs/mcp.md
    contract: 大语言模型      # 可选；设置后按 12 条细分做 coverage 判定
    min_rules: "12"           # 可选：要求 12 条规则全部覆盖
```

产物：`nf-evidence.json`（`nf-evidence-card/1`）。本地复算：

```bash
python scripts/evidence_cli.py verify --card nf-evidence.json
```

说明：Action 只生成卡并对 coverage 阈值判红；它不替代 `bash verify.sh`（仓库门禁真源）。
