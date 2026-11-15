# ADR-APP-010：Apple Silicon 优先；Windows x64 先发

| 项 | 值 |
|---|---|
| 编号 | ADR-APP-010 |
| 状态 | accepted |
| 日期 | 2026-11-15 |
| 范围 | NF APP（Android / Desktop / 平板控制面 + 共享核心） |
| 上位 | `STRATEGY.md` → `app/docs/CONTRACT.md`（A0 冻结）/ `app/docs/CLI.md` |

## 背景

桌面发行需要决定首批架构与签名/公证投入。macOS 上 arm64 已是主流硬件；Intel Mac 用户下降；Universal 二进制会放大体积与公证成本。Windows 侧 x64 覆盖绝大多数用户，arm64 仍在爬坡。签名/公证只在对应平台可执行，本机（Windows）无法完成 macOS 公证。

## 决策

1. macOS 首发 arm64（macOS 13+）；Intel 单独评估后置，不阻塞首发。
2. Windows 以 x64（Windows 10/11）先发；Windows 11 arm64 进评估清单，不承诺首版。
3. 签名/公证按平台分别要求：Windows Authenticode（MSIX 优先）、macOS Developer ID + Hardened Runtime + notarytool + staple；证据模板见 RELEASE_EVIDENCE。
4. 本机非 macOS/无证书 → 签名与公证一律 `OPEN-EXTERNAL`，不得声称「已签/已公证」。

## 后果

**正面**

- 覆盖主流硬件，构建/公证链路最简单。
- 避免 Universal 二进制的体积与双架构公证成本。
- 把「不可执行的外部条件」显式挂账，避免假发布结论。

**负面 / 代价**

- Intel Mac 用户需要 Rosetta 或等后续版本。
- Windows arm64 不在首批，覆盖不完整。
- macOS 证据只能由外部 macOS 环境产生，交付链有外部依赖。

## 替代方案（及否决理由）

| 方案 | 结论 | 理由 |
|---|---|---|
| A. Universal（x64+arm64） | 否决 | 体积与公证成本翻倍；首发无必要 |
| B. Intel 优先 | 否决 | 与硬件分布相悖 |
| C. 仅 Linux 桌面 | 否决 | 作者用户面在 Windows/macOS |
| D. 不做公证（侧载） | 否决 | macOS Gatekeeper 阻断，用户面不可用 |

## 证据落点

| 证据 | 路径 / 判据 |
|---|---|
| 发布清单 M1/M5（Apple Silicon 构建、Intel 评估） | `app/scripts/RELEASE_CHECKLIST.md` §3 |
| 签名/公证脚本与缺环境 exit 4 | `app/scripts/notarize_macos.sh`、`app/scripts/sign_windows.ps1` |
| 证据模板（现状如实） | `app/scripts/RELEASE_EVIDENCE.md` |
| 设备矩阵（Windows 10/11 x64/arm64、macOS 13+ arm64） | `app/docs/DEVICE_MATRIX.md` |
| 现状判定（签名/公证/真机不可执行） | `results/app/BASELINE.md` §0.4/§3 |

## 复审条件

- 用户硬件分布变化（Intel Mac/arm64 Windows 占比）。
- Apple/Microsoft 签名与公证政策变化时。
- 出现 Universal 的强需求（如企业分发）时。

> 本 ADR 只声明决策与边界。实现状态以 `app/docs/ARCHITECTURE.md` §5/§11、`app/results/GATES.json` 与现场复跑命令为准；未落地项写 `OPEN`，不得据本 ADR 声称「已实现」。
