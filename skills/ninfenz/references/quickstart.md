# NinFenz 快速开始

## 环境前提（先自检）

- **Python ≥ 3.11**（`pyproject.toml` 的 `requires-python = ">=3.11"`）；`python --version` 确认。
- **Git**（克隆仓库）；**Bash**（跑 `verify.sh` 需要 Git Bash / WSL / macOS / Linux 终端）。
- 期望输出：`python scripts/nf.py --version` → `nf <版本>`（版本以实跑为准，不锁定本文数字）。

## 安装本 skill

本 skill 目录**自包含**（`skills/ninfenz/` = `SKILL.md` + `references/` 三件 + `agents/openai.yaml`），安装 = 把整个目录复制到宿主 agent 的 skills 目录：

```bash
# 先拿到仓库（或已克隆的本地仓库）
git clone https://github.com/Monyeah777/NinFenz.git

# 复制到宿主 skills 目录（按你的宿主选其一）
mkdir -p ~/.codex/skills && cp -r NinFenz/skills/ninfenz ~/.codex/skills/
# 若宿主要求 CODEX_HOME：cp -r NinFenz/skills/ninfenz "$CODEX_HOME/skills/"
# Windows PowerShell：Copy-Item -Recurse NinFenz\skills\ninfenz "$env:USERPROFILE\.codex\skills\"
```

> 没有「一键安装脚本」——技能安装方是宿主 agent 的 skills 目录约定；本仓库只提供自包含目录（旧版本文档里的 `install-skill-from-github.py` 并不存在，勿照抄）。

## 准备仓库

```bash
git clone https://github.com/Monyeah777/NinFenz.git
cd NinFenz
python scripts/nf.py --version
python scripts/nf.py doctor
```

需要完整验收门禁时，用支持 Bash 的终端执行：

```bash
bash verify.sh
```

## 最快跑通（三步自检）

```bash
python scripts/nf.py --version     # 版本面
python scripts/nf.py doctor        # 环境体检
python scripts/nf.py demo          # 最小演示（装配 → 渲染）

python scripts/nf.py market --list # 市场清单（模块/管线/资产包）
python scripts/nf.py asset ls      # 资产键表
python scripts/nf.py module ls     # 模块清单
python scripts/nf.py worldmodel --walk  # 世界模型步进
```

任一步报错先看 `nf doctor` 的诊断；`doctor` 通过但仍失败 → 按报错给出的修复指引处理（多为路径/依赖/终端问题）。

## 不克隆仓库的 AI 装配路径

1. 读 `docs/agent/AGENT_START.md` 确认装配师角色。
2. 读 `docs/agent/agent_组装指令包_v0.2.md` 获取取货顺序、选件铁律、八段骨架、`##7` 自检。
3. 从仓库 **raw 直链**读取协议层四件（`01_核心协议.md` / `02_联动注册表.md` / `06_Agent执行协议.md` / `07_官方核心出厂与社区预设导航.md`）与 `community/*` 所需包：
   `https://raw.githubusercontent.com/Monyeah777/NinFenz/main/<路径>`（国内镜像 `https://gitee.com/monyeah777/ninfenz/raw/main/<路径>`）——实测 AI 抓 raw 直链可靠，抓仓库主页 HTML 不可靠。
4. 交付单文件完整版 `.md`，并明确来源与缺口。

如无法访问文件，不要假装抓取；向用户要缺失原文或如实标注缺口。

## 接下来读什么

- `skills/ninfenz/SKILL.md` —— 技能总览与快速选路（入口/命令/红线）。
- `skills/ninfenz/references/assembly.md` —— 装配六步与三真源（骨架/编号/验收）。
- `skills/ninfenz/references/commands.md` —— 命令族速查（含 map 到 CLI 的退出码语义）。
