# L3 端壳层退役记录（23 方案分层治理真相源 · 2026-09-09 永久退役）

> **最后复核：2026-11-13**——退役清单的「不在树」与「保留件在场」经全量核对仍成立；CI 现状段补列 5 个此前未点名的 workflow（docker-nfal / external-links / gitee-poll / library-ingest / npm-publish，共 22 个）。本文件是**依赖治理编号**（L0–L3），与抽象阶梯（`docs/layers.md`）互不替代、并置互链。

> **Status**：~~冻结-接线脉冲契约~~ → **2026-09-09 永久退役（作者裁决）**：桌面 GUI 端壳与打包/发布线彻底移出公开面，**不再有接线波**——与 android 线（裁决 #16）同轨。git 历史完整可回溯；**退役后的人机入口 = 终端 `nf shell`**（`docs/terminal.md`），残留回潮由 verify check39 判红。本文件的 L0–L3 是**依赖治理编号**，与抽象阶梯（四阶 + 入口面 + 验证纵切，见 `docs/layers.md`）互不替代、并置互链。
> **契约史**：23 方案分层治理（L0 协议 / L1 内容 / L2 core / L3 端壳）→ 38 方案 F2 三问裁决（2026-09-06：冻结-接线-冻结脉冲节奏，决策档案 docs_f2-decision-steelman.md）→ 第 1 波接线 v2.6 收口（2026-09-06，commit 序列 51f7130→5a3c0e4，smoke_gui 22/22 + build-desktop/build-android 干跑）→ 波后回冻结 → **2026-09-09 作者裁决永久退役**（W33 移出 + 本地清理波收尾）。
> **APK 线移除记录（裁决 #16，2026-09-07）**：Android APK 线**彻底移除**——`git rm` android/（含 app bootstrap/config/controller/ui/screens/main/buildozer/p4a 补丁）+ build-android.yml + selftest_android.py + sync_android.sh；check_ui_core_links 同步去 android 化。理由 = 包络负资产：首次构建 10h+、v0.8/v0.9/v2.6 三轮闪退修复、CI 绿 ≠ 真机不闪退、作者学生预算月投入数百；APK 三大功能（浏览/预览/轻导出）已被 AI 线（A/B1）全覆盖。**不再恢复（git 历史可回溯）**。
> **桌面端壳退役记录（2026-09-09，作者裁决「清掉，保持干净」）**：W33（f8123b6 移出 desktop/src/ui 全量 + 壳打包脚本 + build-desktop.yml + UI 测试/检查脚本）+ 清理波（9b6a443/b5b7e90 后续 commit）`git rm` desktop/main.py + desktop/src/__main__.py + desktop/packaging/（spec/README）+ desktop/scripts/smoke_gui.py/bench.py + scripts/smoke_zone_g_market.py。理由 = 端壳包络能力已被 **CLI（scripts/nf.py：run/import/assemble/serve…）+ AI 装配线（AGENT_START/组装指令包）全覆盖**；PySide6 三平台打包与 UI 测试同步维护负担与 APK 线同型；公开面一致性（README/community 已无桌面工具叙事）。**不再恢复**。

## 分层定义（23 方案，退役后现状）

| 层 | 仓库载体 | 本质 | 演进节奏 |
|---|---|---|---|
| L0 协议层 | 01/02 + 文档链 | 单一事实源声明 | 随变更演进 |
| L1 内容层 | 03/04/05（管线/模块/资产库）+ community/ | 数据 | 随变更演进 |
| L2 核心逻辑层 | desktop/src/core（纯 Python 零第三方依赖）+ scripts/nf.py | 真身 | **高频迭代（主战场）** |
| L3 端壳层 | ~~desktop GUI + 打包线~~（Android #16；桌面 2026-09-09） | 包络 | **已退役——不再接线** |

**战略依据（历史）**：端壳是包络层，基础层才是真身。分层后基础层可高频迭代，端壳只在触发条件达成时执行「批量接线 + Release 产出」。2026-09-09 后该层整体退役——基础层（协议 + core + CLI + AI 装配）已自足，仓库不再产桌面壳。

## 本文件 = 退役清单索引 + 保留边界

**2026-09-05 首次移出主仓库演进主线**（commit `5ae202b`）→ **2026-09-07 android 彻底移除（#16）** → **2026-09-09 桌面端壳彻底移除（作者裁决）**：

- ~~`android/`（入库部分 13 文件）~~——**【已彻底移除·裁决 #16·2026-09-07·不再恢复】**
- ~~`desktop/src/ui/`（11 py：common/main_window/protocol_wizard_dialog/zone_a-g）~~——**【已彻底移除·2026-09-09·不再恢复】**
- ~~`desktop/main.py` + `desktop/src/__main__.py`（GUI 入口，import src.ui）~~——**【同上】**
- ~~`desktop/packaging/`（narrative_forge.spec + build_linux/macos.sh + README）~~——**【同上】**
- ~~`desktop/scripts/smoke_gui.py` + `desktop/scripts/bench.py`（GUI 冒烟/基准，import src.ui/PySide6）~~——**【同上】**
- ~~`scripts/smoke_zone_g_market.py`（E5 UI 冒烟，import src.ui.main_window）~~——**【同上】**
- ~~`scripts/selftest_android.py` + `scripts/sync_android.sh`~~——**【已彻底移除·裁决 #16·2026-09-07·不再恢复】**
- ~~`.github/workflows/build-desktop.yml` + `build-android.yml`~~——**【已彻底移除·不再恢复】**

