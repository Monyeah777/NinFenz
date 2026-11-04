---
id: AUD-0047
title: 元认知生产驾驶舱主仓融合
date: 2026-10-30
scope: 将元原子运行时、动态驾驶、事件溯源、上下文预算、A/B 与正式协议融合进主仓；并收口桥接 Path 参数根相对/类型闸门、包入口惰性加载、生成物原子写与 manifest 可复算；不调用外部模型，不伪造 HR-001。
verdict: pass
auditor: 本轮执行者
subjects:
  - desktop/src/core/cli_bridge.py:4247ed0e73dfc1ca319f6b9881f3b73a875b01ee6b24eda3d4fe861736cadad8
  - desktop/src/core/meta_cockpit/__init__.py:f31cbadd59e3f25aab850122bbcc4ad5adcf5a65596a38c4996f264a38427fd7
  - desktop/src/core/meta_cockpit/build_atom_menu.py:1bedd2efd340114f91442a41b6319f7a9e7f962996d49f656a132e45988dbf95
  - desktop/src/core/meta_cockpit/runtime_executor.py:204a67ec93855257323887011395b0866ac8d5ae1c485362e89eb058ffe64bfb
  - desktop/src/core/meta_cockpit/cockpit_service.py:18280c6966dd618a8b09daa058b461fa43f89e99f11c797ca884338ff5c13bbf
  - desktop/src/core/meta_cockpit/cockpit_ab.py:6afcade08f2469aad4adc6f44e0e3d28a17712a85e3223f41b14c0020c2f88e7
  - desktop/src/core/terminal.py:f07b761f94e3e04a2437bbe88b5d9e646f0a247d26c985486b287153bcae4570
  - desktop/tests/test_meta_cockpit.py:cc2dc4f52729b35f400ca92aa367e685780f9f6735224e7fc0b7550b85f52662
  - desktop/tests/test_cli_error_framing.py:4c186dc60b5e58bfe6c0400242051e14a8995bc7dad5399d68a85d8881d0e133
  - desktop/tests/test_nf_cli.py:18c407b6780205e50997d99ab9ea967e6ee066b2dca5d087e9eeea632d311804
  - scripts/nf.py:723bc8a01e98c2529058a0e16dabe1ad11b0846a6c01fa757829376ea3ab949f
  - tui/_surface.py:8db432e006d08b717d507deb8839e02e0db1ccacc3e4962a712045ccfd2a30bf
  - protocol/check12_weights.json:1389a73ef2fe904120f9f3a32578d8aec7159e776c624c5a5907c448b453821c
  - protocol/coupling_baseline.json:4f1b1ba0c5ecdfc4748ac4f30bc0f6016efaae01af8d4362dfbc96d0b635464a
  - docs/meta-cockpit/README.md:48b92addbaadc17d2bb845595bf39389269871026add1c597a8c71a0c2ca0aba
  - docs/meta-cockpit/功能解析.md:8bc9f97b3f067e11f2e3a8257e84e05845587624db8ee94de27ad10ef53a99a2
  - results/meta-cockpit-manifest.json:7b1231392bea0bc51ed14d73fac3c73c185209c1233e7727e554d5b899031af2

---
> 重审（2026-11-05）：受影响选片 v2（四类规则 + 文档目录前缀 + 硬兜底面）+ 纯函数判据

> 重审（2026-11-05）：G2 吊销分发件（签名 feed：签发/校验/合并，防回滚）+ nf.py 导入块排序

> 重审（2026-11-05）：label 声明层补登记（编码闸门/路径旗标）+ 删零引用函数

> 重审（2026-11-05）：cc_label 声明层（nf-label/1 IR）+ 供应链核对进发布结论

> 重审（2026-11-05）：G1 外部锚点：证据包可声明并可核对（防整链截断），双实现同口径 + 攻击矩阵 33 条

> 重审（2026-11-04）：H1 修复：--trust-repo 环境变量不再泄漏（信任门不再被绕过）+ 新增回归判据

> 重审（2026-11-04）：分片 1/8 抽检修复：编码闸门/路径旗标名单补全、删零引用常量与函数、耦合基线重冻

> 重审（2026-11-04）：证据线 fail-closed 加固：chain 段必填 / 吊销表坏件判 invalid（攻击矩阵 25→29）

> 重审（2026-11-04）：抽检第二个分片：原子写纪律（包/报告走 atomic_write，临时写例外登记）

> 重审（2026-11-04）：check12 修复波：JSON 面登记 / json_doc 收敛 / Rust 回执去重同步 / 基准 JSON 纯净

> 重审（2026-11-04）：本地 HTTP 面 v0（nf serve --http 三端点）落地 + 端点契约登记 local.*

