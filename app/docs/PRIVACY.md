# NF APP 隐私说明（数据地图 / 保留与删除 / 分享脱敏 / Play 数据安全口径）

> ⛔ 操作指令：本件是 APP 的**数据事实与处理口径**，不是合规声明、不是法律意见（法律面见 `app/docs/LEGAL.md`）。每条「数据在哪里」必须能指到落点或写 `OPEN` + owner；`planned` 不得写成「已实现」。改本件必须同步 `app/docs/THREAT_MODEL.md`（B-01/B-02/B-05）与 `app/docs/CONTRACT.md` §6。
> 状态：v1（2026-11-15）· 性质：数据地图 + 处理口径 · 取证时刻：2026-11-15 15:5x。
> 依据：`app/docs/CONTRACT.md` §6（隐私纪律：本地处理、无遥测、无账号、诊断只落本地、分享前预览+脱敏）、`app/schema/ccos-task.schema.json`（`policy.secrets=ccos-only`）、`app/cli/nf_app/security.py`（脱敏实现）。

## 1. 一句话口径

NF APP **在本地处理用户内容，不建账号、不做遥测、不主动联网**；用户内容离开设备的唯一通道是**用户主动发起的分享/导出**与**用户主动交给 CCOS 的任务文件**；诊断只落本地目录；APP 自身不持有任何模型凭据（密钥只在 CCOS）。

现状取证（本机实测 2026-11-15）：`grep -rnE "import (socket|http|urllib|requests)..." app/cli app/core/src` → **0 命中**（`NO_NETWORK_IMPORTS`）；`grep -rniE "telemetry|analytics|crashlytics|firebase|amplitude|sentry" app/cli app/core/src app/schema` → **0 命中**。端壳（`app/android`/`app/desktop`）未建 → 端壳侧证据 `OPEN-PRIVACY-02`。

## 2. 数据地图（类别 × 落点 × 是否离开设备）

| # | 数据类别 | 内容 | 产生/落点（设计口径） | 是否离开设备 | 依据 | 状态 |
|---|---|---|---|---|---|---|
| D-01 | 项目文件 | `project.nfproject.json`（引用 id/version/digest、状态机、评审、history） | 应用数据目录 `projects/<id>/`（`app/docs/ARCHITECTURE.md` §7.1） | 否（除用户主动导出） | `app/schema/nf-project.schema.json` | planned（数据目录未建） |
| D-02 | 作者内容 | 导入原文、映射结果、槽位输入、装配产物 | `projects/<id>/` 与应用数据目录 | 否（除导出/分享/CCOS） | `app/schema/nf-import.schema.json`、`nf-assembly-plan.schema.json` | planned |
| D-03 | Pack / 模板 | 只读内容层（含 template 内嵌快照） | `library/packs/<id>/<version>/` | 否 | `app/schema/nf-pack.schema.json`、`nf-template.schema.json` | planned |
| D-04 | 用户覆盖层 | 条款开关/参数/预设/自定义资产 | `overlay/<project-id>/` | 否 | `app/schema/nf-overlay.schema.json` | planned |
| D-05 | 备份 | 更新前 base/项目快照（本地指针可带时间戳） | `backups/<timestamp>/` | 否 | `app/docs/CONTRACT.md` §5.9 | planned |
| D-06 | 分享缓存 | 为系统分享生成的临时文件/只读 URI | `cache/share/` | **是**（用户主动分享并经系统分享面板） | `app/docs/CONTRACT.md` §6 | planned（端壳未建） |
| D-07 | 剪贴板 | 用户复制的分享文本；回填时读取 | 系统剪贴板 | **是**（剪贴板是系统共享面，其它应用可读；APP 无法观测） | ADR-APP-008；`app/docs/THREAT_MODEL.md` TH-11/TH-12 | partial |
| D-08 | 导出产物 | md/zip/json 与 `nf-export-manifest/1` | `exports/`（用户可见目录） | **是**（用户主动导出到所选位置） | `app/docs/CONTRACT.md` §5.8（导出形态与 manifest 口径） | planned |
| D-09 | 诊断日志 | 本地错误/运行诊断（不含内容正文为原则） | `diagnostics/` | 否（无出站） | `app/docs/CONTRACT.md` §6；`app/docs/ARCHITECTURE.md` §8 | planned |
| D-10 | CCOS 任务/结果 | `ccos-task/1` / `ccos-result/1`（含项目内容引用、约束、验收、预算） | `ccos/outbox\\|inbox/` | **是**（用户主动交给外部执行面） | `app/schema/ccos-task.schema.json`、`ccos-result.schema.json` | planned |
| D-11 | 账号/身份 | **无**（不注册、不登录、无 user id） | — | — | `app/docs/CONTRACT.md` §6；`app/README.md` | enforced（无账号代码：无登录/令牌/用户表） |
| D-12 | 设备标识/广告 ID | **无**（不读取、不上报） | — | — | 同上 | enforced（无相关代码；本机 grep 取证） |
| D-13 | 位置/通讯录/相机/麦克风 | **无**（未申请、未使用） | — | — | 端壳未建，权限清单待落地核验 | OPEN-PRIVACY-02 |
| D-14 | 崩溃/统计上报 | **无**（不设计崩溃上报；诊断只落本地） | — | — | `app/docs/ARCHITECTURE.md` §8（C-05） | partial（无上报实现；端壳落地后需核验无第三方 SDK） |

