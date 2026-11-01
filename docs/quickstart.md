# 五分钟可复现入口（quickstart）

这条路径面向**刚 clone 完的干净检出**：从仓库根出发，6 步，只用本仓文件与 Python 标准库（`pip install` 不是前置）。下面每条命令都在仓库根目录复制粘贴即可，按 1→6 顺序执行，不需要先读别的文档。

环境：Linux / macOS / Windows Git Bash；Python ≥ 3.10。若系统里解释器命令是 `python3`，把命令里的 `python` 换成 `python3`。

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

## 判据挂载

`bash verify.sh` 的 check39（终端与命令面门禁）会执行 `bash scripts/quickstart_check.sh`。本文、脚本、命令面任一侧改坏（增删步、换步号、写错子命令、命令跑不通），check39 立刻 FAIL；步数对齐由 `NF_QUICKSTART_DOC_STEPS` 与 `NF_QUICKSTART_SCRIPT_STEPS` 两个值直接给出，不需要人工数。
