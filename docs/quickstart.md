# 五分钟可复现入口（quickstart）

这条路径面向**刚 clone 完的干净检出**：从仓库根出发，6 步，只用本仓文件与 Python 标准库（`pip install` 不是前置）。下面每条命令都在仓库根目录复制粘贴即可，按 1→6 顺序执行，不需要先读别的文档。

环境：Linux / macOS / Windows Git Bash；**Python ≥ 3.11**（与 `pyproject.toml` 的 `requires-python` 一致；旧版本文中曾写 3.10，属笔误，本次已按真源更正）。若系统里解释器命令是 `python3`，把命令里的 `python` 换成 `python3`。

> **最后更新：2026-11-13（复核）**：6 步 / 三条机读判据 / check39 挂载**复核不变**；修一处**真漂移**（Python 版本 `≥ 3.10` → **`≥ 3.11`**，真源 `pyproject.toml: requires-python`），并补可核现状：
> 文档步 **6** == 脚本步 **6**（slug 序列 version/doctor/demo/assemble/assemble/assemble，`--audit` 静态审计即验）· 墙钟上限 **300 s** · 判据挂载于 `verify.sh` 的 **check39**。见「§现状对照」。

## 一条命令自检

```bash
bash scripts/quickstart_check.sh
```

三条判据全部机读：

- 退出码为 0；
- 脚本打印的 `NF_QUICKSTART_ELAPSED_SECONDS` ≤ `NF_QUICKSTART_MAX_SECONDS`（300 秒）；
- 脚本打印的 `NF_QUICKSTART_DOC_STEPS` == `NF_QUICKSTART_SCRIPT_STEPS`（本文步数 == 脚本步数）。

脚本先做静态审计（步号、步数、命令面三方对齐），再在系统临时目录按下面 6 步同序真跑，最后核对墙钟；结束时固定打印 `NF_QUICKSTART_OK=1` 或 `NF_QUICKSTART_OK=0`。手工复跑用下面的 `.nf-quickstart/` 目录，脚本用临时目录，两者都不写仓库受跟踪文件。

## 6 步（逐条复制粘贴）

### 步骤 1 · 版本

<!-- nf-step: 1 version -->

```bash
python scripts/nf.py --version
```

终端打印一行 `nf` 版本号，退出码 0。

### 步骤 2 · 仓库自检

<!-- nf-step: 2 doctor -->

```bash
python scripts/nf.py doctor
```

打印 `体检：N/N 通过`，退出码 0。出现 `[FAIL]` 行就停在这里，不要继续下一步。

### 步骤 3 · 一键演示世界

<!-- nf-step: 3 demo -->

```bash
python scripts/nf.py demo
```

打印 `质量门：` 且其中 `FAIL 0`，退出码 0；产物落在系统临时目录。

### 步骤 4 · 需求 → 完整版（第一份）

<!-- nf-step: 4 assemble -->

```bash
python scripts/nf.py assemble "写一份关于雨天的校园短篇" --build --dest .nf-quickstart/out1
```

退出码 0；产出 `.nf-quickstart/out1/完整版_校园情感领域包.md`。

### 步骤 5 · 同一需求再产一份并逐字节比对

<!-- nf-step: 5 reproducible -->

```bash
python scripts/nf.py assemble "写一份关于雨天的校园短篇" --build --dest .nf-quickstart/out2
cmp .nf-quickstart/out1/完整版_校园情感领域包.md .nf-quickstart/out2/完整版_校园情感领域包.md
```

第一条命令退出码 0；第二条 `cmp` 也退出码 0（两份产物逐字节相同）——同一需求可复现。

### 步骤 6 · 对产物做机器验收

<!-- nf-step: 6 check -->

```bash
python scripts/nf.py assemble "写一份关于雨天的校园短篇" --check .nf-quickstart/out1/完整版_校园情感领域包.md
```

打印 `✓ 成品通过自组装机器验收`，退出码 0。

收尾：`rm -rf .nf-quickstart`。

## 现状对照（2026-11-13 · 以 `--audit` 实读为准）

| 面 | 现值 | 复核方式 |
|---|---|---|
| 文档步数 | **6** | 本页每步上方的 nf-step 注释行 |
| 脚本步数 | **6** | `scripts/quickstart_check.sh` 的 `# nf-step: N slug` |
| slug 序列 | version → doctor → demo → assemble ×3 | `bash scripts/quickstart_check.sh --audit` |
| 墙钟上限 | **300 s**（`NF_QUICKSTART_MAX_SECONDS`） | 脚本常量 / 实测输出 |
| Python 要求 | **≥ 3.11** | `pyproject.toml: requires-python` |
| 判据挂载 | `verify.sh` 的 **check39** | `bash verify.sh` |

> 本表只作「当时 → 现行」导航；步数对齐以 `--audit` 输出为准（`NF_QUICKSTART_DOC_STEPS` / `NF_QUICKSTART_SCRIPT_STEPS`）。

## 复现与引用口径

```bash
bash scripts/quickstart_check.sh --audit   # 只做静态审计（步号/步数/命令面三方对齐）
bash scripts/quickstart_check.sh           # 完整跑 6 步 + 核对墙钟（末行 NF_QUICKSTART_OK）
```

- 引用本文时：「文档 ↔ 脚本 ↔ 命令面三方对齐，只改一边即红」= 长期口径。
- 增删步骤必须**同时**改本页注释与脚本 `# nf-step:` 行，否则 check39 立刻 FAIL；不要靠人眼数。

## 判据挂载

`bash verify.sh` 的 check39（终端与命令面门禁）会执行 `bash scripts/quickstart_check.sh`。本文、脚本、命令面任一侧改坏（增删步、换步号、写错子命令、命令跑不通），check39 立刻 FAIL；步数对齐由 `NF_QUICKSTART_DOC_STEPS` 与 `NF_QUICKSTART_SCRIPT_STEPS` 两个值直接给出，不需要人工数。