**保留（L2/L1/L0，不受影响）**：`desktop/src/core/` 全量、`desktop/tests/` 全量、`desktop/scripts/seed_from_repo.py`（种子导入器，保留）、根 `scripts/e2e_desktop_headless.py`（headless core 直驱 E2E，CI e2e-desktop.yml 在跑）、`scripts/reconcile_assets.sh`。

## 声明 ⇄ 机检面

| 声明 | 机检 / 真源 |
|---|---|
| 端壳件不再回潮 | `verify.sh` **check39**（端壳退役零回潮：文件名/路径再现即红） |
| 人机入口 = 终端 `nf shell` | check39 断言 `nf shell` 入口在场；`docs/terminal.md` |
| 公开面无桌面工具指引 | `doc_hygiene`（白名单/标识面）+ 人工复核；README/community 已清零 |
| 退役件可回溯 | git 历史（commit 序列见上）；不删除历史 |
| L0–L3 与阶梯面互不替代 | 本文件 ↔ `docs/layers.md` 互链；`protocol/LAYERS.json` 为阶梯真源 |

## 使用与复现口径

```bash
python scripts/nf.py explain check39    # 端壳零回潮 + 终端入口判据口径
python scripts/nf.py shell --help       # 退役后人机入口（终端）
bash verify.sh --checks-only            # 静态门禁（含 check39）
```

- 引用本文件时：L0–L3 是**依赖治理编号**；「已退役/不再恢复」= 长期口径，恢复须作者新裁决另立项。
- 核对方式：退役清单逐条 `test -e` 应为假；保留清单逐条应为真；`check39` 与 `doc_hygiene` 常驻。

## 治理同步（现状）

- verify.sh v2.30：默认锁 L0-L2，clone 即绿零前置；check12 = desktop core/tests unittest 全量 + 全量 py_compile（端壳文件已不在树，compile 面随退役收窄）。
- CI（2026-11-13 复核 · 共 22 个 workflow）：**required** = `static-checks-42`（ci-verify.yml）与 `gate`（分支保护）；另有 coverage.yml（core ≥80%）、sast.yml / lint.yml / dependency-audit.yml / scorecard.yml（静态与供应链面）、cross-lang.yml（跨语言矩阵）、cross-platform.yml（Win/Linux/macOS 三平台 verify --full）、rust-crate.yml（Rust 主 crate + PyO3；ubuntu+windows）、dotnet-build.yml（.NET 引擎；ubuntu+windows）、e2e-desktop.yml（headless core 直驱，无需 GUI）、release-gate.yml（v* tag 即跑 verify+基线+覆盖率）；辅助：linux-parity-refresh.yml（周检跨平台漂移）、ci-health.yml（schedule 静默红看门狗）、npm-package-check.yml（payload stage/verify 的 PR 面）、codeql.yml（代码扫描：python+js/ts）、net-probes.yml（手动跑批，需金标快照 ref，见 task-34）、docker-nfal.yml（容器面）、external-links.yml（外链巡检）、gitee-poll.yml（Gitee 投稿轮询）、library-ingest.yml（GitHub 投稿入库）、npm-publish.yml（npm 发布）。
- 门禁完整性事实（2026-11-09 三处实测修复，均有源码守卫测试）：① 所有 `| tee` 步骤必须 `shell: bash`（GitHub 默认 `bash -e` 无 pipefail，退出码被 tee 吞 → SAST 门禁曾假绿）；② `gate` 必须 `if: always()` 并显式校验 `needs.*.result`（required check 的 skipped 视为通过，曾放行测试红）；③ `linux-parity-refresh` 的 posix SAST 漂移判定逐键比对（只比总数会漏「一规则 +1、另一规则 -1」）。
- Actions 版本（2026-11-09 升级，node24 面）：`actions/checkout` **v7**（3d3c42e5…）、`actions/setup-python` **v6**（ece7cb06…）、`actions/upload-artifact` **v7**（cf430e03…）、`github/codeql-action` **v4**（33d7b85d…）——全部 pin SHA；升级前是 node20 版（被 runner 强制跑 Node 24，annotation 已警告）。
- 分支保护事实（2026-11-08 API 核对 `/branches/main/protection`）：required checks = `static-checks-42` + `gate`（**strict**：分支须与 main 同步才算过）；`enforce_admins=true`（管理员同样受约束）；`required_linear_history=true`（禁 merge commit，只能 squash/rebase）；禁 force push / 删分支；必须解决会话（required_conversation_resolution）；`required_approving_review_count=0`（无强制评审，允许自动合并）。

## 纪律（退役后）

- **端壳线不预设恢复**：新 GUI/新壳形态须作者新裁决后另行立项（不复用本文件路径，不沿用冻结脉冲机制）。
- **L2 core 是唯一真身**：新增能力无端壳同步义务；能力入口一律落 CLI（nf.py）与文档/AI 装配线。
- **公开面一致性**：任何文档不得再出现桌面工具下载/运行/打包指引（README/community 已清零，回归由 doc_hygiene 与人工检查共同兜底）。
