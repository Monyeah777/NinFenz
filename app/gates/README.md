# app/gates —— APP 门禁（QA0–QA6 + S0–S15 自审计）

> ⛔ 操作指令：本目录是 APP 侧**唯一机检入口**。判据登记在 `gates.json`（只增不减），自审计维度在 `dimensions.json`（S0–S15），运行证据落 `app/results/{GATES,SELF_AUDIT}.json` 与 `app/results/logs/`。改判据前先读 `app/docs/QA_PLAN.md` 与 `app/docs/DOD.md`。

## 判定模型

| 状态 | 含义 |
|---|---|
| `PASS` | check 通过（required 或 optional 均记 PASS） |
| `FAIL` | required check 失败/缺件 → 计入 **P0**，本轮不得宣称收口 |
| `OPEN` | 未完成的 optional check → 必须带 `owner` + `next`，计入 P1；**不得写成 PASS** |

- 自审计维度状态：`covered`（有可复跑证据）/ `gap`（有 owner+next 的缺口）/ `open`（外部不可执行，带 owner+next）。
- `p0` = FAIL + 无 owner/next 的缺口；`p1` = 带 owner/next 的 gap + open。
- 停止条件（计划 §15.3）：`FAIL=0`、`P0=0`、`UNSUPPORTED=0`（即全部 OPEN 带 owner+next）、连续两轮。

## 复跑

```bash
python app/gates/run_gates.py                  # 全量（QA0–QA6 + S0–S15），写 app/results/
python app/gates/run_gates.py --only QA0 QA2   # 单门
python app/gates/run_gates.py --json           # 机器面摘要（ok/p0/p1/gates/head）
```

退出码：0 = P0=0；1 = 有 FAIL；2 = 用法/IO。

## check 类型

| kind | 语义 |
|---|---|
| `files` | 路径必须存在（目录/文件） |
| `glob_min` | glob 命中数 ≥ min |
| `glob_json` | 命中的文件全部可解析为 JSON，且数量 ≥ min |
| `cmd` | 子命令，按 `exit` 期望判定（stdout/stderr 落 logs） |
| `func` | `run_gates.py` 内置断言（`check_encoding` / `check_no_machine_paths` 等） |

## 纪律

- 新 check 必须给 `id`（`q<gate>-<slug>`）与 `title`；不得删除既有 id（改口径 = 新增 id + 旧 id 标记 retired 并说明）。
- 命令型 check 不得取网、不得写用户数据目录；允许写 `app/core/target`（构建产物，gitignored）与 `app/results/logs/`。
- 证据日志是**追加式**：每次运行覆盖同名日志，但文件名含 argv，便于溯源。
- 本门禁与仓库 `verify.sh` 的关系：APP 是新增面，`verify.sh` check1–57 不动；若将来接入，新增 `check58` 只调本入口（见 `app/docs/QA_PLAN.md`）。
