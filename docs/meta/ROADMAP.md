# Roadmap

> 结果导向的路标：只给版本节奏、当前状态与治理边界；分波过程与计划已内部归档。
> **最后更新：2026-11-13（复核）**：三条现状 / 版本真源 / 三条长期路标 / 治理边界**复核不变**；
> 补可核锚：版本三处一致（`pyproject.toml` = `packaging/npm/package.json` = `protocol/mcp_package.json`，本轮实读 **1.0.5**）；
> 门禁基线在 `protocol/repo_stats.json`（`baseline_checks` / `baseline_pass`），由 `nf stats --check` 断言；
> 端壳零回潮由 **check39** 判（`verify.sh` 内，含 `nf shell` 终端入口在场）。见「§现状对照」。

## 当前状态

- 公开基础层：`bash verify.sh` 单入口；当前基线（版本/check 数/PASS）见 README 生成区与 `protocol/repo_stats.json`（由 `nf stats --check` 断言），不在此处手写。
- 端壳层退役：L3 桌面 GUI 端壳与打包线已永久退役移出（2026-09-09，同 APK 裁决 #16 轨）；公开面 = 协议 + core 库 + CLI，不产桌面壳。端壳退役后的人机入口 = **终端**（`nf shell`，见 `docs/terminal.md`），GUI 回潮由 verify check39 判红。
- 外部实测：封存挂账，由作者决定一次性补测。

## 现状对照（2026-11-13 · 以实读为准）

| 面 | 现值 / 来源 | 复核方式 |
|---|---|---|
| 版本 | 三处一致（pyproject / npm / mcp_package） | 三个文件实读比对（本轮 **1.0.5**） |
| 门禁基线 | `protocol/repo_stats.json` 的 `baseline_checks` / `baseline_pass` | `nf stats --check` |
| 端壳退役 | **check39**（终壳零回潮 + shell 入口在场 + 菜单无死命令 + 输出确定） | `bash verify.sh` 的 check39 |
| 退役记录 | `docs/L3_FROZEN.md` 在盘 | 文件存在 |
| 人机入口 | `nf shell`（`docs/terminal.md`） | `nf shell --help` / 文档 |
| 外部实测 | 封存挂账，作者决定一次性补测 | 不在本仓门禁内 |

> 本表只作「当时 → 现行」导航；版本与基线数字**不在本文件手写**——「**不手写**」是本文纪律（防漂移）。

## 复现与引用口径

```bash
python scripts/nf.py stats --check   # 自述数字 == 实算（含入口一致性）
bash verify.sh --checks-only         # 含 check39（端壳零回潮）
```

- 引用本文时：「只写方向/状态/边界，不写计划流水」= 长期口径；版本与基线以真源实读为准。
- 端壳线不预设恢复：新端壳形态须作者新裁决后另行立项（退役记录 `docs/L3_FROZEN.md`）。

## 版本真源

当前版本、check 数与 PASS 数不在本文件手写复制：发行版本以 `pyproject.toml` 为入口，并与 npm、MCP 元数据对账；协议门禁版本、check 数与 PASS 数见 `protocol/repo_stats.json`，由 `nf stats --check` 断言。历史版本与结果摘要见 `CHANGELOG.md`。

## 长期路标

1. 继续把内容契约层做成可机检、可执行、模型无关的标准。
2. 以质量唯一论收敛功能；外部工具/链接仅作候选建议，不作背书。
3. 等待真实用户实测后，一次性补测外部互操作证据。

## 治理边界

- 计划、草案、工作日志留本地；公开仓库只承载方向、结果/状态、正式协议与代码。
- 门禁绿是提交前提，不是质量顶尖的宣称。
- 端壳线不预设恢复；新端壳形态须作者新裁决后另行立项（退役记录见 docs/L3_FROZEN.md）。