**边界说明**：如果未来引入任何出站能力（在线 CCOS 桥、云同步、崩溃上报），必须先改本件 + `THREAT_MODEL.md` + `CONTRACT.md` §6，并给用户显式开关；不得以「匿名统计」名义默认开启。

## 3. 无遥测 / 无账号（可核口径）

| 承诺 | 判据 | 状态 |
|---|---|---|
| 无第三方分析/崩溃 SDK | 端壳依赖清单里不得出现 analytics/crash 类库（当前端壳未建 → 清单待出）；控制面/核心：本机 grep 0 命中 | partial |
| 无出站网络调用 | 控制面/核心：`grep -rnE "import (socket\\|http\\|urllib\\|requests)\\|from (http\\|urllib\\|requests)" app/cli app/core/src` → 无命中（本机实测） | enforced（控制面/核心） |
| 无账号/无登录 | 无登录 UI、无令牌存储、无用户表（当前无相关代码） | enforced（现状） |
| 无遥测默认开 | 无开关可开（没有遥测代码） | enforced（现状） |
| 端壳无隐藏上报 | 需端壳工程 + 依赖审计 | OPEN-PRIVACY-02（owner kotlin-ui） |

## 4. 保留与删除

| 项 | 保留策略 | 删除方式 | 状态 |
|---|---|---|---|
| 项目/作者内容/overlay | 保留在用户磁盘，直到用户删除；APP 不自动清理用户内容、不设云端保留 | 用户删除项目目录（端壳提供删除入口；当前未建） | planned |
| Pack / template | 同 id 多版本并存；不自动删除旧版（回滚需要） | 用户在 Pack 管理里删除；`latest` 指针单独维护 | planned |
| 备份 | 仅保留回滚窗口内需要的备份；窗口长度待定 | 按窗口清理或用户手动清理 | OPEN-DATADIR（owner lead） |
| 分享缓存 | 临时；分享结束或下次启动清理（端壳实现） | 清理缓存目录 | planned |
| 诊断日志 | 本地；按大小/时间轮转（策略待定） | 用户删除或轮转覆盖 | OPEN-DATADIR |
| 导出产物 | 用户可见目录，保留不自动删 | 用户自行删除 | planned |
| CCOS 交接文件 | 由用户/外部流程管理（APP 不代删对方目录） | 用户或 CCOS 侧删除 | planned |

**卸载行为**：Android 卸载默认清理应用私有目录（含 `projects/`、`library/`、`backups/`、`cache/`）；用户导出到公共目录的文件**不会**被卸载删除（设计口径，端壳落地后核验）。桌面卸载同理（安装器行为待核）。

**删除请求**：APP 无账号、无服务器侧数据 → 不存在「账号数据删除」流程；用户删除 = 删除本地文件（可自行核验，无需等待处理时限）。

## 5. 分享脱敏规则（具体模式 × 替换 × 实现）

分享/导出前的强制流水线：**脱敏 → 预览 → 分享**；脱敏后仍命中敏感模式 → 拒发（`NF-E-002`，fail-closed）。

| # | 模式 | 示例形态 | 替换为 | 实现位置 |
|---|---|---|---|---|
| R-01 | 仓库根路径（已知 repo 路径） | 本仓绝对路径 | `<repo>` | `app/cli/nf_app/security.py`（`sanitize_text` 的 `repo_paths` 分支） |
| R-02 | 邮箱 | `name@example.com` 形态 | `<email>` | 同上（`_EMAIL_RE`） |
| R-03 | Windows 家目录 | 盘符 + Users 段路径 | `<home>` | 同上（`_WIN_HOME_RE`） |
| R-04 | Windows 盘符路径 | 盘符 + 路径段 | `<path>` | 同上（`_WIN_PATH_RE`） |
| R-05 | NIX 家目录 | home/Users 前缀路径 | `<home>` | 同上（`_NIX_HOME_RE`） |
| R-06 | NIX 绝对路径 | 多段绝对路径 | `<path>` | 同上（`_NIX_PATH_RE`） |
| R-07 | 云厂密钥 | AWS `AKIA…` 形态 | `<secret>` | 同上（`SECRET_PATTERNS`） |
| R-08 | 模型 API 密钥 | `sk-…` 形态 | `<secret>` | 同上 |
| R-09 | 代码托管令牌 | `ghp_`/`gho_`/`ghu_`/`ghs_`/`ghr_` 形态 | `<secret>` | 同上 |
| R-10 | 聊天平台令牌 | `xox[baprs]-…` 形态 | `<secret>` | 同上 |
| R-11 | 私钥块 | `BEGIN … PRIVATE KEY` | `<secret>` | 同上 |
| R-12 | Bearer 令牌 | `bearer …` 形态 | `<secret>` | 同上 |