> 重审（2026-11-04）：cc_resolve（契约面反查）+ 一条链复现脚本落地

> 重审（2026-11-04）：cc_replay 轨迹 + cc_check 单对象策略体检落地（新模块 check_policy）+ 回执去重

> 重审（2026-11-04）：证据复验器扩三种形态 + 攻击矩阵基准（26 项校验路径与基准落地）

> 重审（2026-11-04）：证据包缺省落点改到临时目录（不往仓库落盘）+ CCOS ABI v0 收口

> 重审（2026-11-04）：CCOS ABI v0 + 证据包校验器落地（scripts/nf.py 与 core/terminal.py 摘要变更；并修复本分支既有漂移）

> 重审（2026-10-30）：新增契约级 Git 演进时间线；结构化 Markdown YAML 字段与 JSON schema 差异纳入影响度

> 重审（2026-10-30）：全仓审计口径复核：显式 legacy 清单、subjects 根内解析、Path 参数闸门、惰性导入与 manifest 可复算

> 重审（2026-10-30）：桥接 Path 参数统一根相对与类型闸门；公共子模块惰性加载；生成菜单原子写；入仓 manifest 增加实时复算判据

> 重审（2026-10-29）：CLI 命令树无损分组、meta-cockpit 接线与恢复分支全量验证后重绑；既有结论不变

> 重审（2026-10-29）：恢复分支全量验证：纯度修复、零引用清理、public API 接线、ReDoS/CLI 闸门/文档路径与模板示例修复

> 重审（2026-10-29）：恢复分支全量验证：接线 meta-cockpit 公共模块、清理零引用、修复 ReDoS/CLI 闸门/公开文档路径后重绑；既有结论不变


# 元认知生产驾驶舱主仓融合审计

> 日期：2026-10-30
> 范围：`desktop/src/core/meta_cockpit/`、CLI 桥、终端命令族与自动化测试
> Machine digest：`59357b7056a68bfbd64cdd85333aadfb95c34fdf06f1216563cee56f5e01ce5c`
> Manifest digest：`c9469a7f54041e7c041e353a768bad98054b72bcb4775639f7463754b985abfc`

## 结果

- 33/33 原子执行器在场，14 个方法节点、10 节点内容管线与 5 节点元管线可加载执行。
- 元管线好样本 PASS：5 节点、17 个原子轨迹全部 PASS。
- 六类 fail-closed 突变均被抓：缺执行器、无效方法路由、预算耗尽、缺判据、未知任务类型、输出类型不匹配。
- 动态驾驶验证：不同任务/注入产生不同 need 序列，状态完成且轨迹无 `score`。
- 事件账本验证：提交后可加载、哈希链校验通过、确定性重放与当前状态一致。
- A/B 验证：预注册、盲包、功效分析、强效应、重复 ballot 拒绝、bundle/store 往返均通过。
- 发布清单验证：运行代码、契约、协议与正式说明纳入统一 digest；HR-001 保持 `PENDING`。
- CLI 入口验证：`nf cockpit` 与 `nf cockpit-ab` 可发现、可帮助、可执行；终端能力族与生成投影同步。

## 验证证据

| 检查 | 结果 |
|---|---|
| `tests.test_meta_cockpit` | 11/11 PASS |
| 最终受影响合并集 | 292/292 PASS |
| 终端/TUI/代码度量/权重/文本卫生受影响集 | 233/233 PASS |
| CLI/JSON 形状/耦合/模块命名受影响集 | 79/79 PASS |
| Ruff | PASS |
| 风格棘轮 | 10022 ≤ 基线 10032 |
| 代码规模 | 310 文件；最大行数 7643；最长函数 1262；最大复杂度 116 |
| 耦合 | 0 未登记环；258 模块；SDP 10/10 登记 |
| 元管线运行 | `PENDING-REVIEW`，机器层 PASS |

## 遗留边界

- HR-001 必须由作者或指定复核人签字，本审计未生成 approve 记录。
- 真实跨模型、多 seed A/B 未运行；不宣称已测得质量增量。
- 语义真伪仍由人工复核兜底。
- 工作区存在本次任务前已有的并发修改；本轮未执行 stash、reset、restore 或清理。

## 设计偏差

- 内部原型使用扁平模块导入与 `D:\\NinFenz` 绝对路径；主仓版本改为 `core.meta_cockpit` 包、相对导入和仓库根推导。
- 内部一次性 spike 脚本未直接入库；高价值断言已转为主仓 unittest 契约。
- `jsonschema` 作为可选标准实现使用；缺失时退回主仓确定性 JSON Schema 子集并 fail-closed。
