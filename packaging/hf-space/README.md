---
title: NinFenz Contract Gate
emoji: 🧾
colorFrom: indigo
colorTo: green
sdk: docker
app_port: 7860
pinned: false
license: mit
short_description: Run real NinFenz read-only gates in the browser
---

# NinFenz · Contract Gate（在线 demo / S1 入口）

**NinFenz（NF）是内容契约层（content contract layer）**：把「AI 稳定产出长内容」变成可装载、可质检、可复现的工程。本 Space 让你**在浏览器里跑真实的 NF 只读门禁**——不是模拟，是同源 CLI。

## 能做什么

| 模式 | 跑的其实是 | 回答的问题 |
|---|---|---|
| 文档语义体检 | `nf lint <你的文本>` | 这段内容过不过仓库的文档判据 |
| 自述数字核对 | `nf stats --check` | README / llms.txt 里的数字与实算是否一致 |
| 契约一致性 | `nf conformance` | 协议件与 registry 是否自洽 |
| 只读体检 | `nf doctor` | 仓库级 17 项只读体检 |

## 实现纪律

- **零第三方 Python 依赖**：一个 `http.server` 服务 + 仓库原样 CLI，容器里没有 pip install。
- **只读白名单**：服务端只接受上面四条命令，命令以 argv 列表调用（无 shell），输入上限 200 KB、超时 180 s。
- **不写仓库**：`lint` 模式只往临时文件写，跑完即删。

## 本地复现（与 Space 同源）

```bash
npm i -g ninfenz
ninfenz doctor                                    # 17 项只读体检

# 完整 check 门禁需要真实检出（verify.sh 依赖 .git / .github / results；check 数以 `nf stats` 生成区为准）
git clone https://github.com/Monyeah777/NinFenz && cd NinFenz && bash verify.sh
```

## 链接

- 仓库（canonical）：https://github.com/Monyeah777/NinFenz
- 机器入口 `llms.txt`：https://raw.githubusercontent.com/Monyeah777/NinFenz/main/llms.txt
- 许可：MIT


> **复核（2026-11-14）**：四模式白名单、只读纪律与复现口径**复核不变**；补「§现状对照」把 Space 的入口参数、限额、镜像钉版与 `nf doctor` 实测条数写清（此前只写「17 项」却无处可核）。

## 现状对照（2026-11-14 · 以 `server.py` / `Dockerfile` / `nf doctor` 实读为准）

| 面 | 现值 | 复核方式 |
|---|---|---|
| 白名单模式 | **4**：`lint` / `stats --check` / `conformance` / `doctor` | `server.py` 的 `MODES` |
| 输入上限 | **200 KB**（`MAX_INPUT = 200_000`） | 同上 |
| 超时上限 | **180 s**（`TIMEOUT_S`） | 同上 |
| 服务实现 | 纯 stdlib `http.server`（**零 pip**） | `server.py` 头部与 `Dockerfile` |
| 端口 | **7860**（`EXPOSE 7860` + `app_port: 7860` + `CMD ["python", "server.py"]`） | `Dockerfile` / 本文 frontmatter |
| 镜像基座 | 两段均按 `@sha256` 钉版（`node:22-slim` 装载 + `python:3.12-slim` 运行） | `Dockerfile` 的 `FROM` 行 |
| 装载前提 | 需要 `NF_ROOT`（跑 `tools/stage-space.mjs` 生成 `nf/`）；缺树时退出码 **3** 并给修复指引 | `server.py` 的 `run_mode` |
| `nf doctor` | **17/17 通过**（本文原写的「17 项」本轮实测复核） | `python scripts/nf.py doctor` |

> 本表只作「当时 → 现行」导航；限额与模式以 `server.py` 实读为准。

## 复现与引用口径

```bash
python scripts/nf.py doctor                     # 17/17（Space 的 doctor 模式跑同一条命令）
cd packaging/hf-space && node tools/stage-space.mjs   # 装载 NF 树到 nf/（Space 构建同源）
cd packaging/hf-space && python server.py            # 本地起同源服务（默认 127.0.0.1，见启动日志）
```

- 引用本 Space 时：「浏览器里跑的是**同源 CLI**，不是模拟」——四模式逐条对应仓库真命令。
- 它**只读**：不写仓库、不接受任意子命令；`lint` 模式只往临时文件写、跑完即删。