拒发闸门：`assert_share_safe`（`security.py:392`）——脱敏后仍命中邮箱或密钥形状 → 抛 `NF-E-002`，提示「手动删除或改用脱敏文本」。

**已知缺口（如实登记）**：

- 裸用户名（不带路径，如正文里只写用户名）**不被识别** → `OPEN-PRIVACY-01`。
- 掩码记录（`masks[]`）已产生，但「预览界面展示掩码」属端壳，未建 → partial。
- 第三方应用收到分享内容后的二次传播不可观测（`THREAT_MODEL.md` TH-19）→ 只能靠脱敏前置 + 预览。

## 6. Play 数据安全（Data safety）声明口径

本机**无法提交** Play Console 表单（无开发者账号/无 Android 构建）→ 整节 `OPEN-PRIVACY-03`，下面只给**拟申报口径草稿**，提交前必须与实现逐条核对。

| Play 表单问题 | 拟申报 | 依据 | 提交前核对点 |
|---|---|---|---|
| 是否收集或共享用户数据 | 不收集、不共享（APP 无服务器） | 本件 §2/§3 | 端壳无第三方 SDK/分析库 |
| 传输中加密 | 不适用（APP 无网络传输） | §3 | 端壳无出站 |
| 数据删除请求 | 不适用（无账号/无服务器数据） | §4 | 删除入口可用性 |
| 位置/个人信息/财务/健康/消息/照片/文件 | 均不收集（文件由用户主动导入/导出） | §2 | 权限清单（端壳） |
| 用户主动分享/交给 CCOS 的内容 | 属「用户发起的内容传输」，不是 APP 收集；若表单要求申报，按实际形态说明 | §2 D-06/D-08/D-10 | 分享/CCOS 是否含设备标识（设计：否） |

> 口径纪律：Play 表单的「不收集」必须能被端壳依赖清单与网络调用审查证明；端壳未建前，本表**不得**作为已提交材料引用。

## 7. 与 CCOS 的数据边界

- APP 生成 `ccos-task/1` 时扫描并拒绝密钥/绝对路径/本机用户名（`NF-CCOS-003`，exit 3）；任务只声明 `policy.secrets=ccos-only`，不携带任何凭据。
- CCOS 回传 `ccos-result/1` 进入 APP 后，`human_review.required` 恒 true：内容进项目前必须人工确认。
- APP 不保存 CCOS 的密钥、会话、账号；CCOS 侧数据处理（模型供应商、日志、保留）不在本件范围，由 CCOS 侧声明。

## 8. OPEN 登记

| id | 内容 | owner | 下一步 |
|---|---|---|---|
| OPEN-PRIVACY-01 | 裸用户名不脱敏 | lead | 在 `security.py` 增加用户名探测 + 误伤评估 + 负例 |
| OPEN-PRIVACY-02 | 端壳侧隐私证据缺失（权限清单、第三方 SDK、无出站网络） | kotlin-ui | 端壳落地后出依赖清单 + 权限清单，进 `app/docs/DEPENDENCIES.md` 与 QA5 |
| OPEN-PRIVACY-03 | Play 数据安全表单无法提交（无账号/无构建） | lead | 有 Console 账号后按 §6 草稿逐条核对提交 |
| OPEN-DATADIR | 备份/诊断/分享缓存的保留窗口与清理实现未定 | lead | 端壳数据目录落地时定上限与清理策略，写回本件 §4 |

## 9. 取证命令（本件判据）

```bash
# 控制面/核心无网络调用（期望无输出）
grep -rnE "import (socket|http|urllib|requests)|from (http|urllib|requests)" app/cli app/core/src || echo NO_NETWORK_IMPORTS
# 无遥测/分析 SDK 标记（期望无输出）
grep -rniE "telemetry|analytics|crashlytics|firebase|amplitude|sentry" app/cli app/core/src app/schema || echo NO_TELEMETRY_MARKERS
# 脱敏与拒发判据
PYTHONDONTWRITEBYTECODE=1 python -m pytest app/tests/test_security_negative.py -q -p no:cacheprovider
```

> 本件不是隐私政策正文，也不构成法律合规意见；对外发布用的隐私政策需由发布方在律师/合规审核后单独出具（见 `app/docs/LEGAL.md`）。

