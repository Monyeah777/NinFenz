# 文档命令与数字抽查（DC-08）

> 抽查面：入口文档 `README.md` / `AGENTS.md` / `llms.txt` / `docs/quickstart.md`。
> 判据：命令能否被外部人直接复制执行；数字是否有来源或标注为估算。

## 命令抽查（5 条）

| 文档 | 命令 | 能否直接执行 | 缺少的前置/上下文 |
|---|---|---|---|
| README | `python scripts/nf.py --version` | 能 | 需在仓库根目录、Python >= 3.11 |
| README | `bash verify.sh` | 能 | 需在仓库根；默认 quick 档，发布结论用 `--full` |
| README | `python tui/nf.py` | 能 | 需要交互终端（无 TTY 用 `--list-actions --json`） |
| AGENTS.md | `bash verify.sh --full --no-cache` | 能 | 全量数分钟；需 cold-start 前置（dotnet/cargo 产物） |
| llms.txt | `python scripts/nf.py doctor` | 能 | 只读体检；退出码 0 表示通过 |

## 数字抽查（5 个）

| 数字 | 出处 | 来源类型 |
|---|---|---|
| check 数与 PASS 计数 | `verify.sh` 运行结果 | 实测（每次重算，不在文档写死） |
| 社区资产行数（校园 1575 / 西幻 4284） | `02_联动注册表.md` + verify 段 B 对账 | 实测（门禁对账） |
| 版本号 1.0.x / 0.xx | `docs/meta/VERSION-MATRIX.md` | 发布真源 |
| 仓库体积 / pack 体积 | `git count-objects -vH` | 实测（HS-03） |
| Scorecard 分数 | 平台页面 | 外部平台评分（不作为质量证明） |

## 处置

- 上表 5 条命令本轮抽检可直接执行。
- 无法溯源的数字已降级为定性表述或标注估算；抽查范围内未发现以确定语气写出的无源数字（历史 CHANGELOG 不受本判据约束）。