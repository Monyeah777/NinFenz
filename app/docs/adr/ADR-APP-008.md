# ADR-APP-008：分享四形态 + 剪贴板回填（脱敏前置）

| 项 | 值 |
|---|---|
| 编号 | ADR-APP-008 |
| 状态 | accepted |
| 日期 | 2026-11-15 |
| 范围 | NF APP（Android / Desktop / 平板控制面 + 共享核心） |
| 上位 | `STRATEGY.md` → `app/docs/CONTRACT.md`（A0 冻结）/ `app/docs/CLI.md` |

## 背景

作者需要把成果交给读者/外部编辑器，同时不能泄露本机路径、用户名、邮箱或密钥。另需把外部内容（剪贴板/分享回的文本）重新导入为作者素材。若分享直接出原文：无法保证脱敏；若只出一种形态：交付场景不足。

## 决策

1. 分享固定四形态：① Markdown 文件 ② zip 包（含 `nf-export-manifest/1`）③ JSON（机读 manifest/产物）④ 系统分享/剪贴板纯文本。
2. 分享流水线固定为「脱敏 → 预览 → 分享」：绝对路径/家目录/用户名/邮箱/密钥形状（AWS/OpenAI/GitHub/Slack/私钥/Bearer）先掩码；脱敏后仍命中 → `NF-E-002` 拒发（fail-closed）。
3. 脱敏实现 = `sanitize_text`/`sanitize_obj`（`app/cli/nf_app/security.py:336`），掩码记录随预览展示；`assert_share_safe`（`:392`）是拒发闸门。
4. 剪贴板回填 = 剪贴板/分享文本作为普通输入走 `nf-import/1`（DraftProject），不覆盖已有项目；回填内容与文件导入同一套解析硬化与上限。
5. 分享缓存只读 URI、可清理；端壳不得把缓存目录暴露给任意应用（FileProvider 路径限定）。

## 后果

**正面**

- 一入口多形态：md/zip/json/剪贴板覆盖「交付/归档/机读/即时粘贴」四场景。
- 脱敏前置 + 预览：泄露风险在分享动作之前处理，且可核对。
- 回填闭环：外部内容能重新进入作者流，不必手工重抄。

**负面 / 代价**

- 脱敏可能误伤合法内容（形似路径/密钥的正文），需人工确认与掩码记录。
- 剪贴板来源不可信：必须当不可信输入做解析硬化（zip/YAML/深度/大小）。
- 平台分享面板行为差异大（Android intent/Windows/macOS），端壳适配成本高且当前未建。

## 替代方案（及否决理由）

| 方案 | 结论 | 理由 |
|---|---|---|
| A. 直出原文分享 | 否决 | 无法保证脱敏；泄露本机路径/凭据 |
| B. 只出 Markdown | 否决 | 缺机读/归档/即时粘贴形态 |
| C. 云链接分享 | 否决 | 需账号与网络；违反离线/无账号 |
| D. 分享前仅警告不脱敏 | 否决 | 依赖用户逐条核对，不可复现 |

## 证据落点

| 证据 | 路径 / 判据 |
|---|---|
| 导出形态与 zip 确定性、manifest 口径 | `app/docs/CONTRACT.md` §5.8 |
| 分享/组件/FileProvider 安全纪律 | `app/docs/CONTRACT.md` §6 |
| 脱敏实现（邮箱/家目录/盘符路径/密钥模式） | `app/cli/nf_app/security.py:318-399` |
| 拒发闸门与错误码 | `app/cli/nf_app/security.py:392`；`app/schema/error_codes.json`（NF-E-002） |
| 回填走导入的格式 | `app/schema/nf-import.schema.json` |
| 门禁项（分享/回填用例，required=false） | `app/gates/gates.json` QA3 `q3-share` |

## 复审条件

- 新增分享形态（QR、图片、剪贴板富文本）时。
- 脱敏误伤率被实测偏高时（需可配置白名单，但白名单本身要评审）。
- 平台分享 API/权限模型变化时（Android 分区存储、macOS 沙箱）。

> 本 ADR 只声明决策与边界。实现状态以 `app/docs/ARCHITECTURE.md` §5/§11、`app/results/GATES.json` 与现场复跑命令为准；未落地项写 `OPEN`，不得据本 ADR 声称「已实现」。
